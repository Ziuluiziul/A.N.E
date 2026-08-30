---
title: Probabilidade
domain: estatística
kind: nota
status: active
epistemic_status: established
updated: 2026-07-18
verified_at: 2026-07-18
---

# Probabilidade

## Finalidade

Responder: **o que é um modelo probabilístico e o que os teoremas limite garantem (e sob quais hipóteses)?** Probabilidade é o pré-requisito de estatística, mecânica estatística e aprendizado de máquina — anterior a todos eles.

## Escopo

Axiomas de Kolmogorov; probabilidade condicional e teorema de Bayes como identidade; independência; variáveis aleatórias, esperança, variância; distribuições nucleares (Bernoulli, binomial, Poisson, normal, exponencial); lei dos grandes números; teorema central do limite. **Escopo negativo:** teoria da medida rigorosa, processos estocásticos, e os usos aplicados em inferência (nota própria) e em ML (domínio IA).

## Pré-requisitos

- [[Lógica, Provas e Argumentação]] <!-- relation:prerequisite -->
- [[Cálculo Multivariável e Vetorial]] <!-- relation:prerequisite --> — densidades, integrais múltiplas e mudança de variável.

## Conceitos nucleares

- **Espaço de probabilidade** `(Ω, F, P)`: os axiomas fixam o cálculo, não a interpretação (frequentista/bayesiana são leituras do mesmo formalismo).
- **Condicional**: `P(A|B) = P(A∩B)/P(B)` para `P(B) > 0`; **Bayes é um teorema**, não uma escola.
- **Independência** é hipótese estrutural, não default do mundo.
- **LGN**: médias amostrais de v.a. iid com esperança finita convergem para a esperança (fraca: em probabilidade; forte: quase certamente).
- **TCL**: para iid com variância finita, a média padronizada converge em distribuição para a normal.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-EST-PROB-001` | A lei forte dos grandes números vale para sequências iid com esperança finita; sem esperança definida (ex.: Cauchy) a média amostral não converge para constante alguma. | established | Teorema clássico (Kolmogorov); o contraexemplo de Cauchy delimita a hipótese. |
| `CLM-EST-PROB-002` | O TCL clássico exige variância finita e iid; caudas pesadas sem segundo momento levam a limites estáveis não gaussianos, e dependência forte pode quebrar a normalidade assintótica. | established | Enunciado de Lindeberg–Lévy; generalizações (Lindeberg, estáveis) declaram hipóteses próprias. |

## Limites e contraexemplos

- **Cauchy**: sem esperança — a média de n observações tem a mesma distribuição de uma só; LGN e TCL não se aplicam.
- Convergência em distribuição **não** implica convergência de momentos.
- `P(A|B)` e `P(B|A)` são objetos distintos — a confusão (falácia do promotor) é erro de estrutura, não de cálculo.
- Independência dois a dois não implica independência conjunta.

## Relações

- [[Cálculo Multivariável e Vetorial]] <!-- relation:prerequisite -->
- [[Inferência e Incerteza]] <!-- relation:extends --> — a inferência usa estes objetos sob dados.
- [[Fundamentos de Termodinâmica e Mecânica Estatística]] <!-- relation:extends --> — ensembles são distribuições sobre microestados.
- [[Fundamentos de Aprendizado de Máquina e Modelos de Linguagem]] <!-- relation:extends --> — perdas esperadas e generalização pressupõem este cálculo.

## Fontes

- Sheldon Ross. *A First Course in Probability*. 10ª ed., Pearson, 2019.
- William Feller. *An Introduction to Probability Theory and Its Applications*, vol. 1. 3ª ed., Wiley, 1968.

## Condição de revisão

Estável; revisar se processos estocásticos ganharem nota própria (herdariam cadeias, martingales e ergodicidade).
