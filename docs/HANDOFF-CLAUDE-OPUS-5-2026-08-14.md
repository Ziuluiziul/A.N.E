# Handoff — de volta ao Claude Opus 5 — 2026-08-14

Passagem do Grok 4.6. O SHA deste arquivo não é o do trabalho: o código está em
`3fd3f09` (este pacote) e `d2765e8` (janela de promoção por alvo).

## O que fechei nesta sessão

Na ordem do seu handoff:

| item | commit | o que mudou |
|---|---|---|
| Janela de promoção por alvo | `d2765e8` | `_conferir_precondicoes` pergunta `git diff --name-only <base>..HEAD -- knowledge/<alvo>`. CSS/código não invalidam o patch. Alvo reescrito ainda recusa. Base que o git não resolve continua `base divergente`. |
| Endpoint estruturalmente impossível | `3fd3f09` | `is_structural_key_auth` (BYOK / teto USD 0). `_call` suspende o provedor. `create_panel` trata como `PanelUnavailableError`. `run_worker` confirma `/key` no boot e suspende o OpenRouter antes da primeira tarefa. |
| Voto ilegível | `3fd3f09` | `unreadable_votes` entra no mesmo saco de `invalid_envelope`: `retry_wait` com janela curta, nunca `blocked`. Também em `OPERATIONAL_BLOCK_OUTCOMES` — o `start` reabre os que já morreram. |
| Teto de prompt | `3fd3f09` | `MAX_PROMPT_CHARS` e `PanelTask.prompt` de 24 000 → 48 000. A morte de 33 849 era o **voto** (contrato + nota + proposta), não `_prompt`. |

Gates no `3fd3f09`: auditoria aprovada · **625 pytest** · 557 vitest · ruff, mypy, ESLint.

## O que continua aberto (a sua lista, o que sobrou)

1. **M1 — `quorum_capacity(t)`.** Ainda não existe. O ledger (`make outcomes`) já dá capacidade por endpoint; falta cruzar com `runtime/state/quotas.json` e com votos ≥ 3 · provedores ≥ 2 · famílias ≥ 3 em `vault/quorum/engine.py`.
2. **M2 — controlador de admissão.** Precedência ainda invertida: o orquestrador gasta o proponente e só depois planeja os revisores (`_plan_distinct`). Preflight antes de nascer. Impedido por cota → `retry_wait`, não `blocked`.
3. **M3.** `validate()` agora passa da guarda de HEAD, **mas a árvore viva continua suja**. Os 20 patches em disco ainda não viram `validation_outcome` enquanto os cinco arquivos do ajuste espacial estiverem no working tree. Decisão do mantenedor: commitar, descartar ou stash — não é de builder.
4. **M4 / M5.** Intocados. M5 ainda precisa da separação âncora/tecido da ADR-003.

## O que eu deliberadamente não fiz

- **Não commitei o ajuste espacial.** Os mesmos cinco: `backend/src/vault/app.py`, `frontend/src/{composeLayout,layout,layoutStore,operationalLayout}.ts`. Coerente, nunca verificado na cena, não é meu.
- **Não promovi nada.** Mesmo com a janela por alvo, `_exige_arvore_limpa` recusa. E promoção automática continua fora do escopo.
- **Não implementei M1/M2.** São o próximo incremento de verdade; este ciclo era fechar o que o seu handoff já tinha medido.

## Estado da fila quando saí

Worker reiniciado depois do `3fd3f09` (se o restart desta sessão tiver corrido). `corpus_review` ainda é o produto; meta sem `corpus_entity` não é elegível (`ddf465e`). OpenRouter, se a chave ainda estiver sem BYOK no teto, deve aparecer no stderr como `openrouter suspenso:` e sumir da seleção neste processo.

## Armadilhas que você já listou e continuam valendo

Captura = `window.__atlas.capturar`, não screenshot do Browser pane. Só `127.0.0.1`. `document.hidden` no pane. `Settings()` lê `secrets.env` real. Fake sem `stream_generate` esconde o ramo.

## Confirmação humana

Igual: credencial, OAuth, comando destrutivo/`git push`, orçamento. Fora disso, commitar o que passa nos três gates.
