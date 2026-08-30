"""Publica o raciocínio sem derrubar a chamada se o disco falhar."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from providers.cognitive import CognitiveEvent, CognitiveKind
from vault.cognition.store import CognitionStore, CognitionStoreError

_THROTTLE_S = 0.28
_THROTTLE_CHARS = 48
_LIVE_KINDS = {CognitiveKind.REASONING, CognitiveKind.REASONING_SUMMARY}


@dataclass(slots=True)
class CognitionRecorder:
    store: CognitionStore
    warn: Callable[[str], None] | None = None
    _last_at: dict[str, float] = field(default_factory=dict)
    _last_len: dict[str, int] = field(default_factory=dict)

    def __call__(
        self,
        event: CognitiveEvent,
        *,
        accumulated: str,
        task: str | None = None,
    ) -> None:
        if event.kind not in _LIVE_KINDS and event.kind is not CognitiveKind.FINAL:
            return
        key = f"{event.provider}/{event.endpoint_id}"
        now = time.monotonic()
        if event.kind in _LIVE_KINDS:
            previous_len = self._last_len.get(key, 0)
            previous_at = self._last_at.get(key, 0.0)
            grew = len(accumulated) - previous_len >= _THROTTLE_CHARS
            aged = now - previous_at >= _THROTTLE_S
            if not grew and not aged:
                return
        try:
            self.store.append(
                kind=event.kind.value,
                provider=event.provider,
                endpoint=event.endpoint_id,
                text=accumulated,
                task=task,
            )
        except (CognitionStoreError, OSError) as error:
            if self.warn is not None:
                self.warn(f"cognition log indisponível: {type(error).__name__}: {error}")
            return
        self._last_at[key] = now
        self._last_len[key] = len(accumulated)
