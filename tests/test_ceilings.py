"""O teto em voo é o RPM documentado; sem número, não inventa."""

from __future__ import annotations

from types import SimpleNamespace

from providers.aptitude import classify
from providers.base import ModelInfo
from providers.inventory import EndpointProfile, Inventory
from tools.run_worker import plan_worker_limits
from vault.work.ceilings import (
    MINUTE_PER_DAY,
    ceilings_from_declared,
    effective_max_calls,
    merge_provider_caps,
)


def test_soma_rpm_por_endpoint_e_agregado_uma_vez() -> None:
    modelos = [
        SimpleNamespace(
            provider="groq",
            endpoint_id="openai/gpt-oss-20b",
            declared_limits={
                "requests_per_minute": 30,
                "requests_per_day": 1_000,
            },
        ),
        SimpleNamespace(
            provider="groq",
            endpoint_id="qwen/qwen3.6-27b",
            declared_limits={
                "requests_per_minute": 30,
                "requests_per_day": 1_000,
            },
        ),
        SimpleNamespace(
            provider="groq",
            endpoint_id="groq/compound",
            declared_limits={
                "requests_per_minute": 30,
                "requests_per_day": 250,
            },
        ),
        SimpleNamespace(
            provider="nvidia",
            endpoint_id="deepseek-ai/deepseek-v4-flash-0731",
            declared_limits={"requests_per_minute_aggregate": 40},
        ),
        SimpleNamespace(
            provider="nvidia",
            endpoint_id="outro",
            declared_limits={"requests_per_minute_aggregate": 40},
        ),
        SimpleNamespace(
            provider="nous",
            endpoint_id="stepfun/step-3.7-flash:free",
            declared_limits={"requests_per_minute": 50, "requests_per_day": 1_000},
        ),
    ]
    teto = ceilings_from_declared(
        modelos, eligible=(True, True, False, True, True, True)
    )
    assert teto.provider_caps == {"groq": 60, "nvidia": 40}
    assert teto.endpoint_caps["groq/openai/gpt-oss-20b"] == 30
    assert teto.endpoint_caps["nvidia/outro"] == 40
    assert "groq/groq/compound" not in teto.endpoint_caps
    assert "nous/stepfun/step-3.7-flash:free" not in teto.endpoint_caps
    assert teto.daily_calls == 2_000 + 40 * MINUTE_PER_DAY
    assert teto.simultaneous == 100


def test_merge_respeita_pausa_explicita() -> None:
    merged = merge_provider_caps({"google": 0, "groq": 6}, {"google": 140, "groq": 90})
    assert merged["google"] == 0
    assert merged["groq"] == 90


def test_orcamento_efetivo_sobe_com_o_rpm_simultaneo() -> None:
    modelos = [
        SimpleNamespace(
            provider="groq",
            endpoint_id="llama-3.1-8b",
            declared_limits={"requests_per_minute": 30, "requests_per_day": 1_000},
        )
    ]
    teto = ceilings_from_declared(modelos)
    assert teto.daily_calls == 1_000
    assert teto.simultaneous == 30
    assert effective_max_calls(6, teto) == 30
    assert effective_max_calls(6, teto) != 6
    assert effective_max_calls(6, teto) != 1_000


def test_sem_rpd_usa_rpm_simultaneo_nunca_vezes_o_dia() -> None:
    modelos = [
        SimpleNamespace(
            provider="groq",
            endpoint_id="llama-3.1-8b",
            declared_limits={"requests_per_minute": 30},
        )
    ]
    teto = ceilings_from_declared(modelos)
    assert teto.daily_calls == 0
    assert teto.provider_caps == {"groq": 30}
    assert teto.simultaneous == 30
    assert effective_max_calls(6, teto) == 30
    assert effective_max_calls(6, teto) != 30 * MINUTE_PER_DAY


def test_sem_teto_documentado_permanece_o_sandbox() -> None:
    teto = ceilings_from_declared([])
    assert effective_max_calls(6, teto) == 6
    assert effective_max_calls(6, None) == 6


def _inventario_groq(*, rpm: int, rpd: int | None) -> Inventory:
    limits: dict[str, int] = {"requests_per_minute": rpm}
    if rpd is not None:
        limits["requests_per_day"] = rpd
    model = ModelInfo(
        provider="groq",
        endpoint_id="llama-3.1-8b",
        family="llama",
        declared_limits=limits,
        available=True,
    )
    aptitude = classify(model)
    assert aptitude.eligible
    return Inventory(profiles=[EndpointProfile(aptitude=aptitude, model=model)])


def test_worker_max_calls_usa_rpm_do_pool() -> None:
    inventory = _inventario_groq(rpm=30, rpd=1_000)
    max_calls, concurrency, caps, _endpoints = plan_worker_limits(
        work_max_calls=6,
        worker_concurrency=3,
        configured_caps={},
        inventory=inventory,
    )
    assert max_calls == 30
    assert max_calls != 6
    assert max_calls != 1_000
    assert caps == {"groq": 30}
    # RPM simultâneo 30; 30//4 = 7 recorta a concorrência pelo orçamento por quórum.
    assert concurrency == 7
    max_override, conc_override, _, _ = plan_worker_limits(
        work_max_calls=6,
        worker_concurrency=3,
        configured_caps={},
        inventory=inventory,
        max_calls_override=6,
    )
    assert max_override == 6
    assert conc_override == 1


def _inventario_nvidia() -> Inventory:
    model = ModelInfo(
        provider="nvidia",
        endpoint_id="deepseek-ai/deepseek-v4-flash-0731",
        family="deepseek",
        declared_limits={"requests_per_minute_aggregate": 40},
        available=True,
    )
    aptitude = classify(model)
    assert aptitude.eligible
    return Inventory(profiles=[EndpointProfile(aptitude=aptitude, model=model)])


def test_worker_max_calls_nao_usa_nvidia_diaria() -> None:
    teto = ceilings_from_declared(
        profile.model for profile in _inventario_nvidia().profiles
    )
    assert teto.simultaneous == 40
    assert teto.daily_calls == 40 * MINUTE_PER_DAY
    assert effective_max_calls(6, teto) == 40
    assert effective_max_calls(6, teto) != 40 * MINUTE_PER_DAY
    max_calls, _concurrency, caps, _ = plan_worker_limits(
        work_max_calls=6,
        worker_concurrency=3,
        configured_caps={},
        inventory=_inventario_nvidia(),
    )
    assert max_calls == 40
    assert max_calls != 57_600
    assert caps == {"nvidia": 40}


def test_sem_rpm_o_piso_e_o_sandbox() -> None:
    teto = ceilings_from_declared([])
    assert teto.simultaneous == 0
    assert effective_max_calls(6, teto) == 6
    assert effective_max_calls(10, teto) == 10
    assert effective_max_calls(0, teto) == 0
    assert effective_max_calls(0, None) == 0

