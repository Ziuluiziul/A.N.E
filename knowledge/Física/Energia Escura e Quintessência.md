---
title: Energia Escura e Quintessência
aliases: [Quintessência, Quintessência (Dark Energy Dinâmica)]
domain: física
kind: nota
status: active
epistemic_status: mixed
updated: 2026-07-16
verified_at: 2026-07-16
---

# Energia escura e quintessência

## Evidência para aceleração

Supernovas tipo Ia, CMB, BAO e crescimento de estrutura sustentam uma fase recente de expansão acelerada dentro de modelos cosmológicos. O modelo de referência `ΛCDM` representa o componente acelerador por uma constante cosmológica com

`p_Λ = -ρ_Λ`, `w_Λ=-1`.

A aceleração é propriedade da soma dos componentes: `w_eff<-1/3`. Um campo com `w_φ<-1/3` não acelera o Universo se sua contribuição à densidade total for insuficiente.

## Campo escalar canônico

Para quintessência minimamente acoplada, homogênea e canônica,

`ρ_φ = ½φ̇² + V(φ)`,

`p_φ = ½φ̇² - V(φ)`,

`w_φ = (½φ̇² - V)/(½φ̇² + V)`.

Se a energia potencial domina, `w_φ≈-1`; para energia cinética positiva e potencial não negativo, `w_φ≥-1`. Cruzar `w=-1` exige graus de liberdade, acoplamentos ou cinética não canônica adicionais.

A equação de movimento é

`φ̈ + 3Hφ̇ + dV/dφ = 0`.

O termo `3Hφ̇` funciona como amortecimento cosmológico.

## Classes de dinâmica

- **Thawing:** o campo começa congelado por expansão e passa a evoluir recentemente.
- **Freezing/tracker:** a dinâmica converge para uma trajetória pouco sensível a algumas condições iniciais e depois se aproxima de `w≈-1`.
- **Scaling:** a densidade do campo acompanha por um período o componente dominante.

Essas classificações dependem da forma de `V(φ)` e de acoplamentos. “Tracker” não elimina automaticamente ajuste fino nem resolve o problema da escala da energia do vácuo.

## Observação e degenerescências

Dados normalmente restringem parametrizações como `w(a)=w₀+w_a(1-a)` ou potenciais específicos. Inferências variam com curvatura, massa de neutrinos, calibrações e combinação de datasets. Uma preferência estatística por `w≠-1` não é detecção de um campo escalar sem robustez a sistemáticas e modelos alternativos.

O estudo “Constraining Quintessence Models with ISW-tSZ Cross-Correlations: A Comparative Analysis of Thawing, Tracker, and Scaling-Freezing Dynamics”, arXiv:`2601.17298`, compara modelos thawing, tracker e scaling-freezing usando correlação ISW–tSZ. Os parâmetros alternativos permanecem consistentes com `ΛCDM` dentro de aproximadamente `1σ` no resumo; o menor ``χ²`` de um modelo testado não constitui descoberta de quintessência.

## Estado epistêmico

| ID | Afirmação | Status | Escopo/evidência |
|---|---|---|---|
| `CLM-FIS-DE-001` | A expansão cósmica acelerada é suportada pelos modelos e dados atuais. | `supported` | Supernovas, CMB e estrutura em larga escala dentro do quadro cosmológico. |
| `CLM-FIS-DE-002` | `ΛCDM` é a descrição de referência atual. | `supported` | Ajuste empírico forte, sem identificação microscópica completa da energia escura. |
| `CLM-FIS-DE-003` | Quintessência é o mecanismo físico real da aceleração. | `hypothesis` | Classe de campos escalares sem detecção direta. |
| `CLM-FIS-DE-004` | Classes thawing, tracker e scaling são dinâmicas bem definidas de modelos. | `established` | Resultado teórico dentro das equações e potenciais especificados. |
| `CLM-FIS-DE-005` | Um campo de quintessência foi detectado diretamente. | `speculative` | Ausência de evidência empírica direta de graus de liberdade escalares da energia escura. |

## Relações

- [[Fundamentos de Gravitação e Cosmologia]] <!-- relation:prerequisite -->
- [[Fronteiras da Física — Monitor de Evidências]] <!-- relation:evidence -->
- [[Referências Verificadas de Física]] <!-- relation:evidence -->
- [[MOC — Física Teórica]] <!-- relation:navigation -->

## Referências

- Edmund J. Copeland, M. Sami e Shinji Tsujikawa, “Dynamics of dark energy”, *International Journal of Modern Physics D* 15, 1753–1936 (2006), DOI `10.1142/S021827180600942X`, arXiv:`hep-th/0603057`.
- Ayodeji Ibitoye et al., “Constraining Quintessence Models with ISW-tSZ Cross-Correlations: A Comparative Analysis of Thawing, Tracker, and Scaling-Freezing Dynamics”, *Physical Review D* 113, 063509 (2026), arXiv:`2601.17298`.
