---
title: Modelos Multimodais e Agentes Visuais
aliases: [Multimodal-VLM, Multimodal / VLM — 2025]
domain: ia
kind: nota
status: active
epistemic_status: mixed
updated: 2026-07-16
verified_at: 2026-07-16
---

# Modelos multimodais e agentes visuais

## Arquitetura mínima

Um vision-language model (VLM/MLLM) costuma combinar:

1. encoder visual que transforma pixels/patches em representações;
2. projector, resampler ou cross-attention que alinha representações visuais ao espaço do modelo de linguagem;
3. LLM/autoregressive decoder;
4. treinamento contrastivo, captioning, instruction tuning e/ou preferência.

“End-to-end” pode significar treinamento conjunto de alguns componentes, não necessariamente que todo encoder e LLM sejam atualizados desde pixels brutos em todas as fases.

## Grounding

Grounding exige associar linguagem a regiões, elementos ou ações concretas. Um modelo pode gerar um plano semanticamente correto e ainda clicar no elemento errado. Para agentes web, separar:

- percepção;
- planejamento;
- grounding do alvo;
- execução;
- verificação do estado pós-ação.

A avaliação precisa registrar sucesso real da tarefa, não apenas similaridade da resposta textual.

## LLaVA sem exageros

LLaVA (*Visual Instruction Tuning*) conecta encoder visual e LLM e usa dados de instrução multimodal sintetizados com GPT-4 de texto. O paper reporta 85,1% **relativo** ao GPT-4 em um conjunto sintético de avaliação e 92,53% em ScienceQA na configuração LLaVA+GPT-4. Esses números:

- não são comparação direta com GPT-4V;
- não tornam LLaVA “primeiro MLLM end-to-end” em sentido universal;
- não generalizam para segurança ou agentes web.

## Agentes web multimodais

SeeAct usa um LMM para planejar ações em sites. O paper reporta sucesso de 51,1% em tarefas ao vivo **quando o grounding dos planos foi feito manualmente**; grounding automático permaneceu o gargalo. Portanto, o resultado não deve ser apresentado como 51,1% de autonomia ponta a ponta.

## Avaliação por critérios por amostra

MLLM-Bench propõe critérios específicos por amostra e avaliação pairwise por MLLM judge. A versão publicada em NAACL 2025 avalia 21 MLLMs e reporta 88,02% de concordância com avaliação humana no protocolo do trabalho.

Limites:

- judge pode compartilhar vieses com modelos avaliados;
- critérios/itens podem contaminar treino;
- concordância agregada não garante validade por categoria;
- OCR, spatial reasoning, hallucination e segurança exigem suites próprias.

## Riscos operacionais

- prompt injection em imagem, OCR, alt text ou página;
- grounding incorreto com ação irreversível;
- dados sensíveis em screenshots;
- ataques por sobreposição/elementos invisíveis;
- mudança da UI entre plano e clique;
- excesso de confiança em texto visual pequeno ou ambíguo.

Controles: isolamento, allowlist de ações, confirmação para efeitos externos, checagem pós-condição e logs visuais/redigidos.

## Estado epistêmico

| ID | Afirmação | Status | Escopo/evidência |
|---|---|---|---|
| `CLM-IA-VLM-001` | VLMs integram representações visuais e linguísticas. | `established` | Característica arquitetural das famílias descritas. |
| `CLM-IA-VLM-002` | Escalar parâmetros melhora todos os aspectos de grounding. | `refuted` | Benchmarks mostram erros persistentes de localização, contagem e relações espaciais. |
| `CLM-IA-VLM-003` | O score 85,1% de LLaVA equivale a desempenho geral do GPT-4V. | `refuted` | O número depende do protocolo/judge e não é equivalência geral de capacidade. |
| `CLM-IA-VLM-004` | SeeAct obteve 51,1% ponta a ponta totalmente automático. | `refuted` | O resultado reportado dependia de grounding manual/oráculo no estágio correspondente. |
| `CLM-IA-VLM-005` | MLLM-as-judge substitui avaliação humana crítica. | `refuted` | Juízes automáticos têm vieses e exigem calibração e auditoria humana. |

## Relações

- [[Fundamentos de Aprendizado de Máquina e Modelos de Linguagem]] <!-- relation:prerequisite -->
- [[Segurança, Guardrails e Avaliação]] <!-- relation:extends -->
- [[Operação de APIs e Modelos]] <!-- relation:operational -->
- [[MOC — Inteligência Artificial]] <!-- relation:navigation -->

## Referências verificadas

- Haotian Liu, Chunyuan Li, Qingyang Wu e Yong Jae Lee, “Visual Instruction Tuning”, arXiv:`2304.08485v2`.
- Wentao Ge et al., “MLLM-Bench: Evaluating Multimodal LLMs with Per-sample Criteria”, *NAACL 2025*, 4951–4974, DOI `10.18653/v1/2025.naacl-long.256`, arXiv:`2311.13951`.
- Boyuan Zheng, Boyu Gou, Jihyung Kil, Huan Sun e Yu Su, “GPT-4V(ision) is a Generalist Web Agent, if Grounded”, arXiv:`2401.01614v2`.
