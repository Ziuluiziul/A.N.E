---
title: Orçamento e Roteamento de Cotas
aliases: [Orçamento-Cotas, Orçamento de Cotas — Agregação]
domain: ia
kind: nota
status: active
epistemic_status: operational
updated: 2026-07-16
verified_at: 2026-07-16
---

# Orçamento e roteamento de cotas

> [!warning] Snapshot histórico
> Esta nota registra observações feitas na máquina anterior (LMDE 7, até 27/07/2026)
> e cita caminhos como `~/.config/vault-ia/` que **não existem mais**. Vale como
> registro do que foi medido e das lições operacionais, não como estado atual.
> Reconfira na fonte viva antes de reafirmar qualquer número.

## Distinção fundamental

`limits.json` contém limites **locais de política**. Eles podem ser inferiores, superiores ou simplesmente diferentes da quota real do provedor. Apenas headers, console/endpoint oficial e erros observados podem estabelecer entitlement atual.

## Política local observada em 16/07/2026

Artefato observado: `~/.config/vault-ia/limits.json`, SHA-256 `3a494f1e7f8c30d91e5c93ed16b519924ab1b059e1a803627b423047bfd29f10`. A unidade de controle é **modelo**, não provedor agregado.

| Provider | ID local | RPM | RPD | TPM | TPD |
|---|---|---:|---:|---:|---:|
| Groq | `llama-3.1-8b-instant` | 30 | 14.400 | 6.000 | 500.000 |
| Groq | `llama-3.3-70b-versatile` | 30 | 1.000 | 12.000 | 100.000 |
| Groq | `openai/gpt-oss-120b` | 30 | 1.000 | 8.000 | 200.000 |
| Google | `gemini-2.5-flash` | 5 | 20 | 250.000 | não definido |
| Google | `gemini-3.1-flash-lite` | 15 | 500 | 250.000 | não definido |
| Google | `gemma-4-26b-a4b-it` | 15 | 1.500 | não definido | não definido |
| NVIDIA | `mistralai/mistral-large-3-675b-instruct-2512` | 30 | 10.000 | não definido | não definido |
| NVIDIA | `deepseek-ai/deepseek-v4-flash` | 30 | 10.000 | não definido | não definido |

O governador candidato aplica teto de utilização por prioridade: prioridade 1 até 80%, 2 até 85%, 3 até 90% e 4 até 95%. A prioridade 4 é reservada ao trabalho de maior criticidade; nenhuma classe autoriza consumir os 5% finais. Não existe janela mensal configurada. Somar os limites por modelo para anunciar uma “quota do provedor” seria inválido sem conhecer o escopo oficial da conta/projeto.

Reservas no SQLite evitam concorrência ultrapassar cada limite local configurado, mas não substituem reconciliação com respostas 429 nem implementam, por si, cota agregada de conta/projeto.

## Modelo de capacidade

Para `N` itens, batch médio `B`, taxa de retry `r` e fração de verificações adicionais `v`, uma estimativa inicial é

`C ≈ ceil(N/B) × (1+r+v)` chamadas.

Tokens esperados:

`T ≈ Σ_i(input_i + output_i + tool_i)`.

As variáveis devem vir de uma amostra medida. Usar “número de notas” fixo ou percentuais autorais sem custo por etapa produz orçamento fictício.

## Roteamento por risco

| Classe | Exemplos | Requisitos |
|---|---|---|
| alta | alteração científica, decisão de escrita, metadado bibliográfico | modelo/revisor mais forte, fonte primária, dupla checagem e aprovação humana. |
| média | síntese com fontes já validadas, normalização de estrutura | revisão amostral e gates determinísticos. |
| baixa | formatação, índice, deduplicação literal | modelo econômico ou execução determinística. |

Prioridade não é porcentagem fixa do Vault. Ela é atribuída por tipo de efeito e incerteza.

## Estratégia de execução

1. validar o catálogo antes de reservar quota;
2. estimar custo em amostra pequena;
3. reservar atomicamente;
4. limitar concorrência por provedor e não apenas por processo;
5. aplicar backoff com jitter em 429/5xx;
6. não retry em erro semântico permanente (ID inexistente, schema inválido);
7. registrar uso real sem conteúdo sensível;
8. reconciliar reservas expiradas;
9. parar quando o ganho marginal de evidência for insuficiente.

## Fallback

Fallback precisa preservar capacidade requerida: contexto, ferramentas, modalidade, structured output e política de dados. Trocar para outro modelo apenas porque “é grande” pode mudar comportamento e risco.

Ordem recomendada:

- mesmo provedor/modelo estável compatível;
- outro provedor com suite de regressão aprovada;
- fila/abstention para tarefa crítica;
- nunca degradar silenciosamente uma tarefa de alta prioridade.

## Métricas

- chamadas/tokens por etapa;
- sucesso, 429, 5xx e erro permanente;
- latência p50/p95/p99;
- retries e custo desperdiçado;
- qualidade da evidência por custo;
- taxa de fallback e divergência entre provedores.

## Relações

- [[Operação de APIs e Modelos]] <!-- relation:prerequisite -->
- [[RAG e Contexto Longo]] <!-- relation:operational -->
- [[MOC — Inteligência Artificial]] <!-- relation:navigation -->
