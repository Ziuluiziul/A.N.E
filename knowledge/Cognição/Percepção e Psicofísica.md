---
title: Percepção e Psicofísica
aliases: [Psicofísica, Percepção, Detecção de Sinal]
domain: cognição
kind: nota
status: active
epistemic_status: established
updated: 2026-07-28
verified_at: 2026-07-28
---

# Percepção e psicofísica

## Finalidade

Responder: **como se mede experiência subjetiva com rigor?** A psicofísica é a resposta histórica e ainda a melhor: relacionar grandeza física do estímulo a resposta comportamental por procedimento replicável. É o ponto do Vault em que medição, inferência e cognição se encontram sem metáfora.

## Escopo

Limiares absoluto e diferencial; lei de Weber e as leis de Fechner e Stevens; métodos de medida de limiar (limites, ajuste, escada adaptativa); teoria de detecção de sinal (`d′` e critério); percepção como inferência sob incerteza; constâncias perceptuais; organização perceptual; adaptação; ilusões como evidência de mecanismo; integração multissensorial. **Escopo negativo:** anatomia dos sistemas sensoriais em detalhe (nota de bases neurais), consciência perceptual como problema filosófico, e estética.

## Pré-requisitos

- [[Bases Neurais da Cognição]] <!-- relation:prerequisite --> — o comportamento medido é implementado pelos circuitos descritos lá.
- [[Metrologia e Validação]] <!-- relation:prerequisite --> — psicofísica é metrologia aplicada a um instrumento peculiar: o observador.
- [[Probabilidade]] <!-- relation:prerequisite --> — detecção de sinal é um problema de decisão estatística.

## Conceitos nucleares

- **Limiar diferencial e lei de Weber**: a menor diferença detectável é aproximadamente proporcional à intensidade de referência, `ΔI/I ≈ k`. Vale numa faixa intermediária, não nos extremos.
- **Fechner × Stevens**: Fechner derivou relação logarítmica a partir de Weber; Stevens propôs função de potência com expoente dependente da modalidade, a partir de estimação direta de magnitude. São modelos distintos com procedimentos distintos.
- **Teoria de detecção de sinal**: separa **sensibilidade** (`d′`) de **critério de resposta** (viés). É a contribuição metodológica central: taxa de acerto isolada confunde as duas coisas.
- **Percepção como inferência**: o estímulo proximal é ambíguo; o sistema resolve a ambiguidade usando regularidades. Ilusões são o preço estrutural dessa estratégia, não defeitos.
- **Constância**: cor, tamanho e forma percebidos permanecem estáveis sob variação do estímulo proximal — evidência direta de processamento inferencial.
- **Adaptação**: a resposta se ajusta ao contexto recente; o sistema codifica mudança e contraste com mais fidelidade que valor absoluto.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-COG-PSICO-001` | A menor diferença detectável é aproximadamente proporcional à intensidade de referência (lei de Weber), dentro de uma faixa intermediária de intensidades. | established | Wolfe et al., cap. 1. **Limite explícito:** a proporcionalidade falha perto do limiar absoluto e perto da saturação. Enunciar Weber sem a faixa de validade é erro de escopo. |
| `CLM-COG-PSICO-002` | A teoria de detecção de sinal separa sensibilidade de critério de resposta, e medidas que não fazem essa separação confundem os dois efeitos. | established | Wolfe et al., cap. 1. **Alcance além da percepção:** a mesma estrutura formal descreve qualquer tarefa de classificação binária, incluindo avaliação de sistemas de IA — onde `d′`, precisão e recall respondem à mesma distinção entre discriminabilidade e ponto de corte. |
| `CLM-COG-PSICO-003` | Ilusões perceptuais são consequência sistemática de estratégias inferenciais normalmente adaptativas, não falhas aleatórias do sistema. | established | Wolfe et al., caps. 5–6 e 8. Persistem com conhecimento explícito da ilusão — o que mostra que o processamento é encapsulado e não corrigível por crença. |
| `CLM-COG-PSICO-004` | Fechner e Stevens propõem funções psicofísicas distintas — logarítmica e de potência — obtidas por procedimentos distintos, e a escolha do procedimento afeta a forma estimada. | established | Wolfe et al., cap. 1. **Nuance metodológica:** a discordância não é apenas empírica; depende de o que se pede ao observador. É um caso em que o instrumento de medida participa do resultado, e por isso interessa a [[Metrologia e Validação]] <!-- relation:extends -->. |

## Limites e contraexemplos

- **Relato verbal não é leitura direta da experiência**: é comportamento, sujeito a demanda experimental, critério e expectativa. Todo o aparato de detecção de sinal existe por causa disso.
- **Diferenças individuais são grandes**: funções psicofísicas médias podem não descrever nenhum observador individual — o mesmo problema de agregação que aparece em qualquer média populacional.
- **Ilusão não prova o mecanismo proposto**: demonstra que *algum* processamento não trivial ocorre; a explicação específica exige teste independente.
- **Generalização entre modalidades falha**: expoentes de Stevens variam por modalidade; conclusões sobre visão não transferem para audição ou tato.

## Relações

- [[Bases Neurais da Cognição]] <!-- relation:prerequisite -->
- [[Metrologia e Validação]] <!-- relation:extends --> — o observador como instrumento, com calibração e limite de resolução.
- [[Probabilidade]] <!-- relation:prerequisite -->
- [[Estimação e Testes de Hipótese]] <!-- relation:extends --> — `d′` e critério são estimados por inferência.
- [[Avaliação e Proveniência de Sistemas de IA]] <!-- relation:extends --> — a distinção sensibilidade/critério aplica-se à avaliação de classificadores.
- [[Raciocínio, Julgamento e Decisão]] <!-- relation:extends -->
- [[MOC — Cognição]] <!-- relation:navigation -->

## Fontes

- Jeremy M. Wolfe, Keith R. Kluender, Dennis M. Levi, Linda M. Bartoshuk, Rachel S. Herz, Roberta L. Klatzky e Daniel M. Merfeld. *Sensation and Perception*. 6ª ed., Sinauer Associates / Oxford University Press, 2020. ISBN 978-1-60535-972-4.

## Condição de revisão

Estável. Revisar se o Vault ganhar nota de atenção ou de percepção bayesiana, que absorveria o tratamento formal de percepção como inferência.
