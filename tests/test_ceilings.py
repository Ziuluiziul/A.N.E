"""O teto em voo é o RPM documentado; sem número, não inventa."""

from __future__ import annotations

from types import SimpleNamespace

from vault.work.ceilings import MINUTE_PER_DAY, ceilings_from_declared, merge_provider_caps


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
