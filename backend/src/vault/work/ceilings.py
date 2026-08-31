"""Teto em voo e orçamento diário saem do que a fonte declarou — não de um 8/760.

A morfologia (ADR-003) só vive com chamada aberta. Serializar 1-por-endpoint e
capar o processo em centenas de chamadas mata o sinal por desenho. O número
certo é o RPM/RPD que o mantenedor depositou (Google, Groq) ou confirmou
(NVIDIA 40 agregados). Sem número, não entra soma.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

MINUTE_PER_DAY = 1_440

# Só estes têm arquivo ou confirmação do mantenedor neste ataque.
# Ollama Cloud não publicou RPM; Nous/OpenRouter não vieram em ~/Documentos.
AUTHORIZED_PROVIDERS = frozenset({"google", "groq", "nvidia"})


@dataclass(frozen=True, slots=True)
class WorkCeilings:
    """Capacidade máxima que a documentação autoriza neste inventário."""

    provider_caps: dict[str, int]
    endpoint_caps: dict[str, int]
    daily_calls: int

    @property
    def simultaneous(self) -> int:
        return sum(self.provider_caps.values())


def _positive(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value > 0 else None


def ceilings_from_declared(
    models: Iterable[Any],
    *,
    eligible: Iterable[bool] | None = None,
) -> WorkCeilings:
    """Soma RPM por endpoint; agregado da NVIDIA conta uma vez por provedor.

    `eligible` alinha com o recorte de trabalho (texto geral). Modelo inelegível
    (compound, whisper, TTS) não infla o teto do quórum. Provedor fora de
    `AUTHORIZED_PROVIDERS` some zero — sem arquivo, sem teto novo.
    """
    por_provedor: dict[str, int] = {}
    por_endpoint: dict[str, int] = {}
    diario = 0
    agregado_contado: set[str] = set()

    flags = list(eligible) if eligible is not None else None
    for indice, model in enumerate(models):
        if flags is not None and not flags[indice]:
            continue
        if model.provider not in AUTHORIZED_PROVIDERS:
            continue
        declared = model.declared_limits or {}
        chave = f"{model.provider}/{model.endpoint_id}"
        rpm = _positive(declared.get("requests_per_minute"))
        rpd = _positive(declared.get("requests_per_day"))
        agregado = _positive(declared.get("requests_per_minute_aggregate"))

        if rpm is not None:
            por_endpoint[chave] = rpm
            por_provedor[model.provider] = por_provedor.get(model.provider, 0) + rpm
        elif agregado is not None:
            por_endpoint[chave] = agregado
            por_provedor[model.provider] = max(
                por_provedor.get(model.provider, 0), agregado
            )

        if rpd is not None:
            diario += rpd
        elif (
            agregado is not None
            and model.provider not in agregado_contado
            and rpm is None
        ):
            # NVIDIA: 40 RPM confirmados, RPD não veio no arquivo. O dia é a
            # aritmética do RPM, não um teto inventado de outra natureza.
            diario += agregado * MINUTE_PER_DAY
            agregado_contado.add(model.provider)

    return WorkCeilings(
        provider_caps=por_provedor,
        endpoint_caps=por_endpoint,
        daily_calls=diario,
    )


def merge_provider_caps(
    configured: dict[str, int], derived: dict[str, int]
) -> dict[str, int]:
    """Zero configurado é pausa explícita. Qualquer outro cede ao teto documentado."""
    merged = dict(configured)
    for provider, cap in derived.items():
        if configured.get(provider) == 0:
            continue
        merged[provider] = max(configured.get(provider, 0), cap)
    return merged


def effective_max_calls(work_max_calls: int, teto: WorkCeilings | None) -> int:
    """Orçamento da execução: RPM simultâneo do pool, nunca o diário nem ×1440.

    O cartão do Atlas e o worker leem o mesmo número:
    max(work_max_calls, simultaneous). NVIDIA 40 RPM fica 40, não 40×1440.
    Sem RPM declarado, permanece o piso do processo (6 no default).
    """
    piso = max(0, work_max_calls)
    if teto is None:
        return piso
    return max(piso, teto.simultaneous)
