---
title: Análise Funcional
aliases: [Espaços de Hilbert, Espaços de Banach, Operadores Lineares]
domain: matemática
kind: nota
status: active
epistemic_status: established
updated: 2026-07-28
verified_at: 2026-07-28
---

# Análise funcional

## Finalidade

Responder: **o que sobrevive da álgebra linear em dimensão infinita, e o que não sobrevive?** Esta nota fecha uma dívida: as notas de mecânica quântica do Vault operam sobre espaços de Hilbert e operadores autoadjuntos, e [[Álgebra Linear]] <!-- relation:prerequisite --> declara explicitamente que a dimensão infinita está **fora** do seu escopo. Era o degrau ausente.

## Escopo

Espaços normados, de Banach e de Hilbert; completude e sua necessidade; operadores lineares limitados e não limitados; domínio e a distinção entre simétrico e autoadjunto; espectro e sua decomposição; teorema espectral em dimensão infinita; os quatro teoremas fundamentais (Hahn–Banach, Banach–Steinhaus, aplicação aberta, gráfico fechado); dualidade e topologias fracas; operadores compactos; bases ortonormais e séries de Fourier como caso particular; distribuições em nível de enunciado. **Escopo negativo:** álgebras de operadores (C*, von Neumann), teoria espectral avançada, e as aplicações físicas específicas (domínio de Física).

## Pré-requisitos

- [[Álgebra Linear]] <!-- relation:prerequisite --> — o caso de dimensão finita, cuja generalização é o objeto.
- [[Análise Real]] <!-- relation:prerequisite --> — completude e convergência uniforme.
- [[Teoria da Medida e Integração]] <!-- relation:prerequisite --> — `L²` é o espaço de Hilbert canônico, e é completo por Riesz–Fischer.
- [[Topologia]] <!-- relation:prerequisite --> — topologias fracas e compacidade sem métrica.

## Conceitos nucleares

- **Espaço de Banach**: normado e completo. **Hilbert**: Banach cuja norma vem de produto interno — a geometria (ortogonalidade, projeção) sobrevive.
- **Operador limitado**: contínuo ⇔ limitado. Em dimensão infinita a equivalência é teorema, não trivialidade.
- **Simétrico × autoadjunto**: `⟨Ax,y⟩ = ⟨x,Ay⟩` no domínio **não** basta; autoadjunção exige que os domínios de `A` e `A*` coincidam. **Só operadores autoadjuntos** têm teorema espectral e geram grupos unitários — a distinção é física, não pedantismo.
- **Espectro**: generaliza autovalores e decompõe-se em pontual, contínuo e residual. Operadores podem ter espectro sem nenhum autovalor.
- **Hahn–Banach**: extensão de funcional linear preservando norma. Depende do lema de Zorn, e portanto de [[Teoria dos Conjuntos e Fundamentos]] <!-- relation:operational -->.
- **Banach–Steinhaus**: família pontualmente limitada de operadores é uniformemente limitada. Prova por categoria de Baire.
- **Operador compacto**: leva limitados em relativamente compactos; seu espectro é discreto fora do zero, e por isso se comporta como o caso de dimensão finita.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-MAT-FUNC-001` | Em dimensão infinita, a bola unitária fechada é compacta se e somente se o espaço tem dimensão finita (teorema de Riesz). | established | Rudin, cap. 1. É a falha estrutural que separa este domínio da álgebra linear: os argumentos de compacidade de `R^n` deixam de valer, e o contraexemplo já estava registrado em `CLM-MAT-ANREAL-002`. |
| `CLM-MAT-FUNC-002` | Operador simétrico não é necessariamente autoadjunto quando não é limitado, e apenas os autoadjuntos admitem teorema espectral e geram grupos unitários a um parâmetro. | established | Rudin, cap. 13. **Consequência física direta:** um observável quântico precisa ser autoadjunto, não apenas simétrico; a diferença está no domínio e nas condições de contorno, e determina se a evolução é unitária. Este é o degrau que faltava entre `CLM-MAT-ALGLIN-002` e as notas de mecânica quântica. |
| `CLM-MAT-FUNC-003` | O teorema de Hahn–Banach depende do lema de Zorn, e portanto do axioma da escolha. | established | Rudin, cap. 3. Registra a dependência axiomática explicitada em `CLM-MAT-CONJ-002`. |
| `CLM-MAT-FUNC-004` | O espectro de um operador limitado em espaço de Banach complexo é não vazio e compacto, mas pode não conter nenhum autovalor. | established | Rudin, cap. 10. Contraexemplo canônico: o operador de deslocamento tem espectro no disco unitário e nenhum autovalor. Transportar a intuição de "autovalor" da dimensão finita produz erro aqui. |

## Limites e contraexemplos

- **Nem todo operador é limitado**: derivada e posição/momento não o são. Trabalhar com operadores não limitados exige gerenciar domínios explicitamente, e ignorar isso produz paradoxos aparentes.
- **Convergência tem várias noções**: forte, fraca, e fraca-*. Coincidem em dimensão finita e divergem aqui; afirmar "converge" sem qualificar é incompleto.
- **Base de Hilbert não é base algébrica**: séries infinitas convergentes na norma, não combinações lineares finitas. Uma base de Hamel de espaço de dimensão infinita é não enumerável e inútil na prática.
- **`L²` identifica funções iguais quase sempre**: os elementos são classes de equivalência, não funções. "Valor em um ponto" não é bem definido, o que importa quando se fala em função de onda.

## Relações

- [[Álgebra Linear]] <!-- relation:prerequisite -->
- [[Análise Real]] <!-- relation:prerequisite -->
- [[Teoria da Medida e Integração]] <!-- relation:prerequisite -->
- [[Topologia]] <!-- relation:prerequisite -->
- [[Teoria dos Conjuntos e Fundamentos]] <!-- relation:operational -->
- [[Fundamentos de Mecânica Quântica e Sistemas Abertos]] <!-- relation:extends --> — estados em `L²` e observáveis autoadjuntos instanciam esta estrutura.
- [[Fundamentos de Teoria Quântica de Campos e Teorias Efetivas]] <!-- relation:extends -->
- [[MOC — Matemática]] <!-- relation:navigation -->

## Fontes

- Walter Rudin. *Functional Analysis*. 2ª ed., McGraw-Hill, 1991. ISBN 978-0-07-054236-5.

## Condição de revisão

Estável. Revisar se o Vault ganhar nota de álgebras de operadores, que absorveria a formulação algébrica da teoria quântica.
