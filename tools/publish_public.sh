#!/usr/bin/env bash
# Espelha o HEAD local do vault no GitHub público Ziuluiziul/A.N.E.
# Copia a árvore do produto, nunca runtime/ nem o diário de construção.
# Históricos são desconexos: um commit novo no público, não replay do privado.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
python3 tools/surface.py

SHA="$(git rev-parse --short HEAD)"
DEST="$(mktemp -d)/A.N.E"
git clone --depth 1 "https://github.com/Ziuluiziul/A.N.E.git" "$DEST"
# Só o índice: runtime/, .venv e o diário de construção nem entram.
find "$DEST" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
git archive HEAD | tar -x -C "$DEST"

cd "$DEST"
git config user.name "$(git -C "$ROOT" log -1 --format=%an)"
git config user.email "$(git -C "$ROOT" log -1 --format=%ae)"
git add -A
git ls-files | python3 -c '
import sys
sys.path.insert(0, "'"$ROOT"'")
from tools.surface import arquivos_proibidos
leaked = arquivos_proibidos(p.strip() for p in sys.stdin if p.strip())
if leaked:
    print("vazou no espelho:", *leaked, sep="\n", file=sys.stderr)
    raise SystemExit(1)
'
if git diff --cached --quiet; then
    echo "público já está alinhado a $SHA"
    exit 0
fi

git commit -m "$(cat <<EOF
Alinhe o produto público ao vault ${SHA}, sem diário de construção.

Árvore funcional: código, corpus, ADRs e specs. Handoff, ciclo, prompt
e auditoria de sessão ficam no vault privado.
EOF
)"
git push origin HEAD:main
echo "publicado $(git rev-parse --short HEAD) a partir de vault $SHA"
