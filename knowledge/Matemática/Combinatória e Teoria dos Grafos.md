---
title: Combinatória e Teoria dos Grafos
aliases: [Grafos, Combinatória]
domain: matemática
kind: nota
status: active
epistemic_status: established
updated: 2026-07-28
verified_at: 2026-07-28
---

# Combinatória e teoria dos grafos

## Finalidade

Responder: **como se conta, e como se raciocina sobre relações discretas?** Grafo é a estrutura mínima para "coisas e ligações entre coisas" — é o objeto por trás de redes, dependências, e do próprio grafo de wikilinks deste Vault. A combinatória é o que permite afirmar que algo existe sem exibi-lo.

## Escopo

Contagem: princípio da casa dos pombos, inclusão–exclusão, coeficientes binomiais, funções geradoras. Grafos: definições e representações; conexidade; árvores; caminhos e ciclos eulerianos e hamiltonianos; emparelhamentos (Hall, König); coloração; planaridade (Kuratowski, Euler); fluxo máximo e corte mínimo; grafos aleatórios em nível de enunciado; expansão e espectro em nível de enunciado. **Escopo negativo:** algoritmos e sua complexidade (domínio de Computação), teoria de matroides, e combinatória enumerativa avançada.

## Pré-requisitos

- [[Lógica, Provas e Argumentação]] <!-- relation:prerequisite --> — indução e argumentos de existência não construtivos são o método dominante.

## Conceitos nucleares

- **Casa dos pombos**: `n+1` objetos em `n` caixas forçam repetição. Trivial de enunciar e responsável por uma quantidade desproporcional de teoremas de existência.
- **Grafo**: `G = (V, E)`. Simples, dirigido, ponderado — variações que mudam quais teoremas se aplicam.
- **Árvore**: conexo e acíclico; equivalentemente, conexo com `|V|−1` arestas. Toda árvore com ≥2 vértices tem pelo menos duas folhas.
- **Teorema de Hall**: existe emparelhamento saturando um lado sse toda subcoleção `S` satisfaz `|N(S)| ≥ |S|`. Condição necessária que se revela suficiente — o padrão característico da área.
- **Fluxo máximo = corte mínimo**: dualidade combinatória exata (Ford–Fulkerson), instância discreta da dualidade que a otimização trata em geral.
- **Fórmula de Euler**: para grafo planar conexo, `V − E + F = 2`. Dá limites (`E ≤ 3V − 6`) e daí a não planaridade de `K₅` e `K₃,₃`.
- **Coloração**: número cromático `χ(G)`. Determinar `χ` é difícil em geral; limites por grau (Brooks) são o que se usa.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-MAT-GRAFO-001` | Um grafo é planar se e somente se não contém subdivisão de `K₅` nem de `K₃,₃` (Kuratowski). | established | Diestel, cap. 4. Caracterização estrutural completa — rara nesta área, e por isso notável. |
| `CLM-MAT-GRAFO-002` | O valor do fluxo máximo entre dois vértices iguala a capacidade do corte mínimo que os separa. | established | Diestel, cap. 6. **Escopo:** o enunciado é sobre o valor ótimo; a eficiência de encontrá-lo é questão algorítmica, tratada em [[Algoritmos e Estruturas de Dados]] <!-- relation:operational -->. |
| `CLM-MAT-GRAFO-003` | O método probabilístico prova existência de objetos combinatórios sem construí-los, mostrando que a probabilidade de existirem é positiva. | established | Técnica devida a Erdős; Diestel, cap. 11, aplica a grafos aleatórios. **Limite declarado:** as provas são não construtivas — sabe-se que o objeto existe e frequentemente não se sabe exibir nenhum exemplo explícito. |

## Limites e contraexemplos

- **Euleriano e hamiltoniano não se parecem**: existe critério local simples para circuito euleriano (todos os graus pares, conexo); para ciclo hamiltoniano não há critério comparável, e decidir a existência é NP-completo.
- **Condições suficientes não são necessárias**: os teoremas de Dirac e Ore dão hamiltonicidade sob grau alto; grafos hamiltonianos de grau baixo existem em abundância. Usar a condição como teste é erro comum.
- **Grafo aleatório não é grafo típico do mundo**: o modelo de Erdős–Rényi tem distribuição de grau concentrada, ao contrário das redes empíricas. Conclusões do modelo não transferem sem justificativa — a aresta entre teoria de grafos e redes reais exige fonte que trate das duas.
- Casa dos pombos dá existência, nunca localização.

## Relações

- [[Lógica, Provas e Argumentação]] <!-- relation:prerequisite -->
- [[Algoritmos e Estruturas de Dados]] <!-- relation:operational --> — grafos são a estrutura de entrada de boa parte dos algoritmos.
- [[Probabilidade]] <!-- relation:extends --> — o método probabilístico e os grafos aleatórios.
- [[Recuperação de Informação]] <!-- relation:extends --> — estruturas de ligação e centralidade.
- [[MOC — Matemática]] <!-- relation:navigation -->

## Fontes

- Reinhard Diestel. *Graph Theory*. 5ª ed., Springer (Graduate Texts in Mathematics 173), 2017. ISBN 978-3-662-53621-6.

## Condição de revisão

Estável. Revisar se o Vault ganhar nota de redes complexas ou de teoria espectral de grafos.
