---
title: Metrologia e Validação
domain: metodologia
kind: nota
status: active
epistemic_status: established
updated: 2026-07-18
verified_at: 2026-07-18
---

# Metrologia e validação

## Finalidade

Responder: **o que um número medido significa, e como se declara o quanto ele pode estar errado?** Sem incerteza declarada, um resultado não é comparável, não é acumulável e não passa no gate de evidência do Vault.

## Escopo

Mensurando, resultado e incerteza; erro sistemático vs aleatório; incerteza padrão, combinada e expandida (enunciado GUM); rastreabilidade a padrões; calibração de instrumentos; verificação vs validação (V&V) em computação científica. **Escopo negativo:** metrologia legal, engenharia de instrumentação específica e métodos numéricos (futuro domínio).

## Pré-requisitos

- [[Probabilidade]] <!-- relation:prerequisite --> — incerteza é tratada probabilisticamente.
- [[Inferência e Incerteza]] <!-- relation:prerequisite -->

## Conceitos nucleares

- **Mensurando**: a grandeza que se *pretende* medir — defini-lo mal é o primeiro erro.
- **Erro sistemático** desloca; **aleatório** espalha; repetição só reduz o segundo.
- **Incerteza (GUM)**: parâmetro associado ao resultado que caracteriza a dispersão dos valores atribuíveis ao mensurando; combinada por propagação, expandida por fator de cobertura declarado.
- **Rastreabilidade**: cadeia ininterrupta de comparações a um padrão, cada elo com incerteza própria.
- **Verificação** ("resolvo as equações certo?") ≠ **validação** ("as equações certas para o fenômeno?"): atividades distintas com evidências distintas.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-MET-METRO-001` | Um resultado de medição sem incerteza declarada não é comparável entre laboratórios nem utilizável para decidir concordância com previsão teórica. | established | GUM (JCGM 100); prática padrão de intercomparações; a comparação exige intervalo, não ponto. |
| `CLM-FIS-SIM-001` | Concordância interna, estabilidade e convergência numérica não bastam para validar empiricamente um modelo físico; validação exige confronto com medição independente do fenômeno. | established | Distinção V&V padrão em computação científica; problemas puramente matemáticos são o contraexemplo de escopo. |

## Limites e contraexemplos

- Precisão alta com acurácia baixa: instrumento estável e descalibrado — repetição não conserta viés.
- Dígitos de saída de software não são algarismos significativos do mensurando.
- Código verificado (convergente, estável) pode implementar fielmente um modelo falso do fenômeno — verificação nunca substitui validação.
- Incerteza expandida sem fator de cobertura declarado é número sem semântica.

## Relações

- [[Inferência e Incerteza]] <!-- relation:prerequisite -->
- [[Desenho Experimental e Causalidade]] <!-- relation:extends --> — medição enviesada corrompe qualquer desenho.
- [[Fronteiras da Física — Monitor de Evidências]] <!-- relation:operational --> — o monitor pesa evidência experimental por estes critérios.
- [[Reprodutibilidade e Replicação]] <!-- relation:extends -->

## Fontes

- JCGM. *Evaluation of measurement data — Guide to the Expression of Uncertainty in Measurement* (GUM, JCGM 100:2008) e *International Vocabulary of Metrology* (VIM, JCGM 200:2012). Comitê Conjunto de Guias em Metrologia (BIPM).
- William L. Oberkampf e Christopher J. Roy. *Verification and Validation in Scientific Computing*. Cambridge University Press, 2010.

## Condição de revisão

Revisar se o Vault ganhar nota de Física Computacional (herdaria V&V aplicada) ou se o JCGM publicar revisão do GUM.
