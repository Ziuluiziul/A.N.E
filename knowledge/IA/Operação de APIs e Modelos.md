---
title: Operação de APIs e Modelos
aliases: [API-Google, API-Groq, API-NVIDIA, Janela-Contexto-Entrada-Saída-Tokens]
domain: ia
kind: nota
status: active
epistemic_status: operational
updated: 2026-08-16
verified_at: 2026-07-16
review_after: 2027-01-16
---

# Operação de APIs e modelos

> [!warning] Snapshot histórico
> Esta nota registra observações feitas na máquina anterior (LMDE 7, até 27/07/2026)
> e cita caminhos como `~/.config/vault-ia/` que **não existem mais**. Vale como
> registro do que foi medido e das lições operacionais, não como estado atual.
> Reconfira na fonte viva antes de reafirmar qualquer número.

## Regra de fonte

Catálogos de modelos e limites são dados voláteis. A fonte de verdade é, nesta ordem:

1. endpoint oficial autenticado de catálogo;
2. documentação/model card oficial do modelo;
3. configuração local do broker como **política**, não como descrição do provedor;
4. esta nota apenas como snapshot histórico.

Não inferir janela de contexto, output máximo, modalidade ou quota a partir do nome do modelo.

## Snapshots e revalidação de 16/07/2026

| Provedor | Fonte | Resultado retido |
|---|---|---|
| Google Gemini | GET autenticado em `generativelanguage.googleapis.com/v1/models` | HTTP 200, 19 IDs; os três IDs locais atuais foram observados. |
| NVIDIA NIM | GET autenticado em `integrate.api.nvidia.com/v1/models` | HTTP 200, 119 IDs; os dois IDs locais atuais foram observados. |
| Groq | snapshot `~/.config/vault-ia/catalogs/groq-2026-07-16.txt` | 17 IDs; a reconsulta atual não foi promovida porque não terminou com resposta autenticada aprovada. |

Locks dos snapshots externos sem credenciais: Google SHA-256 `3e428720392b39222495ac0c6d42e00819f7a06d5bf3a8169dfef48b780bb1e4`; Groq `f608656bd633cba7e64e80299bc1c866f3f98d1911a5b62d243e1b6f141e1e66`; NVIDIA `710b4cd8ee94ba4b7c57207e551fed3e9b5559449531064b12dcc7673064f1f6`. Contagem e presença no catálogo não estabelecem janela, quota, qualidade nem compatibilidade de recursos.

## Confronto com a allowlist local

### Google

| ID local atual | Catálogo autenticado `v1` | Roteamento candidato |
|---|---|---|
| `gemini-2.5-flash` | presente | `v1`, por ser ID estável. |
| `gemini-3.1-flash-lite` | presente | `v1`, por ser ID estável. |
| `gemma-4-26b-a4b-it` | presente | `v1`, por ser ID estável. |

O adapter candidato enviava IDs contendo `preview` a `v1beta` e IDs estáveis a `v1`, depois de validação lexical fechada. Os três IDs observados em 16/07/2026 eram estáveis. Essa regra era comportamento do worktree candidato e nunca chegou a ser integrada ao broker principal; ambos foram descontinuados na migração de 2026-07-28.

### NVIDIA

| ID local atual | Presença na reconsulta autenticada | Decisão |
|---|---|---|
| `mistralai/mistral-large-3-675b-instruct-2512` | presente | permitido pela política local; recursos precisam de testes separados. |
| `deepseek-ai/deepseek-v4-flash` | presente | permitido pela política local; nenhum alias ou sucessor é inferido. |

### Groq

| ID local atual | Presença no snapshot lockado | Estado |
|---|---|---|
| `llama-3.1-8b-instant` | presente | **DEPRECIADO pela Groq — desliga 2026-08-16.** Candidato a substituto: `openai/gpt-oss-20b` (requer testes mínimos antes de habilitar). |
| `llama-3.3-70b-versatile` | presente | **DEPRECIADO pela Groq — desliga 2026-08-16.** Candidatos a substituto: `openai/gpt-oss-120b` ou `qwen/qwen3.6-27b` (requerem testes mínimos antes de habilitar). |
| `openai/gpt-oss-120b` | presente | permitido pela política local e atribuído a Groq, não NVIDIA. Candidato a substituto oficial do 70b-versatile (já na allowlist; compatibilidade de recursos exige testes separados). |

A allowlist efetiva é o conjunto de chaves de `limits.json`: modelo ausente é recusado antes da criação do trace. O snapshot Groq confirma presença histórica na coleta de 16/07/2026; como a reconsulta atual não foi aprovada, esta nota não declara continuidade do entitlement ao vivo.

### Depreciação Groq confirmada em 2026-07-17

A Groq anunciou (comunicado de 2026-06-17) a depreciação de `llama-3.1-8b-instant` e `llama-3.3-70b-versatile`, com **desligamento em 2026-08-16**, atingindo os tiers **free e developer** (os usados por esta automação). Fonte: documentação oficial de depreciações da Groq (`console.groq.com/docs/deprecations`), conferida em 2026-07-17. Substitutos indicados: `openai/gpt-oss-20b` (para o 8b) e `openai/gpt-oss-120b` ou `qwen/qwen3.6-27b` (para o 70b).

**Pendência herdada, hoje sem objeto:** na máquina anterior, os dois IDs eram chaves vivas em `~/.config/vault-ia/limits.json`, e trocá-los pelos substitutos antes do desligamento era obrigação operacional — sem isso, a automação falharia fechado ao rotear para modelo inexistente. Com o pipeline descontinuado em 2026-07-28, não existe allowlist a corrigir e a obrigação não tem mais destinatário.

O que sobrevive é o prazo do provedor, não a tarefa: se alguma automação futura reaproveitar esta lista, `llama-3.1-8b-instant` e `llama-3.3-70b-versatile` deixam de existir em 2026-08-16 e precisam ser substituídos **antes** de entrar em uso, contra o catálogo vivo da Groq — não contra esta nota.

## Janela e output

A tabela antiga de context windows foi removida porque não apresentava URLs/versões por linha e misturava input, contexto total e output máximo. Para registrar um limite:

- citar URL oficial;
- registrar ID exato e versão/data;
- distinguir `input_max`, `context_total` e `output_max`;
- indicar modalidade e endpoint;
- testar erro de fronteira em ambiente controlado quando possível.

Sem esses campos, o valor não entra no corpus ativo.

## Compatibilidade e testes mínimos

Antes de habilitar um modelo:

1. confirmar ID no catálogo;
2. executar chamada sem ferramenta, com saída curta;
3. testar streaming se usado;
4. testar tool calling e schema separadamente;
5. medir contagem de tokens pelo método do provedor;
6. registrar erro 429/headers sem expor segredo;
7. fixar fallback de outro provedor somente quando a semântica necessária for compatível.

## Segurança

- chaves não aparecem no Vault, comandos ou traces;
- snapshots não incluem headers/respostas sensíveis;
- lista de modelos é tratada como dado não confiável;
- alias não encontrado falha fechado;
- modelos preview nunca são fallback silencioso para tarefas críticas.

## Relações

- [[Orçamento e Roteamento de Cotas]] <!-- relation:operational -->
- [[Segurança, Guardrails e Avaliação]] <!-- relation:prerequisite -->
- [[Avaliação e Proveniência de Sistemas de IA]] <!-- relation:operational -->
- [[RAG e Contexto Longo]] <!-- relation:operational -->
- [[Modelos Multimodais e Agentes Visuais]] <!-- relation:operational -->
- [[MOC — Inteligência Artificial]] <!-- relation:navigation -->
