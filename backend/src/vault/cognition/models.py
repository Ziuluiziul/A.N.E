"""Quadro de raciocínio ao vivo. Efêmero, atribuído ao endpoint, sem persistir no corpus."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CognitionKind = Literal[
    "reasoning",
    "reasoning-summary",
    "output-delta",
    "final",
    "progress",
    "tool-call",
    "tool-result",
]

COGNITION_KINDS: tuple[CognitionKind, ...] = (
    "reasoning",
    "reasoning-summary",
    "output-delta",
    "final",
    "progress",
    "tool-call",
    "tool-result",
)

_FRAME_ID = re.compile(r"cognition-([0-9]{20})")


def frame_id(revision: int) -> str:
    if revision < 1:
        raise ValueError("revisão cognitiva precisa ser positiva")
    return f"cognition-{revision:020d}"


def revision_from_frame_id(identifier: str | None) -> int | None:
    if identifier is None:
        return None
    match = _FRAME_ID.fullmatch(identifier.strip())
    if match is None:
        return None
    revision = int(match.group(1))
    return revision if revision > 0 else None


class CognitionFrame(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=40)
    revision: int = Field(ge=1)
    timestamp: str = Field(min_length=1, max_length=80)
    kind: CognitionKind
    provider: str = Field(min_length=1, max_length=80)
    endpoint: str = Field(min_length=1, max_length=300)
    task: str | None = Field(default=None, max_length=160)
    text: str = Field(default="", max_length=400)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "revision": self.revision,
            "timestamp": self.timestamp,
            "kind": self.kind,
            "provider": self.provider,
            "endpoint": self.endpoint,
            "text": self.text,
        }
        if self.task:
            payload["task"] = self.task
        return payload
