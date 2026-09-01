"""Camada operacional: vazia em produção, fabricada só sob pedido explícito.

O ponto destes testes não é a fixture funcionar — é ela **não** aparecer sozinha.
Uma trilha sintética que vazasse para produção seria procedência fabricada, que é o
defeito mais grave que este sistema pode ter.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from vault import projection as projection_mod
from vault.config import Settings
from vault.control.credentials import ENV_VAR_BY_PROVIDER
from vault.corpus import CorpusReader
from vault.operational import (
    OPERATIONAL_KINDS,
    QUORUM_ACTIONS,
    STATE_BY_KIND,
    build_operational,
    demo_trail,
    quorum_trails,
)
from vault.projection import build_projection, clear_runtime_overlay_cache, with_runtime_quorum
from vault.work.roles import ROLES


def settings_isoladas() -> Settings:
    """`Settings` sem ler o secrets.env: a flag tem de vir do ambiente, não do disco."""
    return Settings(_env_file=None)  # type: ignore[call-arg]


# --- ausência é o normal ---------------------------------------------------


def test_producao_nasce_sem_camada_operacional() -> None:
    camada, origem = build_operational(demo=False)
    assert camada == {"nodes": [], "edges": []}
    assert origem == "none"


def test_trabalhador_tem_no_proprio_quando_ha_camada_operacional() -> None:
    """A configuração de um papel precisa de placa, e placa precisa de nó.

    Antes disto os sete papéis só existiam na cena como votos dentro de centenas de
    painéis de quórum: não havia nenhum nó que fosse **o** verificador factual, e por
    isso "ativo", "simultâneas" e "raciocínio" não tinham a que ser ancorados.
    """
    camada, origem = build_operational(demo=True)
    trabalhadores = [
        node for node in camada["nodes"] if node["domainId"] == "operacional/trabalhadores"
    ]
    assert origem == "demo"
    assert {node["id"] for node in trabalhadores} == {
        f"op/worker/{nome}" for nome in ROLES
    }
    for node in trabalhadores:
        papel = ROLES[node["operational"]["role"]]
        assert node["operational"]["workerClass"] == (
            "avaliador" if papel.reviews_others else "produtor"
        )
        # O teto do papel é estático e vem de `roles.py`; o efetivo é do painel de
        # controle, que sabe do orçamento da execução. Só o primeiro entra aqui.
        assert node["operational"]["concurrencyMax"] == papel.max_concurrency
        assert "concurrency" not in node["operational"]
        assert node["visual"]["isAnchor"] is True


def test_provedor_configuravel_tem_ancora_mesmo_sem_catalogo(tmp_path: Path) -> None:
    painel_persistido(tmp_path)
    camada, _ = build_operational(demo=False, quorum_root=tmp_path)
    provedores = {
        node["id"]: node
        for node in camada["nodes"]
        if node["domainId"] == "operacional/provedores"
    }
    assert set(provedores) == {f"op/provider/{nome}" for nome in ENV_VAR_BY_PROVIDER}
    nous = provedores["op/provider/nous"]
    assert nous["visual"]["isAnchor"] is True
    assert nous["visual"]["paletteToken"] == "P:nous"
    assert nous["operational"]["modelCount"] == 0
    assert nous["shortLabel"] == "nous"


def test_trabalhador_nao_aparece_sem_camada_operacional() -> None:
    # Corpus limpo não inventa operação. Sete nós fixos seriam exatamente o dado de
    # exemplo que a fronteira da projeção proíbe.
    camada, _ = build_operational(demo=False)
    assert camada["nodes"] == []


def test_projecao_real_nao_traz_evento_algum(corpus_dir: Path) -> None:
    projecao = build_projection(CorpusReader(corpus_dir))
    assert projecao["meta"]["operationalSource"] == "none"
    assert projecao["meta"]["counts"]["operationalNodes"] == 0
    assert all(node["layer"] == "epistemic" for node in projecao["nodes"])


def test_a_flag_e_desligada_por_padrao() -> None:
    assert settings_isoladas().demo_operational is False


def test_a_flag_liga_so_por_pedido_explicito(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VAULT_DEMO_OPERATIONAL", "1")
    assert settings_isoladas().demo_operational is True


# --- a trilha, quando pedida ----------------------------------------------


def test_demo_cobre_a_trilha_inteira(corpus_dir: Path) -> None:
    projecao = build_projection(CorpusReader(corpus_dir), demo_operational=True)
    assert projecao["meta"]["operationalSource"] == "demo"
    tipos = {n["kind"] for n in projecao["nodes"] if n["layer"] == "operational"}
    assert tipos == set(OPERATIONAL_KINDS)


def test_existe_caminho_de_agente_ate_commit() -> None:
    trilha = demo_trail()
    arestas = {(e["source"], e["target"]) for e in trilha["edges"]}
    caminho = [
        ("op/agente/revisor", "op/atividade/varredura"),
        ("op/atividade/varredura", "op/evidencia/doi"),
        ("op/evidencia/doi", "op/proposta/claim-novo"),
        ("op/proposta/claim-novo", "op/commit/aceito"),
    ]
    for passo in caminho:
        assert passo in arestas, passo


def test_existe_ramo_que_termina_em_rejeicao() -> None:
    trilha = demo_trail()
    arestas = {(e["source"], e["target"]) for e in trilha["edges"]}
    assert ("op/proposta/recusada", "op/rejeicao/sem-fonte") in arestas
    rejeicao = next(n for n in trilha["nodes"] if n["kind"] == "rejection")
    assert rejeicao["canonicalState"] == "rejected"


# --- não confundir com o canônico -----------------------------------------


def test_proposta_nao_e_canonica() -> None:
    assert STATE_BY_KIND["proposal"] == "proposed"
    proposta = next(n for n in demo_trail()["nodes"] if n["kind"] == "proposal")
    assert proposta["canonicalState"] == "proposed"
    assert proposta["path"] is None


def test_arquivo_temporario_nao_e_canonico() -> None:
    assert STATE_BY_KIND["temporary-file"] == "temporary"
    temporario = next(n for n in demo_trail()["nodes"] if n["kind"] == "temporary-file")
    assert temporario["canonicalState"] == "temporary"
    assert temporario["layer"] == "operational"


def test_nenhum_no_operacional_tem_arquivo_no_corpus() -> None:
    for node in demo_trail()["nodes"]:
        assert node["path"] is None
        assert node["claimCount"] == 0
        assert node["anchorMocId"] is None


def test_camada_operacional_nao_altera_as_contagens_do_corpus(corpus_dir: Path) -> None:
    sem = build_projection(CorpusReader(corpus_dir))["meta"]["counts"]
    com = build_projection(CorpusReader(corpus_dir), demo_operational=True)["meta"]["counts"]
    for chave in ("notes", "wikilinks", "claims", "mocs", "canonicalEdges"):
        assert sem[chave] == com[chave], chave


def test_nada_de_raciocinio_interno_na_trilha() -> None:
    """Procedência é o que se pode auditar; scratchpad de modelo não é."""
    textos = " ".join(
        f"{n['title']} {n['shortLabel']}" for n in demo_trail()["nodes"]
    ).lower()
    for proibido in ("thought", "reasoning", "scratchpad", "raciocínio", "pensou"):
        assert proibido not in textos


# --- painéis reais ---------------------------------------------------------


def escrever_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def painel_persistido(root: Path, *, outcome: str = "promote") -> Path:
    panel = root / "panel-001"
    proposal = {
        "id": "proposal-001",
        "proposer": {
            "provider": "nvidia",
            "endpoint_id": "meta/llama-proposer",
            "family": "llama",
            "role_name": "proponente",
        },
        # Estes campos existem no armazenamento, mas jamais entram no Atlas.
        "final_response": "conclusão que não pertence ao snapshot operacional",
        "raw_response": "<think>segredo interno</think> chave-falsa-curta",
        "reasoning_block_detected": True,
        "reasoning_block_removed": True,
    }
    escrever_json(
        panel / "task.json",
        {
            "panel_id": "panel-001",
            "task": {
                "id": "task-001",
                "kind": "quorum",
                "prompt": "texto livre não projetado",
                "context": {},
            },
            "proposal": proposal,
        },
    )
    members = [
        {
            "provider": "groq",
            "endpoint_id": "qwen/qwen3",
            "family": "qwen",
            "role_name": "revisor",
        },
        {
            "provider": "nvidia",
            "endpoint_id": "mistral/mixtral",
            "family": "mistral",
            "role_name": "revisor",
        },
        {
            "provider": "groq",
            "endpoint_id": "meta/llama-reviewer",
            "family": "llama",
            "role_name": "revisor",
        },
    ]
    escrever_json(
        panel / "members.json",
        members,
    )
    decisions = ("approve", "approve", "revise")
    for index, (member, decision) in enumerate(zip(members, decisions, strict=True), start=1):
        escrever_json(
            panel / "votes" / f"vote-{index}.json",
            {
                "reviewer": member,
                "final_response": "resultado estruturado; não deve atravessar",
                "raw_response": "<think>também não</think>",
                "reasoning_block_detected": index == 1,
                "reasoning_block_removed": index == 1,
                "schema_valid": True,
                "repair_attempted": False,
                "repair_succeeded": False,
                "error": None,
                "structured_vote": {
                    "decision": decision,
                    "confidence": 0.9 - index / 10,
                    "blocking_issues": [],
                    "non_blocking_issues": ["texto livre fora do Atlas"],
                    "evidence": [],
                    "recommended_action": "promote",
                },
            },
        )
    escrever_json(
        panel / "decision.json",
        {
            "panel_id": "panel-001",
            "id": "decision-001",
            "outcome": outcome,
            "status": "decided",
            "tally": {"approve": 2, "revise": 1, "reject": 0, "abstain": 0},
            "votes": [],
            "valid_vote_count": 3,
            "provider_count": 2,
            "family_count": 3,
            "reason": "texto deliberadamente não projetado",
            "structural_failures": [],
            "decided_at": "2026-08-03T18:00:00+00:00",
        },
    )
    return panel


def test_runtime_quorum_projeta_painel_membros_votos_e_decisao(tmp_path: Path) -> None:
    painel_persistido(tmp_path)
    camada, origem = build_operational(
        demo=False, quorum_root=tmp_path, include_history=True
    )

    assert origem == "quorum"
    kinds = [node["kind"] for node in camada["nodes"]]
    assert kinds.count("quorum-panel") == 1
    assert kinds.count("quorum-member") == 3
    assert kinds.count("quorum-vote") == 3
    assert kinds.count("quorum-decision") == 1
    decisao = next(node for node in camada["nodes"] if node["kind"] == "quorum-decision")
    assert decisao["operational"] == {
        "panelId": "panel-001",
        "action": "promote",
        "tally": {"abstain": 0, "approve": 2, "reject": 0, "revise": 1},
        # Desde 3.5-D o motivo e a apuração chegam à cena: sem eles o painel de decisão
        # mostrava um veredicto sem dizer de onde ele veio.
        "reason": "texto deliberadamente não projetado",
        "validVotes": 3,
        "providerCount": 2,
        "familyCount": 3,
    }
    assert decisao["canonicalState"] == "temporary"
    assert all(edge["kind"] == "operational" for edge in camada["edges"])
    # Nenhum nó de trilha fica solto: painel, membro, voto e decisão existem porque
    # alguma execução os produziu, e um deles sem aresta é defeito de projeção.
    #
    # O trabalhador é a exceção declarada, e não um esquecimento. Ele não vem de
    # execução nenhuma — é a configuração do que **vai** executar —, e a única aresta
    # estática possível seria para o modelo a que o AUTO o resolve, que muda a cada
    # leitura do catálogo. Uma linha gravada aqui apontaria para a resolução de ontem.
    da_trilha = [
        node
        for node in camada["nodes"]
        if node["domainId"] != "operacional/trabalhadores"
        and not (
            node["domainId"] == "operacional/provedores"
            and node["operational"].get("modelCount", 0) == 0
        )
    ]
    assert len(da_trilha) < len(camada["nodes"])
    assert all(node["incomingDegree"] + node["outgoingDegree"] > 0 for node in da_trilha)


def test_decisao_estrutural_projeta_a_regra_que_quebrou(tmp_path: Path) -> None:
    """O rótulo do gate não substitui a regra da política."""
    painel = painel_persistido(tmp_path)
    escrever_json(
        painel / "decision.json",
        {
            "panel_id": "panel-001",
            "id": "decision-001",
            "outcome": "reject",
            "status": "decided",
            "tally": {"approve": 1, "revise": 0, "reject": 1, "abstain": 0},
            "votes": [],
            "valid_vote_count": 2,
            "provider_count": 2,
            "family_count": 2,
            "reason": "falha estrutural objetiva registrada",
            "structural_failures": [
                {
                    "source": "revisor-estrutural",
                    "issue": (
                        "Nenhum wikilink foi declarado com as relações do "
                        "vocabulário permitido."
                    ),
                    "reviewer": {
                        "provider": "ollama",
                        "endpoint_id": "minimax-m3",
                        "family": "minimax-m3",
                        "role_name": "revisor-estrutural",
                    },
                }
            ],
            "decided_at": "2026-08-12T16:22:55+00:00",
        },
    )
    camada, _origem = build_operational(
        demo=False, quorum_root=tmp_path, include_history=True
    )
    decisao = next(node for node in camada["nodes"] if node["kind"] == "quorum-decision")
    assert decisao["operational"]["reason"] == "falha estrutural objetiva registrada"
    assert (
        decisao["operational"]["blockingIssue"]
        == "Nenhum wikilink foi declarado com as relações do vocabulário permitido."
    )


@pytest.mark.parametrize("outcome", sorted(QUORUM_ACTIONS))
def test_atlas_preserva_as_quatro_acoes_fechadas(tmp_path: Path, outcome: str) -> None:
    painel_persistido(tmp_path, outcome=outcome)
    camada = quorum_trails(tmp_path, include_history=True)
    decisao = next(node for node in camada["nodes"] if node["kind"] == "quorum-decision")
    assert decisao["operational"]["action"] == outcome


def test_snapshot_operacional_e_whitelist_sem_resposta_bruta(tmp_path: Path) -> None:
    """A lista branca continua fechada; o que mudou foi o que ela admite.

    Até 3.5-C nenhum texto livre era projetado, e o painel de quórum chegava à cena sem
    ter o que dizer. A direção de 3.5-D pede o oposto — tarefa, proposta, avaliação e
    motivo em linguagem natural —, e o que protege deixou de ser "nada de texto" e
    passou a ser o sanitizador: `_resumo` recusa bloco de raciocínio e qualquer coisa
    com forma de segredo, e corta o resto na fronteira de frase.

    O que **não** afrouxou: chave fora da lista branca continua reprovando, e resposta
    bruta e raciocínio continuam sem caminho por onde entrar.
    """
    painel_persistido(tmp_path)
    camada = quorum_trails(tmp_path, include_history=True)
    serializado = json.dumps(camada, ensure_ascii=False)

    assert "raw_response" not in serializado
    assert "<think" not in serializado.lower()
    assert "segredo interno" not in serializado
    assert "gsk_" not in serializado
    permitido = {
        "panelId",
        "decision",
        "action",
        "confidence",
        "tally",
        "endpoint",
        "provider",
        "family",
        "role",
        "reasoningBlockDetected",
        "reasoningBlockRemoved",
        "validVotes",
        "providerCount",
        "familyCount",
        "task",
        "entity",
        "candidate",
        "assessment",
        "blockingIssue",
        "reason",
        "synthesis",
        # Contagens do registro de modelos: derivadas das arestas já emitidas, nunca de
        # texto produzido por modelo. Entram aqui porque a whitelist é a declaração do
        # que pode atravessar, e não uma formalidade a contornar.
        "modelCount",
        "executionCount",
        "availableCount",
        "endpointStatus",
    }
    for node in camada["nodes"]:
        assert set(node.get("operational", {})) <= permitido


def test_texto_com_raciocinio_ou_segredo_nao_vira_frase_de_painel(tmp_path: Path) -> None:
    """O sanitizador é o que sustenta a abertura ao texto livre — então ele é testado."""
    from vault.operational import _resumo

    assert _resumo("uma frase honesta sobre a proposta") == "uma frase honesta sobre a proposta"
    assert _resumo("<think>cadeia privada</think> conclusão") is None
    assert _resumo("a chave é gsk_ABCDEFGHIJKLMNOPQRSTUVWX") is None
    assert _resumo("a chave é sk-or-v1-ABCDEFGHIJKLMNOPQRSTUVWX") is None
    assert _resumo("") is None
    assert _resumo(None) is None
    # Texto longo é cortado na fronteira de frase, não recusado inteiro.
    longo = "Primeira frase completa. " + "palavra " * 200
    cortado = _resumo(longo, limit=60)
    assert cortado is not None
    assert len(cortado) <= 61
    assert cortado.startswith("Primeira frase completa.")


def test_json_corrompido_e_symlink_fora_da_raiz_sao_ignorados(tmp_path: Path) -> None:
    raiz = tmp_path / "quorum"
    painel_persistido(raiz)
    corrompido = raiz / "panel-corrupt"
    corrompido.mkdir(parents=True)
    (corrompido / "task.json").write_text("{", encoding="utf-8")
    escrever_json(
        corrompido / "members.json",
        [],
    )
    fora = tmp_path / "fora"
    painel_persistido(fora)
    (raiz / "panel-link").symlink_to(fora / "panel-001", target_is_directory=True)

    camada = quorum_trails(raiz, include_history=True)
    paineis = [node for node in camada["nodes"] if node["kind"] == "quorum-panel"]
    assert [node["operational"]["panelId"] for node in paineis] == ["panel-001"]


def test_quorum_trails_projeta_observatorio_recente(tmp_path: Path) -> None:
    painel_persistido(tmp_path)
    camada = quorum_trails(tmp_path)
    kinds = [node["kind"] for node in camada["nodes"]]
    assert kinds.count("quorum-panel") == 1
    assert kinds.count("quorum-decision") == 1
    vazia = quorum_trails(tmp_path, limit=0)
    assert all(node["kind"] != "quorum-panel" for node in vazia["nodes"])


def test_merge_dinamico_preserva_snapshot_e_fingerprint_do_corpus(
    tmp_path: Path, corpus_dir: Path
) -> None:
    painel_persistido(tmp_path)
    base = build_projection(CorpusReader(corpus_dir))
    fingerprint = base["meta"]["corpusFingerprint"]
    merged = with_runtime_quorum(base, tmp_path)

    assert base["meta"]["operationalSource"] == "none"
    assert base["meta"]["counts"]["operationalNodes"] == 0
    assert merged["meta"]["operationalSource"] == "quorum"
    assert merged["meta"]["corpusFingerprint"] == fingerprint
    kinds = [node["kind"] for node in merged["nodes"] if node["layer"] == "operational"]
    assert kinds.count("quorum-panel") == 1
    extras = 8 + len(ENV_VAR_BY_PROVIDER) + len(ROLES)
    assert merged["meta"]["counts"]["operationalNodes"] == extras
    assert len(merged["nodes"]) == len(base["nodes"]) + extras


def test_demo_e_runtime_declaram_origem_mista(tmp_path: Path, corpus_dir: Path) -> None:
    painel_persistido(tmp_path)
    demo = build_projection(CorpusReader(corpus_dir), demo_operational=True)
    merged = with_runtime_quorum(demo, tmp_path)
    assert merged["meta"]["operationalSource"] == "mixed"


def test_overlay_nao_rele_json_enquanto_mtime_nao_muda(
    tmp_path: Path, corpus_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    painel_persistido(tmp_path)
    clear_runtime_overlay_cache()
    chamadas = {"n": 0}
    original = projection_mod.build_operational

    def contar(**kwargs: Any) -> tuple[dict[str, Any], str]:
        chamadas["n"] += 1
        return original(**kwargs)

    monkeypatch.setattr(projection_mod, "build_operational", contar)
    base = build_projection(CorpusReader(corpus_dir))
    chamadas["n"] = 0
    primeiro = with_runtime_quorum(base, tmp_path)
    segundo = with_runtime_quorum(base, tmp_path)
    assert chamadas["n"] == 1
    assert primeiro["meta"]["counts"]["operationalNodes"] == segundo["meta"]["counts"][
        "operationalNodes"
    ]

    (tmp_path / "panel-novo").mkdir()
    with_runtime_quorum(base, tmp_path)
    assert chamadas["n"] == 2
