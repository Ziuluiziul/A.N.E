"""Adaptador da API Gemini.

O inventário vem de `models.list()` a cada execução: modelo antigo sai do ar sem
aviso e um catálogo copiado envelhece calado. Nada aqui presume que um ID visto
ontem continua atendendo hoje.

Limites do free tier variam por modelo e não vêm em header nesta API. Por isso
`get_observed_limits` só reporta o que uma resposta 429 efetivamente revelou, com
`source` dizendo de onde saiu o número.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from providers.base import (
    AdaptiveBackoff,
    GenerationResult,
    ModelInfo,
    ObservedLimits,
    ProbeResult,
    ProviderAccountExhausted,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimited,
    ProviderUnavailable,
    infer_family,
    is_account_exhausted,
    parse_retry_after,
    probe_via_generate,
    verify_via_list_models,
)
from providers.cognitive import CognitiveEvent, CognitiveKind
from providers.google.limits import declared_limits

PROVIDER = "google"


class GoogleAdapter:
    provider = PROVIDER

    def __init__(self, api_key: str) -> None:
        from google import genai
        from google.genai import types

        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=30_000,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        self._last_limits: ObservedLimits | None = None
        self._backoff = AdaptiveBackoff()

    # --- tradução de erro --------------------------------------------------

    @staticmethod
    def _classify(error: Exception) -> Exception:
        response = getattr(error, "response", None)
        code = (
            getattr(error, "code", None)
            or getattr(response, "status_code", None)
            or getattr(response, "status", None)
        )
        headers = getattr(response, "headers", None) or {}
        message = str(error)
        if code in (401, 403) or "API key" in message:
            return ProviderAuthError(f"credencial rejeitada pelo Google: {message}")
        if is_account_exhausted(message):
            return ProviderAccountExhausted(
                f"crédito da conta Google esgotado: {message}"
            )
        if code == 429 or "RESOURCE_EXHAUSTED" in message:
            return ProviderRateLimited(
                f"limite do free tier atingido: {message}",
                parse_retry_after(headers.get("retry-after")),
            )
        if code == 404 or (isinstance(code, int) and 500 <= code < 600):
            return ProviderUnavailable(f"endpoint indisponível: {message}")
        if isinstance(error, httpx.HTTPError | TimeoutError | ConnectionError):
            return ProviderUnavailable(f"falha de transporte no Google: {message}")
        return error

    # --- interface ---------------------------------------------------------

    async def list_models(self) -> list[ModelInfo]:
        from google.genai import types

        await self._backoff.wait()
        try:
            # Uma execução de descoberta pode fazer uma requisição por provedor, não
            # uma requisição escondida por página. Mil é o máximo da API e comporta o
            # catálogo atual; se um dia não comportar, falhamos explicitamente em vez
            # de devolver inventário parcial ou paginar em silêncio.
            pager = await self._client.aio.models.list(
                config=types.ListModelsConfig(page_size=1000)
            )
            raw_models = list(pager.page)
            if pager.config.get("page_token"):
                raise ProviderError(
                    "catálogo do Google excede a primeira página de 1000 endpoints; "
                    "descoberta interrompida para respeitar uma requisição por execução"
                )
        except Exception as error:  # noqa: BLE001 — classificamos e reerguemos
            classified = self._classify(error)
            if isinstance(classified, ProviderRateLimited):
                self._backoff.rate_limited(classified.retry_after_s)
                self._last_limits = ObservedLimits(
                    provider=PROVIDER,
                    source="resposta",
                    retry_after_s=classified.retry_after_s,
                    note=f"429 na listagem: {classified}",
                )
            raise classified from error

        self._backoff.succeeded()
        models: list[ModelInfo] = []
        for model in raw_models:
            endpoint_id = (model.name or "").removeprefix("models/")
            if not endpoint_id:
                continue
            actions = list(getattr(model, "supported_actions", None) or [])
            models.append(
                ModelInfo(
                    provider=PROVIDER,
                    endpoint_id=endpoint_id,
                    family=infer_family(endpoint_id),
                    capabilities=actions,
                    context_window=getattr(model, "input_token_limit", None),
                    max_output_tokens=getattr(model, "output_token_limit", None),
                    declared_limits=declared_limits(endpoint_id),
                    available="generateContent" in actions,
                    raw={"display_name": getattr(model, "display_name", None)},
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
        from google.genai import types

        await self._backoff.wait()
        started = time.perf_counter()
        try:
            response = await self._client.aio.models.generate_content(
                model=endpoint_id,
                contents=prompt,
                config=types.GenerateContentConfig(max_output_tokens=max_output_tokens),
            )
        except Exception as error:  # noqa: BLE001
            classified = self._classify(error)
            if isinstance(classified, ProviderRateLimited):
                self._backoff.rate_limited(classified.retry_after_s)
                self._last_limits = ObservedLimits(
                    provider=PROVIDER,
                    source="resposta",
                    retry_after_s=classified.retry_after_s,
                    note=f"429 em {endpoint_id}: {classified}",
                )
            raise classified from error

        self._backoff.succeeded()
        elapsed = int((time.perf_counter() - started) * 1000)
        usage: dict[str, Any] = {}
        metadata = getattr(response, "usage_metadata", None)
        if metadata is not None:
            usage = {
                "prompt_tokens": getattr(metadata, "prompt_token_count", None),
                "output_tokens": getattr(metadata, "candidates_token_count", None),
                "total_tokens": getattr(metadata, "total_token_count", None),
            }
        return GenerationResult(
            provider=PROVIDER,
            endpoint_id=endpoint_id,
            text=response.text or "",
            usage=usage,
            latency_ms=elapsed,
        )

    async def stream_generate(
        self, endpoint_id: str, prompt: str, *, max_output_tokens: int = 256
    ) -> AsyncIterator[CognitiveEvent]:
        """O intervalo, como o Google o emite: partes, algumas marcadas como pensamento.

        Aqui o raciocínio é **resumo**, e não fluxo. O SDK 2.16 declara
        `ThinkingConfig(include_thoughts, thinking_budget, thinking_level)` e um campo
        `thought` em `Part` — verificado no pacote instalado. Com `include_thoughts`, as
        partes de resumo voltam com `part.thought is True`, e as de resposta, sem ele.

        A distinção entre A e B mora exatamente nesta linha: o que chega é o que o Google
        escolheu contar sobre o próprio raciocínio, não o raciocínio. Classificar isso
        como `REASONING` faria o Atlas prometer um fluxo que o provedor não entrega.
        """
        from google.genai import types

        await self._backoff.wait()
        sequencia = 0
        uso: dict[str, Any] = {}
        try:
            stream = await self._client.aio.models.generate_content_stream(
                model=endpoint_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_output_tokens,
                    thinking_config=types.ThinkingConfig(include_thoughts=True),
                ),
            )
            async for chunk in stream:
                # `usage_metadata` é campo do próprio pedaço — `GenerateContentResponse`
                # o declara, e é o mesmo objeto que `generate` lê depois. O último que
                # vier vale: os anteriores são contagens parciais da mesma resposta.
                metadata = getattr(chunk, "usage_metadata", None)
                if metadata is not None:
                    uso = {
                        "prompt_tokens": getattr(metadata, "prompt_token_count", None),
                        "output_tokens": getattr(metadata, "candidates_token_count", None),
                        "total_tokens": getattr(metadata, "total_token_count", None),
                    }
                for candidato in getattr(chunk, "candidates", None) or []:
                    conteudo = getattr(candidato, "content", None)
                    for parte in getattr(conteudo, "parts", None) or []:
                        texto = getattr(parte, "text", None)
                        if not isinstance(texto, str) or texto == "":
                            continue
                        pensamento = getattr(parte, "thought", None) is True
                        sequencia += 1
                        yield CognitiveEvent(
                            provider=PROVIDER,
                            endpoint_id=endpoint_id,
                            kind=CognitiveKind.REASONING_SUMMARY
                            if pensamento
                            else CognitiveKind.OUTPUT_DELTA,
                            text=texto,
                            raw_field="part.thought" if pensamento else "part.text",
                            sequence=sequencia,
                        )
        except Exception as error:  # noqa: BLE001
            classified = self._classify(error)
            if isinstance(classified, ProviderRateLimited):
                self._backoff.rate_limited(classified.retry_after_s)
            raise classified from error
        self._backoff.succeeded()
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
            note=(
                "A API Gemini não devolve headers de limite. Os tetos do free tier "
                "variam por modelo e só se conhecem por 429 observado ou pela "
                "documentação da conta."
            ),
        )
