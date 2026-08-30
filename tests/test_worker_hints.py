"""As pistas que ligam o ledger à seleção (M4) sem rede nem runtime real."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import tools.run_worker as run_worker
from vault.telemetry.records import Stage
from vault.telemetry.surfaces import (
    Aptidao,
    Capacidade,
    CustoDeFechamento,
    Superficies,
)
from vault.work.fitness import AMOSTRA_PARA_UNFIT

AGORA = datetime(2026, 8, 16, 0, 0, tzinfo=UTC).timestamp()


def test_segundos_desde_interpreta_iso_com_fuso() -> None:
    assert 0.0 <= run_worker._segundos_desde("2026-08-15T23:59:00+00:00", AGORA) < 120
    assert run_worker._segundos_desde("não é data", AGORA) == float("inf")


def test_condenacao_exige_falha_recente_e_aptidao_entra_com_amostra(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Condenar é veredito com prazo: sem falha recente, o endpoint volta a tentar."""
    monkeypatch.setattr(run_worker.time, "time", lambda: AGORA)
    monkeypatch.setattr(
        run_worker,
        "build_records",
        lambda _runtime_dir: [],
    )
    monkeypatch.setattr(
        run_worker,
        "build_surfaces",
        lambda _records: Superficies(
            capacidade=[
                Capacidade(
                    chave="a/velho",
                    tentativas=20,
                    ok=0,
                    por_classe={"tempo-esgotado": 20},
                    ultima_falha="2026-07-01T00:00:00+00:00",
                ),
                Capacidade(
                    chave="b/fresco",
                    tentativas=20,
                    ok=0,
                    por_classe={"tempo-esgotado": 20},
                    ultima_falha="2026-08-15T23:59:00+00:00",
                ),
                Capacidade(
                    chave="c/com-sucesso",
                    tentativas=20,
                    ok=1,
                    por_classe={"ok": 1, "tempo-esgotado": 19},
                    ultima_falha="2026-08-15T23:59:00+00:00",
                ),
            ],
            aptidao=[
                Aptidao(
                    stage=Stage.VOTE,
                    endpoint="d/bom",
                    role="verificador-factual",
                    domain="Física",
                    observacoes=9,
                    utilizaveis=9,
                ),
                # Abaixo da amostra mínima: não vira pista, mas também não veta.
                Aptidao(
                    stage=Stage.VOTE,
                    endpoint="e/ruidoso",
                    role="verificador-factual",
                    domain="Física",
                    observacoes=2,
                    utilizaveis=0,
                ),
                Aptidao(
                    stage=Stage.PROPOSAL,
                    endpoint="f/mudo",
                    role="proponente",
                    domain="Física",
                    observacoes=AMOSTRA_PARA_UNFIT,
                    utilizaveis=0,
                ),
            ],
            custo=CustoDeFechamento(10, 100, 10.0),
            pivotalidade={},
        ),
    )

    pistas = run_worker._pistas_de_capacidade(tmp_path)()

    assert "a/velho" not in pistas.unfit
    assert "b/fresco" in pistas.unfit
    assert "c/com-sucesso" not in pistas.unfit
    assert pistas.aptitude[("vote", "d/bom", "verificador-factual", "Física")] == 1.0
    assert ("vote", "e/ruidoso", "verificador-factual", "Física") not in pistas.aptitude
    assert "f/mudo" in pistas.unfit_por_estagio["proposal"]
    assert "d/bom" not in pistas.unfit_por_estagio.get("vote", frozenset())
    assert "e/ruidoso" not in pistas.unfit_por_estagio.get("vote", frozenset())
