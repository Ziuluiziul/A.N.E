# Handoff — para Grok 4.6 — M0 entregue, M1 e M2 abertos — 2026-08-14

Passagem do Claude Opus 5. O SHA deste commit não aparece aqui: um documento não pode
conter o identificador do commit que o contém.

## Onde parei

`5077733` — o M0 da [ADR-003](ADR-003-instrumentacao-antes-de-morfogenese.md). Antes dele,
nesta mesma sessão, entraram o relatório da frente morfogênica (`227102b`) e a régua com
nomes (`d8b5f5a`). Os quatro commits anteriores são de outro builder e de você.

```text
gates       auditoria aprovada · 620 pytest · 557 vitest · ruff, mypy, ESLint limpos
corpus      84 notas · 672 wikilinks · 267 claims · intocado desde 2026-08-04
ledger      1640 registros — 852 attempt, 471 vote, 160 proposal, 157 decision
árvore      5 arquivos modificados de OUTRO builder (ajuste espacial) — não commite
```

`make outcomes` reconstrói o ledger e imprime as superfícies. `ARGS=--json` para máquina.

## O que o M0 é, e o que ele não é

**É derivado, não emitido.** As tentativas sempre estiveram em
`runtime/state/autonomy/tasks.json` e os votos em `runtime/quorum/<id>/votes/`. Faltava
lê-los. Não acrescentei caminho de escrita no orquestrador de propósito: um segundo
gravador no caminho quente arrisca as chamadas que se quer medir e cria duas verdades
sobre o mesmo evento. Reconstruir é idempotente; apagar `outcomes.jsonl` não perde nada.

**Não é calibração.** `Aptidao` mede se o voto chegou **utilizável** num papel e domínio,
nunca se ele julgou certo. O nome evita a promessa de propósito. Competência epistêmica
é M3 e depende de desfecho independente, que ainda não existe.

Armadilha que já custou uma versão: a primeira `Aptidao` respondia **100% para todo
endpoint**. Ela lia `decision.json`, que só lista voto **contado** — a pergunta era
circular. A fonte certa é `votes/*.json`, que guarda o ilegível também. Se você tocar
nesse caminho, o teste
`test_validade_do_voto_sai_de_votes_e_nao_da_decisao` é o que protege isso.

## O achado que decide o próximo incremento

Fui medir por que nenhum dos patches chega ao corpus e a causa não é a que estava escrita
em lugar nenhum:

```text
patches em disco ............ 20
com base_commit == HEAD ..... 0
bases distintas ............. 9   (todas existem no repositório)
```

`ProposalPromoter._conferir_precondicoes` exige que a base do patch seja o HEAD. O
repositório recebeu **seis commits só hoje**. Logo a janela de promoção de um patch é o
intervalo entre a decisão do painel e o commit seguinte — que na prática é zero.

Isso é mais fundamental que "o promotor é manual": mesmo um promotor automático falharia,
porque o patch envelhece a cada commit. E envelhece por commit **em qualquer arquivo**:
uma mudança em `frontend/src/style.css` invalida um patch em `Física/…md`, que não podem
colidir.

A direção de correção que eu proponho, sem tê-la implementado: a pergunta certa não é "o
HEAD mudou?", e sim "**as notas que este patch toca mudaram desde a base?**" — que o git
responde com `git diff --name-only <base>..HEAD -- knowledge/<alvo>`. Não implementei
porque é afrouxar uma guarda no único caminho que escreve no corpus, e isso merece
incremento próprio, com o mantenedor sabendo. A ADR-003 é explícita: nenhum score
aprendido remove guarda determinística — isto aqui não é score, mas é guarda, e a
prudência vale igual.

Consequência prática para o M3: `ProposalPromoter.validate()` também passa por
`_conferir_precondicoes`, então **hoje ele recusa todos os 20 patches** — por base
divergente, e por árvore suja. A população inicial de `validation_outcome` que a ADR-003
previu para calibrar o `revisor-estrutural` está bloqueada por isso, não por falta de
dados.

## Próximos passos, na ordem que eu seguiria

1. **Janela de promoção por alvo** (acima). Destrava `validate()`, e com ele os 20
   patches viram a primeira população de desfechos. É o pré-requisito real do M3, e é
   pequeno.
2. **M1 — `quorum_capacity(t)`.** Quantos conjuntos disjuntos de revisores satisfazem
   votos ≥ 3, provedores ≥ 2, famílias ≥ 3 e quota disponível, agora. O ledger já dá
   `Capacidade` por endpoint; falta cruzar com `runtime/state/quotas.json` e com a
   diversidade exigida em `vault/quorum/engine.py`.
3. **M2 — controlador de admissão.** Hoje a precedência é invertida: o orquestrador gasta
   o proponente e **só depois** planeja os revisores distintos (`_plan_distinct`, em
   `work/orchestrator.py`), então uma tarefa cujo quórum já era inviável consome uma
   chamada. Inverter: preflight antes de nascer. E tarefa impedida por cota vai para
   `retry_wait` com `next_eligible_at`, não morre em `blocked` — o mecanismo já existe em
   `QueueStore`, não precisa de máquina de estados nova.
4. **Endpoint estruturalmente impossível fora da seleção.** O ledger mostra
   `openrouter/nvidia/nemotron-3.5-lightning:free` com **51 tentativas, zero sucesso, 49
   recusas por credencial** (`a chave precisa incluir uso BYOK no teto de gasto USD 0`).
   Ele não pode funcionar na configuração atual e continua sendo escolhido. Aparece em
   quatro medições seguidas minhas; é a correção mais barata da lista.
5. **Voto ilegível não deve aposentar a nota.** Quatro das `corpus_review` bloqueadas
   morreram em `2 avaliações válidas; mínimo é 3`. É o mesmo defeito que `1328e36`
   corrigiu do lado do proponente, intacto do lado dos revisores.
6. **Teto de prompt.** Uma tarefa morreu com `prompt com 33849 caracteres excede 24000`.
   Notas grandes estão fora do sistema hoje.

## O que eu deliberadamente não fiz

- **Não commitei o ajuste espacial de outro builder.** Cinco arquivos —
  `backend/src/vault/app.py`, `frontend/src/{composeLayout,layout,layoutStore,operationalLayout}.ts`.
  É um ajuste coerente (anel 92→104, folga 1,62→1,78, quórum 1,15→1,0) com os dois
  contadores de versão subidos, mas **nunca foi verificado na cena viva** e não é meu. Ele
  também mantém a árvore suja, o que barra promoção real. Precisa de decisão do
  mantenedor, não de mais um builder passando por cima.
- **Não afrouxei a guarda de base**, pelo motivo da seção anterior.
- **Não implementei M3, M4 nem M5.** M3 depende do item 1; M5 depende da separação
  âncora/tecido que a ADR-003 fixou mas ninguém desenhou ainda.

## Armadilhas desta casa que vão te pegar

1. **Captura é gate em render.** Teste verde não prova cena. O Browser pane não compõe
   quadros: `screenshot` falha. O caminho é `window.__atlas.capturar(nome, w, h)`, que lê
   o canvas e grava em `runtime/captures/`. E ele captura **só o WebGL** — para ver DOM
   sobre a cena é preciso compor por `foreignObject`, com o CSS dentro de `CDATA`, senão
   o `@media (width <= 900px)` traz um `<` literal e o SVG não parseia. Foi assim que eu
   fotografei a régua.
2. **Só por `127.0.0.1`.** Por `localhost` o módulo é bloqueado e parece defeito da
   aplicação.
3. **`document.hidden` é verdadeiro no Browser pane**, o que suspende o polling do
   controle e o dock nasce sem cartão. Redefinir a propriedade e disparar
   `visibilitychange` resolve.
4. **`Settings()` lê o `secrets.env` real por padrão.** Todo teste precisa passar
   `_env_file`, ou usar as funções que recebem o diretório direto — foi por isso que
   `build_records(runtime_dir)` não toca em `Settings`.
5. **Fake sem o método esconde o ramo.** `getattr(adapter, "stream_generate", None)` já
   escolheu um caminho que os fakes não tinham, e 536 testes verdes não viram a cota
   virar estimativa.

## Confirmação humana

Continua obrigatória em quatro casos, e só neles: credencial, OAuth interativo, comando
destrutivo ou administrativo — `git push`, reescrita de histórico, remoção de dados — e
consumo externo acima do orçamento. Fora disso, o regime deste repositório é commitar o
que passa nos três gates. Promoção ao corpus não está nessa lista porque passa pelo
quórum e pelo Promoter, mas **veja o item 1**: hoje ela não roda de todo jeito.
