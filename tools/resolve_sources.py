#!/usr/bin/env python3
"""Resolve DOI, arXiv e ISBN das notas contra as APIs oficiais.

stdlib + HTTP. Não entra em `make audit`: o gate estrutural permanece
offline. Sem rede o identificador sai `skip`, nunca `ok`.

    python3 tools/resolve_sources.py
    python3 tools/resolve_sources.py --offline
    python3 tools/resolve_sources.py --corpus PATH --cache PATH

Contrato: docs/SOURCE-RESOLVER.md. Endpoints copiados da página oficial:

- DOI:    GET https://api.crossref.org/works/{doi}
- arXiv:  GET http://export.arxiv.org/api/query?id_list={id}
- ISBN:   GET https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data

Os três regexes são os mesmos de `vault.promotion.patch` (ciclo de
remoção). Um teste confronta as extrações.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "knowledge"
DEFAULT_CACHE = Path(__file__).resolve().parent.parent / "runtime" / "state" / "sources.json"
ATOM = "{http://www.w3.org/2005/Atom}"
CROSSREF = "https://api.crossref.org/works/"
ARXIV_EXPORT = "http://export.arxiv.org/api/query"
OPENLIBRARY_BOOKS = "https://openlibrary.org/api/books"
USER_AGENT = "A.N.E.-source-resolver (https://github.com/Ziuluiziul/A.N.E)"

# Iguais a vault.promotion.patch. Divergir é defeito: tests/test_resolve_sources.py.
_DOI = re.compile(r"(?:doi\.org/|doi:\s*)?(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.I)
_ARXIV = re.compile(r"(?:arxiv\.org/abs/|arXiv:)\s*`?(\d{4}\.\d{4,5}(?:v\d+)?)`?", re.I)
_ISBN = re.compile(r"(?:ISBN(?:-1[03])?:?\s*)?((?:978|979)(?:[-\s]?\d){10})", re.I)
_QUOTED = re.compile(r"[“\"«]([^”\"»]+)[”\"»]")
_ITALIC = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_SPACES = re.compile(r"\s+")
_TAGS = re.compile(r"<[^>]+>")

CONTAINMENT_MIN = 12
CROSSREF_PAUSE_S = 1.0
ARXIV_PAUSE_S = 3.0
OPENLIBRARY_PAUSE_S = 1.0
HTTP_TIMEOUT_S = 20.0


@dataclass(frozen=True, slots=True)
class Occurrence:
    key: str
    kind: str
    value: str
    path: str
    line: int
    local_title: str | None


@dataclass(frozen=True, slots=True)
class Verdict:
    key: str
    kind: str
    value: str
    status: str
    local_title: str | None
    canonical_title: str | None
    http_status: int | None
    detail: str
    occurrences: int
    fetched_at: str


def identifiers_in(text: str) -> set[str]:
    """DOI, arXiv e ISBN no texto, na forma canônica doi:/arxiv:/isbn:."""
    encontrados: set[str] = set()
    dois: list[str] = []
    for achado in _DOI.finditer(text):
        doi = achado.group(1).casefold().rstrip(".,;")
        dois.append(doi)
        encontrados.add("doi:" + doi)
    for achado in _ARXIV.finditer(text):
        encontrados.add("arxiv:" + achado.group(1).casefold())
    doi_digitos = re.sub(r"\D", "", "".join(dois))
    for achado in _ISBN.finditer(text):
        digits = re.sub(r"\D", "", achado.group(1))
        if len(digits) == 13 and digits not in doi_digitos:
            encontrados.add("isbn:" + digits)
    return encontrados


def extract_title(line: str) -> str | None:
    """Título local na mesma linha: aspas, depois itálico Markdown."""
    quoted = _QUOTED.search(line)
    if quoted:
        titulo = quoted.group(1).strip()
        if titulo:
            return titulo
    italic = _ITALIC.search(line)
    if italic:
        titulo = italic.group(1).strip()
        # *Nature* numa linha de claim é o periódico, não o artigo.
        if len(titulo) >= CONTAINMENT_MIN:
            return titulo
    return None


def normalize_title(text: str) -> str:
    """Caixa, Unicode, pontuação, tags HTML e espaços — o que a Política autoriza."""
    compacto = _TAGS.sub(" ", text)
    compacto = unicodedata.normalize("NFKC", compacto).casefold()
    compacto = _PUNCT.sub(" ", compacto)
    return _SPACES.sub(" ", compacto).strip()


def titles_match(local: str, canonical: str) -> bool:
    """Igualdade após normalizar; subtítulo só se o núcleo local for longo."""
    esquerda = normalize_title(local)
    direita = normalize_title(canonical)
    if not esquerda or not direita:
        return False
    if esquerda == direita:
        return True
    if len(esquerda) >= CONTAINMENT_MIN and esquerda in direita:
        return True
    return len(direita) >= CONTAINMENT_MIN and direita in esquerda


def collect(corpus: Path) -> list[Occurrence]:
    ocorrencias: list[Occurrence] = []
    if not corpus.is_dir():
        return ocorrencias
    for path in sorted(p for p in corpus.rglob("*.md") if p.is_file()):
        try:
            texto = path.read_text(encoding="utf-8")
        except OSError:
            continue
        relativo = path.relative_to(corpus).as_posix()
        for numero, linha in enumerate(texto.splitlines(), 1):
            for chave in sorted(identifiers_in(linha)):
                kind, _, value = chave.partition(":")
                ocorrencias.append(
                    Occurrence(
                        key=chave,
                        kind=kind,
                        value=value,
                        path=relativo,
                        line=numero,
                        local_title=extract_title(linha),
                    )
                )
    return ocorrencias


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _headers() -> dict[str, str]:
    agent = USER_AGENT
    mailto = os.environ.get("VAULT_CROSSREF_MAILTO") or os.environ.get("CROSSREF_MAILTO")
    if mailto:
        agent = f"{USER_AGENT}; mailto:{mailto}"
    return {"User-Agent": agent, "Accept": "*/*"}


def fetch(url: str, timeout: float = HTTP_TIMEOUT_S) -> tuple[int | None, bytes]:
    pedido = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as resposta:  # noqa: S310
            return int(resposta.status), resposta.read()
    except urllib.error.HTTPError as error:
        try:
            corpo = error.read()
        except OSError:
            corpo = b""
        return int(error.code), corpo
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, b""


def _crossref_url(doi: str) -> str:
    return CROSSREF + urllib.parse.quote(doi, safe="")


def _arxiv_url(arxiv_id: str) -> str:
    return f"{ARXIV_EXPORT}?id_list={urllib.parse.quote(arxiv_id, safe='')}"


def _isbn_url(isbn: str) -> str:
    # A forma do caso ouro (ciclo 1) não percent-encode o `:`.
    return f"{OPENLIBRARY_BOOKS}?bibkeys=ISBN:{isbn}&format=json&jscmd=data"


def _title_from_crossref(body: bytes) -> str | None:
    try:
        dados = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    titulos = dados.get("message", {}).get("title")
    if isinstance(titulos, list) and titulos and isinstance(titulos[0], str):
        return titulos[0]
    return None


def _title_from_arxiv(body: bytes) -> str | None:
    try:
        raiz = ET.fromstring(body)
    except ET.ParseError:
        return None
    for entrada in raiz.findall(f"{ATOM}entry"):
        titulo = entrada.findtext(f"{ATOM}title")
        if titulo:
            return _SPACES.sub(" ", titulo).strip()
        return None
    return None


def _title_from_openlibrary(isbn: str, body: bytes) -> str | None:
    try:
        dados = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(dados, dict):
        return None
    registro = dados.get(f"ISBN:{isbn}")
    if not isinstance(registro, dict):
        return None
    titulo = registro.get("title")
    if isinstance(titulo, str) and titulo.strip():
        return titulo.strip()
    return None


def _decide(
    *,
    local_title: str | None,
    canonical_title: str | None,
    resolved: bool,
) -> tuple[str, str]:
    if not resolved:
        return "unresolved", "identificador não resolveu na API oficial"
    if local_title is None:
        return "ok", "resolveu; linha sem título local extraível"
    if canonical_title is None:
        return "unresolved", "API respondeu sem título canônico"
    if titles_match(local_title, canonical_title):
        return "ok", "título canônico corresponde após normalização"
    return "mismatch", "título local diverge do canônico"


def resolve_remote(kind: str, value: str) -> tuple[str, str | None, int | None, str]:
    """Consulta uma API. Devolve (status, título, http, detalhe)."""
    if kind == "doi":
        http, corpo = fetch(_crossref_url(value))
        if http is None:
            return "skip", None, None, "rede indisponível (Crossref)"
        if http == 404:
            return "unresolved", None, http, "Crossref 404"
        if http != 200:
            return "skip", None, http, f"Crossref HTTP {http}"
        titulo = _title_from_crossref(corpo)
        return "resolved", titulo, http, "Crossref 200"
    if kind == "arxiv":
        http, corpo = fetch(_arxiv_url(value))
        if http is None:
            return "skip", None, None, "rede indisponível (arXiv export)"
        if http != 200:
            return "skip", None, http, f"arXiv HTTP {http}"
        titulo = _title_from_arxiv(corpo)
        if titulo is None:
            return "unresolved", None, http, "arXiv sem entry"
        return "resolved", titulo, http, "arXiv 200"
    if kind == "isbn":
        http, corpo = fetch(_isbn_url(value))
        if http is None:
            return "skip", None, None, "rede indisponível (Open Library)"
        if http != 200:
            return "skip", None, http, f"Open Library HTTP {http}"
        titulo = _title_from_openlibrary(value, corpo)
        if titulo is None:
            return "unresolved", None, http, "Open Library sem registro"
        return "resolved", titulo, http, "Open Library 200"
    return "skip", None, None, f"tipo desconhecido: {kind}"


def load_cache(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "entries": {}}
    try:
        dados = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": 1, "entries": {}}
    if not isinstance(dados, dict):
        return {"schema_version": 1, "entries": {}}
    entradas = dados.get("entries")
    if not isinstance(entradas, dict):
        dados["entries"] = {}
    return dados


def save_cache(path: Path, cache: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporario = path.with_name(f".{path.name}.tmp")
    temporario.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporario, path)


def _pause_for(kind: str, enabled: bool) -> None:
    if not enabled:
        return
    if kind == "doi":
        time.sleep(CROSSREF_PAUSE_S)
    elif kind == "arxiv":
        time.sleep(ARXIV_PAUSE_S)
    else:
        time.sleep(OPENLIBRARY_PAUSE_S)


def resolve_all(
    occurrences: Sequence[Occurrence],
    *,
    cache: dict[str, Any],
    offline: bool,
    refresh: bool,
    pause: bool,
) -> list[Verdict]:
    por_chave: dict[str, list[Occurrence]] = {}
    for item in occurrences:
        por_chave.setdefault(item.key, []).append(item)
    vereditos: list[Verdict] = []
    entradas = cache.setdefault("entries", {})
    for chave in sorted(por_chave):
        grupo = por_chave[chave]
        primeira = grupo[0]
        local = max(
            (item.local_title for item in grupo if item.local_title),
            key=len,
            default=None,
        )
        guardado = entradas.get(chave) if not refresh else None
        if (
            isinstance(guardado, dict)
            and guardado.get("status") in {"ok", "mismatch", "unresolved"}
            and not refresh
        ):
            vereditos.append(
                Verdict(
                    key=chave,
                    kind=primeira.kind,
                    value=primeira.value,
                    status=str(guardado["status"]),
                    local_title=local,
                    canonical_title=guardado.get("canonical_title"),
                    http_status=guardado.get("http_status"),
                    detail="cache",
                    occurrences=len(grupo),
                    fetched_at=str(guardado.get("fetched_at", "")),
                )
            )
            continue
        if offline:
            veredito = Verdict(
                key=chave,
                kind=primeira.kind,
                value=primeira.value,
                status="skip",
                local_title=local,
                canonical_title=None,
                http_status=None,
                detail="offline: sem cache utilizável",
                occurrences=len(grupo),
                fetched_at=_now(),
            )
            vereditos.append(veredito)
            continue
        _pause_for(primeira.kind, pause)
        bruto, canonico, http, detalhe = resolve_remote(primeira.kind, primeira.value)
        if bruto == "skip":
            status, motivo = "skip", detalhe
        elif bruto == "unresolved":
            status, motivo = "unresolved", detalhe
        else:
            status, motivo = _decide(
                local_title=local,
                canonical_title=canonico,
                resolved=True,
            )
        quando = _now()
        veredito = Verdict(
            key=chave,
            kind=primeira.kind,
            value=primeira.value,
            status=status,
            local_title=local,
            canonical_title=canonico,
            http_status=http,
            detail=motivo,
            occurrences=len(grupo),
            fetched_at=quando,
        )
        vereditos.append(veredito)
        if status != "skip":
            entradas[chave] = {
                "status": status,
                "canonical_title": canonico,
                "http_status": http,
                "detail": motivo,
                "fetched_at": quando,
            }
    return vereditos


def report(verdicts: Sequence[Verdict], *, stream: Any = sys.stdout) -> int:
    contagem = {"ok": 0, "mismatch": 0, "unresolved": 0, "skip": 0}
    por_tipo = {"doi": 0, "arxiv": 0, "isbn": 0}
    for item in verdicts:
        contagem[item.status] = contagem.get(item.status, 0) + 1
        por_tipo[item.kind] = por_tipo.get(item.kind, 0) + 1
    print(f"doi ............................ {por_tipo['doi']}", file=stream)
    print(f"arxiv .......................... {por_tipo['arxiv']}", file=stream)
    print(f"isbn ........................... {por_tipo['isbn']}", file=stream)
    print(f"ok ............................. {contagem.get('ok', 0)}", file=stream)
    print(f"mismatch ....................... {contagem.get('mismatch', 0)}", file=stream)
    print(f"unresolved ..................... {contagem.get('unresolved', 0)}", file=stream)
    print(f"skip ........................... {contagem.get('skip', 0)}", file=stream)
    for item in verdicts:
        if item.status in {"mismatch", "unresolved"}:
            print(
                f"  !! {item.status.upper()}: {item.key} — {item.detail}",
                file=stream,
            )
            if item.local_title or item.canonical_title:
                print(
                    f"     local: {item.local_title!r} | canônico: {item.canonical_title!r}",
                    file=stream,
                )
    defeitos = contagem.get("mismatch", 0) + contagem.get("unresolved", 0)
    if defeitos:
        print(
            "\nFONTES REPROVADAS — "
            f"mismatch: {contagem.get('mismatch', 0)}; "
            f"unresolved: {contagem.get('unresolved', 0)}",
            file=stream,
        )
        return 1
    print(
        "\nFONTES SEM DEFEITO MEDIDO — skip não é aprovação; "
        "mismatch e unresolved é que reprovam.",
        file=stream,
    )
    return 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve DOI/arXiv/ISBN das notas")
    parser.add_argument(
        "--corpus",
        type=Path,
        default=DEFAULT_ROOT,
        help="raiz do corpus (default: knowledge/)",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=DEFAULT_CACHE,
        help="JSON de cache (default: runtime/state/sources.json)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="só lê o cache; identificador novo sai skip",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="ignora o cache e consulta de novo",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="imprime o manifesto JSON além do resumo",
    )
    parser.add_argument(
        "--no-pause",
        action="store_true",
        help="não espera entre pedidos (testes)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    ocorrencias = collect(args.corpus)
    cache = load_cache(args.cache)
    vereditos = resolve_all(
        ocorrencias,
        cache=cache,
        offline=args.offline,
        refresh=args.refresh,
        pause=not args.no_pause,
    )
    if not args.offline:
        save_cache(args.cache, cache)
    codigo = report(vereditos)
    if args.json:
        print(json.dumps([asdict(item) for item in vereditos], ensure_ascii=False, indent=2))
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
