#!/usr/bin/env python3
"""Gera a projeção que o Atlas consome.

Escreve em `frontend/public/projection.json`, derivado e não versionado: o corpus é a
fonte, este arquivo é uma vista dele. Somente leitura sobre `knowledge/`.

O que sai daqui é o contrato de `vault.projection` — sem caminho absoluto, sem
conteúdo de arquivo, sem credencial.
"""

from __future__ import annotations

import sys
from pathlib import Path

import orjson

from vault.config import REPO_ROOT, get_settings
from vault.corpus import CorpusReader
from vault.corpus.identity import CorpusIdentityError
from vault.projection import ProjectionError, build_projection

DEFAULT_OUTPUT = REPO_ROOT / "frontend" / "public" / "projection.json"


def main(argv: list[str]) -> int:
    output = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUTPUT
    try:
        settings = get_settings()
        payload = build_projection(
            CorpusReader(settings.corpus_dir), demo_operational=settings.demo_operational
        )
    except (CorpusIdentityError, ProjectionError) as error:
        print(f"projeção reprovada: {error}")
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2))

    meta = payload["meta"]
    counts = meta["counts"]
    print(f"contrato ....... v{meta['contractVersion']} (origem: {meta['source']})")
    print(f"impressão ...... {meta['corpusFingerprint']}")
    print(f"notas .......... {counts['notes']} das quais {counts['mocs']} MOCs")
    print(f"wikilinks ...... {counts['wikilinks']} em {counts['canonicalEdges']} arestas")
    print(f"inter-MOC ...... {counts['aggregatedEdges']} filamentos agregados")
    print(f"claims ......... {counts['claims']}")
    print(f"domínios ....... {len(meta['domains'])}")

    diagnostics = meta["diagnostics"]
    if diagnostics["broken"] or diagnostics["undeclared"]:
        print(
            f"!! quebrados: {len(diagnostics['broken'])}; "
            f"sem relation: {len(diagnostics['undeclared'])} — rode `make audit`"
        )
    if diagnostics["collisions"]:
        print(f"!! colisões de nome (ainda sem link ambíguo): {diagnostics['collisions']}")
    print(f"escrito em ..... {output.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
