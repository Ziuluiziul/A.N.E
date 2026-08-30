---
title: Gravidade Quântica em Loop e Cosmologia Quântica
aliases: [Loop Quantum Gravity, Loop Quantum Gravity / Cosmology]
domain: física
kind: nota
status: active
epistemic_status: model-dependent
updated: 2026-07-16
verified_at: 2026-07-16
---

# Gravidade quântica em loop e cosmologia quântica

## Problema abordado

A gravidade quântica em loop (LQG) busca quantizar graus de liberdade geométricos sem introduzir um espaço-tempo de fundo fixo. A cosmologia quântica em loop (LQC) aplica técnicas relacionadas a modelos cosmológicos com simetria reduzida; LQC não é simplesmente a teoria completa “aplicada” sem aproximações.

## Variáveis e cinemática da LQG

Em uma formulação canônica, usam-se uma conexão de Ashtekar–Barbero `A^i_a` e uma tríade densitizada `E^a_i`, com parâmetro de Barbero–Immirzi `γ`. Em vez de quantizar diretamente a conexão, a representação usa:

- holonomias de `A` ao longo de arestas;
- fluxos de `E` através de superfícies;
- estados de rede de spin, rotulados por representações de `SU(2)` e intertwinners.

Operadores de área e volume têm espectros discretos na representação cinemática. Isso é resultado matemático da quantização escolhida; não equivale a observação experimental de “átomos de espaço”.

## Restrições e dinâmica

Estados físicos precisam satisfazer restrições de Gauss, difeomorfismo e Hamiltoniana. A implementação da dinâmica, o limite semiclassico, ambiguidades de quantização e a recuperação controlada da relatividade geral permanecem questões centrais. Spin foams fornecem uma formulação covariante relacionada, também com escolhas de modelo.

## LQC e equação efetiva

Para o modelo FLRW espacialmente plano, homogêneo e isotrópico, em quantizações padrão, a dinâmica efetiva é frequentemente expressa por

`H² = (8πG/3)ρ(1-ρ/ρ_c)`,

onde `ρ_c` é uma densidade crítica da ordem da densidade de Planck, dependente da quantização. Quando `ρ=ρ_c`, `H=0` e a solução efetiva passa de contração a expansão.

A robustez do bounce foi estudada em várias classes de modelos LQC, mas depende estritamente das escolhas de simetria, do esquema de quantização e do estado considerado.

## Perturbações e observação

Há diferentes esquemas para perturbações — dressed metric, deformed algebra e híbridos — que podem produzir assinaturas distintas. Previsões dependem do estado inicial, duração pré-inflacionária, quantização e tratamento de backreaction. Até o snapshot desta nota, não há assinatura observacional exclusiva de LQC aceita como detecção.

## Estado epistêmico

| ID | Afirmação | Status | Escopo/evidência |
|---|---|---|---|
| `CLM-FIS-LQG-001` | Holonomias, fluxos e redes de spin definem a estrutura cinemática da LQG. | `established` | Resultado matemático dentro da quantização canônica usada. |
| `CLM-FIS-LQG-002` | Operadores de área e volume têm espectros discretos no formalismo. | `established` | Resultado matemático, sem observação direta da granularidade. |
| `CLM-FIS-LQG-003` | A equação efetiva FLRW padrão de LQC substitui o big bang por um bounce no âmbito de modelos com simetria reduzida. | `model-dependent` | Robusto em várias classes de LQC, mas depende estritamente de simetria, quantização e estado. |
| `CLM-FIS-LQG-004` | A unicidade da dinâmica física na LQG e a recuperação completa da relatividade geral em todos os regimes permanecem em aberto. | `open` | Dinâmica, limite semiclassico e ambiguidades continuam questões de pesquisa em aberto. |
| `CLM-FIS-LQG-005` | LQG ou LQC foi confirmada experimentalmente. | `open` | Inexistência de evidências observacionais ou fenomenológicas inequívocas até o presente momento. |

## Relações

- [[Fundamentos de Gravitação e Cosmologia]] <!-- relation:prerequisite -->
- [[Gravidade com Torsão e Cosmologias de Bounce]] <!-- relation:contrasts -->
- [[Fronteiras da Física — Monitor de Evidências]] <!-- relation:evidence -->
- [[Referências Verificadas de Física]] <!-- relation:evidence -->
- [[MOC — Física Teórica]] <!-- relation:navigation -->

## Referências

- Abhay Ashtekar e Parampreet Singh, “Loop Quantum Cosmology: A Status Report”, *Classical and Quantum Gravity* 28, 213001 (2011), DOI `10.1088/0264-9381/28/21/213001`, arXiv:`1108.0893`.
- Bao-Fei Li e Parampreet Singh, “Loop Quantum Cosmology: Physics of Singularity Resolution and Its Implications”, em *Handbook of Quantum Gravity*, 3983–4037 (2024), DOI `10.1007/978-981-99-7681-2_102`.
- Carlo Rovelli, “Loop Quantum Gravity”, *Living Reviews in Relativity* 1, 1 (1998), arXiv:`gr-qc/9710008`.
