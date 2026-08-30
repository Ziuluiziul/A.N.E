"""Adaptadores de provedor. Um endpoint é uma identidade própria.

O mesmo modelo servido por dois provedores é tratado como dois ambientes: limites,
latência e comportamento diferem, e o histórico de qualidade de um não vale para o
outro. Nenhum papel permanente é atribuído a modelo nesta fase.
"""

from providers.base import (
    GenerationResult,
    ModelInfo,
    ObservedLimits,
    ProbeResult,
    ProviderAccountExhausted,
    ProviderAdapter,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimited,
    ProviderUnavailable,
    limits_from_headers,
    verify_via_list_models,
)

__all__ = [
    "GenerationResult",
    "ModelInfo",
    "ObservedLimits",
    "ProbeResult",
    "ProviderAdapter",
    "ProviderAccountExhausted",
    "ProviderAuthError",
    "ProviderError",
    "ProviderRateLimited",
    "ProviderUnavailable",
    "build_adapters",
    "limits_from_headers",
    "verify_via_list_models",
]


def _plain_secret(value: object) -> str:
    """Converte `SecretStr` só no limite em que o SDK exige texto puro."""
    getter = getattr(value, "get_secret_value", None)
    return str(getter() if callable(getter) else value)


def build_adapters(settings: object | None = None) -> dict[str, ProviderAdapter]:
    """Adaptadores para os quais existe credencial. Importa sob demanda.

    Os SDKs são importados aqui, e não no topo do módulo, para que a ausência de um
    deles não derrube o inventário dos demais.
    """
    from vault.config import get_settings

    cfg = settings if settings is not None else get_settings()
    adapters: dict[str, ProviderAdapter] = {}

    gemini_key = getattr(cfg, "gemini_api_key", None)
    if gemini_key:
        from providers.google.adapter import GoogleAdapter

        adapters["google"] = GoogleAdapter(_plain_secret(gemini_key))

    groq_key = getattr(cfg, "groq_api_key", None)
    if groq_key:
        from providers.groq.adapter import GroqAdapter

        adapters["groq"] = GroqAdapter(_plain_secret(groq_key))

    nvidia_key = getattr(cfg, "nvidia_api_key", None)
    if nvidia_key:
        from providers.nvidia.adapter import NvidiaAdapter

        adapters["nvidia"] = NvidiaAdapter(_plain_secret(nvidia_key))

    ollama_key = getattr(cfg, "ollama_api_key", None)
    if ollama_key:
        from providers.ollama.adapter import OllamaAdapter

        adapters["ollama"] = OllamaAdapter(_plain_secret(ollama_key))

    nous_key = getattr(cfg, "nous_api_key", None)
    if nous_key:
        from providers.nous.adapter import NousAdapter

        adapters["nous"] = NousAdapter(_plain_secret(nous_key))

    openrouter_key = getattr(cfg, "openrouter_api_key", None)
    if openrouter_key:
        from providers.openrouter.adapter import OpenRouterAdapter

        adapters["openrouter"] = OpenRouterAdapter(
            _plain_secret(openrouter_key),
            allow_uncapped_free_tier=bool(
                getattr(cfg, "openrouter_allow_uncapped_free_tier", False)
            ),
        )

    return adapters
