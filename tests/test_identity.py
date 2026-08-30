"""Identidade e resolução de wikilinks.

O corpus de hoje não tem nenhuma dessas patologias — nem nome repetido, nem título
duplicado, nem alias colidindo, nem caminho fora de NFC. É justamente por isso que
os testes usam corpora sintéticos: a defesa precisa existir antes do defeito, senão
a primeira nota que colidir vai colidir em silêncio.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

from vault.corpus import CorpusReader
from vault.corpus.identity import (
    CorpusIdentityError,
    CorpusIndex,
    IndexedNote,
    domain_slug,
    fold,
    nfc,
    note_id,
    split_target,
)

FRONTMATTER = """---
title: {titulo}
kind: nota
epistemic_status: established
{extra}---

# {titulo}

{corpo}
"""


def escrever(
    raiz: Path, caminho: str, *, titulo: str, aliases: str = "", corpo: str = ""
) -> Path:
    destino = raiz / caminho
    destino.parent.mkdir(parents=True, exist_ok=True)
    extra = f"aliases: [{aliases}]\n" if aliases else ""
    destino.write_text(
        FRONTMATTER.format(titulo=titulo, extra=extra, corpo=corpo), encoding="utf-8"
    )
    return destino


# --- normalização ----------------------------------------------------------


def test_id_vem_do_caminho_relativo_sem_extensao() -> None:
    assert note_id("Física/Entropia.md") == "Física/Entropia"
    assert note_id("Índice.md") == "Índice"
    assert note_id("a/b/c.md") == "a/b/c"


def test_id_normaliza_para_nfc() -> None:
    """`Fisica` acentuado, decomposto e composto, e o mesmo nome para um humano.

    As duas formas sao construidas em tempo de execucao: escreve-las no arquivo-fonte
    faria o teste depender de bytes invisiveis que qualquer editor pode normalizar.
    """
    composto = unicodedata.normalize("NFC", "F\u00edsica/Entropia.md")
    decomposto = unicodedata.normalize("NFD", composto)
    assert decomposto != composto, "as duas formas precisam diferir em bytes"
    assert note_id(decomposto) == note_id(composto) == composto.removesuffix(".md")


def test_fold_ignora_caixa_e_acento() -> None:
    assert fold("Estatística") == fold("ESTATISTICA")
    assert fold("Índice") == "indice"


def test_domain_slug_e_estavel_e_sem_acento() -> None:
    assert domain_slug("Ciências da Vida") == "ciencias-da-vida"
    assert domain_slug("Física") == "fisica"
    assert domain_slug("raiz") == "raiz"


def test_split_target_separa_fragmento() -> None:
    assert split_target("Nota") == ("Nota", None)
    assert split_target("Nota#Seção") == ("Nota", "Seção")
    assert split_target("#Só o fragmento") == ("", "Só o fragmento")


# --- colisão de identidade -------------------------------------------------


def test_mesmo_nome_em_dominios_diferentes_nao_se_sobrescreve(tmp_path: Path) -> None:
    """A patologia que a identidade por caminho elimina de vez."""
    escrever(tmp_path, "Física/Entropia.md", titulo="Entropia física")
    escrever(tmp_path, "Dados/Entropia.md", titulo="Entropia informacional")

    notes = CorpusReader(tmp_path).list_notes()
    assert {n.id for n in notes} == {"Física/Entropia", "Dados/Entropia"}
    assert len({n.title for n in notes}) == 2


def test_colisao_por_normalizacao_unicode_reprova() -> None:
    """Dois arquivos que so diferem em NFC/NFD seriam a mesma nota. Isso e erro."""
    composto = unicodedata.normalize("NFC", "A\u00e7ao.md")
    decomposto = unicodedata.normalize("NFD", composto)
    assert composto != decomposto
    notas = [
        IndexedNote(id=note_id(composto), relative_path=composto, stem="a", title="a"),
        IndexedNote(id=note_id(decomposto), relative_path=decomposto, stem="b", title="b"),
    ]
    with pytest.raises(CorpusIdentityError, match="colidem na mesma identidade"):
        CorpusIndex.build(notas)


def test_colisao_de_nome_e_registrada_sem_reprovar_sozinha(tmp_path: Path) -> None:
    """Dois arquivos de mesmo nome só viram defeito quando um link precisa escolher."""
    escrever(tmp_path, "Física/Entropia.md", titulo="Entropia física")
    escrever(tmp_path, "Dados/Entropia.md", titulo="Entropia informacional")

    graph = CorpusReader(tmp_path).build_graph()
    assert graph.graph["collisions"]["filename"] == {
        "Entropia": ["Dados/Entropia", "Física/Entropia"]
    }


# --- resolução -------------------------------------------------------------


def indice(*notas: IndexedNote) -> CorpusIndex:
    return CorpusIndex.build(list(notas))


NOTA_A = IndexedNote(
    id="Física/Entropia", relative_path="Física/Entropia.md", stem="Entropia", title="Entropia"
)
NOTA_B = IndexedNote(
    id="Dados/Entropia",
    relative_path="Dados/Entropia.md",
    stem="Entropia",
    title="Entropia de Shannon",
    aliases=("Shannon",),
)
NOTA_C = IndexedNote(
    id="Física/Calor", relative_path="Física/Calor.md", stem="Calor", title="Calor"
)


def test_precedencia_id_vence_nome() -> None:
    resolucao = indice(NOTA_A, NOTA_B).resolve("Física/Entropia", source_id="Física/Calor")
    assert (resolucao.target_id, resolucao.matched_by) == ("Física/Entropia", "id")


def test_caminho_relativo_resolve_a_partir_da_nota_de_origem() -> None:
    resolucao = indice(NOTA_A, NOTA_C).resolve("Entropia", source_id="Física/Calor")
    assert (resolucao.target_id, resolucao.matched_by) == ("Física/Entropia", "relative-path")


def test_nome_de_arquivo_unico_resolve() -> None:
    resolucao = indice(NOTA_A, NOTA_C).resolve("Calor", source_id="Índice")
    assert (resolucao.target_id, resolucao.matched_by) == ("Física/Calor", "filename")


def test_titulo_unico_resolve() -> None:
    resolucao = indice(NOTA_A, NOTA_B).resolve("Entropia de Shannon", source_id="Índice")
    assert (resolucao.target_id, resolucao.matched_by) == ("Dados/Entropia", "title")


def test_alias_unico_resolve() -> None:
    resolucao = indice(NOTA_A, NOTA_B).resolve("Shannon", source_id="Índice")
    assert (resolucao.target_id, resolucao.matched_by) == ("Dados/Entropia", "alias")


def test_variacao_de_caixa_e_acento_resolve_por_ultimo() -> None:
    resolucao = indice(NOTA_C).resolve("calor", source_id="Índice")
    assert (resolucao.target_id, resolucao.matched_by) == ("Física/Calor", "folded-filename")


def test_nome_ambiguo_nao_escolhe_ninguem() -> None:
    """O ponto do exercício: dois candidatos produzem zero escolhas."""
    resolucao = indice(NOTA_A, NOTA_B).resolve("Entropia", source_id="Índice")
    assert resolucao.target_id is None
    assert resolucao.ambiguous
    assert resolucao.candidates == ("Dados/Entropia", "Física/Entropia")


def test_ambiguidade_nao_desce_para_um_criterio_mais_frouxo() -> None:
    """Descer esconderia a ambiguidade atrás de um casamento por título."""
    resolucao = indice(NOTA_A, NOTA_B).resolve("Entropia", source_id="Índice")
    assert resolucao.matched_by == "filename"


def test_alvo_inexistente_fica_sem_resolucao() -> None:
    resolucao = indice(NOTA_A).resolve("Nota Que Não Existe", source_id="Índice")
    assert not resolucao.resolved
    assert not resolucao.ambiguous
    assert resolucao.matched_by == "unresolved"


def test_fragmento_nao_muda_a_nota_de_destino() -> None:
    resolucao = indice(NOTA_C).resolve("Calor#Segunda lei", source_id="Índice")
    assert resolucao.target_id == "Física/Calor"
    assert resolucao.fragment == "Segunda lei"


def test_fragmento_sozinho_aponta_para_a_propria_nota() -> None:
    resolucao = indice(NOTA_C).resolve("#Segunda lei", source_id="Física/Calor")
    assert (resolucao.target_id, resolucao.matched_by) == ("Física/Calor", "self")


def test_texto_de_exibicao_nao_chega_ao_resolvedor(tmp_path: Path) -> None:
    """O `|` é apresentação: `[[Nota|assim se lê]]` resolve para `Nota`."""
    escrever(tmp_path, "Física/Calor.md", titulo="Calor")
    escrever(
        tmp_path,
        "Índice.md",
        titulo="Índice",
        corpo="Ver [[Calor|o calor]] <!-- relation:navigation -->",
    )
    reader = CorpusReader(tmp_path)
    [link] = reader.extract_links(reader.read_note("Índice"))
    assert link.target == "Calor"


# --- ambiguidade reprova a projeção ----------------------------------------


def test_link_ambiguo_reprova_a_construcao_do_grafo(tmp_path: Path) -> None:
    escrever(tmp_path, "Física/Entropia.md", titulo="Entropia física")
    escrever(tmp_path, "Dados/Entropia.md", titulo="Entropia informacional")
    escrever(
        tmp_path,
        "Índice.md",
        titulo="Índice",
        corpo="Ver [[Entropia]] <!-- relation:navigation -->",
    )

    with pytest.raises(CorpusIdentityError, match="ambíguo"):
        CorpusReader(tmp_path).build_graph()


def test_diagnostico_da_ambiguidade_lista_os_candidatos(tmp_path: Path) -> None:
    escrever(tmp_path, "Física/Entropia.md", titulo="Entropia física")
    escrever(tmp_path, "Dados/Entropia.md", titulo="Entropia informacional")
    escrever(
        tmp_path,
        "Índice.md",
        titulo="Índice",
        corpo="Ver [[Entropia]] <!-- relation:navigation -->",
    )

    with pytest.raises(CorpusIdentityError) as excinfo:
        CorpusReader(tmp_path).build_graph()
    mensagem = str(excinfo.value)
    assert "Dados/Entropia" in mensagem
    assert "Física/Entropia" in mensagem
    assert "filename" in mensagem


# --- escopo de ingestão ----------------------------------------------------


def test_symlink_que_sai_do_corpus_reprova(tmp_path: Path) -> None:
    fora = tmp_path / "fora"
    fora.mkdir()
    (fora / "Intrusa.md").write_text("---\ntitle: Intrusa\n---\n\ntexto\n", encoding="utf-8")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    escrever(corpus, "Física/Calor.md", titulo="Calor")
    (corpus / "atalho.md").symlink_to(fora / "Intrusa.md")

    with pytest.raises(CorpusIdentityError, match="symlink sai do corpus"):
        CorpusReader(corpus).list_notes()


def test_so_markdown_sob_a_raiz_entra(tmp_path: Path) -> None:
    escrever(tmp_path, "Física/Calor.md", titulo="Calor")
    (tmp_path / "notas.txt").write_text("não é markdown", encoding="utf-8")
    (tmp_path / "README.md").write_text("---\ntitle: leia\n---\n", encoding="utf-8")
    (tmp_path / "runtime").mkdir()
    (tmp_path / "runtime" / "proposta.md").write_text("---\ntitle: p\n---\n", encoding="utf-8")

    ids = {note.id for note in CorpusReader(tmp_path).list_notes()}
    assert ids == {"Física/Calor"}


def test_raiz_inexistente_reprova_na_construcao(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="corpus não encontrado"):
        CorpusReader(tmp_path / "nao-existe")


def test_nfc_e_idempotente() -> None:
    assert nfc(nfc("Física")) == nfc("Física")
