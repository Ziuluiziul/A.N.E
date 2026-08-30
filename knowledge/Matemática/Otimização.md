---
title: Otimização
aliases: [Otimização Convexa, Programação Matemática]
domain: matemática
kind: nota
status: active
epistemic_status: established
updated: 2026-07-28
verified_at: 2026-07-28
---

# Otimização

## Finalidade

Responder: **quando "minimizar" é um problema resolvível, e o que se garante quando um algoritmo para?** Treinar um modelo, ajustar parâmetros e estimar por máxima verossimilhança são todos problemas de otimização; a distinção entre convexo e não convexo é o que separa garantia de heurística.

## Escopo

Conjuntos e funções convexas; problema convexo em forma padrão; condições de otimalidade; dualidade lagrangiana e gap de dualidade; condições KKT; classes (LP, QP, SOCP, SDP); métodos de primeira ordem (gradiente, gradiente estocástico, momento); métodos de segunda ordem (Newton, quase-Newton/BFGS); região de confiança; taxas de convergência. **Escopo negativo:** otimização combinatória e inteira, controle ótimo, e as escolhas empíricas de treinamento de redes profundas (domínio de IA).

## Pré-requisitos

- [[Cálculo Multivariável e Vetorial]] <!-- relation:prerequisite --> — gradiente, hessiana e Taylor de segunda ordem.
- [[Álgebra Linear]] <!-- relation:prerequisite --> — definição positiva, condicionamento, decomposições.
- [[Análise Real]] <!-- relation:prerequisite --> — existência de mínimo exige compacidade ou coercividade.

## Conceitos nucleares

- **Convexidade**: `f(θx + (1−θ)y) ≤ θf(x) + (1−θ)f(y)`. Consequência decisiva: **todo mínimo local é global**.
- **Problema convexo**: minimizar `f₀` convexa sujeito a `f_i ≤ 0` convexas e `Ax = b` afins. A restrição de igualdade ser *afim*, não convexa, faz parte da definição.
- **Dualidade lagrangiana**: o dual é sempre côncavo, mesmo quando o primal não é convexo. Dualidade fraca `d* ≤ p*` vale sempre; **forte** (`d* = p*`) exige qualificação de restrição, como Slater.
- **KKT**: para problema convexo com Slater, KKT é necessária e suficiente. Sem convexidade, é apenas necessária sob regularidade — e é aí que o uso descuidado erra.
- **Gradiente descendente**: taxa `O(1/k)` para convexa com gradiente Lipschitz; linear para fortemente convexa. Não convexa: garante apenas ponto estacionário.
- **Newton e quase-Newton**: convergência local quadrática (Newton) ao custo da hessiana; BFGS aproxima a curvatura sem formá-la.
- **Estocástico (SGD)**: usa gradiente ruidoso; converge sob condições de passo (Robbins–Monro), com taxa pior e custo por iteração muito menor.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-MAT-OTIM-001` | Em um problema convexo, todo mínimo local é mínimo global. | established | Boyd & Vandenberghe, §4.2. É a propriedade que torna a classe tratável; a recíproca é falsa — há funções não convexas sem mínimos locais espúrios. |
| `CLM-MAT-OTIM-002` | Dualidade fraca vale para qualquer problema; dualidade forte exige qualificação de restrição. | established | Boyd & Vandenberghe, §5.2 (fraca) e §5.3 (Slater). **Limite:** existem problemas convexos com gap de dualidade estritamente positivo quando Slater falha; a convexidade sozinha não basta. |
| `CLM-MAT-OTIM-003` | Para funções não convexas, os métodos de gradiente garantem apenas convergência a ponto estacionário — não a mínimo local, e muito menos global. | established | Nocedal & Wright, cap. 3. **Escopo:** o sucesso empírico do treinamento de redes profundas não contradiz isto; é evidência de que a paisagem dessas funções tem propriedades favoráveis, não de que a garantia teórica seja mais forte. Essa distinção é o ponto em que otimização e prática de IA são frequentemente confundidas. |

## Limites e contraexemplos

- **Convexidade é frágil a reparametrização**: a mesma função pode ser convexa numa parametrização e não noutra. "O problema é convexo" é afirmação sobre a formulação, não sobre o fenômeno.
- **Existência exige hipótese**: `f(x) = e^{−x}` em `R` é convexa, limitada inferiormente e não atinge o ínfimo. Convexidade não dá existência de minimizador.
- **Condicionamento domina a prática**: em problemas mal condicionados, o gradiente descendente pode ser inutilizável apesar de todas as garantias assintóticas valerem.
- Ponto estacionário pode ser sela; em alta dimensão, selas são muito mais comuns que mínimos locais.

## Relações

- [[Cálculo Multivariável e Vetorial]] <!-- relation:prerequisite -->
- [[Álgebra Linear]] <!-- relation:prerequisite -->
- [[Análise Real]] <!-- relation:prerequisite -->
- [[Fundamentos de Aprendizado de Máquina e Modelos de Linguagem]] <!-- relation:extends --> — treinamento é minimização de risco empírico, caso não convexo.
- [[Inferência e Incerteza]] <!-- relation:extends --> — máxima verossimilhança é problema de otimização.
- [[Algoritmos e Estruturas de Dados]] <!-- relation:contrasts --> — custo por iteração e complexidade assintótica são eixos distintos.
- [[MOC — Matemática]] <!-- relation:navigation -->

## Fontes

- Stephen Boyd e Lieven Vandenberghe. *Convex Optimization*. Cambridge University Press, 2004. ISBN 978-0-521-83378-3. Edição eletrônica aberta mantida pelos autores.
- Jorge Nocedal e Stephen J. Wright. *Numerical Optimization*. 2ª ed., Springer (Springer Series in Operations Research and Financial Engineering), 2006. ISBN 978-0-387-30303-1.

## Condição de revisão

Estável quanto à teoria. Revisar a seção de métodos estocásticos se o Vault ganhar nota dedicada a treinamento de redes profundas.
