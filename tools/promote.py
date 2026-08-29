#!/usr/bin/env python3
"""Promove um painel de quórum aprovado. É o único caminho até `knowledge/`.

    make promote PAINEL=<id>
    uv run python tools/promote.py <id> --dry-run

Sem argumento, lista os painéis com patch registrado e o que o quórum decidiu sobre
cada um. `--dry-run` roda todas as guardas — recomputa o quórum, confere o digest, a
base e a auditoria numa árvore temporária — e não commita.
"""

from __future__ import annotations

import argparse
import sys

from vault.config import get_settings
from vault.events import OperationalEventRecorder, OperationalEventStore
from vault.promotion import (
    CorpusPatch,
    PromotionRefused,
    ProposalPromoter,
)
from vault.quorum import QuorumStore, QuorumStoreError
from vault.runtime_io import write_private_json

REPO_ROOT = get_settings().corpus_dir.parent


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promoção automática por quórum")
    parser.add_argument("panel", nargs="?", help="identificador do painel")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="verifica tudo sem criar commit",
    )
    return parser.parse_args(argv)


def listar(store: QuorumStore) -> int:
    painels = store.list_panels()
    if not painels:
        print("nenhum painel em runtime/quorum — rode `make quorum` primeiro")
        return 1
    print(f"{len(painels)} painel(is):")
    for panel in painels:
        patch = store.load_patch(panel.id)
        decisao = panel.decision.outcome.value if panel.decision else "sem decisão"
        alvo = "com patch" if patch else "sem patch (nada a promover)"
        print(f"  {panel.id:16} {decisao:10} {len(panel.votes)} voto(s)  {alvo}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = get_settings()
    store = QuorumStore(root=settings.runtime_dir / "quorum")

    if not args.panel:
        return listar(store)

    try:
        panel = store.load_panel(args.panel)
    except QuorumStoreError as error:
        print(f"painel não pôde ser lido: {error}")
        return 1

    bruto = store.load_patch(args.panel)
    if bruto is None:
        print(f"o painel {args.panel} não carrega patch; não há o que promover")
        return 1

    try:
        patch = CorpusPatch.model_validate(bruto)
    except ValueError as error:
        print(f"patch inválido: {error}")
        return 1

    event_store = OperationalEventStore(
        settings.runtime_dir / "events",
        redact=settings.redact,
    )

    emit = OperationalEventRecorder(
        event_store,
        warn=lambda message: print(f"AVISO {message}", file=sys.stderr),
    )

    promoter = ProposalPromoter(repo_root=REPO_ROOT, emit=emit)

    if args.dry_run:
        try:
            promoter.validate(panel, patch)
        except PromotionRefused as error:
            print(f"RECUSADO {error}")
            return 1
        print(f"quórum válido; alvos: {', '.join(patch.targets)}")
        print(f"base do patch: {patch.base_commit[:12]}  HEAD: {promoter.head()[:12]}")
        print("dry-run: nada foi commitado")
        return 0

    try:
        resultado = promoter.promote(panel, patch)
    except PromotionRefused as error:
        print(f"RECUSADO {error}")
        return 1

    destino = settings.runtime_dir / "quorum" / panel.id / "promotion.json"
    write_private_json(destino, resultado.to_dict())

    print(f"PROMOVIDO  commit {resultado.commit[:12]}")
    print(f"  alvos:       {', '.join(resultado.targets)}")
    print(f"  avaliadores: {', '.join(resultado.reviewers)}")
    print(f"  provedores:  {', '.join(resultado.providers)}")
    print(f"  procedência: {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
