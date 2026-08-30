"""Tetos e IDs da Groq, lidos da documentação oficial — nunca de header inventado.

Consultado em 2026-08-17:

- https://console.groq.com/docs/rate-limits — RPM/RPD/TPM/TPD por modelo
- https://console.groq.com/docs/deprecations — desligamentos (Llama 3.1/3.3 em 16/08)

Os headers `x-ratelimit-limit-requests` / `limit-tokens` são RPD e TPM. RPM **não
vem no header**; sem o valor declarado a cota estoura 30 req/min e o 429 come o RPD.
"""

from __future__ import annotations

import re
from typing import Any

ORIGEM = "documentação oficial Groq (console.groq.com/docs/rate-limits), 2026-08-17"

# Por modelo, na conta (organização). Fonte: tabela da página de rate limits.
# Whisper/Orpheus/Guard ficam de fora do trabalho textual; o teto existe para a
# sonda não inventar outro.
DECLARED_BY_MODEL: dict[str, dict[str, Any]] = {
    "groq/compound": {
        "requests_per_minute": 30,
        "requests_per_day": 250,
        "tokens_per_minute": 70_000,
    },
    "groq/compound-mini": {
        "requests_per_minute": 30,
        "requests_per_day": 250,
        "tokens_per_minute": 70_000,
    },
    "openai/gpt-oss-120b": {
        "requests_per_minute": 30,
        "requests_per_day": 1_000,
        "tokens_per_minute": 8_000,
        "tokens_per_day": 200_000,
    },
    "openai/gpt-oss-20b": {
        "requests_per_minute": 30,
        "requests_per_day": 1_000,
        "tokens_per_minute": 8_000,
        "tokens_per_day": 200_000,
    },
    "openai/gpt-oss-safeguard-20b": {
        "requests_per_minute": 30,
        "requests_per_day": 1_000,
        "tokens_per_minute": 8_000,
        "tokens_per_day": 200_000,
    },
    "qwen/qwen3.6-27b": {
        "requests_per_minute": 30,
        "requests_per_day": 1_000,
        "tokens_per_minute": 8_000,
        "tokens_per_day": 200_000,
    },
    "meta-llama/llama-prompt-guard-2-22m": {
        "requests_per_minute": 30,
        "requests_per_day": 14_400,
        "tokens_per_minute": 15_000,
        "tokens_per_day": 500_000,
    },
    "meta-llama/llama-prompt-guard-2-86m": {
        "requests_per_minute": 30,
        "requests_per_day": 14_400,
        "tokens_per_minute": 15_000,
        "tokens_per_day": 500_000,
    },
    "canopylabs/orpheus-v1-english": {
        "requests_per_minute": 10,
        "requests_per_day": 100,
        "tokens_per_minute": 1_200,
        "tokens_per_day": 3_600,
    },
    "canopylabs/orpheus-arabic-saudi": {
        "requests_per_minute": 10,
        "requests_per_day": 100,
        "tokens_per_minute": 1_200,
        "tokens_per_day": 3_600,
    },
}

# Desligados para free/developer. Enterprise com contrato não é este vault.
# Fonte: console.groq.com/docs/deprecations, 2026-08-17.
SHUT_DOWN: dict[str, str] = {
    "llama-3.1-8b-instant": "2026-08-16 → openai/gpt-oss-20b",
    "llama-3.3-70b-versatile": "2026-08-16 → openai/gpt-oss-120b ou qwen/qwen3.6-27b",
    "qwen/qwen3-32b": "2026-07-17 → openai/gpt-oss-120b",
    "meta-llama/llama-4-scout-17b-16e-instruct": (
        "2026-07-17 → openai/gpt-oss-120b ou qwen/qwen3.6-27b"
    ),
    "moonshotai/kimi-k2-instruct-0905": "2026-04-15 → openai/gpt-oss-120b",
    "moonshotai/kimi-k2-instruct": "2025-10-10 → openai/gpt-oss-120b",
    "meta-llama/llama-4-maverick-17b-128e-instruct": "2026-03-09 → openai/gpt-oss-120b",
    "meta-llama/llama-guard-4-12b": "2026-03-05 → openai/gpt-oss-safeguard-20b",
}

_RESET = re.compile(
    r"^(?:(?P<h>\d+(?:\.\d+)?)h)?(?:(?P<m>\d+(?:\.\d+)?)m)?(?:(?P<s>\d+(?:\.\d+)?)s)?$"
)


def declared_limits(endpoint_id: str) -> dict[str, Any]:
    """Cópia do teto documentado, com origem; vazio quando a página não lista o ID."""
    teto = DECLARED_BY_MODEL.get(endpoint_id)
    if teto is None:
        return {}
    return {**teto, "origem": ORIGEM}


def parse_reset_duration(value: str | None) -> float | None:
    """`7.66s` e `2m59.56s` dos headers `x-ratelimit-reset-*` da Groq."""
    if not value:
        return None
    texto = value.strip().lower()
    achado = _RESET.fullmatch(texto)
    if achado is None or not texto:
        return None
    horas = float(achado.group("h") or 0)
    minutos = float(achado.group("m") or 0)
    segundos = float(achado.group("s") or 0)
    total = horas * 3600 + minutos * 60 + segundos
    return total if total > 0 else None
