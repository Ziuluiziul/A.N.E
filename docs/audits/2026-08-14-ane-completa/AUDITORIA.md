# Auditoria completa do A.N.E. — 2026-08-14

**Auditor:** Claude Opus 5 · **HEAD:** `30dd91b` · **Escopo:** todo o repositório
**Antecessoras:** `2026-08-05-atlas-geral` (cena e controle) e `2026-08-09-ane-geral`
(gate alfa). Esta é a primeira que cobre o circuito inteiro — corpus, código, pipeline,
provedores, cena e governança — depois do ciclo de doze commits de 2026-08-14.

**Método.** Tudo abaixo é medido no HEAD acima, com os serviços no ar. Nada é estimado.
Onde a medição não existe, a linha diz que não existe em vez de inferir. A evidência
bruta está em `evidencia/`; os achados ranqueados, em [`ACHADOS.md`](ACHADOS.md).

**O que esta auditoria não faz.** Não verifica verdade científica, não resolve DOI, arXiv
ou ISBN, e não confere se identificador bate com título canônico. `tools/audit.py`
declara isso na própria saída, e a limitação é herdada aqui. Julgamento epistêmico
continua sendo humano.

---

## 1. Veredito

| eixo | estado |
|---|---|
| Corpus | íntegro e **congelado** |
| Código e gates | verdes, sem defeito conhecido em aberto |
| Cena 3D | funcional e verificada ao vivo |
| Pipeline de conhecimento | **executa, delibera e não entrega** |
| Instrumentação | recém-nascida, já produzindo sinal |
| Governança | decisões registradas; uma pendência de mantenedor há cinco sessões |

O sistema faz quase tudo que promete, menos a única coisa para a qual existe: **em dez
dias de operação contínua, nada chegou ao corpus.**

---

## 2. Corpus

```
84 notas · 6.691 linhas · 672 wikilinks · 267 claims
wikilinks quebrados 0 · sem relation: 0 · fora do vocabulário 0
notas órfãs 0 · MOCs vazios 0 · frontmatter inválido 0
claims inválidos 0 · IDs duplicados 0
ESTRUTURA APROVADA
```

Última alteração: `65a4d53`, de **2026-08-04** — dez dias atrás.

**Distribuição por status.** `established` 164 · `refuted` 33 · `supported` 27 · `open`
16 · `model-dependent` 12 · `hypothesis` 6 · `speculative` 5 · `operational` 3 ·
`out-of-scope` 1.

Duas observações, nenhuma delas defeito estrutural:

- **61% dos claims são `established`.** Num corpus cuja política trata identificador não
  resolvido como motivo de omissão, essa proporção é alta o bastante para merecer
  amostragem humana — o auditor não tem como distinguir "estabelecido e verificado" de
  "estabelecido e nunca conferido".
- **33 claims são `refuted`.** A Política é explícita: ausência de evidência não implica
  `refuted`, que exige contradição efetiva. Verificar as 33 é trabalho de fonte, fora do
  alcance de qualquer script.

Distribuição por domínio: Física 17 · Matemática 16 · IA 10 · Computação 9 · Estatística
7 · Cognição 5 · Metodologia 5 · Ciências da Vida 4 · Segurança 4 · Pontes 3 · Dados 2 ·
raiz 2.

---

## 3. Código

| área | linhas | unidades |
|---|---:|---|
| `backend/src/vault` | 13.034 | 10 pacotes |
| `frontend/src` | 30.241 | 100 módulos, 43 de teste |
| `tests/` | 13.012 | 35 arquivos |
| `providers/` | 3.458 | 5 adaptadores |
| `tools/` | 2.597 | 13 scripts |
| `integrations/` | 346 | Google Workspace |
| `docs/` | 8.831 | 26 documentos |

Pacotes do backend: `autonomy`, `cognition`, `control`, `corpus`, `events`, `promotion`,
`proposals`, `quorum`, `telemetry`, `work`.

**Gates, todos verdes no HEAD:** auditoria aprovada · **626 pytest** · **557 vitest** ·
ruff limpo · mypy limpo em 125 arquivos · ESLint limpo.

A razão teste/código é de 13.012 para 13.034 linhas no backend e 9.578 para 20.663 no
frontend. É cobertura alta em linha; não é garantia de cobertura de ramo, e esta sessão
produziu duas provas disso — ver §8.

---

## 4. Pipeline de conhecimento — onde o sistema falha

### 4.1 A fila

```
255 tarefas — 118 queued · 52 completed · 47 rejected · 21 retry_wait · 14 blocked · 3 running

corpus_review        45   31 queued ·  9 blocked · 3 running · 1 completed · 1 rejected
divergence_review   134   73 queued · 36 rejected · 20 retry_wait · 5 blocked
endpoint_diagnosis   47   47 completed
proposal_revision    29   14 queued · 10 rejected · 4 completed · 1 retry_wait
```

A fila está **saudável pela primeira vez**: 14 bloqueadas contra as 80 do início do dia,
e as `corpus_review` voltaram a circular. Isso é resultado direto dos seis commits de
correção do ciclo.

Mas **134 das 255 tarefas são `divergence_review`**, e 73 delas estão na fila sem nota
herdada — lixo anterior ao freio de `ddf465e`, que o worker corretamente não pega e que
ninguém remove. Metade da fila é inventário morto.

### 4.2 Os painéis

```
162 painéis — 103 escalate · 50 reject · 5 promote · 1 revise
24 com patch aplicável
0 promoções efetivas · runtime/proposals/ vazio
```

**A taxa de escalonamento é de 65%** (103 de 159 decididos). O painel, na maioria
esmagadora das vezes, não consegue concluir. Essa é a métrica mais preocupante do
sistema e nenhuma correção deste ciclo a atacou.

### 4.3 A janela de promoção, depois de `d2765e8`

O commit trocou "o HEAD andou?" por "**o alvo mudou?**". O efeito é total:

```
24 patches em disco · 24 com alvo intacto desde a base · 1 com base == HEAD
```

Antes eram zero promovíveis; agora são 24 pela regra da janela. **A correção funciona.**

O que ela revela é desconfortável: dos 24, **23 decidiram `escalate`** e não são
promovíveis por falta de decisão. O único com decisão `promote` é o painel
`59e32f5df5d5` — o stub que substituiria uma nota de 73 linhas por dez linhas com
reticências literais. Confirmei que a guarda de `30eedfc` continua recusando:

```
RECUSADO → replace reduz Física/Gravidade Quântica em Loop e Cosmologia Quântica.md
           sem allows_reduction: claims 5→1, wikilinks 5→0, bytes 4672→603
```

Ou seja: **o único candidato à promoção que o sistema já produziu é um que não deve ser
promovido.** As duas guardas funcionam; o que falta é matéria-prima aprovável.

---

## 5. Provedores e capacidade

142 endpoints inventariados: **50 `ok`, 74 `unavailable`, 14 `auth`, 4 `error`**.

| provedor | ok | unavailable | auth | error |
|---|---:|---:|---:|---:|
| nvidia | 21 | 54 | — | 3 |
| google | 13 | 8 | — | 1 |
| groq | 8 | — | — | — |
| ollama | 7 | 12 | — | — |
| openrouter | 1 | — | 14 | — |

O ledger de desfechos (1.691 registros) mostra a causa dominante por endpoint. **A
natureza do gargalo mudou durante o dia:**

- No início: conta Google sem crédito, com 4 tentativas queimadas por tarefa dentro da
  mesma conta morta.
- Agora: **`orcamento-esgotado`** domina onze endpoints da nvidia, cada um com 12 a 19
  tentativas e taxa de sucesso zero. O teto de 5 chamadas por lote é consumido antes de o
  painel fechar.

Endpoints que **nunca funcionaram** e continuavam elegíveis:

| endpoint | tentativas | ok | causa |
|---|---:|---:|---|
| `nvidia/meta/llama-3.2-3b-instruct` | 13 | 0% | tempo esgotado em 13 de 13 |
| `nvidia/openai/gpt-oss-120b` | 12 | 0% | indisponível em 12 de 12 |
| `openrouter/nvidia/nemotron-3.5-lightning:free` | 51 | 0% | credencial BYOK em 49 |

O último **já foi corrigido** em `3fd3f09`: o OpenRouter é suspenso no boot com
`openrouter suspenso: … BYOK`. Os dois primeiros seguem elegíveis.

Na aptidão por papel, dois endpoints entregam **0% de votos utilizáveis** em 9
observações cada — `google/gemma-4-26b-a4b-it` e `google/gemma-4-31b-it` —, e
`groq/qwen/qwen3.6-27b` fica em 33–34% em 71 observações somadas. São candidatos naturais
a saírem da seleção assim que o M4 existir.

**Custo de fechamento: 9,6 chamadas por painel decidido** — 1.531 chamadas para 160
decisões.

---

## 6. Cena 3D

Verificada ao vivo em `127.0.0.1:5173`, com captura real (`capturas/`):

```
1.026 nós · 2.207 arestas
régua de âncoras: conhecimento 15 · provedores 5 · trabalhadores 7
```

A régua foi refeita neste ciclo (`d8b5f5a`): nome inteiro no lugar do monograma de duas
letras, cabeçalho de grupo visível, e só a lista longa rola — provedores e trabalhadores
ficam presos e sempre visíveis. Verificada a 1280×720 e 1440×1000.

O backend, o worker e o Atlas estavam no ar durante toda a auditoria, com o worker
processando a fila em paralelo às medições.

---

## 7. Governança e documentação

Doze commits em 2026-08-14, de três agentes distintos (Claude Opus 5, Grok 4.6 e um
terceiro builder), sem colisão e sem sobrescrita — cada um commitou apenas os próprios
arquivos, nomeados um a um.

Documentos de decisão: `ADR-001` (paleta), `ADR-002` (painel como nó), **`ADR-003`**
(instrumentação antes de morfogênese, decidida neste ciclo por troca multimodelo).
O relatório que a fundamenta e a proposta original estão versionados ao lado dela.

Handoffs do ciclo: `HANDOFF-GROK-4.6-2026-08-14.md` e
`HANDOFF-CLAUDE-OPUS-5-2026-08-14.md`, encadeados.

**Pendências de árvore:** cinco arquivos modificados de um builder que não voltou —
`backend/src/vault/app.py` e quatro módulos de layout do frontend — e dois handoffs de
2026-08-13 nunca rastreados. Os cinco arquivos barram `validate()` e `promote()`, que
exigem árvore limpa. Está aberto há **cinco sessões**.

---

## 8. Confiabilidade da própria verificação

Três defeitos deste ciclo passaram por suíte verde, e vale registrar o padrão:

1. **A aptidão do M0 respondia 100% para todo endpoint** — lia os votos de
   `decision.json`, que só lista os contados. Pergunta circular; nenhum teste a pegaria,
   porque a construção estava correta.
2. **O `--json` do M0 quebrava na primeira execução** — `vars()` não funciona em
   dataclass com `slots=True`. A suíte cobria a construção dos registros, não a
   serialização.
3. **O relatório da frente morfogênica afirmou independência entre revisores** que não
   existia: os dois `approve` eram do mesmo provedor. Erro de leitura humana, não de
   código.

Nenhum foi encontrado por teste. Os três foram encontrados **ao usar a coisa** — rodando
o comando, lendo a saída, conferindo a fonte. É o mesmo princípio que a casa já aplica a
render ("captura é gate") e que vale igual para ferramenta de linha de comando.

---

## 9. O que mudou neste ciclo

| commit | efeito verificado |
|---|---|
| `d32ea67` | crédito esgotado suspende o provedor inteiro; blocked operacional reabre |
| `30eedfc` | `replace` destrutivo exige `allows_reduction`; `--dry-run` roda as guardas reais |
| `1328e36` | envelope inválido não aposenta a nota; teto de saída do proponente em 8192 |
| `ddf465e` | divergência só nasce de painel de corpus com nota herdada |
| `d8b5f5a` | régua com nome e grupos separados |
| `227102b` | frente morfogênica registrada; ADR-003 |
| `5077733` | M0: 1.691 eventos legíveis de volta, três superfícies |
| `d2765e8` | janela de promoção por alvo — 0 → 24 patches na janela |
| `3fd3f09` | OpenRouter impossível fora da seleção; voto ilegível não aposenta; prompt 48k |
| `30dd91b` | `--json` do ledger corrigido |

Todos verificados nesta auditoria contra o código e contra o estado de runtime.
