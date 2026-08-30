---
title: Segurança, Guardrails e Avaliação
aliases: [Segurança-Guardrails, Segurança & Guardrails — 2025]
domain: ia
kind: nota
status: active
epistemic_status: mixed
updated: 2026-07-16
verified_at: 2026-07-16
---

# Segurança, guardrails e avaliação

## Modelo de ameaça

Guardrails reduzem risco; não provam alinhamento nem segurança completa. O modelo de ameaça deve distinguir:

- conteúdo nocivo de entrada/saída;
- prompt injection direta e indireta;
- exfiltração de dados e segredos;
- uso indevido de ferramentas;
- ações irreversíveis;
- poisoning de memória/RAG;
- falhas de autorização;
- manipulação do avaliador.

## Defesa em profundidade

Uma arquitetura robusta separa:

1. **política humana e escopo** — o que pode ocorrer;
2. **autorização determinística** — identidade, recurso, argumentos e efeito;
3. **classificação semântica** — guard model para conteúdo/contexto;
4. **sandbox e least privilege** — limitar impacto;
5. **validação de entrada/saída** — schemas, tipos, paths, domínios;
6. **confirmação humana** — efeitos externos, destrutivos ou privilegiados;
7. **observabilidade** — traces redigidos, métricas, incidentes;
8. **avaliação adversarial contínua** — versões, idiomas e ataques novos.

Um modelo guard não deve poder ampliar permissões que o código negou.

## Guard models e datasets

### WildGuard

WildGuard unifica detecção de prompt nocivo, resposta nociva e recusa, com dataset e modelo abertos. Resultados do paper são benchmarks no conjunto avaliado; não garantem cobertura de políticas privadas, idiomas ou jailbreaks futuros.

### AEGIS

AEGIS define taxonomia com 13 riscos críticos e 9 esparsos e apresenta dataset de aproximadamente 26 mil interações anotadas, além de ensemble adaptativo de especialistas. A taxonomia pode ser útil para cobertura; garantias de no-regret do algoritmo não equivalem a garantia de moderação perfeita sob distribuição adversarial.

### X-Guard e cobertura multilíngue

X-Guard propõe um agente de moderação multilíngue e reporta cobertura experimental ampla de idiomas. O artefato permanece preprint: seus resultados não demonstram cobertura universal, robustez a dialetos não representados nem equivalência entre tradução intermediária e moderação nativa.

### CultureGuard / Nemotron Safety Guard

CultureGuard descreve um pipeline de dados culturalmente adaptados em oito idiomas além do inglês. O dataset `Nemotron-Safety-Guard-Dataset-v3` contém 386.661 amostras em nove idiomas e treina `Llama-3.1-Nemotron-Safety-Guard-8B-v3`.

O nome do artefato, o paper e o tamanho do dataset devem permanecer separados. Não usar números antigos incompatíveis nem inventar um paper chamado “Llama Nemotron Safety Guard”.

### Policy-as-Prompt

Policy-as-Prompt formaliza moderação em que políticas textuais são entrada do LLM e enumera desafios técnicos, sociotécnicos, organizacionais e de governança. É framework conceitual/preprint, não validação de que prompts substituem governança ou anotação.

## Planejamento seguro em robótica

SAFER combina planner, safety agent, LLM-as-judge e Control Barrier Functions (CBFs). CBFs podem fornecer invariância de um conjunto seguro para a dinâmica/controlador sob hipóteses matemáticas; isso não transmite garantia formal ao raciocínio linguístico inteiro nem a um robô fora do modelo.

## Avaliação

Métricas mínimas por classe e idioma:

- precision, recall e F1;
- false-positive/false-negative por severidade;
- AUROC/AUPRC quando scores são calibrados;
- cobertura de policy labels;
- ataque adaptativo e cross-lingual;
- latência/custo;
- falhas abertas versus fechadas;
- impacto na utilidade benigna.

Separar datasets de treino, tuning e teste. Documentar versão do modelo guard, template, threshold e política. LLM-as-judge exige calibração humana e teste de viés/posição.

## Aplicação ao Vault

- ferramentas de leitura e escrita têm permissões separadas;
- conteúdo recuperado nunca autoriza comando;
- links e referências passam por gate determinístico;
- segredos não entram em Markdown ou traces;
- alterações científicas substantivas requerem diff/revisão humana;
- operação privilegiada permanece decisão humana;
- falha de fonte ou parser nega promoção.

## Estado epistêmico

| ID | Afirmação | Status | Escopo/evidência |
|---|---|---|---|
| `CLM-IA-SEC-001` | Defesa em profundidade reduz dependência de um único controle. | `supported` | Prática consolidada de engenharia; eficácia depende de ameaça, cobertura e operação. |
| `CLM-IA-SEC-002` | Um guard model detecta todos os ataques. | `refuted` | Classificadores têm falsos positivos, falsos negativos e deriva. |
| `CLM-IA-SEC-003` | Benchmark alto garante segurança em produção. | `refuted` | Distribuição, ferramentas, privilégios e adversários mudam o risco operacional. |
| `CLM-IA-SEC-004` | Uma CBF garante o comportamento semântico do LLM. | `refuted` | A garantia aplica-se ao sistema dinâmico e ao modelo matemático especificado. |
| `CLM-IA-SEC-005` | Política textual elimina a necessidade de autorização determinística. | `refuted` | Controle textual não substitui capabilities, validação de esquema e least privilege. |

## Relações

- [[Fundamentos de Aprendizado de Máquina e Modelos de Linguagem]] <!-- relation:prerequisite -->
- [[RAG e Contexto Longo]] <!-- relation:extends -->
- [[Modelos Multimodais e Agentes Visuais]] <!-- relation:extends -->
- [[Operação de APIs e Modelos]] <!-- relation:operational -->
- [[MOC — Inteligência Artificial]] <!-- relation:navigation -->

## Referências verificadas

- Seungju Han et al., “WildGuard: Open One-Stop Moderation Tools for Safety Risks, Jailbreaks, and Refusals of LLMs”, NeurIPS 2024 Datasets and Benchmarks, arXiv:`2406.18495`.
- Shaona Ghosh et al., “AEGIS: Online Adaptive AI Content Safety Moderation with Ensemble of LLM Experts”, arXiv:`2404.05993`.
- Raviraj Joshi et al., “CultureGuard: Towards Culturally-Aware Dataset and Guard Model for Multilingual Safety Applications”, arXiv:`2508.01710v4`.
- Konstantina Palla et al., “Policy-as-Prompt: Rethinking Content Moderation in the Age of Large Language Models”, arXiv:`2502.18695` (preprint).
- Bibek Upadhayay e Vahid Behzadan, “X-Guard: Multilingual Guard Agent for Content Moderation”, arXiv:`2504.08848` (preprint).
- Yi Dong et al., “Safeguarding large language models: a survey”, *Artificial Intelligence Review* (2025), DOI `10.1007/s10462-025-11389-2`.
- Azal Ahmad Khan et al., “Safety Aware Task Planning via Large Language Models in Robotics”, arXiv:`2503.15707` (preprint).
- NIST, “Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile”, NIST AI 600-1 (2024), DOI `10.6028/NIST.AI.600-1`.
