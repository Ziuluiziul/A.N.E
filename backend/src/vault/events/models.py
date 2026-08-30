"""Contrato fechado dos eventos operacionais persistidos em ``runtime/``.

Evento operacional e revisão de corpus são relógios diferentes. Este módulo contém
somente o registro temporal do trabalho: nenhum campo aqui afirma verdade epistêmica,
e nenhum payload livre de modelo atravessa a fronteira sem sanitização.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EventType = Literal[
    "task_created",
    "task_assigned",
    "call_started",
    "call_completed",
    "temporary_created",
    "temporary_discarded",
    "evidence_recorded",
    "proposal_created",
    "quorum_started",
    "vote_requested",
    "vote_received",
    "quorum_decided",
    "promotion_started",
    "promotion_completed",
    "commit_created",
    "corpus_changed",
]

EVENT_TYPES: tuple[EventType, ...] = (
    "task_created",
    "task_assigned",
    "call_started",
    "call_completed",
    "temporary_created",
    "temporary_discarded",
    "evidence_recorded",
    "proposal_created",
    "quorum_started",
    "vote_requested",
    "vote_received",
    "quorum_decided",
    "promotion_started",
    "promotion_completed",
    "commit_created",
    "corpus_changed",
)

_EVENT_ID = re.compile(r"runtime-([0-9]{20})")


def event_id(revision: int) -> str:
    """Identidade estável que também serve de cursor SSE."""
    if revision < 1:
        raise ValueError("revisão operacional precisa ser positiva")
    return f"runtime-{revision:020d}"


def revision_from_event_id(identifier: str | None) -> int | None:
    """Converte ``Last-Event-ID`` apenas quando ele veio deste fluxo."""
    if identifier is None:
        return None
    match = _EVENT_ID.fullmatch(identifier.strip())
    if match is None:
        return None
    revision = int(match.group(1))
    return revision if revision > 0 else None


class OperationalEventDraft(BaseModel):
    """Dados fornecidos pelo produtor antes de o store atribuir ordem e tempo."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: EventType
    actor: str | None = Field(default=None, max_length=240)
    provider: str | None = Field(default=None, max_length=80)
    endpoint: str | None = Field(default=None, max_length=300)
    task: str | None = Field(default=None, max_length=160)
    entity: str | None = Field(default=None, max_length=300)
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OperationalEvent(BaseModel):
    """Uma linha imutável do log operacional, já sanitizada e ordenada."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=28, max_length=28, pattern=_EVENT_ID.pattern)
    revision: int = Field(ge=1)
    timestamp: str = Field(min_length=20, max_length=64)
    type: EventType
    actor: str | None = Field(default=None, max_length=240)
    provider: str | None = Field(default=None, max_length=80)
    endpoint: str | None = Field(default=None, max_length=300)
    task: str | None = Field(default=None, max_length=160)
    entity: str | None = Field(default=None, max_length=300)
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def timestamp_has_timezone(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ValueError("timestamp operacional inválido") from error
        if parsed.tzinfo is None:
            raise ValueError("timestamp operacional precisa de fuso")
        return value

    @model_validator(mode="after")
    def id_matches_revision(self) -> OperationalEvent:
        if self.id != event_id(self.revision):
            raise ValueError("id operacional não corresponde à revisão")
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
