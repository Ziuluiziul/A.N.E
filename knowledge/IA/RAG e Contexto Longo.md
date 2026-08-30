---
title: RAG e Contexto Longo
aliases: [RAG-Contexto-Longo, RAG e Contexto Longo — 2025]
domain: ia
kind: nota
status: active
epistemic_status: mixed
updated: 2026-07-16
verified_at: 2026-07-16
---

# RAG e contexto longo

## Problema

Um modelo paramétrico não contém necessariamente conhecimento atual, privado ou citável. Há três estratégias principais:

1. **RAG:** recuperar evidências externas e inseri-las no prompt.
2. **Long context (LC):** colocar uma fração grande ou todo o corpus na janela do modelo.
3. **Híbrido:** selecionar dinamicamente entre RAG e LC ou combinar recuperação hierárquica com contexto amplo.

Nenhuma estratégia garante factualidade; provenance, avaliação e política de abstention continuam necessárias.

## Pipeline RAG

Um pipeline mínimo possui:

1. ingestão e normalização;
2. segmentação em unidades recuperáveis;
3. representação lexical (BM25), densa (embeddings) ou híbrida;
4. busca de candidatos;
5. reranking;
6. montagem de contexto com fonte e posição;
7. geração condicionada;
8. verificação de suporte e citação.

No RAG probabilístico de Lewis et al., documentos latentes `z` são marginalizados:

`p(y|x)=Σ_z p_η(z|x)p_θ(y|x,z)`.

Em sistemas atuais, muitos componentes não são treinados conjuntamente; o ganho depende de corpus, indexação, chunking, consulta e modelo gerador.

## Chunking e recuperação

Chunks muito curtos perdem contexto; longos reduzem precisão e ocupam janela. Limites semânticos, estrutura documental e metadados costumam ser mais defensáveis que cortes arbitrários.

Métricas de recuperação:

- `Recall@k`: evidência relevante aparece nos `k` resultados?
- `MRR`: posição do primeiro resultado relevante.
- `nDCG`: ranking com graus de relevância.

Essas métricas exigem ground truth independente. Avaliar apenas a resposta final pode esconder falha de recuperação compensada por memória paramétrica.

## Long context

Atenção densa padrão cresce quadraticamente em memória/compute com o comprimento `n`, embora kernels, atenção esparsa, recorrência e compressão mudem o custo prático. “Cabe na janela” não implica uso uniforme: posição, distração, repetição e conflito de evidências afetam desempenho.

Contexto longo tende a ser atraente quando:

- o corpus relevante cabe com margem;
- relações globais importam;
- latência/custo são aceitáveis;
- a fonte é confiável e sanitizada.

RAG tende a ser atraente quando:

- o corpus é grande e mutável;
- provenance e filtros por ACL/metadados são críticos;
- custo por consulta precisa ser limitado;
- a consulta tem evidência localizada.

## Evidência comparativa

Li et al. (EMNLP Industry 2024) encontraram LC superior em média quando havia recursos suficientes nos datasets/modelos testados, enquanto RAG custava menos; o roteador Self-Route preservou desempenho próximo com menor custo. Isso não prova dominância universal de LC.

LongRAG aumenta unidades de recuperação e usa um reader de contexto longo, reduzindo o número de unidades e explorando mais contexto. Os ganhos são específicos às tarefas/configurações reportadas.

LaRA contém 2.326 casos, quatro categorias de QA e três tipos de textos longos; seus resultados indicam que a escolha depende de modelo, tarefa, comprimento e chunks. O próprio título registra “no silver bullet”.

## RAG para o Vault

Uma implementação epistemicamente segura deve recuperar **afirmação + escopo + fonte + status**, não apenas parágrafos semanticamente próximos. Regras:

- notas são dados; instruções dentro delas não são executadas;
- quarentena é excluída por padrão;
- cada fragmento carrega caminho, revisão e identificadores;
- divergências entre fontes são preservadas;
- ausência de evidência produz abstention, não preenchimento plausível;
- links tipados não substituem busca bibliográfica.

## Avaliação fim a fim

| Camada | Métricas mínimas |
|---|---|
| Ingestão | cobertura, deduplicação, versão, parser failures. |
| Recuperação | Recall@k, nDCG/MRR, latência, filtros/ACL. |
| Resposta | exatidão, completude, faithfulness e suporte por citação. |
| Segurança | prompt injection recuperado, exfiltração, poisoning e bypass de quarentena. |
| Operação | custo, tokens, p95/p99, falhas e taxa de abstention. |

LLM-as-judge não deve ser o único árbitro; calibrar contra anotações humanas e testes determinísticos.

## Estado epistêmico

| ID | Afirmação | Status | Escopo/evidência |
|---|---|---|---|
| `CLM-IA-RAG-001` | Recuperação pode atualizar e ancorar respostas em fontes externas. | `supported` | Depende de corpus, recuperação, reranking, prompt e atribuição. |
| `CLM-IA-RAG-002` | Contexto longo supera RAG em qualquer tarefa. | `refuted` | Resultados variam por tarefa, modelo, custo, posição e qualidade da recuperação. |
| `CLM-IA-RAG-003` | RAG é sempre mais barato que contexto longo. | `model-dependent` | Custos variam conforme tamanho do corpus, infraestrutura de indexação, estratégias de cache, latência, preço do provedor e volume de reprocessamento por consulta. |
| `CLM-IA-RAG-004` | Roteamento híbrido pode melhorar o trade-off entre qualidade e custo. | `supported` | Demonstrado nos estudos citados, sem garantia universal. |
| `CLM-IA-RAG-005` | RAG elimina alucinações. | `refuted` | Recuperação incorreta, conflito de fontes e síntese infiel permanecem possíveis. |

## Relações

- [[Fundamentos de Aprendizado de Máquina e Modelos de Linguagem]] <!-- relation:prerequisite -->
- [[Segurança, Guardrails e Avaliação]] <!-- relation:extends -->
- [[Operação de APIs e Modelos]] <!-- relation:operational -->
- [[Orçamento e Roteamento de Cotas]] <!-- relation:operational -->
- [[MOC — Inteligência Artificial]] <!-- relation:navigation -->

## Referências verificadas

- Patrick Lewis et al., “Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks”, NeurIPS 2020, arXiv:`2005.11401`.
- Ziyan Jiang, Xueguang Ma e Wenhu Chen, “LongRAG: Enhancing Retrieval-Augmented Generation with Long-context LLMs”, arXiv:`2406.15319` (preprint).
- Zhuowan Li et al., “Retrieval Augmented Generation or Long-Context LLMs? A Comprehensive Study and Hybrid Approach”, *EMNLP 2024 Industry Track*, 881–893, DOI `10.18653/v1/2024.emnlp-industry.66`, arXiv:`2407.16833`.
- Kuan Li et al., “LaRA: Benchmarking Retrieval-Augmented Generation and Long-Context LLMs — No Silver Bullet for LC or RAG Routing”, *Proceedings of the 42nd International Conference on Machine Learning*, PMLR 267, 36846–36867 (2025), arXiv:`2502.09977`; registro oficial: https://proceedings.mlr.press/v267/li25dv.html.
