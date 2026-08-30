"""A fronteira entre a versão que o frontend declara e a que a API aceita.

Nenhum teste atravessava esta linha, e foi exatamente por aí que passou o defeito: o
frontend subiu `LAYOUT_ALGORITHM_VERSION` de 1 para 2, a API continuou fixa em
`Literal["1"]`, e a memória espacial do corpus morreu em silêncio — `GET` e `PUT`
respondendo 422 durante seis commits, com o cliente tratando erro como "não havia nada
gravado". As duas suítes ficaram verdes o tempo todo, cada uma prendendo o seu lado.

A versão é lida do próprio fonte do frontend. É acoplamento declarado, e é menos frágil
que a alternativa: duplicar a constante num terceiro lugar só adiaria a divergência.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import pytest

with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message="Using `httpx` with `starlette.testclient` is deprecated.*",
    )
    from fastapi.testclient import TestClient

from vault.app import app
from vault.config import get_settings

FONTE = Path(__file__).resolve().parents[1] / "frontend" / "src" / "layoutStore.ts"


def versao_declarada_pelo_frontend() -> str:
    achado = re.search(
        r"export const LAYOUT_ALGORITHM_VERSION = '([^']+)'", FONTE.read_text("utf-8")
    )
    assert achado is not None, "LAYOUT_ALGORITHM_VERSION sumiu de layoutStore.ts"
    return achado.group(1)


def test_a_versao_que_o_frontend_manda_atravessa_a_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Corpus e runtime próprios: um teste de contrato não pode gravar por cima da
    # memória espacial real — e escreveria, porque o PUT vale para a impressão viva.
    corpus = tmp_path / "knowledge"
    corpus.mkdir(parents=True)
    (corpus / "Nota.md").write_text(
        "---\ntitle: Nota\nkind: nota\nepistemic_status: supported\n---\n\nCorpo.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("VAULT_CORPUS_DIR", str(corpus))
    monkeypatch.setenv("VAULT_RUNTIME_DIR", str(tmp_path / "runtime"))
    get_settings.cache_clear()

    versao = versao_declarada_pelo_frontend()
    try:
        with TestClient(app) as client:
            fingerprint = client.get("/corpus/projection").json()["meta"][
                "corpusFingerprint"
            ]

            gravada = client.put(
                f"/layout/{fingerprint}",
                json={
                    "algorithmVersion": versao,
                    "positions": {"Nota": {"x": 1, "y": 2, "z": 3}},
                },
            )
            assert gravada.status_code == 200, (
                f"a API recusou gravar sob a versão {versao!r} que o frontend declara; "
                "é assim que a memória espacial morre sem ninguém ver"
            )

            lida = client.get(
                f"/layout/{fingerprint}", params={"algorithmVersion": versao}
            )
            assert lida.status_code == 200
            assert lida.json()["algorithmVersion"] == versao
            assert lida.json()["positions"]["Nota"]["x"] == 1.0
    finally:
        get_settings.cache_clear()
