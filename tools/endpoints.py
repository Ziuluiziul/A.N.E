#!/usr/bin/env python3
"""Consulta o inventário de endpoints já descobertos. Não chama ninguém.

Os endpoints descobertos só viram capacidade quando dá para perguntar a eles o que
servem. Este comando lê os retratos em `runtime/state/`, aplica a classificação e
cruza com o que a sonda observou, sem gastar cota nem tocar na rede.

    make endpoints
    uv run python tools/endpoints.py --provider nvidia --purpose general
    uv run python tools/endpoints.py --usable --json

A ordem impressa é a mesma que a sonda usa. Se a escolha automática parecer errada, é
aqui que se vê o motivo dela antes de mudar a regra.
"""

from __future__ import annotations

import argparse
from collections import Counter

import orjson

from providers.catalog import DiscoverySnapshotError, load_all_snapshots
from providers.inventory import EndpointProfile, Inventory, build_inventory
from providers.registry import REGISTRY_NAME, EndpointRegistry
from vault.config import get_settings
from vault.runtime_io import read_private_json

TOP_CANDIDATES = 5


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inventário classificado de endpoints")
    parser.add_argument("--provider", help="restringe a um provedor")
    parser.add_argument("--purpose", help="general, code, domain, safety, retrieval…")
    parser.add_argument("--family", help="restringe a uma família de modelos")
    parser.add_argument(
        "--status",
        help="ok, reachable, unavailable, auth, rate_limited, error ou not_probed",
    )
    parser.add_argument(
        "--usable",
        action="store_true",
        help="só o que já produziu texto numa sonda",
    )
    parser.add_argument("--json", action="store_true", help="saída para consumo programático")
    parser.add_argument(
        "--limit",
        type=int,
        default=TOP_CANDIDATES,
        help=f"quantos candidatos listar por provedor (padrão {TOP_CANDIDATES})",
    )
    return parser.parse_args(argv)


def _line(profile: EndpointProfile, position: int) -> str:
    janela = profile.model.context_window
    window = f"{janela:>9}" if janela else "        —"
    status = profile.observed_status or "não sondado"
    return (
        f"{'':8}    {position}. {profile.endpoint_id:44} "
        f"{profile.aptitude.purpose:10} {profile.aptitude.stability:8} "
        f"ctx {window}  {status}"
    )


def report(inventory: Inventory, args: argparse.Namespace) -> None:
    recortado = bool(args.status or args.purpose or args.family or args.usable)
    for provider in inventory.providers():
        do_provedor = inventory.select(provider=provider)
        found = inventory.select(
            provider=provider,
            purpose=args.purpose,
            family=args.family,
            status=args.status,
            usable=True if args.usable else None,
            eligible=None if recortado else True,
        )
        print(f"{provider:8} .. {len(do_provedor)} endpoints, {len(found)} no recorte")

        usaveis = [
            profile for profile in inventory.for_work() if profile.provider == provider
        ]
        confirmado = usaveis[0].endpoint_id if usaveis else "nenhum produziu texto ainda"
        print(f"{'':8}    para trabalho: {confirmado}")

        alcancados = inventory.select(provider=provider, status="reachable")
        if alcancados:
            nomes = ", ".join(profile.endpoint_id for profile in alcancados)
            print(f"{'':8}    alcançados sem texto: {nomes}")

        for position, profile in enumerate(found[: args.limit], start=1):
            print(_line(profile, position))

        descartados = Counter(
            profile.aptitude.modality
            if profile.aptitude.modality != "text"
            else profile.aptitude.purpose
            for profile in do_provedor
            if not profile.aptitude.eligible
        )
        if descartados and not recortado:
            resumo = ", ".join(f"{motivo} {n}" for motivo, n in descartados.most_common())
            print(f"{'':8}    descartados: {resumo}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = get_settings()

    try:
        snapshots = load_all_snapshots(settings.state_dir)
    except DiscoverySnapshotError as error:
        print(str(error))
        return 1

    registry = EndpointRegistry.from_dict(read_private_json(settings.state_dir / REGISTRY_NAME))
    inventory = build_inventory(snapshots, registry)

    if args.provider and args.provider not in inventory.providers():
        conhecidos = ", ".join(inventory.providers())
        print(f"provedor desconhecido: {args.provider} (há {conhecidos})")
        return 1

    if args.json:
        recorte = Inventory(
            profiles=inventory.select(
                provider=args.provider,
                purpose=args.purpose,
                family=args.family,
                status=args.status,
                usable=True if args.usable else None,
            )
        )
        print(orjson.dumps(recorte.to_dict(), option=orjson.OPT_INDENT_2).decode())
        return 0

    if args.provider:
        inventory = Inventory(profiles=inventory.select(provider=args.provider))
    report(inventory, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
