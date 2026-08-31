"""A' — tabela de decisão do orçamento adaptativo, em isolamento."""

from __future__ import annotations

import json
from pathlib import Path

from vault.promotion.policy import (
    BudgetPolicy,
    DecisionLedger,
    Observables,
    PolicyDecision,
    observables_for,
)
from vault.work.quotas import RunBudget


def _obs(
    *,
    remaining: int,
    providers: int = 2,
    endpoints: int = 6,
    familias: int = 2,
    esperado: float = 4.0,
    falhas: int = 0,
    amostra: int = 0,
    votos_validos: int = 0,
    exigidos: int = 3,
) -> Observables:
    return observables_for(
        remaining_calls=remaining,
        eligible_providers=providers,
        eligible_endpoints=endpoints,
        eligible_families=familias,
        expected_calls=esperado,
        schema_failures=falhas,
        total_attempts=amostra,
        valid_votes=votos_validos,
        required_votes=exigidos,
    )


def test_diversidade_impossivel_defere(tmp_path: Path) -> None:
    politica = BudgetPolicy(tmp_path / "policy.json")
    decisao = politica.decide(_obs(remaining=20, providers=1, endpoints=4))
    assert decisao is PolicyDecision.DEFER


def test_familia_unica_no_acervo_nao_defere_com_provedores(tmp_path: Path) -> None:
    """Família não é silo: três provedores vivos seguem, mesmo numa família só."""
    politica = BudgetPolicy(tmp_path / "policy.json")
    decisao = politica.decide(
        _obs(remaining=20, providers=3, endpoints=8, familias=1)
    )
    assert decisao is None


def test_falha_de_schema_persistente_recomenda_switch(tmp_path: Path) -> None:
    politica = BudgetPolicy(tmp_path / "policy.json")
    obs = _obs(remaining=20, falhas=6, amostra=8)
    assert politica.decide(obs) is PolicyDecision.SWITCH
    assert politica.decide(_obs(remaining=20, falhas=3, amostra=8)) is None


def test_orcamento_curto_com_fechamento_viavel_expande(tmp_path: Path) -> None:
    politica = BudgetPolicy(tmp_path / "policy.json")
    obs = _obs(remaining=3, esperado=4.0)
    assert politica.decide(obs) is PolicyDecision.EXPAND_BUDGET


def test_orcamento_suficiente_nao_expande(tmp_path: Path) -> None:
    politica = BudgetPolicy(tmp_path / "policy.json")
    assert politica.decide(_obs(remaining=8)) is None


def test_votos_suficientes_para_e_stop(tmp_path: Path) -> None:
    politica = BudgetPolicy(tmp_path / "policy.json")
    obs = _obs(remaining=8, votos_validos=3, exigidos=3)
    assert politica.decide(obs) is PolicyDecision.STOP


def test_precedencia_defere_acima_de_tudo(tmp_path: Path) -> None:
    politica = BudgetPolicy(tmp_path / "policy.json")
    obs = _obs(remaining=1, providers=1, endpoints=3, falhas=6, amostra=8)
    assert politica.decide(obs) is PolicyDecision.DEFER


def test_orcamento_efetivo_expande_mas_nunca_ultrapassa_o_teto(tmp_path: Path) -> None:
    politica = BudgetPolicy(tmp_path / "policy.json")
    obs = _obs(remaining=3, esperado=4.0)
    efetivo = politica.effective_budget(obs, RunBudget(max_calls=8))
    assert efetivo.max_calls == 9
    limite = politica.effective_budget(_obs(remaining=50), RunBudget(max_calls=8))
    assert limite.max_calls == 8
    inviavel = politica.effective_budget(
        _obs(remaining=1, providers=1, endpoints=2), RunBudget(max_calls=8)
    )
    assert inviavel.max_calls == 8


def test_teto_do_arquivo_e_respeitado_e_24_e_o_absoluto(tmp_path: Path) -> None:
    (tmp_path / "policy.json").write_text(
        json.dumps({"budget": {"hard_ceiling_calls": 999}}), encoding="utf-8"
    )
    politica = BudgetPolicy(tmp_path / "policy.json")
    assert politica.rules.hard_ceiling_calls == 24
    # Expansão nunca encolhe: com estendido abaixo do teto do processo, o teto vence.
    assert politica.effective_budget(
        _obs(remaining=1, esperado=4.0), RunBudget(max_calls=8)
    ).max_calls == 8
    # E o teto duro de 24 manda, mesmo com custo esperado alto: estendido é
    # remaining + necessário, mas nunca passa do ceiling.
    assert politica.effective_budget(
        _obs(remaining=10, esperado=20.0), RunBudget(max_calls=8)
    ).max_calls == 24


def test_sem_arquivo_ou_sem_bloco_politica_fica_inativa(tmp_path: Path) -> None:
    assert not BudgetPolicy(tmp_path / "policy.json").active
    (tmp_path / "policy.json").write_text(
        json.dumps({"schema_version": 1, "activated_at": "2026-01-01T00:00:00+00:00"}),
        encoding="utf-8",
    )
    assert not BudgetPolicy(tmp_path / "policy.json").active
    (tmp_path / "policy.json").write_text(
        json.dumps(
            {"schema_version": 2, "budget": {"hard_ceiling_calls": 20}}
        ),
        encoding="utf-8",
    )
    politica = BudgetPolicy(tmp_path / "policy.json")
    assert politica.active
    assert politica.rules.hard_ceiling_calls == 20


def test_ledger_registra_decisoes_sem_reescrever(tmp_path: Path) -> None:
    ledger = DecisionLedger(tmp_path / "ledger.jsonl")
    obs = _obs(remaining=3)
    ledger.record(
        task_id="t1",
        policy_version="quorum-v2",
        decision=PolicyDecision.EXPAND_BUDGET,
        reason="orçamento curto",
        observáveis=obs,
        effective_budget=RunBudget(max_calls=9),
    )
    ledger.record(
        task_id="t2",
        policy_version="quorum-v2",
        decision=None,
        reason="sem decisão",
        observáveis=_obs(remaining=20),
    )
    linhas = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 2
    primeira = json.loads(linhas[0])
    assert primeira["task_id"] == "t1"
    assert primeira["decision"] == "expand_budget"
    assert primeira["effective_budget"] == 9
    assert primeira["observables"]["eligible_diversity"]["providers"] == 2
