---
title: Algoritmos e Estruturas de Dados
domain: computação
kind: nota
status: active
epistemic_status: established
updated: 2026-07-18
verified_at: 2026-07-18
---

# Algoritmos e estruturas de dados

## Finalidade

Responder: **por que a organização dos dados muda o custo de resolver o mesmo problema?** Correção e complexidade são as duas obrigações de qualquer procedimento — inclusive dos gates deste Vault.

## Escopo

Análise assintótica (O, Ω, Θ) e seus limites; corretude (invariantes, terminação); estruturas nucleares (arrays, listas, pilhas/filas, tabelas hash, árvores balanceadas, heaps, grafos); paradigmas (divisão e conquista, guloso, programação dinâmica); ordenação e busca; grafos (BFS/DFS, caminhos mínimos). **Escopo negativo:** teoria da computação (decidibilidade, classes de complexidade — nota futura), algoritmos distribuídos/paralelos e detalhes de implementação em Python.

## Pré-requisitos

- [[Lógica, Provas e Argumentação]] <!-- relation:prerequisite --> — corretude é prova (invariante + terminação).
- [[Probabilidade]] <!-- relation:prerequisite --> — análise de caso médio e estruturas aleatorizadas.

## Conceitos nucleares

- **Assintótica**: `O` limita por cima, `Θ` aperta; constantes e termos baixos importam na prática, mas a taxa de crescimento domina no limite.
- **Invariante de laço**: o instrumento padrão de prova de corretude iterativa.
- **Tabela hash**: `O(1)` esperado sob hipótese de dispersão — adversários e colisões degradam a `O(n)`.
- **Árvores balanceadas**: `O(log n)` garantido no pior caso — o contraste estrutural com hash.
- **Programação dinâmica**: subestrutura ótima + sobreposição de subproblemas; sem elas, memoizar não ajuda.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-CS-ALG-001` | A escolha de estrutura de dados altera custos de tempo e espaço mesmo quando a função externa computada é equivalente. | established | Análise padrão (ex.: busca em lista `Θ(n)` vs árvore balanceada `Θ(log n)` vs hash `O(1)` esperado); entradas triviais são o contraexemplo de escopo. |
| `CLM-CS-ALG-002` | Comparação por chaves impõe limite inferior `Ω(n log n)` à ordenação; algoritmos que fogem do modelo (counting/radix) fogem também do limite, sob hipóteses sobre as chaves. | established | Prova por árvore de decisão; a fuga por não-comparação delimita o modelo, não o refuta. |

## Limites e contraexemplos

- Assintótica esconde constantes: para `n` pequeno, `O(n²)` simples vence `O(n log n)` sofisticado.
- Hash com função pobre ou adversarial: pior caso linear — a hipótese probabilística é parte do contrato.
- Guloso sem prova de troca segura produz soluções subótimas (contraexemplos clássicos em moedas não canônicas).
- Big-O igual não significa desempenho igual em hardware real (cache, localidade) — ver o futuro domínio de sistemas.

## Relações

- [[Lógica, Provas e Argumentação]] <!-- relation:prerequisite -->
- [[Sistemas Operacionais]] <!-- relation:extends --> — custo real depende de memória e escalonamento.
- [[Recuperação de Informação]] <!-- relation:extends --> — índices invertidos e ranking instanciam estas estruturas.

## Fontes

- Thomas H. Cormen, Charles E. Leiserson, Ronald L. Rivest e Clifford Stein. *Introduction to Algorithms*. 4ª ed., MIT Press, 2022.
- Jon Kleinberg e Éva Tardos. *Algorithm Design*. Pearson, 2006.

## Condição de revisão

Estável; revisar quando teoria da computação (decidibilidade/NP) ganhar nota própria, para mover a fronteira de complexidade.
