---
title: Equações Diferenciais
aliases: [EDO, EDP, Equações Diferenciais Parciais]
domain: matemática
kind: nota
status: active
epistemic_status: established
updated: 2026-07-28
verified_at: 2026-07-28
---

# Equações diferenciais

## Finalidade

Responder: **quando uma lei formulada como taxa de variação determina uma trajetória, e por quanto tempo?** Praticamente toda lei física é uma equação diferencial; o que a matemática acrescenta é dizer quando existe solução, quando é única, e quando ela deixa de existir.

## Escopo

EDOs: existência e unicidade (Picard–Lindelöf), dependência contínua, sistemas lineares, estabilidade e linearização, comportamento qualitativo. EDPs: classificação (elíptica, parabólica, hiperbólica); equações de Laplace, calor e onda; problema de valor inicial e de contorno; boa-postura no sentido de Hadamard; soluções fracas e distribuições; princípio do máximo; métodos de energia; características. **Escopo negativo:** métodos numéricos de solução (domínio de Computação), teoria de sistemas dinâmicos e caos, e as EDPs específicas da relatividade e da mecânica quântica (domínio de Física).

## Pré-requisitos

- [[Análise Real]] <!-- relation:prerequisite --> — existência de solução é teorema de ponto fixo; convergência uniforme é o mecanismo.
- [[Cálculo Multivariável e Vetorial]] <!-- relation:prerequisite -->
- [[Álgebra Linear]] <!-- relation:prerequisite --> — sistemas lineares e autovalores governam estabilidade.

## Conceitos nucleares

- **Picard–Lindelöf**: `y' = f(t,y)`, `y(t₀)=y₀`, com `f` contínua e Lipschitz em `y`, tem solução única **local**. A localidade é parte do enunciado.
- **Boa-postura (Hadamard)**: existência, unicidade e **dependência contínua dos dados**. As três condições são independentes; a terceira é a que separa modelo utilizável de modelo inútil.
- **Classificação de EDPs de 2ª ordem**: pelo sinal do discriminante — elíptica (Laplace, equilíbrio), parabólica (calor, difusão), hiperbólica (onda, propagação). O tipo determina que dados de contorno são apropriados.
- **Solução fraca**: satisfaz a equação no sentido distribucional. Necessária porque soluções clássicas frequentemente não existem — choques em leis de conservação, por exemplo.
- **Princípio do máximo**: para equações elípticas e parabólicas, o extremo ocorre na fronteira. Dá unicidade e estimativas sem resolver.
- **Velocidade de propagação**: hiperbólicas têm cone de dependência finito; parabólicas propagam informação instantaneamente — propriedade não física da equação do calor, e limite conhecido do modelo.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-MAT-EDIF-001` | A condição de Lipschitz garante unicidade local; sem ela, existência pode valer e unicidade falhar. | established | Contraexemplo canônico: `y' = y^{2/3}`, `y(0)=0`, com infinitas soluções. Continuidade sozinha dá existência (Peano), não unicidade. |
| `CLM-MAT-EDIF-002` | Solução local não implica solução global: soluções de EDOs não lineares podem explodir em tempo finito. | established | Exemplo padrão: `y' = y²`, `y(0)=1`, com solução `1/(1−t)` singular em `t=1`. A extensão global exige hipótese adicional (crescimento sublinear ou estimativa a priori). |
| `CLM-MAT-EDIF-003` | O problema de valor inicial para a equação de Laplace é mal posto: a dependência contínua dos dados falha. | established | Exemplo de Hadamard; Evans, cap. 2. **Consequência prática:** o tipo da EDP determina que problema é legítimo — impor dados iniciais a uma equação elíptica não é uma escolha de método, é um erro de formulação. |

## Limites e contraexemplos

- **Existência global de soluções suaves para Navier–Stokes em 3D é um problema aberto** (Problema do Milênio). Registrado aqui como `open`, não como lacuna do texto: é uma fronteira reconhecida, não uma omissão.
- **Linearização não captura tudo**: o teorema de Hartman–Grobman vale para pontos de equilíbrio hiperbólicos; em equilíbrios não hiperbólicos o comportamento linear pode ser qualitativamente enganoso.
- **Boa-postura depende do espaço de funções escolhido**: uma equação pode ser bem posta em `H^s` e mal posta em `C⁰`. "Bem posto" sem especificar o espaço é afirmação incompleta.
- Separação de variáveis e transformadas resolvem uma classe estreita; a maior parte das EDPs não tem solução fechada, e isso é o caso típico, não a exceção.

## Relações

- [[Análise Real]] <!-- relation:prerequisite -->
- [[Cálculo Multivariável e Vetorial]] <!-- relation:prerequisite -->
- [[Álgebra Linear]] <!-- relation:prerequisite -->
- [[Fundamentos de Mecânica Analítica e Campos Clássicos]] <!-- relation:extends --> — as equações de movimento são EDOs/EDPs.
- [[Fundamentos de Gravitação e Cosmologia]] <!-- relation:extends --> — as equações de campo são um sistema de EDPs não lineares.
- [[Fundamentos de Termodinâmica e Mecânica Estatística]] <!-- relation:extends --> — difusão e transporte.
- [[MOC — Matemática]] <!-- relation:navigation -->

## Fontes

- Lawrence C. Evans. *Partial Differential Equations*. 2ª ed., American Mathematical Society (Graduate Studies in Mathematics 19), 2010. ISBN 978-0-8218-4974-3.

## Condição de revisão

Estável quanto ao núcleo. Revisar se o Vault ganhar nota de sistemas dinâmicos, que absorveria estabilidade e comportamento qualitativo.
