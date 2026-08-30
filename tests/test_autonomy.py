"""Fila e worker autônomos são exercitados sem rede nem corpus real."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from providers.registry import EndpointRecord, EndpointRegistry
from vault.autonomy import (
    AutonomousTask,
    AutonomousWorker,
    ExecutionOutcome,
    PersistentTaskQueue,
    TaskBudget,
    TaskGenerator,
    TaskKind,
    TaskOrigin,
    TaskState,
    WorkerAlreadyRunning,
)
from vault.autonomy.models import ATTEMPTS_WINDOW, PANEL_ROLES, stable_task_id
from vault.autonomy.worker import TaskExecutor, _unreadable_votes, corpus_patch_context
from vault.corpus import CorpusReader
from vault.quorum import (
    CORPUS_PATCH_ALLOW_CREATE_KEY,
    CORPUS_PATCH_ALLOWED_TARGETS_KEY,
    CORPUS_PATCH_BASE_KEY,
    Panel,
    PanelMember,
    PanelTask,
    Proposal,
    QuorumStore,
    RecommendedAction,
    Vote,
    VoteDecision,
    decide_panel,
)
from vault.quorum.models import DecisionStatus, ParseResult


def task(origin: TaskOrigin = TaskOrigin.WEAK_CLAIM) -> AutonomousTask:
    identifier, fingerprint = stable_task_id(origin, {"source": "test"})
    return AutonomousTask(
        id=identifier,
        origin=origin,
        objective="Reavalie um claim delimitado.",
        priority=80,
        domain="Teste",
        kind=TaskKind.CORPUS_REVIEW,
        required_roles=list(PANEL_ROLES),
        budget=TaskBudget(),
        corpus_entity="Teste/Nota.md",
        source_fingerprint=fingerprint,
    )


def test_fila_deduplica_e_sobrevive_ao_reinicio(tmp_path: Path) -> None:
    path = tmp_path / "state" / "tasks.json"
    queue = PersistentTaskQueue(path)
    candidate = task()

    assert queue.add_new([candidate]) == [candidate]
    assert queue.add_new([candidate]) == []
    assert PersistentTaskQueue(path).snapshot().tasks[0].id == candidate.id
    assert path.stat().st_mode & 0o777 == 0o600


def test_lease_impede_dois_workers_na_mesma_fila(tmp_path: Path) -> None:
    queue = PersistentTaskQueue(tmp_path / "tasks.json")

    with queue.worker_lease(), pytest.raises(
        WorkerAlreadyRunning, match="worker ativo"
    ), PersistentTaskQueue(queue.path).worker_lease():
        pytest.fail("o segundo worker não pode adquirir a lease")


def test_reinicio_reabre_tentativa_interrompida(tmp_path: Path) -> None:
    queue = PersistentTaskQueue(tmp_path / "tasks.json")
    queue.add_new([task()])
    claimed = queue.claim()
    assert claimed is not None
    running = queue.start(claimed.id)
    assert running.state is TaskState.RUNNING

    recovered = PersistentTaskQueue(queue.path).recover_interrupted()

    assert recovered[0].state is TaskState.QUEUED
    assert recovered[0].attempts[-1].outcome == "interrupted"
    assert recovered[0].attempts[-1].finished_at is not None


def _seed(path: Path, tarefa: AutonomousTask, *, attempts: int, state: str) -> None:
    """Escreve o arquivo da fila como um estado anterior o teria escrito."""
    import json

    historico: list[dict[str, Any]] = [
        {
            "id": f"att-{i:03d}",
            "started_at": "2026-08-16T00:00:00+00:00",
            "finished_at": None,
            "endpoints": [],
            "outcome": None,
            "detail": "",
            "panel_id": None,
        }
        for i in range(attempts)
    ]
    path.write_text(
        json.dumps(
            {
                "tasks": [
                    {**tarefa.model_dump(mode="json"), "state": state, "attempts": historico}
                ]
            }
        ),
        encoding="utf-8",
    )


def test_historico_acima_da_janela_carrega_e_apara_o_mais_antigo(tmp_path: Path) -> None:
    """A fila real alcançou 101 tentativas e o worker caiu lendo o próprio estado.

    O teto do contrato continua valendo; o que muda é o excesso ser aparado na
    leitura — o mais antigo cai primeiro — em vez de impedir a fila de abrir.
    """
    path = tmp_path / "tasks.json"
    tarefa = task()
    _seed(path, tarefa, attempts=ATTEMPTS_WINDOW + 1, state="queued")

    carregada = PersistentTaskQueue(path).snapshot().tasks[0]

    assert len(carregada.attempts) == ATTEMPTS_WINDOW
    assert carregada.attempts[0].id == f"att-{1:03d}"
    assert carregada.attempts[-1].id == f"att-{ATTEMPTS_WINDOW:03d}"


def test_start_mantem_o_historico_dentro_da_janela(tmp_path: Path) -> None:
    path = tmp_path / "tasks.json"
    tarefa = task()
    _seed(path, tarefa, attempts=ATTEMPTS_WINDOW, state="assigned")

    running = PersistentTaskQueue(path).start(tarefa.id)

    assert len(running.attempts) == ATTEMPTS_WINDOW
    assert running.attempts[-1].id != f"att-{ATTEMPTS_WINDOW - 1:03d}"
    assert running.attempts[0].id == f"att-{1:03d}"
    relida = PersistentTaskQueue(path).snapshot().tasks[0]
    assert len(relida.attempts) == ATTEMPTS_WINDOW


class StaticGenerator:
    def __init__(self, generated: list[AutonomousTask]) -> None:
        self.generated = generated

    def generate(self) -> list[AutonomousTask]:
        return self.generated


class StaticExecutor:
    def __init__(self, outcome: ExecutionOutcome) -> None:
        self.outcome = outcome
        self.seen: list[AutonomousTask] = []

    async def __call__(self, candidate: AutonomousTask) -> ExecutionOutcome:
        self.seen.append(candidate)
        return self.outcome


async def test_worker_registra_uma_tentativa_e_eventos(tmp_path: Path) -> None:
    candidate = task()
    executor = StaticExecutor(
        ExecutionOutcome(
            "reject",
            "violação estrutural real",
            ("groq/a", "nvidia/b", "google/c"),
            "panel-1",
        )
    )
    events: list[tuple[str, dict[str, Any]]] = []
    worker = AutonomousWorker(
        queue=PersistentTaskQueue(tmp_path / "tasks.json"),
        generator=StaticGenerator([candidate]),  # type: ignore[arg-type]
        executor=cast(TaskExecutor, executor),
        emit=lambda kind, payload: events.append((kind, payload)),
    )

    finished = await worker.run_cycle()

    assert finished[0].state is TaskState.REJECTED
    assert finished[0].attempts[-1].panel_id == "panel-1"
    assert finished[0].attempts[-1].endpoints == ["groq/a", "nvidia/b", "google/c"]
    assert [kind for kind, _ in events] == [
        "task_created",
        "task_assigned",
        "evidence_recorded",
    ]
    assert events[-1][1]["after"] == {"state": "rejected"}


async def test_falha_vira_retry_explicito_e_nao_loop_oculto(tmp_path: Path) -> None:
    candidate = task()
    executor = StaticExecutor(ExecutionOutcome("unavailable", "endpoint caiu", ("groq/a",)))
    queue = PersistentTaskQueue(tmp_path / "tasks.json")
    worker = AutonomousWorker(
        queue=queue,
        generator=StaticGenerator([candidate]),  # type: ignore[arg-type]
        executor=cast(TaskExecutor, executor),
        retry_delay_s=60,
    )

    first = await worker.run_cycle()
    second = await worker.run_cycle()

    assert first[0].state is TaskState.RETRY_WAIT
    assert first[0].next_eligible_at is not None
    assert second == []
    assert len(executor.seen) == 1


class DeferredExecutor(StaticExecutor):
    def defer_reason(self, _candidate: AutonomousTask) -> str:
        return "orçamento da execução consumido"

    def can_start(self, _candidate: AutonomousTask) -> bool:
        return False


async def test_backpressure_nao_inventa_tentativa(tmp_path: Path) -> None:
    candidate = task()
    executor = DeferredExecutor(ExecutionOutcome("completed"))
    queue = PersistentTaskQueue(tmp_path / "tasks.json")
    worker = AutonomousWorker(
        queue=queue,
        generator=StaticGenerator([candidate]),  # type: ignore[arg-type]
        executor=cast(TaskExecutor, executor),
        retry_delay_s=60,
    )

    deferred = await worker.run_cycle()

    assert deferred == []
    waiting = queue.snapshot().tasks[0]
    assert waiting.state is TaskState.QUEUED
    assert waiting.attempts == []
    assert "last_backpressure" not in waiting.metadata
    assert executor.seen == []


class CheapOnlyExecutor(StaticExecutor):
    def can_start(self, candidate: AutonomousTask) -> bool:
        return candidate.kind is TaskKind.ENDPOINT_DIAGNOSIS


async def test_backpressure_escolhe_trabalho_que_cabe_sem_ocultar_prioridade(
    tmp_path: Path,
) -> None:
    expensive = task().model_copy(update={"priority": 99})
    cheap = task(TaskOrigin.ENDPOINT_FAILURE).model_copy(
        update={"priority": 10, "kind": TaskKind.ENDPOINT_DIAGNOSIS}
    )
    executor = CheapOnlyExecutor(ExecutionOutcome("completed"))
    queue = PersistentTaskQueue(tmp_path / "tasks.json")
    worker = AutonomousWorker(
        queue=queue,
        generator=StaticGenerator([expensive, cheap]),  # type: ignore[arg-type]
        executor=cast(TaskExecutor, executor),
    )

    finished = await worker.run_cycle()

    assert [candidate.id for candidate in executor.seen] == [cheap.id]
    assert finished[0].state is TaskState.COMPLETED
    states = {candidate.id: candidate.state for candidate in queue.snapshot().tasks}
    assert states[expensive.id] is TaskState.QUEUED


def _write_corpus(root: Path) -> CorpusReader:
    (root / "Dados").mkdir(parents=True)
    (root / "Dados" / "MOC — Dados.md").write_text(
        """---
title: MOC — Dados
domain: dados
kind: moc
epistemic_status: mixed
updated: 2026-08-04
---

# Dados

[[Nota aberta]] <!-- relation:navigation -->

## Lacunas priorizadas

Modelagem relacional e proveniência operacional.
""",
        encoding="utf-8",
    )
    (root / "Dados" / "Nota aberta.md").write_text(
        """---
title: Nota aberta
domain: dados
kind: fundamento
epistemic_status: mixed
updated: 2026-08-04
---

# Nota aberta

[[MOC — Dados]] <!-- relation:navigation -->

## Estado epistêmico

| ID | Afirmação | Status | Evidência |
| --- | --- | --- | --- |
| `CLM-DAD-ABR-001` | A questão continua sem resposta. | `open` | Falta fonte primária. |
""",
        encoding="utf-8",
    )
    (root / "Política Epistêmica e de Linkagem.md").write_text(
        """---
title: Política Epistêmica e de Linkagem
domain: vault
kind: registro
epistemic_status: operational
updated: 2026-08-04
---

# Política

Identificador só entra resolvido.
""",
        encoding="utf-8",
    )
    return CorpusReader(root)


def _member(provider: str, endpoint: str, family: str, role: str) -> PanelMember:
    return PanelMember(
        provider=provider,
        endpoint_id=endpoint,
        family=family,
        role_name=role,
    )


def _vote(member: PanelMember, decision: VoteDecision) -> ParseResult:
    action = {
        VoteDecision.APPROVE: RecommendedAction.PROMOTE,
        VoteDecision.REJECT: RecommendedAction.REJECT,
    }[decision]
    return ParseResult(
        reviewer=member,
        schema_valid=True,
        structured_vote=Vote(
            decision=decision,
            confidence=0.8,
            blocking_issues=["claim superdeclarado"] if decision is VoteDecision.REJECT else [],
            recommended_action=action,
        ),
    )


def _persist_panel(
    root: Path,
    *,
    panel_id: str,
    kind: str,
    context: dict[str, object],
    votes: list[ParseResult],
    outcome: RecommendedAction | None = None,
) -> None:
    proposer = _member("google", "g", "gemini", "proponente")
    members = [item.reviewer for item in votes]
    panel = Panel(
        id=panel_id,
        task=PanelTask(kind=kind, prompt="corrija", context=context),
        proposal=Proposal(proposer=proposer, final_response="texto candidato"),
        members=members,
    )
    panel.votes.extend(votes)
    panel.decision = decide_panel(panel)
    if outcome is not None and panel.decision.outcome is not outcome:
        panel.decision = panel.decision.model_copy(
            update={
                "outcome": outcome,
                "status": DecisionStatus.DECIDED,
                "reason": "desfecho forçado no teste",
            }
        )
    store = QuorumStore(root)
    store.create_panel(panel)
    for result in panel.votes:
        store.save_vote(panel.id, result)
    store.save_decision(panel.id, panel.decision)


def _rejected_panel(root: Path) -> None:
    members = [
        _member("groq", "a", "qwen", "verificador-factual"),
        _member("nvidia", "b", "glm", "critico-epistemologico"),
        _member("groq", "c", "llama", "revisor-estrutural"),
    ]
    _persist_panel(
        root,
        panel_id="panel-rejected",
        kind="corpus_review",
        context={"domain": "Dados", "corpus_path": "Dados/Nota aberta.md"},
        votes=[
            _vote(members[0], VoteDecision.REJECT),
            _vote(members[1], VoteDecision.REJECT),
            _vote(members[2], VoteDecision.APPROVE),
        ],
    )


def _escalated_corpus_panel(root: Path) -> None:
    members = [
        _member("groq", "a", "qwen", "verificador-factual"),
        _member("nvidia", "b", "glm", "critico-epistemologico"),
        _member("groq", "c", "llama", "revisor-estrutural"),
    ]
    _persist_panel(
        root,
        panel_id="panel-escalated",
        kind="corpus_review",
        context={"domain": "Dados", "corpus_path": "Dados/Nota aberta.md"},
        votes=[
            _vote(members[0], VoteDecision.APPROVE),
            _vote(members[1], VoteDecision.REJECT),
            _vote(members[2], VoteDecision.APPROVE),
        ],
        outcome=RecommendedAction.ESCALATE,
    )


def test_generator_deriva_corpus_rejeicao_endpoint_e_capacidade(tmp_path: Path) -> None:
    reader = _write_corpus(tmp_path / "knowledge")
    quorum = tmp_path / "runtime" / "quorum"
    _rejected_panel(quorum)
    _escalated_corpus_panel(quorum)
    registry = EndpointRegistry(
        records={
            "nvidia/falhou": EndpointRecord(
                provider="nvidia",
                endpoint_id="falhou",
                observed_status="unavailable",
                detail="529 observado",
                observed_at="2026-08-04T00:00:00+00:00",
            )
        }
    )
    generated = TaskGenerator(
        reader,
        quorum_root=quorum,
        models_root=tmp_path / "runtime" / "modelos",
        registry=registry,
        idle_endpoints=["google/gemini"],
    ).generate()

    origins = {candidate.origin for candidate in generated}
    assert TaskOrigin.WEAK_CLAIM in origins
    assert TaskOrigin.REJECTED_PROPOSAL in origins
    assert TaskOrigin.MODEL_DIVERGENCE in origins
    assert TaskOrigin.ENDPOINT_FAILURE in origins
    assert TaskOrigin.IDLE_CAPACITY in origins
    assert TaskOrigin.POLICY_REVIEW in origins
    assert TaskOrigin.CORPUS_EXPANSION in origins
    assert TaskOrigin.CORPUS_DEFECT not in origins
    politica = next(
        candidate
        for candidate in generated
        if candidate.origin is TaskOrigin.POLICY_REVIEW
    )
    assert politica.priority == 96
    assert politica.metadata.get("lock_targets") is True
    assert "regime de 2026-08-03" in politica.objective
    weak = next(
        candidate for candidate in generated if candidate.origin is TaskOrigin.WEAK_CLAIM
    )
    assert weak.corpus_entity == "Dados/Nota aberta.md"
    assert "CLM-DAD-ABR-001" in weak.objective
    revision = next(
        candidate
        for candidate in generated
        if candidate.origin is TaskOrigin.REJECTED_PROPOSAL
    )
    assert revision.corpus_entity == "Dados/Nota aberta.md"
    divergence = next(
        candidate
        for candidate in generated
        if candidate.origin is TaskOrigin.MODEL_DIVERGENCE
    )
    assert divergence.corpus_entity == "Dados/Nota aberta.md"


def test_generator_nao_amplifica_divergencia_sem_nota(tmp_path: Path) -> None:
    reader = _write_corpus(tmp_path / "knowledge")
    quorum = tmp_path / "runtime" / "quorum"
    members = [
        _member("groq", "a", "qwen", "verificador-factual"),
        _member("nvidia", "b", "glm", "critico-epistemologico"),
        _member("groq", "c", "llama", "revisor-estrutural"),
    ]
    votes = [
        _vote(members[0], VoteDecision.APPROVE),
        _vote(members[1], VoteDecision.REJECT),
        _vote(members[2], VoteDecision.APPROVE),
    ]
    _persist_panel(
        quorum,
        panel_id="panel-meta",
        kind="divergence_review",
        context={"domain": "Dados", "corpus_path": "Dados/Nota aberta.md"},
        votes=votes,
        outcome=RecommendedAction.ESCALATE,
    )
    _persist_panel(
        quorum,
        panel_id="panel-sem-nota",
        kind="corpus_review",
        context={"domain": "Dados"},
        votes=votes,
        outcome=RecommendedAction.ESCALATE,
    )
    generated = TaskGenerator(
        reader,
        quorum_root=quorum,
        models_root=tmp_path / "runtime" / "modelos",
    ).generate()
    assert TaskOrigin.MODEL_DIVERGENCE not in {item.origin for item in generated}


def _panel_com(votos: list[ParseResult]) -> Panel:
    proposer = _member("google", "g", "gemini", "proponente")
    members = [
        _member("groq", "a", "qwen", "verificador-factual"),
        _member("nvidia", "b", "glm", "critico-epistemologico"),
        _member("groq", "c", "llama", "revisor-estrutural"),
    ]
    panel = Panel(
        id="panel-leitura",
        task=PanelTask(kind="corpus_review", prompt="reavalie"),
        proposal=Proposal(proposer=proposer, final_response="texto candidato"),
        members=members,
    )
    panel.votes.extend(votos)
    panel.decision = decide_panel(panel)
    return panel


def _voto_ilegivel(member: PanelMember) -> ParseResult:
    return ParseResult(
        reviewer=member,
        schema_valid=False,
        structured_vote=Vote(
            decision=VoteDecision.ABSTAIN,
            confidence=0.0,
            recommended_action=RecommendedAction.ESCALATE,
        ),
        repair_attempted=True,
        error="nenhum objeto obedece ao schema fechado do voto",
    )


def test_painel_ilegivel_e_painel_em_dissenso_nao_sao_a_mesma_coisa() -> None:
    """Repetir só resolve o que não chegou a ser lido; dissenso repetido é o mesmo."""
    ilegivel = _panel_com(
        [
            _voto_ilegivel(_member("groq", "a", "qwen", "verificador-factual")),
            _voto_ilegivel(_member("nvidia", "b", "glm", "critico-epistemologico")),
            _vote(_member("groq", "c", "llama", "revisor-estrutural"), VoteDecision.APPROVE),
        ]
    )
    assert _unreadable_votes(ilegivel) == "unreadable_votes"

    empatado = _panel_com(
        [
            _vote(_member("groq", "a", "qwen", "verificador-factual"), VoteDecision.APPROVE),
            _vote(_member("nvidia", "b", "glm", "critico-epistemologico"), VoteDecision.REJECT),
            _vote(_member("groq", "c", "llama", "revisor-estrutural"), VoteDecision.APPROVE),
        ]
    )
    assert _unreadable_votes(empatado) is None


async def test_voto_ilegivel_espera_janela_curta_e_nao_a_de_backpressure(
    tmp_path: Path,
) -> None:
    candidate = task()
    executor = StaticExecutor(
        ExecutionOutcome("unreadable_votes", "0 avaliações válidas; mínimo é 3")
    )
    worker = AutonomousWorker(
        queue=PersistentTaskQueue(tmp_path / "tasks.json"),
        generator=StaticGenerator([candidate]),  # type: ignore[arg-type]
        executor=cast(TaskExecutor, executor),
        retry_delay_s=3_600,
        parse_retry_delay_s=60,
    )

    finished = await worker.run_cycle()

    assert finished[0].state is TaskState.RETRY_WAIT
    assert finished[0].next_eligible_at is not None
    espera = datetime.fromisoformat(finished[0].next_eligible_at) - datetime.now(UTC)
    assert timedelta(seconds=30) < espera <= timedelta(seconds=120)


def test_voto_ilegivel_nunca_aposenta_a_tarefa(tmp_path: Path) -> None:
    worker = AutonomousWorker(
        queue=PersistentTaskQueue(tmp_path / "tasks.json"),
        generator=StaticGenerator([]),  # type: ignore[arg-type]
        executor=cast(TaskExecutor, StaticExecutor(ExecutionOutcome("unreadable_votes"))),
    )
    exausta = AutonomousTask.model_validate(
        {
            **task().model_dump(mode="json"),
            "attempts": [{}, {}, {}, {}],
        }
    )

    estado, janela = worker._transition(  # noqa: SLF001
        exausta,
        ExecutionOutcome("unreadable_votes", "2 avaliações válidas; mínimo é 3"),
    )

    assert estado == TaskState.RETRY_WAIT.value
    assert janela is not None


def test_backpressure_nunca_aposenta_a_tarefa(tmp_path: Path) -> None:
    """Escassez que passa sozinha não pode consumir o orçamento de tentativas."""
    worker = AutonomousWorker(
        queue=PersistentTaskQueue(tmp_path / "tasks.json"),
        generator=StaticGenerator([]),  # type: ignore[arg-type]
        executor=cast(TaskExecutor, StaticExecutor(ExecutionOutcome("backpressure", "x"))),
    )
    exausta = AutonomousTask.model_validate(
        {
            **task().model_dump(mode="json"),
            "attempts": [{}, {}, {}, {}],
        }
    )

    estado, janela = worker._transition(  # noqa: SLF001
        exausta,
        ExecutionOutcome("backpressure", "sem painel possível agora"),
    )

    assert estado == TaskState.RETRY_WAIT.value
    assert janela is not None


def test_envelope_invalido_nunca_aposenta_a_tarefa(tmp_path: Path) -> None:
    worker = AutonomousWorker(
        queue=PersistentTaskQueue(tmp_path / "tasks.json"),
        generator=StaticGenerator([]),  # type: ignore[arg-type]
        executor=cast(TaskExecutor, StaticExecutor(ExecutionOutcome("invalid_envelope"))),
    )
    exausta = AutonomousTask.model_validate(
        {
            **task().model_dump(mode="json"),
            "attempts": [{}, {}, {}, {}],
        }
    )

    estado, janela = worker._transition(  # noqa: SLF001
        exausta,
        ExecutionOutcome("invalid_envelope", "não obedece ao CorpusPatch"),
    )

    assert estado == TaskState.RETRY_WAIT.value
    assert janela is not None


def test_falha_de_conta_nunca_aposenta_a_tarefa(tmp_path: Path) -> None:
    worker = AutonomousWorker(
        queue=PersistentTaskQueue(tmp_path / "tasks.json"),
        generator=StaticGenerator([]),  # type: ignore[arg-type]
        executor=cast(TaskExecutor, StaticExecutor(ExecutionOutcome("account_exhausted"))),
    )
    exausta = AutonomousTask.model_validate(
        {
            **task().model_dump(mode="json"),
            "attempts": [{}, {}, {}, {}],
        }
    )

    estado, janela = worker._transition(  # noqa: SLF001
        exausta,
        ExecutionOutcome("account_exhausted", "crédito da conta Google esgotado"),
    )

    assert estado == TaskState.RETRY_WAIT.value
    assert janela is not None


def test_rejected_e_terminal(tmp_path: Path) -> None:
    worker = AutonomousWorker(
        queue=PersistentTaskQueue(tmp_path / "tasks.json"),
        generator=StaticGenerator([]),  # type: ignore[arg-type]
        executor=cast(TaskExecutor, StaticExecutor(ExecutionOutcome("rejected"))),
    )
    estado, janela = worker._transition(  # noqa: SLF001
        task(),
        ExecutionOutcome("rejected", "falha estrutural objetiva registrada"),
    )
    assert estado == TaskState.REJECTED.value
    assert janela is None


def test_falha_de_promocao_nunca_completa_nem_aposenta(tmp_path: Path) -> None:
    worker = AutonomousWorker(
        queue=PersistentTaskQueue(tmp_path / "tasks.json"),
        generator=StaticGenerator([]),  # type: ignore[arg-type]
        executor=cast(TaskExecutor, StaticExecutor(ExecutionOutcome("failed"))),
    )
    exausta = AutonomousTask.model_validate(
        {
            **task().model_dump(mode="json"),
            "attempts": [{}, {}, {}, {}],
        }
    )
    estado, janela = worker._transition(  # noqa: SLF001
        exausta,
        ExecutionOutcome("failed", "promoção falhou: árvore de trabalho suja"),
    )
    assert estado == TaskState.RETRY_WAIT.value
    assert janela is not None


def test_reopen_blocked_operacional_preserva_identidade(tmp_path: Path) -> None:
    queue = PersistentTaskQueue(tmp_path / "tasks.json")
    candidate = task()
    queue.add_new([candidate])
    claimed = queue.claim()
    assert claimed is not None
    queue.start(claimed.id)
    blocked = queue.finish(
        claimed.id,
        state="blocked",
        outcome="error",
        detail="proponente google/gemini não produziu proposta",
        endpoints=["google/gemini-3.6-flash"],
    )

    reopened = queue.reopen_blocked(outcomes=frozenset({"error", "rate_limited"}))

    assert reopened[0].id == blocked.id
    assert reopened[0].state is TaskState.QUEUED
    assert reopened[0].attempts[-1].outcome == "error"
    assert queue.add_new([candidate]) == []
    assert queue.claim() is not None


def test_reopen_blocked_nao_toca_escalate(tmp_path: Path) -> None:
    queue = PersistentTaskQueue(tmp_path / "tasks.json")
    queue.add_new([task()])
    claimed = queue.claim()
    assert claimed is not None
    queue.start(claimed.id)
    queue.finish(claimed.id, state="blocked", outcome="escalate", detail="dissenso")

    assert queue.reopen_blocked(outcomes=frozenset({"error", "rate_limited"})) == []
    assert queue.snapshot().tasks[0].state is TaskState.BLOCKED


async def test_worker_start_reabre_bloqueio_operacional(tmp_path: Path) -> None:
    queue = PersistentTaskQueue(tmp_path / "tasks.json")
    queue.add_new([task()])
    claimed = queue.claim()
    assert claimed is not None
    queue.start(claimed.id)
    queue.finish(
        claimed.id,
        state="blocked",
        outcome="error",
        detail="limite do free tier",
        endpoints=["google/gemini-3.6-flash"],
    )
    worker = AutonomousWorker(
        queue=queue,
        generator=StaticGenerator([]),  # type: ignore[arg-type]
        executor=cast(TaskExecutor, StaticExecutor(ExecutionOutcome("completed"))),
    )

    revived = await worker.start()

    assert revived[0].state is TaskState.QUEUED
    finished = await worker.run_cycle()
    assert finished[0].state is TaskState.COMPLETED


class TestAposentadoriaDeInventarioMorto:
    """Meta sem nota é recusada por `can_start`; ela não gasta chamada, mas ocupa a fila."""

    def _fila(self, tmp_path, tarefas):
        from vault.autonomy.queue import PersistentTaskQueue

        fila = PersistentTaskQueue(tmp_path / "tasks.json")
        fila.add_new(tarefas)
        return fila

    def _tarefa(self, identificador: str, *, entidade: str | None):
        from vault.autonomy.models import AutonomousTask, TaskBudget, TaskKind, TaskOrigin

        return AutonomousTask(
            id=identificador,
            origin=TaskOrigin.REJECTED_PROPOSAL,
            objective="resolva a divergência",
            priority=40,
            domain="operacional",
            kind=TaskKind.DIVERGENCE_REVIEW,
            required_roles=["verificador-factual"],
            budget=TaskBudget(max_calls=5),
            corpus_entity=entidade,
            source_fingerprint="a" * 64,
        )

    def _sem_nota(self, task) -> bool:
        return task.corpus_entity is None

    def test_dry_run_nao_altera_nada(self, tmp_path) -> None:
        fila = self._fila(tmp_path, [self._tarefa("aut-morta-0001", entidade=None)])
        alvos = fila.retire_unclaimable(accept=self._sem_nota, reason="teste")
        assert [t.id for t in alvos] == ["aut-morta-0001"]
        assert fila.snapshot().tasks[0].state.value == "queued"

    def test_aplicar_aposenta_preservando_o_registro(self, tmp_path) -> None:
        fila = self._fila(tmp_path, [self._tarefa("aut-morta-0001", entidade=None)])
        fila.retire_unclaimable(accept=self._sem_nota, reason="motivo", dry_run=False)
        tarefa = fila.snapshot().tasks[0]
        assert tarefa.state.value == "rejected"
        assert tarefa.metadata["retired_reason"] == "motivo"
        assert tarefa.id == "aut-morta-0001"

    def test_quem_tem_nota_nao_e_tocado(self, tmp_path) -> None:
        fila = self._fila(tmp_path, [self._tarefa("aut-viva-0001", entidade="Física/N.md")])
        fila.retire_unclaimable(accept=self._sem_nota, reason="motivo", dry_run=False)
        assert fila.snapshot().tasks[0].state.value == "queued"

    def test_refresh_aposenta_meta_sem_nota(self, tmp_path) -> None:
        fila = self._fila(tmp_path, [self._tarefa("aut-morta-0002", entidade=None)])
        worker = AutonomousWorker(
            queue=fila,
            generator=StaticGenerator([]),  # type: ignore[arg-type]
            executor=cast(TaskExecutor, StaticExecutor(ExecutionOutcome("ok"))),
        )
        worker.refresh()
        tarefa = fila.snapshot().tasks[0]
        assert tarefa.state is TaskState.REJECTED
        assert tarefa.metadata["retired_reason"] == "meta sem nota herdada"


def test_capacidade_ociosa_identidade_e_o_claim_nao_o_lote(tmp_path: Path) -> None:
    """Rotacionar o acervo ocioso não pode nascer tarefa nova para o mesmo claim."""
    reader = _write_corpus(tmp_path / "knowledge")
    primeiro = TaskGenerator(
        reader,
        quorum_root=tmp_path / "runtime" / "quorum",
        models_root=tmp_path / "runtime" / "modelos",
        idle_endpoints=[f"nvidia/e{i:02d}" for i in range(1, 9)],
    ).generate()
    segundo = TaskGenerator(
        reader,
        quorum_root=tmp_path / "runtime" / "quorum",
        models_root=tmp_path / "runtime" / "modelos",
        idle_endpoints=[f"groq/e{i:02d}" for i in range(1, 9)],
    ).generate()
    idle_a = [c for c in primeiro if c.origin is TaskOrigin.IDLE_CAPACITY]
    idle_b = [c for c in segundo if c.origin is TaskOrigin.IDLE_CAPACITY]
    assert len(idle_a) == 1
    assert {c.id for c in idle_a} == {c.id for c in idle_b}
    assert idle_a[0].corpus_entity == "Dados/Nota aberta.md"


def test_generator_deriva_defeito_de_conteudo(tmp_path: Path) -> None:
    reader = _write_corpus(tmp_path / "knowledge")
    (tmp_path / "knowledge" / "Dados" / "Nota quebrada.md").write_text(
        """---
title: Nota quebrada
domain: dados
kind: fundamento
epistemic_status: mixed
updated: 2026-08-04
---

# Nota quebrada

[[MOC — Dados]] <!-- relation:navigation -->

$$
\\rho_S(t)=\\operatorname{Tr}_E\\! ig[U(t)\\rho_{SE}(0)U^\\dagger(t)\\big].
$$

## Decisão do painel abcdefabcdef

O julgamento não pertence à nota.

## Estado epistêmico

| ID | Afirmação | Status | Evidência |
| --- | --- | --- | --- |
| `CLM-DAD-QBR-001` | Há um defeito de forma. | `open` | O corpo contém ata e LaTeX mutilado. |
""",
        encoding="utf-8",
    )
    generated = TaskGenerator(
        reader,
        quorum_root=tmp_path / "runtime" / "quorum",
        models_root=tmp_path / "runtime" / "modelos",
    ).generate()
    defeitos = [
        candidate
        for candidate in generated
        if candidate.origin is TaskOrigin.CORPUS_DEFECT
    ]
    assert len(defeitos) == 1
    assert defeitos[0].corpus_entity == "Dados/Nota quebrada.md"
    assert defeitos[0].priority == 97
    assert defeitos[0].metadata["lock_targets"] is True
    assert "ata de painel" in " ".join(defeitos[0].metadata["defects"])


def test_contexto_de_defeito_trava_o_alvo() -> None:
    identifier, fingerprint = stable_task_id(
        TaskOrigin.CORPUS_DEFECT, {"note": "Dados/Nota quebrada.md"}
    )
    tarefa = AutonomousTask(
        id=identifier,
        origin=TaskOrigin.CORPUS_DEFECT,
        objective="Restaure a nota.",
        priority=97,
        domain="dados",
        kind=TaskKind.CORPUS_REVIEW,
        required_roles=list(PANEL_ROLES),
        budget=TaskBudget(),
        corpus_entity="Dados/Nota quebrada.md",
        source_fingerprint=fingerprint,
        metadata={"lock_targets": True, "allow_create": False},
    )
    contexto = corpus_patch_context(tarefa, base_commit="a" * 40)
    assert contexto[CORPUS_PATCH_ALLOWED_TARGETS_KEY] == ["Dados/Nota quebrada.md"]
    assert contexto[CORPUS_PATCH_ALLOW_CREATE_KEY] is False
    assert contexto[CORPUS_PATCH_BASE_KEY] == "a" * 40
