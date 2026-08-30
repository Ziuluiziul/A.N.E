---
title: Fundamentos de Teoria Quântica de Campos e Teorias Efetivas
domain: física
kind: nota
status: active
epistemic_status: mixed
updated: 2026-07-16
verified_at: 2026-07-16
---

# Fundamentos de teoria quântica de campos e teorias efetivas

## Escopo

Base mínima para partículas, gauge, renormalização, gravitação semiclassica, cordas e interpretação correta de teorias de alta energia.

## 1. Campos relativísticos

Em QFT, campos são distribuições operatoriais ou variáveis de integração em um funcional gerador. Para um escalar,

$$
\mathcal L=\frac12\partial_\mu\phi\partial^\mu\phi-
\frac12m^2\phi^2-\frac{\lambda}{4!}\phi^4.
$$

Partículas são excitações assintóticas em regimes onde estados de uma partícula estão bem definidos; em espaço-tempo curvo ou meios, essa noção pode depender do observador e do estado.

## 2. Quantização e observáveis

A formulação de integrais de caminho usa

$$
Z[J]=\int\mathcal D\phi\
\exp\!\left[\frac{i}{\hbar}\left(S[\phi]+\int J\phi\right)\right].
$$

Expansão perturbativa gera amplitudes organizadas por diagramas, mas o resultado físico requer regularização, renormalização e observáveis infravermelhos bem definidos. Divergências intermediárias não significam infinitos observáveis.

## 3. Gauge e Modelo Padrão

O Modelo Padrão é uma QFT gauge baseada em

$$
SU(3)_C\times SU(2)_L\times U(1)_Y,
$$

com quebra eletrofraca pelo campo de Higgs. Seu enorme sucesso experimental não implica completude: não incorpora gravidade quântica, matéria escura identificada, massas de neutrinos em sua forma mínima nem a origem cosmológica da assimetria matéria–antimatéria.

## 4. Grupo de renormalização

Acoplamentos dependem da escala `μ`:

$$
\mu\frac{dg_i}{d\mu}=\beta_i(g).
$$

Fluxos de RG distinguem operadores relevantes, marginais e irrelevantes perto de pontos fixos. “Irrelevante” aqui é termo técnico de escala, não ausência de efeito em qualquer energia.

## 5. Teoria efetiva de campos

Abaixo de uma escala de corte `Λ`, a lagrangiana inclui todos os operadores permitidos pelas simetrias:

$$
\mathcal L_{\rm EFT}=\mathcal L_{\rm ren}+
\sum_{d>4}\frac{c_d}{\Lambda^{d-4}}\mathcal O_d.
$$

Predições são ordenadas em `E/Λ`. Uma EFT pode ser altamente precisa sem declarar a ontologia ultravioleta; coeficientes são medidos ou obtidos por matching com uma teoria mais fundamental.

## 6. Campos em espaço-tempo curvo

QFT em geometria clássica curva prevê criação de partículas, efeito Unruh e radiação Hawking. A aproximação semiclassica

$$
G_{\mu\nu}=8\pi G\,\langle T_{\mu\nu}\rangle_{\rm ren}
$$

ignora flutuações quânticas completas da geometria. Ela não é uma teoria final de gravidade quântica.

## 7. Como avaliar propostas UV

A construção matemática de alta energia exige recuperação infravermelha, consistência formal, predições distintivas e evidência observacional. Dualidade ou elegância não substituem detecção empírica.

## Estado epistêmico

| ID | Afirmação | Status | Escopo/evidência |
|---|---|---|---|
| `CLM-FIS-QFT-001` | QFT e o Modelo Padrão descrevem com alta precisão as energias testadas. | `established` | Escopo experimental do Modelo Padrão e cálculos renormalizados. |
| `CLM-FIS-QFT-002` | EFT organiza efeitos de escalas altas em uma expansão controlada. | `established` | Wilson–Kogut e Burgess; requer separação de escalas e matching. |
| `CLM-FIS-QFT-003` | QFT semiclassica resolve a gravidade quântica completa. | `refuted` | Mantém a geometria clássica e quantiza apenas os campos de matéria. |
| `CLM-FIS-QFT-004` | Consistência matemática de uma proposta ultravioleta prova que ela descreve a natureza. | `refuted` | Faltam recuperação infravermelha, predições distintivas e evidência. |
| `CLM-FIS-QFT-005` | Uma continuação UV específica do Modelo Padrão foi estabelecida. | `open` | Inexistência de evidência empírica, consenso ou validade em saídas de modelos LLM. |

## Relações justificadas

- [[Fundamentos Matemáticos e Métodos da Física Teórica]] <!-- relation:prerequisite -->
- [[Fundamentos de Mecânica Analítica e Campos Clássicos]] <!-- relation:prerequisite -->
- [[Fundamentos de Mecânica Quântica e Sistemas Abertos]] <!-- relation:prerequisite -->
- [[Cordas, Dimensões Extras e Holografia]] <!-- relation:extends -->
- [[Termodinâmica de Buracos Negros e Informação]] <!-- relation:extends -->
- [[Gravidade Quântica em Loop e Cosmologia Quântica]] <!-- relation:contrasts -->
- [[MOC — Física Teórica]] <!-- relation:navigation -->

## Referências

- Kenneth G. Wilson e J. Kogut, “The Renormalization Group and the ε Expansion”, *Physics Reports* 12, 75–199 (1974), DOI `10.1016/0370-1573(74)90023-4`.
- C. P. Burgess, “An Introduction to Effective Field Theory”, *Annual Review of Nuclear and Particle Science* 57, 329–362 (2007), DOI `10.1146/annurev.nucl.56.080805.140508`.
- R. M. Wald, “The Thermodynamics of Black Holes”, *Living Reviews in Relativity* 4, 6 (2001), DOI `10.12942/lrr-2001-6`.
