"""Adaptador do OpenRouter, limitado por construção às variantes ``:free``.

O OpenRouter é um gateway, não o fabricante do modelo nem necessariamente o host
final da inferência. Por isso o ID pedido continua sendo a identidade do endpoint,
enquanto o provedor upstream observado fica nos metadados de uso. Ele não vira
diversidade adicional de quórum por acidente.

O catálogo muda com frequência. A descoberta consulta ``/models`` e aceita somente
IDs publicados com o sufixo ``:free``, saída textual e preço zero de entrada e saída.
``openrouter/free`` não entra: ele escolhe um modelo aleatório e não preservaria a
identidade exigida pelo histórico deste projeto.
"""

from __future__ import annotations

import re
import time
from collections.abc import AsyncIterator
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
import orjson

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
    limits_from_headers,
    parse_retry_after,
    probe_via_generate,
)
from providers.cognitive import CognitiveEvent, CognitiveKind

PROVIDER = "openrouter"
BASE_URL = "https://openrouter.ai/api/v1"

# Limites mínimos comuns a toda conta que usa variantes gratuitas. A cota diária
# pode subir para 1000 conforme o histórico da conta; sem observar a conta, 50 é o
# único teto que se pode prometer para todas. Ambos são agregados à conta, nunca por
# modelo. Fonte: documentação oficial do OpenRouter, verificada em 2026-08-11.
DECLARED_FREE_BUDGET: dict[str, Any] = {
    "requests_per_minute_aggregate": 20,
    "requests_per_day_aggregate": 50,
    "origem": (
        "documentação oficial do OpenRouter em 2026-08-11; cota diária conservadora "
        "até que o nível da conta seja observado"
    ),
}

_RAW_MODEL_FIELDS = (
    "canonical_slug",
    "name",
    "created",
    "architecture",
    "pricing",
    "supported_parameters",
    "default_parameters",
    "top_provider",
    "per_request_limits",
    "reasoning",
    "expiration_date",
    "knowledge_cutoff",
)

_USAGE_FIELDS = (
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "cost",
    "is_byok",
    "prompt_tokens_details",
    "completion_tokens_details",
)

# A API modela IDs como `author/slug` e variantes como sufixos. Aceitar apenas uma
# variante estática final evita atalhos dinâmicos como `:online`, que habilitam busca
# paga, e aliases móveis. O catálogo passa pela mesma gramática que a geração.
_STATIC_FREE_ID = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*:free$"
)

_ZERO_PRICE = {
    "prompt": 0,
    "completion": 0,
    "request": 0,
    "image": 0,
}


def _dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _zero(value: object) -> bool:
    try:
        return Decimal(str(value)) == 0
    except (InvalidOperation, ValueError):
        return False


def _all_prices_zero(pricing: dict[str, Any]) -> bool:
    """Toda dimensão publicada é zero ou nula; campo novo falha fechado."""
    return bool(pricing) and all(value is None or _zero(value) for value in pricing.values())


def _is_textual_free_variant(raw: dict[str, Any]) -> bool:
    endpoint_id = raw.get("id")
    architecture = _dict(raw.get("architecture"))
    pricing = _dict(raw.get("pricing"))
    return (
        isinstance(endpoint_id, str)
        and _STATIC_FREE_ID.fullmatch(endpoint_id) is not None
        and "text" in _strings(architecture.get("output_modalities"))
        and _zero(pricing.get("prompt"))
        and _zero(pricing.get("completion"))
        and _all_prices_zero(pricing)
    )


def _safe_error(response: httpx.Response) -> str:
    """Mensagem do envelope de erro, sem serializar pedido, headers ou corpo inteiro."""
    try:
        body = orjson.loads(response.content)
    except orjson.JSONDecodeError:
        return f"HTTP {response.status_code}"
    error = body.get("error") if isinstance(body, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    return (
        str(message)[:300]
        if isinstance(message, str) and message
        else f"HTTP {response.status_code}"
    )


def _selected_upstream(body: dict[str, Any]) -> str | None:
    metadata = _dict(body.get("openrouter_metadata"))
    endpoints = _dict(metadata.get("endpoints"))
    available = endpoints.get("available")
    if isinstance(available, list):
        for item in available:
            if not isinstance(item, dict) or item.get("selected") is not True:
                continue
            provider = item.get("provider")
            if isinstance(provider, str) and provider:
                return provider
    provider = body.get("provider")
    return provider if isinstance(provider, str) and provider else None


def _route_observation(
    body: dict[str, Any], headers: httpx.Headers | None = None
) -> dict[str, Any]:
    """Somente escalares estáveis de proveniência; nunca o pipeline ou o prompt."""
    metadata = _dict(body.get("openrouter_metadata"))
    observed: dict[str, Any] = {}
    for source, target in (
        (body.get("model"), "openrouter_model"),
        (_selected_upstream(body), "openrouter_upstream_provider"),
        (metadata.get("strategy"), "openrouter_strategy"),
        (metadata.get("attempt"), "openrouter_attempt"),
    ):
        if isinstance(source, str | int) and not isinstance(source, bool):
            observed[target] = source
    generation_id = headers.get("x-generation-id") if headers is not None else None
    if generation_id:
        observed["openrouter_generation_id"] = generation_id
    return observed


def _tool_detail(item: object) -> dict[str, object]:
    raw = item if isinstance(item, dict) else {}
    function = raw.get("function")
    function = function if isinstance(function, dict) else {}
    # Argumentos são texto do modelo e não atravessam esta fronteira.
    return {
        "name": str(function.get("name") or ""),
        "index": raw.get("index"),
    }


async def _sse_data(response: httpx.Response) -> AsyncIterator[str]:
    """Decodifica framing SSE, inclusive comentários e campos ``data`` multilinha."""
    data: list[str] = []
    async for line in response.aiter_lines():
        if line == "":
            if data:
                yield "\n".join(data)
                data.clear()
            continue
        if line.startswith(":"):
            continue
        if line.startswith("data:"):
            value = line[5:]
            data.append(value[1:] if value.startswith(" ") else value)
    if data:
        yield "\n".join(data)


class OpenRouterAdapter:
    provider = PROVIDER

    def __init__(self, api_key: str, *, allow_uncapped_free_tier: bool = False) -> None:
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                # Preserva a decisão do gateway e o upstream real sem registrar o
                # pipeline completo, que pode carregar dados do pedido.
                "X-OpenRouter-Metadata": "enabled",
            },
            timeout=httpx.Timeout(60.0, connect=5.0),
        )
        self._allow_uncapped_free_tier = allow_uncapped_free_tier
        self._last_limits: ObservedLimits | None = None
        self._backoff = AdaptiveBackoff()

    @staticmethod
    def _require_free(endpoint_id: str) -> None:
        if _STATIC_FREE_ID.fullmatch(endpoint_id) is None:
            raise ProviderError(
                "o adaptador OpenRouter aceita somente IDs estáticos author/slug:free"
            )

    @staticmethod
    def _chat_body(
        endpoint_id: str,
        prompt: str,
        max_output_tokens: int,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        return {
            "model": endpoint_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_output_tokens,
            "stream": stream,
            # Um plugin pode estar habilitado por padrão na conta. Busca web cobra
            # mesmo com modelo :free, então a requisição a desliga explicitamente.
            "plugins": [{"id": "web", "enabled": False}],
            # Segunda linha: qualquer endpoint com preço de token, pedido ou imagem
            # maior que zero é filtrado pelo roteador antes da inferência.
            "provider": {"max_price": dict(_ZERO_PRICE)},
        }

    @staticmethod
    def _limits(headers: httpx.Headers) -> ObservedLimits:
        observed = limits_from_headers(PROVIDER, headers)
        return replace(
            observed,
            declared_requests_per_minute=20,
            note=(
                f"{observed.note} A franquia :free é agregada à conta OpenRouter; "
                "não pertence a cada endpoint."
            ),
        )

    def _raise_status(self, response: httpx.Response, *, auth_403: bool = False) -> None:
        if response.status_code < 400:
            return
        detail = _safe_error(response)
        if response.status_code == 429:
            retry_after = parse_retry_after(response.headers.get("retry-after"))
            self._last_limits = replace(
                self._limits(response.headers), retry_after_s=retry_after
            )
            self._backoff.rate_limited(retry_after)
            raise ProviderRateLimited(
                f"limite agregado do OpenRouter atingido: {detail}", retry_after
            )
        if response.status_code == 401 or (auth_403 and response.status_code == 403):
            raise ProviderAuthError(f"credencial rejeitada pelo OpenRouter: {detail}")
        if response.status_code == 402:
            raise ProviderAccountExhausted(
                f"saldo ou limite de crédito no OpenRouter: {detail}"
            )
        if response.status_code in (403, 404, 408, 409, 502, 503, 504, 529):
            raise ProviderUnavailable(f"endpoint indisponível no OpenRouter: {detail}")
        if response.status_code >= 500:
            raise ProviderUnavailable(f"OpenRouter indisponível: {detail}")
        raise ProviderError(f"pedido recusado pelo OpenRouter: {detail}")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        auth_403: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        await self._backoff.wait()
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.RequestError as error:
            raise ProviderUnavailable(f"OpenRouter inalcançável: {error}") from error
        self._raise_status(response, auth_403=auth_403)
        self._backoff.succeeded()
        self._last_limits = self._limits(response.headers)
        return response

    @staticmethod
    def _json(response: httpx.Response, context: str) -> dict[str, Any]:
        try:
            body = orjson.loads(response.content)
        except orjson.JSONDecodeError as error:
            raise ProviderError(f"{context} do OpenRouter não devolveu JSON válido") from error
        if not isinstance(body, dict):
            raise ProviderError(f"{context} do OpenRouter não devolveu um objeto")
        return body

    async def list_models(self) -> list[ModelInfo]:
        response = await self._request(
            "GET",
            "/models",
            auth_403=True,
            params={"limit": 1000, "output_modalities": "text"},
        )
        body = self._json(response, "catálogo")
        entries = body.get("data")
        if not isinstance(entries, list):
            raise ProviderError("catálogo do OpenRouter sem lista de modelos")
        links = _dict(body.get("links"))
        total = body.get("total_count")
        if (isinstance(total, int) and total > len(entries)) or links.get("next"):
            raise ProviderError(
                "catálogo do OpenRouter excede a página de 1000 endpoints; "
                "descoberta interrompida para não persistir inventário parcial"
            )

        models: list[ModelInfo] = []
        for entry in entries:
            if not isinstance(entry, dict) or not _is_textual_free_variant(entry):
                continue
            endpoint_id = entry["id"]
            assert isinstance(endpoint_id, str)
            supported = _strings(entry.get("supported_parameters"))
            # `completion` é a capacidade semântica desta rota. Os demais itens são
            # parâmetros aceitos e permanecem também literais em `raw`.
            capabilities = list(dict.fromkeys(["completion", *supported]))
            top_provider = _dict(entry.get("top_provider"))
            per_request = _dict(entry.get("per_request_limits"))
            declared = {**per_request, **DECLARED_FREE_BUDGET}
            models.append(
                ModelInfo(
                    provider=PROVIDER,
                    endpoint_id=endpoint_id,
                    family=infer_family(endpoint_id),
                    capabilities=capabilities,
                    context_window=_optional_int(entry.get("context_length"))
                    or _optional_int(top_provider.get("context_length")),
                    max_output_tokens=_optional_int(top_provider.get("max_completion_tokens")),
                    declared_limits=declared,
                    available=True,
                    raw={field: entry.get(field) for field in _RAW_MODEL_FIELDS},
                )
            )
        return sorted(models, key=lambda model: model.endpoint_id)

    async def verify_credential(self) -> str:
        # `/models` pode responder publicamente; `/key` é a prova autenticada e não
        # gera texto nem consome tokens de inferência.
        response = await self._request("GET", "/key", auth_403=True)
        body = self._json(response, "estado da credencial")
        data = body.get("data")
        if not isinstance(data, dict):
            raise ProviderError("estado da credencial no OpenRouter sem objeto data")
        if (
            data.get("is_management_key") is not False
            or data.get("is_provisioning_key") is not False
        ):
            raise ProviderAuthError(
                "o estado da chave precisa declarar explicitamente que ela não é "
                "administrativa nem de provisionamento"
            )
        # Uma chave dedicada com teto USD 0 fecha cobranças do OpenRouter e, com BYOK
        # incluído, as de chaves próprias de provedor. Ela não prova a configuração
        # externa de plugins: um Firecrawl travado por administrador usa créditos fora
        # do OpenRouter, precondição de ativação que `/key` não expõe.
        limit = data.get("limit")
        include_byok = data.get("include_byok_in_limit")
        if _zero(limit):
            if include_byok is not True:
                raise ProviderAuthError(
                    "a chave precisa incluir uso BYOK no teto de gasto USD 0"
                )
            return (
                "credencial :free aceita em /key com teto de gasto USD 0 e BYOK "
                "incluído, sem gerar tokens"
            )

        # Algumas contas sem créditos são identificadas por `/key` como free-tier e
        # não oferecem teto configurável. Essa exceção só existe por opt-in explícito
        # e exige a combinação exata observada: `True` não aceita 1, `None` não aceita
        # campo ausente com outro valor, e BYOK precisa estar explicitamente fora do
        # teto inexistente. As guardas :free, preço zero e plugins desligados continuam
        # aplicadas a cada pedido, mas uma chave BYOK vinculada à conta permanece fora
        # da proteção do OpenRouter — por isso o retorno traz o aviso ostensivo.
        uncapped_free_tier = (
            self._allow_uncapped_free_tier
            and data.get("is_free_tier") is True
            and "limit" in data
            and limit is None
            and include_byok is False
        )
        if uncapped_free_tier:
            return (
                "credencial :free aceita por opt-in: conta declarada free-tier sem "
                "teto. AVISO: uso BYOK fica fora de qualquer teto"
            )

        if self._allow_uncapped_free_tier:
            raise ProviderAuthError(
                "o opt-in sem teto só aceita /key com is_free_tier=true, limit=null "
                "e include_byok_in_limit=false; uso BYOK fica fora de qualquer teto"
            )
        raise ProviderAuthError(
            "a chave é válida, mas precisa de teto de gasto USD 0 para uso :free"
        )

    async def _ensure_zero_spend_key(self) -> None:
        # Revalida em cada chamada: o limite pode ser alterado fora deste processo.
        # `/key` não gera tokens; cachear transformaria uma chave antes segura numa
        # autorização permanente enquanto o worker permanecesse vivo.
        await self.verify_credential()

    async def probe_model(self, endpoint_id: str) -> ProbeResult:
        return await probe_via_generate(self, endpoint_id)

    async def generate(
        self, endpoint_id: str, prompt: str, *, max_output_tokens: int = 256
    ) -> GenerationResult:
        self._require_free(endpoint_id)
        await self._ensure_zero_spend_key()
        started = time.perf_counter()
        response = await self._request(
            "POST",
            "/chat/completions",
            json=self._chat_body(endpoint_id, prompt, max_output_tokens, stream=False),
        )
        body = self._json(response, "geração")
        choices = body.get("choices")
        message: dict[str, Any] = {}
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = _dict(choices[0].get("message"))
        content = message.get("content")
        raw_usage = _dict(body.get("usage"))
        if "cost" in raw_usage and not _zero(raw_usage["cost"]):
            raise ProviderError("OpenRouter registrou custo não zero em uma rota :free")
        usage = {field: raw_usage[field] for field in _USAGE_FIELDS if field in raw_usage}
        usage.update(_route_observation(body, response.headers))
        return GenerationResult(
            provider=PROVIDER,
            endpoint_id=endpoint_id,
            text=content if isinstance(content, str) else "",
            usage=usage,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    def _raise_stream_error(self, raw: object) -> None:
        error = raw if isinstance(raw, dict) else {}
        code = error.get("code")
        if isinstance(code, bool) or not isinstance(code, str | int):
            status = 0
        else:
            try:
                status = int(code)
            except ValueError:
                status = 0
        message = error.get("message")
        detail = str(message)[:300] if isinstance(message, str) else "erro sem detalhe"
        if status == 429:
            self._backoff.rate_limited(None)
            raise ProviderRateLimited(
                f"limite agregado do OpenRouter atingido durante o stream: {detail}"
            )
        if status == 401:
            raise ProviderAuthError(f"credencial rejeitada pelo OpenRouter: {detail}")
        if status in (402, 403, 404, 408, 409, 502, 503, 504, 529) or status >= 500:
            raise ProviderUnavailable(f"stream indisponível no OpenRouter: {detail}")
        raise ProviderError(f"erro durante o stream do OpenRouter: {detail}")

    async def stream_generate(
        self, endpoint_id: str, prompt: str, *, max_output_tokens: int = 256
    ) -> AsyncIterator[CognitiveEvent]:
        """SSE com deltas, raciocínio tipado e erro possível depois do HTTP 200."""
        self._require_free(endpoint_id)
        await self._ensure_zero_spend_key()
        await self._backoff.wait()
        sequence = 0
        finished = False
        final_detail: dict[str, Any] = {}
        # Consumo e proveniência acumulam separados porque o `usage` do evento final
        # precisa ter a mesma forma que `generate` devolve — é dele que o ledger tira
        # `total_tokens`. As mesmas chaves aparecem soltas em `final_detail`, que é o
        # registro do fim do stream; a duplicação é o preço de não deixar as duas
        # leituras divergirem.
        route: dict[str, Any] = {}
        usage: dict[str, Any] = {}
        try:
            async with self._client.stream(
                "POST",
                "/chat/completions",
                json=self._chat_body(endpoint_id, prompt, max_output_tokens, stream=True),
            ) as response:
                if response.status_code >= 400:
                    # No modo streaming o corpo não foi lido ainda. A classificação
                    # usa apenas seu envelope seguro, mas precisa materializá-lo antes.
                    await response.aread()
                self._raise_status(response)
                self._last_limits = self._limits(response.headers)
                generation_id = response.headers.get("x-generation-id")
                if generation_id:
                    route["openrouter_generation_id"] = generation_id
                    final_detail["openrouter_generation_id"] = generation_id

                async for payload in _sse_data(response):
                    if payload == "[DONE]":
                        finished = True
                        break
                    try:
                        chunk = orjson.loads(payload)
                    except orjson.JSONDecodeError as error:
                        raise ProviderError(
                            "evento SSE do OpenRouter não contém JSON válido"
                        ) from error
                    if not isinstance(chunk, dict):
                        raise ProviderError("evento SSE do OpenRouter não contém objeto")
                    if "error" in chunk:
                        self._raise_stream_error(chunk.get("error"))
                    raw_usage = _dict(chunk.get("usage"))
                    if "cost" in raw_usage and not _zero(raw_usage["cost"]):
                        raise ProviderError(
                            "OpenRouter registrou custo não zero em uma rota :free"
                        )
                    # A documentação afirma que o consumo completo vem na última mensagem
                    # do SSE, sem parâmetro que o peça: `usage: {include: true}` e
                    # `stream_options` estão depreciados e não têm efeito.
                    if raw_usage:
                        usage.update(
                            {
                                campo: raw_usage[campo]
                                for campo in _USAGE_FIELDS
                                if campo in raw_usage
                            }
                        )

                    observed = _route_observation(chunk)
                    route.update(observed)
                    final_detail.update(observed)
                    choices = chunk.get("choices")
                    if not isinstance(choices, list) or not choices:
                        continue
                    choice = choices[0] if isinstance(choices[0], dict) else {}
                    finish_reason = choice.get("finish_reason")
                    if isinstance(finish_reason, str) and finish_reason:
                        final_detail["finish_reason"] = finish_reason
                    if finish_reason == "error":
                        self._raise_stream_error(chunk.get("error"))
                    delta = _dict(choice.get("delta"))

                    details = delta.get("reasoning_details")
                    textual_reasoning = False
                    if isinstance(details, list):
                        for item in details:
                            if not isinstance(item, dict):
                                continue
                            kind = item.get("type")
                            text = item.get("text") if kind == "reasoning.text" else None
                            summary = (
                                item.get("summary") if kind == "reasoning.summary" else None
                            )
                            if isinstance(text, str) and text:
                                textual_reasoning = True
                                sequence += 1
                                yield CognitiveEvent(
                                    provider=PROVIDER,
                                    endpoint_id=endpoint_id,
                                    kind=CognitiveKind.REASONING,
                                    text=text,
                                    raw_field="delta.reasoning_details[].text",
                                    sequence=sequence,
                                )
                            elif isinstance(summary, str) and summary:
                                textual_reasoning = True
                                sequence += 1
                                yield CognitiveEvent(
                                    provider=PROVIDER,
                                    endpoint_id=endpoint_id,
                                    kind=CognitiveKind.REASONING_SUMMARY,
                                    text=summary,
                                    raw_field="delta.reasoning_details[].summary",
                                    sequence=sequence,
                                )
                            elif kind == "reasoning.encrypted":
                                sequence += 1
                                yield CognitiveEvent(
                                    provider=PROVIDER,
                                    endpoint_id=endpoint_id,
                                    kind=CognitiveKind.PROGRESS,
                                    raw_field="delta.reasoning_details[]",
                                    sequence=sequence,
                                    detail={
                                        "type": "reasoning.encrypted",
                                        "format": str(item.get("format") or ""),
                                        "index": item.get("index"),
                                    },
                                )

                    if not textual_reasoning:
                        legacy = delta.get("reasoning")
                        raw_field = "delta.reasoning"
                        if not isinstance(legacy, str):
                            legacy = delta.get("reasoning_content")
                            raw_field = "delta.reasoning_content"
                        if isinstance(legacy, str) and legacy:
                            sequence += 1
                            yield CognitiveEvent(
                                provider=PROVIDER,
                                endpoint_id=endpoint_id,
                                kind=CognitiveKind.REASONING,
                                text=legacy,
                                raw_field=raw_field,
                                sequence=sequence,
                            )

                    content = delta.get("content")
                    if isinstance(content, str) and content:
                        sequence += 1
                        yield CognitiveEvent(
                            provider=PROVIDER,
                            endpoint_id=endpoint_id,
                            kind=CognitiveKind.OUTPUT_DELTA,
                            text=content,
                            raw_field="delta.content",
                            sequence=sequence,
                        )
                    tools = delta.get("tool_calls")
                    if isinstance(tools, list):
                        for item in tools:
                            sequence += 1
                            yield CognitiveEvent(
                                provider=PROVIDER,
                                endpoint_id=endpoint_id,
                                kind=CognitiveKind.TOOL_CALL,
                                raw_field="delta.tool_calls",
                                sequence=sequence,
                                detail=_tool_detail(item),
                            )
        except httpx.RequestError as error:
            raise ProviderUnavailable(f"OpenRouter inalcançável: {error}") from error

        if not finished:
            raise ProviderUnavailable("stream do OpenRouter encerrou sem data: [DONE]")
        self._backoff.succeeded()
        sequence += 1
        if usage or route:
            final_detail["usage"] = {**usage, **route}
        yield CognitiveEvent(
            provider=PROVIDER,
            endpoint_id=endpoint_id,
            kind=CognitiveKind.FINAL,
            raw_field="data: [DONE]",
            sequence=sequence,
            detail=final_detail,
        )

    def get_observed_limits(self) -> ObservedLimits:
        if self._last_limits is not None:
            return self._last_limits
        return ObservedLimits(
            provider=PROVIDER,
            source="declarado",
            declared_requests_per_minute=20,
            note=(
                "A documentação declara 20 req/min e ao menos 50 req/dia, agregadas "
                "à conta para variantes :free; nenhuma resposta foi observada ainda."
            ),
        )
