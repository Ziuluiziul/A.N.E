---
title: Álgebra Linear
domain: matemática
kind: nota
status: active
epistemic_status: established
updated: 2026-07-18
verified_at: 2026-07-18
---

# Álgebra linear

## Finalidade

Responder: **que estrutura comum sustenta estados quânticos, transformações geométricas e modelos de aprendizado?** Espaços vetoriais e operadores são a árvore formal compartilhada por Física, IA e computação numérica.

## Escopo

Espaços vetoriais reais/complexos de dimensão finita; independência, bases, dimensão; transformações lineares e matrizes; autovalores/autovetores; produto interno, ortogonalidade; operadores autoadjuntos/unitários; decomposições (espectral, SVD) como resultados de existência. **Escopo negativo:** dimensão infinita rigorosa (análise funcional), métodos numéricos de fatoração (futuro domínio computacional) e derivações físicas específicas.

## Pré-requisitos

- [[Lógica, Provas e Argumentação]] <!-- relation:prerequisite --> — as provas de existência/unicidade usam as técnicas de lá.

## Conceitos nucleares

- **Espaço vetorial** sobre corpo `F`; subespaços, soma direta.
- **Base e dimensão**: toda base de um espaço de dimensão finita tem a mesma cardinalidade.
- **Transformação linear** `T: V → W`; núcleo/imagem; teorema do posto: `dim V = dim ker T + dim im T`.
- **Autovalor/autovetor**: `Tv = λv`, `v ≠ 0`; diagonalizabilidade.
- **Produto interno**: norma, ortogonalidade, projeção; Gram–Schmidt.
- **Teorema espectral** (dimensão finita): operador autoadjunto possui base ortonormal de autovetores com autovalores reais.
- **SVD**: toda matriz real/complexa admite decomposição `A = UΣV*`.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-MAT-ALGLIN-001` | Álgebra linear é pré-requisito formal direto para a formulação padrão da mecânica quântica (estados em espaços de Hilbert, observáveis autoadjuntos) e para grande parte do aprendizado de máquina (representações e transformações lineares). | established | Currículos e textos canônicos; formulação padrão da MQ (ver Relações); introduções puramente conceituais são o contraexemplo declarado de escopo. |
| `CLM-MAT-ALGLIN-002` | Em dimensão finita, todo operador autoadjunto é diagonalizável por base ortonormal com espectro real (teorema espectral). | established | Prova completa em Axler, cap. 7; em dimensão infinita o enunciado exige a maquinaria de análise funcional — fora do escopo. |

## Limites e contraexemplos

- O teorema espectral **não** vale sem autoadjunção: matrizes não normais podem não ser diagonalizáveis (blocos de Jordan).
- Intuição geométrica de R³ não se transfere automaticamente: em C^n o produto interno é sesquilinear; "ângulo" exige definição.
- SVD existe sempre, mas **não** é única quando há valores singulares repetidos.

## Relações

- [[Lógica, Provas e Argumentação]] <!-- relation:prerequisite -->
- [[Análise Funcional]] <!-- relation:extends --> — a generalização para dimensão infinita.
- [[Fundamentos de Mecânica Quântica e Sistemas Abertos]] <!-- relation:extends --> — a formulação de estados/observáveis instancia esta estrutura.
- [[Fundamentos de Aprendizado de Máquina e Modelos de Linguagem]] <!-- relation:extends --> — representações vetoriais e camadas lineares instanciam esta estrutura.
- [[Fundamentos Matemáticos e Métodos da Física Teórica]] <!-- relation:extends -->

## Fontes

- Sheldon Axler. *Linear Algebra Done Right*. 4ª ed., Springer, 2024 (edição aberta do autor).
- Gilbert Strang. *Introduction to Linear Algebra*. 6ª ed., Wellesley-Cambridge Press, 2023.

## Condição de revisão

Estável. A fronteira de dimensão infinita, antes declarada fora de escopo, é tratada em [[Análise Funcional]] <!-- relation:extends --> desde 28/07/2026.
