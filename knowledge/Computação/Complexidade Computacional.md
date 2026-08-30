---
title: Complexidade Computacional
aliases: [P vs NP, NP-completude, Classes de Complexidade]
domain: computação
kind: nota
status: active
epistemic_status: mixed
updated: 2026-08-30
verified_at: 2026-07-28
---

# Complexidade computacional

## Finalidade

Responder: **entre os problemas que têm solução, quais têm solução viável?** Classificar por recurso — tempo, espaço, aleatoriedade — é o que permite dizer, antes de programar, que um problema não terá algoritmo rápido a menos que uma conjectura central caia.

## Escopo

Modelos de custo e notação assintótica; classes P, NP, co-NP, PSPACE, EXP; verificação × solução; reduções polinomiais; NP-completude e teorema de Cook–Levin; problemas completos canônicos (SAT, clique, cobertura); hierarquia de tempo e espaço; classes aleatorizadas (BPP) e não uniformes (P/poly) em nível de enunciado; aproximação e inaproximabilidade em nível de enunciado. **Escopo negativo:** projeto de algoritmos específicos (nota própria), complexidade de comunicação, complexidade quântica, e criptografia (nota própria).

## Pré-requisitos

- [[Teoria da Computação]] <!-- relation:prerequisite --> — decidibilidade precede a pergunta de custo.
- [[Algoritmos e Estruturas de Dados]] <!-- relation:prerequisite --> — análise assintótica e o custo de operações básicas.
- [[Combinatória e Teoria dos Grafos]] <!-- relation:prerequisite --> — a maioria dos problemas completos canônicos é combinatória.

## Conceitos nucleares

- **P**: decidíveis em tempo polinomial determinístico. Aproximação convencional de "tratável", com ressalvas conhecidas.
- **NP**: soluções verificáveis em tempo polinomial dado um certificado. **Não** significa "não polinomial".
- **NP-completo**: em NP e tão difícil quanto qualquer problema de NP por redução polinomial. Se um deles estiver em P, todos estão.
- **Cook–Levin**: SAT é NP-completo. É o ponto de partida do qual todas as outras NP-completudes descendem por redução.
- **Teoremas de hierarquia**: mais tempo (ou espaço) decide estritamente mais problemas. São dos poucos resultados de separação que se sabe provar.
- **BPP**: decidíveis em tempo polinomial com erro limitado por aleatoriedade. Acredita-se que `BPP = P`, sem prova.
- **Aproximação**: para problemas de otimização NP-difíceis, algoritmos com garantia de razão; o PCP mostra que, para alguns, mesmo aproximar é NP-difícil.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-COMP-CPX-001` | SAT é NP-completo (Cook–Levin). | established | Arora & Barak, cap. 2; Sipser, cap. 7. Resultado independente de Cook (1971) e Levin (1973). |
| `CLM-COMP-CPX-002` | `P ≠ NP` não está demonstrado; é conjectura, e a mais consequente da área. | open | Arora & Barak, cap. 1 e 3, tratam explicitamente como aberto. **Evidência circunstancial:** décadas sem algoritmo polinomial para nenhum problema NP-completo, e barreiras conhecidas (relativização, provas naturais, algebrização) que excluem as técnicas disponíveis. Nenhuma dessas é demonstração. Marcar como `established` seria erro de status. |
| `CLM-COMP-CPX-003` | Existem separações provadas entre classes por recursos: `P ⊊ EXP` e `L ⊊ PSPACE`, pelos teoremas de hierarquia. | established | Arora & Barak, cap. 3. **Contraste importante:** sabemos separar classes distantes por diagonalização, e não sabemos separar as adjacentes que importam — é essa assimetria que caracteriza o estado da área. |
| `CLM-COMP-CPX-004` | Tempo polinomial é aproximação imperfeita de viabilidade prática. | established | Arora & Barak, cap. 1, discute o critério. Um algoritmo `O(n¹⁰⁰)` é polinomial e inútil; um exponencial com constante minúscula pode ser prático na faixa de interesse. A classe captura robustez a modelo de máquina, não desempenho. |

## Limites e contraexemplos

- **NP-difícil não impede resolver instâncias**: SAT é NP-completo e resolvedores industriais tratam rotineiramente instâncias com milhões de variáveis. A dificuldade é sobre o pior caso na família inteira, não sobre a instância que você tem.
- **"NP" mal usado é erro frequente**: "este problema é NP" é vazio (quase tudo prático está em NP); o conteúdo está em ser NP-*completo* ou NP-*difícil*.
- **Reduções preservam dificuldade, não estrutura**: uma redução pode transformar uma instância natural em algo irreconhecível; a existência da redução não dá método prático.
- **Complexidade de pior caso não modela distribuição real**: complexidade de caso médio é teoria separada, e conclusões de uma não transferem para a outra.

## Relações

- [[Teoria da Computação]] <!-- relation:prerequisite -->
- [[Algoritmos e Estruturas de Dados]] <!-- relation:prerequisite -->
- [[Criptografia]] <!-- relation:extends --> — a segurança computacional pressupõe dificuldade, e portanto pressupõe conjecturas desta nota.
- [[Otimização]] <!-- relation:contrasts --> — otimização contínua convexa é tratável por razões distintas das combinatórias.
- [[MOC — Ciência da Computação]] <!-- relation:navigation -->

## Fontes

- Sanjeev Arora e Boaz Barak. *Computational Complexity: A Modern Approach*. Cambridge University Press, 2009. ISBN 978-0-521-42426-4.
- Michael Sipser. *Introduction to the Theory of Computation*. 3ª ed., Cengage Learning, 2013. ISBN 978-1-133-18779-0.

## Condição de revisão

Revisar `CLM-COMP-CPX-002` se houver anúncio verificado de resolução de `P vs NP` — o claim está marcado `open` justamente para que a mudança de status seja explícita e datada.
