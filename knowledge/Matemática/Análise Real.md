---
title: Análise Real
domain: matemática
kind: nota
status: active
epistemic_status: established
updated: 2026-07-28
verified_at: 2026-07-28
---

# Análise real

## Finalidade

Responder: **o que autoriza a passagem ao limite?** Derivada, integral, série e convergência são usadas em toda a Física e em toda a análise de algoritmos de aprendizado; a análise real é onde essas operações deixam de ser manipulação simbólica e passam a ter condições de validade declaradas.

## Escopo

Completude de `R` e sua consequência (supremo); sequências e séries; limite e continuidade; continuidade uniforme; diferenciação em uma variável; integral de Riemann e suas limitações; convergência pontual, uniforme e em norma; teoremas de troca de limite com integral e derivada; compacidade em espaços métricos; teorema de Heine–Borel; Bolzano–Weierstrass. **Escopo negativo:** teoria da medida e integral de Lebesgue (nota própria), análise funcional em dimensão infinita, análise complexa e análise numérica.

## Pré-requisitos

- [[Lógica, Provas e Argumentação]] <!-- relation:prerequisite --> — quantificadores encadeados e negação de enunciados são o aparato operante aqui; `∀ε ∃δ` só é legível para quem lê a ordem dos quantificadores.

## Conceitos nucleares

- **Completude**: todo subconjunto não vazio de `R` limitado superiormente tem supremo. É o axioma que separa `R` de `Q` e do qual descendem os teoremas de existência.
- **Convergência**: `a_n → a` quando `∀ε>0 ∃N ∀n>N: |a_n − a| < ε`. Sequência de Cauchy converge em `R` — em `Q` não.
- **Compacidade**: em `R^n`, compacto ⇔ fechado e limitado (Heine–Borel). Em espaço métrico geral a equivalência é com *completo e totalmente limitado*; a versão `R^n` **não** generaliza.
- **Continuidade uniforme**: o `δ` não depende do ponto. Função contínua em compacto é uniformemente contínua.
- **Convergência uniforme**: `sup|f_n − f| → 0`. É a hipótese que licencia trocar limite com integral e preservar continuidade no limite.
- **Integral de Riemann**: definida por somas superiores/inferiores; existe para funções contínuas em intervalo compacto e para limitadas com conjunto de descontinuidades de medida nula.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-MAT-ANREAL-001` | A completude de `R` é o que garante os teoremas de existência da análise elementar (valor intermediário, valor extremo, Bolzano–Weierstrass); em `Q` os enunciados correspondentes são falsos. | established | Rudin, cap. 1–2; o contraexemplo padrão é `x² = 2` sem solução em `Q`, com a sequência de aproximações sendo de Cauchy e não convergente em `Q`. |
| `CLM-MAT-ANREAL-002` | Convergência pontual não preserva continuidade nem comuta com integração; convergência uniforme preserva continuidade e comuta com integração em intervalo compacto. | established | Rudin, cap. 7. Contraexemplo pontual clássico: `f_n(x) = xⁿ` em `[0,1]` converge pontualmente para função descontínua. |
| `CLM-MAT-ANREAL-003` | A integral de Riemann é insuficiente para os teoremas de convergência que a probabilidade e a análise moderna exigem, motivando a construção de Lebesgue. | established | Rudin, cap. 6, discute o limite; a construção alternativa e os teoremas de convergência dominada/monótona estão em Folland, cap. 2. Limite de escopo: a afirmação é sobre adequação da ferramenta, não sobre incorreção da integral de Riemann onde ela se aplica. |

## Limites e contraexemplos

- **Continuidade não implica diferenciabilidade**: a função de Weierstrass é contínua em todo ponto e diferenciável em nenhum. Intuição gráfica falha aqui.
- **Heine–Borel não vale em espaço métrico arbitrário**: a bola unitária fechada de um espaço normado de dimensão infinita é fechada e limitada, e não é compacta.
- **Convergência pontual de derivadas não dá derivada do limite**: `f_n → f` uniformemente não garante `f_n' → f'`; é preciso convergência uniforme das derivadas.
- Séries condicionalmente convergentes podem ser reordenadas para convergir a qualquer valor (teorema de Riemann sobre rearranjos) — "soma" não é comutativa fora da convergência absoluta.

## Relações

- [[Lógica, Provas e Argumentação]] <!-- relation:prerequisite -->
- [[Cálculo Multivariável e Vetorial]] <!-- relation:extends --> — a versão multivariável dos mesmos teoremas de limite.
- [[Teoria da Medida e Integração]] <!-- relation:extends --> — resolve a limitação declarada em `CLM-MAT-ANREAL-003`.
- [[Topologia]] <!-- relation:extends --> — compacidade e continuidade reaparecem sem métrica.
- [[Probabilidade]] <!-- relation:extends --> — convergência de variáveis aleatórias instancia estas noções.
- [[MOC — Matemática]] <!-- relation:navigation -->

## Fontes

- Walter Rudin. *Principles of Mathematical Analysis*. 3ª ed., McGraw-Hill, 1976. ISBN 978-0-07-054235-8.
- Stephen Abbott. *Understanding Analysis*. 2ª ed., Springer (Undergraduate Texts in Mathematics), 2015. ISBN 978-1-4939-2711-1.

## Condição de revisão

Estável. Material assentado há mais de um século; revisar apenas se o Vault ganhar nota de análise funcional, que absorveria a fronteira de dimensão infinita.
