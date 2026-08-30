---
title: Variedades Diferenciáveis e Geometria
aliases: [Variedades, Geometria Diferencial, Manifolds]
domain: matemática
kind: nota
status: active
epistemic_status: established
updated: 2026-07-28
verified_at: 2026-07-28
---

# Variedades diferenciáveis e geometria

## Finalidade

Responder: **como fazer cálculo em espaços que só localmente parecem `R^n`?** É o formalismo em que a relatividade geral e as teorias de gauge são escritas; sem ele, "curvatura do espaço-tempo" e "conexão" são metáforas.

## Escopo

Variedades topológicas e estrutura suave; cartas e atlas; aplicações suaves e difeomorfismos; espaço tangente e cotangente; campos vetoriais e colchete de Lie; formas diferenciais e derivada exterior; teorema de Stokes; métrica riemanniana e pseudo-riemanniana; conexão afim e transporte paralelo; curvatura (Riemann, Ricci, escalar); geodésicas; fibrados e conexões em nível de enunciado. **Escopo negativo:** as equações de campo da relatividade geral e suas soluções (domínio da Física), teoria de índice, e geometria complexa.

## Pré-requisitos

- [[Topologia]] <!-- relation:prerequisite --> — a variedade é primeiro um espaço topológico Hausdorff com base enumerável.
- [[Cálculo Multivariável e Vetorial]] <!-- relation:prerequisite --> — derivada como aplicação linear é o objeto que se transporta para as cartas.
- [[Álgebra Linear]] <!-- relation:prerequisite --> — o espaço tangente é um espaço vetorial em cada ponto.

## Conceitos nucleares

- **Variedade suave de dimensão `n`**: espaço topológico Hausdorff, com base enumerável, localmente homeomorfo a `R^n`, munido de atlas cujas transições são `C^∞`.
- **Espaço tangente `T_pM`**: espaço vetorial de dimensão `n` em cada ponto; definível como derivações sobre germes de funções suaves — definição que não depende de mergulho em espaço ambiente.
- **Campo vetorial**: seção do fibrado tangente; colchete `[X,Y]` mede a não comutatividade dos fluxos.
- **Forma diferencial**: seção do fibrado exterior; `d` é a derivada exterior, com `d² = 0`.
- **Teorema de Stokes**: `∫_M dω = ∫_{∂M} ω`. Unifica gradiente, divergente e rotacional do cálculo vetorial num único enunciado.
- **Métrica**: campo tensorial simétrico não degenerado. **Riemanniana** se definida positiva; **pseudo-riemanniana** (assinatura lorentziana) é o caso da relatividade.
- **Conexão de Levi-Civita**: única conexão compatível com a métrica e livre de torsão. As duas condições são independentes — abandonar a segunda é o que gera as teorias com torsão.
- **Curvatura**: tensor de Riemann mede a não comutatividade do transporte paralelo; Ricci e escalar são traços dele.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-MAT-VAR-001` | Dada uma métrica, existe uma única conexão afim simétrica e compatível com ela (teorema fundamental da geometria riemanniana). | established | Lee, cap. 5; Nakahara, cap. 7. A unicidade depende de exigir **torsão nula**; sem essa condição há uma família de conexões compatíveis, que é o espaço em que teorias de Einstein–Cartan operam. |
| `CLM-MAT-VAR-002` | O espaço tangente é definível intrinsecamente, sem referência a um espaço ambiente em que a variedade estaria mergulhada. | established | Lee, cap. 3, define por derivações. O teorema de mergulho de Whitney garante que todo mergulho é *possível*, mas a geometria não depende de nenhum escolhido. |
| `CLM-MAT-VAR-003` | Curvatura é uma propriedade intrínseca da métrica, detectável por medidas internas à variedade, sem observação externa. | established | Consequência do *Theorema Egregium* de Gauss generalizado; Lee, cap. 7. **Limite de escopo:** vale para a curvatura riemanniana; curvatura *extrínseca* (segunda forma fundamental) depende do mergulho por construção. |

## Limites e contraexemplos

- **Estrutura suave não é única**: existem variedades topológicas com estruturas diferenciáveis não difeomorfas — as esferas exóticas de Milnor em dimensão 7, e `R⁴` admite infinitas estruturas suaves distintas. "A" variedade suave é uma escolha.
- **Nem toda variedade admite métrica lorentziana**: a existência exige condições topológicas (campo de linhas não nulo); a esfera `S²` não admite.
- **Assinatura importa**: teoremas riemannianos não transferem para o caso lorentziano. Geodésicas minimizantes, existência de vizinhanças normais e comportamento de completude mudam qualitativamente.
- Curvatura nula não implica topologia trivial: o toro plano é intrinsecamente plano e não é simplesmente conexo.

## Relações

- [[Topologia]] <!-- relation:prerequisite -->
- [[Cálculo Multivariável e Vetorial]] <!-- relation:prerequisite -->
- [[Álgebra Linear]] <!-- relation:prerequisite -->
- [[Fundamentos de Gravitação e Cosmologia]] <!-- relation:extends --> — a relatividade geral é uma teoria de geometria pseudo-riemanniana.
- [[Gravidade com Torsão e Cosmologias de Bounce]] <!-- relation:extends --> — abandona a condição de torsão nula de `CLM-MAT-VAR-001`.
- [[Fundamentos Matemáticos e Métodos da Física Teórica]] <!-- relation:extends -->
- [[MOC — Matemática]] <!-- relation:navigation -->

## Fontes

- John M. Lee. *Introduction to Smooth Manifolds*. 2ª ed., Springer (Graduate Texts in Mathematics 218), 2012. ISBN 978-1-4419-9981-8.
- Mikio Nakahara. *Geometry, Topology and Physics*. 2ª ed., Institute of Physics Publishing, 2003. ISBN 978-0-7503-0606-5.

## Condição de revisão

Estável. Revisar se o Vault ganhar nota própria de teoria de gauge e fibrados, que absorveria as conexões em fibrados principais.
