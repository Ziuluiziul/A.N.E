# Baseline de promoção — 2026-08-16

Referência anterior à ativação do caminho nativo quórum → promoção.
Todos os números foram apurados do `runtime/state` em 2026-08-16, antes
da ativação do `policy.json` (que acontece na subida do worker).

## Números de referência

| Métrica | Valor |
|---|---|
| Desfechos no ledger | 2737 |
| Votos `ok` | 475 |
| Propostas `ok` | 258 |
| Propostas promovidas | 0 |
| `runtime/proposals/` | vazio |
| `sem-diversidade` (24h) | 88 de 206 (43%) |
| `rate-limit` | 324 |
| `votos-validos-insuficientes` (tentativas) | 173 |
| `orcamento-esgotado` | 162 |
| `envelope-invalido` | 142 |
| `schema-invalid` (votos) | 270 |
| Fila: total / completed / rejected / blocked / retry_wait / running | 297 / 80 / 181 / 28 / 7 / 1 |
| Rejeição dominante | `quorum_capacity:call_budget — 5 chamadas para 9.7 por fechamento` |
| `VAULT_WORK_MAX_CALLS` (default) | 6 |
| `VAULT_WORKER_CONCURRENCY` (default) | 3 |
| Quórum mínimo | 3 votos válidos, 2 provedores, 2 famílias |

## Interpretação

1. **O loop produz, mas nada sobe.** 258 propostas `ok` sem uma única
   promoção: o Promoter existe (`vault/promotion/promoter.py`) e é testado,
   mas nenhum caminho de execução o invoca. O corpus ganhou 3 commits
   manuais desde a migração (b2e3d8c, 65a4d53, f91591a).
2. **O gargalo não é o quórum em si.** 43% dos desfechos recentes são
   `sem-diversidade` (mesmos provedores/famílias tentando votar), e a fila
   está exaurida. O teto de chamadas por fechamento (6) fica abaixo da
   estimativa (≈9.7), então fechamentos válidos são raros.
3. **Os 258 patches históricos formam a coorte `pre-autonomous-promotion`.**
   Após a ativação, só fechamentos novos entram no Promoter; os históricos
   ficam como benchmark e não são aplicados retroativamente.

## Evidência

- `evidencia/outcomes.jsonl` — ledger de desfechos (2737 linhas).
- `evidencia/tasks.json` — fila autônoma (297 tarefas).
- `evidencia/quotas.json`, `evidencia/endpoints.json` — estado de cotas e descoberta.
- `evidencia/commits-do-corpus.txt` — histórico do corpus desde 2026-07-28.

## Próxima medição

Repetir esta auditoria depois de (a) ativação do caminho nativo e (b)
implementação do orçamento adaptativo (A'): esperado ≈9.7 chamadas por
fechamento, soft 12–16, teto 24. O contraste com esta linha de base
responde se a promoção passou a acontecer sem inflar custo.