"""A interface que todo provedor implementa, e os tipos que ela troca.

As operações essenciais ficam nesta fronteira: listar o que existe, validar a
credencial, sondar um endpoint, gerar texto, expor seu stream e dizer que limites
foram observados. Roteamento, fila e escolha de modelo não moram aqui.

Limite declarado e limite observado são coisas diferentes e ficam em campos
diferentes. `ObservedLimits.source` diz de onde veio o número, para que ninguém
confunda o que a API respondeu com o que alguém supôs.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from providers.cognitive import CognitiveEvent

PROBE_PROMPT = "Responda apenas: ok"

# Orçamento da sonda. Já foi 16, e 16 media a si mesmo: modelo com raciocínio interno
# gastava o orçamento inteiro pensando e devolvia 200 vazio, o que a sonda registrava
# como `reachable`. O endpoint funcionava; o teto é que não deixava provar. Com folga
# para a deliberação caber, a sonda volta a medir o endpoint em vez do próprio limite.
# Continua barato: uma chamada por provedor por execução, com prompt trivial.
PROBE_MAX_OUTPUT_TOKENS = 512


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class ProviderError(RuntimeError):
    """Falha atribuível ao provedor, com a causa já classificada."""


class ProviderAuthError(ProviderError):
    """Credencial ausente, inválida ou sem permissão para o endpoint."""


class ProviderRateLimited(ProviderError):
    def __init__(self, message: str, retry_after_s: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class ProviderAccountExhausted(ProviderError):
    """Saldo ou crédito da conta esgotado: o provedor inteiro não atende."""


class ProviderUnavailable(ProviderError):
    """Endpoint existe no catálogo mas não atendeu — indisponível, não inexistente."""


_ACCOUNT_EXHAUSTED_MARKERS = (
    "prepayment credits",
    "credits are depleted",
    "credit is depleted",
    "insufficient credit",
    "insufficient funds",
    "billing hard limit",
)


def is_account_exhausted(message: str) -> bool:
    """Falha de conta, não de endpoint: 429 de crédito não é o mesmo que RPM."""
    text = message.casefold()
    return any(marker in text for marker in _ACCOUNT_EXHAUSTED_MARKERS)


def is_structural_key_auth(message: str) -> bool:
    """Auth da conta inteira (BYOK / teto USD 0), não de um modelo só."""
    text = message.casefold()
    return "byok" in text or "teto de gasto usd 0" in text


@dataclass(frozen=True, slots=True)
class ModelInfo:
    """Identidade de um endpoint. Não de um modelo em abstrato."""

    provider: str
    endpoint_id: str
    family: str
    capabilities: list[str] = field(default_factory=list)
    context_window: int | None = None
    max_output_tokens: int | None = None
    declared_limits: dict[str, Any] = field(default_factory=dict)
    available: bool = True
    probe_outcome: str = "not_tested"
    raw: dict[str, Any] = field(default_factory=dict)
    observed_at: str = field(default_factory=now)


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """Resultado de uma sonda. `ok` e `reachable` não são sinônimos.

    `reachable` é o endpoint que aceitou a chamada, autenticou e devolveu 200 sem
    escrever nada. O caminho existe e a credencial vale; a utilidade não foi
    demonstrada. Chamar isso de `ok` faria o registro afirmar mais do que se mediu, e
    a diferença importa porque é ela que decide se um endpoint pode receber trabalho.
    """

    provider: str
    endpoint_id: str
    # ok | reachable | auth | rate_limited | account_exhausted | unavailable | error
    outcome: str
    detail: str = ""
    latency_ms: int | None = None
    observed_at: str = field(default_factory=now)

    @property
    def ok(self) -> bool:
        """Respondeu e produziu texto. Só isso autoriza trabalho."""
        return self.outcome == "ok"

    @property
    def reachable(self) -> bool:
        """Chegou até o modelo, com ou sem texto de volta."""
        return self.outcome in ("ok", "reachable")


@dataclass(frozen=True, slots=True)
class GenerationResult:
    provider: str
    endpoint_id: str
    text: str
    usage: dict[str, Any] = field(default_factory=dict)
    latency_ms: int | None = None
    observed_at: str = field(default_factory=now)


@dataclass(frozen=True, slots=True)
class ObservedLimits:
    """Limites que uma resposta revelou. O campo `provider` não é a chave deles.

    Limite é por endpoint: na Groq, dois modelos da mesma conta reportaram tetos
    diferentes. O `_last_limits` guardado dentro de cada adaptador é apenas a leitura
    da última resposta daquela instância — armazenamento transitório, que o segundo
    endpoint sobrescreve. A chave `(provider, endpoint)` vive em
    `providers.registry`, e é de lá que o orquestrador deve planejar cota.
    """

    provider: str
    source: str  # headers | resposta | declarado | desconhecido
    requests_per_minute: int | None = None
    requests_per_day: int | None = None
    tokens_per_minute: int | None = None
    declared_requests_per_minute: int | None = None
    requests_remaining: int | None = None
    tokens_remaining: int | None = None
    retry_after_s: float | None = None
    note: str = ""
    raw: dict[str, str] = field(default_factory=dict)
    observed_at: str = field(default_factory=now)


class AdaptiveBackoff:
    """Atrasa a próxima chamada após 429 sem criar uma tentativa escondida.

    `retry-after` tem precedência. Quando não existe, o atraso cresce
    exponencialmente até um minuto. Cada comando faz no máximo uma requisição por
    provedor: descoberta e sonda são execuções separadas. Uma falha só condiciona uma
    execução futura, em vez de multiplicar consumo de cota.
    """

    def __init__(self, *, max_delay_s: float = 60.0) -> None:
        self._failures = 0
        self._not_before = 0.0
        self._max_delay_s = max_delay_s

    async def wait(self) -> None:
        remaining = self._not_before - time.monotonic()
        if remaining > 0:
            await asyncio.sleep(remaining)

    def rate_limited(self, retry_after_s: float | None) -> None:
        """Registra o 429 apenas para agendamento interno.

        O valor observado continua no ``ProviderRateLimited``/``ObservedLimits``;
        nunca devolvemos o fallback local para que ele não possa ser confundido com
        um ``retry-after`` informado pelo servidor. O bloqueio em processo é limitado
        a ``max_delay_s``.
        """
        self._failures += 1
        fallback = min(2.0 ** (self._failures - 1), self._max_delay_s)
        recomendado = max(retry_after_s, 0.0) if retry_after_s is not None else fallback
        bloqueio = min(recomendado, self._max_delay_s)
        self._not_before = max(self._not_before, time.monotonic() + bloqueio)

    def succeeded(self) -> None:
        self._failures = 0
        self._not_before = 0.0

    def hold(self, seconds: float | None) -> None:
        """Atrasa a próxima chamada sem contar como falha — janela vazia, não 429."""
        if seconds is None or seconds <= 0:
            return
        self._not_before = max(
            self._not_before, time.monotonic() + min(seconds, self._max_delay_s)
        )


@runtime_checkable
class ProviderAdapter(Protocol):
    provider: str

    async def list_models(self) -> list[ModelInfo]:
        """Endpoints que a conta realmente alcança agora."""
        ...

    async def probe_model(self, endpoint_id: str) -> ProbeResult:
        """Uma chamada mínima. Classifica a resposta em vez de propagar traceback."""
        ...

    async def generate(
        self, endpoint_id: str, prompt: str, *, max_output_tokens: int = 256
    ) -> GenerationResult: ...

    def stream_generate(
        self, endpoint_id: str, prompt: str, *, max_output_tokens: int = 256
    ) -> AsyncIterator[CognitiveEvent]:
        """O que o endpoint emite **durante** a execução, já classificado.

        Uma versão anterior deste texto dizia que a deliberação por quórum continuaria
        passando por `generate`, por ser "uma pergunta de resposta única". A pergunta
        continua sendo de resposta única; o que mudou é como ela é recolhida. Desde a
        ligação do canal cognitivo, o quórum consome o stream: mostrar o raciocínio
        enquanto ele acontece exige alguém escutando o intervalo, e não há como escutar
        depois o que só existe durante.

        `generate` não some — é o caminho de quem só quer o texto final e não deve pagar
        o custo do stream. A sonda de aptidão é esse caso: uma chamada mínima por endpoint.

        O contrato é o do envelope: cada evento corresponde a um campo que o endpoint de
        fato emitiu, com `raw_field` dizendo qual. Provedor que não entrega intervalo
        emite apenas `FINAL` — e isso não é falha, é a descrição correta dele.

        O `FINAL` carrega em `detail["usage"]` o consumo que o provedor reportou, no
        mesmo formato de `GenerationResult.usage`. Sem essa chave, consumir o stream
        trocaria a medida de cota por estimativa — ver `providers.cognitive`.
        """
        ...

    async def verify_credential(self) -> str:
        """Prova que a credencial vale, e devolve o detalhe já pronto para a interface.

        Existe separada de `list_models` porque as duas coisas só coincidem quando o
        catálogo é privado à conta. No Ollama Cloud ele é público — listar responde 200
        para qualquer chave —, e ali validar pela listagem afirmaria o que a chamada
        não mediu.
        """
        ...

    def get_observed_limits(self) -> ObservedLimits:
        """O que as respostas já revelaram sobre limite. Sem estimativa."""
        ...


async def probe_via_generate(adapter: ProviderAdapter, endpoint_id: str) -> ProbeResult:
    """Sondagem padrão: uma geração mínima com a falha já classificada.

    Os três provedores sondam igual porque a pergunta é a mesma — este endpoint
    responde? A tradução do erro de cada SDK já aconteceu dentro de `generate`, então
    aqui só resta escolher o rótulo e nunca deixar um traceback subir.
    """
    started = time.perf_counter()

    def elapsed_ms() -> int:
        return int((time.perf_counter() - started) * 1000)

    try:
        result = await adapter.generate(
            endpoint_id, PROBE_PROMPT, max_output_tokens=PROBE_MAX_OUTPUT_TOKENS
        )
    except ProviderAuthError as error:
        return ProbeResult(adapter.provider, endpoint_id, "auth", str(error), elapsed_ms())
    except ProviderAccountExhausted as error:
        return ProbeResult(
            adapter.provider,
            endpoint_id,
            "account_exhausted",
            str(error),
            elapsed_ms(),
        )
    except ProviderRateLimited as error:
        return ProbeResult(
            adapter.provider,
            endpoint_id,
            "rate_limited",
            str(error),
            elapsed_ms(),
        )
    except ProviderUnavailable as error:
        return ProbeResult(
            adapter.provider,
            endpoint_id,
            "unavailable",
            str(error),
            elapsed_ms(),
        )
    except Exception as error:  # noqa: BLE001 — o smoke test relata, não estoura
        detail = f"{type(error).__name__}: {error}"
        return ProbeResult(adapter.provider, endpoint_id, "error", detail, elapsed_ms())
    # Um modelo com raciocínio interno gasta o orçamento de saída antes de escrever
    # qualquer coisa: com os 16 tokens da sonda, o Gemini devolve 200 e nada mais.
    # Isso é alcance comprovado, não utilidade comprovada — e o registro precisa
    # separar os dois, porque é dele que sairá a decisão de dar trabalho ao endpoint.
    text = result.text.strip()
    if not text:
        return ProbeResult(
            adapter.provider,
            endpoint_id,
            "reachable",
            f"200 sem texto sob {PROBE_MAX_OUTPUT_TOKENS} tokens de saída",
            elapsed_ms(),
        )
    return ProbeResult(adapter.provider, endpoint_id, "ok", text[:120], elapsed_ms())


async def verify_via_list_models(adapter: ProviderAdapter) -> str:
    """Validação padrão de quem tem catálogo privado: listar autentica e não gera nada.

    Vale para Google, Groq e NVIDIA, onde `/models` responde a partir da conta e recusa
    quem não tem credencial. Não vale universalmente — ver `providers.ollama.adapter`.
    """
    models = await adapter.list_models()
    return f"{len(models)} endpoint(s) alcançáveis com esta credencial"


def infer_family(endpoint_id: str) -> str:
    """Família a partir do ID, para agrupar sem inventar taxonomia.

    Devolve o primeiro segmento significativo: `meta/llama-3.3-70b` → `llama`,
    `models/gemini-2.5-flash` → `gemini`. Palpite explícito e barato, usado apenas
    para agrupar na visualização; nada de decisão depende dele.

    `:` está entre os separadores por causa da Ollama, onde ele abre a etiqueta de
    tamanho: sem ele `gemma4:31b` viraria uma família de um membro só, porque a
    etiqueta entraria no nome do grupo. Os outros provedores não usam `:` em ID
    nenhum, então a regra não muda o que já estava agrupado.
    """
    tail = endpoint_id.rsplit("/", 1)[-1]
    for separator in ("-", "_", ".", ":"):
        tail = tail.split(separator)[0]
    return tail.lower() or endpoint_id.lower()


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _as_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def limits_from_headers(provider: str, headers: Any) -> ObservedLimits:
    """Lê headers `x-ratelimit-*` sem transportar a semântica entre provedores.

    Na Groq, a documentação define requests como RPD e tokens como TPM. Para os
    demais provedores os tetos ficam crus até que a API declare a janela.
    """
    collected = {
        key.lower(): value
        for key, value in dict(headers or {}).items()
        if key.lower().startswith("x-ratelimit") or key.lower() == "retry-after"
    }
    return ObservedLimits(
        provider=provider,
        source="headers" if collected else "desconhecido",
        requests_per_day=(
            _as_int(collected.get("x-ratelimit-limit-requests")) if provider == "groq" else None
        ),
        tokens_per_minute=(
            _as_int(collected.get("x-ratelimit-limit-tokens")) if provider == "groq" else None
        ),
        requests_remaining=_as_int(collected.get("x-ratelimit-remaining-requests")),
        tokens_remaining=_as_int(collected.get("x-ratelimit-remaining-tokens")),
        retry_after_s=parse_retry_after(collected.get("retry-after")),
        note=(
            "Groq: requisições em RPD e tokens em TPM; resets permanecem em raw."
            if collected and provider == "groq"
            else (
                "Headers preservados em raw; a janela não foi presumida."
                if collected
                else "A resposta não trouxe headers de limite."
            )
        ),
        raw=collected,
    )
