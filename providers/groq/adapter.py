"""Adaptador da Groq.

Os limites da conta não são presumidos: a Groq devolve `x-ratelimit-*` em cada
resposta, e por isso toda geração passa por `with_raw_response`, que preserva os
headers. Um 429 registra o `retry-after` que veio, não um valor inventado.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import replace

import httpx

from providers.base import (
    AdaptiveBackoff,
    GenerationResult,
    ModelInfo,
    ObservedLimits,
    ProbeResult,
    ProviderAccountExhausted,
    ProviderAuthError,
    ProviderRateLimited,
    ProviderUnavailable,
    infer_family,
    is_account_exhausted,
    limits_from_headers,
    parse_retry_after,
    probe_via_generate,
    verify_via_list_models,
)
from providers.cognitive import CognitiveEvent, CognitiveKind
from providers.groq.limits import SHUT_DOWN, declared_limits, parse_reset_duration

PROVIDER = "groq"


def _ferramenta(item: object) -> dict[str, object]:
    """Só escalares de uma chamada de ferramenta: nome e índice.

    O argumento fica de fora de propósito — ele é texto que o modelo escreveu, e a lista
    branca que o Atlas recebe é deliberadamente pequena.
    """
    funcao = getattr(item, "function", None)
    return {
        "name": str(getattr(funcao, "name", "") or ""),
        "index": getattr(item, "index", None),
    }


def _uso_do_pedaco(pedaco: object) -> dict[str, object]:
    """O consumo de um pedaço, nos dois lugares em que a SDK 1.6 o declara.

    `ChatCompletionChunk` traz `usage` no topo **e** `x_groq.usage`, ambos opcionais —
    verificado no pacote instalado. A documentação de streaming não afirma qual deles a
    Groq preenche, então ler os dois descreve o que chegou em vez de apostar num.

    Nada é acrescentado à requisição para provocar esse campo: `stream_options` é
    parâmetro da OpenAI, e presumir compatibilidade é exatamente o que já fez esta
    fronteira afirmar o que não tinha medido.
    """
    for fonte in (pedaco, getattr(pedaco, "x_groq", None)):
        uso = getattr(fonte, "usage", None)
        if uso is not None and hasattr(uso, "model_dump"):
            return dict(uso.model_dump())
    return {}


class GroqAdapter:
    provider = PROVIDER

    def __init__(self, api_key: str) -> None:
        from groq import AsyncGroq

        self._client = AsyncGroq(
            api_key=api_key,
            timeout=httpx.Timeout(30.0, connect=5.0),
            max_retries=0,
        )
        self._last_limits: ObservedLimits | None = None
        self._backoff = AdaptiveBackoff()

    @staticmethod
    def _classify(error: Exception) -> Exception:
        import groq

        if isinstance(error, groq.AuthenticationError | groq.PermissionDeniedError):
            return ProviderAuthError(f"credencial rejeitada pela Groq: {error}")
        if is_account_exhausted(str(error)):
            return ProviderAccountExhausted(f"crédito da conta Groq esgotado: {error}")
        if isinstance(error, groq.RateLimitError):
            headers = getattr(getattr(error, "response", None), "headers", None) or {}
            retry_after = parse_retry_after(headers.get("retry-after"))
            return ProviderRateLimited(f"limite da Groq atingido: {error}", retry_after)
        if isinstance(
            error, groq.NotFoundError | groq.InternalServerError | groq.APIConnectionError
        ):
            return ProviderUnavailable(f"endpoint indisponível na Groq: {error}")
        return error

    async def list_models(self) -> list[ModelInfo]:
        await self._backoff.wait()
        try:
            raw = await self._client.models.with_raw_response.list()
        except Exception as error:  # noqa: BLE001
            classified = self._classify(error)
            if isinstance(classified, ProviderRateLimited):
                self._backoff.rate_limited(classified.retry_after_s)
                response = getattr(error, "response", None)
                observed = limits_from_headers(PROVIDER, getattr(response, "headers", None))
                self._last_limits = replace(
                    observed,
                    retry_after_s=classified.retry_after_s,
                )
            raise classified from error

        self._backoff.succeeded()
        self._last_limits = limits_from_headers(PROVIDER, raw.headers)
        self._segurar_se_esgotou()
        listing = await raw.parse()
        models: list[ModelInfo] = []
        for model in listing.data:
            endpoint_id = model.id
            desligado = SHUT_DOWN.get(endpoint_id)
            context = getattr(model, "context_window", None)
            capabilities = list(getattr(model, "capabilities", None) or [])
            models.append(
                ModelInfo(
                    provider=PROVIDER,
                    endpoint_id=endpoint_id,
                    family=infer_family(endpoint_id),
                    capabilities=capabilities,
                    context_window=context,
                    max_output_tokens=getattr(model, "max_completion_tokens", None),
                    declared_limits=declared_limits(endpoint_id),
                    available=bool(getattr(model, "active", True)) and desligado is None,
                    raw={
                        "owned_by": getattr(model, "owned_by", None),
                        "capabilities_reported": bool(capabilities),
                        **({"shutdown": desligado} if desligado else {}),
                    },
                )
            )
        return sorted(models, key=lambda m: m.endpoint_id)

    async def verify_credential(self) -> str:
        return await verify_via_list_models(self)

    async def probe_model(self, endpoint_id: str) -> ProbeResult:
        return await probe_via_generate(self, endpoint_id)

    async def generate(
        self, endpoint_id: str, prompt: str, *, max_output_tokens: int = 256
    ) -> GenerationResult:
        await self._backoff.wait()
        started = time.perf_counter()
        try:
            raw = await self._client.chat.completions.with_raw_response.create(
                model=endpoint_id,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=max_output_tokens,
            )
        except Exception as error:  # noqa: BLE001
            classified = self._classify(error)
            if isinstance(classified, ProviderRateLimited):
                self._backoff.rate_limited(classified.retry_after_s)
                response = getattr(error, "response", None)
                observed = limits_from_headers(PROVIDER, getattr(response, "headers", None))
                self._last_limits = replace(
                    observed,
                    retry_after_s=classified.retry_after_s,
                )
            raise classified from error

        self._backoff.succeeded()
        self._last_limits = limits_from_headers(PROVIDER, raw.headers)
        self._segurar_se_esgotou()
        completion = await raw.parse()
        elapsed = int((time.perf_counter() - started) * 1000)
        usage = completion.usage.model_dump() if completion.usage else {}
        text = completion.choices[0].message.content or "" if completion.choices else ""
        return GenerationResult(
            provider=PROVIDER,
            endpoint_id=endpoint_id,
            text=text,
            usage=usage,
            latency_ms=elapsed,
        )

    async def stream_generate(
        self, endpoint_id: str, prompt: str, *, max_output_tokens: int = 256
    ) -> AsyncIterator[CognitiveEvent]:
        """O intervalo, como a Groq o emite.

        O `ChoiceDelta` do SDK 1.6 declara `content`, `reasoning`, `tool_calls` e
        `executed_tools` — verificado no próprio pacote instalado, e não presumido da
        compatibilidade com a OpenAI, que aqui justamente não vale: `reasoning` e
        `executed_tools` são campos da Groq e não existem no delta da OpenAI.

        Cada campo vira um tipo do envelope, e nenhum vira mais de um. O que o delta não
        traz não é emitido — ausência de raciocínio é informação sobre o endpoint.
        """
        await self._backoff.wait()
        sequencia = 0
        uso: dict[str, object] = {}
        try:
            stream = await self._client.chat.completions.create(
                model=endpoint_id,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=max_output_tokens,
                stream=True,
            )
            async for chunk in stream:
                # O consumo vem no último pedaço, e esse pedaço costuma chegar sem
                # `choices`. Lê-lo antes do desvio abaixo é o que impede de descartá-lo
                # junto com o pedaço que não tem delta nenhum.
                uso = _uso_do_pedaco(chunk) or uso
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                for campo, tipo in (
                    ("reasoning", CognitiveKind.REASONING),
                    ("content", CognitiveKind.OUTPUT_DELTA),
                ):
                    texto = getattr(delta, campo, None)
                    if not isinstance(texto, str) or texto == "":
                        continue
                    sequencia += 1
                    yield CognitiveEvent(
                        provider=PROVIDER,
                        endpoint_id=endpoint_id,
                        kind=tipo,
                        text=texto,
                        raw_field=f"delta.{campo}",
                        sequence=sequencia,
                    )
                for campo, tipo in (
                    ("tool_calls", CognitiveKind.TOOL_CALL),
                    ("executed_tools", CognitiveKind.TOOL_RESULT),
                ):
                    for item in getattr(delta, campo, None) or []:
                        sequencia += 1
                        yield CognitiveEvent(
                            provider=PROVIDER,
                            endpoint_id=endpoint_id,
                            kind=tipo,
                            raw_field=f"delta.{campo}",
                            sequence=sequencia,
                            # Só escalares: nome e índice bastam para dizer o que foi
                            # usado, e o argumento da ferramenta pode conter qualquer
                            # coisa que o modelo tenha escrito.
                            detail=_ferramenta(item),
                        )
        except Exception as error:  # noqa: BLE001
            classified = self._classify(error)
            if isinstance(classified, ProviderRateLimited):
                self._backoff.rate_limited(classified.retry_after_s)
            raise classified from error
        self._backoff.succeeded()
        # Stream não devolve header; o hold fica para generate/list, que leem raw.
        sequencia += 1
        yield CognitiveEvent(
            provider=PROVIDER,
            endpoint_id=endpoint_id,
            kind=CognitiveKind.FINAL,
            raw_field="stream.end",
            sequence=sequencia,
            detail={"usage": uso} if uso else {},
        )

    def get_observed_limits(self) -> ObservedLimits:
        if self._last_limits is not None:
            return self._last_limits
        return ObservedLimits(
            provider=PROVIDER,
            source="desconhecido",
            note="Nenhuma resposta observada ainda nesta sessão.",
        )

    def _segurar_se_esgotou(self) -> None:
        """Se o header diz que a janela acabou, espera o reset em vez de provocar 429."""
        limites = self._last_limits
        if limites is None:
            return
        if limites.tokens_remaining == 0:
            espera = parse_reset_duration(limites.raw.get("x-ratelimit-reset-tokens"))
            self._backoff.hold(espera)
        elif limites.requests_remaining == 0:
            espera = parse_reset_duration(limites.raw.get("x-ratelimit-reset-requests"))
            self._backoff.hold(espera)
