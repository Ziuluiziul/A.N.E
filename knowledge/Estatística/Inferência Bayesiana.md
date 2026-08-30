---
title: Inferência Bayesiana
aliases: [Bayes, Análise Bayesiana, Prior e Posterior]
domain: estatística
kind: nota
status: active
epistemic_status: established
updated: 2026-07-28
verified_at: 2026-07-28
---

# Inferência bayesiana

## Finalidade

Responder: **como atualizar crença quantificada diante de evidência?** É o arcabouço que responde diretamente `P(hipótese | dados)` — a pergunta que o valor-p não responde — ao custo de exigir uma distribuição a priori explícita.

## Escopo

Teorema de Bayes como regra de atualização; prior, verossimilhança, posterior, preditiva; conjugação; priors informativos, fracamente informativos e impróprios; intervalos de credibilidade; modelos hierárquicos; fator de Bayes; computação (MCMC, Metropolis–Hastings, Gibbs, HMC) em nível de enunciado; checagem preditiva posterior. **Escopo negativo:** a teoria da medida por trás (nota própria), implementação de amostradores, e o debate filosófico sobre interpretação de probabilidade.

## Pré-requisitos

- [[Probabilidade]] <!-- relation:prerequisite --> — probabilidade condicional é a operação inteira.
- [[Teoria da Medida e Integração]] <!-- relation:prerequisite --> — a posterior é definida por densidade em relação a uma medida de referência.

## Conceitos nucleares

- **Regra de atualização**: `p(θ | y) ∝ p(y | θ) · p(θ)`. A constante de normalização é a evidência marginal `p(y)`.
- **Prior**: distribuição sobre `θ` **antes** dos dados. É input do modelo, não resultado; declará-lo é a exigência central do método.
- **Conjugação**: família de priors que produz posterior na mesma família. Conveniência computacional, não virtude epistêmica.
- **Intervalo de credibilidade**: região com massa posterior `1−α`. Ao contrário do intervalo de confiança, **é** afirmação de probabilidade sobre o parâmetro — dado o modelo e o prior.
- **Modelo hierárquico**: parâmetros com priors que têm seus próprios parâmetros. Produz encolhimento (*shrinkage*) e é a resposta natural a comparações múltiplas.
- **Fator de Bayes**: razão de evidências marginais entre modelos. Sensível ao prior de maneira que a posterior de parâmetros não é.
- **Checagem preditiva posterior**: simular dados do modelo ajustado e compará-los aos observados. É o teste de adequação do arcabouço.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-EST-BAYES-001` | A posterior responde `P(θ | dados)` diretamente, o que a inferência frequentista não fornece sem prior. | established | Gelman et al., cap. 1. **Custo declarado:** a resposta é condicional ao prior escolhido; a pergunta é respondida ao preço de uma premissa adicional explícita, não de graça. |
| `CLM-EST-BAYES-002` | Com dados suficientes e prior com suporte adequado, a posterior concentra-se no valor verdadeiro independentemente do prior (Bernstein–von Mises, sob regularidade). | established | Gelman et al., cap. 4. **Limites:** exige modelo bem especificado, dimensão fixa e prior com massa positiva na vizinhança do verdadeiro. Falha em dimensão crescente, em modelos mal especificados e quando o prior atribui probabilidade zero à região correta. |
| `CLM-EST-BAYES-003` | Modelos hierárquicos produzem encolhimento que melhora a estimativa conjunta de muitos parâmetros relacionados, tratando comparações múltiplas por construção em vez de por correção posterior. | established | Gelman et al., cap. 5. **Escopo:** o ganho é em erro quadrático agregado; estimativas individuais são deliberadamente enviesadas na direção da média do grupo. |
| `CLM-EST-BAYES-004` | O fator de Bayes é sensível à escolha do prior mesmo quando a posterior dos parâmetros não é. | established | Gelman et al., cap. 7; o efeito é o paradoxo de Jeffreys–Lindley, em que priors difusos favorecem arbitrariamente o modelo mais simples. Priors impróprios tornam o fator de Bayes indefinido. |

## Limites e contraexemplos

- **"Prior não informativo" é rótulo, não propriedade**: um prior uniforme numa parametrização é informativo em outra. Não existe ausência de escolha.
- **Posterior não corrige modelo errado**: se a família de verossimilhança não contém nada próximo do processo gerador, a posterior converge com confiança para o membro menos ruim. Coerência interna não é calibração externa.
- **Convergência de MCMC não é verificável, apenas falsificável**: diagnósticos detectam falha, nunca provam convergência.
- **Custo computacional é restrição real**: em modelos grandes, a diferença entre bayesiano e frequentista frequentemente é decidida por viabilidade, não por epistemologia.

## Relações

- [[Probabilidade]] <!-- relation:prerequisite -->
- [[Teoria da Medida e Integração]] <!-- relation:prerequisite -->
- [[Estimação e Testes de Hipótese]] <!-- relation:contrasts --> — responde a pergunta oposta com premissas diferentes.
- [[Inferência e Incerteza]] <!-- relation:extends -->
- [[Aprendizado Estatístico]] <!-- relation:extends --> — regularização corresponde a prior sob a leitura MAP.
- [[Avaliação e Proveniência de Sistemas de IA]] <!-- relation:operational --> — calibração de incerteza em sistemas de IA.
- [[MOC — Estatística e Inferência]] <!-- relation:navigation -->

## Fontes

- Andrew Gelman, John B. Carlin, Hal S. Stern, David B. Dunson, Aki Vehtari e Donald B. Rubin. *Bayesian Data Analysis*. 3ª ed., CRC Press (Chapman & Hall/CRC Texts in Statistical Science), 2013. ISBN 978-1-4398-4095-5. Edição eletrônica disponibilizada pelos autores.

## Condição de revisão

Estável quanto ao núcleo. Revisar a seção computacional se o Vault ganhar nota de métodos de Monte Carlo.
