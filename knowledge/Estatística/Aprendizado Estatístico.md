---
title: Aprendizado Estatístico
aliases: [Statistical Learning, Viés-Variância, Regularização]
domain: estatística
kind: nota
status: active
epistemic_status: established
updated: 2026-07-28
verified_at: 2026-07-28
---

# Aprendizado estatístico

## Finalidade

Responder: **por que um modelo que ajusta bem os dados vistos pode falhar nos não vistos, e o que controla isso?** É a teoria que separa ajuste de generalização — a distinção sem a qual nenhuma avaliação de sistema preditivo significa alguma coisa.

## Escopo

Risco esperado e risco empírico; decomposição viés–variância; sobreajuste e capacidade; regularização (`L1`, `L2`, *early stopping*); validação cruzada e suas armadilhas; seleção de modelos (AIC, BIC, validação); métodos lineares e suas extensões; árvores e *ensembles*; *boosting* e *bagging*; maldição da dimensionalidade; complexidade de VC e limites de generalização em nível de enunciado. **Escopo negativo:** arquiteturas de redes profundas e sua prática de treinamento (domínio de IA), otimização numérica (domínio de Matemática), e avaliação de sistemas em produção (domínio de IA).

## Pré-requisitos

- [[Probabilidade]] <!-- relation:prerequisite --> — risco é esperança sobre a distribuição geradora.
- [[Estimação e Testes de Hipótese]] <!-- relation:prerequisite --> — viés, variância e consistência vêm de lá.
- [[Álgebra Linear]] <!-- relation:prerequisite -->
- [[Otimização]] <!-- relation:prerequisite --> — o ajuste é minimização de risco empírico.

## Conceitos nucleares

- **Risco esperado × risco empírico**: `R(f) = E[L(Y, f(X))]` contra `R̂(f) = (1/n)ΣL(y_i, f(x_i))`. Toda a dificuldade está na diferença entre os dois.
- **Decomposição viés–variância**: para perda quadrática, `erro = viés² + variância + ruído irredutível`. O último termo limita qualquer modelo.
- **Capacidade**: flexibilidade da família de funções. Capacidade alta reduz viés e aumenta variância.
- **Regularização**: penalizar complexidade. `L2` (ridge) encolhe; `L1` (lasso) encolhe e zera coeficientes, produzindo seleção de variáveis.
- **Validação cruzada**: estima risco fora da amostra reutilizando os dados. Só é válida se **toda** decisão dependente dos dados estiver dentro do laço.
- **Maldição da dimensionalidade**: em dimensão alta, vizinhanças locais deixam de ser locais; métodos baseados em proximidade degradam.
- **Ensembles**: *bagging* reduz variância por média sobre reamostras; *boosting* reduz viés ajustando sequencialmente aos resíduos.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-EST-APREND-001` | O erro de predição decompõe-se em viés ao quadrado, variância e ruído irredutível; nenhum modelo reduz o terceiro termo. | established | Hastie, Tibshirani & Friedman, §7.3. **Escopo:** a decomposição exata é para perda quadrática; para outras perdas existem análogos, não a mesma identidade. |
| `CLM-EST-APREND-002` | Selecionar variáveis ou hiperparâmetros usando todos os dados e depois validar com os mesmos dados produz estimativa de erro otimista e inválida. | established | Hastie et al., §7.10.2, demonstra o efeito com exemplo numérico. É o erro de "vazamento" mais comum e uma causa direta de resultados não replicáveis. |
| `CLM-EST-APREND-003` | Não existe algoritmo de aprendizado uniformemente superior sobre todas as distribuições possíveis (*no free lunch*). | established | Resultado de Wolpert; discutido em Hastie et al., cap. 2 e 7. **Escopo:** o enunciado é sobre o conjunto de *todos* os problemas possíveis, a maioria dos quais é ruído sem estrutura. Não implica que a escolha de método seja arbitrária em problemas reais — implica que a justificativa vem de suposições sobre o domínio, não de superioridade universal. |
| `CLM-EST-APREND-004` | Regularização `L1` produz soluções esparsas; `L2` não. | established | Hastie et al., §3.4. Consequência da geometria da bola de norma: os vértices da `L1` tocam os eixos. |

## Limites e contraexemplos

- **Validação cruzada não é imune a dependência**: com dados temporais ou agrupados, a divisão aleatória vaza informação entre folds e superestima o desempenho.
- **AIC e BIC respondem perguntas diferentes**: AIC visa erro preditivo; BIC visa identificar o modelo verdadeiro sob prior implícito. Usá-los como intercambiáveis é erro de objetivo.
- **A curva clássica de viés–variância não descreve todos os regimes**: modelos fortemente sobreparametrizados podem generalizar bem apesar de interpolar os dados de treino, fenômeno hoje bem documentado empiricamente. Registrado aqui como `open` quanto à explicação teórica; o **fato empírico** é o que está estabelecido, não o mecanismo.
- **Erro de teste é estimativa, não verdade**: reutilizar o conjunto de teste para decisões o converte gradualmente em conjunto de treino.

## Relações

- [[Estimação e Testes de Hipótese]] <!-- relation:prerequisite -->
- [[Probabilidade]] <!-- relation:prerequisite -->
- [[Otimização]] <!-- relation:prerequisite -->
- [[Inferência Bayesiana]] <!-- relation:contrasts --> — regularização corresponde a prior sob a leitura MAP.
- [[Fundamentos de Aprendizado de Máquina e Modelos de Linguagem]] <!-- relation:extends --> — a instância em redes profundas.
- [[Avaliação e Proveniência de Sistemas de IA]] <!-- relation:operational --> — protocolos de avaliação dependem destes resultados.
- [[Reprodutibilidade e Replicação]] <!-- relation:evidence -->
- [[MOC — Estatística e Inferência]] <!-- relation:navigation -->

## Fontes

- Trevor Hastie, Robert Tibshirani e Jerome Friedman. *The Elements of Statistical Learning: Data Mining, Inference, and Prediction*. 2ª ed., Springer (Springer Series in Statistics), 2009. ISBN 978-0-387-84857-0. Edição eletrônica disponibilizada pelos autores.

## Condição de revisão

Revisar quando o Vault ganhar nota dedicada a generalização em regime sobreparametrizado — o ponto marcado como `open` em Limites exige fonte primária própria.
