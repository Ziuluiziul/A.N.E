# Achados — auditoria completa de 2026-08-14

Ranqueados por consequência, não por dificuldade. Cada um traz a medida que o sustenta e
onde ela foi tirada. `A` é aberto, `C` corrigido neste ciclo e verificado aqui.

## Estado em 2026-08-17

Medido de novo, não redescoberto.

| ID | estado | evidência |
|---|---|---|
| A-1 | parcialmente fechado | 3 promoções autônomas: `0d77a1a`, `062b7fc`, `7829edd` |
| A-2 / A-3 | aberto | M1/M2 no código; 491 decisões, 10 chamadas/decisão — o painel ainda é caro |
| A-4 | fechado | `d443048` — seleção lê o ledger por estágio |
| A-5 | fechado | `make retire-tasks`: 0 meta reivindicável sem nota (157 já `rejected`/`blocked`) |
| A-6 | fechado | árvore limpa; `validate()`/`promote()` deixaram de recusar por isso |
| A-7 | fechado | os dois handoffs de 13/08 estão rastreados no git |
| A-8 | fechado | `make audit` passa `--contra=HEAD` |
| A-9 | aberto | só amostragem humana |
| A-10 | fechado neste ciclo original | `--json` e aptidão têm teste |
| A-11 | fechado neste ciclo | `voto vazio não escala o patch`: reposição de cadeira + `resume_votes`/`tools/revote.py` |

Lacunas do M0 em 17/08: `validation_outcome` e `promotion_outcome` eram cegueira do
ledger — o diário já tinha 3 `promoted` e 8 `rejected`. O ledger passou a ler
`runtime/promotion/promotions.jsonl`. Resta `tokens por chamada`, que o ledger de cota
não amarra a `task_id`.

---

## A-1 · O corpus não recebe nada há dez dias, e a causa mudou de lugar

**Medida:** `knowledge/` inalterado desde `65a4d53` (2026-08-04). 162 painéis, 24 patches
em disco, 5 decisões `promote`, **0 promoções**. `runtime/proposals/` vazio.

Ao longo do dia a causa migrou três vezes, e cada correção revelou a seguinte: conta
Google sem crédito → envelope inválido → amplificador de divergência → janela de
promoção. Todas corrigidas. O que sobrou é o mais duro: **de 24 patches, 23 decidiram
`escalate`** — não há o que promover, porque o painel raramente conclui.

O único com decisão `promote` é o stub destrutivo, e a guarda o recusa corretamente.

**Consequência:** o sistema hoje é uma máquina de deliberar que não deposita. Enquanto
`escalate` for o desfecho de dois em cada três painéis, nenhuma correção de transporte
muda o resultado.

---

## A-2 · Dois em cada três painéis escalonam

**Medida:** 103 `escalate` em 159 decididos — **65%**. Contra 50 `reject`, 5 `promote`,
1 `revise`.

Nenhuma correção deste ciclo tocou nisso. As causas de escalonamento visíveis no ledger
são votos válidos insuficientes e diversidade insuficiente — ou seja, o painel não se
forma, não que ele discorde.

**Direção:** é o alvo natural do M1/M2 da [ADR-003](../../ADR-003-instrumentacao-antes-de-morfogenese.md).
Se `quorum_capacity(t)` disser que não há painel completo possível, a tarefa não deveria
nascer e consumir um proponente para escalonar depois.

---

## A-3 · O orçamento do lote virou a causa dominante

**Medida:** `orcamento-esgotado` domina **onze endpoints da nvidia**, cada um com 12 a 19
tentativas e **0% de sucesso**. `max_calls: 5` por tarefa é consumido antes de o painel
fechar — 4 chamadas formam o painel mínimo e a quinta é a única arbitragem.

**Consequência:** com três votos exigidos, dois provedores e três famílias, qualquer
falha isolada consome o lote inteiro. É exatamente a situação que o controlador de
admissão existe para evitar: reservar antes de gastar, em vez de gastar e descobrir.

---

## A-4 · Endpoints que nunca funcionaram continuam elegíveis

**Medida:**

| endpoint | tentativas | ok | causa única |
|---|---:|---:|---|
| `nvidia/meta/llama-3.2-3b-instruct` | 13 | 0% | tempo esgotado, 13 de 13 |
| `nvidia/openai/gpt-oss-120b` | 12 | 0% | indisponível, 12 de 12 |

Na aptidão por papel, `google/gemma-4-26b-a4b-it` e `google/gemma-4-31b-it` entregam
**0% de votos utilizáveis** em 9 observações cada.

O caso análogo do OpenRouter — 51 tentativas, 0% — **foi corrigido** em `3fd3f09`. Estes
não.

**Direção:** o ledger já mede isto. Falta a seleção consultá-lo, que é o M4.

---

## A-5 · Metade da fila é inventário morto

**Medida:** 134 das 255 tarefas são `divergence_review`; **73 estão `queued` sem nota
herdada**. O worker corretamente não as pega desde `ddf465e`, e nada as remove.

**Consequência:** hoje é ruído; se alguma mudança futura voltar a torná-las elegíveis,
vira gasto. Uma limpeza explícita é mais segura que confiar no filtro permanecer.

---

## A-6 · A árvore suja bloqueia o único caminho até o corpus

**Medida:** cinco arquivos modificados de um builder que não voltou —
`backend/src/vault/app.py`, `frontend/src/{composeLayout,layout,layoutStore,operationalLayout}.ts`.
`ProposalPromoter._conferir_precondicoes` exige árvore limpa, então **`validate()` e
`promote()` recusam tudo** enquanto isso durar.

O ajuste é coerente — anel 92→104, folga 1,62→1,78, quórum 1,15→1,0, com os dois
contadores de versão subidos — mas **nunca foi verificado na cena viva**, e um comentário
em `composeLayout.ts` ficou explicando um valor que não é mais o do código.

**Aberto há cinco sessões.** É decisão do mantenedor: verificar e commitar, ou descartar.
Nenhum builder deveria decidir por cima de outro.

**Efeito colateral:** sem `validate()`, não há `validation_outcome`, e sem ele o M3 da
ADR-003 não tem contra o que calibrar revisor nenhum.

---

## A-7 · Dois handoffs de 2026-08-13 nunca foram rastreados

**Medida:** `docs/HANDOFF-CLAUDE-OPUS-5-2026-08-13.md` e
`docs/HANDOFF-CLAUDE-OPUS-5-CONFIGURACAO-2026-08-13.md` estão como `??` desde o início
desta sessão. Ambos descrevem trabalho que já entrou no repositório.

---

## A-8 · O auditor estrutural é cego a destruição

**Medida:** aplicando o patch do painel `59e32f5df5d5` a uma cópia do corpus, a auditoria
reprova — mas **por um único sinal**, frontmatter ausente. Os 4 claims e os 5 wikilinks
perdidos não geram defeito algum: 267→263 e 672→667 passam calados.

A guarda de `30eedfc` cobre o caminho da promoção. **Não cobre edição direta** de
`knowledge/` por um humano ou por um agente com acesso ao disco.

**Direção:** o auditor poderia comparar contra o commit anterior e exigir declaração para
redução — o mesmo princípio de `allows_reduction`, aplicado ao gate estrutural.

---

## A-9 · O perfil epistêmico do corpus nunca foi amostrado

**Medida:** 164 de 267 claims são `established` (61%); 33 são `refuted` (12%).

Nenhuma das duas proporções é defeito, e nenhum script pode julgá-las: `established`
exige fonte verificada e `refuted` exige contradição efetiva, e a auditoria declara que
não resolve fonte. São 197 claims cuja justificativa nunca foi conferida por ninguém
desde a migração.

**Direção:** amostragem humana, ou o desfecho factual de L3 que a ADR-003 previu para o
`verificador-factual`. É o único achado desta lista que não se fecha com código.

---

## A-10 · Três defeitos do ciclo passaram por suíte verde

**Medida:** a aptidão do M0 respondia 100% para todos (fonte circular); o `--json`
quebrava por `vars()` sobre dataclass com `slots`; e o relatório afirmou independência
entre revisores que eram do mesmo provedor.

Nenhum apareceu em teste. Os três apareceram **ao usar**: rodando o comando, lendo a
saída, conferindo a fonte.

**Direção:** a casa já trata captura como gate em render. O mesmo vale para ferramenta de
linha de comando — todo ramo de saída precisa ser exercido, e o `--json` agora tem teste.

---

## A-11 · Voto vazio (Flash Lite / Longcat) escalonava o patch pronto

**Medida (2026-08-17/18):** de 9 quóruns disparados para inundar a A.N.E, **7 geraram
patch completo e decidiram `escalate` por falta de voto válido** — não por desacordo.
Nos painéis `6a1c34fef8d0`, `ce26d745bcc8`, `3c956d934cd9`, `489c103b7742` o painel
tinha **0 votos válidos**; em `50e2576ed8e4` e `1c28278240a2`, 2 e 1. A causa era
`final_response` vazio dos revisores `gemini-3.5-flash-lite` e `nous/longcat-2.0:free`
(com 1536 tokens a cota de saída era comida pelo pensamento interno). O schema
`parse_vote` devolvia `abstain` — mas a cadeira **ficava ocupada**, então o painel
escalava com o patch no disco e não havia caminho de fechá-lo senão um novo
`run_quorum` do zero.

**Correção (`voto-vazio-nao-escala-o-patch`):**
- `QuorumOrchestrator.collect_votes` marca endpoint com voto não-contado em
  `_failed_endpoints` (antes, só falha de transporte contava).
- `_replenish_invalid_votes` repõe cada papel sem voto válido por outro endpoint
  diverso (2 provedores / 2 famílias), respeitando cota — **uma** rodada extra, sem
  loop. Quem já falhou não é reescolhido.
- `resume_votes(panel)` reabre painel `escalate` com patch em disco, repõe e decide
  de novo — sem regerar a proposta.
- `tools/revote.py` aplica isso em lote: `uv run python tools/revote.py --pendentes`
  reabre todos os `escalate` que têm patch e promove automaticamente se o quórum
  fechar `promote` (o ProposalPromoter continua o único caminho até `knowledge/`).
- `VOTE_MAX_OUTPUT_TOKENS` 1536 → 4096 (cabe o raciocínio e sobra o JSON do voto).
- Teste `test_voto_invalido_e_reposto_sem_escalar_o_patch` exerce o caminho; o antigo
  `test_voto_invalido_vira_abstencao_sem_retry` foi substituído porque o comportamento
  mudou de propósito.

**Verificação:** `make audit && make test && make lint` verdes (742 pytest + 596
vitest). Os 7 painéis pendentes são reabertos por `tools/revote.py` após este commit.

---

## Corrigidos e verificados neste ciclo

| | correção | verificação nesta auditoria |
|---|---|---|
| C-1 | `d32ea67` — falha de conta suspende o provedor inteiro | fila com 14 bloqueadas contra 80 no início do dia |
| C-2 | `30eedfc` — `replace` destrutivo exige `allows_reduction` | o stub segue recusado, com as três métricas na mensagem |
| C-3 | `30eedfc` — `--dry-run` roda worktree, auditoria e projeção | `validate()` existe e é chamado pelo dry-run |
| C-4 | `1328e36` — envelope inválido não aposenta a nota | `corpus_review` voltou a circular: 31 na fila |
| C-5 | `ddf465e` — divergência exige nota herdada | 73 meta antigas paradas, nenhuma nova sem nota |
| C-6 | `d2765e8` — janela de promoção por alvo | **24 de 24 patches com alvo intacto**, contra 0 antes |
| C-7 | `3fd3f09` — OpenRouter BYOK fora da seleção | `openrouter suspenso: … BYOK` no boot do worker |
| C-8 | `3fd3f09` — voto ilegível não aposenta | `unreadable_votes` entrou na lista de retry |
| C-9 | `3fd3f09` — teto de prompt 24k → 48k | `MAX_PROMPT_CHARS = 48_000` e `Field(max_length=48_000)` |
| C-10 | `5077733` — M0 legível de volta | 1.691 registros, três superfícies discriminando |
| C-11 | `30dd91b` — `--json` do ledger | saída válida e com teste que a protege |

---

## Ordem sugerida

1. **A-6** — decisão do mantenedor sobre os cinco arquivos. Destrava `validate()`, e com
   ele o substrato do M3. É o único item que não depende de código.
2. **A-2 e A-3 juntos** — M1 `quorum_capacity` e M2 admissão. Atacam a mesma causa por
   dois lados e são o próximo incremento já decidido na ADR-003.
3. **A-4** — a seleção consultar o ledger. Barato, e o dado já existe.
4. **A-5 e A-7** — limpeza; minutos cada.
5. **A-8** — guarda de redução no auditor estrutural, fechando o caminho da edição direta.
6. **A-9** — amostragem humana do corpus. Não tem atalho.
