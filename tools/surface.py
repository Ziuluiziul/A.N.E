#!/usr/bin/env python3
"""Superfície do produto — o que pode ir ao GitHub público A.N.E.

Handoff, ciclo, prompt, bootstrap, frente morfogênica, auditoria de sessão e
notas de plugin não são o produto. Vivem no diretório irmão ``_ane-construcao/``
e no histórico do vault privado. Este script recusa qualquer um deles no índice Git.

    python3 tools/surface.py
    make publish-check
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

_PREFIXOS_DOCS = (
    "HANDOFF-",
    "CICLO-",
    "PROMPT-",
    "BOOTSTRAP-",
    "FRENTE-",
)


def e_construcao(caminho: str) -> bool:
    """Verdadeiro se o path versionado é diário de construção, não produto."""

    posix = caminho.replace("\\", "/")
    if posix == "docs/X-MCP.md" or posix.startswith(".claude/"):
        return True
    if posix.startswith("docs/audits/"):
        return True
    if not posix.startswith("docs/"):
        return False
    nome = posix.rsplit("/", 1)[-1]
    return nome.startswith(_PREFIXOS_DOCS)


def arquivos_proibidos(rastreados: Iterable[str]) -> list[str]:
    return sorted(path for path in rastreados if e_construcao(path))


def arquivos_rastreados(repo: Path) -> list[str]:
    concluido = subprocess.run(  # noqa: S603 — git ls-files, sem shell
        ["git", "-C", str(repo), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if concluido.returncode != 0:
        return []
    return [item.decode("utf-8") for item in concluido.stdout.split(b"\0") if item]


def verificar(repo: Path | None = None) -> list[str]:
    raiz = repo or RAIZ
    return arquivos_proibidos(arquivos_rastreados(raiz))


def main(argv: Sequence[str] | None = None) -> int:
    del argv  # nenhum argumento: o gate é o índice do repositório
    vazou = verificar()
    if vazou:
        print(
            "SUPERFÍCIE REPROVADA — diário de construção no índice Git "
            f"({len(vazou)}). Arquivo interno: diretório irmão _ane-construcao/",
            file=sys.stderr,
        )
        for path in vazou:
            print(path, file=sys.stderr)
        return 1
    print(
        "SUPERFÍCIE APROVADA — nenhum handoff, ciclo, prompt "
        "ou auditoria de sessão no índice."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
