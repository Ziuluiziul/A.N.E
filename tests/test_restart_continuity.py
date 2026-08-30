"""Continuidade espacial através do reinício do backend.

O Ciclo 2 entregou a reconciliação certa para uma sessão viva: a transição vai de uma
impressão de origem declarada para uma de destino, e nunca procura o arquivo mais
recente por data. O que faltava era a origem **sobreviver ao encerramento do
processo** — sem isso, editar uma nota com o backend desligado apagava o mapa mental
inteiro, silenciosamente.

Cada teste aqui reinicia de verdade: constrói um watcher novo, com store novo, sobre o
mesmo diretório de runtime. Reaproveitar o objeto anterior testaria a memória do
processo, que nunca esteve em dúvida.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from vault.corpus.watcher import CorpusProjectionWatcher
from vault.layout_store import POINTER_NAME, LayoutStore, LayoutStoreError, Position

ALGORITMO = "teste-1"

NOTA = """---
title: {titulo}
kind: {kind}
epistemic_status: established
---

# {titulo}

{corpo}
"""


def escrever(
    raiz: Path, caminho: str, *, titulo: str, kind: str = "nota", corpo: str = ""
) -> None:
    destino = raiz / caminho
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(NOTA.format(titulo=titulo, kind=kind, corpo=corpo), encoding="utf-8")


@pytest.fixture
def ambiente(tmp_path: Path) -> tuple[Path, Path]:
    """Um corpus mínimo com um MOC e duas notas, mais o diretório de runtime."""
    corpus = tmp_path / "knowledge"
    escrever(
        corpus,
        "Física/MOC — Física.md",
        titulo="MOC — Física",
        kind="moc",
        corpo=(
            "- [[Entropia]] <!-- relation:navigation -->\n"
            "- [[Calor]] <!-- relation:navigation -->\n"
        ),
    )
    escrever(corpus, "Física/Entropia.md", titulo="Entropia")
    escrever(corpus, "Física/Calor.md", titulo="Calor")
    return corpus, tmp_path / "runtime"


def novo_watcher(ambiente: tuple[Path, Path]) -> CorpusProjectionWatcher:
    """Simula um processo novo: watcher e store reconstruídos sobre o mesmo disco."""
    corpus, runtime = ambiente
    return CorpusProjectionWatcher(corpus, LayoutStore(runtime / "layout"))


def posicoes_de(watcher: CorpusProjectionWatcher) -> dict[str, Position]:
    snapshot = watcher.layout_store.load(watcher.fingerprint or "", ALGORITMO)
    return dict(snapshot.positions) if snapshot else {}


async def semear(watcher: CorpusProjectionWatcher, **extra: tuple[float, float, float]) -> None:
    """Grava um layout para a impressão viva, como o frontend faria."""
    projecao = watcher.projection
    posicoes = {
        str(node["id"]): Position(float(indice) * 10, float(indice) * 5, 1.0)
        for indice, node in enumerate(projecao["nodes"])
    }
    posicoes.update({nome: Position(*valores) for nome, valores in extra.items()})
    await asyncio.to_thread(
        watcher.layout_store.save,
        watcher.fingerprint or "",
        posicoes,
        algorithm_version=ALGORITMO,
        known_ids=set(posicoes),
    )


# --- reinício sem alteração -------------------------------------------------


async def test_reinicio_sem_alteracao_preserva_todas_as_coordenadas(
    ambiente: tuple[Path, Path],
) -> None:
    primeiro = novo_watcher(ambiente)
    await primeiro.refresh()
    await semear(primeiro)
    antes = posicoes_de(primeiro)
    assert antes

    segundo = novo_watcher(ambiente)
    await segundo.refresh()

    assert segundo.fingerprint == primeiro.fingerprint
    assert posicoes_de(segundo) == antes


async def test_a_impressao_fica_anotada_no_disco(ambiente: tuple[Path, Path]) -> None:
    watcher = novo_watcher(ambiente)
    await watcher.refresh()
    assert watcher.layout_store.last_fingerprint() == watcher.fingerprint


# --- corpus alterado com o backend desligado --------------------------------


async def test_corpus_alterado_offline_preserva_entidades_anteriores(
    ambiente: tuple[Path, Path],
) -> None:
    """O caso que motivou o ciclo: sem o ponteiro, tudo isto seria recalculado."""
    corpus, _ = ambiente
    primeiro = novo_watcher(ambiente)
    await primeiro.refresh()
    await semear(primeiro, **{"Física/Entropia": (123.0, 456.0, 7.0)})
    impressao_antiga = primeiro.fingerprint
    antes = posicoes_de(primeiro)

    # Backend "desligado": nenhum watcher observa esta escrita.
    escrever(corpus, "Física/Pressão.md", titulo="Pressão")

    segundo = novo_watcher(ambiente)
    await segundo.refresh()

    assert segundo.fingerprint != impressao_antiga
    depois = posicoes_de(segundo)
    # Toda entidade que sobreviveu à edição atravessa com a coordenada exata.
    assert depois == antes
    assert depois["Física/Entropia"] == Position(123.0, 456.0, 7.0)


async def test_nota_nova_offline_recebe_somente_colocacao_local(
    ambiente: tuple[Path, Path],
) -> None:
    corpus, _ = ambiente
    primeiro = novo_watcher(ambiente)
    await primeiro.refresh()
    await semear(primeiro)
    antes = posicoes_de(primeiro)

    escrever(corpus, "Física/Pressão.md", titulo="Pressão")

    segundo = novo_watcher(ambiente)
    await segundo.refresh()
    depois = posicoes_de(segundo)

    # As conhecidas atravessam intactas; a nova ainda não tem posição gravada — quem
    # a coloca é o layout do frontend, localmente, sem mexer nas demais.
    for identidade, posicao in antes.items():
        assert depois[identidade] == posicao
    assert "Física/Pressão" not in depois


async def test_nota_removida_offline_desaparece_apos_reinicio(
    ambiente: tuple[Path, Path],
) -> None:
    corpus, _ = ambiente
    primeiro = novo_watcher(ambiente)
    await primeiro.refresh()
    await semear(primeiro)
    assert "Física/Calor" in posicoes_de(primeiro)

    (corpus / "Física" / "Calor.md").unlink()
    # O MOC deixaria de resolver o wikilink; removê-lo mantém o corpus íntegro.
    escrever(
        corpus,
        "Física/MOC — Física.md",
        titulo="MOC — Física",
        kind="moc",
        corpo="- [[Entropia]] <!-- relation:navigation -->\n",
    )

    segundo = novo_watcher(ambiente)
    await segundo.refresh()
    assert "Física/Calor" not in posicoes_de(segundo)
    assert "Física/Entropia" in posicoes_de(segundo)


# --- ponteiro ausente, corrompido ou órfão ----------------------------------


async def test_ponteiro_ausente_inicia_corretamente(ambiente: tuple[Path, Path]) -> None:
    watcher = novo_watcher(ambiente)
    assert watcher.layout_store.last_fingerprint() is None
    assert await watcher.refresh() is True
    assert watcher.projection["meta"]["counts"]["notes"] == 3


@pytest.mark.parametrize(
    ("nome", "conteudo"),
    [
        ("json inválido", b"{ nao e json"),
        ("truncado", b'{"schemaVersion": 1, "corpusFing'),
        ("vazio", b""),
        (
            "schema de outra versão",
            b'{"schemaVersion": 99, "corpusFingerprint": "' + b"a" * 64 + b'"}',
        ),
        (
            "impressão fora do formato",
            b'{"schemaVersion": 1, "corpusFingerprint": "nao-hexadecimal"}',
        ),
        ("impressão do tipo errado", b'{"schemaVersion": 1, "corpusFingerprint": 42}'),
    ],
)
async def test_ponteiro_corrompido_nao_impede_a_projecao(
    ambiente: tuple[Path, Path], nome: str, conteudo: bytes
) -> None:
    _, runtime = ambiente
    diretorio = runtime / "layout"
    diretorio.mkdir(parents=True, exist_ok=True)
    (diretorio / POINTER_NAME).write_bytes(conteudo)

    watcher = novo_watcher(ambiente)
    assert watcher.layout_store.last_fingerprint() is None, nome
    assert await watcher.refresh() is True, nome
    assert watcher.projection["meta"]["counts"]["notes"] == 3
    assert watcher.last_error is None


async def test_ponteiro_sem_layout_correspondente_nao_inventa_posicoes(
    ambiente: tuple[Path, Path],
) -> None:
    """Impressão anotada apontando para um layout que não existe: zero invenção."""
    _, runtime = ambiente
    store = LayoutStore(runtime / "layout")
    orfa = "b" * 64
    store.remember_fingerprint(orfa)
    assert store.load(orfa) is None

    watcher = novo_watcher(ambiente)
    await watcher.refresh()
    assert posicoes_de(watcher) == {}
    assert watcher.last_error is None


async def test_a_origem_nunca_vem_da_data_de_modificacao(ambiente: tuple[Path, Path]) -> None:
    """Um layout alheio e mais novo no disco não pode virar origem."""
    corpus, runtime = ambiente
    primeiro = novo_watcher(ambiente)
    await primeiro.refresh()
    await semear(primeiro, **{"Física/Entropia": (11.0, 22.0, 3.0)})

    # Snapshot de outro corpus, gravado depois — portanto o "mais recente" por data.
    intruso = "c" * 64
    primeiro.layout_store.save(
        intruso,
        {"Física/Entropia": Position(999.0, 999.0, 9.0)},
        algorithm_version=ALGORITMO,
    )

    escrever(corpus, "Física/Pressão.md", titulo="Pressão")
    segundo = novo_watcher(ambiente)
    await segundo.refresh()

    assert posicoes_de(segundo)["Física/Entropia"] == Position(11.0, 22.0, 3.0)


# --- concorrência -----------------------------------------------------------


async def test_dois_refresh_concorrentes_nao_intercalam(ambiente: tuple[Path, Path]) -> None:
    """Sem o lock, ambos veriam `fingerprint is None` e publicariam revisão própria."""
    watcher = novo_watcher(ambiente)
    resultados = await asyncio.gather(watcher.refresh(), watcher.refresh())

    assert sorted(resultados) == [False, True]
    assert watcher.revision == 1
    assert watcher.layout_store.last_fingerprint() == watcher.fingerprint


async def test_refresh_concorrente_apos_mudanca_publica_uma_revisao(
    ambiente: tuple[Path, Path],
) -> None:
    corpus, _ = ambiente
    watcher = novo_watcher(ambiente)
    await watcher.refresh()
    revisao = watcher.revision

    escrever(corpus, "Física/Pressão.md", titulo="Pressão")
    await asyncio.gather(watcher.refresh(), watcher.refresh(), watcher.refresh())
    assert watcher.revision == revisao + 1


# --- falha do store não governa o corpus ------------------------------------


async def test_falha_do_store_nao_bloqueia_a_verdade_do_corpus(
    ambiente: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    watcher = novo_watcher(ambiente)

    def explode(*_args: object, **_kwargs: object) -> None:
        raise LayoutStoreError("disco cheio")

    monkeypatch.setattr(watcher.layout_store, "remember_fingerprint", explode)
    monkeypatch.setattr(watcher.layout_store, "carry_forward", explode)

    assert await watcher.refresh() is True
    assert watcher.projection["meta"]["counts"]["notes"] == 3
    # A falha fica visível, mas não decide qual versão do corpus a API serve.
    assert watcher.last_error is not None
    assert "não anotada" in watcher.last_error or "não reconciliada" in watcher.last_error


async def test_ponteiro_recusa_impressao_invalida(ambiente: tuple[Path, Path]) -> None:
    _, runtime = ambiente
    store = LayoutStore(runtime / "layout")
    with pytest.raises(LayoutStoreError, match="impressão digital inválida"):
        store.remember_fingerprint("../../etc/passwd")
    assert not (store.directory / POINTER_NAME).exists()


async def test_ponteiro_tem_schema_versionado(ambiente: tuple[Path, Path]) -> None:
    _, runtime = ambiente
    store = LayoutStore(runtime / "layout")
    store.remember_fingerprint("d" * 64)
    gravado = json.loads((store.directory / POINTER_NAME).read_text(encoding="utf-8"))
    assert gravado["schemaVersion"] == 1
    assert gravado["corpusFingerprint"] == "d" * 64
    assert gravado["updatedAt"]


async def test_o_ponteiro_nao_deixa_temporario_para_tras(ambiente: tuple[Path, Path]) -> None:
    _, runtime = ambiente
    store = LayoutStore(runtime / "layout")
    store.remember_fingerprint("e" * 64)
    store.remember_fingerprint("f" * 64)
    assert sorted(p.name for p in store.directory.iterdir()) == [POINTER_NAME]


# --- o corpus não é tocado --------------------------------------------------


async def test_knowledge_permanece_byte_a_byte_intacto(ambiente: tuple[Path, Path]) -> None:
    corpus, _ = ambiente

    def digerir() -> str:
        digest = hashlib.sha256()
        for caminho in sorted(corpus.rglob("*.md")):
            digest.update(caminho.relative_to(corpus).as_posix().encode())
            digest.update(caminho.read_bytes())
        return digest.hexdigest()

    antes = digerir()
    primeiro = novo_watcher(ambiente)
    await primeiro.refresh()
    await semear(primeiro)
    segundo = novo_watcher(ambiente)
    await segundo.refresh()
    assert digerir() == antes


async def test_o_corpus_real_tambem_nao_e_tocado(corpus_dir: Path, tmp_path: Path) -> None:
    """O mesmo, agora contra knowledge/ de verdade, e sem escrever nele."""
    from vault.corpus import CorpusReader
    from vault.projection import corpus_fingerprint

    antes = corpus_fingerprint(CorpusReader(corpus_dir))
    watcher = CorpusProjectionWatcher(corpus_dir, LayoutStore(tmp_path / "layout"))
    await watcher.refresh()
    assert watcher.fingerprint == antes
    assert corpus_fingerprint(CorpusReader(corpus_dir)) == antes
