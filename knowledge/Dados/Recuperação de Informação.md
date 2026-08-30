---
title: Recuperação de Informação
domain: informação
kind: nota
status: active
epistemic_status: mixed
updated: 2026-07-18
verified_at: 2026-07-18
---

# Recuperação de informação

## Finalidade

Responder: **como encontrar, ordenar e avaliar documentos relevantes a uma consulta — e o que "relevante" significa operacionalmente?** RAG e busca semântica são aplicações; esta nota é o fundamento que as precede.

## Escopo

Representação documental (bag-of-words, TF-IDF, embeddings como representação); índice invertido; modelos de ranking (booleano, vetorial, BM25 como família probabilística); avaliação com coleções de teste (precisão/revocação, MAP, nDCG); julgamentos de relevância. **Escopo negativo:** arquiteturas de LLM, chunking/engenharia de RAG (nota própria em IA), bancos de dados relacionais e ontologias (notas futuras do domínio).

## Pré-requisitos

- [[Álgebra Linear]] <!-- relation:prerequisite --> — o modelo vetorial e embeddings vivem em espaços com produto interno.
- [[Probabilidade]] <!-- relation:prerequisite --> — modelos probabilísticos de relevância.
- [[Algoritmos e Estruturas de Dados]] <!-- relation:prerequisite --> — índice invertido é a estrutura que torna a busca viável.

## Conceitos nucleares

- **Relevância é relação consulta-documento-tarefa**, operacionalizada por julgamentos humanos em coleções de teste — não uma propriedade intrínseca do documento.
- **Índice invertido**: termo → lista de postings; a troca de espaço por tempo que fundou a área.
- **TF-IDF/BM25**: pesar frequência local contra raridade global; BM25 adiciona saturação e normalização por tamanho.
- **Embeddings**: proximidade vetorial captura similaridade distribucional — **não** significado pleno nem verdade (limite herdado da política de quarentena do Vault).
- **Avaliação**: sem coleção de teste e julgamentos, "melhorou" é anedota; métricas de ranking (nDCG) pesam posição.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-INFO-RI-001` | A avaliação de sistemas de recuperação exige coleção de teste com julgamentos de relevância; métricas calculadas sem julgamentos não medem qualidade de recuperação. | established | Metodologia Cranfield/TREC consolidada; julgamentos incompletos (pooling) são a limitação declarada, não a exceção. |
| `CLM-INFO-RI-002` | Recuperação documental melhora acesso a contexto, mas não garante que a resposta gerada seja correta ou fiel às fontes. | supported | Literatura de avaliação de RAG; sistemas com verificação adicional são o contraexemplo parcial. Escopo: arquiteturas RAG; revisão anual. |

## Limites e contraexemplos

- Similaridade de embedding alta com relevância nula (mesmo vocabulário, tarefa distinta) — proximidade vetorial não é resposta.
- Julgamentos de relevância envelhecem: coleção de 2010 não avalia consultas de 2026.
- BM25 forte em domínio geral pode perder para léxico exato em domínios técnicos (identificadores, códigos) — híbridos existem por isso.
- nDCG alto com utilidade baixa: métrica de ranking não captura completude de resposta para tarefas gerativas.

## Relações

- [[Álgebra Linear]] <!-- relation:prerequisite -->
- [[RAG e Contexto Longo]] <!-- relation:extends --> — RAG aplica estes fundamentos num pipeline gerativo.
- [[Avaliação e Proveniência de Sistemas de IA]] <!-- relation:extends --> — a avaliação de RAG herda a metodologia de coleções de teste.
- [[Inferência e Incerteza]] <!-- relation:extends --> — comparar sistemas é inferência sob amostras de consultas.

## Fontes

- Christopher D. Manning, Prabhakar Raghavan e Hinrich Schütze. *Introduction to Information Retrieval*. Cambridge University Press, 2008.
- Stephen Robertson e Hugo Zaragoza. “The Probabilistic Relevance Framework: BM25 and Beyond”. *Foundations and Trends in Information Retrieval* 3(4), 333–389 (2009). DOI `10.1561/1500000019`.

## Condição de revisão

Anual (`CLM-INFO-RI-002` referencia literatura viva); fundamentos clássicos estáveis.
