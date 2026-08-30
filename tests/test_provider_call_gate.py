"""O gate local limita pressão sem esconder ou perder chamadas."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import cast

import pytest

from providers.base import GenerationResult, ProviderAdapter
from vault.work.call_gate import ProviderCallDisabled, ProviderCallGate
from vault.work.orchestrator import Plan, execute
from vault.work.quotas import QuotaLedger
from vault.work.tasks import Assignment, Task


async def _eventually(predicate: Callable[[], bool]) -> None:
    for _ in range(100):
        if predicate():
            return
        await asyncio.sleep(0)
    pytest.fail("estado concorrente esperado não foi observado")


async def test_gate_aplica_cap_do_provedor_e_endpoint_unico() -> None:
    gate = ProviderCallGate({"groq": 2})
    release = asyncio.Event()
    entered: list[str] = []

    async def hold(endpoint_id: str) -> None:
        async with gate.slot("groq", endpoint_id):
            entered.append(endpoint_id)
            await release.wait()

    first = asyncio.create_task(hold("modelo-a"))
    await _eventually(lambda: entered == ["modelo-a"])
    same_endpoint = asyncio.create_task(hold("modelo-a"))
    other_endpoint = asyncio.create_task(hold("modelo-b"))
    await _eventually(lambda: gate.running("groq") == 2 and gate.pending("groq") == 1)

    assert entered == ["modelo-a", "modelo-b"]
    assert gate.load("groq") == 3
    assert gate.running("groq", "modelo-a") == 1
    assert gate.pending("groq", "modelo-a") == 1
    assert gate.running("groq", "modelo-b") == 1

    release.set()
    await asyncio.gather(first, same_endpoint, other_endpoint)
    assert gate.load("groq") == 0
    assert gate.load("groq", "modelo-a") == 0


async def test_gate_libera_slots_em_erro_e_cancelamento() -> None:
    gate = ProviderCallGate({"groq": 1})

    with pytest.raises(RuntimeError, match="falha simulada"):
        async with gate.slot("groq", "modelo-a"):
            raise RuntimeError("falha simulada")
    assert gate.load("groq") == 0

    entered = asyncio.Event()

    async def wait_forever() -> None:
        async with gate.slot("groq", "modelo-a"):
            entered.set()
            await asyncio.Event().wait()

    active = asyncio.create_task(wait_forever())
    await entered.wait()
    active.cancel()
    with pytest.raises(asyncio.CancelledError):
        await active
    assert gate.load("groq") == 0
    assert gate.load("groq", "modelo-a") == 0


async def test_cancelar_pendente_nao_vaza_contadores_ou_slot_de_endpoint() -> None:
    gate = ProviderCallGate({"groq": 1})
    release = asyncio.Event()
    entered = asyncio.Event()

    async def hold(endpoint_id: str) -> None:
        async with gate.slot("groq", endpoint_id):
            entered.set()
            await release.wait()

    active = asyncio.create_task(hold("modelo-a"))
    await entered.wait()
    pending = asyncio.create_task(hold("modelo-b"))
    await _eventually(lambda: gate.pending("groq") == 1)
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending

    assert gate.running("groq") == 1
    assert gate.pending("groq") == 0
    assert gate.load("groq", "modelo-b") == 0
    release.set()
    await active
    assert gate.load("groq") == 0


def test_suspender_fecha_o_provedor_sem_zerar_a_capacidade() -> None:
    gate = ProviderCallGate({"google": 2})

    assert not gate.disabled("google")
    assert gate.suspend("google")
    assert not gate.suspend("google")
    assert gate.disabled("google")
    assert gate.suspended("google")
    assert gate.capacity("google") == 2
    assert "falha de conta" in (gate.disabled_reason("google") or "")


async def test_cap_zero_falha_imediatamente_sem_criar_espera() -> None:
    gate = ProviderCallGate({"google": 0})

    assert gate.disabled("google")
    with pytest.raises(ProviderCallDisabled, match="concorrência=0"):
        async with gate.slot("google", "gemini"):
            raise AssertionError("slot desabilitado não pode ser adquirido")
    assert gate.load("google") == 0


async def test_execute_nao_chama_provedor_com_cap_zero() -> None:
    gate = ProviderCallGate({"google": 0})
    called = False

    class Adapter:
        provider = "google"

        async def generate(
            self,
            endpoint_id: str,
            prompt: str,
            *,
            max_output_tokens: int = 256,
        ) -> GenerationResult:
            nonlocal called
            called = True
            return GenerationResult("google", endpoint_id, "inesperado")

    task = Task(kind="teste", role_name="proponente", prompt="pergunta")
    plan = Plan(assignments=[Assignment(task, "google", "gemini", "teste")])

    results = await execute(
        plan,
        {"google": cast(ProviderAdapter, Adapter())},
        QuotaLedger(),
        gate=gate,
    )

    assert not called
    assert results[0].outcome == "skipped"
    assert "concorrência=0" in results[0].detail


async def test_execute_compartilha_gate_entre_atribuicoes() -> None:
    gate = ProviderCallGate({"groq": 1})
    release = asyncio.Event()
    started = asyncio.Event()
    active = 0
    maximum = 0

    class Adapter:
        provider = "groq"

        async def generate(
            self,
            endpoint_id: str,
            prompt: str,
            *,
            max_output_tokens: int = 256,
        ) -> GenerationResult:
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            started.set()
            try:
                await release.wait()
                return GenerationResult("groq", endpoint_id, "ok", latency_ms=1)
            finally:
                active -= 1

    task = Task(kind="teste", role_name="proponente", prompt="pergunta")
    plan = Plan(
        assignments=[
            Assignment(task, "groq", "modelo-a", "teste"),
            Assignment(task, "groq", "modelo-b", "teste"),
        ]
    )
    execution = asyncio.create_task(
        execute(
            plan,
            {"groq": cast(ProviderAdapter, Adapter())},
            QuotaLedger(),
            gate=gate,
        )
    )
    await started.wait()
    await _eventually(lambda: gate.pending("groq") == 1)

    assert maximum == 1
    assert gate.running("groq") == 1
    release.set()
    results = await execution
    assert [result.outcome for result in results] == ["ok", "ok"]
    assert maximum == 1
    assert gate.load("groq") == 0


async def test_gate_respeita_rpm_do_mesmo_endpoint() -> None:
    """1-por-endpoint mata a morfologia; o teto documentado é o RPM."""
    gate = ProviderCallGate(
        {"groq": 30},
        endpoint_caps={"groq/openai/gpt-oss-20b": 30},
    )
    release = asyncio.Event()
    entered = 0

    async def hold() -> None:
        nonlocal entered
        async with gate.slot("groq", "openai/gpt-oss-20b"):
            entered += 1
            await release.wait()

    tasks = [asyncio.create_task(hold()) for _ in range(8)]
    await _eventually(lambda: entered == 8)
    assert gate.running("groq", "openai/gpt-oss-20b") == 8
    release.set()
    await asyncio.gather(*tasks)
    assert gate.load("groq") == 0
