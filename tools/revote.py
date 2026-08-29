#!/usr/bin/env python3
"""Reabre painéis com patch pronto e escalate por voto vazio.

    uv run python tools/revote.py 6a1c34fef8d0
    uv run python tools/revote.py --pendentes

Não gera proposta de novo. Reposição de cadeira + nova decisão. Promote
automático só se o quórum fechar promote — o Promoter continua o único
caminho até knowledge/.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from providers import build_adapters
from providers.catalog import DiscoverySnapshotError, load_all_snapshots
from providers.inventory import build_inventory
from providers.registry import REGISTRY_NAME, EndpointRegistry
from vault.config import get_settings
from vault.events import OperationalEventRecorder, OperationalEventStore
from vault.promotion import PromotionRefused, ProposalPromoter
from vault.promotion.patch import CorpusPatch
from vault.quorum import QuorumStore, QuorumStoreError
from vault.runtime_io import read_private_json, write_private_json
from vault.work.call_gate import ProviderCallGate
from vault.work.ceilings import ceilings_from_declared, merge_provider_caps
from vault.work.orchestrator import QuorumExecutionError, QuorumOrchestrator
from vault.work.quota_store import load_ledger, persist_ledger
from vault.work.quotas import RunBudget
from vault.work.store import WorkStore


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paineis", nargs="*", help="ids de painel")
    parser.add_argument(
        "--pendentes",
        action="store_true",
        help="todos os escalate com patch em disco",
    )
    return parser.parse_args(argv)


def _pendentes(store: QuorumStore) -> list[str]:
    ids: list[str] = []
    for panel in store.list_panels():
        if panel.decision is None:
            continue
        if panel.decision.outcome.value != "escalate":
            continue
        if store.load_patch(panel.id) is None:
            continue
        ids.append(panel.id)
    return ids


async def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = get_settings()
    try:
        snapshots = load_all_snapshots(settings.state_dir)
    except DiscoverySnapshotError as error:
        print(str(error))
        return 1
    registry = EndpointRegistry.from_dict(
        read_private_json(settings.state_dir / REGISTRY_NAME)
    )
    inventory = build_inventory(snapshots, registry)
    teto = ceilings_from_declared(
        (profile.model for profile in inventory.profiles),
        eligible=(profile.aptitude.eligible for profile in inventory.profiles),
    )
    provider_caps = merge_provider_caps(
        dict(getattr(settings, "provider_concurrency", {})), teto.provider_caps
    )
    adapters = build_adapters(settings)
    if not adapters:
        print("nenhuma credencial de provedor")
        return 1
    ledger, ledger_path = load_ledger(settings.state_dir)
    store = QuorumStore(settings.runtime_dir / "quorum")
    ids = list(args.paineis)
    if args.pendentes:
        ids.extend(_pendentes(store))
    ids = list(dict.fromkeys(ids))
    if not ids:
        print("nenhum painel para reabrir")
        return 1

    emit = OperationalEventRecorder(
        OperationalEventStore(settings.runtime_dir / "events", redact=settings.redact),
        warn=lambda message: print(f"AVISO {message}", file=sys.stderr),
    )
    orchestrator = QuorumOrchestrator(
        inventory=inventory,
        adapters=adapters,
        ledger=ledger,
        budget=RunBudget(max_calls=max(settings.work_max_calls, teto.daily_calls)),
        store=store,
        work_store=WorkStore(settings.models_dir),
        redact=settings.redact,
        emit=emit,
        call_gate=ProviderCallGate(provider_caps, endpoint_caps=teto.endpoint_caps),
    )
    promoter = ProposalPromoter(repo_root=settings.corpus_dir.parent, emit=emit)
    code = 0
    try:
        for panel_id in ids:
            try:
                panel = store.load_panel(panel_id)
            except QuorumStoreError as error:
                print(f"{panel_id}: ilegível ({error})")
                code = 1
                continue
            try:
                panel = await orchestrator.resume_votes(panel)
            except QuorumExecutionError as error:
                print(f"{panel_id}: {settings.redact(str(error))}")
                code = 1
                continue
            decision = panel.decision
            if decision is None:
                print(f"{panel_id}: sem decisão")
                code = 1
                continue
            outcome = decision.outcome.value
            print(
                f"{panel_id}: {outcome} "
                f"({decision.valid_vote_count} válidos) — {decision.reason}"
            )
            if outcome != "promote":
                if outcome == "escalate":
                    code = 1
                continue
            bruto = store.load_patch(panel_id)
            if bruto is None:
                print("  sem patch")
                continue
            try:
                resultado = promoter.promote(panel, CorpusPatch.model_validate(bruto))
            except PromotionRefused as error:
                print(f"  RECUSADO {error}")
                code = 1
                continue
            write_private_json(
                settings.runtime_dir / "quorum" / panel.id / "promotion.json",
                resultado.to_dict(),
            )
            print(f"  PROMOVIDO {resultado.commit[:12]} → {', '.join(resultado.targets)}")
    finally:
        persist_ledger(ledger, ledger_path, settings.redact)
    return code


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
