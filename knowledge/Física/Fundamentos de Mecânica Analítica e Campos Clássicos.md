---
title: Fundamentos de Mecânica Analítica e Campos Clássicos
domain: física
kind: nota
status: active
epistemic_status: established
updated: 2026-07-16
verified_at: 2026-07-16
---

# Fundamentos de mecânica analítica e campos clássicos

## Escopo

Vocabulário mínimo para entender ações, simetrias, campos e limites clássicos usados no restante do núcleo de Física.

## 1. Princípio variacional

Para coordenadas generalizadas `q^i(t)` e lagrangiana `L(q,\dot q,t)`, a ação é

$$
S[q]=\int_{t_1}^{t_2}L(q,\dot q,t)\,dt.
$$

Variações com extremos fixos produzem

$$
\frac{d}{dt}\frac{\partial L}{\partial \dot q^i}-\frac{\partial L}{\partial q^i}=0.
$$

Para campos `φ_a(x)`, com densidade lagrangiana `\mathcal L(φ_a,\partial_μφ_a)`,

$$
\partial_\mu\frac{\partial\mathcal L}{\partial(\partial_\mu\phi_a)}-
\frac{\partial\mathcal L}{\partial\phi_a}=0.
$$

O formalismo não diz qual ação descreve a natureza; essa escolha é uma hipótese física restringida por simetrias, graus de liberdade e dados.

## 2. Simetrias e Noether

Uma simetria contínua da ação implica, sob as hipóteses do teorema, uma corrente conservada:

$$
\partial_\mu j^\mu=0.
$$

Exemplos:

- translações temporais → energia;
- translações espaciais → momento linear;
- rotações → momento angular;
- simetria global de fase → carga conservada.

Simetrias de gauge são redundâncias locais da descrição; sua análise requer vínculos e identidades de Noether, não apenas a versão elementar do teorema.

## 3. Formalismo hamiltoniano

Se a transformação de Legendre é regular,

$$
p_i=\frac{\partial L}{\partial\dot q^i},\qquad H=p_i\dot q^i-L,
$$

com equações

$$
\dot q^i=\frac{\partial H}{\partial p_i},\qquad
\dot p_i=-\frac{\partial H}{\partial q^i}.
$$

Teorias de gauge e gravitação são sistemas vinculados; o tratamento correto usa a análise de Dirac. Não se deve contar variáveis de gauge como graus de liberdade físicos.

## 4. Relatividade especial e campos

O intervalo de Minkowski `ds²=η_{μν}dx^μdx^ν` é invariante de Lorentz. Causalidade local separa vetores temporais, nulos e espaciais. O eletromagnetismo pode ser escrito por

$$
F_{\mu\nu}=\partial_\mu A_\nu-\partial_\nu A_\mu,
\qquad
\partial_\mu F^{\mu\nu}=j^\nu,
$$

mais a identidade de Bianchi `∂_[λF_{μν]}=0`. A invariância `A_μ→A_μ+∂_μχ` é gauge.

## 5. Limites

- Equações clássicas podem ser teorias fundamentais no regime observado ou limites efetivos de uma descrição quântica.
- Simetria matemática não é evidência empírica suficiente para um novo campo.
- Conservação global pode falhar ou exigir qualificação em espaço-tempo curvo sem simetria temporal global.

## Estado epistêmico

| ID | Afirmação | Status | Escopo/evidência |
|---|---|---|---|
| `CLM-FIS-MEC-001` | Euler–Lagrange e Hamilton descrevem sistemas regulares. | `established` | Resultado matemático sob diferenciabilidade e transformação de Legendre regular; Goldstein e Carroll. |
| `CLM-FIS-MEC-002` | Noether liga simetrias contínuas da ação a correntes. | `established` | Sob hipóteses explícitas; referência Noether/Tavel na seção Referências. |
| `CLM-FIS-MEC-003` | Maxwell e invariância de Lorentz descrevem o eletromagnetismo clássico. | `established` | Confirmado nos regimes experimentais clássicos e relativísticos. |
| `CLM-FIS-MEC-004` | Toda simetria formal corresponde a uma simetria da natureza. | `refuted` | Não segue da matemática; exige dinâmica e teste empírico. |

## Relações justificadas

- [[Fundamentos Matemáticos e Métodos da Física Teórica]] <!-- relation:prerequisite --> fornece cálculo variacional, geometria e grupos.
- [[Fundamentos de Gravitação e Cosmologia]] <!-- relation:extends --> aplica ação, campos e causalidade à geometria curva.
- [[Fundamentos de Teoria Quântica de Campos e Teorias Efetivas]] <!-- relation:extends --> quantiza campos e organiza correções por escala.
- [[Cordas, Dimensões Extras e Holografia]] <!-- relation:extends --> especializa campos, gauge e compactificação.
- [[MOC — Física Teórica]] <!-- relation:navigation -->

## Referências

- Emmy Noether, “Invariant Variation Problems”, tradução de M. A. Tavel, arXiv:`physics/0503066`.
- Sean M. Carroll, “Lecture Notes on General Relativity”, arXiv:`gr-qc/9712019`.
- Herbert Goldstein, Charles Poole e John Safko, *Classical Mechanics*, 3ª ed., Addison-Wesley (2001), ISBN `978-0201657029`.
