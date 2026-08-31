"""Handlers de sinal do worker: POSIX e NT sem AttributeError."""

from __future__ import annotations

import asyncio
import signal
from types import SimpleNamespace

import pytest

import tools.run_worker as run_worker


def test_install_signal_handlers_nao_levanta_no_loop() -> None:
    """Chama o instalador num loop real. No NT os sinais POSIX ausentes são no-op."""

    async def _run() -> None:
        stop = asyncio.Event()
        run_worker._install_signal_handlers(stop)

    asyncio.run(_run())


def test_install_signal_handlers_ignora_sinais_posix_ausentes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simula NT no POSIX: SIGHUP/SIGUSR* inexistentes não derrubam a instalação."""
    fake = SimpleNamespace(
        SIGINT=signal.SIGINT,
        SIGTERM=signal.SIGTERM,
    )
    monkeypatch.setattr(run_worker, "signal", fake)

    async def _run() -> None:
        stop = asyncio.Event()
        run_worker._install_signal_handlers(stop)

    asyncio.run(_run())
