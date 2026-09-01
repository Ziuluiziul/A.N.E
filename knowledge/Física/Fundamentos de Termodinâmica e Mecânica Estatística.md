---
title: Fundamentos de Termodinâmica e Mecânica Estatística
domain: física
kind: nota
status: active
epistemic_status: established
updated: 2026-07-16
verified_at: 2026-07-16
---

# Fundamentos de termodinâmica e mecânica estatística

## Escopo

Base mínima para entropia, ensembles, irreversibilidade, não equilíbrio e termodinâmica de buracos negros.

## 1. Estados macroscópicos e primeira lei

Para um sistema simples,

$$
dU=\delta Q-\delta W,
$$

com convenção de trabalho realizado pelo sistema. Em equilíbrio reversível,

$$
dU=T\,dS-p\,dV+\mu\,dN+\cdots.
$$

`U`, `S`, `V` e `N` são funções de estado; calor e trabalho dependem do caminho.

## 2. Entropia estatística

No ensemble microcanônico,

$$
S_B=k_B\ln\Omega.
$$

Para distribuição `{p_i}`,

$$
S_G=-k_B\sum_i p_i\ln p_i.
$$

No ensemble canônico,

$$
Z(\beta)=\sum_i e^{-\beta E_i},\qquad
F=-k_BT\ln Z,
$$

com médias e flutuações obtidas por derivadas de `ln Z`. Equivalência de ensembles exige limites e hipóteses; pode falhar em sistemas pequenos, interações de longo alcance ou transições específicas.

## 3. Segunda lei

Para sistema isolado macroscópico,

$$
\Delta S\ge0.
$$

Na mecânica estatística, isso é comportamento típico sob coarse graining e condições iniciais de baixa entropia, não violação da reversibilidade microscópica. Flutuações negativas locais são possíveis em pequenas escalas e tempos finitos; teoremas de flutuação quantificam sua razão de probabilidade.

## 4. Transporte próximo do equilíbrio

Fluxos `J_i` respondem a forças termodinâmicas `X_j`:

$$
J_i=\sum_jL_{ij}X_j.
$$

Sob reversibilidade microscópica apropriada, valem relações de reciprocidade de Onsager. O regime é linear e próximo do equilíbrio; extrapolação irrestrita para sistemas fortemente dirigidos é inválida.

## 5. Não equilíbrio

A decomposição local

$$
\frac{dS}{dt}=\Phi+\Pi,
\qquad \Pi\ge0,
$$

distingue fluxo de entropia e produção interna. Longe do equilíbrio, não há princípio variacional universal estabelecido equivalente à minimização de energia livre. Estabilidade, bifurcações e relações constitutivas precisam ser analisadas para cada sistema.

## 6. Informação

Entropias termodinâmica, de Gibbs/Shannon e de von Neumann têm relações formais e operacionais, mas não são intercambiáveis sem especificar ensemble, coarse graining e subsistema. “Informação” sem definição operacional não é uma substância física adicional.

## Estado epistêmico

| ID | Afirmação | Status | Escopo/evidência |
|---|---|---|---|
| `CLM-FIS-TH-001` | Leis de equilíbrio e ensembles descrevem os regimes para os quais foram definidos. | `established` | Termodinâmica e mecânica estatística de equilíbrio; equivalência requer hipóteses. |
| `CLM-FIS-TH-002` | A segunda lei é monotonicidade microscópica exata de toda trajetória. | `refuted` | Flutuações e reversibilidade microscópica impedem essa leitura literal. |
| `CLM-FIS-TH-003` | Relações lineares de Onsager valem arbitrariamente longe do equilíbrio. | `refuted` | Onsager é regime linear próximo do equilíbrio e sob reversibilidade apropriada. |
| `CLM-FIS-TH-004` | Estruturas dissipativas podem emergir em sistemas dirigidos. | `supported` | Teoria e experimentos em classes específicas; não é princípio universal. |
| `CLM-FIS-TH-005` | Existe uma lei variacional universal para sistemas fora do equilíbrio. | `open` | Ausência de evidência exaustiva mantida após busca sem chamada recente; propostas são locais ou específicas. |

## Relações justificadas

- [[Fundamentos Matemáticos e Métodos da Física Teórica]] <!-- relation:prerequisite -->
- [[Termodinâmica Fora do Equilíbrio]] <!-- relation:extends -->
- [[Termodinâmica de Buracos Negros e Informação]] <!-- relation:extends -->
- [[Fundamentos de Mecânica Quântica e Sistemas Abertos]] <!-- relation:prerequisite -->
- [[MOC — Física Teórica]] <!-- relation:navigation -->

## Referências

- Lars Onsager, “Reciprocal Relations in Irreversible Processes. I”, *Physical Review* 37, 405–426 (1931).
- Lars Onsager, “Reciprocal Relations in Irreversible Processes. II”, *Physical Review* 38, 2265–2279 (1931).
- Denis J. Evans e Debra J. Searles, “The Fluctuation Theorem”, *Advances in Physics* 51, 1529–1585 (2002).
