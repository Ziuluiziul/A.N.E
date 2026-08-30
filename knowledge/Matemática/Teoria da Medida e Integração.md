---
title: Teoria da Medida e Integração
aliases: [Medida, Lebesgue, Integral de Lebesgue]
domain: matemática
kind: nota
status: active
epistemic_status: established
updated: 2026-07-28
verified_at: 2026-07-28
---

# Teoria da medida e integração

## Finalidade

Responder: **como se atribui "tamanho" a conjuntos e integral a funções de modo que os limites se comportem?** É a fundação técnica que torna a probabilidade um caso particular da medida e que dá os teoremas de convergência que a análise elementar não tem.

## Escopo

σ-álgebras e espaços mensuráveis; medida e suas propriedades (aditividade contável, continuidade); medida de Lebesgue em `R^n`; funções mensuráveis; integral de Lebesgue; teoremas de convergência (monótona, dominada, lema de Fatou); teorema de Fubini–Tonelli; espaços `L^p`; medidas com sinal; Radon–Nikodym; conjuntos não mensuráveis. **Escopo negativo:** análise harmônica, teoria ergódica, medidas em espaços topológicos gerais (Riesz) e a construção probabilística específica (nota de Probabilidade).

## Pré-requisitos

- [[Análise Real]] <!-- relation:prerequisite --> — a insuficiência da integral de Riemann é o que motiva esta construção.
- [[Lógica, Provas e Argumentação]] <!-- relation:prerequisite -->

## Conceitos nucleares

- **σ-álgebra**: coleção de subconjuntos fechada sob complemento e união contável. É a estrutura mínima em que "medir" faz sentido de forma consistente.
- **Medida**: `μ: Σ → [0,∞]` com `μ(∅)=0` e aditividade contável em conjuntos disjuntos.
- **Função mensurável**: pré-imagem de mensurável é mensurável. Não é continuidade — é a condição correta para integrar.
- **Integral de Lebesgue**: construída por aproximação com funções simples, particionando o *contradomínio* em vez do domínio. É a inversão de perspectiva que faz os teoremas de limite funcionarem.
- **Convergência dominada**: se `f_n → f` pontualmente e `|f_n| ≤ g` com `g` integrável, então `∫f_n → ∫f`. É a licença de troca limite–integral mais usada na prática.
- **`L^p`**: espaço das funções com `∫|f|^p < ∞`, módulo igualdade quase sempre. Completo (Riesz–Fischer) — daí sua utilidade.
- **Radon–Nikodym**: se `ν ≪ μ`, existe densidade `dν/dμ`. É o que dá sentido formal a "função de densidade" e a razão de verossimilhança.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-MAT-MEDIDA-001` | A integral de Lebesgue estende a de Riemann: toda função Riemann-integrável em intervalo compacto é Lebesgue-integrável com o mesmo valor, e existem funções Lebesgue-integráveis que não são Riemann-integráveis. | established | Folland, cap. 2. Contraexemplo canônico: a indicadora dos racionais em `[0,1]`, com integral de Lebesgue 0 e sem integral de Riemann. |
| `CLM-MAT-MEDIDA-002` | Sob o axioma da escolha, existem subconjuntos de `R` não Lebesgue-mensuráveis. | established | Construção de Vitali; Folland, cap. 1. O axioma e sua independência estão em [[Teoria dos Conjuntos e Fundamentos]] <!-- relation:prerequisite -->. **Limite de escopo:** o enunciado depende do axioma da escolha — em modelos de ZF com determinação, todo conjunto de reais pode ser mensurável. A dependência do axioma é parte da afirmação, não uma ressalva externa. |
| `CLM-MAT-MEDIDA-003` | A teoria de probabilidade de Kolmogorov é a teoria da medida restrita a espaços de medida total 1; "variável aleatória" é função mensurável e "esperança" é integral. | established | Identificação estrutural padrão; Folland, cap. 10, trata probabilidade como caso particular. O conteúdo interpretativo de probabilidade **não** é estabelecido por esta identificação — é questão separada, tratada em [[Inferência e Incerteza]] <!-- relation:contrasts -->. |

## Limites e contraexemplos

- **Fubini exige hipótese**: sem σ-finitude ou sem integrabilidade do módulo, a troca de ordem de integração pode dar valores diferentes. Existem contraexemplos com integrais iteradas distintas e finitas.
- **Convergência quase sempre não implica convergência em `L^p`** e vice-versa: as duas noções são independentes; a "typewriter sequence" converge em `L^1` e em ponto nenhum.
- **Medida não é comprimento intuitivo**: o conjunto de Cantor é não enumerável e tem medida zero. Cardinalidade e medida são independentes.
- Lema de Fatou dá apenas desigualdade; supor igualdade sem dominação é o erro comum.

## Relações

- [[Análise Real]] <!-- relation:prerequisite -->
- [[Probabilidade]] <!-- relation:extends --> — instancia esta teoria com `μ(Ω)=1`.
- [[Inferência e Incerteza]] <!-- relation:extends --> — verossimilhança como densidade de Radon–Nikodym.
- [[Fundamentos de Termodinâmica e Mecânica Estatística]] <!-- relation:extends --> — medidas em espaço de fase.
- [[MOC — Matemática]] <!-- relation:navigation -->

## Fontes

- Gerald B. Folland. *Real Analysis: Modern Techniques and Their Applications*. 2ª ed., Wiley, 1999. ISBN 978-0-471-31716-6.
- Walter Rudin. *Principles of Mathematical Analysis*. 3ª ed., McGraw-Hill, 1976. ISBN 978-0-07-054235-8.

## Condição de revisão

Estável. Revisar se o Vault ganhar nota de teoria ergódica ou de análise funcional.
