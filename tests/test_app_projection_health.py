"""GET pesados não podem silenciar /health.

O overlay de quórum e o snapshot de controle são trabalho síncrono. Sem thread
+ health no event loop, um GET lento deixava a porta aceitando TCP e não
respondendo HTTP — medido ao vivo em 2026-08-31 com o Atlas aberto.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from vault.app import app
from vault.config import get_settings
from vault.control.snapshot import clear_control_snapshot_cache
from vault.projection import clear_runtime_overlay_cache


def _nota(corpus: Path) -> None:
    corpus.mkdir(parents=True)
    (corpus / "Nota.md").write_text(
        "---\ntitle: Nota\nkind: nota\nepistemic_status: supported\n---\n\nCorpo.\n",
        encoding="utf-8",
    )


@pytest.fixture
def api_isolada(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    corpus = tmp_path / "knowledge"
    _nota(corpus)
    monkeypatch.setenv("VAULT_CORPUS_DIR", str(corpus))
    monkeypatch.setenv("VAULT_RUNTIME_DIR", str(tmp_path / "runtime"))
    get_settings.cache_clear()
    clear_runtime_overlay_cache()
    clear_control_snapshot_cache()
    yield
    get_settings.cache_clear()
    clear_runtime_overlay_cache()
    clear_control_snapshot_cache()


async def test_health_responde_com_projection_lenta_em_voo(
    api_isolada: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def lento(
        projection: dict[str, Any],
        quorum_root: Path,
        state_dir: Path | None = None,
    ) -> dict[str, Any]:
        time.sleep(1.2)
        return projection

    monkeypatch.setattr("vault.app.with_runtime_quorum", lento)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        projection = asyncio.create_task(client.get("/corpus/projection"))
        await asyncio.sleep(0.2)
        inicio = time.perf_counter()
        health = await client.get("/health")
        decorrido = time.perf_counter() - inicio
        assert health.status_code == 200
        assert "version" in health.json()
        assert decorrido < 0.4
        resposta = await projection
        assert resposta.status_code == 200


async def test_health_responde_com_snapshot_de_controle_lento(
    api_isolada: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vault.control.models import ControlSnapshot
    from vault.control.snapshot import build_snapshot as original

    def lento(settings: Any, preferences: Any) -> ControlSnapshot:
        time.sleep(1.2)
        return original(settings, preferences)

    monkeypatch.setattr("vault.control.routes.build_snapshot", lento)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        snapshot = asyncio.create_task(client.get("/api/control/snapshot"))
        await asyncio.sleep(0.2)
        inicio = time.perf_counter()
        health = await client.get("/health")
        decorrido = time.perf_counter() - inicio
        notes = await client.get("/corpus/notes")
        proposals = await client.get("/proposals")
        layout = await client.get("/operational-layout/6")
        assert health.status_code == 200
        assert "version" in health.json()
        assert decorrido < 0.4
        assert notes.status_code == 200
        assert proposals.status_code == 200
        assert layout.status_code == 200
        resposta = await snapshot
        assert resposta.status_code == 200


async def test_health_responde_com_documento_lento(
    api_isolada: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def lento(ref: str) -> dict[str, Any]:
        time.sleep(1.2)
        return {"id": ref, "title": "Nota", "path": "Nota.md", "body": "Corpo."}

    monkeypatch.setattr("vault.app._read_document_payload", lento)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        documento = asyncio.create_task(client.get("/corpus/documents/Nota"))
        await asyncio.sleep(0.2)
        inicio = time.perf_counter()
        health = await client.get("/health")
        nota = await client.get("/corpus/notes/Nota")
        decorrido = time.perf_counter() - inicio
        assert health.status_code == 200
        assert nota.status_code == 200
        assert decorrido < 0.4
        resposta = await documento
        assert resposta.status_code == 200
