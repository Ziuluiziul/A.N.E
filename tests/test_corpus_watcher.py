"""Watcher: evento de disco só vira revisão depois de uma projeção válida."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from vault.corpus.watcher import CorpusProjectionWatcher
from vault.layout_store import LayoutStore, Position

ALGORITMO = "teste-1"


def escrever_nota(
    corpus: Path,
    relative: str,
    *,
    kind: str = "nota",
    title: str | None = None,
) -> Path:
    path = corpus / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "---",
                f"title: {title or path.stem}",
                f"kind: {kind}",
                "epistemic_status: supported",
                "---",
                "",
                "Conteúdo completo para o fixture isolado.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def watcher_em(corpus: Path, runtime: Path) -> CorpusProjectionWatcher:
    return CorpusProjectionWatcher(corpus, LayoutStore(runtime / "layout"))


async def test_touch_nao_muda_impressao_revisao_nem_chave_de_layout(tmp_path: Path) -> None:
    corpus = tmp_path / "knowledge"
    moc = escrever_nota(corpus, "Física/MOC — Física.md", kind="moc")
    escrever_nota(corpus, "Física/Antiga.md")
    watcher = watcher_em(corpus, tmp_path / "runtime")

    assert await watcher.refresh() is True
    fingerprint = watcher.fingerprint
    revision = watcher.revision
    projection = watcher.projection
    assert fingerprint is not None
    watcher.layout_store.save(
        fingerprint,
        {"Física/Antiga": Position(1, 2, 3)},
        algorithm_version=ALGORITMO,
    )
    arquivos_antes = sorted(path.name for path in watcher.layout_store.directory.iterdir())

    moc.touch()

    assert await watcher.refresh() is False
    assert watcher.fingerprint == fingerprint
    assert watcher.revision == revision
    assert watcher.projection is projection
    arquivos_depois = sorted(path.name for path in watcher.layout_store.directory.iterdir())
    assert arquivos_depois == arquivos_antes


async def test_erro_nao_expoe_caminho_absoluto_do_corpus(tmp_path: Path) -> None:
    corpus = tmp_path / "knowledge-ainda-ausente"
    watcher = watcher_em(corpus, tmp_path / "runtime")

    assert await watcher.refresh() is False
    assert watcher.last_error is not None
    assert str(tmp_path) not in watcher.last_error


async def test_nota_nova_recebe_projecao_e_carrega_todas_as_posicoes_antigas(
    tmp_path: Path,
) -> None:
    corpus = tmp_path / "knowledge"
    escrever_nota(corpus, "Física/MOC — Física.md", kind="moc")
    escrever_nota(corpus, "Física/Antiga.md")
    watcher = watcher_em(corpus, tmp_path / "runtime")
    assert await watcher.refresh() is True
    old_fingerprint = watcher.fingerprint
    assert old_fingerprint is not None
    antigas = {
        "Física/MOC — Física": Position(64, 0, 4),
        "Física/Antiga": Position(61, 3, 2),
    }
    watcher.layout_store.save(old_fingerprint, antigas, algorithm_version=ALGORITMO)

    escrever_nota(corpus, "Física/Nova.md")

    assert await watcher.refresh() is True
    new_fingerprint = watcher.fingerprint
    assert new_fingerprint is not None and new_fingerprint != old_fingerprint
    assert {node["id"] for node in watcher.projection["nodes"]} == {
        "Física/Antiga",
        "Física/MOC — Física",
        "Física/Nova",
    }
    carregadas = watcher.layout_store.load(new_fingerprint, ALGORITMO)
    assert carregadas is not None
    assert carregadas.positions == antigas


async def test_nota_removida_some_da_projecao_e_do_layout_novo(tmp_path: Path) -> None:
    corpus = tmp_path / "knowledge"
    escrever_nota(corpus, "Física/MOC — Física.md", kind="moc")
    escrever_nota(corpus, "Física/Fica.md")
    removida = escrever_nota(corpus, "Física/Removida.md")
    watcher = watcher_em(corpus, tmp_path / "runtime")
    assert await watcher.refresh() is True
    old_fingerprint = watcher.fingerprint
    assert old_fingerprint is not None
    watcher.layout_store.save(
        old_fingerprint,
        {
            "Física/MOC — Física": Position(64, 0, 4),
            "Física/Fica": Position(61, 3, 2),
            "Física/Removida": Position(60, 4, 1),
        },
        algorithm_version=ALGORITMO,
    )

    removida.unlink()

    assert await watcher.refresh() is True
    new_fingerprint = watcher.fingerprint
    assert new_fingerprint is not None
    assert "Física/Removida" not in {node["id"] for node in watcher.projection["nodes"]}
    carregadas = watcher.layout_store.load(new_fingerprint, ALGORITMO)
    assert carregadas is not None
    assert set(carregadas.positions) == {"Física/MOC — Física", "Física/Fica"}


async def test_falha_da_memoria_nao_bloqueia_projecao_valida(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpus = tmp_path / "knowledge"
    escrever_nota(corpus, "Física/Antiga.md")
    watcher = watcher_em(corpus, tmp_path / "runtime")
    assert await watcher.refresh() is True
    old_fingerprint = watcher.fingerprint
    events = watcher.events()
    assert (await anext(events)).kind == "current"

    def falhar_reconciliacao(*_args, **_kwargs) -> None:
        raise PermissionError("caminho privado que não pode chegar ao SSE")

    monkeypatch.setattr(watcher.layout_store, "carry_forward", falhar_reconciliacao)
    escrever_nota(corpus, "Física/Nova.md")

    assert await watcher.refresh() is True
    assert watcher.fingerprint != old_fingerprint
    assert "Física/Nova" in {node["id"] for node in watcher.projection["nodes"]}
    changed = await asyncio.wait_for(anext(events), timeout=1)
    error = await asyncio.wait_for(anext(events), timeout=1)
    assert changed.kind == "changed"
    assert error.kind == "error"
    assert error.fingerprint == watcher.fingerprint
    assert error.detail is not None and "memória espacial não reconciliada" in error.detail
    assert "caminho privado" not in error.detail
    memory_error = watcher.last_error
    assert await watcher.refresh() is False
    assert watcher.last_error == memory_error
    await events.aclose()


async def test_erro_e_publicado_sem_substituir_ultima_projecao_valida(tmp_path: Path) -> None:
    corpus = tmp_path / "knowledge"
    nota = escrever_nota(corpus, "Física/Antiga.md")
    watcher = watcher_em(corpus, tmp_path / "runtime")
    assert await watcher.refresh() is True
    projection = watcher.projection
    fingerprint = watcher.fingerprint

    events = watcher.events()
    current = await anext(events)
    assert current.kind == "current"
    assert current.fingerprint == fingerprint

    escrever_nota(corpus, "Física/Antiga.md", kind="artefato-desconhecido")
    assert await watcher.refresh() is False
    error = await asyncio.wait_for(anext(events), timeout=1)
    assert error.kind == "error"
    assert error.fingerprint == fingerprint
    assert error.detail is not None and "fora do vocabulário" in error.detail
    assert watcher.projection is projection

    escrever_nota(corpus, "Física/Antiga.md", title="Antiga corrigida")
    assert await watcher.refresh() is True
    changed = await asyncio.wait_for(anext(events), timeout=1)
    assert changed.kind == "changed"
    assert changed.fingerprint == watcher.fingerprint
    assert changed.fingerprint != fingerprint
    await events.aclose()
    assert nota.is_file()


async def test_reversao_exata_de_edicao_invalida_emite_recuperacao(tmp_path: Path) -> None:
    corpus = tmp_path / "knowledge"
    nota = escrever_nota(corpus, "Física/Antiga.md")
    original = nota.read_bytes()
    watcher = watcher_em(corpus, tmp_path / "runtime")
    assert await watcher.refresh() is True
    events = watcher.events()
    assert (await anext(events)).kind == "current"

    escrever_nota(corpus, "Física/Antiga.md", kind="artefato-desconhecido")
    assert await watcher.refresh() is False
    assert (await anext(events)).kind == "error"

    nota.write_bytes(original)
    assert await watcher.refresh() is False
    recovered = await anext(events)
    assert recovered.kind == "recovered"
    assert recovered.fingerprint == watcher.fingerprint
    assert recovered.detail is not None and "válido novamente" in recovered.detail
    await events.aclose()


async def test_servico_awatch_observa_mudanca_e_encerra_limpo(tmp_path: Path) -> None:
    corpus = tmp_path / "knowledge"
    escrever_nota(corpus, "Física/Antiga.md")
    watcher = watcher_em(corpus, tmp_path / "runtime")
    await watcher.start()
    events = watcher.events()
    try:
        current = await anext(events)
        assert current.kind == "current"
        await asyncio.sleep(0.1)  # deixa o observador nativo entrar na espera

        escrever_nota(corpus, "Física/Nova.md")

        changed = await asyncio.wait_for(anext(events), timeout=3)
        assert changed.kind == "changed"
        assert changed.fingerprint == watcher.fingerprint
        assert {node["id"] for node in watcher.projection["nodes"]} == {
            "Física/Antiga",
            "Física/Nova",
        }
    finally:
        await events.aclose()
        await watcher.stop()
