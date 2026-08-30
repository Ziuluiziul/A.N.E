# Auditoria AAA — 2026-08-24

**Auditor:** Grok 4.6 · **HEAD:** `269e104` · **Escopo:** corpus, pipeline, Atlas, ADRs, runtime
**Antecessoras:** `2026-08-14-ane-completa`, `2026-08-16-baseline-promocao`, `2026-08-17-primeira-promocao`

**Método.** Estrutura medida com `python3 tools/audit.py --contra=HEAD`. Corpus, diário,
fila e política lidos do disco nesta data. Fontes externas **não** foram resolvidas.
Onde a medição não existe, a linha diz que não existe.

**O que AAA significa aqui.** Não é volume nem brilho. É: o corpus só afirma o que
pode defender; o ciclo que o edita não corrompe nem mente sobre o próprio sucesso; a
cena mostra o estado vivo sem recarregar a página; o que a ADR aceitou está no caminho
quente ou está honestamente desligado.

---

## 1. Veredito

| eixo | nota | estado |
|---|---|---|
| Estrutura do corpus | A | `make audit` limpo: 84 notas, 672 wikilinks, 267 claims, 0 defeito |
| Verdade e proveniência | D | 0 resolução DOI neste gate; 18 promoções sem claim novo; 4 corrupções no texto |
| Pipeline de promoção | D | 18 commits de promoção, mas 43/52 rejeições do diário são árvore suja — e isso é terminal |
| Política editorial | C | Política (2026-07-18) e `AGENTS.md` (2026-08-03) se contradizem sobre quem promove |
| Atlas 3D | B | Cena densa e contratada; `atlas.ts` 2808 linhas sem teste; ADR-005 não implementada |
| Instrumentação | C | M0–M2 e M4 no código; ledger canônico parado em 17/08; A' com 1304 no-ops |
| Autonomia de código | D | ADR-006: tipo existe, ciclo não |
| Gates / CI | B | `audit`+`test`+`lint` no GitHub; sem DOI, sem visual, sem smoke de provedor |

O sistema deixou de ser a máquina que deliberava sem depositar. Agora deposita — e
**parte do que depositou piorou o corpus**, enquanto o working tree do operador
**queima** as aprovações seguintes.

---

## 2. O que já é profissional

- Separação corpus / código / runtime / secrets.
- Promoter com worktree, lock no `git-common-dir`, digest, diversidade recompute.
- Quórum determinístico; OpenRouter fora da contagem de provedor.
- Guarda de redução (`allows_reduction`) e janela por alvo, não por HEAD global.
- Contrato frontend versionado que recusa major desconhecida.
- Paleta OKLCH, LOD em pixels projetados, `prefers-reduced-motion`, modo `?texto=1`.
- Auditor estrutural que declara, na própria saída, o que **não** verifica.
- CI que de fato roda os três gates.

Isso é base de produto. Não é AAA.

---

## 3. Números desta data

```
HEAD                         269e104
notas / wikilinks / claims   84 / 672 / 267
audit estrutural             APROVADO · fontes externas NÃO verificadas
commits "Promove proposta"   18
diário de promoção           63 chaves · 10 promoted · 52 rejected · 1 stale
rejeições por árvore suja    43 / 52
policy-decisions             1304 · decisão efetiva 0
outcomes.jsonl               5421 · última linha 2026-08-17T21:23
fila autônoma                835 · queued 213 · rejected 261 · blocked 182 · completed 175
painéis em disco             607
árvore local                 4 arquivos sujos (+467/−77) em autonomy/generator
```

Distribuição de claims (267): `established` 164 · `refuted` 33 · `supported` 27 ·
`open` 14 · `model-dependent` 12 · `hypothesis` 7 · `speculative` 6 · `operational` 3 ·
`out-of-scope` 1.

`verified_at` mais recente no corpus: **2026-07-31**. Nenhuma verificação de fonte em
agosto. 18 promoções em agosto; 17/18 não tocaram `updated`.

---

## 4. Achados, por consequência

### P0 — o produto mente, corrompe, ou queima trabalho pago

**P0-1 · Árvore suja recusa promote e o diário torna isso permanente.**
`promoter.py` exige working tree limpa. `autonomy.py` marca `rejected` (terminal).
Replay devolve `already_promoted`. Medido: 43 das 52 rejeições do diário são
"árvore de trabalho suja". As quatro mais recentes (24–25/08) morreram no **diff
local desta sessão**. Quórum pago, patch aprovado, corpus intacto, chave morta.

**P0-2 · Falha de assimilação ainda devolve `outcome="promote"`.**
`worker.py:855–860`: qualquer `Exception` na promoção vira `ExecutionOutcome("promote",
…)`. A tarefa completa como sucesso. A UI e a métrica mentem.

**P0-3 · Quatro corrupções já estão no corpus canônico.**

| commit | dano | arquivo |
|---|---|---|
| `044ed7a` | LaTeX `\operatorname{Tr}_E\! ig[` | `Física/Fundamentos de Mecânica Quântica e Sistemas Abertos.md:60` |
| `3ff4686` | título canônico `fünfdimensionale` → `cinco-dimensional` | `Física/Cordas, Dimensões Extras e Holografia.md:82` |
| `4431a2a` | ISBN `978-0-226-61865-4` removido | `Metodologia/Filosofia da Ciência.md:68` |
| `062b7fc`, `1e59546` | ata de painel no corpo da nota | `Seleção Natural Cosmológica.md:14`, `Complexidade Computacional.md:47` |

Nenhuma é stub. Todas passaram no auditor estrutural. O gate não vê LaTeX, título
canônico nem vazamento de runtime para o corpus.

**P0-4 · Diff local não commitado bloqueia o ciclo inteiro.**
`generator.py` +329, `test_autonomy.py` +208, `worker.py` +5, `run_worker.py` +2.
Enquanto existir, P0-1 continua verdadeiro. Stash ou commit **hoje**, ou o Promoter
continua incinerando aprovações.

### P1 — o ciclo produz movimento sem rigor

**P1-1 · As 18 promoções não aumentaram o conhecimento.**
0 claims novos, 0 wikilinks novos, 2 trocas de status sem fonte nova
(`open→speculative`, `open→hypothesis`), 2 injeções de metadado operacional, 4
corrupções. O loop aprendeu a fechar painel. Ainda não aprendeu a editar ciência.

**P1-2 · Política e regime se contradizem, e a Política vence no papel.**
`knowledge/Política Epistêmica e de Linkagem.md` (`updated: 2026-07-18`) exige
revisão humana para alteração científica substantiva. `AGENTS.md` transfere isso ao
quórum desde 2026-08-03 e declara a Política soberana. As 18 promoções operam no
regime do AGENTS e violam o item 5 da Política.

**P1-3 · Identificador não é conferido por máquina.**
`tools/audit.py` declara isso na saída. 91 DOI / 71 arXiv / 34 ISBN no texto.
Regra 1 do AGENTS é honra de processo. Um identificador plausível e errado passa.

**P1-4 · ADR-007 está ligada e é teatro.**
`policy.json` quorum-v2 desde 17/08. 1304 decisões, **todas `decision: null`**.
`run_worker.py` sobe `max_calls` ao teto diário (~91k). `EXPAND_BUDGET` nunca
dispara. `SWITCH` não tem ramo no worker.

**P1-5 · M0 canônico congelou em 17/08.**
`outcomes.jsonl` parou. A operação de 18–24/08 vive em `tasks.json`, painéis e
`policy-decisions.jsonl`. `make outcomes` descreve o passado.

**P1-6 · ADR-006 não tem caminho de execução.**
`CodePatch` e `validate_code` existem. Não há `promote()` de código, não há
`TaskKind`, não há gerador. `validate_code` tem zero chamadas fora do próprio
arquivo.

### P2 — o Atlas e o corpus ainda não são produto fechado

**P2-1 · ADR-005 aceita, não implementada.** Operação ainda entra na projeção
(`app.py` `with_runtime_quorum`); mudança de fingerprint ainda faz `location.reload()`.

**P2-2 · `atlas.ts` 2808 linhas, `main.ts` 1250, `composeLayout.ts` 770 — sem teste
próprio.** 564 vitest cobrem geometria e contrato, zero regressão visual, zero E2E.

**P2-3 · Modo texto não carrega o corpo da nota.** Substitui a cena, lista metadados
e ligações, não entrega leitura. Sem axe/pa11y.

**P2-4 · Camada 1 é 65/65 claims `established`.** Matemática + Estatística sem um
único `open`/`supported`. Ou o formalismo está perfeito, ou o vocabulário não está
sendo usado. 61% do corpus inteiro é `established` sem verificação de fonte em agosto.

**P2-5 · Template partido.** Notas de fundamento (Matemática, CS, Vida, Segurança)
nascem completas. Física e IA são ensaio contínuo sem Finalidade / Escopo negativo /
Pré-requisitos. 2 notas operacionais de IA sem tabela de claims. `review_after`
ausente em `IA/Orçamento e Roteamento de Cotas.md`.

**P2-6 · Gerador uncommitted pode fabricar demanda** (`_note_extension`,
`_undeclared_moc_growth`). Contraria o espírito da regra 4 se nascer nota sem
lacuna declarada.

### P3 — higiene

God-modules (`orchestrator` 1802, `operational` 1214, `atlas` 2808). 607 painéis
sem GC. `runtime/proposals/` vazio. Diário 10 `promoted` vs 18 commits de promoção.
Versão `0.1.0`. CI sem `pip-audit`/`pnpm audit` no gate.

---

## 5. O que as auditorias anteriores acertaram — e o que envelheceu

| achado antigo | agora |
|---|---|
| A-1 corpus congelado | **fechado e invertido**: 18 promoções, qualidade ruim |
| A-2 65% escalate | parcialmente mitigado (M1/M2 no código); custo de fechamento ainda alto |
| A-6 árvore suja | **reaberto**: voltou a ser a causa dominante do diário |
| A-9 61% established | **aberto**, e agora com promoções que não verificam fonte |
| Baseline 0 promoções | superado em volume, não em rigor |
| ADR-003 M0–M2 | no código; M0 legado defasado; M3/M5 não |

A lição que se repete: cada guarda corrigiu a causa daquele dia e revelou a
seguinte. A causa de hoje não é "não promove". É **promove o errado e recusa o
certo por estado do operador**.
