"""Fronteira best-effort entre trabalho durável e sua telemetria operacional."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from vault.events.models import EventType, OperationalEventDraft
from vault.events.store import OperationalEventStore, OperationalEventStoreError


def _silent_warning(_message: str) -> None:
    return None


@dataclass(slots=True)
class OperationalEventRecorder:
    """Grava eventos sem deixar uma falha de I/O corromper a máquina de estados.

    Erro de contrato continua sendo levantado: payload inválido é defeito de código e
    precisa falhar nos testes. Só indisponibilidade da persistência é degradada, pois
    uma tarefa já atribuída não pode ficar presa por causa da camada de observação.
    """

    store: OperationalEventStore
    warn: Callable[[str], None] = _silent_warning
    failure_count: int = 0

    def __call__(self, kind: EventType, payload: dict[str, Any]) -> None:
        draft = OperationalEventDraft(type=kind, **payload)
        try:
            self.store.append(draft)
        except (OperationalEventStoreError, OSError) as error:
            self.failure_count += 1
            self.warn(f"event log indisponível: {type(error).__name__}: {error}")
