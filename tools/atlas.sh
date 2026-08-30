#!/usr/bin/env bash
# Sobe o A.N.E. e abre o Atlas no navegador. É o que o ícone da área de trabalho chama.
#
# `set -m` torna o encerramento verificável: com job control cada serviço em segundo plano vira
# líder do próprio grupo, o PID guardado **é** o PGID, e `kill -- -PGID` alcança a
# árvore inteira — backend, frontend e worker, inclusive seus executores intermediários.
#
# Roda em terminal visível de propósito: o ponto do ícone é acompanhar, e log de
# backend escondido não deixa acompanhar nada.

set -euo pipefail
set -m

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
URL="${VAULT_ATLAS_URL:-http://127.0.0.1:5173}"
ESPERA_MAX_S="${VAULT_ATLAS_TIMEOUT:-90}"
CARENCIA_ENCERRAMENTO_S="${VAULT_ATLAS_SHUTDOWN_TIMEOUT:-35}"

cd "$REPO"
# Libera as portas **só** de processos que rodam de dentro deste repositório.
# `fuser -k` às cegas já derrubou serviço de outro projeto que ocupava a porta;
# o teste é o cwd do processo: quem não nasceu aqui não é desta pilha.
for porta in 8000 5173; do
    for pid in $(fuser "$porta/tcp" 2>/dev/null); do
        alvo="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
        case "$alvo" in
            "$REPO"|"$REPO"/*) kill "$pid" 2>/dev/null || true ;;
        esac
    done
done

printf '\033]0;A.N.E. — Atlas Neural-Epistêmico\007'
echo "A.N.E. — Atlas Neural-Epistêmico"
echo "repositório: $REPO"
echo "atlas:       $URL"
echo

# Estado antes de subir: quem já respondeu por sonda, e o que falta comprovar.
if [ -f runtime/state/endpoints.json ]; then
    echo "── endpoints ──────────────────────────────────────────────"
    uv run python tools/endpoints.py 2>/dev/null \
        | grep -E "^\w+ +\.\.|para trabalho|alcançados" || true
    echo
fi

GRUPOS=()

vivos() {
    local pgid restantes=0
    for pgid in "${GRUPOS[@]:-}"; do
        [ -n "$pgid" ] && kill -0 -- "-$pgid" 2>/dev/null && restantes=$((restantes + 1))
    done
    echo "$restantes"
}

sinalizar() {
    local sinal=$1 pgid
    for pgid in "${GRUPOS[@]:-}"; do
        [ -n "$pgid" ] && kill "-$sinal" -- "-$pgid" 2>/dev/null || true
    done
}

encerrar() {
    trap - EXIT INT TERM HUP
    echo
    echo "── encerrando ─────────────────────────────────────────────"
    sinalizar TERM

    # Os adaptadores têm timeout máximo de 30s. O worker recebe o sinal, termina no
    # máximo a chamada já enviada, persiste fila/ledger e não inicia a próxima. A
    # carência acrescenta 5s para esse fechamento; depois força, porque servidor
    # sobrevivente impediria a próxima abertura do ícone.
    local espera=0
    while [ "$(vivos)" -gt 0 ] && [ "$espera" -lt "$CARENCIA_ENCERRAMENTO_S" ]; do
        sleep 1
        espera=$((espera + 1))
    done
    if [ "$(vivos)" -gt 0 ]; then
        echo "   desligamento limpo não terminou em ${espera}s; forçando"
        sinalizar KILL
    fi
}
trap encerrar EXIT INT TERM HUP

echo "── projetando o corpus ────────────────────────────────────"
uv run python tools/corpus_graph.py

echo
echo "── subindo serviços (Ctrl-C encerra todos) ────────────────"
SERVICOS=()
# Streams SSE legítimos ficam abertos enquanto o navegador está vivo. Sem um teto de
# encerramento, o reloader espera essas conexões para sempre e deixa a porta aceitando
# conexões sem ter worker ASGI para respondê-las. Três segundos bastam para requests
# comuns; depois o Uvicorn cancela apenas os streams da geração antiga e recarrega.
uv run uvicorn vault.app:app --reload --timeout-graceful-shutdown 3 --port 8000 &
BACKEND=$!
GRUPOS+=("$BACKEND")
SERVICOS+=("$BACKEND")

(cd frontend && pnpm run dev) &
FRONTEND=$!
GRUPOS+=("$FRONTEND")
SERVICOS+=("$FRONTEND")

if [ "${VAULT_AUTONOMOUS_WORKER:-1}" = "1" ]; then
    WORKER_ARGS=(--interval "${VAULT_WORKER_INTERVAL:-2}")
    if [ -n "${VAULT_WORK_MAX_CALLS:-}" ]; then
        WORKER_ARGS+=(--max-calls "$VAULT_WORK_MAX_CALLS")
    fi
    if [ -n "${VAULT_WORKER_CONCURRENCY:-}" ]; then
        WORKER_ARGS+=(--concurrency "$VAULT_WORKER_CONCURRENCY")
    fi
    uv run python tools/run_worker.py "${WORKER_ARGS[@]}" &
    WORKER=$!
    GRUPOS+=("$WORKER")
    SERVICOS+=("$WORKER")
else
    echo "worker autônomo desativado por VAULT_AUTONOMOUS_WORKER=0"
fi

# `make dev` e o ícone compartilham este supervisor. A única diferença é abrir ou não
# o navegador: manter dois jeitos de subir os serviços foi o que deixou o defeito do
# `setsid` sobreviver sem ser notado.
(
    decorrido=0
    until curl -sfo /dev/null "$URL"; do
        sleep 1
        decorrido=$((decorrido + 1))
        [ "$decorrido" -ge "$ESPERA_MAX_S" ] && exit 1
    done
    echo
    echo "── Atlas no ar em $URL ────────────────────────────────────"
    if [ "${VAULT_ATLAS_OPEN:-1}" = "1" ]; then
        xdg-open "$URL" >/dev/null 2>&1 || echo "abra $URL no navegador"
    fi
) &
GRUPOS+=("$!")

# Se um serviço cair, encerra os demais em vez de deixar meia pilha rodando.
wait -n "${SERVICOS[@]}"
