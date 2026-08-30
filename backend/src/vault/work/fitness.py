"""Fitness por estágio — o que a seleção prefere, nunca o que ela impõe.

A aptidão é medida por `(estágio, endpoint, papel, domínio)` no ledger de desfechos
(`vault.telemetry`). Dois estágios, duas taxas que não se misturam: um modelo pode
sintetizar bem (propose) e julgar mal (review). Esta unidade só transforma a amostra
em tier — a seleção (o orquestrador) decide o que fazer com o tier.

Tier é julgamento editorial sobre a amostra, não veredito: `C` cobre tanto o não
medido quanto o medido e fraco, e `UNFIT` exige evidência longa de incapacidade
(amostra ≥ `AMOSTRA_PARA_UNFIT` e zero respostas utilizáveis) para que uma sequência
curta ruim não elimine um provedor raro que a diversidade ainda precisa.
"""

from __future__ import annotations

from enum import StrEnum

# Referência editorial: o que separa "aceitável" de "fraco" não é um corte universal —
# é a linha que o mantenedor marcou para B na calibração; A segue como a faixa de
# confiança alta.
TIER_A_MIN = 0.70
TIER_B_MIN = 0.58

# Abaixo disso uma sequência ruim ainda é sequência, não identidade: com menos
# observações o endpoint pode ter sido sondado apenas em condições adversas.
AMOSTRA_PARA_UNFIT = 12


class Tier(StrEnum):
    """Histórico forte, aceitável, desconhecido ou fraco, e condenado por evidência."""

    A = "A"
    B = "B"
    C = "C"
    UNFIT = "UNFIT"


def classificar(taxa: float | None, observacoes: int, utilizaveis: int) -> Tier:
    """Reduz `(taxa, amostra)` a um tier do vocabulário fechado.

    A ordem dos critérios importa: a condenação é sobre a contagem de utilizáveis,
    não sobre a taxa — com amostra curta, zero utilizáveis ainda é `C`.
    """
    if observacoes >= AMOSTRA_PARA_UNFIT and utilizaveis == 0:
        return Tier.UNFIT
    if taxa is None:
        return Tier.C
    if taxa >= TIER_A_MIN:
        return Tier.A
    if taxa >= TIER_B_MIN:
        return Tier.B
    return Tier.C


def ordem(tier: Tier) -> int:
    """Ordem de preferência para ordenação: `A` antes de `B` antes de `C`."""
    return {Tier.A: 0, Tier.B: 1, Tier.C: 2, Tier.UNFIT: 3}[tier]
