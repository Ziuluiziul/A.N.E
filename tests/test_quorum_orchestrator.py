"""A integração do quórum usa fakes: estes testes nunca consomem cota externa."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

import pytest

from providers.base import (
    GenerationResult,
    ModelInfo,
    ProbeResult,
    ProviderAccountExhausted,
    ProviderAdapter,
    ProviderRateLimited,
    ProviderUnavailable,
)
from providers.catalog import DiscoverySnapshot
from providers.cognitive import CognitiveEvent, CognitiveKind
from providers.inventory import Inventory, build_inventory
from providers.registry import EndpointRegistry
from vault.autonomy import (
    AutonomousTask,
    OrchestratedTaskExecutor,
    TaskBudget,
    TaskKind,
    TaskOrigin,
)
from vault.autonomy.models import PANEL_ROLES, stable_task_id
from vault.corpus import CorpusReader
from vault.promotion import CorpusPatch
from vault.quorum import (
    CORPUS_PATCH_ALLOW_CREATE_KEY,
    CORPUS_PATCH_ALLOWED_TARGETS_KEY,
    CORPUS_PATCH_BASE_KEY,
    PATCH_DIGEST_KEY,
    QuorumStore,
)
from vault.work.call_gate import ProviderCallGate
from vault.work.capacity import CapacityHints
from vault.work.orchestrator import (
    InvalidProposalEnvelope,
    PanelUnavailableError,
    QuorumExecutionError,
    QuorumOrchestrator,
)
from vault.work.quotas import QuotaLedger, RunBudget
from vault.work.store import WorkStore
from vault.work.tasks import Task

SECRET_REASONING = "RACIOCINIO_INTERNO_NAO_PERSISTIR"

ENDPOINTS = (
    ("groq", "alpha-4", "alpha"),
    ("groq", "beta-3", "beta"),
    ("nvidia", "gamma-2", "gamma"),
    ("nvidia", "delta-1", "delta"),
    ("groq", "epsilon-1", "epsilon"),
)


def inventory_for(entries: tuple[tuple[str, str, str], ...] = ENDPOINTS) -> Inventory:
    snapshots: dict[str, DiscoverySnapshot] = {}
    registry = EndpointRegistry()
    by_provider: dict[str, list[ModelInfo]] = {}
    for provider, endpoint_id, family in entries:
        by_provider.setdefault(provider, []).append(
            ModelInfo(
                provider=provider,
                endpoint_id=endpoint_id,
                family=family,
                available=True,
                context_window=128_000,
            )
        )
        registry.record_probe(ProbeResult(provider, endpoint_id, "ok", "ok", 1))
    for provider, models in by_provider.items():
        snapshots[provider] = DiscoverySnapshot(
            path=Path(f"models-{provider}.json"),
            models=models,
        )
    return build_inventory(snapshots, registry)


def vote_payload(
    decision: str,
    *,
    blocking_issues: list[str] | None = None,
) -> str:
    actions = {
        "approve": "promote",
        "reject": "reject",
        "revise": "revise",
        "abstain": "escalate",
    }
    return json.dumps(
        {
            "decision": decision,
            "confidence": 0.8,
            "blocking_issues": blocking_issues or [],
            "non_blocking_issues": [],
            "evidence": [],
            "recommended_action": actions[decision],
        }
    )


class FakeAdapter:
    def __init__(
        self,
        provider: str,
        calls: list[tuple[str, str, str]],
        votes: dict[str, str],
        *,
        invalid_role: str | None = None,
        invalid_patch: bool = False,
        blocking_by_role: dict[str, list[str]] | None = None,
        patch_path: str = "Teste.md",
        empty_endpoints: set[str] | None = None,
        spent_invalid: list[str] | None = None,
        patch_suffix: str = "",
        truncate_patch: bool = False,
        output_tokens: list[int] | None = None,
        think_only_endpoints: set[str] | None = None,
        extra_field: bool = False,
    ) -> None:
        self.provider = provider
        self.calls = calls
        self.votes = votes
        self.invalid_role = invalid_role
        self.invalid_patch = invalid_patch
        self.blocking_by_role = blocking_by_role or {}
        self.patch_path = patch_path
        self.empty_endpoints = set(empty_endpoints or [])
        self.spent_invalid = spent_invalid if spent_invalid is not None else []
        self.patch_suffix = patch_suffix
        self.truncate_patch = truncate_patch
        self.output_tokens = output_tokens if output_tokens is not None else []
        self.think_only_endpoints = set(think_only_endpoints or [])
        self.extra_field = extra_field

    async def generate(
        self,
        endpoint_id: str,
        prompt: str,
        *,
        max_output_tokens: int = 256,
    ) -> GenerationResult:
        self.calls.append((self.provider, endpoint_id, prompt))
        self.output_tokens.append(max_output_tokens)
        if endpoint_id in self.empty_endpoints:
            return GenerationResult(
                provider=self.provider,
                endpoint_id=endpoint_id,
                text="",
                usage={"total_tokens": 1},
            )
        if endpoint_id in self.think_only_endpoints:
            return GenerationResult(
                provider=self.provider,
                endpoint_id=endpoint_id,
                text=f"<think>{SECRET_REASONING}</think>",
                usage={"total_tokens": 8},
            )
        return GenerationResult(
            provider=self.provider,
            endpoint_id=endpoint_id,
            text=self._texto(prompt),
            usage={"total_tokens": 10},
        )

    async def stream_generate(
        self,
        endpoint_id: str,
        prompt: str,
        *,
        max_output_tokens: int = 256,
    ) -> AsyncIterator[CognitiveEvent]:
        """O quórum consome stream nos adaptadores reais; o fake precisa percorrer o
        mesmo caminho, ou a contabilidade testada é a do caminho antigo, que não existe
        mais. O texto emitido é idêntico ao de `generate`: mesmo delta de conteúdo e o
        consumo real no `FINAL`, como os adaptadores concretos fazem."""
        self.calls.append((self.provider, endpoint_id, prompt))
        self.output_tokens.append(max_output_tokens)
        if endpoint_id in self.empty_endpoints:
            yield CognitiveEvent(
                provider=self.provider,
                endpoint_id=endpoint_id,
                kind=CognitiveKind.FINAL,
                raw_field="stream.end",
                sequence=1,
                detail={"usage": {"total_tokens": 1}},
            )
            return
        if endpoint_id in self.think_only_endpoints:
            texto = f"<think>{SECRET_REASONING}</think>"
        else:
            texto = self._texto(prompt)
        sequencia = 0
        if texto:
            sequencia += 1
            yield CognitiveEvent(
                provider=self.provider,
                endpoint_id=endpoint_id,
                kind=CognitiveKind.OUTPUT_DELTA,
                text=texto,
                raw_field="delta.content",
                sequence=sequencia,
            )
        sequencia += 1
        yield CognitiveEvent(
            provider=self.provider,
            endpoint_id=endpoint_id,
            kind=CognitiveKind.FINAL,
            raw_field="stream.end",
            sequence=sequencia,
            detail={"usage": {"total_tokens": 10}},
        )

    def _texto(self, prompt: str) -> str:
        role = self._role(prompt)
        if role == "proponente":
            if "proposal_id exato:" in prompt:
                repairing = "Resposta a reparar:" in prompt
                if self.invalid_patch:
                    return '{"operations":[]}'
                proposal_id = re.search(r"proposal_id exato: ([0-9a-f]+)", prompt)
                base_commit = re.search(r"base_commit exato: ([0-9a-f]+)", prompt)
                assert proposal_id is not None and base_commit is not None
                corpo = {
                    "proposal_id": proposal_id.group(1),
                    "base_commit": base_commit.group(1),
                    "operations": [
                        {
                            "action": "create",
                            "path": self.patch_path,
                            "content": "# Teste\n\nConteúdo integral.",
                        }
                    ],
                }
                if self.extra_field:
                    corpo["campo_extra"] = True
                payload = json.dumps(corpo)
                if repairing:
                    return payload
                if self.truncate_patch:
                    return payload[: max(len(payload) // 2, 8)]
                return payload + self.patch_suffix
            return f"<think>{SECRET_REASONING}</think>Proposta final verificável."
        if role == self.invalid_role and role not in self.spent_invalid:
            self.spent_invalid.append(role)
            return f"<think>{SECRET_REASONING}</think>isto não é JSON"
        payload = vote_payload(
            self.votes[role],
            blocking_issues=self.blocking_by_role.get(role),
        )
        return f"<think>{SECRET_REASONING}</think>{payload}"

    @staticmethod
    def _role(prompt: str) -> str:
        markers = {
            "Você propõe uma alteração": "proponente",
            "Você verifica fatos": "verificador-factual",
            "Você avalia força epistêmica": "critico-epistemologico",
            "Você verifica forma": "revisor-estrutural",
            "Você decide um empate": "arbitro",
        }
        for marker, role in markers.items():
            if marker in prompt:
                return role
        raise AssertionError(f"prompt sem papel reconhecível: {prompt[:120]}")


class _FailingStreamAdapter:
    """Um provedor que começa a responder e aborta: falha com erro de provedor.

    O quórum consome stream nos adaptadores reais; este fake lança `ProviderUnavailable`
    antes do `FINAL`, como um upstream cortado no meio da resposta. É o mesmo caminho
    que o orquestrador precisa tolerar sem derrubar os demais votos do `gather`.
    """

    def __init__(self, provider: str, calls: list[tuple[str, str, str]]) -> None:
        self.provider = provider
        self.calls = calls

    async def generate(
        self,
        endpoint_id: str,
        prompt: str,
        *,
        max_output_tokens: int = 256,
    ) -> GenerationResult:
        self.calls.append((self.provider, endpoint_id, prompt))
        raise ProviderUnavailable(f"{self.provider}/{endpoint_id} fora do ar (simulado)")

    async def stream_generate(
        self,
        endpoint_id: str,
        prompt: str,
        *,
        max_output_tokens: int = 256,
    ) -> AsyncIterator[CognitiveEvent]:
        self.calls.append((self.provider, endpoint_id, prompt))
        yield CognitiveEvent(
            provider=self.provider,
            endpoint_id=endpoint_id,
            kind=CognitiveKind.REASONING,
            text="pensando até a queda...",
            raw_field="delta.reasoning",
            sequence=1,
        )
        raise ProviderUnavailable(f"{self.provider}/{endpoint_id} fora do ar (simulado)")


def build_orchestrator(
    tmp_path: Path,
    *,
    votes: dict[str, str],
    entries: tuple[tuple[str, str, str], ...] = ENDPOINTS,
    invalid_role: str | None = None,
    invalid_patch: bool = False,
    blocking_by_role: dict[str, list[str]] | None = None,
    max_calls: int = 6,
    patch_path: str = "Teste.md",
    empty_endpoints: set[str] | None = None,
    patch_suffix: str = "",
    truncate_patch: bool = False,
    think_only_endpoints: set[str] | None = None,
    extra_field: bool = False,
) -> tuple[QuorumOrchestrator, list[tuple[str, str, str]], QuorumStore]:
    calls: list[tuple[str, str, str]] = []
    spent_invalid: list[str] = []
    output_tokens: list[int] = []
    adapters = {
        provider: cast(
            ProviderAdapter,
            FakeAdapter(
                provider,
                calls,
                votes,
                invalid_role=invalid_role,
                invalid_patch=invalid_patch,
                blocking_by_role=blocking_by_role,
                patch_path=patch_path,
                empty_endpoints=empty_endpoints,
                spent_invalid=spent_invalid,
                patch_suffix=patch_suffix,
                truncate_patch=truncate_patch,
                output_tokens=output_tokens,
                think_only_endpoints=think_only_endpoints,
                extra_field=extra_field,
            ),
        )
        for provider in {entry[0] for entry in entries}
    }
    store = QuorumStore(tmp_path / "quorum")
    orchestrator = QuorumOrchestrator(
        inventory=inventory_for(entries),
        adapters=adapters,
        ledger=QuotaLedger(),
        budget=RunBudget(max_calls=max_calls),
        store=store,
        work_store=WorkStore(tmp_path / "modelos"),
    )
    return orchestrator, calls, store


def quorum_task() -> Task:
    return Task(
        kind="teste-quorum",
        role_name="proponente",
        prompt="Produza uma proposta pequena.",
        max_output_tokens=128,
    )


def patch_task() -> Task:
    return Task(
        kind="teste-patch",
        role_name="proponente",
        prompt="Crie a nota Teste.md com o conteúdo integral pedido.",
        max_output_tokens=512,
        context={CORPUS_PATCH_BASE_KEY: "a" * 40},
    )


def test_proponente_faz_fair_share_pelo_ledger(tmp_path: Path) -> None:
    orchestrator, _calls, _store = build_orchestrator(tmp_path, votes={})
    orchestrator.ledger.record_call(
        endpoint="groq/alpha-4",
        provider="groq",
        tokens=1,
    )

    assignment, refusal = orchestrator._select_proposer(  # noqa: SLF001
        quorum_task(),
        orchestrator._callable_profiles(),  # noqa: SLF001
    )

    assert refusal == ""
    assert assignment is not None
    assert assignment.provider == "nvidia"
    assert "fair-share" in assignment.reason


async def test_proponente_considera_carga_pendente_compartilhada(tmp_path: Path) -> None:
    orchestrator, _calls, _store = build_orchestrator(tmp_path, votes={})
    gate = ProviderCallGate({"groq": 1, "nvidia": 1})
    orchestrator.call_gate = gate
    acquired = asyncio.Event()

    async def pending_call() -> None:
        async with gate.slot("groq", "modelo-pendente"):
            acquired.set()

    async with gate.slot("groq", "modelo-ativo"):
        queued = asyncio.create_task(pending_call())
        for _ in range(100):
            if gate.pending("groq") == 1:
                break
            await asyncio.sleep(0)
        else:
            pytest.fail("chamada pendente não entrou no gate")

        assignment, refusal = orchestrator._select_proposer(  # noqa: SLF001
            quorum_task(),
            orchestrator._callable_profiles(),  # noqa: SLF001
        )
        assert refusal == ""
        assert assignment is not None
        assert assignment.provider == "nvidia"
        assert "fair-share" in assignment.reason
        queued.cancel()
        with pytest.raises(asyncio.CancelledError):
            await queued
    assert not acquired.is_set()


def _tarefas_de_revisao(dominio: str = "Física") -> list[Task]:
    return [
        Task(
            kind="corpus_review",
            role_name=papel,
            prompt="avalie a proposta",
            max_output_tokens=512,
            context={"domain": dominio},
        )
        for papel in PANEL_ROLES
    ]


def test_endpoint_condenado_pelo_ledger_nao_entra_na_selecao(tmp_path: Path) -> None:
    """A-4: verde no inventário e morto na telemetria não é candidato a voto."""
    orchestrator, _calls, _store = build_orchestrator(tmp_path, votes={})
    condenado = ENDPOINTS[0]
    orchestrator.capacity_hints = lambda: CapacityHints(
        unfit=frozenset({f"{condenado[0]}/{condenado[1]}"})
    )

    chaves = {p.key for p in orchestrator._callable_profiles()}  # noqa: SLF001

    assert f"{condenado[0]}/{condenado[1]}" not in chaves
    assert "nvidia/gamma-2" in chaves


def test_pista_que_falha_nao_derruba_a_selecao(tmp_path: Path) -> None:
    def pista_quebrada() -> CapacityHints:
        raise OSError("ledger ilegível")

    orchestrator, _calls, _store = build_orchestrator(tmp_path, votes={})
    orchestrator.capacity_hints = pista_quebrada

    chaves = {p.key for p in orchestrator._callable_profiles()}  # noqa: SLF001

    assert "groq/alpha-4" in chaves


def test_aptidao_reordena_o_trio_de_revisores_sem_afrouxar_diversidade(
    tmp_path: Path,
) -> None:
    """Preferência, não veredito: o melhor histórico vence entre trios igualmente válidos."""
    estrela = "nvidia/estrela-1"
    orchestrator, _calls, _store = build_orchestrator(
        tmp_path,
        votes={},
        entries=(
            ("groq", "alpha-4", "alpha"),
            ("groq", "beta-3", "beta"),
            ("groq", "gama-2", "gama"),
            ("nvidia", "delta-1", "delta"),
            ("nvidia", "estrela-1", "estrela"),
        ),
    )
    tarefas = _tarefas_de_revisao()

    sem_pistas, refusal = orchestrator._plan_distinct(  # noqa: SLF001
        tarefas,
        orchestrator._callable_profiles(),  # noqa: SLF001
    )
    assert sem_pistas is not None, refusal
    assert all(assignment.endpoint_id != "estrela-1" for assignment in sem_pistas)

    orchestrator.capacity_hints = lambda: CapacityHints(
        aptitude={("vote", estrela, papel, "Física"): 1.0 for papel in PANEL_ROLES}
    )
    com_pistas, refusal = orchestrator._plan_distinct(  # noqa: SLF001
        tarefas,
        orchestrator._callable_profiles(),  # noqa: SLF001
    )
    assert com_pistas is not None, refusal
    escolhidos = [assignment.endpoint_id for assignment in com_pistas]
    assert "estrela-1" in escolhidos
    provedores = {a.provider for a in com_pistas}
    perfis = orchestrator._callable_profiles()  # noqa: SLF001
    familias = {p.family for p in perfis if p.endpoint_id in escolhidos}
    assert len(provedores) >= 2
    assert len(familias) >= 2


def test_unfit_de_voto_nao_vence_aptidao_mas_entra_se_a_diversidade_pedir(
    tmp_path: Path,
) -> None:
    """UNFIT é o fim da fila, não a porta fechada."""
    estrela = "nvidia/estrela-1"
    nvidia = ("nvidia/delta-1", "nvidia/estrela-1")
    orchestrator, _calls, _store = build_orchestrator(
        tmp_path,
        votes={},
        entries=(
            ("groq", "alpha-4", "alpha"),
            ("groq", "beta-3", "beta"),
            ("groq", "gama-2", "gama"),
            ("nvidia", "delta-1", "delta"),
            ("nvidia", "estrela-1", "estrela"),
        ),
    )
    tarefas = _tarefas_de_revisao()
    orchestrator.capacity_hints = lambda: CapacityHints(
        aptitude={("vote", estrela, papel, "Física"): 1.0 for papel in PANEL_ROLES},
        unfit_por_estagio={"vote": frozenset({estrela})},
    )
    sem_estrela, refusal = orchestrator._plan_distinct(  # noqa: SLF001
        tarefas,
        orchestrator._callable_profiles(),  # noqa: SLF001
    )
    assert sem_estrela is not None, refusal
    assert all(assignment.endpoint_id != "estrela-1" for assignment in sem_estrela)

    orchestrator.capacity_hints = lambda: CapacityHints(
        unfit_por_estagio={"vote": frozenset(nvidia)},
    )
    com_nvidia, refusal = orchestrator._plan_distinct(  # noqa: SLF001
        tarefas,
        orchestrator._callable_profiles(),  # noqa: SLF001
    )
    assert com_nvidia is not None, refusal
    assert any(assignment.provider == "nvidia" for assignment in com_nvidia)


def test_aptidao_de_proposta_desempata_sem_furar_fair_share(tmp_path: Path) -> None:
    estrela = "nvidia/delta-1"
    orchestrator, _calls, _store = build_orchestrator(tmp_path, votes={})
    orchestrator.capacity_hints = lambda: CapacityHints(
        aptitude={("proposal", estrela, "proponente", "—"): 1.0},
    )
    preferido, refusal = orchestrator._select_proposer(  # noqa: SLF001
        quorum_task(),
        orchestrator._callable_profiles(),  # noqa: SLF001
    )
    assert refusal == ""
    assert preferido is not None
    assert preferido.endpoint_id == "delta-1"

    orchestrator.ledger.record_call(endpoint=estrela, provider="nvidia", tokens=1)
    equilibrado, refusal = orchestrator._select_proposer(  # noqa: SLF001
        quorum_task(),
        orchestrator._callable_profiles(),  # noqa: SLF001
    )
    assert refusal == ""
    assert equilibrado is not None
    assert equilibrado.provider == "groq"


async def test_fluxo_completo_isola_raciocinio_e_persiste_decisao(tmp_path: Path) -> None:
    orchestrator, calls, store = build_orchestrator(
        tmp_path,
        votes={
            "verificador-factual": "approve",
            "critico-epistemologico": "approve",
            "revisor-estrutural": "revise",
            "arbitro": "approve",
        },
    )

    panel = await orchestrator.run(quorum_task())

    assert panel.decision is not None
    assert panel.decision.outcome.value == "promote"
    assert len(calls) == 4
    assert orchestrator.ledger.run_calls == 4
    for chave, registros in orchestrator.ledger.events.items():
        assert registros, chave
        assert all(tokens == 10 for _, tokens in registros), (
            f"{chave}: consumo deve sair do FINAL do stream, não da estimativa"
        )
    assert panel.proposal.reasoning_block_detected
    assert panel.proposal.final_response == "Proposta final verificável."
    assert {member.role_name for member in panel.members} == {
        "verificador-factual",
        "critico-epistemologico",
        "revisor-estrutural",
    }
    assert panel.proposal.proposer.key not in {member.key for member in panel.members}
    assert len({member.key for member in panel.members}) == 3
    assert len({member.provider for member in panel.members}) >= 2
    assert len({member.family for member in panel.members}) >= 2
    assert all(SECRET_REASONING not in prompt for _, _, prompt in calls[1:])

    persisted = "\n".join(
        path.read_text(encoding="utf-8") for path in tmp_path.rglob("*") if path.is_file()
    )
    assert SECRET_REASONING not in persisted
    assert "<think>" not in persisted
    loaded = store.load_panel(panel.id)
    assert loaded.decision is not None
    assert loaded.decision.outcome.value == "promote"
    assert len(loaded.votes) == 3


async def test_openrouter_pode_propor_mas_nao_entra_nos_avaliadores(tmp_path: Path) -> None:
    entries = (
        ("openrouter", "00-modelo:free", "gateway-modelo"),
        ("groq", "a-modelo", "familia-a"),
        ("groq", "b-modelo", "familia-b"),
        ("nvidia", "c-modelo", "familia-c"),
    )
    orchestrator, calls, _ = build_orchestrator(
        tmp_path,
        entries=entries,
        votes={
            "verificador-factual": "approve",
            "critico-epistemologico": "approve",
            "revisor-estrutural": "approve",
            "arbitro": "approve",
        },
    )

    panel = await orchestrator.run(quorum_task())

    assert panel.proposal.proposer.provider == "openrouter"
    assert {member.provider for member in panel.members} == {"groq", "nvidia"}
    assert calls[0][0] == "openrouter"
    assert all(provider != "openrouter" for provider, _, _ in calls[1:])


async def test_patch_do_model_e_o_artefato_votado_e_persistido(tmp_path: Path) -> None:
    orchestrator, calls, store = build_orchestrator(
        tmp_path,
        votes={
            "verificador-factual": "approve",
            "critico-epistemologico": "approve",
            "revisor-estrutural": "approve",
            "arbitro": "approve",
        },
    )

    panel = await orchestrator.run(patch_task())

    raw_patch = store.load_patch(panel.id)
    assert raw_patch is not None
    patch = CorpusPatch.model_validate(raw_patch)
    assert patch.proposal_id == panel.proposal.id
    assert patch.base_commit == "a" * 40
    assert json.loads(panel.proposal.final_response) == raw_patch
    assert panel.task.context[PATCH_DIGEST_KEY] == patch.digest()
    assert panel.decision is not None and panel.decision.outcome.value == "promote"
    assert len(calls) == 4
    assert all(panel.proposal.final_response in prompt for _, _, prompt in calls[1:])
    assert all(
        "recommended_action aceita somente o enum exato" in prompt for _, _, prompt in calls[1:]
    )


async def test_ciclo_de_quorum_emite_eventos_fechados_sem_resposta_livre(
    tmp_path: Path,
) -> None:
    orchestrator, _, _ = build_orchestrator(
        tmp_path,
        votes={
            "verificador-factual": "approve",
            "critico-epistemologico": "approve",
            "revisor-estrutural": "approve",
            "arbitro": "approve",
        },
    )
    events: list[tuple[str, dict[str, object]]] = []
    orchestrator.emit = lambda kind, payload: events.append((kind, payload))

    await orchestrator.run(patch_task())

    kinds = [kind for kind, _ in events]
    assert kinds.count("call_started") == 4
    assert kinds.count("call_completed") == 4
    assert kinds.count("evidence_recorded") == 4
    assert kinds.count("vote_requested") == 3
    assert kinds.count("vote_received") == 3
    assert "proposal_created" in kinds
    assert "temporary_created" in kinds
    assert "quorum_started" in kinds
    assert kinds[-1] == "quorum_decided"
    call_starts = [payload for kind, payload in events if kind == "call_started"]
    assert all(
        cast(dict[str, object], payload["metadata"]).get("deadline_seconds") == 240
        for payload in call_starts
    )
    serialized = json.dumps(events, ensure_ascii=False)
    assert "final_response" not in serialized
    assert SECRET_REASONING not in serialized


async def test_patch_malformado_encerra_sem_retry_nem_painel(tmp_path: Path) -> None:
    """Envelope irrecuperável (schema) aborta sem reparo e sem rotacionar."""
    orchestrator, calls, store = build_orchestrator(
        tmp_path,
        votes={
            "verificador-factual": "approve",
            "critico-epistemologico": "approve",
            "revisor-estrutural": "approve",
            "arbitro": "approve",
        },
        invalid_patch=True,
    )

    with pytest.raises(InvalidProposalEnvelope, match="patch inválido"):
        await orchestrator.run(patch_task())

    assert len(calls) == 1
    assert store.list_panels() == []


async def test_envelope_vazio_apos_think_passa_ao_proximo_proponente(tmp_path: Path) -> None:
    """HTTP 200 só com think não repara o mesmo endpoint: o lote segue no próximo."""
    orchestrator, calls, store = build_orchestrator(
        tmp_path,
        votes={
            "verificador-factual": "approve",
            "critico-epistemologico": "approve",
            "revisor-estrutural": "approve",
            "arbitro": "approve",
        },
        max_calls=8,
    )
    primeiro, refusal = orchestrator._select_proposer(  # noqa: SLF001
        patch_task(),
        orchestrator._callable_profiles(),  # noqa: SLF001
    )
    assert primeiro is not None, refusal
    adapter = orchestrator.adapters[primeiro.provider]
    adapter.think_only_endpoints.add(primeiro.endpoint_id)  # type: ignore[attr-defined]

    panel = await orchestrator.run(patch_task())

    assert panel.decision is not None
    assert [item.id for item in store.list_panels()] == [panel.id]
    proposer_calls = [
        (provider, endpoint, prompt)
        for provider, endpoint, prompt in calls
        if "proposal_id exato:" in prompt
    ]
    assert len(proposer_calls) == 2
    assert proposer_calls[0][:2] == (primeiro.provider, primeiro.endpoint_id)
    assert proposer_calls[1][0] != primeiro.provider
    assert all("Resposta a reparar:" not in prompt for _, _, prompt in proposer_calls)
    assert panel.proposal.proposer.provider != primeiro.provider


async def test_campo_extra_nao_rotaciona_proponente(tmp_path: Path) -> None:
    orchestrator, calls, store = build_orchestrator(
        tmp_path,
        votes={
            "verificador-factual": "approve",
            "critico-epistemologico": "approve",
            "revisor-estrutural": "approve",
            "arbitro": "approve",
        },
        extra_field=True,
    )

    with pytest.raises(InvalidProposalEnvelope, match="patch inválido"):
        await orchestrator.run(patch_task())

    assert len(calls) == 1
    assert store.list_panels() == []


async def test_prosa_trailing_no_envelope_nao_dispara_reparo(tmp_path: Path) -> None:
    orchestrator, calls, store = build_orchestrator(
        tmp_path,
        votes={
            "verificador-factual": "approve",
            "critico-epistemologico": "approve",
            "revisor-estrutural": "approve",
            "arbitro": "approve",
        },
        patch_suffix="\n\nAqui a ata do painel e um $$ LaTeX.",
    )

    panel = await orchestrator.run(patch_task())

    assert panel.decision is not None
    assert len(calls) == 4
    assert all("Resposta a reparar:" not in prompt for _, _, prompt in calls)
    assert [item.id for item in store.list_panels()] == [panel.id]


async def test_json_truncado_repara_uma_vez_sem_subir_tokens(tmp_path: Path) -> None:
    orchestrator, calls, store = build_orchestrator(
        tmp_path,
        votes={
            "verificador-factual": "approve",
            "critico-epistemologico": "approve",
            "revisor-estrutural": "approve",
            "arbitro": "approve",
        },
        truncate_patch=True,
    )
    task = patch_task()
    panel = await orchestrator.run(task)

    assert panel.decision is not None
    assert [item.id for item in store.list_panels()] == [panel.id]
    proposer_calls = [prompt for _, _, prompt in calls if "proposal_id exato:" in prompt]
    assert len(proposer_calls) == 2
    assert "Resposta a reparar:" in proposer_calls[1]
    tetos = next(iter(orchestrator.adapters.values())).output_tokens  # type: ignore[attr-defined]
    assert tetos[:2] == [task.max_output_tokens, task.max_output_tokens]


async def test_tarefa_autonoma_nao_pode_criar_nota(tmp_path: Path) -> None:
    orchestrator, calls, store = build_orchestrator(
        tmp_path,
        votes={
            "verificador-factual": "approve",
            "critico-epistemologico": "approve",
            "revisor-estrutural": "approve",
            "arbitro": "approve",
        },
    )
    task = patch_task()
    task = Task(
        kind=task.kind,
        role_name=task.role_name,
        prompt=task.prompt,
        max_output_tokens=task.max_output_tokens,
        context={
            **task.context,
            CORPUS_PATCH_ALLOWED_TARGETS_KEY: ["Teste.md"],
            CORPUS_PATCH_ALLOW_CREATE_KEY: False,
        },
    )

    with pytest.raises(QuorumExecutionError, match="não autoriza criar nota"):
        await orchestrator.run(task)

    assert len(calls) == 1
    assert store.list_panels() == []


async def test_patch_nao_pode_sair_do_alvo_autorizado(tmp_path: Path) -> None:
    orchestrator, calls, store = build_orchestrator(
        tmp_path,
        votes={
            "verificador-factual": "approve",
            "critico-epistemologico": "approve",
            "revisor-estrutural": "approve",
            "arbitro": "approve",
        },
    )
    task = patch_task()
    task = Task(
        kind=task.kind,
        role_name=task.role_name,
        prompt=task.prompt,
        max_output_tokens=task.max_output_tokens,
        context={
            **task.context,
            CORPUS_PATCH_ALLOWED_TARGETS_KEY: ["Outra.md"],
            CORPUS_PATCH_ALLOW_CREATE_KEY: True,
        },
    )

    with pytest.raises(QuorumExecutionError, match="saiu dos alvos autorizados"):
        await orchestrator.run(task)

    assert len(calls) == 1
    assert store.list_panels() == []


async def test_voto_invalido_e_reposto_sem_escalar_o_patch(tmp_path: Path) -> None:
    orchestrator, calls, store = build_orchestrator(
        tmp_path,
        votes={
            "verificador-factual": "approve",
            "critico-epistemologico": "approve",
            "revisor-estrutural": "approve",
            "arbitro": "approve",
        },
        invalid_role="verificador-factual",
        max_calls=10,
    )

    panel = await orchestrator.run(quorum_task())

    assert panel.decision is not None
    assert panel.decision.valid_vote_count >= 3
    assert panel.decision.outcome.value == "promote"
    assert any(not vote.schema_valid for vote in panel.votes)
    assert len(panel.members) >= 4
    assert len(calls) >= 5
    recarregado = store.load_panel(panel.id)
    assert recarregado.decision is not None
    assert recarregado.decision.outcome.value == "promote"


async def test_gather_com_membro_falho_vira_abstencao_sem_duplicar_cota(
    tmp_path: Path,
) -> None:
    """A falha de um provedor no `gather` não cancela os demais votos nem a cota.

    Um adaptador que aborta no meio do stream precisa (a) virar abstenção no painel,
    (b) deixar os outros membros concluírem o voto e (c) ser contabilizado uma única
    vez, com zero tokens — porque a chamada falhou, mas foi feita.
    """
    calls: list[tuple[str, str, str]] = []
    votes = {
        "verificador-factual": "approve",
        "critico-epistemologico": "approve",
        "revisor-estrutural": "approve",
        "arbitro": "approve",
    }
    adapters: dict[str, ProviderAdapter] = {
        "groq": cast(ProviderAdapter, FakeAdapter("groq", calls, votes)),
        "nvidia": cast(ProviderAdapter, _FailingStreamAdapter("nvidia", calls)),
    }
    orchestrator = QuorumOrchestrator(
        inventory=inventory_for(ENDPOINTS),
        adapters=adapters,
        ledger=QuotaLedger(),
        budget=RunBudget(max_calls=6),
        store=QuorumStore(tmp_path / "quorum"),
        work_store=WorkStore(tmp_path / "modelos"),
    )

    panel = await orchestrator.run(quorum_task())

    assert len(calls) == 4
    assert orchestrator.ledger.run_calls == 4
    assert panel.decision is not None
    assert panel.decision.outcome.value == "escalate"
    falhos = [voto for voto in panel.votes if not voto.schema_valid]
    assert falhos
    assert all(voto.reviewer.provider == "nvidia" for voto in falhos)
    assert all(voto.structured_vote.decision.value == "abstain" for voto in falhos)
    validos = [voto for voto in panel.votes if voto.schema_valid]
    assert validos
    assert all(voto.structured_vote.decision.value == "approve" for voto in validos)
    assert panel.decision.valid_vote_count == len(validos)
    nvidia_endpoints = [c[1] for c in calls if c[0] == "nvidia"]
    assert sorted(nvidia_endpoints) == ["delta-1", "gamma-2"]
    registros_nvidia = orchestrator.ledger.events["nvidia"]
    assert registros_nvidia == [(at, 0) for at, _ in registros_nvidia]


async def test_empate_usa_arbitro_independente_sem_expor_respostas(tmp_path: Path) -> None:
    orchestrator, calls, store = build_orchestrator(
        tmp_path,
        votes={
            "verificador-factual": "approve",
            "critico-epistemologico": "reject",
            "revisor-estrutural": "revise",
            "arbitro": "approve",
        },
        blocking_by_role={"critico-epistemologico": ["ressalva não estrutural"]},
    )

    panel = await orchestrator.run(quorum_task())

    assert panel.decision is not None
    assert panel.decision.outcome.value == "promote"
    assert panel.decision.synthesized_by is not None
    used = {panel.proposal.proposer.key, *(member.key for member in panel.members)}
    assert panel.decision.synthesized_by.key not in used
    assert len(calls) == 5
    assert len({(provider, endpoint) for provider, endpoint, _ in calls}) == 5
    arbitration_prompt = calls[-1][2]
    assert "final_response" not in arbitration_prompt
    assert SECRET_REASONING not in arbitration_prompt
    loaded = store.load_panel(panel.id)
    assert loaded.decision is not None
    assert loaded.decision.synthesized_by == panel.decision.synthesized_by


async def test_rejeicao_estrutural_objetiva_vence_maioria(tmp_path: Path) -> None:
    orchestrator, calls, _ = build_orchestrator(
        tmp_path,
        votes={
            "verificador-factual": "approve",
            "critico-epistemologico": "approve",
            "revisor-estrutural": "reject",
            "arbitro": "approve",
        },
        blocking_by_role={"revisor-estrutural": ["wikilink sem relation"]},
    )

    panel = await orchestrator.run(quorum_task())

    assert panel.decision is not None
    assert panel.decision.outcome.value == "reject"
    assert panel.decision.reason == "falha estrutural objetiva registrada"
    assert [failure.issue for failure in panel.decision.structural_failures] == [
        "wikilink sem relation"
    ]
    assert panel.decision.structural_failures[0].reviewer is not None
    assert len(calls) == 4


async def test_empate_sem_quinto_endpoint_escala_com_motivo(tmp_path: Path) -> None:
    orchestrator, calls, _ = build_orchestrator(
        tmp_path,
        votes={
            "verificador-factual": "approve",
            "critico-epistemologico": "reject",
            "revisor-estrutural": "revise",
            "arbitro": "approve",
        },
        entries=ENDPOINTS[:4],
    )

    panel = await orchestrator.run(quorum_task())

    assert panel.decision is not None
    assert panel.decision.outcome.value == "escalate"
    assert "síntese não executada" in panel.decision.reason
    assert "sem endpoint independente" in panel.decision.reason
    assert len(calls) == 4


def _patch_task_com_alvos(alvos: list[str]) -> Task:
    base = patch_task()
    return Task(
        kind=base.kind,
        role_name=base.role_name,
        prompt=base.prompt,
        max_output_tokens=base.max_output_tokens,
        context={
            **base.context,
            CORPUS_PATCH_ALLOWED_TARGETS_KEY: alvos,
            CORPUS_PATCH_ALLOW_CREATE_KEY: True,
        },
    )


async def test_alvo_com_caixa_divergente_resolve_para_o_caminho_canonico(
    tmp_path: Path,
) -> None:
    """`domain: física` no frontmatter induz o proponente a escrever o alvo minúsculo.

    Recusar o patch perderia a proposta certa; aceitar a variante deixaria o Promoter
    criar uma segunda taxonomia. O alvo é reescrito para o caminho autorizado.
    """
    orchestrator, _, store = build_orchestrator(
        tmp_path,
        votes={
            "verificador-factual": "approve",
            "critico-epistemologico": "approve",
            "revisor-estrutural": "approve",
            "arbitro": "approve",
        },
        patch_path="física/Gravidade.md",
    )

    panel = await orchestrator.run(_patch_task_com_alvos(["Física/Gravidade.md"]))

    assert "Física/Gravidade.md" in panel.proposal.final_response
    assert "física/Gravidade.md" not in panel.proposal.final_response
    persisted = store.load_panel(panel.id)
    assert persisted.proposal.final_response == panel.proposal.final_response


async def test_alvo_ambiguo_entre_autorizados_e_recusado(tmp_path: Path) -> None:
    orchestrator, calls, store = build_orchestrator(
        tmp_path,
        votes={
            "verificador-factual": "approve",
            "critico-epistemologico": "approve",
            "revisor-estrutural": "approve",
            "arbitro": "approve",
        },
        patch_path="física/Gravidade.md",
    )
    task = _patch_task_com_alvos(["Física/Gravidade.md", "FÍSICA/Gravidade.md"])

    with pytest.raises(QuorumExecutionError, match="ambíguo"):
        await orchestrator.run(task)

    assert len(calls) == 1
    assert store.list_panels() == []


async def test_travessia_de_caminho_nao_vira_patch(tmp_path: Path) -> None:
    orchestrator, calls, store = build_orchestrator(
        tmp_path,
        votes={
            "verificador-factual": "approve",
            "critico-epistemologico": "approve",
            "revisor-estrutural": "approve",
            "arbitro": "approve",
        },
        patch_path="../fora-do-corpus.md",
    )

    with pytest.raises(QuorumExecutionError, match="patch inválido"):
        await orchestrator.run(_patch_task_com_alvos(["../fora-do-corpus.md"]))

    assert len(calls) == 1
    assert store.list_panels() == []


def _executor(tmp_path: Path) -> OrchestratedTaskExecutor:
    (tmp_path / "knowledge").mkdir(exist_ok=True)
    return OrchestratedTaskExecutor(
        inventory=inventory_for(),
        adapters={},
        ledger=QuotaLedger(),
        process_budget=RunBudget(max_calls=10),
        quorum_store=QuorumStore(tmp_path / "quorum"),
        work_store=WorkStore(tmp_path / "modelos"),
        reader=CorpusReader(tmp_path / "knowledge"),
    )


def _autonomous(endpoints: list[str]) -> AutonomousTask:
    identifier, fingerprint = stable_task_id(TaskOrigin.WEAK_CLAIM, {"source": "teste"})
    tarefa = AutonomousTask(
        id=identifier,
        origin=TaskOrigin.WEAK_CLAIM,
        objective="Reavalie um claim delimitado.",
        priority=80,
        domain="Teste",
        kind=TaskKind.CORPUS_REVIEW,
        required_roles=list(PANEL_ROLES),
        budget=TaskBudget(),
        source_fingerprint=fingerprint,
    )
    if not endpoints:
        return tarefa
    return AutonomousTask.model_validate(
        {
            **tarefa.model_dump(mode="json"),
            "attempts": [{"endpoints": endpoints, "outcome": "error"}],
        }
    )


async def test_diagnostico_com_todos_provedores_desabilitados_da_backpressure(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path)
    executor.call_gate = ProviderCallGate({"groq": 0, "nvidia": 0})
    diagnosis = _autonomous([]).model_copy(update={"kind": TaskKind.ENDPOINT_DIAGNOSIS})

    outcome = await executor(diagnosis)

    assert outcome.outcome == "backpressure"
    assert outcome.endpoints == ()
    assert executor.ledger.run_calls == 0


def test_endpoint_ja_tentado_e_evitado_enquanto_sobra_painel(tmp_path: Path) -> None:
    executor = _executor(tmp_path)
    disponivel = executor._without_attempted(_autonomous(["groq/alpha-4"]))  # noqa: SLF001
    assert "groq/alpha-4" not in {profile.key for profile in disponivel.profiles}
    assert len(disponivel.profiles) == len(ENDPOINTS) - 1


def test_preferencia_por_endpoint_novo_cede_antes_de_inviabilizar_o_painel(
    tmp_path: Path,
) -> None:
    """Com acervo pequeno, excluir todo tentado condena a tarefa a nunca ser avaliada."""
    executor = _executor(tmp_path)
    gastos = ["groq/alpha-4", "groq/beta-3"]

    disponivel = executor._without_attempted(_autonomous(gastos))  # noqa: SLF001

    assert len(disponivel.profiles) == len(ENDPOINTS)
    assert {"groq/alpha-4", "groq/beta-3"} <= {p.key for p in disponivel.profiles}


def _inventory_parcialmente_sondado(usaveis: int) -> Inventory:
    """Espelha o acervo real: catálogo grande, punhado de endpoints comprovados."""
    registry = EndpointRegistry()
    modelos: list[ModelInfo] = []
    for indice in range(12):
        endpoint = f"modelo-{indice}"
        modelos.append(
            ModelInfo(
                provider="groq",
                endpoint_id=endpoint,
                family=f"familia-{indice}",
                available=True,
                context_window=128_000,
            )
        )
        if indice < usaveis:
            registry.record_probe(ProbeResult("groq", endpoint, "ok", "ok", 1))
    snapshot = DiscoverySnapshot(path=Path("models-groq.json"), models=modelos)
    return build_inventory({"groq": snapshot}, registry)


def test_piso_do_painel_se_mede_no_que_e_chamavel_nao_no_catalogo(
    tmp_path: Path,
) -> None:
    """Sobrar catálogo não sondado não ajuda painel nenhum: ele só usa o comprovado."""
    executor = _executor(tmp_path)
    executor.inventory = _inventory_parcialmente_sondado(usaveis=5)
    gastos = ["groq/modelo-0", "groq/modelo-1"]

    disponivel = executor._without_attempted(_autonomous(gastos))  # noqa: SLF001

    usaveis = {p.key for p in disponivel.select(usable=True)}
    assert usaveis >= set(gastos), "abaixo do piso, a preferência tem de ceder"
    assert len(usaveis) == 5


async def test_escassez_de_painel_e_adiamento_e_nao_veredito(tmp_path: Path) -> None:
    """Catorze tarefas foram aposentadas sem gastar chamada por esta classificação."""
    orchestrator, calls, store = build_orchestrator(
        tmp_path,
        votes={"verificador-factual": "approve"},
        entries=(("groq", "unico-1", "alpha"),),
    )

    with pytest.raises(PanelUnavailableError):
        await orchestrator.run(quorum_task())

    assert calls == []
    assert store.list_panels() == []


class _AccountDeadAdapter:
    def __init__(self, provider: str, calls: list[tuple[str, str]]) -> None:
        self.provider = provider
        self.calls = calls

    async def generate(
        self,
        endpoint_id: str,
        prompt: str,
        *,
        max_output_tokens: int = 256,
    ) -> GenerationResult:
        self.calls.append((self.provider, endpoint_id))
        raise ProviderAccountExhausted("Your prepayment credits are depleted")


class _RateLimitedAdapter:
    def __init__(self, provider: str, calls: list[tuple[str, str]]) -> None:
        self.provider = provider
        self.calls = calls

    async def generate(
        self,
        endpoint_id: str,
        prompt: str,
        *,
        max_output_tokens: int = 256,
    ) -> GenerationResult:
        del prompt, max_output_tokens
        self.calls.append((self.provider, endpoint_id))
        raise ProviderRateLimited("429 RESOURCE_EXHAUSTED")


async def test_proponente_com_429_troca_de_provedor(tmp_path: Path) -> None:
    orchestrator, calls, store = build_orchestrator(
        tmp_path,
        votes={"verificador-factual": "approve"},
        entries=ENDPOINTS + (("nous", "zeta-1", "zeta"), ("nous", "eta-1", "eta")),
    )
    limited: list[tuple[str, str]] = []
    orchestrator.adapters["groq"] = cast(ProviderAdapter, _RateLimitedAdapter("groq", limited))

    panel = await orchestrator.run(quorum_task())

    assert limited
    assert panel.proposal.proposer.provider != "groq"
    assert panel.decision is not None
    assert store.list_panels()


async def test_proponente_sem_credito_adia_e_suspende_o_provedor(tmp_path: Path) -> None:
    orchestrator, _calls, store = build_orchestrator(
        tmp_path,
        votes={"verificador-factual": "approve"},
    )
    dead: list[tuple[str, str]] = []
    orchestrator.adapters = {
        name: cast(ProviderAdapter, _AccountDeadAdapter(name, dead))
        for name in orchestrator.adapters
    }

    with pytest.raises(PanelUnavailableError, match="indisponível"):
        await orchestrator.run(quorum_task())

    assert dead
    assert orchestrator.call_gate.suspended(dead[0][0])
    assert store.list_panels() == []


def test_meta_sem_nota_nao_e_elegivel(tmp_path: Path) -> None:
    executor = _executor(tmp_path)
    sem_nota = _autonomous([]).model_copy(update={"kind": TaskKind.DIVERGENCE_REVIEW})
    com_nota = _autonomous([]).model_copy(
        update={
            "kind": TaskKind.DIVERGENCE_REVIEW,
            "corpus_entity": "Dados/Nota.md",
        }
    )
    assert executor.can_start(sem_nota) is False
    assert executor.can_start(com_nota) is True


def test_inventario_habilitado_omite_provedor_suspenso(tmp_path: Path) -> None:
    executor = _executor(tmp_path)
    executor.call_gate.suspend("groq")

    remaining = {
        profile.provider
        for profile in executor._enabled_inventory(executor.inventory).profiles  # noqa: SLF001
    }

    assert "groq" not in remaining
    assert "nvidia" in remaining
