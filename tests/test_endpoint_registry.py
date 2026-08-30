"""O registro operacional é o que separa palpite de observação entre execuções."""

from __future__ import annotations

from providers.base import ObservedLimits, ProbeResult
from providers.registry import EndpointRegistry


def test_sucesso_e_falha_posterior_preservam_o_ultimo_sucesso() -> None:
    """Saber que já respondeu um dia é diferente de saber que responde agora."""
    registry = EndpointRegistry()
    registry.record_probe(
        ProbeResult(
            "groq",
            "qwen/qwen3.6-27b",
            "ok",
            "ok",
            120,
            observed_at="2026-08-03T10:00:00",
        )
    )
    registry.record_probe(
        ProbeResult(
            "groq",
            "qwen/qwen3.6-27b",
            "unavailable",
            "503",
            90,
            observed_at="2026-08-03T11:00:00",
        )
    )

    record = registry.records["groq/qwen/qwen3.6-27b"]
    assert record.observed_status == "unavailable"
    assert record.last_success == "2026-08-03T10:00:00"
    assert record.probes == 2


def test_estados_ficam_separados_por_provedor() -> None:
    """O mesmo modelo em dois provedores é ambiente distinto, com histórico distinto."""
    registry = EndpointRegistry()
    registry.record_probe(ProbeResult("groq", "openai/gpt-oss-120b", "ok", "ok", 1))
    registry.record_probe(ProbeResult("nvidia", "openai/gpt-oss-120b", "unavailable", "404", 1))

    assert registry.statuses("groq") == {"openai/gpt-oss-120b": "ok"}
    assert registry.statuses("nvidia") == {"openai/gpt-oss-120b": "unavailable"}


def test_registro_sobrevive_a_ida_e_volta_pelo_disco() -> None:
    registry = EndpointRegistry()
    registry.record_probe(ProbeResult("google", "gemini-3.6-flash", "ok", "ok", 42))
    restored = EndpointRegistry.from_dict(registry.to_dict())
    assert restored.to_dict() == registry.to_dict()
    assert restored.status("google", "gemini-3.6-flash") == "ok"


def test_registro_ausente_ou_corrompido_vira_registro_vazio() -> None:
    """Perder o histórico atrasa a convergência; travar a sonda seria pior."""
    assert EndpointRegistry.from_dict(None).records == {}
    assert EndpointRegistry.from_dict({"schema_version": 99, "endpoints": {}}).records == {}
    assert EndpointRegistry.from_dict({"schema_version": 1, "endpoints": "lixo"}).records == {}

    parcial = EndpointRegistry.from_dict(
        {
            "schema_version": 1,
            "endpoints": {
                "google/valido": {
                    "provider": "google",
                    "endpoint_id": "valido",
                    "observed_status": "ok",
                },
                "google/sem-status": {"provider": "google", "endpoint_id": "x"},
            },
        }
    )
    assert list(parcial.records) == ["google/valido"]


def test_limites_ficam_por_endpoint_e_nao_se_sobrescrevem() -> None:
    """Dois modelos da mesma conta Groq reportaram tetos diferentes; ambos importam."""
    registry = EndpointRegistry()
    registry.record_probe(
        ProbeResult("groq", "allam-2-7b", "ok", "ok", 1),
        ObservedLimits(provider="groq", source="headers", requests_per_day=7000),
    )
    registry.record_probe(
        ProbeResult("groq", "qwen/qwen3.6-27b", "ok", "ok", 1),
        ObservedLimits(provider="groq", source="headers", requests_per_day=1000),
    )

    assert registry.records["groq/allam-2-7b"].observed_limits["requests_per_day"] == 7000
    assert registry.records["groq/qwen/qwen3.6-27b"].observed_limits["requests_per_day"] == 1000


def test_sonda_sem_headers_preserva_o_limite_ja_conhecido() -> None:
    """Uma resposta sem header não é notícia de que o limite deixou de existir."""
    registry = EndpointRegistry()
    registry.record_probe(
        ProbeResult("groq", "qwen/qwen3.6-27b", "ok", "ok", 1),
        ObservedLimits(provider="groq", source="headers", tokens_per_minute=8000),
    )
    registry.record_probe(ProbeResult("groq", "qwen/qwen3.6-27b", "ok", "ok", 1))

    guardado = registry.records["groq/qwen/qwen3.6-27b"].observed_limits
    assert guardado["tokens_per_minute"] == 8000


def test_alcancado_sem_texto_nao_vira_ultimo_sucesso() -> None:
    """`reachable` mantém o último sucesso real em vez de fabricar um novo."""
    registry = EndpointRegistry()
    registry.record_probe(
        ProbeResult("google", "gemini-3.6-flash", "reachable", "200 sem texto", 90)
    )
    record = registry.records["google/gemini-3.6-flash"]
    assert record.observed_status == "reachable"
    assert record.last_success is None
