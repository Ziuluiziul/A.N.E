---
title: Termodinâmica de Buracos Negros e Informação
aliases: [Termodinâmica de Buracos Negros, Termodinâmica de Buracos Negros & Entropia de Informação]
domain: física
kind: nota
status: active
epistemic_status: mixed
updated: 2026-08-26
verified_at: 2026-08-26
---

# Termodinâmica de buracos negros e informação

## Leis mecânicas e termodinâmicas

Para buracos negros estacionários, a lei de área clássica estabelece que a área do horizonte não diminui sob hipóteses adequadas de energia e cosmic censorship. A primeira lei mecânica, para um buraco negro de Kerr–Newman, pode ser escrita

`dM = (κ/8πG)dA + Ω_H dJ + Φ_H dQ`,

e em unidades com `c=1`. A identificação termodinâmica usa

`S_BH = k_B c³A/(4Gℏ)`,
`T_H = ℏκ/(2πk_B c)`.

A radiação Hawking é um resultado semiclassico: campos quânticos propagam‑se em uma geometria clássica. Um buraco negro isolado pode perder massa; portanto, a área não obedece isoladamente à lei clássica durante evaporação quântica.

## Entropia generalizada

A lei generalizada considera

`S_gen = A/(4Gℏ) + S_out`,

com convenções apropriadas, e afirma `ΔS_gen≥0` no domínio onde a formulação é válida. `S_out` é a entropia de campos fora do horizonte; não é uma metáfora para “ordem”, alinhamento ou controle de agentes.

## Paradoxo da informação

Cálculos semiclassicos originais produzem radiação aproximadamente térmica e, se a evaporação termina sem correlações suficientes, parecem mapear estados puros em mistos. Isso tensiona a unitariedade da mecânica quântica.

A Page curve é o comportamento esperado da entropia da radiação em uma evolução unitária: cresce até o Page time e depois decresce. A fórmula de ilhas inclui regiões gravitacionais no cálculo da entropia fina da radiação:

`S(R) = min_ext [Area(∂I)/(4G_N) + S_semicl(R∪I)]`.

Replica wormholes e superfícies quânticas extremas reproduzem Page curves em modelos semiclassicos/controlados. Isso é progresso teórico importante, mas não uma demonstração experimental geral da microdinâmica unitária de buracos negros astrofísicos.

## Escopo do resultado para Kerr

Wang e Li calcularam ilhas e Page curve para buracos negros de Kerr em uma configuração específica. O resultado não deve ser citado como solução universal do paradoxo sem declarar geometria, aproximação e acoplamento ao banho/radiação usados.

## Estado epistêmico

| ID | Afirmação | Status | Escopo/evidência |
|---|---|---|---|
| `CLM-FIS-BHI-001` | As leis da mecânica de horizontes valem para buracos negros clássicos estacionários. | `established` | Resultado teórico em GR sob hipóteses de estacionariedade e regularidade. |
| `CLM-FIS-BHI-002` | Entropia de Bekenstein–Hawking e temperatura Hawking emergem semiclassicamente. | `supported` | Pilares teóricos; radiação Hawking astrofísica não foi detectada diretamente. |
| `CLM-FIS-BHI-003` | A lei generalizada da termodinâmica vale nos regimes controlados estudados. | `supported` | Forte suporte teórico, não um teorema sem hipóteses para toda gravidade quântica. |
| `CLM-FIS-BHI-004` | Ilhas e replica wormholes produzem Page curves em modelos controlados. | `model-dependent` | Resultado semiclassico forte, dependente de setups e aproximações específicas. |
| `CLM-FIS-BHI-005` | O mecanismo microscópico completo da evaporação foi estabelecido. | `open` | Problema de fronteira sem descrição universalmente aceita; buscas via LLMs (nous/stepfun, nvidia/deepseek, nvidia/llama) não proveram evidência para fechamento. |

## Relações

- [[Fundamentos de Gravitação e Cosmologia]] <!-- relation:prerequisite -->
- [[Cordas, Dimensões Extras e Holografia]] <!-- relation:extends -->
- [[Referências Verificadas de Física]] <!-- relation:evidence -->
- [[MOC — Física Teórica]] <!-- relation:navigation -->

## Referências

- Jacob D. Bekenstein, “Black Holes and Entropy”, *Physical Review D* 7, 2333–2346 (1973), DOI `10.1103/PhysRevD.7.2333`.
- S. W. Hawking, “Particle creation by black holes”, *Communications in Mathematical Physics* 43, 199–220 (1975), DOI `10.1007/BF02345020`.
- Ahmed Almheiri et al., “The entropy of Hawking radiation”, *Reviews of Modern Physics* 93, 035002 (2021), DOI `10.1103/RevModPhys.93.035002`.
- Liqiang Wang e Ran Li, “Entanglement islands and the Page curve of Hawking radiation for rotating Kerr black holes”, *Physical Review D* 110, 066012 (2024), DOI `10.1103/PhysRevD.110.066012`.
