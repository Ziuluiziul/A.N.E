#!/usr/bin/env python3
"""Reconstrói o ledger de desfechos e imprime as superfícies derivadas.

    make outcomes            reconstrói e imprime
    make outcomes ARGS=--json  imprime as superfícies em JSON

Somente leitura sobre `runtime/`: lê a fila e os painéis, grava apenas o próprio ledger.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys

from vault.config import get_settings
from vault.telemetry import AMOSTRA_MINIMA, build_records, build_surfaces, write_ledger


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ledger de desfechos (M0 da ADR-003)")
    parser.add_argument("--json", action="store_true", help="saída legível por máquina")
    parser.add_argument(
        "--top", type=int, default=12, help="quantas linhas por superfície (padrão: 12)"
    )
    return parser.parse_args(argv)


def _fracao(valor: float | None) -> str:
    return "—" if valor is None else f"{valor:.0%}"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    runtime = get_settings().runtime_dir
    registros = build_records(runtime)
    if not registros:
        print("nenhum evento em runtime/ — rode `make worker` ou `make quorum` primeiro")
        return 1
    destino = write_ledger(runtime, registros)
    superficies = build_surfaces(registros)

    if args.json:
        # `dataclasses.asdict`, e não `vars`: as superfícies usam `slots=True` e não têm
        # `__dict__`. `vars` levantava TypeError, e nenhum teste percorria este ramo.
        json.dump(
            {
                "registros": len(registros),
                "capacidade": [dataclasses.asdict(c) for c in superficies.capacidade],
                "aptidao": [dataclasses.asdict(a) for a in superficies.aptidao],
                "custo": dataclasses.asdict(superficies.custo),
                "pivotalidade": superficies.pivotalidade,
                "lacunas": [dataclasses.asdict(lac) for lac in superficies.lacunas],
            },
            sys.stdout,
            ensure_ascii=False,
            indent=2,
        )
        print()
        return 0

    print(f"{len(registros)} registros → {destino}")
    estagios: dict[str, int] = {}
    for registro in registros:
        estagios[registro.stage.value] = estagios.get(registro.stage.value, 0) + 1
    print("  " + " · ".join(f"{v} {k}" for k, v in sorted(estagios.items())))

    print(f"\n── capacidade por endpoint ── (taxa oculta abaixo de {AMOSTRA_MINIMA} obs.)")
    print(f"  {'endpoint':44} {'tent.':>6} {'ok':>5}  causa dominante")
    for item in superficies.capacidade[: args.top]:
        dominante = next(
            (f"{k} ×{v}" for k, v in item.por_classe.items() if k != "ok"), "—"
        )
        taxa = _fracao(item.taxa_ok)
        print(f"  {item.chave[:44]:44} {item.tentativas:6d} {taxa:>5}  {dominante}")

    print("\n── aptidão operacional (endpoint × papel × domínio) ──")
    if not superficies.aptidao:
        print("  nenhum voto registrado")
    for apto in superficies.aptidao[: args.top]:
        print(
            f"  {apto.endpoint[:34]:34} {apto.role[:22]:22} {apto.domain[:14]:14} "
            f"{apto.observacoes:3d} obs  {_fracao(apto.taxa):>5}"
        )

    custo = superficies.custo
    print("\n── custo de fechamento ──")
    print(f"  painéis decididos ......... {custo.paineis_decididos}")
    print(f"  registros de chamada ...... {custo.registros_de_chamada}")
    media = custo.tentativas_por_decisao
    print(f"  chamadas por decisão ...... {'—' if media is None else f'{media:.1f}'}")

    if superficies.pivotalidade:
        print("\n── influência do voto (regra real do quórum, um voto retirado por vez) ──")
        for rotulo, quantidade in superficies.pivotalidade.items():
            print(f"  {rotulo:12} {quantidade}")

    print("\n── lacunas que a calibração vai exigir ──")
    for lacuna in superficies.lacunas:
        print(f"  {lacuna.nome}\n      {lacuna.motivo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
