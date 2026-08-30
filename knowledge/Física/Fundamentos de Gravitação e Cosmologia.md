---
title: Fundamentos de Gravitação e Cosmologia
domain: física
kind: nota
status: active
epistemic_status: mixed
updated: 2026-07-16
verified_at: 2026-07-16
---

# Fundamentos de gravitação e cosmologia

## Escopo

Esta nota fixa a linguagem mínima usada pelas demais notas de cosmologia e gravitação. Ela separa: (i) relatividade geral testada em muitos regimes; (ii) cosmologia FLRW inferida estatisticamente; e (iii) extrapolações para curvaturas/energias onde a teoria clássica pode falhar.

## Relatividade geral

O campo gravitacional é representado por uma métrica lorentziana `g_{μν}`. Sua curvatura satisfaz

`G_{μν} + Λ g_{μν} = 8πG T_{μν}`,

onde `G_{μν}=R_{μν}-½Rg_{μν}`, `Λ` é a constante cosmológica e `T_{μν}` é o tensor energia–momento. A identidade de Bianchi implica `∇_μT^{μν}=0` quando as equações valem.

A teoria descreve com alta precisão, entre outros fenômenos, dinâmica do Sistema Solar, atraso de Shapiro, pulsares binários e ondas gravitacionais. Isso não confirma extensões de alta curvatura nem resolve a quantização do campo gravitacional.

## Cosmologia homogênea e isotrópica

A métrica FLRW pode ser escrita como

`ds² = -dt² + a(t)²[dχ²/(1-kχ²) + χ²dΩ²]`,

com fator de escala `a(t)`, curvatura espacial `k` e parâmetro de Hubble `H=ȧ/a`. Para matéria perfeita, as equações de Friedmann são

`H² = (8πG/3)ρ - k/a² + Λ/3`,

`ä/a = -(4πG/3)(ρ+3p) + Λ/3`,

`ρ̇ + 3H(ρ+p)=0`.

Se `Λ` for incorporada ao fluido efetivo, a expansão acelera quando `ρ_tot+3p_tot<0`, ou `w_eff=p_tot/ρ_tot<-1/3`. O parâmetro de estado de um componente isolado não garante aceleração se ele for subdominante.

## Horizontes, singularidades e completude

Uma divergência de coordenadas não é necessariamente singularidade física. Critérios relevantes incluem invariantes de curvatura, extensão da variedade e completude geodésica. Os teoremas de singularidade de Penrose–Hawking demonstram incompletude sob hipóteses causais e condições de energia; não especificam, por si, uma “origem” física nem provam que toda extensão quântica tenha bounce.

Um bounce cosmológico requer `H=0` e `Ḣ>0` no ponto de transição. O mecanismo pode vir de curvatura espacial, matéria efetiva, gravidade modificada ou correções quânticas. Consequências em um modelo não são intercambiáveis entre teorias.

## Perturbações e evidência cosmológica

Parâmetros cosmológicos são inferidos combinando CMB, BAO, supernovas, lenteamento e crescimento de estrutura. A adequação do modelo `ΛCDM` é forte em várias escalas, mas tensões de parâmetros e preferências por extensões dependem de combinações de dados, sistemáticas e escolhas de modelo.

“Consistente com os dados” significa que o modelo não foi discriminado dentro da precisão e do espaço paramétrico considerados; não significa que seus campos ou mecanismos foram detectados diretamente.

## Campo quântico em espaço-tempo curvo

A radiação Hawking e a criação cosmológica de partículas são resultados de teoria quântica de campos em uma geometria tratada classicamente. Esse regime semiclassico não é uma teoria completa de gravidade quântica. Efeitos de backreaction, singularidades e microestados gravitacionais exigem hipóteses adicionais.

## Estado epistêmico

| ID | Afirmação | Status | Escopo/evidência |
|---|---|---|---|
| `CLM-FIS-GR-001` | As equações de Einstein descrevem os regimes gravitacionais testados. | `established` | Testes no Sistema Solar, pulsares binários e ondas gravitacionais; extrapolação à escala de Planck não validada. |
| `CLM-FIS-GR-002` | FLRW descreve a expansão cósmica em grande escala. | `supported` | Homogeneidade e isotropia são aproximações sustentadas estatisticamente em grandes escalas. |
| `CLM-FIS-GR-003` | `ΛCDM` é o modelo cosmológico de referência. | `supported` | Ajusta múltiplos conjuntos de dados; componentes escuros não estão identificados microscopicamente. |
| `CLM-FIS-GR-004` | Singularidades clássicas surgem sob as hipóteses dos teoremas. | `established` | Resultado matemático; não seleciona uma resolução quântica. |
| `CLM-FIS-GR-005` | Um bounce específico substitui universalmente a singularidade. | `model-dependent` | Depende da teoria, matéria, truncamento e condições iniciais. |

## Relações

- [[Fundamentos Matemáticos e Métodos da Física Teórica]] <!-- relation:prerequisite -->
- [[Fundamentos de Mecânica Analítica e Campos Clássicos]] <!-- relation:prerequisite -->
- [[Energia Escura e Quintessência]] <!-- relation:extends -->
- [[Gravidade com Torsão e Cosmologias de Bounce]] <!-- relation:extends -->
- [[Gravidade Quântica em Loop e Cosmologia Quântica]] <!-- relation:extends -->
- [[Termodinâmica de Buracos Negros e Informação]] <!-- relation:extends -->
- [[MOC — Física Teórica]] <!-- relation:navigation -->

## Referências essenciais

- Sean M. Carroll, “Lecture Notes on General Relativity”, arXiv:`gr-qc/9712019`: https://arxiv.org/abs/gr-qc/9712019
- Planck Collaboration, “Planck 2018 results. VI. Cosmological parameters”, *Astronomy & Astrophysics* 641, A6 (2020), DOI `10.1051/0004-6361/201833910`: https://doi.org/10.1051/0004-6361/201833910
- Robert M. Wald, “General Relativity”, University of Chicago Press (1984), DOI `10.7208/chicago/9780226870373.001.0001`, ISBN `978-0226870335`.
