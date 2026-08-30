"""Tarefa, atribuição e resultado. As três coisas que o orquestrador move.

Uma tarefa é independente das outras: nada aqui encadeia execução, porque tarefa que
depende de tarefa vira fila serial e um modelo lento trava o resto. Dependência real,
quando existir, é modelada como tarefa nova criada depois do resultado — não como
espera dentro desta.

`Assignment` é a decisão registrada antes da chamada: qual endpoint, qual papel, por
qual motivo. Guardar o motivo é o que permite auditar uma escolha ruim sem reconstruir
o estado do inventário naquele instante.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from vault.work.roles import Role, get_role

MAX_PROMPT_CHARS = 48_000


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class TaskRefused(ValueError):
    """Tarefa malformada não entra na fila; entrar e falhar depois é pior."""


@dataclass(frozen=True, slots=True)
class Task:
    """Uma unidade de trabalho, com o papel que a executa já decidido."""

    kind: str
    role_name: str
    prompt: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = field(default_factory=now)
    max_output_tokens: int = 512
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.kind.strip():
            raise TaskRefused("tarefa sem tipo")
        if not self.prompt.strip():
            raise TaskRefused("tarefa sem prompt")
        if len(self.prompt) > MAX_PROMPT_CHARS:
            raise TaskRefused(
                f"prompt com {len(self.prompt)} caracteres excede {MAX_PROMPT_CHARS}"
            )
        if self.max_output_tokens <= 0:
            raise TaskRefused("max_output_tokens precisa ser positivo")
        get_role(self.role_name)  # levanta cedo se o papel não existir

    @property
    def role(self) -> Role:
        return get_role(self.role_name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "role": self.role_name,
            "created_at": self.created_at,
            "max_output_tokens": self.max_output_tokens,
            "prompt": self.prompt,
            "context": self.context,
        }


@dataclass(frozen=True, slots=True)
class Assignment:
    """A decisão de mandar esta tarefa para este endpoint, e o porquê."""

    task: Task
    provider: str
    endpoint_id: str
    reason: str

    @property
    def key(self) -> str:
        return f"{self.provider}/{self.endpoint_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task.id,
            "role": self.task.role_name,
            "provider": self.provider,
            "endpoint_id": self.endpoint_id,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class WorkResult:
    """O que aconteceu. `outcome` usa o mesmo vocabulário das sondas.

    `skipped` é o desfecho de quem nunca chegou a ser chamado — cota, orçamento ou
    ausência de endpoint apto. Ele não é falha do modelo e não deve manchar o
    histórico dele.
    """

    assignment: Assignment
    # ok | reachable | skipped | auth | rate_limited | account_exhausted | unavailable | error
    outcome: str
    text: str = ""
    detail: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    latency_ms: int | None = None
    observed_at: str = field(default_factory=now)

    @property
    def ok(self) -> bool:
        return self.outcome == "ok"

    @property
    def called(self) -> bool:
        """Consumiu cota? `skipped` é o único desfecho que não consumiu."""
        return self.outcome != "skipped"

    def to_dict(self) -> dict[str, Any]:
        return {
            "assignment": self.assignment.to_dict(),
            "outcome": self.outcome,
            "text": self.text,
            "detail": self.detail,
            "usage": self.usage,
            "latency_ms": self.latency_ms,
            "observed_at": self.observed_at,
        }
