"""Cotas do free tier Google, lidas do painel da conta — não de header.

Fonte: `/home/ziul/Documentos/google.md` (captura do console, 2026-08-17).
A API Gemini não devolve `x-ratelimit-*`; sem este mapa a cota trata o
provedor como sem teto por modelo e o 429 (20 RPD no Flash) chega primeiro.

Os números são o lado direito de `usado / limite`. IDs de imagem, live, TTS
pro e embedding ficam de fora: a tabela ou não os cobre ou não servem ao
quórum.
"""

from __future__ import annotations

from typing import Any

ORIGEM = "painel Google AI Studio (Documentos/google.md), 2026-08-17"

# endpoint_id → (RPM, TPM, RPD)
_TETO: dict[str, tuple[int, int, int]] = {
    "antigravity-preview-05-2026": (60, 100_000, 100),
    "gemini-2.5-flash": (5, 250_000, 20),
    "gemini-2.5-flash-lite": (10, 250_000, 20),
    "gemini-2.5-flash-preview-tts": (3, 10_000, 10),
    "gemini-3-flash-preview": (5, 250_000, 20),
    "gemini-3.1-flash-lite": (15, 250_000, 500),
    "gemini-3.1-flash-lite-preview": (15, 250_000, 500),
    "gemini-3.1-flash-tts-preview": (3, 10_000, 10),
    "gemini-3.5-flash": (5, 250_000, 20),
    "gemini-3.5-flash-lite": (15, 250_000, 500),
    "gemini-3.6-flash": (5, 250_000, 20),
    "gemini-3.7-flash": (5, 250_000, 20),
    "gemma-4-26b-a4b-it": (30, 16_000, 14_400),
    "gemma-4-31b-it": (30, 16_000, 14_400),
}


def declared_limits(endpoint_id: str) -> dict[str, Any]:
    """Teto documentado deste ID, ou vazio se a captura não o cobre."""
    chave = endpoint_id.removeprefix("models/")
    teto = _TETO.get(chave)
    if teto is None:
        return {}
    rpm, tpm, rpd = teto
    return {
        "requests_per_minute": rpm,
        "tokens_per_minute": tpm,
        "requests_per_day": rpd,
        "origem": ORIGEM,
    }
