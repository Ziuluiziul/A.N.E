"""Distribuição assíncrona sobre o event log persistente."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass

from vault.events.models import OperationalEvent, OperationalEventDraft
from vault.events.store import OperationalEventStore, OperationalEventStoreError

POLL_INTERVAL_SECONDS = 0.1
# O primeiro quadro SSE não deve despejar o histórico inteiro; o cliente corta em 160.
SNAPSHOT_EVENT_LIMIT = 160
REPLAY_BATCH_LIMIT = 500


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    runtime_revision: int
    events: tuple[OperationalEvent, ...]

    @property
    def latest_id(self) -> str | None:
        return self.events[-1].id if self.events else None

    def to_dict(self) -> dict[str, object]:
        return {
            "runtimeRevision": self.runtime_revision,
            "events": [event.to_dict() for event in self.events],
        }


class OperationalEventBus:
    """Acorda assinantes locais e detecta produtores em outros processos."""

    def __init__(self, store: OperationalEventStore) -> None:
        self.store = store
        self._revision = 0
        self._condition = asyncio.Condition()
        self._stop_event = asyncio.Event()
        self._poll_task: asyncio.Task[None] | None = None

    @property
    def revision(self) -> int:
        return self._revision

    async def start(self) -> None:
        if self._poll_task is not None:
            return
        self._revision = await asyncio.to_thread(self.store.latest_revision)
        self._stop_event = asyncio.Event()
        self._poll_task = asyncio.create_task(self._poll(), name="vault-operational-events")

    async def stop(self) -> None:
        task = self._poll_task
        if task is None:
            return
        self._stop_event.set()
        with suppress(asyncio.CancelledError):
            await task
        self._poll_task = None

    async def publish(self, draft: OperationalEventDraft) -> OperationalEvent:
        event = await asyncio.to_thread(self.store.append, draft)
        await self._advance(event.revision)
        return event

    async def snapshot(self) -> RuntimeSnapshot:
        # ``load(limit=...)`` com revisão 0 lê a cauda; não bloqueia no jsonl inteiro.
        events = await asyncio.to_thread(self.store.load, limit=SNAPSHOT_EVENT_LIMIT)
        # O cursor precisa vir exatamente do mesmo retrato que será enviado. Um produtor
        # externo pode anexar uma linha entre ``load`` e uma segunda leitura da cauda; se
        # essa linha virasse a revisão sem estar em ``events``, o SSE avançaria o cursor
        # além dela e a conexão jamais a receberia.
        revision = events[-1].revision if events else 0
        await self._advance(revision)
        return RuntimeSnapshot(revision, tuple(events))

    async def wait_after(
        self,
        revision: int,
        *,
        timeout: float,
    ) -> list[OperationalEvent]:
        events = await asyncio.to_thread(
            self.store.load,
            after_revision=revision,
            limit=REPLAY_BATCH_LIMIT,
        )
        if events:
            await self._advance(events[-1].revision)
            return events

        async with self._condition:
            if self._revision <= revision:
                try:
                    await asyncio.wait_for(
                        self._condition.wait_for(lambda: self._revision > revision),
                        timeout=timeout,
                    )
                except TimeoutError:
                    return []
        events = await asyncio.to_thread(
            self.store.load,
            after_revision=revision,
            limit=REPLAY_BATCH_LIMIT,
        )
        return events

    async def _poll(self) -> None:
        while not self._stop_event.is_set():
            with suppress(TimeoutError):
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=POLL_INTERVAL_SECONDS,
                )
            if self._stop_event.is_set():
                break
            try:
                revision = await asyncio.to_thread(self.store.latest_revision)
            except OperationalEventStoreError:
                continue
            await self._advance(revision)

    async def _advance(self, revision: int) -> None:
        if revision <= self._revision:
            return
        async with self._condition:
            if revision <= self._revision:
                return
            self._revision = revision
            self._condition.notify_all()
