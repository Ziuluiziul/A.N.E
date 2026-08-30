"""O fitness reduz amostra a tier; não escolhe endpoint — isso é do orquestrador."""

from __future__ import annotations

from vault.work.fitness import (
    AMOSTRA_PARA_UNFIT,
    TIER_A_MIN,
    TIER_B_MIN,
    Tier,
    classificar,
    ordem,
)


def test_sem_taxa_e_amostra_curta_ficam_em_c() -> None:
    assert classificar(None, 0, 0) is Tier.C
    assert classificar(None, AMOSTRA_PARA_UNFIT - 1, 0) is Tier.C
    assert classificar(0.0, AMOSTRA_PARA_UNFIT - 1, 0) is Tier.C


def test_cortes_de_a_e_b_respeitam_a_calibracao() -> None:
    assert classificar(TIER_A_MIN, 20, 14) is Tier.A
    assert classificar(TIER_A_MIN - 0.01, 20, 13) is Tier.B
    assert classificar(TIER_B_MIN, 20, 12) is Tier.B
    assert classificar(TIER_B_MIN - 0.01, 20, 11) is Tier.C


def test_unfit_exige_amostra_longa_e_zero_utilizaveis() -> None:
    assert classificar(0.0, AMOSTRA_PARA_UNFIT, 0) is Tier.UNFIT
    assert classificar(0.0, AMOSTRA_PARA_UNFIT, 1) is Tier.C


def test_ordem_poe_unfit_depois_de_c() -> None:
    assert ordem(Tier.A) < ordem(Tier.B) < ordem(Tier.C) < ordem(Tier.UNFIT)
