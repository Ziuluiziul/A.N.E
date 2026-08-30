---
title: Cordas, Dimensões Extras e Holografia
aliases: [Kaluza-Klein (5D), Calabi-Yau, M-Theory e AdS-CFT]
domain: física
kind: nota
status: active
epistemic_status: model-dependent
updated: 2026-07-16
verified_at: 2026-07-16
---

# Cordas, dimensões extras e holografia

## Kaluza–Klein

A construção original de Kaluza estende a métrica para cinco dimensões. Com uma dimensão compacta parametrizada por `y ~ y+2πR`, componentes da métrica podem ser reorganizados, após redução dimensional, em campos gravitacional, vetorial e escalar em quatro dimensões.

Para um campo periódico simples,

`Φ(x,y)=Σ_n φ_n(x)e^{iny/R}`,

os modos têm massas

`m_n² = m_0² + n²/R²`.

Logo, “a massa Kaluza–Klein é a massa de Planck” não é geral: ela depende do raio, geometria, warping e condições de contorno. Limites experimentais restringem modelos específicos, não “dimensões extras” como classe única.

## Compactificação Calabi–Yau

Uma variedade Calabi–Yau usada em compactificações é, sob hipóteses padrão, uma variedade Kähler compacta com primeira classe de Chern nula; o teorema de Yau garante uma métrica Ricci-flat em cada classe Kähler apropriada. A condição completa não se reduz ao slogan `c₁=0` fora dessas hipóteses.

Em compactificações de strings:

- uma Calabi–Yau threefold tem seis dimensões reais internas;
- números de Hodge `h^{1,1}` e `h^{2,1}` contam classes de deformações/moduli em contextos usuais;
- o conteúdo de supersimetria depende da teoria de cordas, holonomia, orientifolds, fluxos e branas;
- números de famílias de férmions não são dados genericamente por um único número de Hodge.

Estabilizar moduli e obter física quadridimensional realista são problemas adicionais. Enumerar geometrias ou vacua possíveis é um resultado matemático/computacional, não evidência de que uma compactificação descreva a natureza.

## Teoria de cordas e M-theory

Cordas perturbativas substituem partículas puntiformes fundamentais por objetos unidimensionais cujos modos incluem um estado de spin 2 identificado com o gráviton. Dualidades relacionam regimes das cinco teorias supersimétricas de cordas; M-theory é o framework conjecturado que organiza esses limites e inclui objetos estendidos de dimensão maior.

A consistência matemática e a incorporação de gravidade quântica são motivações fortes. Falta, porém, confirmação experimental exclusiva de cordas/M-theory.

## AdS/CFT

A correspondência holográfica proposta por Maldacena relaciona, em exemplos controlados, uma teoria gravitacional/string em espaço anti-de Sitter a uma teoria de campos conforme sem gravidade na fronteira. O caso canônico envolve string IIB em `AdS₅×S⁵` e `N=4` super-Yang–Mills.

A dualidade tem amplo suporte teórico e testes internos em limites supersimétricos, large-`N` e forte/fraco acoplamento. Ela não é uma identidade empiricamente demonstrada entre “qualquer gravidade” e “qualquer CFT”, nem comprova diretamente que o Universo observável seja AdS.

## Fronteira 2025–2026

- Im e Jodłowski estudam sensibilidades de colisores e detectores a dimensões extras power-law warped; não relatam detecção.
- AbdusSalam, Hughes, Quevedo e Schachner analisam numericamente estabilização de moduli e vacua em mais de 80 mil Calabi–Yau threefolds; é resultado teórico/computacional.
- Wrase discute uso de IA em um estudo de vacua no interior do espaço de moduli; o preprint é reflexão/metodologia, não ganho empírico para string theory.
- Busca automatizada usando os modelos nous/upstage/solar-pro4:free, nvidia/meta/llama-3.1-70b-instruct, nvidia/meta/llama-3.2-11b-vision-instruct e nvidia/meta/llama-3.2-3b-instruct não identificou evidências de dimensões extras ou de cordas na natureza; portanto o claim `CLM-FIS-STR-006` permanece `open`.

## Estado epistêmico

| ID                | Afirmação                                                                 | Status            | Escopo/evidência                                                                   |
| ----------------- | ------------------------------------------------------------------------- | ----------------- | ---------------------------------------------------------------------------------- |
| `CLM-FIS-STR-001` | Redução de Kaluza–Klein produz uma torre com escala `n/R`.                | `established`     | Resultado matemático da compactificação simples.                                   |
| `CLM-FIS-STR-002` | O teorema de Yau garante métricas Ricci‑planas nas condições apropriadas. | `established`     | Teorema matemático; não seleciona uma compactificação física.                    |
| `CLM-FIS-STR-003` | Uma compactificação específica reproduz a física observada.               | `model-dependent` | Depende de geometria, fluxos, branas, moduli e estabilização.                      |
| `CLM-FIS-STR-004` | M-theory é a unificação final da natureza.                                | `hypothesis`      | Síntese teórica sem confirmação empírica direta.                                   |
| `CLM-FIS-STR-005` | AdS/CFT vale em exemplos controlados de dualidade.                        | `supported`       | Forte suporte teórico e checks em classes específicas, não demonstração universal. |
| `CLM-FIS-STR-006` | Dimensões extras ou cordas foram detectadas na natureza.                  | `open`            | Não há detecção confirmada no conjunto de evidências auditado.                     |

## Relações

- [[Fundamentos de Gravitação e Cosmologia]] <!-- relation:prerequisite -->
- [[Termodinâmica de Buracos Negros e Informação]] <!-- relation:extends -->
- [[Fronteiras da Física — Monitor de Evidências]] <!-- relation:evidence -->
- [[Referências Verificadas de Física]] <!-- relation:evidence -->
- [[MOC — Física Teórica]] <!-- relation:navigation -->

## Referências

- Theodor Kaluza, “Zum Unitätsproblem der Physik”, *Sitzungsberichte der Preussischen Akademie der Wissenschaften* (1921), p. 966–972. Fonte institucional: https://ui.adsabs.harvard.edu/abs/1921SPAW.......966K/abstract
- Oskar Klein, “Quantentheorie und cinco-dimensional Relativitätstheorie”, *Zeitschrift für Physik* 37, 895–906 (1926). Fonte institucional: https://ui.adsabs.harvard.edu/abs/1926ZPhy...37..895K/abstract
- Edward Witten, “String theory dynamics in various dimensions”, *Nuclear Physics B* 443, 85–126 (1995), DOI `10.1016/0550-3213(95)00158-O`, arXiv:`hep-th/9503124`.
- Shing‑Tong Yau, “On the Ricci curvature of a compact Kähler manifold and the complex Monge–Ampére equation, I”, *CPAM* 31, 339–411 (1978), DOI `10.1002/cpa.3160310304`.
- Juan Maldacena, “The Large N Limit of Superconformal Field Theories and Supergravity”, *Advances in Theoretical and Mathematical Physics* 2, 231–252 (1998), DOI `10.4310/ATMP.1998.v2.n2.a1`, arXiv:`hep-th/9711200`.
- Sang Hui Im e Krzysztof Jodłowski, “Searches for power‑law warped extra dimensions”, *JHEP* 2026, 19, DOI `10.1007/JHEP01(2026)019`, arXiv:`2412.20913`.
- Shehu AbdusSalam et al., “Coexisting flux string vacua from numerical Kähler moduli stabilisation”, *JHEP* 2026, 56, DOI `10.1007/JHEP01(2026)056`.
- Timm Wrase, “AI usage in string theory, a case study: String Vacua in the Interior of Moduli Space”, arXiv:`2604.01384` (preprint).
