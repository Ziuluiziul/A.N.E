---
title: MOC — Cognição
domain: cognição
kind: moc
status: active
epistemic_status: mixed
updated: 2026-07-30
verified_at: 2026-07-28
---

# Cognição

**Objeto central:** percepção, memória, julgamento e decisão tratados como fenômenos **mensuráveis** — com o instrumento, a norma de comparação e o estado replicativo declarados em cada caso.

## Árvore de pré-requisitos

### Implementação

1. [[Bases Neurais da Cognição]] <!-- relation:navigation --> — o que se sabe da implementação física, e a distância entre mecanismo celular e explicação cognitiva.

### Medida

2. [[Percepção e Psicofísica]] <!-- relation:navigation --> — como medir experiência subjetiva com rigor; sensibilidade contra critério.

### Norma e desvio

3. [[Raciocínio, Julgamento e Decisão]] <!-- relation:navigation --> — heurísticas, vieses e a norma probabilística da qual são desvio.

### Persistência

4. [[Memória]] <!-- relation:navigation --> — codificação, consolidação, reconsolidação e esquecimento; onde a evidência de engrama chega e onde para.

## O que este domínio exige de disciplina

Cognição é onde o Vault corre quatro riscos específicos, e cada nota carrega a contramedida:

| Risco | Onde é tratado |
|---|---|
| **Inferência reversa** — concluir processo mental a partir de ativação cerebral | `CLM-COG-NEURO-003`: fMRI é sinal indireto; necessidade exige intervenção causal |
| **Estado replicativo ignorado** — citar clássico sem checar se replica | `CLM-COG-JULG-003` e `-004`: números da OSC 2015 verificados na fonte |
| **Engrama reificado** — confundir suficiência experimental com identidade da memória | `CLM-COG-MEM-007` e `-008`: evocar comportamento não identifica a memória com o conjunto manipulado |
| **Homonímia com IA** — "neurônio", "aprendizado", "viés", "atenção" | Todas as arestas para IA são `contrasts`, nunca `extends` |

A homonímia com IA merece registro explícito, porque é a ponte mais tentadora e a mais frágil do Vault inteiro. Neurônio artificial e neurônio biológico compartilham nome e quase nada mais; "viés" em julgamento humano é desvio de norma probabilística, enquanto em sistema de IA é regularidade estatística de dados de treino. Sem fonte primária tratando explicitamente dos dois domínios, a política proíbe a aresta — e aqui ela é proibida.

## Como se liga ao resto do Vault

| Ponte | Tipo | Justificativa |
|---|---|---|
| Bases neurais ↔ [[Bioenergética e Termodinâmica dos Sistemas Vivos]] <!-- relation:prerequisite --> | **legítima** | O potencial de repouso é estado estacionário mantido por bombas que consomem ATP. |
| Psicofísica ↔ [[Metrologia e Validação]] <!-- relation:prerequisite --> | **legítima** | Psicofísica é metrologia com o observador como instrumento. |
| Julgamento ↔ [[Inferência Bayesiana]] <!-- relation:extends --> | **legítima** | Negligência da taxa-base é literalmente a omissão do prior. |
| Julgamento ↔ [[Reprodutibilidade e Replicação]] <!-- relation:evidence --> | **legítima** | O campo é simultaneamente objeto e caso de estudo do problema. |
| Cognição ↔ [[Fundamentos de Aprendizado de Máquina e Modelos de Linguagem]] <!-- relation:contrasts --> | **contraste** | Homonímia sem fonte que trate ambos. |

## Escopo negativo (critérios de exclusão)

- Consciência como problema explicativo — filosófico, sem protocolo de medida acordado.
- Psicometria de inteligência e diferenças de grupo.
- Psicologia clínica e diagnóstico.
- Neuromitos (estilos de aprendizagem, dominância hemisférica, uso de 10% do cérebro) — não entram nem para refutar, salvo com fonte primária.
- Afirmações de cognição quântica sem replicação independente.

## Lacunas priorizadas (não criar sem função)

Atenção e controle executivo; linguagem e processamento sintático; desenvolvimento
cognitivo; tomada de decisão sequencial e aprendizado por reforço em humanos. Cada
uma entra quando uma nota consumidora a exigir — vale a regra de crescimento do
[[Índice]] <!-- relation:navigation -->.

> **Memória saiu desta lista em 2026-07-30.** [[Memória]] <!-- relation:navigation -->
> liga a plasticidade de `CLM-COG-NEURO-002` aos resultados comportamentais sem
> identificar traço e substrato: `CLM-COG-MEM-008` mantém essa correspondência como
> questão `open`. Os dois claims devem ser reavaliados em conjunto, mas cada status
> continua respondendo à formulação e à evidência da própria linha.
>
> Memória de trabalho e controle executivo **continuam** lacuna: a nota nova as
> exclui explicitamente no escopo negativo.

## Teste de navegação (casos reais)

- "Essa área do cérebro é responsável por X?" → Bases Neurais → `CLM-COG-NEURO-003` → inferência reversa é inválida.
- "Por que as pessoas ignoram taxa-base?" → Julgamento → `CLM-COG-JULG-002` → é o prior de Bayes omitido.
- "Esse experimento clássico de psicologia vale?" → Julgamento → `CLM-COG-JULG-003/004` → cheque o estado replicativo antes de citar.
- "Onde uma memória está?" → [[Memória]] <!-- relation:navigation --> → `CLM-COG-MEM-007/008` → evocar comportamento não demonstra identidade entre memória e conjunto celular.
- "Modelos de linguagem têm vieses cognitivos?" → Julgamento → Limites → homônimo, origem distinta, aresta de contraste.

## Fonte curricular

Bibliografia declarada por nota. Kandel et al. (neurociência), Wolfe et al.
(percepção), Tversky & Kahneman 1974 e Open Science Collaboration 2015 tiveram
identificadores verificados em 28/07/2026. [[Memória]] <!-- relation:navigation -->
declara por fonte a profundidade verificada em 30/07/2026.

Voltar ao [[Índice]] <!-- relation:navigation -->.
