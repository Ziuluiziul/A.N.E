"""Painel de controle operacional: uma leitura agregada e as mutações que ela admite."""

from vault.control.credentials import (
    ENV_VAR_BY_PROVIDER,
    CredentialError,
    mask,
    remove_credential,
    write_credential,
)
from vault.control.models import (
    ControlSnapshot,
    CredentialResult,
    OperationState,
    ProviderState,
    ReasoningSupport,
    WorkerState,
)
from vault.control.preferences import ControlPreferences, PreferenceStore, WorkerPreference
from vault.control.routes import router
from vault.control.snapshot import build_snapshot, concurrency_ceiling, reasoning_support

__all__ = [
    "ENV_VAR_BY_PROVIDER",
    "ControlPreferences",
    "ControlSnapshot",
    "CredentialError",
    "CredentialResult",
    "OperationState",
    "PreferenceStore",
    "ProviderState",
    "ReasoningSupport",
    "WorkerPreference",
    "WorkerState",
    "build_snapshot",
    "concurrency_ceiling",
    "mask",
    "reasoning_support",
    "remove_credential",
    "router",
    "write_credential",
]
