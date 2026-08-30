---
title: Termodinâmica Fora do Equilíbrio
aliases: [Prigogine — Estruturas Dissipativas, Prigogine: Estruturas Dissipativas]
domain: física
kind: nota
status: active
epistemic_status: established
updated: 2026-07-16
verified_at: 2026-07-16
---

# Termodinâmica fora do equilíbrio

## Balanço de entropia

Para um sistema aberto, a variação de entropia pode ser decomposta como

`dS/dt = Π - Φ`,

onde `Π≥0` é a produção interna de entropia e `Φ` representa o fluxo líquido de entropia para fora, conforme a convenção de sinais. Uma estrutura pode manter organização local enquanto produz entropia e troca energia/matéria com o ambiente; isso não viola a segunda lei.

Dizer apenas que o sistema “exporta entropia” omite produção interna, condições de contorno e balanços de energia.

## Regime linear próximo do equilíbrio

Perto do equilíbrio, fluxos `J_i` podem ser aproximados por relações de Onsager

`J_i = Σ_j L_{ij}X_j`,

em termos de forças termodinâmicas `X_j`. Sob hipóteses restritas, coeficientes satisfazem reciprocidade e o estado estacionário pode obedecer ao princípio de mínima produção de entropia de Prigogine.

O princípio não vale genericamente longe do equilíbrio.

## Estruturas dissipativas

Longe do equilíbrio, instabilidades e bifurcações podem gerar padrões macroscópicos sustentados por fluxo, como convecção de Bénard e reações oscilatórias. “Ordem a partir de flutuações” é um resumo histórico, não uma lei quantitativa universal; o mecanismo deve ser dado pelas equações e parâmetros do sistema.

## Não-equivalências

- O princípio de energia livre de Friston pertence a outro formalismo e não é resultado de Prigogine.
- Termos como “metabolismo”, “agente” ou “caos” não transferem automaticamente a termodinâmica para serviços de software ou alinhamento de IA.
- Sistemas dissipativos em biologia e redes podem ser analisados termodinamicamente apenas quando variáveis, fluxos e balanços físicos são definidos.

## Estado epistêmico

| ID | Afirmação | Status | Escopo/evidência |
|---|---|---|---|
| `CLM-FIS-NEQ-001` | A segunda lei e a produção de entropia organizam a descrição macroscópica irreversível. | `established` | Termodinâmica no regime e coarse graining declarados. |
| `CLM-FIS-NEQ-002` | As relações de Onsager valem no regime linear próximo do equilíbrio. | `established` | Requer forças pequenas e hipóteses de reversibilidade microscópica. |
| `CLM-FIS-NEQ-003` | O princípio de mínima produção de entropia é universal. | `refuted` | Vale apenas sob hipóteses restritas próximas do equilíbrio. |
| `CLM-FIS-NEQ-004` | Estruturas dissipativas emergem em sistemas específicos longe do equilíbrio. | `supported` | Suporte teórico e experimental nos sistemas correspondentes. |
| `CLM-FIS-NEQ-005` | Conceitos termodinâmicos justificam automaticamente arquiteturas de agentes ou serviços. | `out-of-scope` | A extrapolação não é uma relação física demonstrada. |

## Relações

- [[MOC — Física Teórica]] <!-- relation:navigation -->
- [[Referências Verificadas de Física]] <!-- relation:evidence -->

## Referências

- Ilya Prigogine, “Time, Structure and Fluctuations”, Nobel Lecture, 8 de dezembro de 1977. Fonte institucional: https://www.nobelprize.org/prizes/chemistry/1977/prigogine/lecture/
- Lars Onsager, “Reciprocal Relations in Irreversible Processes. I”, *Physical Review* 37, 405–426 (1931), DOI `10.1103/PhysRev.37.405`.
