"""A fronteira entre proposta e corpus é a coisa que estes testes protegem."""

from __future__ import annotations

import json
import multiprocessing
import stat
from collections.abc import Sequence
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import Any

import pytest

from vault.proposals import Proposal, ProposalStore
from vault.proposals.store import PromotionRefused


@pytest.fixture
def store(tmp_path: Path) -> ProposalStore:
    return ProposalStore(tmp_path / "proposals")


def salvar(store: ProposalStore, payload: dict[str, object] | None = None) -> Proposal:
    return store.save_proposal(
        kind="claim-candidato",
        provider="groq",
        endpoint="algum-endpoint",
        prompt_summary="lacuna em estatística",
        payload=payload if payload is not None else {"texto": "proposta qualquer"},
    )


def _salvar_em_processo(
    directory: str,
    barrier: Any,
    results: Any,
) -> None:
    barrier.wait()
    results.put(salvar(ProposalStore(Path(directory))).id)


def _promover_em_processo(
    directory: str,
    proposal_id: str,
    barrier: Any,
    results: Any,
) -> None:
    barrier.wait()
    local_store = ProposalStore(Path(directory))
    try:
        local_store.promote_after_validation(
            proposal_id,
            validated_by="processo concorrente",
            verdict_note="validação simultânea",
        )
    except PromotionRefused:
        results.put("refused")
    else:
        results.put("approved")


def _join_processes(processes: Sequence[BaseProcess]) -> None:
    try:
        for process in processes:
            process.join(timeout=10)
        assert all(process.exitcode == 0 for process in processes)
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)


def test_proposta_nasce_pendente(store: ProposalStore) -> None:
    proposal = salvar(store)
    assert proposal.status == "pending"
    assert proposal.validated_by is None
    assert store.list_proposals("pending") == [proposal]


def test_id_carrega_provedor_e_e_estavel_por_conteudo(store: ProposalStore) -> None:
    a = salvar(store)
    b = salvar(store, {"texto": "outra coisa"})
    assert "groq" in a.id
    assert a.id != b.id


def test_propostas_identicas_recebem_ids_distintos_sem_sobrescrita(
    store: ProposalStore,
) -> None:
    a = salvar(store)
    b = salvar(store)

    assert a.id != b.id
    assert {proposal.id for proposal in store.list_proposals()} == {a.id, b.id}
    assert len(list(store.directory.glob("*.json"))) == 2


def test_saves_identicos_concorrentes_nao_perdem_propostas(store: ProposalStore) -> None:
    workers = 8
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(workers)
    results = context.Queue()
    processes = [
        context.Process(
            target=_salvar_em_processo,
            args=(str(store.directory), barrier, results),
        )
        for _ in range(workers)
    ]

    for process in processes:
        process.start()
    _join_processes(processes)
    ids = [results.get(timeout=10) for _ in range(workers)]
    results.close()
    results.join_thread()

    assert len(set(ids)) == workers
    assert {proposal.id for proposal in store.list_proposals()} == set(ids)


def test_promocao_exige_quem_validou_e_por_que(store: ProposalStore) -> None:
    proposal = salvar(store)
    with pytest.raises(PromotionRefused, match="quem validou"):
        store.promote_after_validation(proposal.id, validated_by="  ", verdict_note="ok")
    with pytest.raises(PromotionRefused, match="motivo"):
        store.promote_after_validation(proposal.id, validated_by="Luiz", verdict_note="")
    assert store.get(proposal.id).status == "pending"


def test_promocao_registra_o_veredito(store: ProposalStore) -> None:
    proposal = salvar(store)
    promoted = store.promote_after_validation(
        proposal.id, validated_by="Luiz", verdict_note="fonte conferida no original"
    )
    assert promoted.status == "approved"
    assert promoted.validated_by == "Luiz"
    assert promoted.validated_at
    assert store.list_proposals("pending") == []


def test_proposta_ja_decidida_nao_se_decide_de_novo(store: ProposalStore) -> None:
    proposal = salvar(store)
    store.promote_after_validation(proposal.id, validated_by="Luiz", verdict_note="ok")
    with pytest.raises(PromotionRefused, match="já foi decidida"):
        store.promote_after_validation(proposal.id, validated_by="Luiz", verdict_note="ok")


def test_so_uma_promocao_concorrente_vence(store: ProposalStore) -> None:
    proposal = salvar(store, {"texto": "x" * 250_000})
    workers = 6
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(workers)
    results = context.Queue()
    processes = [
        context.Process(
            target=_promover_em_processo,
            args=(str(store.directory), proposal.id, barrier, results),
        )
        for _ in range(workers)
    ]

    for process in processes:
        process.start()
    _join_processes(processes)
    outcomes = [results.get(timeout=10) for _ in range(workers)]
    results.close()
    results.join_thread()

    assert outcomes.count("approved") == 1
    assert outcomes.count("refused") == workers - 1
    assert store.get(proposal.id).status == "approved"


def test_rejeicao_e_decisao_registrada_tambem(store: ProposalStore) -> None:
    proposal = salvar(store)
    rejected = store.promote_after_validation(
        proposal.id,
        validated_by="Luiz",
        verdict_note="DOI não resolveu no editor",
        approved=False,
    )
    assert rejected.status == "rejected"


def test_id_nao_permite_travessia_de_diretorio(store: ProposalStore) -> None:
    outside = store.directory.parent / "outside.json"
    escaped = Proposal(
        id="../outside",
        created_at="2026-07-30T00:00:00+00:00",
        kind="claim-candidato",
        provider="groq",
        endpoint="algum-endpoint",
        prompt_summary="não deve ser lida",
        payload={"texto": "sentinela"},
    )
    outside.write_text(json.dumps(escaped.to_dict()), encoding="utf-8")
    original = outside.read_bytes()

    with pytest.raises(ValueError, match="ID de proposta inválido"):
        store.get("../outside")
    with pytest.raises(ValueError, match="ID de proposta inválido"):
        store.promote_after_validation(
            "../outside",
            validated_by="Luiz",
            verdict_note="não deve escapar",
        )

    assert outside.read_bytes() == original


def test_provider_inseguro_e_sanitizado_no_id(store: ProposalStore) -> None:
    proposal = store.save_proposal(
        kind="claim-candidato",
        provider="../../groq/perigoso",
        endpoint="algum-endpoint",
        prompt_summary="teste de fronteira",
        payload={"texto": "continua dentro do store"},
    )

    assert "/" not in proposal.id
    assert "\\" not in proposal.id
    assert (store.directory / f"{proposal.id}.json").is_file()


def test_escrita_e_lock_usam_modos_privados(store: ProposalStore) -> None:
    proposal = salvar(store)
    proposal_path = store.directory / f"{proposal.id}.json"
    lock_path = store.directory / ".proposal-store.lock"

    assert stat.S_IMODE(store.directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(proposal_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(lock_path.stat().st_mode) == 0o600

    store.promote_after_validation(proposal.id, validated_by="Luiz", verdict_note="ok")
    assert stat.S_IMODE(proposal_path.stat().st_mode) == 0o600


def test_falha_no_replace_preserva_json_anterior_e_limpa_temporario(
    store: ProposalStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proposal = salvar(store)
    proposal_path = store.directory / f"{proposal.id}.json"
    original = proposal_path.read_bytes()

    def falhar_no_replace(_source: object, _target: object) -> None:
        raise OSError("falha simulada no replace")

    monkeypatch.setattr("vault.proposals.store.os.replace", falhar_no_replace)

    with pytest.raises(OSError, match="falha simulada"):
        store.promote_after_validation(
            proposal.id,
            validated_by="Luiz",
            verdict_note="não deve truncar o original",
        )

    assert proposal_path.read_bytes() == original
    assert store.get(proposal.id).status == "pending"
    assert list(store.directory.glob(".proposal-*.tmp")) == []


def test_store_escreve_so_no_proprio_diretorio(store: ProposalStore, repo_root: Path) -> None:
    """Promover não toca em knowledge/. A aplicação no corpus é edição humana."""
    antes = sorted(p.name for p in (repo_root / "knowledge").iterdir())
    proposal = salvar(store)
    store.promote_after_validation(proposal.id, validated_by="Luiz", verdict_note="ok")
    assert sorted(p.name for p in (repo_root / "knowledge").iterdir()) == antes
    assert list(store.directory.glob("*.json"))
