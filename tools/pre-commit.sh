#!/usr/bin/env bash
# Gate local de pré-commit: o mesmo contrato que o AGENTS.md exige antes de
# qualquer alteração — auditoria, testes e lint, os três verdes.
#
# Instalado como .git/hooks/pre-commit (symlink para este arquivo, que é
# versionado; o hook em si não é). Para um commit que precise pular os gates:
#
#     VAULT_SKIP_HOOKS=1 git commit ...
set -euo pipefail

if [ "${VAULT_SKIP_HOOKS:-0}" = "1" ]; then
    echo "pre-commit: VAULT_SKIP_HOOKS=1 — gates pulados"
    exit 0
fi

REPO="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
cd "$REPO"

# `env -u PYTHONPATH` existe por causa de um acidente real de 2026-08-16: um
# shell de agente com PYTHONPATH apontando para o venv 3.11 do Hermes fez o
# pytest 3.13 importar o pydantic_core compilado errado, e a suíte inteira
# falhou na coleta. O venv do projeto é quem manda aqui; herança externa não.
#
# `GIT_INDEX_FILE` e afins são exportados pelo próprio `git commit` no processo
# do hook. Os testes que exercitam o ProposalPromoter criam repositórios
# próprios em tmp e, com o índice herdado, passam a commitar contra o índice do
# repositório externo — oito testes falharam na primeira execução por isso. Um
# gate não pode vazar o contexto do commit para dentro da suíte.
gate() {
    env -u PYTHONPATH \
        -u GIT_INDEX_FILE -u GIT_PREFIX -u GIT_DIR -u GIT_WORK_TREE \
        make "$1"
}

gate audit
gate test
gate lint
