# Atlas e SSE

Neste produto, **Atlas** é a UI Three.js em `http://127.0.0.1:5173`
(`tools/atlas.sh:16` default `VAULT_ATLAS_URL`; `frontend/vite.config.ts:97-100`
`host: '127.0.0.1'`, `port: 5173`). Não é [MongoDB Atlas](https://www.mongodb.com/docs/manual/changeStreams/).
Não é NVIDIA Atlas — o dump não contém esse produto; o adapter NVIDIA fala com
NIM hospedado (`providers/nvidia/adapter.py:50`).

## SSE (WHATWG)

Server-Sent Events é o Living Standard
https://html.spec.whatwg.org/multipage/server-sent-events.html (consulta
2026-08-30): interface `EventSource`, MIME `text/event-stream`, reconexão com o
header `Last-Event-ID`. Comentários (linhas que começam com `:`) o
`EventSource` descarta antes do JavaScript.

## O que o vault expõe (três GET)

Não existe path `/atlas/sse` neste dump (busca no backend e no frontend, 2026-08-30).
Os três GET estão em `backend/src/vault/app.py`:

| Método e path | Linha | Papel | `Last-Event-ID` |
| --- | ---: | --- | --- |
| `GET /corpus/events` | 313 | Projeção do corpus: `current` / `changed` / `error` / `recovered` (`vault/corpus/watcher.py:40-41`) | **não** lido nesta rota |
| `GET /runtime/events` | 345 | Tecido operacional: snapshot, replay por ID, heartbeat | `request.headers.get("last-event-id")` na linha 354; `revision_from_event_id` em `vault/events/models.py:64-72` |
| `GET /runtime/cognition` | 404 | Raciocínio ao vivo; **não** é a trilha operacional e **não** entra no corpus | `last-event-id` na linha 411; `revision_from_frame_id` em `vault/cognition/models.py:39-46` |

Os três devolvem `media_type="text/event-stream"` (linhas 331, 399, 444).

### `/runtime/events`

Heartbeat a cada `RUNTIME_HEARTBEAT_SECONDS = 15.0` (`app.py:53`) **sem** campo
`id`, de propósito: o comentário nas linhas 380-383 explica que um `id` no
heartbeat avançaria o `Last-Event-ID` do navegador. Eventos nomeados nesta rota:

- `runtime_snapshot` (linhas 364-367) — payload do snapshot; `id` = `snapshot.latest_id`
- `runtime_heartbeat` (linhas 384-387) — `{runtimeRevision}` do cursor; sem `id`
- o `event.type` persistido (`vault/events/models.py:16-33`): `task_created`,
  `task_assigned`, `call_started`, `call_completed`, `temporary_created`,
  `temporary_discarded`, `evidence_recorded`, `proposal_created`,
  `quorum_started`, `vote_requested`, `vote_received`, `quorum_decided`,
  `promotion_started`, `promotion_completed`, `commit_created`, `corpus_changed`

### `/runtime/cognition`

- `cognition_snapshot` (`app.py:417-419`)
- `cognition_heartbeat` (`app.py:429-432`), sem `id`, mesmo motivo
- o `frame.kind` (`vault/cognition/models.py:10-18`): `reasoning`,
  `reasoning-summary`, `output-delta`, `final`, `progress`, `tool-call`,
  `tool-result`

O front escuta `cognition_snapshot` e cada `kind` (`frontend/src/cognition.ts:124-136`).
Não há listener de `cognition_heartbeat` nesse arquivo.

### Front e proxy

| Constante | Path | Arquivo |
| --- | --- | --- |
| `BACKEND_EVENTS` | `/corpus/events` | `frontend/src/contract.ts:991` |
| `BACKEND_RUNTIME_EVENTS` | `/runtime/events` | `frontend/src/runtime.ts:99` |
| `BACKEND_COGNITION` | `/runtime/cognition` | `frontend/src/cognition.ts:33` |

Proxy Vite: `BACKEND_PROXY_PREFIXES` inclui `/corpus` e `/runtime`
(`frontend/vite.config.ts:10-16`); alvo default `http://127.0.0.1:8000`
(`vite.config.ts:33-34`). O navegador fala same-origin; o Vite encaminha.

## O que isto não é

[MongoDB change streams](https://www.mongodb.com/docs/manual/changeStreams/)
(consulta 2026-08-30) assinam mudanças duráveis num replica set. O vault não
abre cursor Mongo: o fluxo é HTTP SSE nas três rotas acima. A coincidência de
nome *Atlas* para com MongoDB Atlas é acidental e **não** descreve este
produto.

## Ver também

[ADR-005](ADR-005-propriedade-do-estado-operacional.md) é a decisão de
autoridade do estado operacional (`runtimeLayer`). Este documento é o contrato
HTTP do tecido: quem emite, em qual path, com qual cursor. A decisão não muda
aqui.
