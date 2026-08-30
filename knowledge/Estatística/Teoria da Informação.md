---
title: Teoria da Informação
aliases: [Entropia de Shannon, Informação Mútua, Shannon]
domain: estatística
kind: nota
status: active
epistemic_status: established
updated: 2026-07-28
verified_at: 2026-07-28
---

# Teoria da informação

## Finalidade

Responder: **quanto pode ser comprimido, e quanto pode ser transmitido de forma confiável?** Shannon converteu "informação" de metáfora em quantidade com unidade e teoremas de limite. É também um dos pontos em que o Vault precisa de mais cuidado: "entropia" aparece em física e em teoria da informação, e a identidade entre as duas é matemática, não automática.

## Escopo

Entropia, entropia conjunta e condicional; informação mútua; divergência de Kullback–Leibler; desigualdade de processamento de dados; codificação de fonte e limite de compressão sem perda; codificação de canal e capacidade; teorema de codificação de canal ruidoso; taxa–distorção; princípio de máxima entropia; conexão com verossimilhança e com seleção de modelos. **Escopo negativo:** códigos corretores específicos, teoria de informação de redes, e a entropia termodinâmica como grandeza física (domínio de Física).

## Pré-requisitos

- [[Probabilidade]] <!-- relation:prerequisite --> — todas as grandezas são funcionais de distribuições.
- [[Análise Real]] <!-- relation:prerequisite --> — convexidade e desigualdade de Jensen sustentam quase todos os resultados.

## Conceitos nucleares

- **Entropia**: `H(X) = −Σ p(x) log p(x)`. Mede incerteza média; em bits com `log₂`. Máxima na uniforme, nula no determinístico.
- **Divergência KL**: `D(p‖q) = Σ p log(p/q)`. Não negativa, nula sse `p=q`. **Não é métrica** — é assimétrica e viola a desigualdade triangular.
- **Informação mútua**: `I(X;Y) = H(X) − H(X|Y) = D(p_{XY} ‖ p_X p_Y)`. Zero sse independentes; simétrica.
- **Processamento de dados**: se `X → Y → Z` é cadeia de Markov, `I(X;Z) ≤ I(X;Y)`. Pós-processar não cria informação.
- **Codificação de fonte**: o comprimento médio ótimo de código sem perda é limitado inferiormente por `H(X)` e atingível dentro de 1 bit.
- **Capacidade de canal**: `C = max_{p(x)} I(X;Y)`. Abaixo de `C`, existe código com erro arbitrariamente pequeno; acima, não.
- **Máxima entropia**: dada restrição de momentos, a distribuição de máxima entropia é a menos comprometida com o que não foi especificado.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-EST-INFO-001` | A entropia de Shannon é o limite inferior do comprimento médio de qualquer código sem perda unicamente decodificável para a fonte. | established | Cover & Thomas, cap. 5 (desigualdade de Kraft e teorema de codificação de fonte). **Escopo:** vale para fonte com distribuição conhecida; compressão universal atinge o limite assintoticamente sem conhecê-la. |
| `CLM-EST-INFO-002` | Existe codificação com probabilidade de erro arbitrariamente pequena para qualquer taxa abaixo da capacidade do canal, e não existe acima dela. | established | Cover & Thomas, cap. 7 (teorema de codificação de canal ruidoso e sua recíproca). **Limite:** o teorema é de existência e assintótico em comprimento de bloco; não fornece código construtivo nem garantia a comprimento finito. |
| `CLM-EST-INFO-003` | Minimizar a divergência KL do modelo à distribuição empírica equivale a maximizar a verossimilhança. | established | Cover & Thomas, cap. 11. É a identidade que conecta este domínio à inferência estatística e ao treinamento por entropia cruzada. |
| `CLM-EST-INFO-004` | A identidade formal entre a entropia de Shannon e a entropia de Gibbs–Boltzmann é uma coincidência estrutural das expressões, e a interpretação física exige argumento adicional. | established | Cover & Thomas, cap. 4, trata a analogia com cautela explícita. **Escopo declarado:** a política do Vault proíbe tratar vocabulário compartilhado como relação. A ponte com [[Fundamentos de Termodinâmica e Mecânica Estatística]] <!-- relation:contrasts --> existe na literatura (Jaynes, Landauer), mas o que este claim afirma é apenas que a igualdade de fórmula **não** estabelece por si a identidade dos conceitos. |

## Limites e contraexemplos

- **KL não é distância**: `D(p‖q) ≠ D(q‖p)`. Usá-la como métrica produz conclusões erradas sobre "proximidade" de distribuições.
- **Informação mútua alta não é causalidade**: `I(X;Y)` é simétrica e não distingue direção. Causalidade exige o aparato de intervenção, não de associação.
- **Entropia diferencial não é o análogo contínuo direto**: pode ser negativa e não é invariante por mudança de variável. A informação mútua, sim, é bem comportada no caso contínuo.
- **Capacidade é limite, não desempenho**: sistemas reais operam abaixo dela, e a distância depende de restrições de complexidade e latência que o teorema não modela.

## Relações

- [[Probabilidade]] <!-- relation:prerequisite -->
- [[Estimação e Testes de Hipótese]] <!-- relation:extends --> — verossimilhança e KL são a mesma quantidade sob outra leitura.
- [[Aprendizado Estatístico]] <!-- relation:extends --> — entropia cruzada como função de perda.
- [[Fundamentos de Termodinâmica e Mecânica Estatística]] <!-- relation:contrasts --> — a relação com a entropia física é declarada como contraste, não como identidade.
- [[Recuperação de Informação]] <!-- relation:operational -->
- [[MOC — Estatística e Inferência]] <!-- relation:navigation -->

## Fontes

- Thomas M. Cover e Joy A. Thomas. *Elements of Information Theory*. 2ª ed., Wiley-Interscience, 2006. ISBN 978-0-471-24195-9.

## Condição de revisão

Estável. Revisar `CLM-EST-INFO-004` se o Vault ganhar nota dedicada ao princípio de Landauer, que trataria a ponte física com fonte primária própria.
