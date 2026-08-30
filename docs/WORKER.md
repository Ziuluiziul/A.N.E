# Worker autônomo

O processo que deriva e executa a fila **não** nasce da API. `vault.app:app`
sobe watcher do corpus, bus operacional e bus cognitivo (`app.py:88-115`); não
instancia `tools/run_worker.py`. Quem spawna o worker, quando spawna, é o
supervisor POSIX `tools/atlas.sh`.

## Flag `VAULT_AUTONOMOUS_WORKER`

| Campo | Valor neste dump |
| --- | --- |
| Nome | `VAULT_AUTONOMOUS_WORKER` |
| Default no supervisor | `1` (`tools/atlas.sh:106`: `${VAULT_AUTONOMOUS_WORKER:-1}`) |
| `1` | spawna `uv run python tools/run_worker.py` com `--interval` (default 2 via `VAULT_WORKER_INTERVAL`) |
| `≠1` (o texto impresso assume `=0`) | **não** spawna; imprime `worker autônomo desativado por VAULT_AUTONOMOUS_WORKER=0` (`atlas.sh:118-119`) |
| Quem seta | o ambiente do processo que chama `atlas.sh` (`make dev` é `@tools/atlas.sh`, `Makefile:49-50`) |
| Restart | matar o supervisor e subir de novo: a flag é lida no spawn, não há hot-reload dela |

A flag **não** entra em `backend/src/vault/config.py`. `Settings` declara
`work_max_calls`, `worker_concurrency`, `provider_concurrency`,
`demo_operational` — e `extra="ignore"` (`config.py:44`). Um
`VAULT_AUTONOMOUS_WORKER` no `secrets.env` é ignorado pelo backend. Só o
supervisor a lê.

`.env.example:99-101` e `README.md:37`: `VAULT_AUTONOMOUS_WORKER=0 make dev`
sobe visualização e API sem chamadas de modelo pelo worker da pilha.

Onde a flag vive: variável de ambiente, no sentido de
https://www.12factor.net/config (consulta 2026-08-30) — config que varia entre
deploys, fora do código. Isso **não** afirma que o vault implementa
OpenFeature nem qualquer serviço de flags.

## Substituição e Windows

`make worker` → `uv run python tools/run_worker.py $(ARGS)` (`Makefile:79-80`).
É o mesmo binário que o supervisor spawna. A API não o substitui.

O dump do produto **não** contém `START.md`. A nota Windows lida fora do dump
(`/workspace/ane-context/win/START.md`, 2026-08-30) descreve dois processos —
`uvicorn vault.app:app` na 8000 e Vite na 5173 — *No WSL, no make, no
atlas.sh*. Nessa via o worker **nunca** nasce com a pilha: se existir, é
processo externo (`make worker` / `tools/run_worker.py`).

`tools/run_worker.py:65-67` tem `--interval` default **15.0** no argparse.
`atlas.sh` passa `--interval "${VAULT_WORKER_INTERVAL:-2}"`. `make worker` sem
ARGS usa o 15 do argparse, não o 2 do supervisor. São defaults de **entrada
diferente**, não uma contradição escondida.

## Teto `VAULT_WORK_MAX_CALLS`

`Settings.work_max_calls` em `config.py:93-96`: `default=6`, alias
`VAULT_WORK_MAX_CALLS` / `ANE_WORK_MAX_CALLS`. `.env.example:103-105` diz o
mesmo: vazio usa o padrão 6. `atlas.sh:108-110` só encaminha `--max-calls`
quando a variável **não** está vazia; vazia, o Python aplica o 6 do Settings.
`run_worker.py:70-73` (`--max-calls`) sobrescreve nesta execução.

O teto limita chamadas externas **do processo** de work / quorum / worker. Não
é RPM de provedor.

## Padrão para documentar a próxima flag

Nome; default; o que `0` faz versus `1`; quem seta (env do supervisor, não
`Settings`); o que precisa restart. Sem promover handoff a spec.
