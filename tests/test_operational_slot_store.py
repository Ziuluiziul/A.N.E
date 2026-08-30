"""Ordinais operacionais: estado próprio, atômico e estável sob concorrência."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from vault.layout_store import (
    OPERATIONAL_SLOTS_SCHEMA_VERSION,
    LayoutStoreError,
    OperationalSlotStore,
    slots_from_payload,
)

VERSION = 4


@pytest.fixture
def store(tmp_path: Path) -> OperationalSlotStore:
    return OperationalSlotStore(tmp_path / "operational-slots")


def test_merge_grava_e_preserva_ordinais_aceitos(store: OperationalSlotStore) -> None:
    first = store.merge(VERSION, {"painel-a": 0})
    second = store.merge(VERSION, {"painel-a": 9, "painel-b": 0})

    assert first.slots == {"painel-a": 0}
    assert second.slots == {"painel-a": 0, "painel-b": 1}
    assert second.schema_version == OPERATIONAL_SLOTS_SCHEMA_VERSION
    assert second.algorithm_version == VERSION
    assert store.load(VERSION) == second


def test_painel_ausente_na_requisicao_nao_perde_seu_lugar(
    store: OperationalSlotStore,
) -> None:
    store.merge(VERSION, {"painel-a": 0})

    merged = store.merge(VERSION, {"painel-b": 0})

    assert merged.slots == {"painel-a": 0, "painel-b": 1}


def test_duas_instancias_concorrentes_nao_duplicam_ordinal(tmp_path: Path) -> None:
    directory = tmp_path / "operational-slots"
    barrier = threading.Barrier(2)

    def write(panel_id: str) -> None:
        barrier.wait()
        OperationalSlotStore(directory).merge(VERSION, {panel_id: 0})

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(write, panel_id) for panel_id in ("painel-a", "painel-b")]
        for future in futures:
            future.result(timeout=5)

    snapshot = OperationalSlotStore(directory).load(VERSION)
    assert snapshot is not None
    assert set(snapshot.slots) == {"painel-a", "painel-b"}
    assert set(snapshot.slots.values()) == {0, 1}


@pytest.mark.parametrize("invalid", [-1, 1.5, True, "1"])
def test_ordinal_invalido_e_recusado(store: OperationalSlotStore, invalid: object) -> None:
    with pytest.raises(LayoutStoreError, match="ordinal inválido"):
        store.merge(VERSION, {"painel": invalid})  # type: ignore[dict-item]


def test_save_recusa_ordinal_duplicado(store: OperationalSlotStore) -> None:
    with pytest.raises(LayoutStoreError, match="mesmo ordinal"):
        store.save(VERSION, {"painel-a": 0, "painel-b": 0})


def test_corrupcao_vira_ausencia(store: OperationalSlotStore) -> None:
    store.directory.mkdir(parents=True)
    (store.directory / f"v{VERSION}.json").write_text(
        json.dumps(
            {
                "schemaVersion": OPERATIONAL_SLOTS_SCHEMA_VERSION,
                "algorithmVersion": VERSION,
                "slots": {"painel-a": 0, "painel-b": 0},
            }
        ),
        encoding="utf-8",
    )

    assert store.load(VERSION) is None


def test_versao_nao_pode_criar_path_arbitrario(store: OperationalSlotStore) -> None:
    with pytest.raises(LayoutStoreError, match="versão"):
        store.merge(10_001, {"painel": 0})
    assert store.load(10_001) is None


def test_payload_tem_tipo_proprio() -> None:
    assert slots_from_payload({"painel": 3}) == {"painel": 3}
    with pytest.raises(LayoutStoreError):
        slots_from_payload({"painel": {"x": 3, "y": 0, "z": 0}})
