"""Event bus operacional: persistência privada, replay e atualização em tempo real."""

from vault.events.bus import OperationalEventBus, RuntimeSnapshot
from vault.events.models import (
    EVENT_TYPES,
    EventType,
    OperationalEvent,
    OperationalEventDraft,
    event_id,
    revision_from_event_id,
)
from vault.events.recorder import OperationalEventRecorder
from vault.events.store import OperationalEventStore, OperationalEventStoreError

__all__ = [
    "EVENT_TYPES",
    "EventType",
    "OperationalEvent",
    "OperationalEventBus",
    "OperationalEventDraft",
    "OperationalEventRecorder",
    "OperationalEventStore",
    "OperationalEventStoreError",
    "RuntimeSnapshot",
    "event_id",
    "revision_from_event_id",
]
