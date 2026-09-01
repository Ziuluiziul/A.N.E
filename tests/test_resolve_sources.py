"""Resolvedor de identificadores: extração, matching e HTTP mockado."""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from pathlib import Path
from urllib.error import URLError

import pytest

from tools import resolve_sources as rs
from vault.promotion.patch import identifiers_in as patch_identifiers

LINHA_DOI = (
    '- Amos Tversky e Daniel Kahneman. "Judgment under Uncertainty: Heuristics '
    'and Biases". *Science* 185(4157), 1124–1131 (1974). DOI `10.1126/science.185.4157.1124`.'
)
LINHA_ISBN = (
    "- Sanjeev Arora e Boaz Barak. *Computational Complexity: A Modern Approach*. "
    "Cambridge University Press, 2009. ISBN 978-0-521-42426-4."
)
LINHA_ARXIV = (
    "Wentao Ge et al., “MLLM-Bench: Evaluating Multimodal LLMs with Per-sample "
    "Criteria”, *NAACL 2025*, arXiv:`2311.13951`."
)
OURO_ISBN = "9780226618654"


class _FakeResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_extracao_bate_com_o_promoter() -> None:
    bloco = "\n".join((LINHA_DOI, LINHA_ISBN, LINHA_ARXIV))
    assert rs.identifiers_in(bloco) == patch_identifiers(bloco)
    assert rs.identifiers_in(bloco) == {
        "doi:10.1126/science.185.4157.1124",
        "isbn:9780521424264",
        "arxiv:2311.13951",
    }


def test_titulo_local_aspas_e_italico() -> None:
    assert rs.extract_title(LINHA_DOI) == "Judgment under Uncertainty: Heuristics and Biases"
    assert rs.extract_title(LINHA_ISBN) == "Computational Complexity: A Modern Approach"
    assert (
        rs.extract_title(LINHA_ARXIV)
        == "MLLM-Bench: Evaluating Multimodal LLMs with Per-sample Criteria"
    )


def test_matching_so_normaliza_caixa_unicode_pontuacao() -> None:
    assert rs.titles_match(
        "Judgment under Uncertainty: Heuristics and Biases",
        "Judgment under Uncertainty: Heuristics and Biases",
    )
    assert rs.titles_match(
        "Theory and Reality",
        "Theory and Reality: An Introduction to the Philosophy of Science, Second Edition",
    )
    assert not rs.titles_match(
        "Judgment under Uncertainty: Heuristics and Biases",
        "Estimating the reproducibility of psychological science",
    )


def test_collect_varre_linha_a_linha(tmp_path: Path) -> None:
    nota = tmp_path / "Física"
    nota.mkdir()
    (nota / "Nota.md").write_text(LINHA_DOI + "\n" + LINHA_ISBN + "\n", encoding="utf-8")
    ocorrencias = rs.collect(tmp_path)
    assert [item.key for item in ocorrencias] == [
        "doi:10.1126/science.185.4157.1124",
        "isbn:9780521424264",
    ]
    assert ocorrencias[0].path == "Física/Nota.md"
    assert ocorrencias[0].line == 1
    assert ocorrencias[0].local_title is not None


def test_offline_sem_cache_e_skip_nao_reprova(tmp_path: Path) -> None:
    (tmp_path / "Nota.md").write_text(LINHA_DOI + "\n", encoding="utf-8")
    cache_path = tmp_path / "sources.json"
    codigo = rs.main(
        [
            "--corpus",
            str(tmp_path),
            "--cache",
            str(cache_path),
            "--offline",
            "--no-pause",
        ]
    )
    assert codigo == 0
    assert not cache_path.exists()


def test_crossref_ok_e_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "Nota.md").write_text(LINHA_DOI + "\n", encoding="utf-8")
    respostas: list[tuple[str, int, bytes]] = []

    def fake_urlopen(pedido: object, timeout: float = 0) -> _FakeResponse:
        url = getattr(pedido, "full_url", str(pedido))
        respostas.append((url, 200, b""))
        corpo = json.dumps(
            {
                "message": {
                    "title": ["Judgment under Uncertainty: Heuristics and Biases"],
                    "DOI": "10.1126/science.185.4157.1124",
                }
            }
        ).encode()
        return _FakeResponse(200, corpo)

    monkeypatch.setattr(rs.urllib.request, "urlopen", fake_urlopen)
    ocorrencias = rs.collect(tmp_path)
    vereditos = rs.resolve_all(
        ocorrencias, cache={"entries": {}}, offline=False, refresh=True, pause=False
    )
    assert vereditos[0].status == "ok"
    assert "api.crossref.org/works/" in respostas[0][0]

    def fake_errado(pedido: object, timeout: float = 0) -> _FakeResponse:
        corpo = json.dumps({"message": {"title": ["Outro artigo"]}}).encode()
        return _FakeResponse(200, corpo)

    monkeypatch.setattr(rs.urllib.request, "urlopen", fake_errado)
    errados = rs.resolve_all(
        ocorrencias, cache={"entries": {}}, offline=False, refresh=True, pause=False
    )
    assert errados[0].status == "mismatch"
    saida = io.StringIO()
    assert rs.report(errados, stream=saida) == 1
    assert "FONTES REPROVADAS" in saida.getvalue()


def test_crossref_404_e_unresolved(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "Nota.md").write_text(LINHA_DOI + "\n", encoding="utf-8")

    def fake_urlopen(pedido: object, timeout: float = 0) -> _FakeResponse:
        return _FakeResponse(404, b"{}")

    monkeypatch.setattr(rs.urllib.request, "urlopen", fake_urlopen)
    vereditos = rs.resolve_all(
        rs.collect(tmp_path),
        cache={"entries": {}},
        offline=False,
        refresh=True,
        pause=False,
    )
    assert vereditos[0].status == "unresolved"


def test_rede_cai_vira_skip_nunca_ok(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "Nota.md").write_text(LINHA_DOI + "\n", encoding="utf-8")

    def fake_urlopen(pedido: object, timeout: float = 0) -> Iterator[None]:
        raise URLError("sem rede")

    monkeypatch.setattr(rs.urllib.request, "urlopen", fake_urlopen)
    vereditos = rs.resolve_all(
        rs.collect(tmp_path),
        cache={"entries": {}},
        offline=False,
        refresh=True,
        pause=False,
    )
    assert vereditos[0].status == "skip"
    assert rs.report(vereditos, stream=io.StringIO()) == 0


def test_cache_evita_segunda_consulta(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "Nota.md").write_text(LINHA_DOI + "\n", encoding="utf-8")
    chamadas = {"n": 0}

    def fake_urlopen(pedido: object, timeout: float = 0) -> _FakeResponse:
        chamadas["n"] += 1
        corpo = json.dumps(
            {"message": {"title": ["Judgment under Uncertainty: Heuristics and Biases"]}}
        ).encode()
        return _FakeResponse(200, corpo)

    monkeypatch.setattr(rs.urllib.request, "urlopen", fake_urlopen)
    cache: dict[str, object] = {"entries": {}}
    ocorrencias = rs.collect(tmp_path)
    primeiro = rs.resolve_all(
        ocorrencias, cache=cache, offline=False, refresh=False, pause=False
    )
    segundo = rs.resolve_all(
        ocorrencias, cache=cache, offline=False, refresh=False, pause=False
    )
    assert primeiro[0].status == "ok"
    assert segundo[0].detail == "cache"
    assert chamadas["n"] == 1


def test_isbn_open_library_ouro(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    linha = (
        '- Peter Godfrey-Smith. *Theory and Reality*. University of Chicago Press, '
        "2021. ISBN 978-0-226-61865-4.\n"
    )
    (tmp_path / "Nota.md").write_text(linha, encoding="utf-8")
    visto: list[str] = []

    def fake_urlopen(pedido: object, timeout: float = 0) -> _FakeResponse:
        url = getattr(pedido, "full_url", str(pedido))
        visto.append(url)
        corpo = json.dumps(
            {
                f"ISBN:{OURO_ISBN}": {
                    "title": "Theory and Reality",
                    "subtitle": (
                        "An Introduction to the Philosophy of Science, Second Edition"
                    ),
                    "authors": [{"name": "Peter Godfrey-Smith"}],
                    "identifiers": {"isbn_13": [OURO_ISBN], "isbn_10": ["022661865X"]},
                }
            }
        ).encode()
        return _FakeResponse(200, corpo)

    monkeypatch.setattr(rs.urllib.request, "urlopen", fake_urlopen)
    vereditos = rs.resolve_all(
        rs.collect(tmp_path),
        cache={"entries": {}},
        offline=False,
        refresh=True,
        pause=False,
    )
    assert vereditos[0].status == "ok"
    assert vereditos[0].key == f"isbn:{OURO_ISBN}"
    assert visto[0] == (
        f"https://openlibrary.org/api/books?bibkeys=ISBN:{OURO_ISBN}&format=json&jscmd=data"
    )


def test_arxiv_atom(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "Nota.md").write_text(LINHA_ARXIV + "\n", encoding="utf-8")
    atom = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>MLLM-Bench: Evaluating Multimodal LLMs with Per-sample Criteria</title>
  </entry>
</feed>
"""

    def fake_urlopen(pedido: object, timeout: float = 0) -> _FakeResponse:
        url = getattr(pedido, "full_url", str(pedido))
        assert "export.arxiv.org/api/query" in url
        assert "id_list=2311.13951" in url
        return _FakeResponse(200, atom.encode())

    monkeypatch.setattr(rs.urllib.request, "urlopen", fake_urlopen)
    vereditos = rs.resolve_all(
        rs.collect(tmp_path),
        cache={"entries": {}},
        offline=False,
        refresh=True,
        pause=False,
    )
    assert vereditos[0].status == "ok"
