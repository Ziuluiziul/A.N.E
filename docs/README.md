# Documentação do A.N.E.

Este diretório guarda decisões de arquitetura, o guia do Workspace e as
specs de provedor, SSE, worker e X MCP.
Não é diário de sessões, nem arquivo de handoffs.

| Documento | Papel |
| --- | --- |
| [ADR-001](ADR-001-paleta-oklch.md) | Paleta OKLCH da cena |
| [ADR-002](ADR-002-painel-como-no.md) | Painel como nó |
| [ADR-003](ADR-003-instrumentacao-antes-de-morfogenese.md) | Instrumentação antes de morfogênese |
| [ADR-004](ADR-004-posicao-derivada-da-relacao.md) | Posição derivada da relação |
| [ADR-005](ADR-005-propriedade-do-estado-operacional.md) | Estado operacional como propriedade |
| [ADR-006](ADR-006-o-sistema-edita-o-proprio-codigo.md) | O sistema edita o próprio código |
| [ADR-007](ADR-007-orcamento-adaptativo-por-politica.md) | Orçamento adaptativo por política |
| [GOOGLE-WORKSPACE.md](GOOGLE-WORKSPACE.md) | OAuth e leitura mínima do Workspace |
| [PROVEDORES.md](PROVEDORES.md) | google, groq, nvidia: página oficial versus o que o vault declara |
| [ATLAS-SSE.md](ATLAS-SSE.md) | Contrato HTTP SSE do tecido runtime (não MongoDB Atlas) |
| [WORKER.md](WORKER.md) | `VAULT_AUTONOMOUS_WORKER`: quem spawna, default, teto de chamadas |
| [X-MCP.md](X-MCP.md) | Plugin Cursor / Grok Bot; não é contrato do vault |

Este diretório não é diário de sessões. Handoff, CICLO e PROMPT ficam fora
do índice. Docs não promovem handoff a spec.

Registros estruturados de auditoria do produto ficam em `audits/`.
O corpus e a política editorial moram em `knowledge/`, nunca aqui.
