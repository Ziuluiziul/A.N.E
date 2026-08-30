"""Lê os retratos que a descoberta gravou. Não repete a listagem externa.

Estava dentro de `tools/smoke_providers.py`, onde só a CLI alcançava. O orquestrador
precisa dos mesmos retratos e vive no pacote instalado, que não inclui `tools/` — daí
a mudança de casa. A validação continua estrita: retrato de outro provedor, schema
desconhecido ou caminho fora de `state_dir` viram erro, nunca inventário parcial
tratado como completo.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import orjson

from providers.base import ModelInfo

MANIFEST_NAME = "models-discovery.json"


class DiscoverySnapshotError(RuntimeError):
    """Não se escolhe endpoint sem o inventário de uma descoberta completa."""


@dataclass(frozen=True, slots=True)
class DiscoverySnapshot:
    path: Path
    models: list[ModelInfo]


def load_discovery_manifest(state_dir: Path) -> dict[str, str]:
    """Resolve os retratos de uma única descoberta completa."""
    path = state_dir / MANIFEST_NAME
    try:
        raw = orjson.loads(path.read_bytes())
    except (OSError, orjson.JSONDecodeError) as error:
        raise DiscoverySnapshotError(
            "manifesto de descoberta ausente ou ilegível; rode `make discover-models`"
        ) from error
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise DiscoverySnapshotError("manifesto de descoberta tem schema desconhecido")
    if raw.get("status") != "complete":
        raise DiscoverySnapshotError(
            f"descoberta não foi concluída: status={raw.get('status', 'ausente')}"
        )
    providers = raw.get("providers")
    if not isinstance(providers, dict) or not all(
        isinstance(name, str) and isinstance(filename, str)
        for name, filename in providers.items()
    ):
        raise DiscoverySnapshotError("manifesto de descoberta sem provedores válidos")
    return providers


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _model_from_dict(raw: object, provider: str) -> ModelInfo:
    if not isinstance(raw, dict):
        raise DiscoverySnapshotError("entrada de modelo não é objeto")
    endpoint_id = raw.get("endpoint_id")
    family = raw.get("family")
    item_provider = raw.get("provider")
    if (
        item_provider != provider
        or not isinstance(endpoint_id, str)
        or not isinstance(family, str)
    ):
        raise DiscoverySnapshotError("entrada de modelo não corresponde ao provedor")
    capabilities = raw.get("capabilities", [])
    if not isinstance(capabilities, list) or not all(isinstance(c, str) for c in capabilities):
        raise DiscoverySnapshotError(f"capabilities inválidas em {endpoint_id}")
    declared = raw.get("declared_limits", {})
    model_raw = raw.get("raw", {})
    if not isinstance(declared, dict) or not isinstance(model_raw, dict):
        raise DiscoverySnapshotError(f"metadados inválidos em {endpoint_id}")
    return ModelInfo(
        provider=provider,
        endpoint_id=endpoint_id,
        family=family,
        capabilities=capabilities,
        context_window=_optional_int(raw.get("context_window")),
        max_output_tokens=_optional_int(raw.get("max_output_tokens")),
        declared_limits=declared,
        available=raw.get("available") is True,
        probe_outcome=str(raw.get("probe_outcome", "not_tested")),
        raw=model_raw,
        observed_at=str(raw.get("observed_at", "")),
    )


def load_discovery_snapshot(
    state_dir: Path,
    provider: str,
    manifest: dict[str, str] | None = None,
) -> DiscoverySnapshot:
    """Carrega o retrato apontado pelo manifesto; não repete a listagem externa."""
    resolved_manifest = manifest if manifest is not None else load_discovery_manifest(state_dir)
    filename = resolved_manifest.get(provider)
    if filename is None:
        raise DiscoverySnapshotError(
            f"manifesto não contém retrato de {provider}; repita a descoberta"
        )
    path = state_dir / filename
    if path.resolve().parent != state_dir.resolve() or path.name != filename:
        raise DiscoverySnapshotError(f"caminho de retrato inválido para {provider}")
    try:
        raw = orjson.loads(path.read_bytes())
    except (OSError, orjson.JSONDecodeError) as error:
        raise DiscoverySnapshotError(f"retrato ilegível: {path.name}") from error
    if not isinstance(raw, dict) or raw.get("provider") != provider:
        raise DiscoverySnapshotError(f"retrato não corresponde a {provider}: {path.name}")
    entries = raw.get("models")
    if not isinstance(entries, list):
        raise DiscoverySnapshotError(f"retrato sem lista de modelos: {path.name}")
    models = [_model_from_dict(item, provider) for item in entries]
    return DiscoverySnapshot(path=path, models=models)


def load_all_snapshots(state_dir: Path) -> dict[str, DiscoverySnapshot]:
    """Todos os retratos da descoberta corrente, um por provedor."""
    manifest = load_discovery_manifest(state_dir)
    return {
        provider: load_discovery_snapshot(state_dir, provider, manifest)
        for provider in sorted(manifest)
    }
