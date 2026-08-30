"""Adaptador da API de inferência da Nous Research.

Documentação oficial: https://portal.nousresearch.com/api-docs (OAS 3.0,
``Nous Research Inference API 1.0.0``). Base:
``https://inference-api.nousresearch.com/v1``, OpenAI-compatível, chave no header
``Authorization: Bearer``. Chaves e créditos: portal.nousresearch.com.

A descoberta é deliberadamente estreita, pelo mesmo motivo que a do OpenRouter:
entram somente variantes publicadas cujo ID termina em ``:free`` e cujo preço de
entrada e saída é zero — o catálogo completo tem 368 modelos e a maior parte
cobra por token contra créditos da conta. A geração recusa qualquer outro ID na
hora, então preferência manual não aciona modelo pago.

O catálogo é **público**: ``/v1/models`` responde 200 sem chave. Listar, portanto,
não prova credencial nenhuma — a verificação usa uma chamada mínima
(``max_tokens=1``) num modelo-sentinela ``:free``, sem mensagem, e autentica sem
gerar conteúdo. É o mesmo princípio da Ollama Cloud: a chamada que prova a chave
não pode ser a listagem pública.

O teto do free tier — 50 RPM e 500.000 TPM — vem da documentação oficial e entra
como ``declared_limits`` com a origem dita em texto, nunca como limite observado.
"""

from __future__ import annotations

import re
import time
from collections.abc import AsyncIterator
from dataclasses import replace
from decimal import Decimal, InvalidOperation

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
    limits_from_headers,
    parse_retry_after,
    probe_via_generate,
)
from providers.cognitive import CognitiveEvent, CognitiveKind

PROVIDER = "nous"
BASE_URL = "https://inference-api.nousresearch.com/v1"

# Teto do free tier, da documentação oficial (portal.nousresearch.com/api-docs,
# seção "API Key Rate Limits"). Declarado, não observado: só entra na conta
# quando uma resposta real confirmar o contrário.
FREE_RPM = 50
FREE_TPM = 500_000
DECLARED_BUDGET = {
    "requests_per_minute": FREE_RPM,
    "tokens_per_minute": FREE_TPM,
    "origem": "documentação oficial da Nous (api-docs, free tier), 2026-08-16",
}

# O menor modelo :free do catálogo, usado só para provar a chave com uma chamada
# de um token. Sentinela é identidade estável; a escolha não atribui papel algum.
SENTINEL = "stepfun/step-3.7-flash:free"

# A API modela IDs como `author/slug` e variantes como sufixos. Aceitar apenas a
# variante estática final impede atalhos e aliases móveis; o catálogo passa pela
# mesma gramática que a geração — a mesma regra que o OpenRouter aplica.
_STATIC_FREE_ID = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*:free$"
)


def _preco_zero(raw: object) -> bool:
    """Preço de entrada e saída exatamente zero, como a API publica em string."""
    if not isinstance(raw, dict):
        return False
    for campo in ("prompt", "completion"):
        valor = raw.get(campo)
        if valor is None:
            return False
        try:
            if Decimal(str(valor)) != 0:
                return False
        except InvalidOperation:
            return False
    return True


def _ferramenta(item: object) -> dict[str, object]:
    """Só escalares de uma chamada de ferramenta: nome e índice.

    O argumento fica de fora — é texto que o modelo escreveu, e a lista branca que o
    Atlas recebe é deliberadamente pequena.
    """
    funcao = getattr(item, "function", None)
    return {
        "name": str(getattr(funcao, "name", "") or ""),
        "index": getattr(item, "index", None),
    }


class NousAdapter:
    provider = PROVIDER

    def __init__(self, api_key: str) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=BASE_URL,
            timeout=httpx.Timeout(60.0, connect=5.0),
            max_retries=0,
        )
        self._last_limits: ObservedLimits | None = None
        self._backoff = AdaptiveBackoff()

    @staticmethod
    def _classify(error: Exception) -> Exception:
        import openai

        if isinstance(error, openai.AuthenticationError | openai.PermissionDeniedError):
            return ProviderAuthError(f"credencial rejeitada pela Nous: {error}")
        if is_account_exhausted(str(error)):
            return ProviderAccountExhausted(f"crédito da conta Nous esgotado: {error}")
        if getattr(error, "status_code", None) == 402:
            # 402 é o pedágio x402 da documentação: sem pagamento não há inferência.
            return ProviderAccountExhausted(f"pagamento exigido pela Nous (402): {error}")
        if isinstance(error, openai.RateLimitError):
            headers = getattr(getattr(error, "response", None), "headers", None) or {}
            retry_after = parse_retry_after(headers.get("retry-after"))
            return ProviderRateLimited(f"limite da Nous atingido: {error}", retry_after)
        if isinstance(
            error, openai.NotFoundError | openai.InternalServerError | openai.APIConnectionError
        ):
            return ProviderUnavailable(f"endpoint indisponível na Nous: {error}")
        return error

    @staticmethod
    def _require_free(endpoint_id: str) -> None:
        if _STATIC_FREE_ID.fullmatch(endpoint_id) is None:
            raise ProviderError(
                "o adaptador Nous aceita somente IDs estáticos author/slug:free"
            )

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
                    observed, retry_after_s=classified.retry_after_s
                )
            raise classified from error

        self._backoff.succeeded()
        self._last_limits = limits_from_headers(PROVIDER, raw.headers)
        listing = raw.parse()  # resposta legada da SDK da OpenAI: parse é síncrono
        models = [
            ModelInfo(
                provider=PROVIDER,
                endpoint_id=model.id,
                family=infer_family(model.id),
                context_window=getattr(model, "context_length", None),
                declared_limits=DECLARED_BUDGET,
                raw={
                    "canonical_slug": getattr(model, "canonical_slug", None),
                    "hugging_face_id": getattr(model, "hugging_face_id", None),
                    "pricing": getattr(model, "pricing", None),
                },
            )
            for model in listing.data
            if model.id.endswith(":free")
            and _STATIC_FREE_ID.fullmatch(model.id) is not None
            and _preco_zero(getattr(model, "pricing", None))
        ]
        return sorted(models, key=lambda m: m.endpoint_id)

    async def verify_credential(self) -> str:
        """Uma chamada mínima no modelo-sentinela: prova a chave sem gerar conteúdo.

        `/v1/models` é público — responder 200 para qualquer chave não mede nada.
        `max_tokens=1` com lista de mensagens vazia autentica e não produz texto.
        """
        await self._backoff.wait()
        try:
            await self._client.chat.completions.create(
                model=SENTINEL,
                messages=[],
                max_tokens=1,
            )
        except Exception as error:  # noqa: BLE001
            raise self._classify(error) from error
        self._backoff.succeeded()
        return (
            "credencial aceita pela API da Nous "
            f"(sentinela {SENTINEL}, {FREE_RPM} RPM e {FREE_TPM:,} TPM no free tier)"
        )

    async def probe_model(self, endpoint_id: str) -> ProbeResult:
        return await probe_via_generate(self, endpoint_id)

    async def generate(
        self, endpoint_id: str, prompt: str, *, max_output_tokens: int = 256
    ) -> GenerationResult:
        self._require_free(endpoint_id)
        await self._backoff.wait()
        started = time.perf_counter()
        try:
            raw = await self._client.chat.completions.with_raw_response.create(
                model=endpoint_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_output_tokens,
            )
        except Exception as error:  # noqa: BLE001
            classified = self._classify(error)
            if isinstance(classified, ProviderRateLimited):
                self._backoff.rate_limited(classified.retry_after_s)
                response = getattr(error, "response", None)
                observed = limits_from_headers(PROVIDER, getattr(response, "headers", None))
                self._last_limits = replace(
                    observed, retry_after_s=classified.retry_after_s
                )
            raise classified from error

        self._backoff.succeeded()
        self._last_limits = limits_from_headers(PROVIDER, raw.headers)
        completion = raw.parse()  # resposta legada da SDK da OpenAI: parse é síncrono
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
        """O intervalo, como a API OpenAI-compatível da Nous o emite.

        A documentação oficial diz que o raciocínio do Hermes 4 pode vir no campo
        ``reasoning_content`` da resposta; aqui ele é lido do dicionário do pedaço,
        como no adaptador da NVIDIA, e emitido como ``REASONING`` quando existir —
        nunca inferido do conteúdo.
        """
        self._require_free(endpoint_id)
        await self._backoff.wait()
        sequencia = 0
        uso: dict[str, object] = {}
        try:
            stream = await self._client.chat.completions.create(
                model=endpoint_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_output_tokens,
                stream=True,
            )
            async for chunk in stream:
                reportado = getattr(chunk, "usage", None)
                if reportado is not None and hasattr(reportado, "model_dump"):
                    uso = dict(reportado.model_dump())
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                bruto = delta.model_dump() if hasattr(delta, "model_dump") else {}
                for campo, tipo in (
                    ("reasoning_content", CognitiveKind.REASONING),
                    ("content", CognitiveKind.OUTPUT_DELTA),
                ):
                    texto = bruto.get(campo)
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
                for item in getattr(delta, "tool_calls", None) or []:
                    sequencia += 1
                    yield CognitiveEvent(
                        provider=PROVIDER,
                        endpoint_id=endpoint_id,
                        kind=CognitiveKind.TOOL_CALL,
                        raw_field="delta.tool_calls",
                        sequence=sequencia,
                        detail=_ferramenta(item),
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
        observed = self._last_limits or ObservedLimits(
            provider=PROVIDER,
            source="desconhecido",
            note="Nenhuma resposta observada ainda nesta sessão.",
        )
        return replace(
            observed,
            declared_requests_per_minute=FREE_RPM,
            note=f"{observed.note} Free tier declarado: {FREE_RPM} RPM, {FREE_TPM:,} TPM.",
        )
