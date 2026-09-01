"""O inventário junta três fontes; o risco é uma delas se passar pela outra."""

from __future__ import annotations

from pathlib import Path

from providers.base import ModelInfo, ObservedLimits, ProbeResult
from providers.catalog import DiscoverySnapshot
from providers.inventory import build_inventory
from providers.registry import EndpointRegistry


def snapshot(provider: str, *endpoint_ids: str) -> DiscoverySnapshot:
    return DiscoverySnapshot(
        path=Path(f"models-{provider}-2026.json"),
        models=[
            ModelInfo(
                provider=provider,
                endpoint_id=endpoint_id,
                family="teste",
                available=True,
                context_window=131072,
            )
            for endpoint_id in endpoint_ids
        ],
    )


def test_nunca_sondado_e_falhou_nao_se_confundem() -> None:
    """`None` é ausência de pergunta; `unavailable` é resposta. Tratar igual seria erro."""
    registry = EndpointRegistry()
    registry.record_probe(ProbeResult("nvidia", "z-ai/glm-5.2", "unavailable", "404", 1))

    inventory = build_inventory(
        {"nvidia": snapshot("nvidia", "z-ai/glm-5.2", "meta/llama-3.3-70b-instruct")},
        registry,
    )
    por_id = {profile.endpoint_id: profile for profile in inventory.profiles}

    assert por_id["z-ai/glm-5.2"].observed_status == "unavailable"
    assert por_id["meta/llama-3.3-70b-instruct"].observed_status is None
    assert inventory.select(status="not_probed") == [por_id["meta/llama-3.3-70b-instruct"]]
    assert inventory.select(status="unavailable") == [por_id["z-ai/glm-5.2"]]


def test_apelido_latest_nao_recebe_trabalho() -> None:
    """No Google, `-latest` come o RPM do SKU estável; o painel AI Studio agrega os dois."""
    registry = EndpointRegistry()
    registry.record_probe(ProbeResult("google", "gemini-3.5-flash-lite", "ok", "ok", 1))
    registry.record_probe(ProbeResult("google", "gemini-flash-lite-latest", "ok", "ok", 1))

    inventory = build_inventory(
        {
            "google": snapshot(
                "google", "gemini-3.5-flash-lite", "gemini-flash-lite-latest"
            )
        },
        registry,
    )
    usaveis = [profile.endpoint_id for profile in inventory.select(usable=True)]
    assert usaveis == ["gemini-3.5-flash-lite"]
    assert "gemini-flash-lite-latest" not in {
        p.endpoint_id for p in inventory.for_work()
    }


def test_preview_google_cede_ao_estavel_do_mesmo_sku() -> None:
    """`3.1-flash-lite` e `3.1-flash-lite-preview` são um teto só no Studio."""
    registry = EndpointRegistry()
    for endpoint in (
        "gemini-3.1-flash-lite",
        "gemini-3.1-flash-lite-preview",
        "gemini-3-flash-preview",
        "gemini-3.1-pro-preview",
        "gemini-3.1-pro-preview-customtools",
    ):
        registry.record_probe(ProbeResult("google", endpoint, "ok", "ok", 1))

    inventory = build_inventory(
        {
            "google": snapshot(
                "google",
                "gemini-3.1-flash-lite",
                "gemini-3.1-flash-lite-preview",
                "gemini-3-flash-preview",
                "gemini-3.1-pro-preview",
                "gemini-3.1-pro-preview-customtools",
            )
        },
        registry,
    )
    trabalho = [profile.endpoint_id for profile in inventory.for_work()]
    assert "gemini-3.1-flash-lite" in trabalho
    assert "gemini-3.1-flash-lite-preview" not in trabalho
    assert "gemini-3-flash-preview" in trabalho
    assert "gemini-3.1-pro-preview" in trabalho
    assert "gemini-3.1-pro-preview-customtools" not in trabalho


def test_trabalho_exige_aptidao_e_sonda_produtiva() -> None:
    """Nem só classificar basta, nem só responder: `usable_for_work` pede os dois."""
    registry = EndpointRegistry()
    registry.record_probe(ProbeResult("groq", "qwen/qwen3.6-27b", "ok", "ok", 1))
    registry.record_probe(ProbeResult("groq", "gemini-fake", "reachable", "sem texto", 1))
    registry.record_probe(ProbeResult("groq", "whisper-large-v3", "ok", "texto", 1))

    inventory = build_inventory(
        {"groq": snapshot("groq", "qwen/qwen3.6-27b", "gemini-fake", "whisper-large-v3")},
        registry,
    )
    usaveis = [profile.endpoint_id for profile in inventory.select(usable=True)]

    # whisper respondeu ok e mesmo assim não serve: transcrição não é tarefa textual.
    assert usaveis == ["qwen/qwen3.6-27b"]


def test_limites_seguem_o_endpoint_e_nao_o_provedor() -> None:
    registry = EndpointRegistry()
    registry.record_probe(
        ProbeResult("groq", "allam-2-7b", "ok", "ok", 1),
        ObservedLimits(provider="groq", source="headers", requests_per_day=7000),
    )
    registry.record_probe(
        ProbeResult("groq", "qwen/qwen3.6-27b", "ok", "ok", 1),
        ObservedLimits(provider="groq", source="headers", requests_per_day=1000),
    )

    inventory = build_inventory(
        {"groq": snapshot("groq", "allam-2-7b", "qwen/qwen3.6-27b")},
        registry,
    )
    limites = {
        profile.endpoint_id: profile.observed_limits["requests_per_day"]
        for profile in inventory.profiles
    }
    assert limites == {"allam-2-7b": 7000, "qwen/qwen3.6-27b": 1000}


def test_inventario_sem_registro_nao_inventa_observacao() -> None:
    inventory = build_inventory({"groq": snapshot("groq", "qwen/qwen3.6-27b")})
    profile = inventory.profiles[0]
    assert profile.observed_status is None
    assert profile.probes == 0
    assert profile.observed_limits == {}
    assert not profile.usable_for_work


def test_consulta_combina_filtros_e_mantem_a_ordem_de_preferencia() -> None:
    inventory = build_inventory(
        {
            "groq": snapshot("groq", "llama-3.1-8b-instant", "qwen/qwen3.6-27b"),
            "nvidia": snapshot("nvidia", "bigcode/starcoder2-15b", "z-ai/glm-5.2"),
        }
    )
    assert inventory.providers() == ["groq", "nvidia"]

    gerais = [profile.endpoint_id for profile in inventory.select(purpose="general")]
    assert gerais == ["z-ai/glm-5.2", "qwen/qwen3.6-27b", "llama-3.1-8b-instant"]

    codigo = [profile.endpoint_id for profile in inventory.select(purpose="code")]
    assert codigo == ["bigcode/starcoder2-15b"]

    assert [p.endpoint_id for p in inventory.select(provider="nvidia", purpose="general")] == [
        "z-ai/glm-5.2"
    ]
