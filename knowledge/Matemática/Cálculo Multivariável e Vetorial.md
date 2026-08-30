---
title: Cálculo Multivariável e Vetorial
domain: matemática
kind: nota
status: active
epistemic_status: established
updated: 2026-07-18
verified_at: 2026-07-18
---

# Cálculo multivariável e vetorial

## Finalidade

Responder: **como variação e acúmulo se formalizam em várias dimensões?** Derivadas parciais, gradiente e os teoremas integrais são a linguagem em que campos clássicos, otimização e termodinâmica se expressam.

## Escopo

Funções `R^n → R^m`; derivadas parciais e direcionais; gradiente, jacobiana, hessiana; regra da cadeia; otimização com restrições (multiplicadores de Lagrange); integrais múltiplas e mudança de variável; campos vetoriais; divergência, rotacional; teoremas de Green, Stokes e Gauss (enunciados clássicos em R², R³). **Escopo negativo:** formas diferenciais e variedades (tratadas no aparato da física teórica), análise real rigorosa (construção de R, topologia) e métodos numéricos.

## Pré-requisitos

- [[Lógica, Provas e Argumentação]] <!-- relation:prerequisite -->
- [[Álgebra Linear]] <!-- relation:prerequisite --> — a derivada em `R^n` é uma transformação linear (jacobiana).

## Conceitos nucleares

- **Diferenciabilidade**: aproximação linear local; a jacobiana é a matriz da derivada.
- **Gradiente** `∇f`: direção de maior crescimento local; ortogonal às superfícies de nível.
- **Hessiana**: classificação de pontos críticos (com as ressalvas do caso degenerado).
- **Multiplicadores de Lagrange**: condição necessária de extremo sob restrição regular.
- **Teoremas integrais**: Green/Stokes/Gauss relacionam integrais de campo em fronteiras e interiores — a base matemática das leis de conservação em forma integral.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-MAT-CALCMV-001` | Para `f` diferenciável em `p` com `∇f(p) ≠ 0`, o gradiente aponta a direção de máxima taxa de crescimento local e é ortogonal ao conjunto de nível de `f` em `p`. | established | Prova padrão via derivada direcional e regra da cadeia; hipótese de diferenciabilidade é essencial. |
| `CLM-MAT-CALCMV-002` | Os teoremas de Green, Stokes e Gauss expressam a igualdade entre a integral de uma "derivada" do campo no interior e a integral do campo na fronteira, sob hipóteses de regularidade do campo e da região. | established | Enunciados e provas clássicos; falham sem regularidade (campo singular no interior — ver contraexemplos). |

## Limites e contraexemplos

- Derivadas parciais existirem **não** implica diferenciabilidade (contraexemplo padrão em `R²`).
- Hessiana singular não classifica o ponto crítico (ex.: `f(x,y) = x⁴ + y⁴` vs `x⁴ − y⁴` na origem).
- Gauss/Stokes falham com singularidades no domínio: o campo `r/|r|³` em região contendo a origem exige excisão — exatamente o que dá conteúdo à lei de Gauss do eletromagnetismo.
- Multiplicadores de Lagrange são condição **necessária**, não suficiente; e exigem regularidade da restrição (`∇g ≠ 0`).

## Relações

- [[Álgebra Linear]] <!-- relation:prerequisite -->
- [[Fundamentos de Mecânica Analítica e Campos Clássicos]] <!-- relation:extends --> — variações e campos usam este aparato.
- [[Fundamentos de Termodinâmica e Mecânica Estatística]] <!-- relation:extends --> — diferenciais e potenciais termodinâmicos.
- [[Fundamentos Matemáticos e Métodos da Física Teórica]] <!-- relation:extends -->

## Fontes

- Jerrold E. Marsden e Anthony Tromba. *Vector Calculus*. 6ª ed., W. H. Freeman, 2012.
- Michael Spivak. *Calculus on Manifolds*. Addison-Wesley, 1965 (ponte declarada para o tratamento rigoroso, fora do escopo).

## Condição de revisão

Estável; revisar se surgir nota própria de formas diferenciais/variedades, que herdaria a fronteira rigorosa.
