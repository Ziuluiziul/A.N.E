"""Projeção viva do corpus, sem transformar eventos de filesystem em verdade.

O filesystem só avisa que algo pode ter mudado. A mudança publicada é outra coisa:
uma projeção completa, válida e estável entre duas leituras do manifesto. Assim um
``touch`` não cria revisão, e um arquivo observado no meio da gravação não substitui
a última visão íntegra que o Atlas já tinha.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from watchfiles import Change, awatch

from vault.corpus.identity import CorpusIdentityError
from vault.corpus.reader import CorpusReader
from vault.layout_store import LayoutStore
from vault.projection import ProjectionError, build_projection, corpus_fingerprint

WATCH_DEBOUNCE_MS = 250
WATCH_STEP_MS = 50
WATCH_STOP_TIMEOUT_MS = 250
STABLE_READ_ATTEMPTS = 3


class ProjectionUnavailable(RuntimeError):
    """Ainda não existe uma projeção válida para servir."""


class CorpusChangedDuringProjection(RuntimeError):
    """O corpus continuou mudando durante todas as tentativas de leitura."""


@dataclass(frozen=True, slots=True)
class CorpusEvent:
    kind: Literal["current", "changed", "error", "recovered"]
    fingerprint: str | None
    revision: int
    detail: str | None = None

    def to_dict(self) -> dict[str, str | int | None]:
        return {
            "fingerprint": self.fingerprint,
            "revision": self.revision,
            "detail": self.detail,
        }


def _markdown_only(_change: Change, path: str) -> bool:
    """Eventos irrelevantes podem existir sob a raiz; só Markdown forma o corpus."""
    return Path(path).suffix.lower() == ".md"


class CorpusProjectionWatcher:
    """Mantém a última projeção válida e publica transições observadas."""

    def __init__(
        self,
        corpus_dir: Path,
        layout_store: LayoutStore,
        *,
        demo_operational: bool = False,
    ) -> None:
        self.corpus_dir = Path(corpus_dir).resolve()
        self.layout_store = layout_store
        self.demo_operational = demo_operational
        self._projection: dict[str, Any] | None = None
        self._fingerprint: str | None = None
        self._last_error: str | None = None
        self._recoverable_error = False
        self._revision = 0
        self._subscribers: set[asyncio.Queue[CorpusEvent]] = set()
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        # `refresh` atravessa `await` e escreve estado compartilhado. Hoje só o laço
        # de observação o chama, em sequência, então não há corrida — o lock existe
        # para que a sequencialidade seja invariante do método, e não consequência de
        # quem por acaso o invoca.
        self._refresh_lock = asyncio.Lock()

    @property
    def fingerprint(self) -> str | None:
        return self._fingerprint

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def projection(self) -> dict[str, Any]:
        if self._projection is None:
            raise ProjectionUnavailable(self._last_error or "projeção ainda não calculada")
        return self._projection

    async def start(self) -> None:
        """Calcula o estado inicial e inicia exatamente uma tarefa de observação."""
        if self._task is not None:
            return
        await self.refresh()
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._watch(), name="vault-corpus-watcher")

    async def stop(self) -> None:
        """Encerra a tarefa própria sem procurar nem matar processos alheios."""
        task = self._task
        if task is None:
            return
        self._stop_event.set()
        with suppress(asyncio.CancelledError):
            await task
        self._task = None

    async def refresh(self) -> bool:
        """Tenta publicar uma projeção nova; preserva a anterior em qualquer falha."""
        async with self._refresh_lock:
            return await self._refresh_locked()

    async def _refresh_locked(self) -> bool:
        try:
            candidate = await asyncio.to_thread(self._build_stable_projection)
        except asyncio.CancelledError:
            raise
        except Exception as error:  # O watcher não pode morrer por uma gravação parcial.
            self._last_error = self._safe_error(error)
            self._recoverable_error = True
            self._publish(
                CorpusEvent("error", self._fingerprint, self._revision, self._last_error)
            )
            return False

        new_fingerprint = str(candidate["meta"]["corpusFingerprint"])
        if new_fingerprint == self._fingerprint:
            # ``generatedAt`` muda a cada build, mas não é revisão de corpus. Retemos
            # o mesmo objeto para que um touch não altere nem payload nem chave.
            recovered = self._recoverable_error and self._last_error is not None
            if recovered:
                self._last_error = None
                self._recoverable_error = False
                self._publish(
                    CorpusEvent(
                        "recovered",
                        self._fingerprint,
                        self._revision,
                        "corpus válido novamente; projeção anterior permaneceu íntegra",
                    )
                )
            return False

        # Origem da reconciliação. Em sessão viva é a impressão que este processo
        # publicou; no primeiro cálculo depois de um reinício, é a que ficou anotada
        # no disco. Sem ela, um corpus editado com o backend desligado apareceria sem
        # posição nenhuma — o mapa mental morreria no encerramento do processo.
        old_fingerprint = self._fingerprint
        if old_fingerprint is None:
            old_fingerprint = await asyncio.to_thread(self.layout_store.last_fingerprint)
        known_ids = {
            str(node["id"])
            for node in candidate["nodes"]
            if node.get("layer") == "epistemic"
        }
        memory_error: str | None = None
        if old_fingerprint is not None:
            try:
                await asyncio.to_thread(
                    self.layout_store.carry_forward,
                    old_fingerprint,
                    new_fingerprint,
                    known_ids=known_ids,
                )
            except asyncio.CancelledError:
                raise
            except Exception as error:
                # Layout é cache derivado. Sua falha precisa ser visível, mas nunca
                # pode governar qual versão válida do corpus a API serve.
                memory_error = (
                    f"{type(error).__name__}: memória espacial não reconciliada; "
                    "a projeção nova foi publicada"
                )

        try:
            await asyncio.to_thread(self.layout_store.remember_fingerprint, new_fingerprint)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            # O ponteiro é cache derivado, como o próprio layout: perdê-lo custa a
            # memória espacial no próximo reinício, e nada mais. Não pode decidir
            # qual versão do corpus a API serve.
            memory_error = memory_error or (
                f"{type(error).__name__}: última impressão espacial não anotada; "
                "a projeção nova foi publicada"
            )

        self._projection = candidate
        self._fingerprint = new_fingerprint
        self._last_error = memory_error
        self._recoverable_error = False
        self._revision += 1
        self._publish(CorpusEvent("changed", new_fingerprint, self._revision))
        if memory_error is not None:
            self._publish(
                CorpusEvent("error", new_fingerprint, self._revision, memory_error)
            )
        return True

    async def events(self) -> AsyncGenerator[CorpusEvent]:
        """Entrega o estado atual na conexão e depois as mudanças deste processo."""
        queue: asyncio.Queue[CorpusEvent] = asyncio.Queue(maxsize=8)
        self._subscribers.add(queue)
        try:
            initial_fingerprint = self._fingerprint
            initial_revision = self._revision
            initial_error = self._last_error
            if initial_fingerprint is not None:
                yield CorpusEvent("current", initial_fingerprint, initial_revision)
                if initial_error is not None:
                    yield CorpusEvent(
                        "error",
                        initial_fingerprint,
                        initial_revision,
                        initial_error,
                    )
            elif initial_error is not None:
                yield CorpusEvent("error", None, initial_revision, initial_error)
            while True:
                yield await queue.get()
        finally:
            self._subscribers.discard(queue)

    async def _watch(self) -> None:
        try:
            async for _changes in awatch(
                self.corpus_dir,
                watch_filter=_markdown_only,
                debounce=WATCH_DEBOUNCE_MS,
                step=WATCH_STEP_MS,
                stop_event=self._stop_event,
                rust_timeout=WATCH_STOP_TIMEOUT_MS,
            ):
                await self.refresh()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._last_error = self._safe_error(error)
            self._recoverable_error = True
            self._publish(
                CorpusEvent("error", self._fingerprint, self._revision, self._last_error)
            )

    def _build_stable_projection(self) -> dict[str, Any]:
        for _attempt in range(STABLE_READ_ATTEMPTS):
            reader = CorpusReader(self.corpus_dir)
            before = corpus_fingerprint(reader)
            candidate = build_projection(reader, demo_operational=self.demo_operational)
            after = corpus_fingerprint(reader)
            if before == after == candidate["meta"]["corpusFingerprint"]:
                return candidate
        raise CorpusChangedDuringProjection(
            "o corpus continuou mudando durante o cálculo; a última projeção válida foi mantida"
        )

    def _safe_error(self, error: Exception) -> str:
        # Erro de ontologia já fala em identidades sanitizadas e é útil ao editor. As
        # demais exceções podem conter caminho absoluto ou até um trecho de YAML no
        # texto produzido pela biblioteca, então o SSE expõe somente a classe segura.
        if isinstance(error, (ProjectionError, CorpusChangedDuringProjection)):
            return str(error)
        if isinstance(error, CorpusIdentityError):
            return "CorpusIdentityError: identidade do corpus inválida; rode `make audit`"
        return f"{type(error).__name__}: atualização rejeitada; última projeção válida mantida"

    def _publish(self, event: CorpusEvent) -> None:
        for queue in tuple(self._subscribers):
            if queue.full():
                with suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            queue.put_nowait(event)
