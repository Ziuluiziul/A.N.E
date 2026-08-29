#!/usr/bin/env python3
"""Aposenta o inventário morto da fila autônoma.

    make retire-tasks              lista o que seria aposentado, sem mudar nada
    make retire-tasks ARGS=--aplicar   aposenta de verdade

Meta-tarefa sem nota herdada é recusada por `can_start` desde `ddf465e` — ela nunca
gasta chamada, mas o `claim` a percorre e descarta a cada ciclo. Nada é removido: o
estado vira `rejected`, o motivo entra no metadado, e o histórico de tentativas
continua servindo ao ledger de desfechos.
"""

from __future__ import annotations

import argparse
import collections

from vault.autonomy.models import AutonomousTask, TaskKind
from vault.autonomy.queue import PersistentTaskQueue
from vault.config import get_settings

MOTIVO = "meta sem nota herdada: recusada por can_start desde o freio da divergência"


def sem_nota_herdada(task: AutonomousTask) -> bool:
    return (
        task.kind in {TaskKind.DIVERGENCE_REVIEW, TaskKind.PROPOSAL_REVISION}
        and task.corpus_entity is None
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aposenta tarefas irreivindicáveis")
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="muda o estado de verdade; sem isto apenas lista",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = get_settings()
    queue = PersistentTaskQueue(settings.state_dir / "autonomy" / "tasks.json")

    alvos = queue.retire_unclaimable(
        accept=sem_nota_herdada, reason=MOTIVO, dry_run=not args.aplicar
    )
    if not alvos:
        print("nada a aposentar: nenhuma meta sem nota em estado reivindicável")
        return 0

    por_tipo = collections.Counter(task.kind.value for task in alvos)
    por_estado = collections.Counter(task.state.value for task in alvos)
    verbo = "aposentadas" if args.aplicar else "seriam aposentadas"
    print(f"{len(alvos)} tarefa(s) {verbo}")
    for rotulo, contagem in (("tipo", por_tipo), ("estado", por_estado)):
        print(f"  por {rotulo}: " + ", ".join(f"{k}={v}" for k, v in sorted(contagem.items())))
    if not args.aplicar:
        print("\nnada foi alterado; use ARGS=--aplicar para efetivar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
