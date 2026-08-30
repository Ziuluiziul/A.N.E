"""Persistencia concorrente do ledger de quotas.

O arquivo JSON e substituido atomicamente, mas isso sozinho nao evita *lost update*:
dois processos podem carregar o mesmo retrato, acrescentar chamadas distintas e o
ultimo substituir a escrita do primeiro. O lock vive em arquivo separado porque
``os.replace`` troca o inode do JSON; travar o proprio JSON deixaria processos antigos
e novos protegendo inodes diferentes.

Cada ledger carregado guarda um checkpoint privado. Na persistencia, somente o delta
multiconjunto em relacao a esse checkpoint e mesclado ao retrato atual do disco sob o
lock. Assim eventos ja carregados nao sao duplicados e ocorrencias numericamente
identicas acrescentadas por processos distintos continuam sendo contadas.
"""

from __future__ import annotations

import fcntl
import math
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from vault.runtime_io import read_private_json, redact_json, write_private_json
from vault.work.quotas import QuotaLedger

LEDGER_NAME = "quotas.json"


def _lock_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.lock")


@contextmanager
def _process_lock(path: Path, *, exclusive: bool) -> Iterator[None]:
    """Trava o inode estavel do ``.lock`` e mantem artefatos em modo privado."""
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(path.parent, 0o700)
    flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW
    descriptor = os.open(_lock_path(path), flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        fcntl.flock(descriptor, operation)
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _decode(raw: Any) -> QuotaLedger:
    ledger = QuotaLedger()
    if not isinstance(raw, dict) or not isinstance(raw.get("events"), dict):
        return ledger
    for key, entries in raw["events"].items():
        if not isinstance(key, str) or not isinstance(entries, list):
            continue
        valid: list[tuple[float, int]] = []
        for entry in entries:
            if not isinstance(entry, list | tuple) or len(entry) != 2:
                continue
            at, tokens = entry
            if (
                isinstance(at, bool)
                or not isinstance(at, int | float)
                or not math.isfinite(float(at))
                or isinstance(tokens, bool)
                or not isinstance(tokens, int)
            ):
                continue
            valid.append((float(at), max(tokens, 0)))
        if valid:
            ledger.events[key] = valid
    return ledger


def _payload(ledger: QuotaLedger) -> dict[str, dict[str, list[tuple[float, int]]]]:
    return {"events": {key: list(entries) for key, entries in ledger.events.items()}}


def load_ledger(state_dir: Path) -> tuple[QuotaLedger, Path]:
    """Carrega o consumo valido e registra o retrato como checkpoint do processo."""
    path = state_dir / LEDGER_NAME
    with _process_lock(path, exclusive=False):
        ledger = _decode(read_private_json(path))
    ledger.prune()
    ledger.mark_persisted()
    return ledger, path


def persist_ledger(
    ledger: QuotaLedger,
    path: Path,
    redact: Callable[[str], str] | object = None,
) -> None:
    """Mescla apenas chamadas novas, poda e grava JSON privado/atomico sob lock."""
    sanitize = redact if callable(redact) else (lambda text: text)
    moment = time.time()
    ledger.prune(moment)
    additions = ledger.pending_events()

    with _process_lock(path, exclusive=True):
        merged = _decode(read_private_json(path))
        merged.prune(moment)
        for key, entries in additions.items():
            merged.events.setdefault(key, []).extend(entries)
        merged.prune(moment)

        sanitized = redact_json(_payload(merged), sanitize)
        canonical = _decode(sanitized)
        canonical.prune(moment)
        write_private_json(path, _payload(canonical))

    # O budget de execucao e local ao processo; so as janelas persistentes sao
    # substituidas pelo retrato mesclado que acabou de ir ao disco.
    ledger.mark_persisted(canonical.events)
