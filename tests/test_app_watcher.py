"""Fronteira HTTP entre a projeção viva e sua memória espacial."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message="Using `httpx` with `starlette.testclient` is deprecated.*",
    )
    from fastapi.testclient import TestClient

from vault.app import OPERATIONAL_LAYOUT_VERSION, app
from vault.config import get_settings

ALGORITHM_VERSION = "1"


def _nota(corpus: Path) -> None:
    corpus.mkdir(parents=True)
    (corpus / "Nota.md").write_text(
        "---\ntitle: Nota\nkind: nota\nepistemic_status: supported\n---\n\nCorpo.\n",
        encoding="utf-8",
    )


def test_put_de_layout_recusa_fingerprint_que_nao_e_o_vivo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpus = tmp_path / "knowledge"
    _nota(corpus)
    monkeypatch.setenv("VAULT_CORPUS_DIR", str(corpus))
    monkeypatch.setenv("VAULT_RUNTIME_DIR", str(tmp_path / "runtime"))
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            projection = client.get("/corpus/projection")
            assert projection.status_code == 200
            fingerprint = projection.json()["meta"]["corpusFingerprint"]
            body = {
                "algorithmVersion": ALGORITHM_VERSION,
                "positions": {"Nota": {"x": 1, "y": 2, "z": 3}},
            }

            stale = client.put(f"/layout/{'b' * 64}", json=body)
            assert stale.status_code == 409
            assert stale.json()["detail"] == (
                "impressão do layout não corresponde à projeção viva"
            )

            current = client.put(f"/layout/{fingerprint}", json=body)
            assert current.status_code == 200
            assert current.json()["stored"] == 1

            loaded = client.get(
                f"/layout/{fingerprint}",
                params={"algorithmVersion": ALGORITHM_VERSION},
            )
            assert loaded.status_code == 200
            assert loaded.json()["corpusFingerprint"] == fingerprint
            assert loaded.json()["algorithmVersion"] == ALGORITHM_VERSION
            assert loaded.json()["positions"] == {
                "Nota": {"x": 1.0, "y": 2.0, "z": 3.0, "pinned": False}
            }

            # Versão diferente não é erro de contrato: é ausência de memória para
            # aquela geometria. Enquanto isto respondia 422, subir a versão no frontend
            # derrubava a memória espacial inteira em silêncio.
            outra = client.get(
                f"/layout/{fingerprint}", params={"algorithmVersion": "2"}
            )
            assert outra.status_code == 200
            assert outra.json()["positions"] == {}

            # O que continua sendo recusado é vocabulário inválido, que é o que o store
            # declara e a API não tem por que reinterpretar.
            invalida = client.get(
                f"/layout/{fingerprint}", params={"algorithmVersion": "não/é/versão"}
            )
            assert invalida.status_code == 422

            # Congela o watcher na projeção aceita e muda somente o filesystem. O PUT
            # precisa podar pelo snapshot vivo, não por essa edição ainda não aceita.
            assert client.portal is not None
            client.portal.call(app.state.corpus_watcher.stop)
            (corpus / "Nota.md").unlink()
            while_disk_differs = client.put(f"/layout/{fingerprint}", json=body)
            assert while_disk_differs.status_code == 200
            assert while_disk_differs.json()["stored"] == 1
    finally:
        get_settings.cache_clear()


def test_slots_operacionais_tem_namespace_e_merge_proprios(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supported = str(OPERATIONAL_LAYOUT_VERSION)
    unsupported = str(OPERATIONAL_LAYOUT_VERSION + 1)
    corpus = tmp_path / "knowledge"
    _nota(corpus)
    monkeypatch.setenv("VAULT_CORPUS_DIR", str(corpus))
    monkeypatch.setenv("VAULT_RUNTIME_DIR", str(tmp_path / "runtime"))
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            first = client.put(
                f"/operational-layout/{supported}",
                json={"slots": {"painel-a": 0}},
            )
            assert first.status_code == 200
            assert first.json()["slots"] == {"painel-a": 0}

            collision = client.put(
                f"/operational-layout/{supported}",
                json={"slots": {"painel-a": 9, "painel-b": 0}},
            )
            assert collision.status_code == 200
            assert collision.json()["slots"] == {"painel-a": 0, "painel-b": 1}

            loaded = client.get(f"/operational-layout/{supported}")
            assert loaded.status_code == 200
            assert loaded.json()["algorithmVersion"] == OPERATIONAL_LAYOUT_VERSION
            assert loaded.json()["slots"] == {"painel-a": 0, "painel-b": 1}

            outra = client.get(f"/operational-layout/{unsupported}")
            assert outra.status_code == 200
            assert outra.json()["slots"] == {}

            nova = client.put(
                f"/operational-layout/{unsupported}",
                json={"slots": {"painel-c": 2}},
            )
            assert nova.status_code == 200
            assert nova.json()["slots"] == {"painel-c": 2}
    finally:
        get_settings.cache_clear()
