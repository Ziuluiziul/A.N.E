#!/usr/bin/env python3
"""Mantém a fila autônoma viva dentro do orçamento desta execução."""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from providers import build_adapters
from providers.base import ProviderAuthError, is_structural_key_auth
from providers.catalog import DiscoverySnapshotError, load_all_snapshots
from providers.cognitive import CognitiveEvent
from providers.inventory import Inventory, build_inventory
from providers.registry import REGISTRY_NAME, EndpointRegistry
from tools.run_quorum import current_head, load_ledger, persist_ledger
from vault.autonomy import (
    AutonomousTask,
    AutonomousWorker,
    ExecutionOutcome,
    OrchestratedTaskExecutor,
    PersistentTaskQueue,
    TaskGenerator,
    WorkerAlreadyRunning,
)
from vault.cognition import CognitionRecorder, CognitionStore
from vault.config import get_settings
from vault.corpus import CorpusReader
from vault.events import OperationalEventRecorder, OperationalEventStore
from vault.promotion import (
    POLICY_VERSION,
    PromotionJournal,
    PromotionPolicy,
    ProposalPromoter,
    QuorumPromotion,
)
from vault.promotion.policy import LEDGER_NAME, BudgetPolicy, DecisionLedger
from vault.quorum import QuorumStore
from vault.runtime_io import read_private_json
from vault.telemetry import build_records, build_surfaces
from vault.work.call_gate import ProviderCallGate
from vault.work.capacity import CapacityHints
from vault.work.ceilings import ceilings_from_declared, merge_provider_caps
from vault.work.fitness import Tier, classificar
from vault.work.quotas import RunBudget
from vault.work.store import WorkStore


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Worker autônomo do Vault")
    parser.add_argument("--once", action="store_true", help="executa no máximo uma tarefa")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="deriva e lista tarefas sem persistir nem chamar modelo",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=15.0,
        help="segundos entre ciclos quando não há trabalho elegível",
    )
    parser.add_argument(
        "--max-calls",
        type=int,
        default=None,
        help="sobrescreve VAULT_WORK_MAX_CALLS nesta execução",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="sobrescreve VAULT_WORKER_CONCURRENCY nesta execução",
    )
    return parser.parse_args(argv)


def _idle_endpoints(inventory: Any, ledger: Any) -> list[str]:
    cutoff = time.time() - 60.0
    return [
        profile.key
        for profile in inventory.select(usable=True)
        if not any(at >= cutoff for at, _tokens in ledger.events.get(profile.key, []))
    ]


# Quanto tempo as pistas de telemetria valem, e quantas tentativas bastam para condenar
# um endpoint que nunca entregou. Doze é o que a auditoria observou nos casos claros.
TTL_DAS_PISTAS_S = 300.0
MINIMO_PARA_CONDENAR = 12
# A condenação expira de propósito: um endpoint condenado não recebe tentativa nova, e
# sem tentativa nova o veredito nunca mudaria. Depois de um dia sem falha registrada ele
# volta a ser elegível; se falhar de novo, volta a ser condenado — um teste por dia é o
# preço da recuperação, e o painel inteiro não paga por ele.
TTL_DA_CONDENACAO_S = 86_400.0


def _segundos_desde(falha_iso: str, agora: float) -> float:
    try:
        quando = datetime.fromisoformat(falha_iso)
    except ValueError:
        return float("inf")
    return agora - quando.timestamp()


def _promotion_nativa(settings: Any, emit: Callable[..., None]) -> QuorumPromotion:
    """O caminho quórum → Promoter desta execução.

    A ativação da política acontece aqui, na subida — antes de qualquer fechamento
    do ciclo — para que a primeira decisão já esteja dentro do contrato: somente
    decisões posteriores à ativação entram na assimilação automática.
    """
    base = settings.runtime_dir / "promotion"
    politica = PromotionPolicy(base / "policy.json")
    ativada = politica.activate()
    print(
        f"promoção autônoma ativa: política {POLICY_VERSION}, "
        f"fechamentos anteriores a {ativada} ficam de fora"
    )
    return QuorumPromotion(
        journal=PromotionJournal(base / "promotions.jsonl"),
        policy=politica,
        promoter=ProposalPromoter(repo_root=settings.corpus_dir.parent, emit=emit),
    )


def _pistas_de_capacidade(runtime_dir: Path) -> Callable[[], CapacityHints]:
    """Liga o M1 ao ledger de desfechos do M0, com cache.

    Reconstruir o ledger lê a fila inteira e 160 diretórios de painel; fazer isso a cada
    admissão custaria mais que a chamada que se quer economizar. O TTL é largo porque as
    duas grandezas daqui mudam em horas — custo médio de fechamento e quais endpoints
    estão operacionalmente mortos —, ao contrário da capacidade, que muda a cada chamada.
    """
    lido_em = 0.0
    guardadas = CapacityHints()

    def pistas() -> CapacityHints:
        nonlocal lido_em, guardadas
        agora = time.time()
        if agora - lido_em < TTL_DAS_PISTAS_S:
            return guardadas
        try:
            superficies = build_surfaces(build_records(runtime_dir))
        except (OSError, ValueError):
            # Telemetria ausente ou ilegível não pode derrubar o worker: sem pista, o
            # estimador usa o painel mínimo e conta só endpoints verdes.
            return guardadas
        mortos = frozenset(
            item.chave
            for item in superficies.capacidade
            if item.tentativas >= MINIMO_PARA_CONDENAR
            and item.ok == 0
            and item.ultima_falha is not None
            and _segundos_desde(item.ultima_falha, agora) < TTL_DA_CONDENACAO_S
        )
        # Aptidão por (estágio, endpoint, papel, domínio), só com amostra mínima.
        # Estágios "proposal" e "vote" medem coisas diferentes — sintetizar e julgar —
        # e o seletor não as mistura. Preferência de seleção; o piso de diversidade do
        # motor continua.
        aptidao = {
            (item.stage.value, item.endpoint, item.role, item.domain): taxa
            for item in superficies.aptidao
            if (taxa := item.taxa) is not None
        }
        # Condenação por estágio: amostra longa e zero entregas utilizáveis. É a única
        # exclusão que o fitness faz, e o seletor ainda a sujeita ao piso de diversidade.
        unfit_por_estagio: dict[str, set[str]] = {}
        for item in superficies.aptidao:
            if classificar(item.taxa, item.observacoes, item.utilizaveis) is Tier.UNFIT:
                unfit_por_estagio.setdefault(item.stage.value, set()).add(item.endpoint)
        lido_em = agora
        guardadas = CapacityHints(
            expected_calls_per_closure=superficies.custo.tentativas_por_decisao,
            unfit=mortos,
            aptitude=aptidao,
            unfit_por_estagio={
                estagio: frozenset(chaves) for estagio, chaves in unfit_por_estagio.items()
            },
        )
        return guardadas

    return pistas


def _effective_concurrency(*, requested: int, max_calls: int) -> int:
    """Cada quórum exige ~4 chamadas; não promete mais tarefas do que o orçamento cobre."""
    por_tarefa = 4
    teto = max(1, max_calls // por_tarefa)
    return max(1, min(requested, teto))


def _teto_documentado(inventory: Inventory) -> tuple[dict[str, int], dict[str, int], int]:
    """RPM/RPD declarados viram cap em voo e orçamento do dia. Sem número, some zero."""
    teto = ceilings_from_declared(
        (profile.model for profile in inventory.profiles),
        eligible=(profile.aptitude.eligible for profile in inventory.profiles),
    )
    return teto.provider_caps, teto.endpoint_caps, teto.daily_calls


def _install_signal_handlers(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        try:
            loop.add_signal_handler(signum, stop.set)
        except (NotImplementedError, RuntimeError):
            continue


class _NoCredentialExecutor:
    def can_start(self, task: AutonomousTask) -> bool:
        del task
        return False

    async def __call__(self, task: AutonomousTask) -> ExecutionOutcome:
        del task
        raise RuntimeError("executor sem credenciais não pode receber tarefa")


async def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = get_settings()
    max_calls = args.max_calls if args.max_calls is not None else settings.work_max_calls
    concurrency = (
        args.concurrency if args.concurrency is not None else settings.worker_concurrency
    )
    # A concorrência deriva do orçamento do processo (cada quórum exige ~4
    # chamadas). O ceiling da política é o limite de *expansão* de um fechamento
    # viável, não o teto de planejamento — usá-lo aqui cortaria o que o mantenedor
    # já autorizou no orçamento do processo. O clamp fica depois do teto
    # documentado, senão 760 chamadas capam o worker em 190 tarefas.
    politica_orcamento = BudgetPolicy(settings.runtime_dir / "promotion" / "policy.json")

    try:
        snapshots = load_all_snapshots(settings.state_dir)
    except DiscoverySnapshotError as error:
        print(f"worker não iniciou: {error}")
        return 1

    registry = EndpointRegistry.from_dict(read_private_json(settings.state_dir / REGISTRY_NAME))
    inventory = build_inventory(snapshots, registry)
    derivado, por_endpoint, diario = _teto_documentado(inventory)
    provider_caps = merge_provider_caps(
        dict(getattr(settings, "provider_concurrency", {})), derivado
    )
    if args.max_calls is None:
        max_calls = max(max_calls, diario)
    if args.concurrency is None:
        concurrency = max(concurrency, sum(provider_caps.values()) or 1)
    concurrency = _effective_concurrency(requested=concurrency, max_calls=max_calls)
    call_gate = ProviderCallGate(provider_caps, endpoint_caps=por_endpoint)
    inventory = Inventory(
        profiles=[
            profile
            for profile in inventory.profiles
            if not call_gate.disabled(profile.provider)
        ]
    )
    ledger, ledger_path = load_ledger(settings.state_dir)
    generator = TaskGenerator(
        CorpusReader(settings.corpus_dir),
        quorum_root=settings.runtime_dir / "quorum",
        models_root=settings.models_dir,
        registry=registry,
        idle_endpoints=_idle_endpoints(inventory, ledger),
    )

    candidates = generator.generate()
    if args.dry_run:
        print(f"{len(candidates)} tarefa(s) derivada(s); nada persistido")
        for task in candidates[:30]:
            entity = f" · {task.corpus_entity}" if task.corpus_entity else ""
            print(f"  {task.priority:3} {task.id} {task.origin.value:27} {task.domain}{entity}")
        return 0

    queue = PersistentTaskQueue(settings.state_dir / "autonomy" / "tasks.json")
    try:
        with queue.worker_lease():
            return await _run_with_lease(
                args=args,
                settings=settings,
                queue=queue,
                inventory=inventory,
                ledger=ledger,
                ledger_path=ledger_path,
                generator=generator,
                candidate_count=len(candidates),
                max_calls=max_calls,
                concurrency=concurrency,
                call_gate=call_gate,
                politica_orcamento=politica_orcamento,
            )
    except WorkerAlreadyRunning as error:
        print(f"worker não iniciou: {error}")
        return 1


async def _run_with_lease(
    *,
    args: argparse.Namespace,
    settings: Any,
    queue: PersistentTaskQueue,
    inventory: Any,
    ledger: Any,
    ledger_path: Any,
    generator: TaskGenerator,
    candidate_count: int,
    max_calls: int,
    concurrency: int,
    call_gate: ProviderCallGate,
    politica_orcamento: BudgetPolicy,
) -> int:
    event_store = OperationalEventStore(
        settings.runtime_dir / "events",
        redact=settings.redact,
    )
    emit = OperationalEventRecorder(
        event_store,
        warn=lambda message: print(f"AVISO {message}", file=sys.stderr),
    )
    cognition = CognitionRecorder(
        CognitionStore(settings.cognition_dir, redact=settings.redact),
        warn=lambda message: print(f"AVISO {message}", file=sys.stderr),
    )

    def on_cognitive(event: CognitiveEvent, accumulated: str, task: str | None = None) -> None:
        """Adapta o relé posicional do orquestrador à assinatura do gravador."""
        cognition(event, accumulated=accumulated, task=task)

    stop = asyncio.Event()
    _install_signal_handlers(stop)
    adapters = build_adapters(settings)
    await _suspend_impossible_providers(adapters, call_gate)

    if not adapters:
        worker = AutonomousWorker(
            queue=queue,
            generator=generator,
            executor=_NoCredentialExecutor(),
            poll_interval_s=max(args.interval, 0.1),
            emit=emit,
            redact=settings.redact,
        )
        print("worker em espera: nenhuma credencial de provedor disponível")
        if args.once:
            await worker.start()
            worker.refresh()
            print("worker não executou: nenhuma credencial de provedor disponível")
            return 1
        await worker.run_forever(stop)
        return 0

    executor = OrchestratedTaskExecutor(
        inventory=inventory,
        adapters=adapters,
        ledger=ledger,
        process_budget=RunBudget(max_calls=max_calls),
        quorum_store=QuorumStore(settings.runtime_dir / "quorum"),
        work_store=WorkStore(settings.models_dir),
        reader=CorpusReader(settings.corpus_dir),
        resolve_base_commit=lambda: current_head(settings.corpus_dir.parent),
        redact=settings.redact,
        emit=emit,
        on_cognitive=on_cognitive,
        should_stop=stop.is_set,
        call_gate=call_gate,
        capacity_hints=_pistas_de_capacidade(settings.runtime_dir),
        promotion=_promotion_nativa(settings, emit),
        budget_policy=politica_orcamento,
        decision_ledger=DecisionLedger(
            settings.runtime_dir / "promotion" / LEDGER_NAME
        ),
    )
    worker = AutonomousWorker(
        queue=queue,
        generator=generator,
        executor=executor,
        poll_interval_s=max(args.interval, 0.1),
        concurrency=concurrency,
        emit=emit,
        redact=settings.redact,
    )
    print(
        f"worker ativo: {candidate_count} fonte(s) de tarefa; "
        f"orçamento {max_calls} chamada(s); "
        f"concorrência {concurrency} tarefa(s) simultânea(s); "
        "provedores "
        + ", ".join(
            f"{provider}={call_gate.capacity(provider)}" for provider in sorted(adapters)
        )
    )
    try:
        if args.once:
            await worker.start()
            finished = await worker.run_cycle()
            persist_ledger(ledger, ledger_path, settings.redact)
            if not finished:
                print("nenhuma tarefa elegível")
                return 1
            for task in finished:
                print(f"{task.id}: {task.state.value}")
            return 0 if all(t.state.value in {"completed", "rejected"} for t in finished) else 1
        await worker.start()
        while not stop.is_set():
            finished = await worker.run_cycle()
            persist_ledger(ledger, ledger_path, settings.redact)
            if finished:
                continue
            try:
                await asyncio.wait_for(stop.wait(), timeout=max(args.interval, 0.1))
            except TimeoutError:
                continue
        return 0
    finally:
        persist_ledger(ledger, ledger_path, settings.redact)


async def _suspend_impossible_providers(
    adapters: dict[str, Any],
    call_gate: ProviderCallGate,
) -> None:
    adapter = adapters.get("openrouter")
    if adapter is None:
        return
    try:
        await adapter.verify_credential()
    except ProviderAuthError as error:
        if is_structural_key_auth(str(error)):
            call_gate.suspend("openrouter")
            print(f"openrouter suspenso: {error}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
