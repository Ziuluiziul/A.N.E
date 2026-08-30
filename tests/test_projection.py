"""O contrato de projeção é a fronteira entre a máquina e o navegador.

Metade destes testes é sobre o que **não** pode atravessar: caminho absoluto, chave,
conteúdo de arquivo, dado inventado. A outra metade prende a ontologia: um `kind`
novo no corpus tem de reprovar a projeção, não virar `note` por omissão.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from vault.corpus import CorpusReader
from vault.projection import (
    CONTRACT_VERSION,
    EPISTEMIC_STATUSES,
    KIND_MAP,
    PALETTE_TOKENS,
    ProjectionError,
    build_projection,
    corpus_fingerprint,
)

BASELINE_NOTES = 84
BASELINE_WIKILINKS = 670
BASELINE_CLAIMS = 267
BASELINE_MOCS = 15
BASELINE_DOMINIOS = 12

NOTA = """---
title: {titulo}
kind: {kind}
epistemic_status: {status}
updated: 2026-07-30
---

# {titulo}

{corpo}
"""


def escrever(raiz: Path, caminho: str, **campos: str) -> None:
    destino = raiz / caminho
    destino.parent.mkdir(parents=True, exist_ok=True)
    campos.setdefault("kind", "nota")
    campos.setdefault("status", "established")
    campos.setdefault("corpo", "")
    destino.write_text(NOTA.format(**campos), encoding="utf-8")


@pytest.fixture(scope="module")
def projecao(corpus_dir: Path) -> dict:
    return build_projection(CorpusReader(corpus_dir))


# --- sanitização -----------------------------------------------------------


def test_nenhum_caminho_absoluto_atravessa_a_fronteira(projecao: dict, repo_root: Path) -> None:
    serializado = json.dumps(projecao, ensure_ascii=False)
    # Reduz a um conjunto pequeno antes de afirmar: um assert sobre a string inteira
    # obriga o pytest a montar a explicação de 200 KB quando falha.
    vazamentos = [
        agulha
        for agulha in (str(repo_root), str(Path.home()), "/home/", "/tmp/")
        if agulha in serializado
    ]
    assert vazamentos == []
    caminhos_suspeitos = [
        node["path"]
        for node in projecao["nodes"]
        if node["path"].startswith("/") or ".." in node["path"]
    ]
    assert caminhos_suspeitos == []


def test_a_projecao_nao_carrega_conteudo_de_nota(projecao: dict) -> None:
    """O navegador recebe estrutura, não o corpus inteiro."""
    campos = set()
    for node in projecao["nodes"]:
        campos.update(node)
    assert "body" not in campos
    assert "content" not in campos
    assert "frontmatter" not in campos


def test_nenhuma_credencial_atravessa_a_fronteira(projecao: dict) -> None:
    """Procura chave de verdade, não a palavra "token".

    `visual.paletteToken` é um nome de campo legítimo; proibir a substring seria um
    teste que reprova o inocente e deixa passar o culpado. O que interessa é o
    formato das chaves reais e os nomes das variáveis de ambiente.
    """
    serializado = json.dumps(projecao, ensure_ascii=False)
    formatos = re.compile(
        r"AIza[0-9A-Za-z_\-]{20,}|gsk_[0-9A-Za-z]{20,}|nvapi-[0-9A-Za-z_\-]{20,}"
        r"|sk-(?:or-v1-)?[0-9A-Za-z_\-]{20,}|ya29\.[0-9A-Za-z_\-]{20,}"
    )
    assert formatos.findall(serializado) == []

    variaveis = {
        "GEMINI_API_KEY",
        "GROQ_API_KEY",
        "NVIDIA_API_KEY",
        "OLLAMA_API_KEY",
        "OPENROUTER_API_KEY",
        "GOOGLE_WORKSPACE_CLIENT_SECRET_FILE",
        "GOOGLE_WORKSPACE_TOKEN_FILE",
    }
    assert sorted(v for v in variaveis if v in serializado) == []
    assert sorted(chaves_recursivas(projecao) & variaveis) == []


def chaves_recursivas(valor: object) -> set[str]:
    if isinstance(valor, dict):
        return set(valor) | {k for v in valor.values() for k in chaves_recursivas(v)}
    if isinstance(valor, list):
        return {k for item in valor for k in chaves_recursivas(item)}
    return set()


# --- versão e origem -------------------------------------------------------


def test_contrato_declara_versao_e_origem(projecao: dict) -> None:
    meta = projecao["meta"]
    assert meta["contractVersion"] == CONTRACT_VERSION
    assert meta["source"] == "corpus"


def test_impressao_digital_coincide_com_o_manifesto_do_auditor(
    projecao: dict, corpus_dir: Path
) -> None:
    """Mesmo número que `make audit` imprime — conferível numa linha de terminal."""
    assert projecao["meta"]["corpusFingerprint"] == corpus_fingerprint(CorpusReader(corpus_dir))
    assert len(projecao["meta"]["corpusFingerprint"]) == 64


def test_campos_derivados_sao_declarados(projecao: dict) -> None:
    """Inferência marcada como inferência: o frontend não pode lê-la como frontmatter."""
    computados = projecao["meta"]["computedFields"]
    for campo in ("domainId", "anchorMocId", "visual.paletteToken", "edges[kind=aggregated]"):
        assert campo in computados


# --- contagens -------------------------------------------------------------


def test_contagens_batem_com_a_baseline(projecao: dict) -> None:
    counts = projecao["meta"]["counts"]
    assert counts["notes"] == BASELINE_NOTES
    assert counts["wikilinks"] == BASELINE_WIKILINKS
    assert counts["claims"] == BASELINE_CLAIMS
    assert counts["mocs"] == BASELINE_MOCS
    assert len(projecao["meta"]["domains"]) == BASELINE_DOMINIOS


def test_corpus_atual_nao_tem_diagnostico_pendente(projecao: dict) -> None:
    diagnostics = projecao["meta"]["diagnostics"]
    assert diagnostics["broken"] == []
    assert diagnostics["undeclared"] == []
    assert diagnostics["collisions"] == {}


# --- ontologia -------------------------------------------------------------


def test_todo_no_tem_tipo_do_vocabulario_fechado(projecao: dict) -> None:
    tipos = {node["kind"] for node in projecao["nodes"]}
    assert tipos <= set(KIND_MAP.values())
    assert "moc" in tipos and "note" in tipos


def test_todo_no_tem_status_epistemico_conhecido(projecao: dict) -> None:
    for node in projecao["nodes"]:
        assert node["epistemicStatus"] in EPISTEMIC_STATUSES


def test_tudo_em_knowledge_e_canonico(projecao: dict) -> None:
    assert {node["canonicalState"] for node in projecao["nodes"]} == {"canonical"}


def test_kind_desconhecido_reprova_em_vez_de_virar_nota(tmp_path: Path) -> None:
    escrever(tmp_path, "Física/Nova.md", titulo="Nova", kind="artefato-novo")
    with pytest.raises(ProjectionError, match="fora do vocabulário conhecido"):
        build_projection(CorpusReader(tmp_path))


def test_status_epistemico_desconhecido_reprova(tmp_path: Path) -> None:
    escrever(tmp_path, "Física/Nova.md", titulo="Nova", status="talvez")
    with pytest.raises(ProjectionError, match="fora do vocabulário"):
        build_projection(CorpusReader(tmp_path))


def test_kind_ausente_reprova_em_vez_de_adivinhar(tmp_path: Path) -> None:
    destino = tmp_path / "Física" / "Sem.md"
    destino.parent.mkdir(parents=True)
    destino.write_text("---\ntitle: Sem\n---\n\ntexto\n", encoding="utf-8")
    with pytest.raises(ProjectionError, match="não declara `kind`"):
        build_projection(CorpusReader(tmp_path))


# --- domínios, MOCs e âncoras ----------------------------------------------


def test_cada_dominio_recebe_um_token_de_paleta_distinto(projecao: dict) -> None:
    tokens = [dominio["paletteToken"] for dominio in projecao["meta"]["domains"]]
    assert len(tokens) == len(set(tokens))
    assert set(tokens) <= set(PALETTE_TOKENS)


def test_mocs_sao_ancoras_e_notas_nao(projecao: dict) -> None:
    for node in projecao["nodes"]:
        assert node["visual"]["isAnchor"] == (node["kind"] == "moc")


def test_moc_nao_ancora_a_si_mesmo(projecao: dict) -> None:
    for node in projecao["nodes"]:
        if node["kind"] == "moc":
            assert node["anchorMocId"] is None


def test_ancora_nunca_e_de_outro_dominio(projecao: dict) -> None:
    dominio_de = {node["id"]: node["domainId"] for node in projecao["nodes"]}
    for node in projecao["nodes"]:
        ancora = node["anchorMocId"]
        if ancora is not None:
            assert dominio_de[ancora] == node["domainId"]


def test_dominio_com_dois_mocs_nao_recebe_ancora_arbitraria(projecao: dict) -> None:
    """Computação tem dois MOCs; quem não é reivindicado por um deles fica sem âncora."""
    com_dois = [d for d in projecao["meta"]["domains"] if len(d["mocIds"]) > 1]
    assert com_dois, "o corpus tem ao menos um domínio com mais de um MOC"
    for dominio in com_dois:
        notas = [n for n in projecao["nodes"] if n["domainId"] == dominio["id"]]
        ancoras = {n["anchorMocId"] for n in notas if n["kind"] != "moc"}
        assert ancoras <= set(dominio["mocIds"]) | {None}


# --- arestas ---------------------------------------------------------------


def test_toda_aresta_liga_dois_nos_existentes(projecao: dict) -> None:
    ids = {node["id"] for node in projecao["nodes"]}
    for edge in projecao["edges"]:
        assert edge["source"] in ids
        assert edge["target"] in ids


def test_arestas_canonicas_declaram_relacao_do_vocabulario(projecao: dict) -> None:
    familias = set(projecao["meta"]["relationFamilies"])
    for edge in projecao["edges"]:
        if edge["kind"] == "canonical":
            assert set(edge["relations"]) <= familias
            assert edge["primaryRelation"] in familias


def test_agregados_ligam_mocs_e_declaram_que_sao_calculados(projecao: dict) -> None:
    mocs = {node["id"] for node in projecao["nodes"] if node["kind"] == "moc"}
    agregados = [e for e in projecao["edges"] if e["kind"] == "aggregated"]
    assert agregados, "a visão global precisa de filamentos inter-MOC"
    for edge in agregados:
        assert edge["source"] in mocs
        assert edge["target"] in mocs
        assert edge["source"] != edge["target"]
        assert edge["matchedBy"] == "computed"


def test_agregado_pesa_o_que_as_arestas_canonicas_somam(projecao: dict) -> None:
    """O peso do agregado soma os **dois sentidos** do par.

    Este teste prendia a agregação por par ordenado, que era o defeito: um par de MOCs
    com tráfego de ida e volta produzia duas arestas agregadas, desenhadas como dois
    tubos paralelos entre os mesmos territórios.
    """
    ancora_de = {
        node["id"]: (node["id"] if node["kind"] == "moc" else node["anchorMocId"])
        for node in projecao["nodes"]
    }
    esperado: dict[tuple[str, str], int] = {}
    for edge in projecao["edges"]:
        if edge["kind"] != "canonical":
            continue
        origem, destino = ancora_de[edge["source"]], ancora_de[edge["target"]]
        if origem and destino and origem != destino:
            chave = (origem, destino) if origem < destino else (destino, origem)
            esperado[chave] = esperado.get(chave, 0) + edge["weight"]
    obtido = {
        (e["source"], e["target"]): e["weight"]
        for e in projecao["edges"]
        if e["kind"] == "aggregated"
    }
    assert obtido == esperado


def test_agregado_e_unico_por_par_nao_ordenado(projecao: dict) -> None:
    agregados = [e for e in projecao["edges"] if e["kind"] == "aggregated"]
    pares = [frozenset((e["source"], e["target"])) for e in agregados]
    assert len(pares) == len(set(pares)), "par de MOCs com mais de uma aresta agregada"
    # E a ordem do par é canônica, para a chave ser estável entre execuções.
    for edge in agregados:
        assert edge["source"] < edge["target"]


def test_agregado_preserva_a_direcao_que_a_unificacao_absorveu(projecao: dict) -> None:
    """Unificar o par não pode apagar de que sentido cada relação veio."""
    ancora_de = {
        node["id"]: (node["id"] if node["kind"] == "moc" else node["anchorMocId"])
        for node in projecao["nodes"]
    }
    por_sentido: dict[tuple[str, str], int] = {}
    for edge in projecao["edges"]:
        if edge["kind"] != "canonical":
            continue
        origem, destino = ancora_de[edge["source"]], ancora_de[edge["target"]]
        if origem and destino and origem != destino:
            por_sentido[(origem, destino)] = (
                por_sentido.get((origem, destino), 0) + edge["weight"]
            )

    reciprocos = 0
    for edge in projecao["edges"]:
        if edge["kind"] != "aggregated":
            continue
        a, b = edge["source"], edge["target"]
        assert edge["weightByDirection"]["forward"] == por_sentido.get((a, b), 0)
        assert edge["weightByDirection"]["backward"] == por_sentido.get((b, a), 0)
        assert edge["weight"] == (
            edge["weightByDirection"]["forward"] + edge["weightByDirection"]["backward"]
        )
        soma = set(edge["relationsByDirection"]["forward"]) | set(
            edge["relationsByDirection"]["backward"]
        )
        assert soma == set(edge["relations"])
        if edge["reciprocal"]:
            reciprocos += 1
            assert edge["weightByDirection"]["forward"] > 0
            assert edge["weightByDirection"]["backward"] > 0
    # O corpus real tem pares recíprocos; sem eles o teste não provaria nada.
    assert reciprocos > 0


# --- sem fallback silencioso -----------------------------------------------


def test_corpus_ausente_falha_em_vez_de_cair_para_demonstracao(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_projection(CorpusReader(tmp_path / "inexistente"))


def test_corpus_vazio_produz_projecao_vazia_e_nao_dados_de_exemplo(tmp_path: Path) -> None:
    projecao = build_projection(CorpusReader(tmp_path))
    assert projecao["nodes"] == []
    assert projecao["edges"] == []
    assert projecao["meta"]["source"] == "corpus"


def test_conteudo_da_nota_chega_projetado_e_sem_marcacao(projecao: dict) -> None:
    """A projeção levava só metadado, e o painel aberto não tinha o que mostrar.

    O que entra é o conteúdo epistêmico: a abertura do corpo e os claims com afirmação,
    status do vocabulário fechado e evidência. Texto puro, porque o painel escreve numa
    malha de glifos e não tem negrito para aplicar.
    """
    notas = [n for n in projecao["nodes"] if n["kind"] == "note"]
    assert notas, "o corpus de teste precisa ter nota"
    com_claims = [n for n in notas if n["claims"]]
    assert com_claims, "nenhuma nota projetou claim"

    for node in projecao["nodes"]:
        if node["layer"] != "epistemic":
            continue
        assert node["claimCount"] == len(node["claims"])
        for claim in node["claims"]:
            assert claim["id"].startswith("CLM-")
            assert claim["statement"]
            assert claim["status"]
            # Nada de marcação crua: nem ênfase, nem wikilink, nem comentário.
            for campo in (claim["statement"], claim["evidence"] or ""):
                assert "**" not in campo
                assert "[[" not in campo
                assert "<!--" not in campo
        if node["summary"]:
            assert "**" not in node["summary"]
            assert "<!--" not in node["summary"]


def test_texto_puro_preserva_o_que_nao_e_marcacao() -> None:
    from vault.projection import _texto_puro

    assert _texto_puro("**tem** fonte") == "tem fonte"
    assert _texto_puro("ver [[Nota Alvo]]") == "ver Nota Alvo"
    assert _texto_puro("[[Outra|apelido]]") == "Outra"
    comentario = _texto_puro("relação <!-- relation:prerequisite --> some")
    assert " ".join(comentario.split()) == "relação some"
    # Multiplicação e sublinhado dentro de palavra não são ênfase.
    assert _texto_puro("3 * 4 e a_b_c") == "3 * 4 e a_b_c"
