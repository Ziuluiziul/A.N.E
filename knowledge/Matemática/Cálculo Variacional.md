---
title: Cálculo Variacional
aliases: [Cálculo de Variações, Euler-Lagrange, Princípio de Ação, Noether]
domain: matemática
kind: nota
status: active
epistemic_status: established
updated: 2026-07-28
verified_at: 2026-07-28
---

# Cálculo variacional

## Finalidade

Responder: **como se otimiza sobre um espaço de funções, e não sobre um espaço de números?** Esta nota fecha uma dívida explícita: `CLM-MAT-ALG-003`, em [[Álgebra Abstrata e Teoria de Grupos]] <!-- relation:operational -->, afirma que a conexão entre simetria contínua e lei de conservação é um teorema de mecânica analítica, e não da teoria de grupos isolada. O teorema é o de Noether, e o aparato que o sustenta é este.

## Escopo

Funcional e sua variação; primeira variação e equação de Euler–Lagrange; condições de contorno naturais e fixas; segunda variação e condições de suficiência (Legendre, Jacobi); problemas com vínculo e multiplicadores; princípio de ação estacionária; teorema de Noether e a correspondência simetria–conservação; formulação hamiltoniana e transformada de Legendre; métodos diretos e existência de minimizadores; problemas clássicos (braquistócrona, geodésicas, superfície mínima). **Escopo negativo:** teoria do controle ótimo, cálculo variacional em espaços de Sobolev com rigor moderno, e as aplicações físicas específicas (domínio de Física).

## Pré-requisitos

- [[Cálculo Multivariável e Vetorial]] <!-- relation:prerequisite --> — a variação é a generalização funcional da derivada direcional.
- [[Equações Diferenciais]] <!-- relation:prerequisite --> — Euler–Lagrange **é** uma EDO ou EDP; o problema variacional se converte em problema diferencial.
- [[Otimização]] <!-- relation:contrasts --> — mesma pergunta em espaço de dimensão infinita, onde a existência de minimizador deixa de ser garantida por compacidade.

## Conceitos nucleares

- **Funcional**: aplicação de um espaço de funções nos reais, tipicamente `J[y] = ∫ F(x, y, y′) dx`.
- **Primeira variação**: análoga à derivada; anula-se em extremos. A condição `δJ = 0` é **necessária**, não suficiente — exatamente como `∇f = 0`.
- **Euler–Lagrange**: `∂F/∂y − d/dx(∂F/∂y′) = 0`. Converte otimização funcional em equação diferencial.
- **Condição de contorno natural**: quando o extremo não é fixo, a própria variação impõe a condição na fronteira. Não é escolha do modelador.
- **Ação estacionária**: as trajetórias físicas tornam a ação estacionária. **Estacionária**, não necessariamente mínima — o nome "princípio de mínima ação" é impreciso e induz erro.
- **Teorema de Noether**: cada simetria contínua da ação corresponde a uma quantidade conservada. Translação temporal ↔ energia; espacial ↔ momento; rotacional ↔ momento angular.
- **Método direto**: em vez de resolver Euler–Lagrange, demonstrar existência de minimizador por compacidade e semicontinuidade inferior.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-MAT-VARIAC-001` | Uma função que extremiza um funcional do tipo integral satisfaz a equação de Euler–Lagrange, que é condição **necessária** e não suficiente. | established | Gelfand & Fomin, cap. 1–2. Soluções de Euler–Lagrange podem ser máximos, mínimos ou pontos de sela; distinguir exige a segunda variação (Legendre, Jacobi). |
| `CLM-MAT-VARIAC-002` | A cada simetria contínua de um funcional de ação corresponde uma quantidade conservada ao longo das soluções das equações de movimento (teorema de Noether). | established | Gelfand & Fomin, cap. 4 (§20, teoremas de conservação). **Hipóteses que a formulação exige e que são omitidas com frequência:** existência de formulação lagrangiana, ação diferenciável, e simetria **contínua** — simetrias discretas, como paridade, não produzem lei de conservação por este teorema. Esta é a evidência que `CLM-MAT-ALG-003` referenciava. |
| `CLM-MAT-VARIAC-003` | O princípio físico é de ação **estacionária**, não de ação mínima; trajetórias reais podem corresponder a pontos de sela do funcional. | established | Gelfand & Fomin, cap. 4. O nome tradicional "mínima ação" é histórico e incorreto no caso geral. |
| `CLM-MAT-VARIAC-004` | A existência de minimizador não é garantida pela existência do funcional: em espaço de dimensão infinita, sequências minimizantes podem não convergir. | established | Gelfand & Fomin, cap. 8 (métodos diretos). **Contraste com dimensão finita:** a falha remete a `CLM-MAT-FUNC-001` — a bola unitária não é compacta em dimensão infinita, e é exatamente por isso que o argumento padrão de existência não transfere. |

## Limites e contraexemplos

- **Nem todo problema tem solução**: o exemplo de Weierstrass exibe funcional com ínfimo não atingido. A existência é teorema a demonstrar, não pressuposto.
- **Nem todo sistema físico é lagrangiano**: sistemas com dissipação não admitem formulação lagrangiana padrão, e Noether não se aplica a eles sem extensão.
- **Simetria da equação não é simetria da solução**: soluções podem quebrar a simetria do funcional que as gera. Fenômeno central em física, e frequentemente lido como contradição.
- **Multiplicadores exigem regularidade do vínculo**: a mesma condição de qualificação que aparece em [[Otimização]] <!-- relation:contrasts --> reaparece aqui, e é omitida com a mesma frequência.

## Relações

- [[Cálculo Multivariável e Vetorial]] <!-- relation:prerequisite -->
- [[Equações Diferenciais]] <!-- relation:prerequisite -->
- [[Otimização]] <!-- relation:contrasts -->
- [[Análise Funcional]] <!-- relation:operational --> — a falha de compacidade que limita a existência de minimizadores.
- [[Álgebra Abstrata e Teoria de Grupos]] <!-- relation:operational --> — fornece a noção de simetria contínua; a conservação é demonstrada aqui.
- [[Fundamentos de Mecânica Analítica e Campos Clássicos]] <!-- relation:extends --> — a instância física do princípio de ação.
- [[Variedades Diferenciáveis e Geometria]] <!-- relation:extends --> — geodésicas são solução variacional.
- [[MOC — Matemática]] <!-- relation:navigation -->

## Fontes

- I. M. Gelfand e S. V. Fomin. *Calculus of Variations*. Traduzido e editado por Richard A. Silverman. Prentice-Hall, 1963; reimpressão Dover Publications, 2000. ISBN 978-0-486-41448-5.

## Condição de revisão

Estável. Revisar se o Vault ganhar nota de controle ótimo ou de espaços de Sobolev, que absorveriam respectivamente o problema de controle e o rigor moderno da existência.
