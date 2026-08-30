"""Registro operacional dos endpoints: o que foi observado, nunca o que se supõe.

`providers.aptitude` lê nomes e metadados e produz palpite. Aqui só entra resultado de
chamada real, com a data em que ela aconteceu. Quando os dois discordam, este arquivo
vence: um endpoint bem classificado que devolveu 404 continua sendo um endpoint que
devolveu 404.

O registro é acumulativo entre execuções. É ele que permite dirigir a próxima sonda
sem repetir o que já se sabe, mantendo o limite de uma chamada por provedor por
execução: uma falha condiciona a execução seguinte em vez de virar retry escondido.

Estrutura pura, sem I/O — o pacote instalado não depende de `tools/`. Quem persiste é
a fronteira de CLI, com `write_private_json`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from providers.base import ObservedLimits, ProbeResult

REGISTRY_NAME = "endpoints.json"
SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class EndpointRecord:
    """A última observação sobre um endpoint, e desde quando ele nunca mais respondeu.

    `observed_limits` mora aqui, e não no adaptador, porque limite é por endpoint. Na
    Groq, `allam-2-7b` reportou 7000 RPD / 6000 TPM e `qwen3.6-27b` reportou 1000 RPD
    / 8000 TPM na mesma conta: guardar um número por provedor faria o segundo apagar
    o primeiro e o orquestrador planejar cota com o teto do endpoint errado.
    """

    provider: str
    endpoint_id: str
    # ok | reachable | auth | rate_limited | account_exhausted | unavailable | error
    observed_status: str
    detail: str = ""
    latency_ms: int | None = None
    observed_at: str = ""
    last_success: str | None = None
    probes: int = 0
    observed_limits: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "endpoint_id": self.endpoint_id,
            "observed_status": self.observed_status,
            "detail": self.detail,
            "latency_ms": self.latency_ms,
            "observed_at": self.observed_at,
            "last_success": self.last_success,
            "probes": self.probes,
            "observed_limits": self.observed_limits,
        }


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


@dataclass(slots=True)
class EndpointRegistry:
    records: dict[str, EndpointRecord] = field(default_factory=dict)

    @staticmethod
    def key(provider: str, endpoint_id: str) -> str:
        return f"{provider}/{endpoint_id}"

    def status(self, provider: str, endpoint_id: str) -> str | None:
        record = self.records.get(self.key(provider, endpoint_id))
        return record.observed_status if record else None

    def statuses(self, provider: str) -> dict[str, str]:
        """Estados observados de um provedor, indexados pelo endpoint."""
        return {
            record.endpoint_id: record.observed_status
            for record in self.records.values()
            if record.provider == provider
        }

    def record_probe(
        self,
        probe: ProbeResult,
        limits: ObservedLimits | None = None,
    ) -> EndpointRecord:
        """Grava a sonda já redigida.

        `last_success` só avança quando o endpoint produziu texto: `reachable` mantém
        o último sucesso de verdade, e não inventa um.

        Limite ausente preserva o que já se sabia. A resposta desta execução pode não
        ter trazido headers, e isso não apaga a leitura de uma execução anterior.
        """
        key = self.key(probe.provider, probe.endpoint_id)
        previous = self.records.get(key)
        if limits is not None:
            observed_limits = asdict(limits)
        else:
            observed_limits = previous.observed_limits if previous else {}
        updated = EndpointRecord(
            provider=probe.provider,
            endpoint_id=probe.endpoint_id,
            observed_status=probe.outcome,
            detail=probe.detail,
            latency_ms=probe.latency_ms,
            observed_at=probe.observed_at,
            last_success=(
                probe.observed_at
                if probe.ok
                else (previous.last_success if previous else None)
            ),
            probes=(previous.probes if previous else 0) + 1,
            observed_limits=observed_limits,
        )
        self.records[key] = updated
        return updated

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "endpoints": {
                key: record.to_dict() for key, record in sorted(self.records.items())
            },
        }

    @classmethod
    def from_dict(cls, raw: object) -> EndpointRegistry:
        """Aceita ausência e descarta schema desconhecido, sem derrubar o comando.

        Um registro ilegível vira registro vazio: perder o histórico atrasa a
        convergência, mas travar a sonda por causa dele seria pior.
        """
        if not isinstance(raw, dict) or raw.get("schema_version") != SCHEMA_VERSION:
            return cls()
        entries = raw.get("endpoints")
        if not isinstance(entries, dict):
            return cls()
        records: dict[str, EndpointRecord] = {}
        for key, value in entries.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                continue
            provider = _text(value.get("provider"))
            endpoint_id = _text(value.get("endpoint_id"))
            status = _text(value.get("observed_status"))
            if not provider or not endpoint_id or not status:
                continue
            last_success = value.get("last_success")
            limits = value.get("observed_limits")
            records[cls.key(provider, endpoint_id)] = EndpointRecord(
                provider=provider,
                endpoint_id=endpoint_id,
                observed_status=status,
                detail=_text(value.get("detail")),
                latency_ms=_optional_int(value.get("latency_ms")),
                observed_at=_text(value.get("observed_at")),
                last_success=last_success if isinstance(last_success, str) else None,
                probes=_optional_int(value.get("probes")) or 0,
                observed_limits=limits if isinstance(limits, dict) else {},
            )
        return cls(records=records)
