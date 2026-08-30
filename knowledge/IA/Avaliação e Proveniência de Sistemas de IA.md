---
title: Avaliação e Proveniência de Sistemas de IA
domain: ia
kind: nota
status: active
epistemic_status: mixed
updated: 2026-07-16
verified_at: 2026-07-16
---

# Avaliação e proveniência de sistemas de IA

## Escopo

Contrato mínimo para que resultados de modelos sejam comparáveis, auditáveis e reproduzíveis. Avaliação mede comportamento sob um protocolo; não prova inteligência geral, segurança universal ou correção fora da distribuição.

## 1. Unidade de avaliação

Toda execução deve congelar:

- tarefa e critério de sucesso;
- dataset, versão, split e licença;
- modelo, provedor, endpoint e versão/alias resolvido;
- template de prompt, system prompt e ferramentas;
- parâmetros de decoding, limite de tokens e sementes quando disponíveis;
- hardware/software relevante;
- data, latência, custo e limites de cota;
- transformações de entrada e filtros de saída.

Sem esse contrato, dois scores com o mesmo nome podem medir sistemas diferentes.

## 2. Métricas por componente

### Recuperação

- `Recall@k`: fração de evidências relevantes recuperadas;
- `Precision@k`: fração dos itens recuperados que é relevante;
- `MRR`: inverso do rank do primeiro item relevante;
- `nDCG`: ganho com relevância graduada e posição.

### Resposta

- correção factual e completude;
- fidelidade ao contexto;
- cobertura de citações e precisão da atribuição;
- calibração/abstenção;
- robustez a perturbações e injeção;
- latência, tokens e custo.

### Agentes

- sucesso end-to-end;
- precisão de grounding;
- ações inválidas ou não autorizadas;
- recuperação após falha;
- dano potencial e necessidade de intervenção humana.

Não combinar essas métricas em um único score sem pesos, unidades e trade-offs explícitos.

## 3. Baselines e incerteza

Um resultado exige baseline comparável, intervalos de confiança ou variabilidade entre execuções e análise de erro. Selecionar exemplos após observar o resultado produz viés. Test sets contaminados, overlapping com treino ou repetidamente otimizados deixam de medir generalização independente.

Diferença pequena em benchmark não é automaticamente significativa nem operacionalmente relevante. Comparação entre datasets distintos é inválida sem normalização e justificativa.

## 4. Avaliação humana e LLM-as-judge

Avaliação humana deve registrar instruções, treinamento, número de avaliadores, acordo e resolução de desacordo. Juízes baseados em LLM podem escalar triagem, mas têm vieses de posição, verbosidade, estilo, autoconsistência e preferência por famílias de modelos. Devem ser calibrados contra humanos e nunca ser a única evidência em gates críticos.

## 5. Proveniência por claim

Um claim promovido precisa de:

- texto exato e escopo;
- fonte canônica e versão;
- localizador: seção, página, tabela ou trecho;
- data de resolução e identificador persistente;
- hash do payload ou snapshot quando a fonte é volátil;
- transformação aplicada;
- responsável ou agente que produziu a síntese;
- decisão de promoção, quarentena ou rejeição.

Para RAG, guardar IDs e hashes dos chunks recuperados, ranking, consulta e resposta. Guardar apenas a resposta final impede reconstruir por que o modelo afirmou algo.

## 6. Modelo PROV

A estrutura W3C PROV distingue:

- `Entity`: documento, dataset, prompt, modelo, resposta ou manifesto;
- `Activity`: recuperação, transformação, inferência, avaliação ou promoção;
- `Agent`: pessoa, serviço ou processo responsável.

Relações como `wasDerivedFrom`, `wasGeneratedBy` e `wasAssociatedWith` registram linhagem; não substituem verificação factual.

## 7. Reprodutibilidade e deriva

APIs hospedadas podem mudar pesos, infraestrutura ou políticas mantendo alias. Por isso:

1. resolver alias para versão quando o provedor expõe essa informação;
2. armazenar timestamp e fingerprint da resposta;
3. usar conjunto sentinela para detectar deriva;
4. invalidar benchmark quando modelo, prompt, dataset ou ferramenta muda;
5. nunca somar quotas, custos ou scores de provedores como se fossem uma única grandeza.

## 8. Critério do Vault

- conteúdo científico: fonte primária/revisão e localizador;
- snapshot operacional: `verified_at` e `review_after`;
- relação semântica: tipo e justificativa;
- falha de resolução: quarentena;
- promoção automática: proibida sem gates determinísticos e aprovação humana.

## Estado epistêmico

| ID | Afirmação | Status | Escopo/evidência |
|---|---|---|---|
| `CLM-IA-EVAL-001` | O significado de uma métrica depende do protocolo de avaliação. | `established` | Dataset, split, prompt, modelo, decoding e avaliador definem a medição. |
| `CLM-IA-EVAL-002` | LLM-as-judge substitui revisão humana em decisões críticas. | `refuted` | Vieses de posição, estilo e família exigem calibração e supervisão. |
| `CLM-IA-EVAL-003` | Um hash prova que o conteúdo de uma fonte é verdadeiro. | `refuted` | Hash prova identidade/integridade do artefato, não veracidade semântica. |
| `CLM-IA-EVAL-004` | Proveniência completa permite reconstruir a linhagem de uma saída. | `established` | Requer entidades, atividades, agentes, versões e transformações registradas. |
| `CLM-IA-EVAL-005` | Um benchmark único garante segurança em produção. | `refuted` | Cobertura limitada não inclui toda deriva, integração, ferramenta ou ameaça. |

## Relações justificadas

- [[Fundamentos de Aprendizado de Máquina e Modelos de Linguagem]] <!-- relation:prerequisite --> fixa objetivos, generalização, incerteza e avaliação.
- [[RAG e Contexto Longo]] <!-- relation:extends --> define métricas de recuperação, fidelidade e atribuição.
- [[Modelos Multimodais e Agentes Visuais]] <!-- relation:extends --> separa grounding, planejamento e sucesso end-to-end.
- [[Segurança, Guardrails e Avaliação]] <!-- relation:prerequisite --> exige ameaça, métricas e testes adversariais.
- [[Operação de APIs e Modelos]] <!-- relation:operational --> fixa versões, endpoints e snapshots.
- [[Política Epistêmica e de Linkagem]] <!-- relation:operational --> aplica proveniência ao Vault.
- [[MOC — Inteligência Artificial]] <!-- relation:navigation -->

## Referências

- Percy Liang et al., “Holistic Evaluation of Language Models”, arXiv:`2211.09110`.
- NIST, “Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile”, NIST AI 600-1 (2024), DOI `10.6028/NIST.AI.600-1`.
- W3C, “PROV-O: The PROV Ontology”, Recommendation de 30 abril 2013. Fonte institucional: https://www.w3.org/TR/prov-o/
- C2PA, “C2PA Specifications”, versão 2.4. Fonte institucional: https://spec.c2pa.org/specifications/specifications/2.4/index.html
