---
title: Raciocínio, Julgamento e Decisão
aliases: [Heurísticas e Vieses, Vieses Cognitivos, Julgamento sob Incerteza]
domain: cognição
kind: nota
status: active
epistemic_status: mixed
updated: 2026-07-28
verified_at: 2026-07-28
---

# Raciocínio, julgamento e decisão

## Finalidade

Responder: **como pessoas julgam probabilidade e decidem sob incerteza, e onde isso se afasta sistematicamente da norma estatística?** É a nota que fecha o circuito do Vault: usa [[Probabilidade]] <!-- relation:prerequisite --> como norma, [[Desenho Experimental e Causalidade]] <!-- relation:prerequisite --> como método, e é o campo em que a própria [[Reprodutibilidade e Replicação]] <!-- relation:evidence --> foi posta à prova de forma mais dura.

## Escopo

Heurísticas de representatividade, disponibilidade e ancoragem; negligência da taxa-base; falácia da conjunção; enquadramento e aversão à perda; excesso de confiança e calibração de julgamento; raciocínio dedutivo e o efeito de conteúdo; racionalidade limitada; o estado replicativo dos achados clássicos. **Escopo negativo:** economia comportamental aplicada a política pública, psicometria de inteligência, e psicologia clínica.

## Pré-requisitos

- [[Probabilidade]] <!-- relation:prerequisite --> — sem a norma não há desvio a medir; "viés" é definido em relação a um padrão normativo explícito.
- [[Estimação e Testes de Hipótese]] <!-- relation:prerequisite --> — os achados do campo são estimativas com incerteza, e é onde a leitura descuidada custa caro.
- [[Bases Neurais da Cognição]] <!-- relation:prerequisite -->

## Conceitos nucleares

- **Representatividade**: julgar probabilidade pela semelhança com um protótipo. Produz negligência da taxa-base e insensibilidade ao tamanho da amostra.
- **Disponibilidade**: julgar frequência pela facilidade de recuperar exemplos. Confunde frequência real com saliência e cobertura.
- **Ancoragem**: estimativas se deslocam na direção de um valor inicial arbitrário, mesmo quando reconhecido como irrelevante.
- **Negligência da taxa-base**: ignorar a prevalência ao avaliar evidência diagnóstica. É exatamente o termo do prior no teorema de Bayes.
- **Falácia da conjunção**: julgar `P(A e B) > P(A)`. Viola um axioma, não uma convenção.
- **Enquadramento**: escolhas se invertem conforme a descrição de opções logicamente equivalentes.
- **Racionalidade limitada**: os desvios são compreensíveis como adaptação a restrição de tempo, informação e computação — o que **explica** sem tornar normativo.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-COG-JULG-001` | Julgamentos de probabilidade são frequentemente produzidos por heurísticas — representatividade, disponibilidade e ancoragem — que geram desvios sistemáticos e previsíveis em relação à norma probabilística. | established | Tversky e Kahneman, "Judgment under Uncertainty: Heuristics and Biases", *Science* 185(4157):1124–1131 (1974), DOI `10.1126/science.185.4157.1124` — verificado na fonte em 28/07/2026. O artigo apresenta exatamente essas três heurísticas. **Escopo:** "sistemáticas e previsíveis" é a afirmação central e é o que sustenta o campo; a magnitude de efeito em cada paradigma específico é questão separada, tratada abaixo. |
| `CLM-COG-JULG-002` | A negligência da taxa-base é, formalmente, omissão do termo do prior no teorema de Bayes. | established | Identificação direta entre o achado empírico e a estrutura de [[Inferência Bayesiana]] <!-- relation:extends -->. É a aresta mais produtiva desta nota: o "viés" é a distância a uma norma que o Vault já define formalmente em outro domínio. |
| `CLM-COG-JULG-003` | Em uma replicação sistemática de 100 estudos experimentais e correlacionais de psicologia, 97% dos originais reportavam resultado estatisticamente significativo e 36% das replicações atingiram significância na mesma direção, com tamanhos de efeito de replicação em torno da metade dos originais. | established | Open Science Collaboration, "Estimating the reproducibility of psychological science", *Science* 349(6251):aac4716 (2015), DOI `10.1126/science.aac4716` — números verificados na fonte em 28/07/2026. **Escopo estrito:** a amostra é de três periódicos de psicologia; o resultado **não** é um veredito sobre achados individuais nem sobre o campo inteiro, e "falha em replicar" não equivale a "falso". |
| `CLM-COG-JULG-004` | O estado replicativo dos achados deste campo é heterogêneo: alguns efeitos são robustos e replicam consistentemente, outros são substancialmente menores que o originalmente reportado ou não replicam. | supported | Segue de `CLM-COG-JULG-003` aplicado a este campo específico. **Status deliberadamente `supported`, não `established`:** afirmar qual efeito individual sobrevive exigiria uma meta-análise por paradigma, que não foi consultada aqui. O que se afirma é a heterogeneidade, não um veredito item a item. Tratar qualquer resultado clássico deste campo como estabelecido sem checar seu estado replicativo atual é erro que esta nota existe para prevenir. |

## Limites e contraexemplos

- **"Viés" pressupõe norma**: chamar um julgamento de enviesado exige declarar o padrão normativo. Em ambientes com estrutura diferente da assumida, a mesma heurística pode ser a resposta melhor calibrada.
- **Achado de laboratório não transfere automaticamente**: tarefas com apostas hipotéticas e amostras de estudantes têm validade externa limitada, e a extrapolação para decisão profissional ou política é passo separado que exige evidência própria.
- **A literatura de vieses sofre dos vieses que estuda**: seleção de resultados publicáveis, flexibilidade analítica e enquadramento afetam o próprio campo. É a razão de `CLM-COG-JULG-003` estar nesta nota e não apenas em Metodologia.
- **Dicotomia de "dois sistemas" é modelo, não anatomia**: a divisão em processamento rápido/automático e lento/deliberado é organizadora e não corresponde a duas estruturas identificadas. Usá-la como se fosse mecanismo é reificação.
- **Vieses em modelos de linguagem são fenômeno distinto**: sistemas de IA exibem padrões de resposta que recebem os mesmos nomes. A origem é diferente e a aresta é de **contraste**, não de evidência — sem fonte que trate explicitamente dos dois, a ponte não se faz.

## Relações

- [[Probabilidade]] <!-- relation:prerequisite -->
- [[Estimação e Testes de Hipótese]] <!-- relation:prerequisite -->
- [[Inferência Bayesiana]] <!-- relation:extends --> — a norma da qual a negligência da taxa-base é o desvio.
- [[Bases Neurais da Cognição]] <!-- relation:prerequisite -->
- [[Percepção e Psicofísica]] <!-- relation:extends --> — critério de resposta e viés de julgamento são a mesma família de problema.
- [[Reprodutibilidade e Replicação]] <!-- relation:evidence --> — o campo é caso de estudo e objeto do próprio problema.
- [[Desenho Experimental e Causalidade]] <!-- relation:prerequisite -->
- [[Segurança, Guardrails e Avaliação]] <!-- relation:contrasts --> — "viés" em sistemas de IA é homônimo com origem distinta.
- [[MOC — Cognição]] <!-- relation:navigation -->

## Fontes

- Amos Tversky e Daniel Kahneman. "Judgment under Uncertainty: Heuristics and Biases". *Science* 185(4157), 1124–1131 (1974). DOI `10.1126/science.185.4157.1124`.
- Open Science Collaboration. "Estimating the reproducibility of psychological science". *Science* 349(6251), aac4716 (2015). DOI `10.1126/science.aac4716`.

## Condição de revisão

Revisar `CLM-COG-JULG-004` quando meta-análises por paradigma forem consultadas — o status `supported` marca precisamente a lacuna entre saber que o campo é heterogêneo e saber qual efeito específico sobrevive.
