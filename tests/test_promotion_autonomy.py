"""O caminho nativo quórum → promoção: política, diário, idempotência e wiring."""

from __future__ import annotations

import datetime
import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

from providers.base import ModelInfo, ProbeResult, ProviderAdapter
from providers.catalog import DiscoverySnapshot
from providers.cognitive import CognitiveKind
from providers.inventory import Inventory, build_inventory
from providers.registry import EndpointRegistry
from vault.autonomy import OrchestratedTaskExecutor
from vault.autonomy.models import AutonomousTask, TaskBudget, TaskKind, TaskOrigin, TaskState
from vault.corpus import CorpusReader
from vault.promotion import (
    PATCH_DIGEST_KEY,
    POLICY_VERSION,
    BudgetPolicy,
    CorpusPatch,
    DecisionLedger,
    PatchOperation,
    PromotionJournal,
    PromotionPolicy,
    PromotionReport,
    ProposalPromoter,
    QuorumPromotion,
)
from vault.quorum import QuorumStore
from vault.quorum.models import (
    DecisionStatus,
    Panel,
    PanelMember,
    PanelTask,
    ParseResult,
    Proposal,
    QuorumDecision,
    RecommendedAction,
    Vote,
    VoteDecision,
)
from vault.work.call_gate import ProviderCallGate
from vault.work.quotas import QuotaLedger, RunBudget
from vault.work.store import WorkStore

NOTA = """---
id: nota-de-teste
title: Nota de teste
domain: teste
kind: fundamento
epistemic_status: supported
updated: 2026-08-04
verified_at: 2026-08-04
---

# Nota de teste

Conteúdo mínimo para o auditor estrutural.
"""

NOTA_ALTERADA = NOTA.replace("updated: 2026-08-04", "updated: 2026-08-05")

ENDPOINTS = (
    ("nvidia", "alpha-1", "alpha"),
    ("nvidia", "beta-2", "beta"),
    ("groq", "gamma-2", "gamma"),
    ("groq", "delta-1", "delta"),
    ("google", "epsilon-1", "epsilon"),
)


def membro(provider: str, endpoint: str, family: str, papel: str = "critico") -> PanelMember:
    return PanelMember(
        provider=provider,
        endpoint_id=endpoint,
        family=family,
        role_name=papel,
    )


def voto(reviewer: PanelMember) -> ParseResult:
    return ParseResult(
        reviewer=reviewer,
        schema_valid=True,
        structured_vote=Vote(
            decision=VoteDecision.APPROVE,
            confidence=0.8,
            recommended_action=RecommendedAction.PROMOTE,
        ),
    )


def patch_simples(base: str = "0" * 40, caminho: str = "teste/Nota de teste.md") -> CorpusPatch:
    return CorpusPatch(
        proposal_id="prop-1",
        base_commit=base,
        operations=[PatchOperation(action="create", path=caminho, content=NOTA)],
    )


def painel(
    patch: CorpusPatch,
    *,
    decidido_em: str | None = None,
    digest: str | None = None,
) -> Panel:
    avaliadores = [
        voto(membro("nvidia", "z-ai/glm-5.2", "glm")),
        voto(membro("groq", "llama-3.3-70b-versatile", "llama")),
        voto(membro("nvidia", "deepseek-ai/deepseek-v4-pro", "deepseek")),
    ]
    p = Panel(
        id="painel1",
        task=PanelTask(
            kind="proposta",
            prompt="proponha a nota de teste",
            context={PATCH_DIGEST_KEY: digest if digest is not None else patch.digest()},
        ),
        proposal=Proposal(
            id="prop-1",
            proposer=membro("groq", "qwen/qwen3.6-27b", "qwen3", "proponente"),
            final_response="proposta de teste",
        ),
        members=[v.reviewer for v in avaliadores],
        votes=avaliadores,
    )
    return p.model_copy(
        update={
            "decision": QuorumDecision(
                id="dec-1",
                panel_id=p.id,
                outcome=RecommendedAction.PROMOTE,
                status=DecisionStatus.DECIDED,
                reason="maioria aprova",
                valid_vote_count=3,
                provider_count=2,
                family_count=2,
                tally={
                    VoteDecision.APPROVE: 3,
                    VoteDecision.REJECT: 0,
                    VoteDecision.REVISE: 0,
                    VoteDecision.ABSTAIN: 0,
                },
                votes=[],
                decided_at=decidido_em
                or (
                    datetime.datetime.now(datetime.UTC)
                    + datetime.timedelta(minutes=10)
                ).isoformat(),
            )
        }
    )


def repo_de_teste(raiz: Path) -> Path:
    """Um repositório mínimo com a mesma forma do Vault: corpus e auditor."""
    subprocess.run(["git", "init", "-q", "-b", "main", str(raiz)], check=True)
    subprocess.run(["git", "-C", str(raiz), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(raiz), "config", "user.name", "teste"], check=True)
    (raiz / "knowledge").mkdir()
    (raiz / "knowledge" / "Semente.md").write_text(NOTA, encoding="utf-8")
    (raiz / "tools").mkdir()
    (raiz / "tools" / "audit.py").write_text(
        "import sys\nraise SystemExit(0)\n", encoding="utf-8"
    )
    subprocess.run(["git", "-C", str(raiz), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(raiz), "commit", "-qm", "base"], check=True)
    return raiz


def _promocao_ativa(repo: Path, raiz: Path) -> QuorumPromotion:
    politica = PromotionPolicy(raiz / "policy.json")
    politica.activate()
    return QuorumPromotion(
        journal=PromotionJournal(raiz / "promotions.jsonl"),
        policy=politica,
        promoter=ProposalPromoter(repo_root=repo),
    )


def _head(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _contagem_de_commits(repo: Path) -> int:
    saida = subprocess.run(
        ["git", "-C", str(repo), "log", "--all", "--format=%H", "--grep=Promove proposta"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return len([linha for linha in saida.splitlines() if linha])


# --- ativação e coorte -------------------------------------------------------


def test_ativacao_e_idempotente_e_grava_o_momento(tmp_path: Path) -> None:
    politica = PromotionPolicy(tmp_path / "policy.json")
    primeira = politica.activate()
    segunda = politica.activate()
    assert primeira == segunda
    dados = json.loads((tmp_path / "policy.json").read_text(encoding="utf-8"))
    assert dados["policy_version"] == POLICY_VERSION


def test_decisao_anterior_a_ativacao_e_coorte_e_fica_de_fora(tmp_path: Path) -> None:
    politica = PromotionPolicy(tmp_path / "policy.json")
    ativada = politica.activate()
    patch = patch_simples()
    antigo = painel(patch, decidido_em="2020-01-01T00:00:00+00:00")
    veredito = politica.authorize(antigo, patch)
    assert not veredito.authorized
    assert "coorte pré-ativação" in veredito.reason
    novo = painel(patch, decidido_em=ativada)
    assert politica.authorize(novo, patch).authorized


def test_digest_divergente_nao_autoriza(tmp_path: Path) -> None:
    politica = PromotionPolicy(tmp_path / "policy.json")
    politica.activate()
    patch = patch_simples()
    veredito = politica.authorize(painel(patch, digest="0" * 64), patch)
    assert not veredito.authorized
    assert "digest" in veredito.reason


def test_sem_ativacao_nao_autoriza(tmp_path: Path) -> None:
    politica = PromotionPolicy(tmp_path / "policy.json")
    veredito = politica.authorize(painel(patch_simples()), patch_simples())
    assert not veredito.authorized
    assert "ativada" in veredito.reason


# --- ciclo completo e idempotência -------------------------------------------


def test_ciclo_quorum_promocao_commita_uma_vez(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = repo_de_teste(tmp_path / "repo")
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    promocao = _promocao_ativa(repo, tmp_path / "estado")
    patch = patch_simples(base=_head(repo), caminho="Nota nova.md")

    relatorio = promocao.promote(painel(patch), patch)

    assert relatorio.state == "promoted"
    assert (repo / "knowledge" / "Nota nova.md").is_file()
    assert _contagem_de_commits(repo) == 1
    chave = PromotionJournal.key(
        patch.proposal_id,
        patch.digest(),
        PromotionJournal.targets_fingerprint(patch.targets),
    )
    estados = [entrada["state"] for entrada in promocao.journal.entries(chave)]
    assert estados == ["eligible", "promotion_pending", "applying", "promoted"]


def test_replay_do_mesmo_fechamento_nao_commita_de_novo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = repo_de_teste(tmp_path / "repo")
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    promocao = _promocao_ativa(repo, tmp_path / "estado")
    patch = patch_simples(base=_head(repo), caminho="Nota nova.md")
    fechamento = painel(patch)

    primeiro = promocao.promote(fechamento, patch)
    segundo = promocao.promote(fechamento, patch)

    assert primeiro.state == "promoted"
    assert segundo.state == "already_promoted"
    assert _contagem_de_commits(repo) == 1


def test_crash_antes_do_commit_repromove_e_commita_uma_vez(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = repo_de_teste(tmp_path / "repo")
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    promocao = _promocao_ativa(repo, tmp_path / "estado")
    patch = patch_simples(base=_head(repo), caminho="Nota nova.md")
    chave = PromotionJournal.key(
        patch.proposal_id,
        patch.digest(),
        PromotionJournal.targets_fingerprint(patch.targets),
    )
    promocao.journal.append(
        {"key": chave, "state": "applying", "at": "2026-08-17T00:00:00+00:00"}
    )

    relatorio = promocao.promote(painel(patch), patch)

    assert relatorio.state == "promoted"
    assert _contagem_de_commits(repo) == 1
    assert (repo / "knowledge" / "Nota nova.md").is_file()


def test_crash_depois_do_commit_nao_repromove(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = repo_de_teste(tmp_path / "repo")
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    promocao = _promocao_ativa(repo, tmp_path / "estado")
    patch = patch_simples(base=_head(repo), caminho="Nota nova.md")
    fechamento = painel(patch)

    promocao.promote(fechamento, patch)
    chave = PromotionJournal.key(
        patch.proposal_id,
        patch.digest(),
        PromotionJournal.targets_fingerprint(patch.targets),
    )
    promocao.journal.append(
        {"key": chave, "state": "applying", "at": "2026-08-17T00:00:00+00:00"}
    )

    relatorio = promocao.promote(fechamento, patch)

    assert relatorio.state == "already_promoted"
    assert relatorio.commit is not None
    assert _contagem_de_commits(repo) == 1


def test_failed_nao_e_terminal_e_reaplica(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = repo_de_teste(tmp_path / "repo")
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    promocao = _promocao_ativa(repo, tmp_path / "estado")
    patch = patch_simples(base=_head(repo), caminho="Nota nova.md")
    chave = PromotionJournal.key(
        patch.proposal_id,
        patch.digest(),
        PromotionJournal.targets_fingerprint(patch.targets),
    )
    promocao.journal.append(
        {
            "key": chave,
            "state": "failed",
            "at": "2026-08-24T00:00:00+00:00",
            "detail": "árvore de trabalho suja",
        }
    )

    relatorio = promocao.promote(painel(patch), patch)

    assert relatorio.state == "promoted"
    assert _contagem_de_commits(repo) == 1


def test_alvo_mudado_desde_a_base_vira_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = repo_de_teste(tmp_path / "repo")
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    promocao = _promocao_ativa(repo, tmp_path / "estado")
    base = _head(repo)
    patch = patch_simples(base=base, caminho="Nota nova.md")
    (repo / "knowledge" / "Nota nova.md").write_text(NOTA, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "trabalho alheio"], check=True)

    relatorio = promocao.promote(painel(patch), patch)

    assert relatorio.state == "stale"
    assert _contagem_de_commits(repo) == 0


def test_arvore_suja_nao_rejeita_promocao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = repo_de_teste(tmp_path / "repo")
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    promocao = _promocao_ativa(repo, tmp_path / "estado")
    patch = patch_simples(base=_head(repo), caminho="Nota nova.md")
    (repo / "knowledge" / "Semente.md").write_text(NOTA + "\n", encoding="utf-8")

    relatorio = promocao.promote(painel(patch), patch)

    assert relatorio.state == "promoted"
    assert (repo / "knowledge" / "Nota nova.md").is_file()
    assert _contagem_de_commits(repo) == 1


def test_coorte_nao_entra_no_diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = repo_de_teste(tmp_path / "repo")
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    promocao = _promocao_ativa(repo, tmp_path / "estado")
    patch = patch_simples(base=_head(repo), caminho="Nota nova.md")
    antigo = painel(patch, decidido_em="2020-01-01T00:00:00+00:00")

    relatorio = promocao.promote(antigo, patch)

    assert relatorio.state == "skipped"
    assert "coorte" in relatorio.detail
    assert _contagem_de_commits(repo) == 0
    chave = PromotionJournal.key(
        patch.proposal_id,
        patch.digest(),
        PromotionJournal.targets_fingerprint(patch.targets),
    )
    assert promocao.journal.entries(chave) == []


# --- wiring: o executor do worker conduz o ciclo inteiro ----------------------


def inventory_for(entries=ENDPOINTS) -> Inventory:
    snapshots: dict[str, DiscoverySnapshot] = {}
    registry = EndpointRegistry()
    por_provedor: dict[str, list[ModelInfo]] = {}
    for provider, endpoint_id, family in entries:
        por_provedor.setdefault(provider, []).append(
            ModelInfo(
                provider=provider,
                endpoint_id=endpoint_id,
                family=family,
                available=True,
                context_window=128_000,
            )
        )
        registry.record_probe(ProbeResult(provider, endpoint_id, "ok", "ok", 1))
    for provider, modelos in por_provedor.items():
        snapshots[provider] = DiscoverySnapshot(
            path=Path(f"models-{provider}.json"),
            models=modelos,
        )
    return build_inventory(snapshots, registry)


def _voto_payload(decisions: dict[str, str]) -> dict[str, str]:
    acoes = {
        "approve": "promote",
        "reject": "reject",
        "revise": "revise",
        "abstain": "escalate",
    }
    return {
        papel: json.dumps(
            {
                "decision": decisao,
                "confidence": 0.8,
                "blocking_issues": [],
                "non_blocking_issues": [],
                "evidence": [],
                "recommended_action": acoes[decisao],
            }
        )
        for papel, decisao in decisions.items()
    }


class _FakeAdapter:
    """O mesmo fake do orquestrador, com `replace` no lugar de `create`."""

    def __init__(
        self,
        provider: str,
        votes: dict[str, str],
        *,
        patch_path: str = "Semente.md",
    ) -> None:
        self.provider = provider
        self.votes = votes
        self.patch_path = patch_path

    async def generate(self, endpoint_id: str, prompt: str, **_: Any) -> Any:
        return _GenerationResult(
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
    ) -> Any:
        """O quórum consome stream; o fake precisa percorrer o mesmo caminho."""
        texto = self._texto(prompt)
        if texto:
            yield _CognitiveEvent(
                provider=self.provider,
                endpoint_id=endpoint_id,
                kind=CognitiveKind.OUTPUT_DELTA,
                text=texto,
                raw_field="delta.content",
                sequence=1,
            )
        yield _CognitiveEvent(
            provider=self.provider,
            endpoint_id=endpoint_id,
            kind=CognitiveKind.FINAL,
            raw_field="stream.end",
            sequence=2,
            detail={"usage": {"total_tokens": 10}},
        )

    def _texto(self, prompt: str) -> str:
        if "proposal_id exato:" in prompt and "base_commit exato:" in prompt:
            import re

            proposal_id = re.search(r"proposal_id exato: ([0-9a-f]+)", prompt)
            base_commit = re.search(r"base_commit exato: ([0-9a-f]+)", prompt)
            assert proposal_id is not None and base_commit is not None
            return json.dumps(
                {
                    "proposal_id": proposal_id.group(1),
                    "base_commit": base_commit.group(1),
                    "operations": [
                        {
                            "action": "replace",
                            "path": self.patch_path,
                            "content": NOTA_ALTERADA,
                        }
                    ],
                }
            )
        papel = _papel(prompt)
        return self.votes[papel]


def _papel(prompt: str) -> str:
    marcadores = {
        "Você verifica fatos": "verificador-factual",
        "Você avalia força epistêmica": "critico-epistemologico",
        "Você verifica forma": "revisor-estrutural",
    }
    for marcador, papel in marcadores.items():
        if marcador in prompt:
            return papel
    raise AssertionError(f"prompt sem papel reconhecível: {prompt[:120]}")


class _GenerationResult:
    def __init__(
        self, *, provider: str, endpoint_id: str, text: str, usage: dict[str, int]
    ) -> None:
        self.provider = provider
        self.endpoint_id = endpoint_id
        self.text = text
        self.usage = usage


class _CognitiveEvent:
    def __init__(
        self,
        *,
        provider: str,
        endpoint_id: str,
        kind: str,
        raw_field: str,
        sequence: int,
        detail: dict[str, Any] | None = None,
        text: str = "",
    ) -> None:
        self.provider = provider
        self.endpoint_id = endpoint_id
        self.kind = kind
        self.text = text
        self.raw_field = raw_field
        self.sequence = sequence
        self.detail = detail or {}


async def test_executor_promove_o_ciclo_inteiro_ate_o_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tarefa → quórum → proposta → Promoter → auditoria → commit, numa sessão."""
    repo = repo_de_teste(tmp_path / "repo")
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    politica = PromotionPolicy(tmp_path / "estado" / "policy.json")
    politica.activate()
    promocao = QuorumPromotion(
        journal=PromotionJournal(tmp_path / "estado" / "promotions.jsonl"),
        policy=politica,
        promoter=ProposalPromoter(repo_root=repo),
    )
    votos = _voto_payload(
        {
            "verificador-factual": "approve",
            "critico-epistemologico": "approve",
            "revisor-estrutural": "approve",
        }
    )
    executor = OrchestratedTaskExecutor(
        inventory=inventory_for(),
        adapters={
            provider: cast(ProviderAdapter, _FakeAdapter(provider, votos))
            for provider in {entrada[0] for entrada in ENDPOINTS}
        },
        ledger=QuotaLedger(),
        process_budget=RunBudget(max_calls=8),
        quorum_store=QuorumStore(tmp_path / "estado" / "quorum"),
        work_store=WorkStore(tmp_path / "estado" / "modelos"),
        reader=CorpusReader(repo / "knowledge"),
        resolve_base_commit=lambda: _head(repo),
        redact=lambda texto: texto,
        emit=lambda _kind, _payload: None,
        call_gate=ProviderCallGate(),
        promotion=promocao,
    )
    tarefa = AutonomousTask(
        id="aut-promocao-01",
        origin=TaskOrigin.WEAK_CLAIM,
        objective="Reavalie a semente e proponha a alteração pontual pedida.",
        priority=50,
        domain="Física",
        kind=TaskKind.CORPUS_REVIEW,
        required_roles=["verificador-factual", "critico-epistemologico", "revisor-estrutural"],
        budget=TaskBudget(max_calls=8, max_output_tokens=2048),
        state=TaskState.QUEUED,
        corpus_entity="Semente.md",
        source_fingerprint="a" * 16,
    )

    desfecho = await executor(tarefa)

    assert desfecho.outcome == "promote"
    assert "promovido" in desfecho.detail
    assert desfecho.panel_id is not None
    assert _contagem_de_commits(repo) == 1
    # O diário registrou o fechamento como promovido, com o commit na linha.
    linhas = [
        json.loads(linha)
        for linha in (tmp_path / "estado" / "promotions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if linha.strip()
    ]
    assert linhas[-1]["state"] == "promoted"
    assert len(linhas[-1]["commit"]) == 40
    assert linhas[-1]["panel_id"] == desfecho.panel_id
    assert linhas[-1]["source"] == "quorum"


def _linhas_do_diario(tmp_path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(linha)
        for linha in (tmp_path / "estado" / "promotions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if linha.strip()
    ]


def _monta_executor_de_promocao(tmp_path: Path, repo: Path) -> OrchestratedTaskExecutor:
    """Executor com quórum de teste e promoção ativa, para os ensaios de crash."""
    politica = PromotionPolicy(tmp_path / "estado" / "policy.json")
    politica.activate()
    promocao = QuorumPromotion(
        journal=PromotionJournal(tmp_path / "estado" / "promotions.jsonl"),
        policy=politica,
        promoter=ProposalPromoter(repo_root=repo),
    )
    votos = _voto_payload(
        {
            "verificador-factual": "approve",
            "critico-epistemologico": "approve",
            "revisor-estrutural": "approve",
        }
    )
    return OrchestratedTaskExecutor(
        inventory=inventory_for(),
        adapters={
            provider: cast(ProviderAdapter, _FakeAdapter(provider, votos))
            for provider in {entrada[0] for entrada in ENDPOINTS}
        },
        ledger=QuotaLedger(),
        process_budget=RunBudget(max_calls=8),
        quorum_store=QuorumStore(tmp_path / "estado" / "quorum"),
        work_store=WorkStore(tmp_path / "estado" / "modelos"),
        reader=CorpusReader(repo / "knowledge"),
        resolve_base_commit=lambda: _head(repo),
        redact=lambda texto: texto,
        emit=lambda _kind, _payload: None,
        call_gate=ProviderCallGate(),
        promotion=promocao,
    )


def _tarefa_de_revisao(tarefa_id: str = "aut-promocao-01") -> AutonomousTask:
    return AutonomousTask(
        id=tarefa_id,
        origin=TaskOrigin.WEAK_CLAIM,
        objective="Reavalie a semente e proponha a alteração pontual pedida.",
        priority=50,
        domain="Física",
        kind=TaskKind.CORPUS_REVIEW,
        required_roles=["verificador-factual", "critico-epistemologico", "revisor-estrutural"],
        budget=TaskBudget(max_calls=8, max_output_tokens=2048),
        state=TaskState.QUEUED,
        corpus_entity="Semente.md",
        source_fingerprint="a" * 16,
    )


async def test_crash_entre_autorizacao_e_commit_nao_duplica_nem_perde(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Quinto invariante: o processo morre depois da autorização e antes do commit.

    A re-execução da mesma tarefa não pode reabrir o quórum — painel novo geraria
    proposta nova, chave de diário nova, e a recuperação pelo proposal_id ficaria
    cega. Ela reusa o painel fechado e o diário decide: sem commit no histórico, a
    proposta é reaplicada uma única vez.
    """
    repo = repo_de_teste(tmp_path / "repo")
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    executor = _monta_executor_de_promocao(tmp_path, repo)

    def morre_depois_de_autorizar(self, *_args: Any, **_kw: Any) -> Any:
        raise SystemExit("morte súbita entre autorização e commit")

    original = ProposalPromoter._validar_e_commitar
    monkeypatch.setattr(ProposalPromoter, "_validar_e_commitar", morre_depois_de_autorizar)
    with pytest.raises(SystemExit):
        await executor(_tarefa_de_revisao())
    # A máquina ficou presa em applying, sem commit — o estado que o restart encontra.
    assert _contagem_de_commits(repo) == 0
    linhas = _linhas_do_diario(tmp_path)
    assert linhas[-1]["state"] == "applying"

    # O restart (mesma tarefa de volta à fila) reusa o painel e recupera.
    monkeypatch.setattr(ProposalPromoter, "_validar_e_commitar", original)
    desfecho = await executor(_tarefa_de_revisao())

    assert desfecho.outcome == "promote"
    assert "promovido" in desfecho.detail
    assert _contagem_de_commits(repo) == 1
    linhas = _linhas_do_diario(tmp_path)
    assert linhas[-1]["state"] == "promoted"
    assert len(linhas[-1]["commit"]) == 40


async def test_crash_depois_do_commit_nao_commita_de_novo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O processo morre depois da promoção e antes de registrar o desfecho da tarefa.

    A re-execução reusa o painel; o diário já registra `promoted` (terminal) e
    responde already_promoted — o corpus não recebe um segundo commit. O caminho
    complementar — diário preso em `applying` com commit já existente no histórico —
    é a recuperação por git-grep, presa no nível unitário em
    test_crash_depois_do_commit_nao_repromove.
    """
    repo = repo_de_teste(tmp_path / "repo")
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    executor = _monta_executor_de_promocao(tmp_path, repo)
    promocao = executor.promotion
    assert promocao is not None
    promote_original = promocao.promote

    def morre_apos_promover(*args: Any, **kwargs: Any) -> Any:
        promote_original(*args, **kwargs)
        raise SystemExit("morte súbita após a promoção")

    monkeypatch.setattr(promocao, "promote", morre_apos_promover)
    with pytest.raises(SystemExit):
        await executor(_tarefa_de_revisao())
    # O commit existe e o diário registrou promoted; o desfecho da tarefa é que não.
    assert _contagem_de_commits(repo) == 1
    linhas = _linhas_do_diario(tmp_path)
    assert linhas[-1]["state"] == "promoted"

    monkeypatch.setattr(promocao, "promote", promote_original)
    desfecho = await executor(_tarefa_de_revisao())

    assert desfecho.outcome == "promote"
    assert "promoted" in desfecho.detail
    assert _contagem_de_commits(repo) == 1
    linhas = _linhas_do_diario(tmp_path)
    assert linhas[-1]["state"] == "promoted"


async def test_excecao_na_assimilacao_nao_devolve_promote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = repo_de_teste(tmp_path / "repo")
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    executor = _monta_executor_de_promocao(tmp_path, repo)
    promocao = executor.promotion
    assert promocao is not None

    def explode(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("boom na assimilação")

    monkeypatch.setattr(promocao, "promote", explode)
    desfecho = await executor(_tarefa_de_revisao())
    assert desfecho.outcome == "failed"
    assert "boom na assimilação" in desfecho.detail
    assert _contagem_de_commits(repo) == 0


async def test_recusa_da_assimilacao_nao_devolve_promote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = repo_de_teste(tmp_path / "repo")
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    executor = _monta_executor_de_promocao(tmp_path, repo)
    promocao = executor.promotion
    assert promocao is not None

    def recusa(*_args: Any, **_kwargs: Any) -> Any:
        return PromotionReport("rejected", "diff fora dos alvos declarados")

    monkeypatch.setattr(promocao, "promote", recusa)
    desfecho = await executor(_tarefa_de_revisao())
    assert desfecho.outcome == "rejected"
    assert "diff fora dos alvos" in desfecho.detail
    assert _contagem_de_commits(repo) == 0


# --- A' — orçamento adaptativo: política, observáveis e decisão -----------------


def _com_politica_orcamentaria(
    executor: OrchestratedTaskExecutor,
    tmp_path: Path,
) -> OrchestratedTaskExecutor:
    executor.budget_policy = BudgetPolicy(tmp_path / "estado" / "policy.json")
    executor.decision_ledger = DecisionLedger(
        tmp_path / "estado" / "policy-decisions.jsonl"
    )
    return executor


def _linhas_do_ledger(tmp_path: Path) -> list[dict[str, Any]]:
    caminho = tmp_path / "estado" / "policy-decisions.jsonl"
    return [
        json.loads(linha)
        for linha in caminho.read_text(encoding="utf-8").splitlines()
        if linha.strip()
    ]


async def test_politica_expande_orcamento_e_admite_fechamento_corto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A' — orçamento curto com fechamento viável vira expansão, não adiamento.

    Cinco chamadas já consumidas de um orçamento de oito: faltam três, o painel
    exige quatro. Sem política, a tarefa nem começa; com a expansão, o quórum
    fecha e promove, e o ledger registra a decisão com os observáveis.
    """
    repo = repo_de_teste(tmp_path / "repo")
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    executor = _com_politica_orcamentaria(_monta_executor_de_promocao(tmp_path, repo), tmp_path)
    for indice in range(5):
        executor.ledger.record_call(endpoint=f"consumido-{indice}", provider="nvidia")

    tarefa = _tarefa_de_revisao()
    assert executor.defer_reason(tarefa) is None
    assert executor.can_start(tarefa) is True

    desfecho = await executor(tarefa)

    assert desfecho.outcome == "promote"
    assert executor.ledger.run_calls == 9
    entradas = _linhas_do_ledger(tmp_path)
    expansoes = [e for e in entradas if e["decision"] == "expand_budget"]
    assert expansoes, "a política precisou expandir para admitir este fechamento"
    assert expansoes[0]["effective_budget"] == 9
    assert expansoes[0]["task_id"] == tarefa.id
    assert expansoes[0]["policy_version"] == "quorum-v2"


async def test_politica_defere_diversidade_impossivel_sem_gastar_chamada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A' — diversidade impossível defere antes da primeira chamada.

    Com um único provedor elegível, nenhum painel pode nascer; gastar o proponente
    seria desperdício. O DEFER é bloqueio estrutural (não backpressure): nada é
    gasto, o ledger registra, e a reabertura espera o próximo início do worker.
    """
    repo = repo_de_teste(tmp_path / "repo")
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    executor = _com_politica_orcamentaria(_monta_executor_de_promocao(tmp_path, repo), tmp_path)
    executor.inventory = inventory_for(
        (
            ("nvidia", "alpha-1", "alpha"),
            ("nvidia", "beta-2", "beta"),
            ("nvidia", "theta-1", "theta"),
            ("nvidia", "zeta-1", "zeta"),
        )
    )

    desfecho = await executor(_tarefa_de_revisao())

    assert desfecho.outcome == "blocked"
    assert "diversidade" in desfecho.detail
    assert executor.ledger.run_calls == 0
    entradas = _linhas_do_ledger(tmp_path)
    adiamentos = [e for e in entradas if e["decision"] == "defer"]
    assert adiamentos
    assert adiamentos[0]["observables"]["eligible_diversity"]["providers"] == 1


async def test_ativacao_promove_schema_1_a_2_preservando_o_momento(tmp_path: Path) -> None:
    """A ativação legada sobe de schema sem mover a referência de causalidade.

    O `activated_at` original não pode mudar: o diário de promoções ancora nele a
    coorte pré-ativação. O bloco `budget` entra com os defaults de código, e a
    política orçamentária passa a ler o arquivo como ativa.
    """
    caminho = tmp_path / "estado" / "policy.json"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    original = {
        "schema_version": 1,
        "policy_version": "quorum-v1",
        "activated_at": "2026-08-17T03:15:21+00:00",
    }
    caminho.write_text(json.dumps(original), encoding="utf-8")

    politica = PromotionPolicy(caminho)
    assert politica.activate() == original["activated_at"]

    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert dados["schema_version"] == 2
    assert dados["activated_at"] == original["activated_at"]
    assert dados["budget"]["hard_ceiling_calls"] == 24
    assert BudgetPolicy(caminho).active


def _repo_com_auditor(repo: Path, corpo: str) -> Path:
    (repo / "tools" / "audit.py").write_text(corpo, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "auditor"], check=True)
    return repo


def test_admit_patch_aceita_patch_promovivel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O gate pré-quórum deixa passar o que o Promoter conseguiria commitar."""
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    repo = repo_de_teste(tmp_path / "repo")
    promoter = ProposalPromoter(repo_root=repo)
    patch = CorpusPatch(
        proposal_id="prop-gate-1",
        base_commit=promoter.head(),
        operations=[
            PatchOperation(action="replace", path="Semente.md", content=NOTA_ALTERADA)
        ],
    )
    assert promoter.admit_patch(patch) is None


def test_admit_patch_recusa_diff_vazio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Diff vazio é recusa determinística: nada para os avaliadores julgarem."""
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    repo = repo_de_teste(tmp_path / "repo")
    promoter = ProposalPromoter(repo_root=repo)
    patch = CorpusPatch(
        proposal_id="prop-gate-2",
        base_commit=promoter.head(),
        operations=[
            PatchOperation(action="replace", path="Semente.md", content=NOTA)
        ],
    )
    recusa = promoter.admit_patch(patch)
    assert recusa is not None
    assert "diff fora dos alvos" in recusa


def test_admit_patch_recusa_auditoria_estrutural(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Patch que quebra a estrutura do corpus não chega ao quórum."""
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    repo = _repo_com_auditor(
        repo_de_teste(tmp_path / "repo"),
        (
            "import pathlib, sys\n"
            "raiz = pathlib.Path(sys.argv[1])\n"
            "corpus = (raiz / 'Semente.md').read_text(encoding='utf-8')\n"
            "sys.exit(1 if 'REPROVA-AUDITORIA' in corpus else 0)\n"
        ),
    )
    promoter = ProposalPromoter(repo_root=repo)
    patch = CorpusPatch(
        proposal_id="prop-gate-3",
        base_commit=promoter.head(),
        operations=[
            PatchOperation(
                action="replace",
                path="Semente.md",
                content=NOTA_ALTERADA + "\nREPROVA-AUDITORIA",
            )
        ],
    )
    recusa = promoter.admit_patch(patch)
    assert recusa is not None
    assert "auditoria estrutural reprovou" in recusa


def test_admit_patch_recusa_ata_de_painel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    repo = repo_de_teste(tmp_path / "repo")
    promoter = ProposalPromoter(repo_root=repo)
    patch = CorpusPatch(
        proposal_id="prop-ata",
        base_commit=promoter.head(),
        operations=[
            PatchOperation(
                action="replace",
                path="Semente.md",
                content=NOTA + "\n## Painel de divergência 01dda91c2800\n",
            )
        ],
    )
    recusa = promoter.admit_patch(patch)
    assert recusa is not None
    assert "ata de painel" in recusa


async def test_preflight_recusa_patch_antes_dos_avaliadores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Admission falhou → `rejected` com só o proponente gasto, zero avaliadores."""
    repo = repo_de_teste(tmp_path / "repo")
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    executor = _monta_executor_de_promocao(tmp_path, repo)
    monkeypatch.setattr(
        ProposalPromoter,
        "admit_patch",
        lambda self, patch: "recusa determinística de teste",
    )

    desfecho = await executor(_tarefa_de_revisao())

    assert desfecho.outcome == "rejected"
    assert "recusa determinística" in desfecho.detail
    assert executor.ledger.run_calls == 1
    paineis = list(executor.quorum_store.list_panels())
    assert paineis == []
