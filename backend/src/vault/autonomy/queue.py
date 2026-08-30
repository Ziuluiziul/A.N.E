"""Fila privada, atômica e recuperável do worker autônomo."""

from __future__ import annotations

import fcntl
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from vault.autonomy.models import (
    ATTEMPTS_WINDOW,
    AutonomousTask,
    TaskAttempt,
    TaskState,
    now,
)
from vault.runtime_io import read_private_json, write_private_json

_PRIVATE_FILE_MODE = 0o600


class QueueError(RuntimeError):
    pass


class WorkerAlreadyRunning(QueueError):
    pass


class QueueSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    revision: int = Field(default=0, ge=0)
    tasks: list[AutonomousTask] = Field(default_factory=list, max_length=10_000)


def _updated(task: AutonomousTask, **changes: Any) -> AutonomousTask:
    payload = task.model_dump(mode="json")
    payload.update(changes)
    payload["updated_at"] = now()
    return AutonomousTask.model_validate(payload)


class PersistentTaskQueue:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.path.parent.chmod(0o700)
        self._lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self._worker_lock_path = self.path.with_suffix(self.path.suffix + ".worker.lock")

    @contextmanager
    def worker_lease(self) -> Iterator[None]:
        """Impede dois workers de recuperarem/executarem a mesma fila ao mesmo tempo."""
        descriptor = os.open(
            self._worker_lock_path,
            os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW,
            _PRIVATE_FILE_MODE,
        )
        locked = False
        try:
            os.fchmod(descriptor, _PRIVATE_FILE_MODE)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise WorkerAlreadyRunning(
                    "já existe um worker ativo para esta fila"
                ) from error
            locked = True
            yield
        finally:
            if locked:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    @contextmanager
    def _lock(self) -> Iterator[None]:
        descriptor = os.open(
            self._lock_path,
            os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW,
            _PRIVATE_FILE_MODE,
        )
        locked = False
        try:
            os.fchmod(descriptor, _PRIVATE_FILE_MODE)
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            locked = True
            yield
        finally:
            if locked:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _read(self) -> QueueSnapshot:
        raw = read_private_json(self.path)
        if raw is None:
            if self.path.exists():
                raise QueueError(f"fila ausente ou ilegível: {self.path}")
            return QueueSnapshot()
        try:
            return QueueSnapshot.model_validate(raw)
        except ValueError as error:
            raise QueueError(f"fila inválida: {self.path}") from error

    def _write(self, snapshot: QueueSnapshot) -> None:
        write_private_json(self.path, snapshot.model_dump(mode="json"))

    @staticmethod
    def _replace(snapshot: QueueSnapshot, tasks: list[AutonomousTask]) -> QueueSnapshot:
        return QueueSnapshot(revision=snapshot.revision + 1, tasks=tasks)

    def snapshot(self) -> QueueSnapshot:
        with self._lock():
            return self._read().model_copy(deep=True)

    def add_new(self, candidates: list[AutonomousTask]) -> list[AutonomousTask]:
        """Acrescenta identidades inéditas; tarefa terminal não renasce sem evidência nova."""
        with self._lock():
            snapshot = self._read()
            known = {task.id for task in snapshot.tasks}
            added = [task for task in candidates if task.id not in known]
            if not added:
                return []
            self._write(self._replace(snapshot, [*snapshot.tasks, *added]))
            return added

    def retire_unclaimable(
        self,
        *,
        accept: Callable[[AutonomousTask], bool],
        reason: str,
        dry_run: bool = True,
    ) -> list[AutonomousTask]:
        """Aposenta o que nunca mais será reivindicado, sem apagar registro nenhum.

        Depois de `ddf465e`, meta-tarefa sem nota herdada é permanentemente recusada por
        `can_start`. Ela não gasta chamada — mas ocupa a fila: 157 das 263 tarefas, 102
        delas ainda em estado reivindicável, que o `claim` percorre e descarta a cada
        ciclo. É inventário morto, e confiar em o filtro nunca mudar é frágil.

        O estado vira `rejected` e o motivo fica no metadado: a identidade permanece, e
        `add_new` continua recusando recriá-la. **Nada é removido** — o histórico de
        tentativas de cada tarefa é o insumo do ledger de desfechos.

        `dry_run` é o padrão de propósito: mudar de estado 102 registros de uma vez é
        operação de manutenção, e quem a dispara decide, não quem a implementa.
        """
        with self._lock():
            snapshot = self._read()
            alvos = [
                task
                for task in snapshot.tasks
                if task.state in {TaskState.QUEUED, TaskState.RETRY_WAIT} and accept(task)
            ]
            if dry_run or not alvos:
                return alvos
            aposentadas = {task.id for task in alvos}
            tasks: list[AutonomousTask] = []
            resultado: list[AutonomousTask] = []
            for task in snapshot.tasks:
                if task.id not in aposentadas:
                    tasks.append(task)
                    continue
                metadata = dict(task.metadata)
                metadata["retired_reason"] = reason[:200]
                aposentada = _updated(
                    task,
                    state=TaskState.REJECTED.value,
                    next_eligible_at=None,
                    metadata=metadata,
                )
                resultado.append(aposentada)
                tasks.append(aposentada)
            self._write(self._replace(snapshot, tasks))
            return resultado

    def reopen_blocked(
        self,
        *,
        outcomes: frozenset[str],
        state: Literal["queued", "retry_wait"] = "queued",
        next_eligible_at: str | None = None,
    ) -> list[AutonomousTask]:
        """Reabre blocked operacional. A identidade permanece; add_new continua recusando."""
        target = TaskState(state)
        if target is TaskState.RETRY_WAIT and next_eligible_at is None:
            raise QueueError("retry_wait exige próxima janela elegível")
        with self._lock():
            snapshot = self._read()
            reopened: list[AutonomousTask] = []
            tasks: list[AutonomousTask] = []
            for task in snapshot.tasks:
                last = task.attempts[-1] if task.attempts else None
                if (
                    task.state is not TaskState.BLOCKED
                    or last is None
                    or last.outcome not in outcomes
                ):
                    tasks.append(task)
                    continue
                revived = _updated(
                    task,
                    state=target.value,
                    next_eligible_at=next_eligible_at,
                )
                reopened.append(revived)
                tasks.append(revived)
            if reopened:
                self._write(self._replace(snapshot, tasks))
            return reopened

    def recover_interrupted(self) -> list[AutonomousTask]:
        """Reabre trabalho que ficou em voo quando o processo morreu."""
        with self._lock():
            snapshot = self._read()
            recovered: list[AutonomousTask] = []
            tasks: list[AutonomousTask] = []
            for task in snapshot.tasks:
                if task.state not in {TaskState.ASSIGNED, TaskState.RUNNING}:
                    tasks.append(task)
                    continue
                attempts = list(task.attempts)
                if attempts and attempts[-1].finished_at is None:
                    attempts[-1] = attempts[-1].model_copy(
                        update={
                            "finished_at": now(),
                            "outcome": "interrupted",
                            "detail": "processo terminou antes de registrar o desfecho",
                        }
                    )
                reopened = _updated(
                    task,
                    state=TaskState.QUEUED.value,
                    next_eligible_at=None,
                    attempts=[attempt.model_dump(mode="json") for attempt in attempts],
                )
                recovered.append(reopened)
                tasks.append(reopened)
            if recovered:
                self._write(self._replace(snapshot, tasks))
            return recovered

    def claim(
        self,
        *,
        at: str | None = None,
        accept: Callable[[AutonomousTask], bool] | None = None,
    ) -> AutonomousTask | None:
        moment = at or now()
        with self._lock():
            snapshot = self._read()
            eligible = [
                task
                for task in snapshot.tasks
                if (
                    task.state is TaskState.QUEUED
                    or (
                        task.state is TaskState.RETRY_WAIT
                        and task.next_eligible_at is not None
                        and task.next_eligible_at <= moment
                    )
                )
                and (accept is None or accept(task))
            ]
            if not eligible:
                return None
            chosen = min(eligible, key=lambda task: (-task.priority, task.created_at, task.id))
            claimed = _updated(
                chosen,
                state=TaskState.ASSIGNED.value,
                next_eligible_at=None,
            )
            tasks = [claimed if task.id == chosen.id else task for task in snapshot.tasks]
            self._write(self._replace(snapshot, tasks))
            return claimed

    def start(self, task_id: str) -> AutonomousTask:
        with self._lock():
            snapshot = self._read()
            task = self._find(snapshot, task_id)
            if task.state is not TaskState.ASSIGNED:
                raise QueueError(f"tarefa {task_id} não está atribuída: {task.state.value}")
            attempts = [*task.attempts, TaskAttempt()]
            # A janela do histórico é a do contrato: quem ultrapassa cai por fora,
            # e a mais antiga cai primeiro. Aparar aqui mantém a invariante no
            # ponto em que ela nasce, sem depender do validador aparar na leitura.
            if len(attempts) > ATTEMPTS_WINDOW:
                attempts = attempts[-ATTEMPTS_WINDOW:]
            running = _updated(
                task,
                state=TaskState.RUNNING.value,
                attempts=[attempt.model_dump(mode="json") for attempt in attempts],
            )
            self._write(
                self._replace(
                    snapshot,
                    [running if item.id == task_id else item for item in snapshot.tasks],
                )
            )
            return running

    def defer_claimed(
        self,
        task_id: str,
        *,
        detail: str,
        next_eligible_at: str,
    ) -> AutonomousTask:
        """Devolve uma atribuição à espera sem inventar uma tentativa de modelo.

        Backpressure é decisão do escalonador tomada antes de qualquer chamada. Se
        entrasse em ``attempts``, um processo com o orçamento já consumido acabaria
        bloqueando a tarefa só por continuar vivo.
        """
        with self._lock():
            snapshot = self._read()
            task = self._find(snapshot, task_id)
            if task.state is not TaskState.ASSIGNED:
                raise QueueError(f"tarefa {task_id} não está atribuída: {task.state.value}")
            metadata = dict(task.metadata)
            metadata["last_backpressure"] = detail[:1_000]
            deferred = _updated(
                task,
                state=TaskState.RETRY_WAIT.value,
                next_eligible_at=next_eligible_at,
                metadata=metadata,
            )
            self._write(
                self._replace(
                    snapshot,
                    [deferred if item.id == task_id else item for item in snapshot.tasks],
                )
            )
            return deferred

    def finish(
        self,
        task_id: str,
        *,
        state: Literal["completed", "rejected", "blocked", "retry_wait"],
        outcome: str,
        detail: str = "",
        endpoints: list[str] | None = None,
        panel_id: str | None = None,
        next_eligible_at: str | None = None,
    ) -> AutonomousTask:
        target_state = TaskState(state)
        with self._lock():
            snapshot = self._read()
            task = self._find(snapshot, task_id)
            if task.state not in {TaskState.RUNNING, TaskState.ASSIGNED}:
                raise QueueError(f"tarefa {task_id} não está em execução: {task.state.value}")
            attempts = list(task.attempts)
            if not attempts or attempts[-1].finished_at is not None:
                attempts.append(TaskAttempt())
            attempts[-1] = attempts[-1].model_copy(
                update={
                    "finished_at": now(),
                    "endpoints": list(dict.fromkeys(endpoints or [])),
                    "outcome": outcome[:80],
                    "detail": detail[:1_000],
                    "panel_id": panel_id,
                }
            )
            finished = _updated(
                task,
                state=target_state.value,
                next_eligible_at=next_eligible_at,
                attempts=[attempt.model_dump(mode="json") for attempt in attempts],
            )
            self._write(
                self._replace(
                    snapshot,
                    [finished if item.id == task_id else item for item in snapshot.tasks],
                )
            )
            return finished

    @staticmethod
    def _find(snapshot: QueueSnapshot, task_id: str) -> AutonomousTask:
        for task in snapshot.tasks:
            if task.id == task_id:
                return task
        raise QueueError(f"tarefa inexistente: {task_id}")
