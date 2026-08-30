---
title: Fundamentos de Aprendizado de Máquina e Modelos de Linguagem
aliases: [Fundamentos de IA, Fundamentos de Machine Learning e LLMs]
domain: ia
kind: nota
status: active
epistemic_status: mixed
updated: 2026-07-16
verified_at: 2026-07-16
---

# Fundamentos de aprendizado de máquina e modelos de linguagem

## Função desta nota

Esta é a base conceitual para RAG, contexto longo, multimodalidade, agentes, avaliação e guardrails. Ela separa objetivo de treino, arquitetura, distribuição de dados, capacidade de inferência e comportamento operacional; nenhum desses níveis deve ser inferido automaticamente dos outros.

## 1. Aprendizado estatístico

Dado um conjunto `D={(x_i,y_i)}`, aprendizado supervisionado escolhe parâmetros `θ` para minimizar risco empírico regularizado,

`θ̂ = argmin_θ [ (1/n) Σ_i ℓ(f_θ(x_i),y_i) + λΩ(θ) ]`.

O objetivo real é risco na distribuição de uso, não apenas no conjunto de treino. Generalização depende de hipótese de amostragem, capacidade, regularização, otimização e distância entre distribuições. Dividir treino, validação e teste evita usar o teste como sinal de otimização; escolhas repetidas guiadas pelo teste vazam informação.

No aprendizado não supervisionado, objetivos como densidade, reconstrução, contraste ou clustering definem representações diferentes. “Descobrir estrutura” não garante que a estrutura seja causal, semanticamente desejável ou estável fora da amostra.

## 2. Redes neurais e otimização

Uma rede compõe transformações parametrizadas. Backpropagation aplica a regra da cadeia para calcular gradientes; otimizadores como SGD/Adam aproximam minimização em paisagens não convexas. Baixa loss de treino não prova ótimo global nem generalização.

Aspectos mínimos:

- inicialização e normalização afetam fluxo de gradiente;
- regularização explícita e implícita altera a solução selecionada;
- batch, schedule, precisão numérica e clipping fazem parte do experimento;
- seed única não mede variância;
- ablação deve alterar um fator por vez ou modelar interações.

## 3. Tokens, embeddings e atenção

Tokenização transforma texto em unidades discretas dependentes de vocabulário; contagem de tokens não é contagem de palavras e varia entre tokenizers. Embeddings mapeiam IDs para vetores; proximidade geométrica é aprendida pelo objetivo/dados, não ontologia universal.

Para matrizes de queries, keys e values, atenção escalada é

`Attention(Q,K,V)=softmax(QKᵀ/√d_k)V`.

Máscaras impõem causalidade ou visibilidade. Multi-head attention permite subespaços distintos, mas não garante interpretabilidade sem validação. Custo quadrático da atenção densa no comprimento motiva variantes esparsas, recorrentes, compressão e recuperação externa.

## 4. Modelagem autoregressiva e pós-treino

Um modelo causal fatoriza

`p(x_1,…,x_T)=Π_t p(x_t | x_<t)`.

Treino por next-token prediction estima condicionais na distribuição dos dados. Decodificação (`temperature`, top-p, beam/search) muda a distribuição de saída sem mudar os pesos. Uma resposta provável pode ser falsa; likelihood linguística não é verificador factual.

Pós-treino pode incluir instruction tuning, preference optimization, RLHF/RLAIF, ferramentas e políticas de sistema. Cada etapa altera comportamento observável, mas não fornece por si só garantias formais de veracidade, segurança ou obediência sob ataques adaptativos.

## 5. Escala, compute e eficiência

Leis de escala são regularidades empíricas em famílias e regimes medidos. Elas orientam alocação de parâmetros, dados e compute, mas extrapolação fora do regime é hipótese. Treino compute-optimal depende de qualidade/deduplicação dos dados, arquitetura, orçamento e objetivo.

Na inferência, distinguir:

- parâmetros residentes e memória de KV cache;
- prefill e decode;
- latência de primeiro token e throughput;
- quantização de pesos/ativações/KV;
- batching, speculative decoding e paralelismo;
- janela anunciada, janela efetivamente testada e qualidade ao longo do contexto.

## 6. In-context learning, RAG e ferramentas

Exemplos no prompt podem induzir comportamento sem atualização persistente de pesos; mecanismo e confiabilidade variam. RAG adiciona uma cadeia observável — consulta, recuperação, reranking, composição e geração — que pode melhorar atualização e atribuição, mas introduz falhas de recall, conflito, prompt injection e citação incorreta.

Ferramentas transformam o modelo em componente de um sistema. Autorização, schemas, idempotência, sandbox, confirmação e logs devem ser controles externos. Texto gerado não amplia capabilities.

Aplicações: [[RAG e Contexto Longo]] <!-- relation:extends --> e [[Segurança, Guardrails e Avaliação]] <!-- relation:extends -->.

## 7. Multimodalidade e agentes

Modelos multimodais alinham ou fundem representações de texto, imagem, áudio, vídeo e ação. Grounding exige métricas ligadas ao objeto/tarefa; fluência descritiva não prova localização ou causalidade. Agentes adicionam estado, planejamento, ferramentas e loops; erros se acumulam e feedback ambiental pode ser adversarial.

Aplicação: [[Modelos Multimodais e Agentes Visuais]] <!-- relation:extends -->.

## 8. Incerteza, calibração e avaliação

Softmax não é probabilidade calibrada por definição. Calibração compara confiança e frequência empírica sob uma distribuição; pode degradar com shift. Para geração aberta, avaliação combina métricas automáticas, testes funcionais, verificadores, julgamento humano cego e análise de erro.

Uma comparação profissional fixa:

1. hipótese e unidade experimental;
2. modelos/versões e templates;
3. datasets, licenças e contaminação;
4. seeds, orçamento e stopping;
5. métricas e intervalos de incerteza;
6. análise por subgrupo/idioma;
7. custo e latência;
8. critérios de falha e reprodução.

Aplicação: [[Avaliação e Proveniência de Sistemas de IA]] <!-- relation:extends -->.

## 9. Falhas de categoria a evitar

- benchmark alto ≠ competência universal;
- contexto longo nominal ≠ uso uniforme de todos os tokens;
- chain-of-thought aparente ≠ processo causal fiel;
- recuperação de documento ≠ entailment da resposta;
- alinhamento comportamental ≠ segurança formal;
- correlação de representações ≠ símbolo ou conceito humano idêntico;
- chamada bem-sucedida de API ≠ entitlement permanente;
- ausência de incidente observado ≠ risco nulo.

## Estado epistêmico

| ID | Afirmação | Status | Escopo/evidência |
|---|---|---|---|
| `CLM-IA-FOUND-001` | Minimizar risco empírico garante risco baixo sob qualquer distribuição futura. | `refuted` | Generalização pressupõe relação entre amostra e distribuição-alvo; `MURPHY-2022`, capítulos 4–6. |
| `CLM-IA-FOUND-002` | Atenção escalada combina valores por pesos derivados de queries e keys. | `established` | Definição arquitetural em `VASWANI-2017`, seção 3.2.1. |
| `CLM-IA-FOUND-003` | Next-token prediction é um verificador factual. | `refuted` | O objetivo estima probabilidade condicional de tokens; veracidade exige evidência/verificação adicional. |
| `CLM-IA-FOUND-004` | Leis de escala observadas extrapolam universalmente. | `refuted` | Ajustes são empíricos e condicionados à família/regime; `KAPLAN-2020` e `HOFFMANN-2022`. |
| `CLM-IA-FOUND-005` | Pós-treino muda comportamento, mas não prova segurança completa. | `supported` | Resultado sistêmico delimitado; ataques, distribuição e ferramentas permanecem variáveis. |
| `CLM-IA-FOUND-006` | Um sistema com ferramentas exige autorização e validação externas ao texto do modelo. | `operational` | Invariante de segurança adotado pelo Vault e detalhado na nota de guardrails. |

## Relações

- [[MOC — Inteligência Artificial]] <!-- relation:navigation -->
- [[Operação de APIs e Modelos]] <!-- relation:operational -->
- [[Política Epistêmica e de Linkagem]] <!-- relation:operational -->

## Referências

- Kevin P. Murphy, “Probabilistic Machine Learning: An Introduction”, MIT Press (2022), ISBN `978-0262046824`.
- Ashish Vaswani et al., “Attention Is All You Need”, arXiv:`1706.03762`.
- Tom B. Brown et al., “Language Models are Few-Shot Learners”, arXiv:`2005.14165`.
- Jared Kaplan et al., “Scaling Laws for Neural Language Models”, arXiv:`2001.08361`.
- Jordan Hoffmann et al., “Training Compute-Optimal Large Language Models”, arXiv:`2203.15556`.
- Chuan Guo et al., “On Calibration of Modern Neural Networks”, arXiv:`1706.04599`.
- Jacob Devlin et al., “BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding”, arXiv:`1810.04805`.
- Long Ouyang et al., “Training language models to follow instructions with human feedback”, NeurIPS 2022, arXiv:`2203.02155`.
- Jason Wei et al., “Chain-of-Thought Prompting Elicits Reasoning in Large Language Models”, NeurIPS 2022, arXiv:`2201.11903`.
