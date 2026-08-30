# ADR-007 — Orçamento adaptativo por política (A')

**Data:** 2026-08-17 · **Estado:** aceita em direção
**HEAD na decisão:** `efcd858`
**Decidida por:** mantenedor, com a condição do primeiro fechamento autônomo real
(`0d77a1a`) cumprida como ensaio de integração.
**Relacionadas:** [ADR-006](ADR-006-o-sistema-edita-o-proprio-codigo.md) (promoção
autônoma), auditoria de [2026-08-16](audits/2026-08-16-baseline-promocao/AUDITORIA.md)
(2737 desfechos: 250 sem-diversidade, 162 orcamento-esgotado, 346
votos-validos-insuficientes), [evidência da primeira promoção](audits/2026-08-17-primeira-promocao/evidencia.json).

## A decisão

O orçamento de chamadas deixa de ser só o teto fixo do processo (`work_max_calls`)
e passa a ser **decisão de política sobre observáveis**, com a tabela determinística
em dado (bloco `budget` de `runtime/promotion/policy.json`), não em arquitetura.
O teto duro de **24 chamadas** permanece autoridade externa, em código: nenhuma
política pode cruzá-lo, e mudá-lo é decisão humana.

## Por que

A baseline pós-ativação mostrou os custos que o orçamento fixo impõe:

- **250 desfechos sem-diversidade** — painel impossível, mas o proponente já foi
  pago; a diversidade só era conferida depois da chamada.
- **162 orcamento-esgotado** — fechamento viável cortado no meio do processo por
  um teto que não sabe que o quórum está perto de fechar.
- O teto macio (12–16) e a concorrência efetiva (`max_calls // 4`, que com
  `work_max_calls=6` reduz a concorrência pedida de 3 para 1) eram constantes de
  código, não resultado de política.

## A tabela de decisão

Observáveis (todos do estado vivo, sem I/O novo no ciclo):

| observável | fonte |
|---|---|
| `expected_calls` | `CapacityHints.expected_calls_per_closure` (ledger M0) ou 4.0 |
| `remaining_calls` | `process_budget.max_calls − ledger.run_calls` |
| `eligible_diversity` | perfis usáveis, chamáveis, fora dos tentados, que contam para quórum |
| `schema_failure_rate` | votos `schema_valid=False` nos últimos `observation_window` painéis |
| `valid_votes` / `required_votes` | 0 / 3 no pré-ciclo (STOP só vale no meio do ciclo) |
| `observed_sample_size` | total de votos contados na janela |
| `closure_probability` | derivada: 1.0 se viável e cabe, senão 0.0 se inviável, senão fração |

Decisões, na ordem (impossibilidade > inaptidão > escassez > suficiência):

1. **DEFER** — `eligible_diversity` não cobre 2 provedores e 4 endpoints: nenhuma
   chamada gasta; a tarefa volta à fila inteira (`backpressure`).
2. **SWITCH** — falha de schema persistente (janela ≥ 8, taxa ≥ 0.5): recomenda a
   troca de endpoint; o mecanismo de troca já existe (`failed_endpoint` no gerador,
   `_without_attempted` no executor) — aqui a regra fica explícita e registrada.
3. **EXPAND_BUDGET** — fechamento viável e `remaining < expected + margin`:
   estende o teto do ciclo para `min(24, remaining + expected + margin)`, nunca
   além do ceiling e nunca abaixo do teto do processo. Vale uma vez: como
   `remaining` decresce, a segunda expansão não alcança o processo; o gasto total
   fica limitado por `processo + expected + margin < 24`.
4. **STOP** — `valid_votes ≥ required_votes`: não planejar mais chamadas.

## Onde a decisão entra

- **`defer_reason`** (admissão): EXPAND faz a tarefa ser admitida — tanto o cheque
  de orçamento quanto a estimativa de capacidade passam a usar o teto efetivo.
- **`can_start`** (seleção da fila): sem orçamento no processo, a tarefa só começa
  se a política expandir.
- **`_quorum`** (execução): DEFER devolve `backpressure` antes do orquestrador;
  EXPAND vira o orçamento do orquestrador. A reutilização de painel fechado
  (quinto invariante) acontece antes da consulta — nunca se consulta política
  sobre um fechamento já decidido.
- **Concorrência do worker**: deriva do orçamento do processo (cada quórum exige
  ~4 chamadas), nunca do ceiling da política — o ceiling limita a *expansão* de um
  fechamento, não o planejamento; usá-lo como teto cortaria o que o mantenedor já
  autorizou.

Toda decisão vai para `runtime/promotion/policy-decisions.jsonl` (ledger
append-only) com `task_id`, `policy_version`, decisão, razão, observáveis e
orçamento efetivo.

## Migração da política

`PromotionPolicy.activate()` promove schema 1 → 2 **no lugar**, preservando o
`activated_at` original: o contrato de causalidade do diário de promoções (decisão
posterior à ativação) não pode mudar de referência só porque o orçamento ganhou
regras. O bloco `budget` entra com os defaults de código. A promoção anterior
(`0d77a1a`, `quorum-v1`) permanece coorte válida; entradas novas citam
`quorum-v2`.

## O que fica de fora (explícito)

- **SWITCH age por recomendação registrada**: o mecanismo operacional já existe; a
  tabela o formaliza, não o substitui.
- **STOP é no-op no pré-ciclo**: o orquestrador já planeja exatamente três votos;
  a regra existe para quando o ciclo ganhar planejamento aberto.
- **O ceiling 24 não é negociável por dado**: `BudgetPolicy` recalcula qualquer
  valor acima dele para 24.
- **`outcomes.jsonl` (ledger legado) não recebe nada novo**: o ciclo vivo registra
  em `tasks.json`, painéis e `policy-decisions.jsonl`; o legado segue como baseline.

## Medição de sucesso

- `calls/closure` cai (DEFER evita o proponente pago sem painel).
- `closures/time` sobe (EXPAND fecha o que o teto cortava).
- Concorrência efetiva preserva o pedido do mantenedor (orçamento do processo).
- O ledger de decisões permite auditar cada expansão: por que, quanto, para quem.