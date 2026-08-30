---
title: Teoria da Computação
aliases: [Computabilidade, Autômatos, Máquina de Turing]
domain: computação
kind: nota
status: active
epistemic_status: established
updated: 2026-07-28
verified_at: 2026-07-28
---

# Teoria da computação

## Finalidade

Responder: **o que pode ser computado, independentemente de máquina, linguagem ou tempo disponível?** É a fronteira lógica anterior a qualquer questão de eficiência: há problemas que nenhum programa resolve, e saber quais é o que impede perseguir o impossível.

## Escopo

Autômatos finitos e linguagens regulares; autômatos de pilha e linguagens livres de contexto; máquinas de Turing e a hierarquia de Chomsky; decidibilidade e reconhecibilidade; o problema da parada; redução como técnica de prova; teorema de Rice; tese de Church–Turing; computabilidade relativa e graus de Turing em nível de enunciado. **Escopo negativo:** complexidade e classes de recursos (nota própria), semântica de linguagens de programação, e lógica matemática além do necessário (domínio de Matemática).

## Pré-requisitos

- [[Lógica, Provas e Argumentação]] <!-- relation:prerequisite --> — diagonalização e prova por contradição são o método central.
- [[Combinatória e Teoria dos Grafos]] <!-- relation:prerequisite --> — contagem e argumentos de cardinalidade sustentam os resultados de não computabilidade.

## Conceitos nucleares

- **Máquina de Turing**: modelo com fita infinita e controle finito. Sua importância é de robustez: todos os modelos razoáveis de computação propostos desde 1936 têm o mesmo poder.
- **Decidível × reconhecível**: decidível = existe máquina que sempre para com resposta correta. Reconhecível = para e aceita nas instâncias positivas, podendo não parar nas negativas. A diferença é onde mora o problema da parada.
- **Problema da parada**: não existe algoritmo que, dado um programa e uma entrada, decida se ele para. Provado por diagonalização.
- **Redução**: se `A` reduz a `B` e `B` é decidível, `A` é decidível; contrapositivamente, `A` indecidível implica `B` indecidível. É como a indecidibilidade se propaga.
- **Teorema de Rice**: toda propriedade não trivial da *linguagem* reconhecida por uma máquina é indecidível. Consequência: análise estática perfeita de comportamento de programas é impossível em geral.
- **Tese de Church–Turing**: a noção intuitiva de "algoritmo" coincide com a computabilidade de Turing. É tese, não teorema.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-COMP-TEO-001` | O problema da parada é indecidível. | established | Sipser, cap. 4 (prova por diagonalização). Resultado de Turing (1936). |
| `CLM-COMP-TEO-002` | Toda propriedade não trivial da linguagem reconhecida por uma máquina de Turing é indecidível (teorema de Rice). | established | Sipser, cap. 5. **Escopo:** vale para propriedades *semânticas* (da linguagem reconhecida), não sintáticas (do código). Verificar se um programa tem mais de 100 linhas é decidível; verificar se ele calcula uma função específica não é. |
| `CLM-COMP-TEO-003` | A tese de Church–Turing é uma afirmação sobre a adequação de uma formalização a um conceito intuitivo, e por isso não é demonstrável nem refutável por prova matemática. | established | Sipser, §3.3, apresenta-a explicitamente como tese. **Evidência a favor:** a convergência de modelos independentes (λ-cálculo, funções recursivas, máquinas de registradores) ao mesmo conjunto de funções computáveis. Isso é evidência forte, não demonstração — a distinção importa e é frequentemente apagada. |

## Limites e contraexemplos

- **Indecidível não é "difícil"**: é a ausência de qualquer algoritmo correto para todas as instâncias. Ferramentas práticas de análise estática funcionam por serem incompletas ou não sólidas em casos escolhidos — não por contornarem Rice.
- **A tese não é sobre eficiência**: equivalência de poder computacional não implica equivalência de custo. Um modelo pode simular outro com sobrecarga exponencial.
- **Computação hipercomputacional é especulação**: propostas que excederiam a barreira de Turing dependem de recursos físicos idealizados (precisão infinita, tempo infinito em intervalo finito) sem realização conhecida. Registrado como `speculative`, fora do corpus estabelecido.
- Hierarquia de Chomsky classifica linguagens, não dificuldade prática: linguagens regulares podem exigir autômatos de tamanho exponencial na descrição.

## Relações

- [[Lógica, Provas e Argumentação]] <!-- relation:prerequisite -->
- [[Complexidade Computacional]] <!-- relation:extends --> — o que é decidível, mas a que custo.
- [[Algoritmos e Estruturas de Dados]] <!-- relation:extends -->
- [[MOC — Ciência da Computação]] <!-- relation:navigation -->

## Fontes

- Michael Sipser. *Introduction to the Theory of Computation*. 3ª ed., Cengage Learning, 2013. ISBN 978-1-133-18779-0.

## Condição de revisão

Estável. Resultados de 1936–1953; nenhuma revisão prevista salvo criação de nota sobre computação quântica, que trataria o poder computacional relativo com fonte própria.
