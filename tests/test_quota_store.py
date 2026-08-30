"""O ledger persistente conserva consumo entre processos concorrentes."""

from __future__ import annotations

import json
import multiprocessing
import stat
import time
from pathlib import Path
from typing import Protocol, cast

from vault.runtime_io import write_private_json
from vault.work.quota_store import load_ledger, persist_ledger


class BarrierLike(Protocol):
    def wait(self) -> object: ...


def _record_in_process(state_dir: str, index: int, barrier: object) -> None:
    ledger, path = load_ledger(Path(state_dir))
    cast(BarrierLike, barrier).wait()
    ledger.record_call(
        endpoint=f"fake/modelo-{index}",
        provider="fake",
        tokens=index + 1,
    )
    persist_ledger(ledger, path)


def _events(path: Path) -> dict[str, list[list[float | int]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return cast(dict[str, list[list[float | int]]], payload["events"])


def test_writers_concorrentes_nao_perdem_atualizacoes(tmp_path: Path) -> None:
    workers = 6
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(workers)
    processes = [
        context.Process(target=_record_in_process, args=(str(tmp_path), index, barrier))
        for index in range(workers)
    ]
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=10)
        assert all(process.exitcode == 0 for process in processes)
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)

    events = _events(tmp_path / "quotas.json")
    assert len(events["fake"]) == workers
    assert sum(int(entry[1]) for entry in events["fake"]) == sum(range(1, workers + 1))
    assert all(len(events[f"fake/modelo-{index}"]) == 1 for index in range(workers))


def test_merge_e_multiconjunto_e_repetir_persistencia_e_idempotente(tmp_path: Path) -> None:
    moment = time.time()
    write_private_json(
        tmp_path / "quotas.json",
        {"events": {"fake": [[moment, 512]]}},
    )
    first, first_path = load_ledger(tmp_path)
    second, second_path = load_ledger(tmp_path)

    # Mesmo timestamp e mesmos tokens: cada processo acrescentou uma ocorrencia real.
    first.record("fake", tokens=512, now=moment)
    second.record("fake", tokens=512, now=moment)
    persist_ledger(first, first_path)
    persist_ledger(second, second_path)
    persist_ledger(second, second_path)

    assert _events(first_path)["fake"] == [[moment, 512]] * 3


def test_load_descarta_formas_invalidas_e_store_poda_e_escreve_privado(
    tmp_path: Path,
) -> None:
    now = time.time()
    path = tmp_path / "quotas.json"
    write_private_json(
        path,
        {
            "events": {
                "valido": [[now, 7], [now, -3]],
                "expirado": [[now - 90_000, 1]],
                "invalido": [["ontem", 1], [now], [now, True], None],
            }
        },
    )

    ledger, loaded_path = load_ledger(tmp_path)
    assert loaded_path == path
    assert ledger.events == {"valido": [(now, 7), (now, 0)]}

    ledger.record("novo", tokens=5, now=now)
    persist_ledger(ledger, path)

    assert _events(path) == {
        "novo": [[now, 5]],
        "valido": [[now, 7], [now, 0]],
    }
    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "quotas.json.lock").stat().st_mode) == 0o600
