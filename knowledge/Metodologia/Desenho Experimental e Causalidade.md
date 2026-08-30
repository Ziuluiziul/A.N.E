---
title: Desenho Experimental e Causalidade
domain: metodologia
kind: nota
status: active
epistemic_status: established
updated: 2026-07-18
verified_at: 2026-07-18
---

# Desenho experimental e causalidade

## Finalidade

Responder: **quando uma diferença observada autoriza uma conclusão causal?** Todo claim de intervenção no Vault — de física experimental a avaliação de IA — passa por esta pergunta.

## Escopo

Confundimento; intervenção vs condicionamento (`do(x)` vs `ver x`); randomização e o que ela garante; potential outcomes e efeito médio de tratamento; critérios gráficos de identificação (backdoor) em nível de enunciado; viéses estruturais (seleção, colisor). **Escopo negativo:** inferência estatística dos estimadores (nota de Inferência), métodos avançados (IV, RDD, DiD) e descoberta causal automática.

## Pré-requisitos

- [[Probabilidade]] <!-- relation:prerequisite -->
- [[Inferência e Incerteza]] <!-- relation:prerequisite -->

## Conceitos nucleares

- **Confundidor**: causa comum de tratamento e desfecho; gera associação sem causação.
- **Intervenção**: `P(Y | do(X=x))` difere de `P(Y | X=x)` — a distinção formal central de Pearl.
- **Randomização**: quebra as setas que entram no tratamento; identifica o efeito **médio** sob hipóteses próprias (aleatorização válida, não interferência entre unidades, consistência do tratamento).
- **Colisor**: condicionar num efeito comum **cria** associação espúria — controlar "tudo" é erro estrutural.
- **Identificação ≠ estimação**: primeiro decide-se se o efeito é identificável do desenho; só então se estima.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-MET-CAUSAL-001` | Associação observacional não identifica efeito causal sem hipóteses de identificação explícitas (ausência de confundimento não medido, ou critério gráfico satisfeito). | established | Formalismo de Pearl (backdoor); potential outcomes (Rubin); "associação não basta" é o enunciado do gate interdisciplinar do dossiê. |
| `CLM-MET-CAUSAL-002` | Randomização bem executada identifica o efeito médio do tratamento, sob não-interferência e consistência; não identifica efeitos individuais nem mecanismos. | established | Resultado padrão de potential outcomes; heterogeneidade de efeito é o limite declarado. |
| `CLM-MET-CAUSAL-003` | Estratégias de identificação sob confundimento não medido compram identificação com moedas diferentes e falham de modos diferentes: métodos proximais e de controles negativos exigem **proxies observados** do confundidor; fatoração estrutural (estilo two-way fixed effects) exige **separabilidade aditiva** do confundidor em componentes de unidade e tempo. | established | Miao & Tchetgen Tchetgen (proximal); literatura de dados em painel (fixed effects). Caso conferido na fonte: Yu, Fang, Peng, Qi, Zhou & Shi, “Two-way Deconfounder for Off-policy Evaluation in Causal Reinforcement Learning”, arXiv:2412.05783 — identifica por separabilidade aditiva, e o termo `proxy` **não** integra o conjunto de hipóteses. Verificado no PDF em 27/07/2026. |

## Limites e contraexemplos

- **Paradoxo de Simpson**: a direção da associação inverte por estrato — sem modelo causal, nenhuma agregação é "a correta".
- **Viés de colisor**: amostrar por hospitalização induz correlações entre doenças independentes na população.
- Randomização não protege contra atrito diferencial pós-aleatorização nem contra medição enviesada do desfecho.
- Efeito médio positivo é compatível com dano em subgrupos.
- **Confundir as duas estratégias de identificação leva a auditoria inválida.** Testar
  degradação sob colinearidade proxy–confundidor não estressa um estimador que não usa
  proxy. O teste análogo para fatoração estrutural é confundimento com interação
  genuína unidade×tempo — variação que a separabilidade aditiva proíbe e que o sistema
  real não tem obrigação de respeitar.
- Nenhuma das duas torna a hipótese testável a partir do dado observacional. O que se
  pode obter é a **curva de degradação**: quão rápido o estimador se deteriora conforme
  a realidade se afasta da forma assumida. "Consistente sob H" com curva de degradação
  conhecida é objeto operacionalmente muito melhor que "consistente sob H" sozinho.

## Relações

- [[Inferência e Incerteza]] <!-- relation:prerequisite -->
- [[Reprodutibilidade e Replicação]] <!-- relation:extends --> — replicar é reexecutar o desenho, não o cálculo.
- [[Avaliação e Proveniência de Sistemas de IA]] <!-- relation:operational --> — comparações de modelos são quase-experimentos com confundidores próprios.
- [[Fronteiras da Física — Monitor de Evidências]] <!-- relation:operational --> — o monitor classifica evidência experimental usando estes critérios.

## Fontes

- Judea Pearl. *Causality: Models, Reasoning, and Inference*. 2ª ed., Cambridge University Press, 2009.
- Yu, Fang, Peng, Qi, Zhou & Shi. “Two-way Deconfounder for Off-policy Evaluation in Causal Reinforcement Learning”. [arXiv:2412.05783](https://arxiv.org/abs/2412.05783)
- Guido W. Imbens e Donald B. Rubin. *Causal Inference for Statistics, Social, and Biomedical Sciences*. Cambridge University Press, 2015.

## Condição de revisão

Estável no núcleo; revisar se métodos quase-experimentais ganharem nota própria.
