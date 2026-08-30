"""Quando uma chamada pode acontecer. Contabilidade, não estimativa.

Três tetos coexistem e nenhum substitui o outro: o que a API revelou por header, o
que o mantenedor declarou sem verificação, e o orçamento configurado para a execução.
O ledger respeita os três e diz **qual** deles bloqueou — "limite atingido" sem dizer
qual limite obriga quem lê a adivinhar.

Escopo importa. Na Groq os tetos são por endpoint: dois modelos da mesma conta
reportaram 7000 e 1000 requisições por dia. No NIM da NVIDIA o orçamento informado é
agregado por provedor. Contabilizar tudo num escopo só faria um endpoint gastar a
cota do outro, ou o inverso, e nos dois casos o erro só apareceria como 429.

Sem retry: o ledger nega antes da chamada. Ele nunca dorme esperando janela abrir —
a execução seguinte reavalia, e é ela que aproveita a janela.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

MINUTE_S = 60.0
DAY_S = 86_400.0

# Relógio de parede, não monotônico: o ledger atravessa execuções, e `monotonic()`
# não é comparável entre processos. Ajuste de relógio distorce a janela, e é um risco
# aceito — a alternativa seria não ter contabilidade nenhuma entre execuções.

# Além dessa idade nenhum evento influencia janela alguma, e guardá-lo só faria o
# arquivo crescer para sempre.
_MAX_EVENT_AGE_S = DAY_S


@dataclass(frozen=True, slots=True)
class EndpointLimits:
    """Tetos de um alvo. `None` é "não se sabe", nunca "não há"."""

    requests_per_minute: int | None = None
    requests_per_day: int | None = None
    tokens_per_minute: int | None = None
    source: str = "desconhecido"

    @classmethod
    def from_observed(
        cls,
        observed: dict[str, Any],
        declared: dict[str, Any],
    ) -> EndpointLimits:
        """Lê o que o registro guardou para este endpoint.

        `declared_requests_per_minute` (agregado da NVIDIA) fica de fora de
        propósito: aplicá-lo por endpoint daria a cada modelo o orçamento inteiro
        da conta. `requests_per_minute` sem sufixo é teto **deste** endpoint —
        na Groq o header não traz RPM, só a documentação.
        """
        return cls(
            requests_per_minute=_positive(observed.get("requests_per_minute"))
            or _positive(declared.get("requests_per_minute")),
            requests_per_day=_positive(observed.get("requests_per_day"))
            or _positive(declared.get("requests_per_day")),
            tokens_per_minute=_positive(observed.get("tokens_per_minute"))
            or _positive(declared.get("tokens_per_minute")),
            source=str(
                observed.get("source")
                or ("declarado" if declared else "desconhecido")
            ),
        )

    @property
    def known(self) -> bool:
        return any(
            value is not None
            for value in (
                self.requests_per_minute,
                self.requests_per_day,
                self.tokens_per_minute,
            )
        )


def _positive(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value > 0 else None


@dataclass(frozen=True, slots=True)
class Decision:
    allowed: bool
    reason: str

    def __bool__(self) -> bool:
        return self.allowed


@dataclass(slots=True)
class QuotaLedger:
    """Consumo observado por escopo, com janelas deslizantes reais.

    A chave é livre: `groq/qwen3.6-27b` para o teto do endpoint, `groq` para o teto
    agregado do provedor. Quem chama decide o escopo; o ledger só conta.
    """

    events: dict[str, list[tuple[float, int]]] = field(default_factory=dict)
    run_calls: int = 0
    _persisted_events: dict[str, list[tuple[float, int]]] = field(
        default_factory=dict,
        init=False,
        repr=False,
        compare=False,
    )

    def _window(self, key: str, since: float, now: float) -> tuple[int, int]:
        recent = [(at, tokens) for at, tokens in self.events.get(key, []) if at >= now - since]
        return len(recent), sum(tokens for _, tokens in recent)

    def allows(
        self,
        key: str,
        limits: EndpointLimits,
        *,
        estimated_tokens: int = 0,
        now: float | None = None,
    ) -> Decision:
        """Diz se cabe mais uma chamada, e por que não quando não cabe."""
        moment = now if now is not None else time.time()

        if limits.requests_per_minute is not None:
            used, _ = self._window(key, MINUTE_S, moment)
            if used >= limits.requests_per_minute:
                return Decision(False, f"{key}: {used}/{limits.requests_per_minute} req/min")

        if limits.requests_per_day is not None:
            used, _ = self._window(key, DAY_S, moment)
            if used >= limits.requests_per_day:
                return Decision(False, f"{key}: {used}/{limits.requests_per_day} req/dia")

        if limits.tokens_per_minute is not None:
            _, tokens = self._window(key, MINUTE_S, moment)
            if tokens + estimated_tokens > limits.tokens_per_minute:
                return Decision(
                    False,
                    f"{key}: {tokens}+{estimated_tokens}/{limits.tokens_per_minute} tokens/min",
                )

        return Decision(True, f"{key}: dentro dos tetos conhecidos [{limits.source}]")

    def record(self, key: str, *, tokens: int = 0, now: float | None = None) -> None:
        """Anota consumo num escopo. Não conta chamada — ver `record_call`."""
        moment = now if now is not None else time.time()
        self.events.setdefault(key, []).append((moment, max(tokens, 0)))

    def record_call(
        self,
        *,
        endpoint: str,
        provider: str,
        tokens: int = 0,
        now: float | None = None,
    ) -> None:
        """Uma chamada externa: dois escopos contabilizados, um número somado.

        Contar por escopo faria uma chamada valer duas no orçamento da execução, e o
        teto do mantenedor passaria a significar metade do que ele escreveu.
        Chamada que falhou também entra: o provedor cobrou a requisição de qualquer
        forma, e ignorá-la faria a execução seguinte estourar de novo.
        """
        moment = now if now is not None else time.time()
        self.record(endpoint, tokens=tokens, now=moment)
        self.record(provider, tokens=tokens, now=moment)
        self.run_calls += 1

    def prune(self, now: float | None = None) -> None:
        moment = now if now is not None else time.time()
        for key, entries in list(self.events.items()):
            kept = [(at, tokens) for at, tokens in entries if at >= moment - _MAX_EVENT_AGE_S]
            if kept:
                self.events[key] = kept
            else:
                del self.events[key]

    def pending_events(self) -> dict[str, list[tuple[float, int]]]:
        """Eventos acrescentados desde o ultimo checkpoint persistido.

        A diferenca e um multiconjunto, nao um ``set``. Duas chamadas podem receber
        exatamente o mesmo timestamp e a mesma estimativa de tokens; cada ocorrencia
        alem da multiplicidade carregada continua sendo uma chamada separada.
        """
        pending: dict[str, list[tuple[float, int]]] = {}
        for key, entries in self.events.items():
            loaded = Counter(self._persisted_events.get(key, ()))
            additions: list[tuple[float, int]] = []
            for entry in entries:
                if loaded[entry] > 0:
                    loaded[entry] -= 1
                else:
                    additions.append(entry)
            if additions:
                pending[key] = additions
        return pending

    def mark_persisted(
        self,
        events: dict[str, list[tuple[float, int]]] | None = None,
    ) -> None:
        """Atualiza estado e checkpoint depois de uma leitura ou escrita canonica."""
        if events is not None:
            self.events = {key: list(entries) for key, entries in events.items()}
        self._persisted_events = {
            key: list(entries) for key, entries in self.events.items()
        }


@dataclass(frozen=True, slots=True)
class RunBudget:
    """Teto da execução inteira, independente do que os provedores permitem.

    É o limite que o mantenedor controla sem depender de header nenhum, e o único que
    protege contra um catálogo grande demais convidando a gastar muito de uma vez.
    """

    max_calls: int

    def allows(self, ledger: QuotaLedger) -> Decision:
        gasto = f"orçamento da execução: {ledger.run_calls}/{self.max_calls}"
        if ledger.run_calls >= self.max_calls:
            return Decision(False, gasto)
        return Decision(True, gasto)
