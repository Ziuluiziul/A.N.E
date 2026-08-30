---
title: Estimação e Testes de Hipótese
aliases: [Inferência Frequentista, Máxima Verossimilhança, Testes]
domain: estatística
kind: nota
status: active
epistemic_status: established
updated: 2026-07-28
verified_at: 2026-07-28
---

# Estimação e testes de hipótese

## Finalidade

Responder: **o que exatamente um estimador estima, e o que um teste de hipótese autoriza a concluir?** É o maquinário frequentista padrão — e o lugar onde a distância entre o que o formalismo garante e o que se afirma na prática é maior.

## Escopo

Modelo estatístico e suficiência; estimadores pontuais (momentos, máxima verossimilhança); propriedades (viés, consistência, eficiência); informação de Fisher e cota de Cramér–Rao; estimação intervalar; testes de hipótese, erros tipo I e II, potência; lema de Neyman–Pearson; razão de verossimilhança; valor-p e sua definição operacional; comparações múltiplas. **Escopo negativo:** inferência bayesiana (nota própria), teoria da decisão em profundidade, e a crítica metodológica ao uso de testes (domínio de Metodologia).

## Pré-requisitos

- [[Probabilidade]] <!-- relation:prerequisite --> — a distribuição amostral de um estimador é o objeto central.
- [[Teoria da Medida e Integração]] <!-- relation:prerequisite --> — verossimilhança é densidade de Radon–Nikodym; suficiência é enunciada com esperança condicional.
- [[Otimização]] <!-- relation:prerequisite --> — máxima verossimilhança é problema de maximização.

## Conceitos nucleares

- **Verossimilhança**: `L(θ | x) = f(x | θ)` vista como função de `θ`. **Não** é distribuição de probabilidade sobre `θ`; não integra 1.
- **Suficiência**: `T(X)` é suficiente se a distribuição condicional de `X` dado `T` não depende de `θ`. Fatoração de Neyman é o critério prático.
- **Consistência × não viés**: são independentes. O EMV é consistente sob condições de regularidade e frequentemente viesado — o de variância normal é o exemplo padrão.
- **Informação de Fisher**: `I(θ) = E[(∂/∂θ log f)²]`. Cramér–Rao dá cota inferior para a variância de estimadores não viesados.
- **Erro tipo I (`α`)**: rejeitar `H₀` verdadeira. **Tipo II (`β`)**: não rejeitar `H₀` falsa. **Potência** `= 1 − β`.
- **Neyman–Pearson**: para hipóteses simples, o teste de razão de verossimilhança é uniformemente mais potente ao nível `α`.
- **Valor-p**: probabilidade, **sob `H₀`**, de observar estatística tão ou mais extrema que a observada. É afirmação sobre os dados dado o modelo, nunca sobre a hipótese.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-EST-INFER-001` | O valor-p é `P(dados tão ou mais extremos | H₀)`, e **não** `P(H₀ | dados)`; a inversão dos dois é inválida sem prior. | established | Casella & Berger, §8.3. A quantidade `P(H₀ | dados)` exige o teorema de Bayes e uma distribuição a priori, que o arcabouço frequentista não fornece. Esta é a confusão mais consequente da estatística aplicada. |
| `CLM-EST-INFER-002` | Um intervalo de confiança de 95% é uma afirmação sobre o procedimento em repetição, não sobre a probabilidade de o parâmetro estar no intervalo calculado. | established | Casella & Berger, §9.1. Uma vez calculado o intervalo, o parâmetro está ou não está nele; a probabilidade 0,95 é a taxa de cobertura do método sob amostragem repetida. |
| `CLM-EST-INFER-003` | O estimador de máxima verossimilhança é consistente e assintoticamente eficiente sob condições de regularidade; fora delas, pode ser inconsistente. | established | Casella & Berger, §10.1. **Limite declarado:** as condições incluem identificabilidade, suporte não dependente de `θ` e diferenciabilidade. O exemplo de Neyman–Scott, com parâmetros incidentais crescendo com a amostra, dá EMV inconsistente. |
| `CLM-EST-INFER-004` | Não rejeitar `H₀` não é evidência de que `H₀` seja verdadeira. | established | Consequência direta da assimetria do arcabouço: o teste controla o erro tipo I, e a taxa de erro tipo II depende da potência, frequentemente não reportada. Ausência de evidência exige análise de potência para virar evidência de ausência. |

## Limites e contraexemplos

- **Significância estatística não é relevância**: com `n` grande, diferenças arbitrariamente pequenas atingem `p < 0,05`. Tamanho de efeito e intervalo são obrigatórios para leitura.
- **Comparações múltiplas destroem a taxa nominal**: 20 testes independentes ao nível 0,05 dão ~64% de chance de ao menos um falso positivo. Correção não é opcional.
- **A cota de Cramér–Rao só vale para não viesados** e sob regularidade; estimadores viesados podem ter erro quadrático médio menor — o estimador de James–Stein domina a média amostral em dimensão ≥ 3.
- **O modelo é premissa, não conclusão**: toda garantia acima é condicional à especificação correta. Robustez a má especificação é questão separada e não é fornecida pelos teoremas.

## Relações

- [[Probabilidade]] <!-- relation:prerequisite -->
- [[Teoria da Medida e Integração]] <!-- relation:prerequisite -->
- [[Inferência Bayesiana]] <!-- relation:contrasts --> — trata `θ` como aleatório e responde a pergunta que o valor-p não responde.
- [[Inferência e Incerteza]] <!-- relation:extends -->
- [[Desenho Experimental e Causalidade]] <!-- relation:operational --> — identificação precede estimação; estimar bem um efeito não identificado não ajuda.
- [[Reprodutibilidade e Replicação]] <!-- relation:evidence --> — o uso incorreto destes procedimentos é causa documentada da crise de replicação.
- [[MOC — Estatística e Inferência]] <!-- relation:navigation -->

## Fontes

- George Casella e Roger L. Berger. *Statistical Inference*. 2ª ed., Duxbury Press, 2002. ISBN 978-0-534-24312-8.

## Condição de revisão

Estável quanto à teoria. Revisar se o Vault ganhar nota de teoria da decisão estatística.
