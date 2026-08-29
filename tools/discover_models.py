#!/usr/bin/env python3
"""Inventaria os endpoints que cada provedor realmente oferece à conta, agora.

Não copia catálogo antigo e não presume que um ID visto ontem continua atendendo.
Cada execução grava um retrato datado em `runtime/state/`, para que a comparação
entre duas datas seja possível sem que nenhuma delas seja tomada como permanente.

Só lista. Não gera texto, não gasta cota de inferência.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from providers import ProviderError, build_adapters
from providers.base import ProviderRateLimited
from providers.catalog import (
    MANIFEST_NAME,
    DiscoverySnapshotError,
    load_discovery_manifest,
    load_discovery_snapshot,
)
from vault.config import get_settings
from vault.runtime_io import redact_json, write_private_json


def _args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        metavar="PROVEDOR",
        help="atualiza somente este provedor e preserva os demais retratos válidos",
    )
    return parser.parse_args(argv)


def _valid_previous_providers(state_dir: Path) -> dict[str, str]:
    """Só reaproveita entradas de um manifesto completo cujo retrato ainda é válido."""
    try:
        previous = load_discovery_manifest(state_dir)
    except DiscoverySnapshotError:
        return {}

    valid: dict[str, str] = {}
    for name, filename in previous.items():
        try:
            load_discovery_snapshot(state_dir, name, previous)
        except DiscoverySnapshotError:
            continue
        valid[name] = filename
    return valid


def _snapshot_path(state_dir: Path, provider: str, stamp: str, *, unique: bool) -> Path:
    """Não sobrescreve o retrato vigente durante uma atualização transacional."""
    path = state_dir / f"models-{provider}-{stamp}.json"
    if not unique or not path.exists():
        return path
    suffix = 1
    while True:
        candidate = state_dir / f"models-{provider}-{stamp}-{suffix}.json"
        if not candidate.exists():
            return candidate
        suffix += 1


async def main(argv: Sequence[str] | None = None) -> int:
    args = _args(argv)
    settings = get_settings()
    adapters = build_adapters(settings)
    if not adapters:
        print("nenhuma credencial de provedor em ~/.config/vault-autodidata/secrets.env")
        print(
            "preencha GEMINI_API_KEY, GROQ_API_KEY, NVIDIA_API_KEY, "
            "OLLAMA_API_KEY, OPENROUTER_API_KEY ou NOUS_API_KEY"
        )
        return 1
    if args.provider:
        adapter = adapters.get(args.provider)
        if adapter is None:
            known = ", ".join(sorted(adapters)) or "nenhum"
            print(f"sem credencial para {args.provider} (há: {known})")
            return 1
        adapters = {args.provider: adapter}

    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    state_dir = settings.state_dir
    exit_code = 0
    manifest_path = state_dir / MANIFEST_NAME
    filtered = args.provider is not None
    previous = _valid_previous_providers(state_dir) if filtered else {}
    manifest: dict[str, object] = {
        "schema_version": 1,
        "observed_at": stamp,
        "status": "running",
        "providers": previous,
    }
    # Uma descoberta completa continua publicando seu progresso: sem filtro, todos os
    # provedores formam uma única execução e o manifesto descreve inclusive a falha
    # parcial. Já ``--provider`` é uma atualização transacional do inventário vigente.
    # Enquanto a listagem e seu retrato não terminarem, o manifesto completo anterior
    # precisa continuar byte a byte intacto para seus consumidores.
    if not filtered:
        write_private_json(manifest_path, manifest)

    for name, adapter in adapters.items():
        try:
            models = await adapter.list_models()
        except ProviderError as error:
            detail = settings.redact(f"{type(error).__name__}: {error}")[:400]
            print(f"{name:8} .. {detail}")
            exit_code = 1
            manifest["status"] = (
                "rate_limited" if isinstance(error, ProviderRateLimited) else "failed"
            )
            manifest["failed_provider"] = name
            if isinstance(error, ProviderRateLimited):
                manifest["rate_limit"] = redact_json(
                    asdict(adapter.get_observed_limits()),
                    settings.redact,
                )
                retry_after = (
                    f"{error.retry_after_s:g} s"
                    if error.retry_after_s is not None
                    else "não informado"
                )
                print(f"{'':8}    retry-after: {retry_after}")
            if not filtered:
                write_private_json(manifest_path, manifest)
            if isinstance(error, ProviderRateLimited):
                break
            continue
        except Exception as error:  # noqa: BLE001 — fronteira da CLI, sem traceback
            detail = settings.redact(f"{type(error).__name__}: {error}")[:400]
            print(f"{name:8} .. erro não classificado: {detail}")
            exit_code = 1
            manifest["status"] = "failed"
            manifest["failed_provider"] = name
            if not filtered:
                write_private_json(manifest_path, manifest)
            continue

        active = [model for model in models if model.available]
        families = sorted({settings.redact(m.family) for m in models})
        print(f"{name:8} .. {len(models)} endpoints, {len(active)} listados como ativos")
        print(f"{'':8}    famílias: {', '.join(families)}")

        path = _snapshot_path(state_dir, name, stamp, unique=filtered)
        write_private_json(
            path,
            {
                "provider": name,
                "observed_at": stamp,
                "count": len(models),
                "models": redact_json([asdict(m) for m in models], settings.redact),
            },
        )
        providers = manifest["providers"]
        assert isinstance(providers, dict)
        providers[name] = path.name
        if not filtered:
            write_private_json(manifest_path, manifest)
        print(f"{'':8}    retrato: {path}")

    if exit_code == 0:
        manifest["status"] = "complete"
        write_private_json(manifest_path, manifest)
        print(f"{'':8}    manifesto: {manifest_path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
