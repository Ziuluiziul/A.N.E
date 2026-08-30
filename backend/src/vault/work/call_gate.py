"""Backpressure compartilhado para chamadas externas no mesmo processo.

O ledger responde se ainda existe cota; este gate responde quantas chamadas podem
estar em voo ao mesmo tempo. As duas proteções são independentes: uma requisição na
fila do gate ainda não consumiu cota, mas precisa aparecer como carga para que novos
trabalhos não escolham repetidamente o mesmo provedor.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager


class ProviderCallDisabled(RuntimeError):
    """O provedor foi explicitamente configurado sem concorrência."""


class ProviderCallGate:
    """Limita concorrência por provedor e, quando informado, por endpoint.

    Uma instância deve ser compartilhada por todos os orquestradores do processo.
    ``provider_caps`` aceita diretamente uma configuração ``provedor -> limite``;
    provedores ausentes usam ``default_provider_cap``. Sem ``endpoint_caps``, o
    padrão continua 1-por-endpoint (testes e ferramentas pontuais). O worker
    passa o RPM declarado para o mesmo modelo poder ter dezenas em voo — a cota
    é que corta, não este semáforo.
    """

    def __init__(
        self,
        provider_caps: Mapping[str, int] | None = None,
        *,
        default_provider_cap: int = 1,
        endpoint_caps: Mapping[str, int] | None = None,
        default_endpoint_cap: int = 1,
    ) -> None:
        self._validate_cap("default_provider_cap", default_provider_cap)
        self._validate_cap("default_endpoint_cap", default_endpoint_cap)
        caps = dict(provider_caps or {})
        for provider, cap in caps.items():
            self._validate_cap(provider, cap)
        por_endpoint = dict(endpoint_caps or {})
        for chave, cap in por_endpoint.items():
            self._validate_cap(chave, cap)

        self._provider_caps = caps
        self._default_provider_cap = default_provider_cap
        self._endpoint_caps = por_endpoint
        self._default_endpoint_cap = default_endpoint_cap
        self._provider_slots: dict[str, asyncio.Semaphore] = {}
        self._endpoint_slots: dict[str, asyncio.Semaphore] = {}
        self._provider_running: Counter[str] = Counter()
        self._provider_pending: Counter[str] = Counter()
        self._endpoint_running: Counter[str] = Counter()
        self._endpoint_pending: Counter[str] = Counter()
        self._suspended: set[str] = set()

    @staticmethod
    def _validate_cap(name: str, cap: int) -> None:
        if isinstance(cap, bool) or not isinstance(cap, int) or cap < 0:
            raise ValueError(f"limite de concorrência inválido para {name}: {cap!r}")

    def capacity(self, provider: str) -> int:
        """Capacidade concorrente configurada para um provedor."""
        return self._provider_caps.get(provider, self._default_provider_cap)

    def disabled(self, provider: str) -> bool:
        """Capacidade zero ou suspensão em processo: o provedor não recebe chamada."""
        return self.capacity(provider) == 0 or provider in self._suspended

    def suspend(self, provider: str) -> bool:
        """Fecha o provedor neste processo sem alterar a capacidade configurada."""
        if provider in self._suspended:
            return False
        self._suspended.add(provider)
        return True

    def suspended(self, provider: str) -> bool:
        return provider in self._suspended

    def disabled_reason(self, provider: str) -> str | None:
        if provider in self._suspended:
            return f"provedor {provider} suspenso por falha de conta"
        if self.capacity(provider) == 0:
            return f"provedor {provider} desabilitado por concorrência=0"
        return None

    def running(self, provider: str, endpoint_id: str | None = None) -> int:
        """Chamadas que já adquiriram todos os slots."""
        if endpoint_id is None:
            return self._provider_running[provider]
        return self._endpoint_running[self._endpoint_key(provider, endpoint_id)]

    def pending(self, provider: str, endpoint_id: str | None = None) -> int:
        """Chamadas aguardando pelo slot de endpoint ou de provedor."""
        if endpoint_id is None:
            return self._provider_pending[provider]
        return self._endpoint_pending[self._endpoint_key(provider, endpoint_id)]

    def load(self, provider: str, endpoint_id: str | None = None) -> int:
        """Carga total observável: em voo mais pendentes."""
        return self.running(provider, endpoint_id) + self.pending(provider, endpoint_id)

    @asynccontextmanager
    async def slot(self, provider: str, endpoint_id: str) -> AsyncIterator[None]:
        """Adquire e sempre libera os dois limites, inclusive sob cancelamento."""
        reason = self.disabled_reason(provider)
        if reason is not None:
            raise ProviderCallDisabled(reason)
        endpoint_key = self._endpoint_key(provider, endpoint_id)
        provider_slot = self._provider_slots.setdefault(
            provider, asyncio.Semaphore(self.capacity(provider))
        )
        endpoint_slot = self._endpoint_slots.setdefault(
            endpoint_key,
            asyncio.Semaphore(self._endpoint_capacity(endpoint_key)),
        )
        endpoint_acquired = False
        provider_acquired = False
        running = False

        self._provider_pending[provider] += 1
        self._endpoint_pending[endpoint_key] += 1
        try:
            # Endpoint primeiro: uma chamada que espera o mesmo modelo não ocupa uma
            # vaga do provedor enquanto outro endpoint poderia usá-la.
            await endpoint_slot.acquire()
            endpoint_acquired = True
            await provider_slot.acquire()
            provider_acquired = True

            self._decrement(self._provider_pending, provider)
            self._decrement(self._endpoint_pending, endpoint_key)
            self._provider_running[provider] += 1
            self._endpoint_running[endpoint_key] += 1
            running = True
            yield
        finally:
            if running:
                self._decrement(self._provider_running, provider)
                self._decrement(self._endpoint_running, endpoint_key)
            else:
                self._decrement(self._provider_pending, provider)
                self._decrement(self._endpoint_pending, endpoint_key)
            if provider_acquired:
                provider_slot.release()
            if endpoint_acquired:
                endpoint_slot.release()

    def _endpoint_capacity(self, endpoint_key: str) -> int:
        return self._endpoint_caps.get(endpoint_key, self._default_endpoint_cap)

    @staticmethod
    def _endpoint_key(provider: str, endpoint_id: str) -> str:
        return f"{provider}/{endpoint_id}"

    @staticmethod
    def _decrement(counter: Counter[str], key: str) -> None:
        if counter[key] <= 1:
            counter.pop(key, None)
        else:
            counter[key] -= 1
