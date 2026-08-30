"""O leitor tem de concordar com o auditor.

`tools/audit.py` é o gate e é independente de propósito — ele reimplementa as
expressões regulares em vez de importar o backend. O preço dessa independência é que
as duas implementações podem divergir em silêncio. Este arquivo é o que impede isso:
as contagens do leitor são comparadas com as do auditor na mesma árvore.

Os números da baseline de 2026-07-30 (81 notas, 627 wikilinks, 267 claims) entram
como asserção explícita. Se uma nota nova entrar no corpus, este teste falha e o
número é atualizado de propósito — não por acidente.
"""

from __future__ import annotations

import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from vault.corpus import CorpusReader
from vault.projection import build_projection

BASELINE_NOTES = 84
BASELINE_WIKILINKS = 672
BASELINE_CLAIMS = 267

CANONICAL_STATUSES = {
    "established",
    "supported",
    "model-dependent",
    "hypothesis",
    "speculative",
    "open",
    "refuted",
    "operational",
    "out-of-scope",
    "quarantine",
}
EXPECTED_STATUS_COUNTS = {
    "established": 164,
    "supported": 27,
    "model-dependent": 12,
    "hypothesis": 7,
    "speculative": 6,
    "open": 14,
    "refuted": 33,
    "operational": 3,
    "out-of-scope": 1,
}


def test_lista_todas_as_notas_do_corpus(corpus_dir: Path) -> None:
    notes = CorpusReader(corpus_dir).list_notes()
    assert len(notes) == BASELINE_NOTES
    assert all(note.frontmatter for note in notes), "toda nota tem frontmatter"


def test_contagens_batem_com_a_baseline(corpus_dir: Path) -> None:
    reader = CorpusReader(corpus_dir)
    notes = reader.list_notes()
    links = sum(len(reader.extract_links(note)) for note in notes)
    claims = sum(len(reader.extract_claims(note)) for note in notes)
    assert (links, claims) == (BASELINE_WIKILINKS, BASELINE_CLAIMS)


def test_ids_de_claim_sao_unicos_no_corpus(corpus_dir: Path) -> None:
    reader = CorpusReader(corpus_dir)
    ids = [claim.id for note in reader.list_notes() for claim in reader.extract_claims(note)]
    assert len(ids) == len(set(ids))


def test_todos_os_267_statuses_sao_canonicos(corpus_dir: Path) -> None:
    reader = CorpusReader(corpus_dir)
    statuses = [
        claim.status for note in reader.list_notes() for claim in reader.extract_claims(note)
    ]

    assert len(statuses) == BASELINE_CLAIMS
    assert set(statuses) <= CANONICAL_STATUSES
    assert Counter(statuses) == EXPECTED_STATUS_COUNTS


def test_claims_reais_com_pipe_preservam_as_celulas(corpus_dir: Path) -> None:
    reader = CorpusReader(corpus_dir)
    claims = {
        claim.id: claim for note in reader.list_notes() for claim in reader.extract_claims(note)
    }
    expected = {
        "CLM-EST-INFER-001": (
            "O valor-p é `P(dados tão ou mais extremos | H₀)`, e **não** "
            "`P(H₀ | dados)`; a inversão dos dois é inválida sem prior.",
            "Casella & Berger",
            42,
        ),
        "CLM-EST-BAYES-001": (
            "A posterior responde `P(θ | dados)` diretamente, o que a inferência "
            "frequentista não fornece sem prior.",
            "Gelman et al.",
            41,
        ),
        "CLM-MAT-CONJ-001": (
            "Existem conjuntos infinitos de cardinalidades distintas; em particular "
            "`|R| > |N|`, por argumento diagonal.",
            "Enderton",
            40,
        ),
    }

    for claim_id, (statement, evidence_start, line) in expected.items():
        claim = claims[claim_id]
        assert claim.statement == statement
        assert claim.status == "established"
        assert claim.evidence.startswith(evidence_start)
        assert claim.line == line


def test_pipe_na_evidencia_e_status_com_crases(tmp_path: Path) -> None:
    note_path = tmp_path / "Nota.md"
    note_path.write_text(
        """---
title: Nota
---

# Nota

| `CLM-TESTE-PIPE-001` | Relação `A | B`. | `supported` | Fonte `C | D`; A | B. |
""",
        encoding="utf-8",
    )

    reader = CorpusReader(tmp_path)
    [claim] = reader.extract_claims(reader.read_note("Nota"))

    assert claim.statement == "Relação `A | B`."
    assert claim.status == "supported"
    assert claim.evidence == "Fonte `C | D`; A | B."
    assert claim.line == 7


def test_read_note_nao_escapa_do_corpus(
    corpus_dir: Path,
    repo_root: Path,
) -> None:
    reader = CorpusReader(corpus_dir)

    with pytest.raises(KeyError, match="não encontrada no corpus"):
        reader.read_note("../README.md")
    with pytest.raises(KeyError, match="não encontrada no corpus"):
        reader.read_note(repo_root / "README.md")


def test_todo_wikilink_resolve_e_declara_relacao(corpus_dir: Path) -> None:
    graph = CorpusReader(corpus_dir).build_graph()
    assert graph.graph["broken"] == []
    assert graph.graph["undeclared"] == []


def test_grafo_cobre_o_corpus_sem_no_fantasma(corpus_dir: Path) -> None:
    """As chaves do grafo são identidades por caminho, não nomes de arquivo."""
    reader = CorpusReader(corpus_dir)
    graph = reader.build_graph()
    assert graph.number_of_nodes() == BASELINE_NOTES
    assert set(graph.nodes) == {note.id for note in reader.list_notes()}
    # A identidade carrega o domínio: dois arquivos de mesmo nome em pastas
    # diferentes não podem mais colapsar num nó só.
    assert "Segurança/MOC — Segurança" in graph.nodes
    assert sum("/" in node for node in graph.nodes) == BASELINE_NOTES - 2


def test_identidade_carrega_o_dominio_e_nao_so_o_nome(corpus_dir: Path) -> None:
    for note in CorpusReader(corpus_dir).list_notes():
        assert note.id == note.path.as_posix().removesuffix(".md")
        if note.domain != "raiz":
            assert note.id.startswith(f"{note.domain}/")


def test_alias_resolve_para_a_nota(corpus_dir: Path) -> None:
    """Alias que repete o próprio nome da nota é legítimo — `Índice` faz isso."""
    reader = CorpusReader(corpus_dir)
    aliases = reader.alias_index()
    assert aliases, "o corpus usa aliases"
    ids = {note.id for note in reader.list_notes()}
    for alvos in aliases.values():
        # Nenhum alias do corpus atual é ambíguo, e todos apontam para nota real.
        assert len(alvos) == 1
        assert alvos[0] in ids


def test_auditor_concorda_com_o_leitor(corpus_dir: Path, repo_root: Path) -> None:
    """Roda o gate de verdade e compara as linhas de contagem com o leitor."""
    completed = subprocess.run(  # noqa: S603 — script do próprio repositório
        [sys.executable, str(repo_root / "tools" / "audit.py"), str(corpus_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    numbers = {}
    for line in completed.stdout.splitlines():
        if "." * 3 in line:
            label, _, value = line.partition(" ...")
            numbers[label.strip()] = value.strip(". ").split()[0]

    counts = build_projection(CorpusReader(corpus_dir))["meta"]["counts"]
    assert int(numbers["notas markdown"]) == counts["notes"]
    assert int(numbers["wikilinks"]) == counts["wikilinks"]
    assert int(numbers["linhas definidoras de claims"]) == counts["claims"]
