#!/usr/bin/env python3
"""Roda um lote de tarefas nos endpoints já comprovados.

    make work TAREFA="Explique em três frases o que é um claim model-dependent."
    uv run python tools/run_work.py --papel critico-epistemologico --dry-run

Uma chamada por atribuição, sem retry e sem fallback oculto. O orçamento da execução
vem de `VAULT_WORK_MAX_CALLS` (padrão 6) e é o teto que não depende de header nenhum:
ultrapassá-lo é decisão do mantenedor, não ajuste do orquestrador.

`--dry-run` mostra o plano sem gastar nada. Use antes de qualquer lote grande.
"""

from __future__ import annotations

import argparse
import asyncio

from providers import build_adapters
from providers.catalog import DiscoverySnapshotError, load_all_snapshots
from providers.inventory import Inventory, build_inventory
from providers.registry import REGISTRY_NAME, EndpointRegistry
from vault.config import get_settings
from vault.runtime_io import read_private_json
from vault.work.call_gate import ProviderCallGate
from vault.work.ceilings import ceilings_from_declared, merge_provider_caps
from vault.work.orchestrator import execute, plan_batch
from vault.work.quota_store import load_ledger, persist_ledger
from vault.work.quotas import RunBudget
from vault.work.roles import ROLES
from vault.work.store import WorkStore
from vault.work.tasks import Task, TaskRefused


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Executa tarefas nos endpoints comprovados")
    parser.add_argument("prompt", nargs="?", help="o texto da tarefa")
    parser.add_argument(
        "--papel",
        default="proponente",
        choices=sorted(ROLES),
        help="papel que executa a tarefa (padrão: proponente)",
    )
    parser.add_argument("--tipo", default="pergunta-livre", help="rótulo do tipo de tarefa")
    parser.add_argument(
        "--replicas",
        type=int,
        default=1,
        help="quantas cópias independentes da tarefa distribuir entre provedores",
    )
    parser.add_argument("--max-tokens", type=int, default=512, help="teto de saída por chamada")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="mostra o plano sem chamar ninguém",
    )
    return parser.parse_args(argv)


async def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = get_settings()

    if not args.prompt:
        print("nada a fazer: passe o texto da tarefa")
        return 1

    try:
        tasks = [
            Task(
                kind=args.tipo,
                role_name=args.papel,
                prompt=args.prompt,
                max_output_tokens=args.max_tokens,
            )
            for _ in range(max(args.replicas, 1))
        ]
    except TaskRefused as error:
        print(f"tarefa recusada: {error}")
        return 1

    try:
        snapshots = load_all_snapshots(settings.state_dir)
    except DiscoverySnapshotError as error:
        print(str(error))
        return 1

    registry = EndpointRegistry.from_dict(read_private_json(settings.state_dir / REGISTRY_NAME))
    inventory = build_inventory(snapshots, registry)
    teto = ceilings_from_declared(
        (profile.model for profile in inventory.profiles),
        eligible=(profile.aptitude.eligible for profile in inventory.profiles),
    )
    provider_caps = merge_provider_caps(
        dict(getattr(settings, "provider_concurrency", {})), teto.provider_caps
    )
    call_gate = ProviderCallGate(provider_caps, endpoint_caps=teto.endpoint_caps)
    inventory = Inventory(
        profiles=[
            profile
            for profile in inventory.profiles
            if not call_gate.disabled(profile.provider)
        ]
    )
    ledger, ledger_path = load_ledger(settings.state_dir)
    budget = RunBudget(max_calls=max(settings.work_max_calls, teto.daily_calls))

    plan = plan_batch(tasks, inventory, ledger, budget)
    print(f"plano: {len(plan.assignments)} chamada(s), {len(plan.refusals)} recusa(s)")
    for assignment in plan.assignments:
        print(f"  → {assignment.key:44} {assignment.reason}")
    for refusal in plan.refusals:
        print(f"  · recusada: {refusal.reason}")

    if args.dry_run:
        print("\ndry-run: nada foi chamado")
        return 0
    if not plan.assignments:
        return 1

    adapters = build_adapters(settings)
    if not adapters:
        print("nenhuma credencial de provedor em ~/.config/vault-autodidata/secrets.env")
        return 1

    try:
        results = await execute(
            plan,
            adapters,
            ledger,
            redact=settings.redact,
            gate=call_gate,
        )
    finally:
        persist_ledger(ledger, ledger_path, settings.redact)
    store = WorkStore(root=settings.models_dir)

    print()
    todos_ok = True
    for result in results:
        if not result.called:
            continue
        destino = store.record(result)
        marca = "ok" if result.ok else result.outcome.upper()
        latencia = f"{result.latency_ms} ms" if result.latency_ms is not None else "—"
        resumo = result.text.replace("\n", " ")[:100] if result.ok else result.detail
        print(f"{marca:12} {result.assignment.key:40} ({latencia}) {resumo}")
        if destino is not None:
            print(f"{'':12} {destino}")
        todos_ok = todos_ok and result.ok

    print(f"\ncota registrada: {ledger_path}")
    return 0 if todos_ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
