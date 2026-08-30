---
title: Inferência e Incerteza
domain: estatística
kind: nota
status: active
epistemic_status: established
updated: 2026-07-30
verified_at: 2026-07-18
---

# Inferência e incerteza

## Finalidade

Responder: **como dados finitos sustentam (ou não) conclusões sobre parâmetros e previsões, e como quantificar o quanto não sabemos?** É a ponte disciplinada entre probabilidade e decisão.

## Escopo

Estimação pontual e intervalar; máxima verossimilhança; testes de hipótese e seus erros; interpretação correta de p-valor e intervalo de confiança; inferência bayesiana (posterior como atualização); calibração de previsões probabilísticas; bootstrap como ideia. **Escopo negativo:** desenho de experimentos (nota própria em metodologia), teoria da decisão formal, e avaliação de modelos de ML (domínio IA).

## Pré-requisitos

- [[Probabilidade]] <!-- relation:prerequisite -->

## Conceitos nucleares

- **Verossimilhança**: função dos parâmetros dados os dados; base comum a frequentistas e bayesianos.
- **Intervalo de confiança 95%**: procedimento que cobre o parâmetro em 95% das repetições — **não** "95% de chance de conter o parâmetro" numa realização.
- **p-valor**: probabilidade, sob H₀, de estatística tão ou mais extrema — **não** a probabilidade de H₀.
- **Posterior** `∝` verossimilhança × prior; sensibilidade ao prior é parte do relatório, não um defeito oculto.
- **Calibração**: entre previsões "70%", cerca de 70% devem ocorrer; avaliável com dados (reliability diagram, scores próprios).

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-STAT-CALIB-001` | Uma previsão probabilística pode ser avaliada quanto à calibração sem que calibração, isoladamente, estabeleça utilidade decisória. | established | Literatura estatística de scoring rules; previsão calibrada e não informativa (sempre a taxa-base) é o contraexemplo interno. |
| `CLM-EST-PVAL-001` | P-valor não é probabilidade da hipótese nula nem medida do tamanho do efeito; conclusões que o tratam assim são inválidas independentemente do n. | established | Definição formal; advertência oficial da ASA (2016) sobre uso e má interpretação. |

## Limites e contraexemplos

- Significância estatística com efeito minúsculo: n grande detecta irrelevâncias práticas.
- Ausência de significância não é evidência de ausência (poder baixo).
- Comparações múltiplas sem correção inflam falsos positivos — o gate de qualquer varredura.
- Priors impróprios podem gerar posteriors impróprios; verificar é obrigação de quem modela.

## Relações

- [[Probabilidade]] <!-- relation:prerequisite -->
- [[Desenho Experimental e Causalidade]] <!-- relation:extends --> — inferência válida depende de como os dados foram gerados.
- [[Metrologia e Validação]] <!-- relation:extends --> — incerteza de medição alimenta a inferência.
- [[Avaliação e Proveniência de Sistemas de IA]] <!-- relation:operational --> — avaliações de modelos são inferências sob amostras.

## Fontes

- George Casella e Roger L. Berger. *Statistical Inference*. 2ª ed., Duxbury, 2002.
- Ronald L. Wasserstein e Nicole A. Lazar. “The ASA Statement on p-Values: Context, Process, and Purpose”. *The American Statistician* 70(2), 129–133 (2016). DOI `10.1080/00031305.2016.1154108`.
- Andrew Gelman et al. *Bayesian Data Analysis*. 3ª ed., CRC Press, 2013.

## Condição de revisão

Estável no núcleo; revisar a seção de calibração se o Vault incorporar avaliação sistemática de previsões dos próprios agentes.
