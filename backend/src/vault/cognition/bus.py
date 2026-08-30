"""Distribuição assíncrona do raciocínio ao vivo, no mesmo molde do event bus."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass

from vault.cognition.models import CognitionFrame
from vault.cognition.store import CognitionStore

POLL_INTERVAL_SECONDS = 0.08
SNAPSHOT_LIMIT = 80
REPLAY_BATCH_LIMIT = 80


@dataclass(frozen=True, slots=True)
class CognitionSnapshot:
    revision: int
    frames: tuple[CognitionFrame, ...]

    @property
    def latest_id(self) -> str | None:
        return self.frames[-1].id if self.frames else None

    def to_dict(self) -> dict[str, object]:
        return {
            "revision": self.revision,
            "frames": [frame.to_dict() for frame in self.frames],
        }


class CognitionBus:
    def __init__(self, store: CognitionStore) -> None:
        self.store = store
        self._revision = 0
        self._condition = asyncio.Condition()
        self._stop_event = asyncio.Event()
        self._poll_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._poll_task is not None:
            return
        self._revision = await asyncio.to_thread(self.store.latest_revision)
        self._stop_event = asyncio.Event()
        self._poll_task = asyncio.create_task(self._poll(), name="vault-cognition")

    async def stop(self) -> None:
        task = self._poll_task
        if task is None:
            return
        self._stop_event.set()
        with suppress(asyncio.CancelledError):
            await task
        self._poll_task = None

    async def snapshot(self) -> CognitionSnapshot:
        frames = await asyncio.to_thread(self.store.load, limit=SNAPSHOT_LIMIT)
        revision = frames[-1].revision if frames else 0
        await self._advance(revision)
        return CognitionSnapshot(revision, tuple(frames))

    async def wait_after(self, revision: int, *, timeout: float) -> list[CognitionFrame]:
        frames = await asyncio.to_thread(
            self.store.load,
            after_revision=revision,
            limit=REPLAY_BATCH_LIMIT,
        )
        if frames:
            await self._advance(frames[-1].revision)
            return frames
        async with self._condition:
            if self._revision <= revision:
                try:
                    await asyncio.wait_for(
                        self._condition.wait_for(lambda: self._revision > revision),
                        timeout=timeout,
                    )
                except TimeoutError:
                    return []
        frames = await asyncio.to_thread(
            self.store.load,
            after_revision=revision,
            limit=REPLAY_BATCH_LIMIT,
        )
        if frames:
            await self._advance(frames[-1].revision)
        return frames

    async def _advance(self, revision: int) -> None:
        async with self._condition:
            if revision > self._revision:
                self._revision = revision
                self._condition.notify_all()

    async def _poll(self) -> None:
        while not self._stop_event.is_set():
            with suppress(TimeoutError):
                await asyncio.wait_for(self._stop_event.wait(), timeout=POLL_INTERVAL_SECONDS)
            latest = await asyncio.to_thread(self.store.latest_revision)
            await self._advance(latest)
