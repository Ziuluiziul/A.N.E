"""Adaptador dos NIM Free Endpoints da NVIDIA.

O orçamento de 40 requisições por minuto agregadas foi confirmado pelo
mantenedor em 2026-08-17. Entra como `declared_limits`, com a origem dita em
texto, e nunca como limite observado — `get_observed_limits` só devolve o que
uma resposta real mostrou.
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

PROVIDER = "nvidia"


def _ferramenta(item: object) -> dict[str, object]:
    """Só escalares de uma chamada de ferramenta: nome e índice.

    O argumento fica de fora — ele é texto que o modelo escreveu, e a lista branca que o
    Atlas recebe é deliberadamente pequena.
    """
    funcao = getattr(item, "function", None)
    return {
        "name": str(getattr(funcao, "name", "") or ""),
        "index": getattr(item, "index", None),
    }
BASE_URL = "https://integrate.api.nvidia.com/v1"

# Orçamento informado pelo mantenedor e reconfirmado em 2026-08-17: 40 RPM
# agregados da conta. Entra como `declared_limits`, nunca como observado.
DECLARED_REQUESTS_PER_MINUTE = 40
DECLARED_BUDGET = {
    "requests_per_minute_aggregate": DECLARED_REQUESTS_PER_MINUTE,
    "origem": "confirmado pelo mantenedor em 2026-08-17 (40 RPM agregados)",
}


class NvidiaAdapter:
    provider = PROVIDER

    def __init__(self, api_key: str) -> None:
        from openai import AsyncOpenAI

        # 60s, e não os 30s dos outros dois adaptadores: no NIM o mesmo endpoint
        # respondeu em 25,2s e 25,8s antes de estourar em 30,8s. Vivendo na borda ele
        # derruba o painel inteiro por latência de fila, não por incapacidade — e é o
        # único endpoint nvidia usável, então sua queda custa a diversidade exigida.
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
            return ProviderAuthError(f"credencial rejeitada pela NVIDIA: {error}")
        if is_account_exhausted(str(error)):
            return ProviderAccountExhausted(f"crédito da conta NVIDIA esgotado: {error}")
        if isinstance(error, openai.RateLimitError):
            headers = getattr(getattr(error, "response", None), "headers", None) or {}
            retry_after = parse_retry_after(headers.get("retry-after"))
            return ProviderRateLimited(f"limite do NIM atingido: {error}", retry_after)
        status = getattr(error, "status_code", None)
        if isinstance(
            error, openai.NotFoundError | openai.InternalServerError | openai.APIConnectionError
        ) or status in {404, 408, 409, 410, 502, 503, 504}:
            return ProviderUnavailable(f"endpoint indisponível no NIM: {error}")
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
        # `parse()` aqui é síncrono: `with_raw_response` da SDK da OpenAI devolve a
        # resposta legada. Na SDK da Groq o mesmo atributo devolve a nova, cujo
        # `parse()` é corrotina. Mesmo nome, contratos diferentes.
        listing = raw.parse()
        models = [
            ModelInfo(
                provider=PROVIDER,
                endpoint_id=model.id,
                family=infer_family(model.id),
                capabilities=list(getattr(model, "capabilities", None) or []),
                declared_limits=DECLARED_BUDGET,
                raw={
                    "owned_by": getattr(model, "owned_by", None),
                    "capabilities_reported": bool(getattr(model, "capabilities", None)),
                },
            )
            for model in listing.data
        ]
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
                max_tokens=max_output_tokens,
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
        """O intervalo, como a API compatível com a OpenAI o emite.

        O `ChoiceDelta` da SDK 2.50 declara `content`, `tool_calls`, `function_call`,
        `refusal` e `role` — e **nenhum** campo de raciocínio, ao contrário do delta da
        Groq. Alguns modelos servidos aqui devolvem raciocínio dentro do próprio
        `content`, entre marcas; separá-lo seria interpretação nossa, não campo do
        provedor, e por isso ele sai como `OUTPUT_DELTA`, que é o que ele é na origem.

        `reasoning_content` — campo que parte do catálogo da NVIDIA emite fora do
        esquema da SDK — é lido do dicionário do pedaço, e não de um atributo tipado:
        ele existe no JSON e não no modelo Pydantic. Quando não vier, não é emitido.

        O consumo é lido de `chunk.usage` quando ele vier, e a requisição não ganha
        `stream_options.include_usage` para provocá-lo: a NVIDIA não documenta esse
        parâmetro, e mandá-lo mesmo assim arrisca um 400 que derrubaria a chamada inteira
        para ganhar um número. Endpoint que não reporta consumo no intervalo fica sem a
        chave, e o ledger volta a estimar — como já fazia antes de existir stream.
        """
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
                # Antes do desvio: o pedaço que traz consumo costuma vir sem `choices`.
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
            declared_requests_per_minute=DECLARED_REQUESTS_PER_MINUTE,
            note=f"{observed.note} Orçamento {DECLARED_BUDGET['origem']}.",
        )
