"""Inventário consultável dos endpoints: catálogo, classificação e observação juntos.

Três fontes respondem a perguntas diferentes e ficam em lugares diferentes. O retrato
da descoberta (`providers.catalog`) diz o que a conta alcança. A classificação
(`providers.aptitude`) diz para que serve. O registro (`providers.registry`) diz o que
aconteceu quando alguém chamou. Consultar as três à mão em cada chamador produziria
três versões da mesma junção — esta é a única.

Sobre os campos que a diretriz pede e que **não** estão aqui: `reasoning_level` e
`tool_support` não são declarados por nenhum dos três provedores, e `input_types` só
seria adivinhação a partir do nome. Preenchê-los com palpite faria o inventário
parecer mais informado do que é — a mesma falha que a seleção alfabética cometia.
`assigned_roles` pertence ao orquestrador, que atribui papel a partir daqui; guardar a
coluna vazia agora seria placeholder.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from providers.aptitude import Aptitude, classify, preference_key
from providers.base import ModelInfo
from providers.catalog import DiscoverySnapshot
from providers.registry import EndpointRecord, EndpointRegistry


@dataclass(frozen=True, slots=True)
class EndpointProfile:
    """Tudo que se sabe sobre um endpoint, com a origem de cada parte preservada."""

    aptitude: Aptitude
    model: ModelInfo
    record: EndpointRecord | None = None

    # --- identidade --------------------------------------------------------

    @property
    def provider(self) -> str:
        return self.aptitude.provider

    @property
    def endpoint_id(self) -> str:
        return self.aptitude.endpoint_id

    @property
    def key(self) -> str:
        return self.aptitude.key

    @property
    def family(self) -> str:
        return self.aptitude.family

    # --- o que foi observado -----------------------------------------------

    @property
    def observed_status(self) -> str | None:
        """`None` é "nunca sondado", que não é o mesmo que "falhou"."""
        return self.record.observed_status if self.record else None

    @property
    def observed_latency_ms(self) -> int | None:
        return self.record.latency_ms if self.record else None

    @property
    def last_success(self) -> str | None:
        return self.record.last_success if self.record else None

    @property
    def probes(self) -> int:
        return self.record.probes if self.record else 0

    @property
    def observed_limits(self) -> dict[str, Any]:
        """Limites desta chave `(provider, endpoint)`, não do provedor inteiro."""
        return self.record.observed_limits if self.record else {}

    @property
    def usable_for_work(self) -> bool:
        """Apto pelo nome **e** comprovado por sonda que produziu texto."""
        return self.aptitude.eligible and self.observed_status == "ok"

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "endpoint_id": self.endpoint_id,
            "family": self.family,
            "capabilities": list(self.model.capabilities),
            "context_window": self.model.context_window,
            "max_output_tokens": self.model.max_output_tokens,
            "output_modality": self.aptitude.modality,
            "purpose": self.aptitude.purpose,
            "stability": self.aptitude.stability,
            "version": list(self.aptitude.version),
            "eligible": self.aptitude.eligible,
            "reason": self.aptitude.reason,
            "declared_limits": dict(self.model.declared_limits),
            "observed_limits": self.observed_limits,
            "observed_status": self.observed_status,
            "observed_latency_ms": self.observed_latency_ms,
            "last_success": self.last_success,
            "probes": self.probes,
            "usable_for_work": self.usable_for_work,
        }


@dataclass(frozen=True, slots=True)
class Inventory:
    profiles: list[EndpointProfile] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.profiles)

    def select(
        self,
        *,
        provider: str | None = None,
        purpose: str | None = None,
        family: str | None = None,
        status: str | None = None,
        eligible: bool | None = None,
        usable: bool | None = None,
    ) -> list[EndpointProfile]:
        """Consulta por atributo, já na ordem de preferência.

        Filtro ausente não filtra. `status=None` não significa "sem status": para
        pedir os nunca sondados existe `status="not_probed"`, porque a diferença
        entre "não perguntei" e "perguntei e falhou" é justamente o que importa.
        """
        found = self.profiles
        if provider is not None:
            found = [profile for profile in found if profile.provider == provider]
        if purpose is not None:
            found = [profile for profile in found if profile.aptitude.purpose == purpose]
        if family is not None:
            found = [profile for profile in found if profile.family == family]
        if status is not None:
            wanted = None if status == "not_probed" else status
            found = [profile for profile in found if profile.observed_status == wanted]
        if eligible is not None:
            found = [profile for profile in found if profile.aptitude.eligible is eligible]
        if usable is not None:
            found = [profile for profile in found if profile.usable_for_work is usable]
        return sorted(found, key=lambda profile: preference_key(profile.aptitude))

    def providers(self) -> list[str]:
        return sorted({profile.provider for profile in self.profiles})

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": len(self.profiles),
            "endpoints": [profile.to_dict() for profile in self.select()],
        }


def build_inventory(
    snapshots: dict[str, DiscoverySnapshot],
    registry: EndpointRegistry | None = None,
) -> Inventory:
    """Junta os retratos à classificação e ao que a sonda observou."""
    known = registry or EndpointRegistry()
    profiles: list[EndpointProfile] = []
    for provider, snapshot in snapshots.items():
        for model in snapshot.models:
            profiles.append(
                EndpointProfile(
                    aptitude=classify(model),
                    model=model,
                    record=known.records.get(EndpointRegistry.key(provider, model.endpoint_id)),
                )
            )
    return Inventory(profiles=profiles)
