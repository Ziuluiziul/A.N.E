"""Adaptador do Ollama Cloud.

Não há SDK aqui, e não é esquecimento. A documentação oficial descreve a nuvem como a
própria API da Ollama servida em `https://ollama.com/api`, com a chave em
`Authorization: Bearer` — o mesmo protocolo do host local, com autenticação. A camada
compatível com a OpenAI (`/v1/...`) só é documentada para `localhost:11434`; usá-la
contra ollama.com seria apostar em comportamento não documentado, e um cliente `httpx`
falando o protocolo descrito custa menos que essa aposta.

Duas assimetrias em relação aos outros três adaptadores. Ambas foram medidas contra a
API em 2026-08-05, não deduzidas:

1. **Listar não prova credencial.** `GET /api/tags` respondeu 200 sem header nenhum e
   200 com uma chave inválida: o catálogo da nuvem é público. Validar pela listagem
   faria o painel dizer "disponível" para uma chave que o provedor rejeita, e por isso
   `verify_credential` usa outra rota — ver o método, inclusive pelo erro que a
   primeira escolha cometeu.
2. **A descoberta custa `1 + N` chamadas, e não uma.** Em `/api/tags` da nuvem todo
   endpoint vem com `details` vazio: só nomes. Janela, arquitetura e capacidades moram
   em `/api/show`, um pedido por modelo. Aceitar esse custo não foi conforto — sem a
   janela declarada, `providers.aptitude.preference_key` ordena por `-context_window`
   e coloca todo endpoint da Ollama atrás de qualquer modelo que declare a sua, de
   modo que o AUTO nunca escolheria nenhum. O provedor existiria no painel sem poder
   receber trabalho. Nenhuma das duas rotas exige credencial nem gasta cota de
   inferência; o que elas custam é tempo de rede, e por isso correm em paralelo.

Referências: https://docs.ollama.com/cloud, https://docs.ollama.com/api/authentication,
https://docs.ollama.com/api/chat, https://docs.ollama.com/api/usage e
https://docs.ollama.com/api/errors.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from dataclasses import replace
from typing import Any

import httpx

from providers.base import (
    AdaptiveBackoff,
    GenerationResult,
    ModelInfo,
    ObservedLimits,
    ProbeResult,
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

PROVIDER = "ollama"
BASE_URL = "https://ollama.com"

# 60 s, como no NIM e não como nos 30 s de Groq e Gemini. A nuvem serve modelos de
# centenas de bilhões de parâmetros e ainda não há medição própria de latência aqui —
# apertar o teto sem tê-la mediria o timeout, não o endpoint.
TIMEOUT = httpx.Timeout(60.0, connect=5.0)

# Quantos `/api/show` correm ao mesmo tempo. Os dezoito modelos da nuvem levaram 11,4 s
# em sequência quando medidos em 2026-08-05, a ~630 ms cada. Quatro é folgado o
# bastante para encurtar isso e contido o bastante para não parecer enxurrada num
# endpoint público que ninguém nos autorizou a saturar.
SHOW_CONCURRENCY = 4

# Modelo-sentinela da verificação de credencial. Não existe, e é para não existir: o
# que se quer do pedido é que ele pare antes de resolver modelo e antes de gerar nada.
VERIFY_MODEL = "vault-autodidata-verificacao-de-credencial"


class OllamaAdapter:
    provider = PROVIDER

    def __init__(self, api_key: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=TIMEOUT,
            follow_redirects=False,
        )
        self._last_limits: ObservedLimits | None = None
        self._backoff = AdaptiveBackoff()

    # --- transporte ---------------------------------------------------------

    @staticmethod
    def _detail(response: httpx.Response) -> str:
        """A mensagem que a API pôs em `error`, ou o status cru se não houver uma."""
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict) and isinstance(body.get("error"), str):
            return body["error"]
        return f"HTTP {response.status_code}"

    @classmethod
    def _classify(cls, response: httpx.Response) -> Exception:
        """Traduz o status documentado em erro de provedor, sem inventar categoria."""
        detail = cls._detail(response)
        status = response.status_code
        if status == 401:
            return ProviderAuthError(f"credencial rejeitada pelo Ollama Cloud: {detail}")
        # 403 não é credencial recusada, e tratá-lo como tal difama a chave. Medido em
        # 2026-08-05: chave inválida devolve 401 em qualquer modelo, enquanto uma chave
        # boa devolve 403 nos modelos fora do plano — "this model requires a
        # subscription". Isso é o endpoint existir no catálogo e não atender a esta
        # conta, que é a definição de `ProviderUnavailable`. A distinção decide o que o
        # painel diz: com 403 virando `auth`, a sonda de um modelo pago faria o
        # mantenedor recadastrar uma chave que está perfeita.
        if status == 403:
            return ProviderUnavailable(f"endpoint fora do plano no Ollama Cloud: {detail}")
        if status == 429:
            retry_after = parse_retry_after(response.headers.get("retry-after"))
            return ProviderRateLimited(
                f"limite do Ollama Cloud atingido: {detail}", retry_after
            )
        # 502 é o gateway dizendo que o modelo da nuvem não foi alcançado; 404 é o
        # endpoint que não existe mais. Nos dois casos o caminho existe e não atendeu.
        if status in (404, 500, 502, 503, 504):
            return ProviderUnavailable(f"endpoint indisponível no Ollama Cloud: {detail}")
        return ProviderError(f"resposta inesperada do Ollama Cloud: {detail}")

    async def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> Any:
        """Uma chamada, com o 429 já registrado e o corpo de erro já classificado."""
        await self._backoff.wait()
        try:
            response = await self._client.request(method, path, json=payload)
        except httpx.RequestError as error:
            raise ProviderUnavailable(f"Ollama Cloud inalcançável: {error}") from error

        if response.status_code >= 400:
            classified = self._classify(response)
            if isinstance(classified, ProviderRateLimited):
                self._backoff.rate_limited(classified.retry_after_s)
                self._last_limits = replace(
                    limits_from_headers(PROVIDER, response.headers),
                    retry_after_s=classified.retry_after_s,
                )
            raise classified

        self._backoff.succeeded()
        # A Ollama não documenta headers de limite. `limits_from_headers` recolhe os
        # que existirem e diz "desconhecido" quando não vier nenhum — o que é o caso
        # observado hoje. Nada é preenchido por suposição.
        self._last_limits = limits_from_headers(PROVIDER, response.headers)
        try:
            return response.json()
        except ValueError as error:
            raise ProviderError("Ollama Cloud respondeu 200 sem JSON") from error

    # --- interface do provedor ----------------------------------------------

    async def _describe(self, endpoint_id: str) -> dict[str, Any] | None:
        """O que `/api/show` declara sobre um modelo, ou `None` se ele não respondeu.

        Um modelo que falha aqui não derruba a descoberta inteira: ele entra com o que
        `/api/tags` deu e a janela fica ausente, que é exatamente o que se sabe dele.
        Credencial recusada e 429 continuam subindo — os dois dizem algo sobre a
        execução toda, e engoli-los transformaria um problema de conta em dezoito
        janelas misteriosamente vazias.
        """
        try:
            body = await self._request("POST", "/api/show", {"model": endpoint_id})
        except (ProviderAuthError, ProviderRateLimited):
            raise
        except ProviderError:
            return None
        return body if isinstance(body, dict) else None

    async def list_models(self) -> list[ModelInfo]:
        """`GET /api/tags` para os nomes, `POST /api/show` para o que cada um declara."""
        body = await self._request("GET", "/api/tags")
        entries = body.get("models") if isinstance(body, dict) else None
        if not isinstance(entries, list):
            raise ProviderError("catálogo do Ollama Cloud sem lista de modelos")

        listados: list[tuple[str, dict[str, Any]]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            endpoint_id = entry.get("model") or entry.get("name")
            if isinstance(endpoint_id, str) and endpoint_id:
                listados.append((endpoint_id, entry))

        limite = asyncio.Semaphore(SHOW_CONCURRENCY)

        async def descrever(endpoint_id: str) -> dict[str, Any] | None:
            async with limite:
                return await self._describe(endpoint_id)

        descricoes = await asyncio.gather(*(descrever(nome) for nome, _ in listados))

        models = [
            _model_info(endpoint_id, entry, descricao)
            for (endpoint_id, entry), descricao in zip(listados, descricoes, strict=True)
        ]
        return sorted(models, key=lambda model: model.endpoint_id)

    async def verify_credential(self) -> str:
        """`POST /api/chat` sem mensagens: passa pelo portão da credencial e para ali.

        A primeira escolha foi `GET /api/ps`, e estava errada por um motivo que vale
        deixar escrito. Dela eu havia medido só o lado negativo — 401 sem chave e 401
        com chave inválida — e tratei um 200 hipotético como prova de validade. Com uma
        chave real ela devolve 401 também: na nuvem não existe instância rodando para
        listar. O painel passou a chamar de inválida uma credencial que funciona, que é
        o mesmo defeito de antes com o sinal trocado. Medir só o lado que se consegue
        medir e concluir sobre o outro não é evidência, é suposição com número.

        Os dois lados desta rota foram medidos em 2026-08-05: chave válida devolve 200
        com `done_reason: load`, sem `eval_count`, sem texto e sem resolver o modelo;
        chave recusada devolve 401. A lista de mensagens vazia é o que faz a chamada
        parar antes de gerar qualquer coisa — o custo é uma requisição, não um token.
        """
        await self._request(
            "POST",
            "/api/chat",
            {"model": VERIFY_MODEL, "messages": [], "stream": False},
        )
        return (
            "credencial aceita em /api/chat, sem gerar tokens; "
            "a listagem de modelos é pública e não a prova"
        )

    async def probe_model(self, endpoint_id: str) -> ProbeResult:
        return await probe_via_generate(self, endpoint_id)

    async def generate(
        self, endpoint_id: str, prompt: str, *, max_output_tokens: int = 256
    ) -> GenerationResult:
        started = time.perf_counter()
        body = await self._request(
            "POST",
            "/api/chat",
            {
                "model": endpoint_id,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                # O teto de saída da Ollama é `num_predict`, dentro de `options`; não há
                # `max_tokens` nesta API.
                "options": {"num_predict": max_output_tokens},
            },
        )
        elapsed = int((time.perf_counter() - started) * 1000)
        message = body.get("message") if isinstance(body, dict) else None
        message = message if isinstance(message, dict) else {}
        content = message.get("content")
        # A deliberação vem em `thinking`, num campo separado de `content`. Ela não
        # entra no texto — o orquestrador tem `strip_reasoning` justamente para tirá-la
        # de onde ela aparece —, mas o tamanho dela entra no uso, porque `num_predict`
        # é gasto pelos dois. Dezesseis dos dezoito modelos da nuvem declaram
        # `thinking`, e um 200 sem texto sob orçamento apertado se explica por aqui:
        # sem esta contagem, o registro diria apenas "alcançável" e não diria por quê.
        thinking = message.get("thinking")
        usage = _usage(body)
        if isinstance(thinking, str) and thinking:
            usage["thinking_chars"] = len(thinking)
        return GenerationResult(
            provider=PROVIDER,
            endpoint_id=endpoint_id,
            text=content if isinstance(content, str) else "",
            usage=usage,
            latency_ms=elapsed,
        )

    async def stream_generate(
        self, endpoint_id: str, prompt: str, *, max_output_tokens: int = 256
    ) -> AsyncIterator[CognitiveEvent]:
        """O intervalo, como a Ollama o emite: NDJSON com `content` e `thinking`.

        Este é o caso em que o raciocínio **já chegava e era jogado fora**. Em
        `generate`, `message.thinking` é lido e só o comprimento dele sobrevive, em
        `usage["thinking_chars"]`: o registro dizia quanto o modelo pensou e nunca o quê.
        Dezesseis dos dezoito modelos da nuvem declaram `thinking`.

        Com `stream: true` a API emite um objeto JSON por linha, cada um com um pedaço em
        `message.content` e/ou `message.thinking`, e um último com `done: true`.
        """
        await self._backoff.wait()
        sequencia = 0
        pensamento_chars = 0
        corpo = {
            "model": endpoint_id,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "options": {"num_predict": max_output_tokens},
        }
        try:
            async with self._client.stream("POST", "/api/chat", json=corpo) as response:
                if response.status_code >= 400:
                    await response.aread()
                    classified = self._classify(response)
                    if isinstance(classified, ProviderRateLimited):
                        self._backoff.rate_limited(classified.retry_after_s)
                    raise classified
                async for linha in response.aiter_lines():
                    if not linha.strip():
                        continue
                    try:
                        quadro = json.loads(linha)
                    except ValueError:
                        # Linha que não é JSON não é evento: ignorá-la é melhor que
                        # inventar um tipo para ela.
                        continue
                    if not isinstance(quadro, dict):
                        continue
                    mensagem = quadro.get("message")
                    mensagem = mensagem if isinstance(mensagem, dict) else {}
                    for campo, tipo in (
                        ("thinking", CognitiveKind.REASONING),
                        ("content", CognitiveKind.OUTPUT_DELTA),
                    ):
                        texto = mensagem.get(campo)
                        if not isinstance(texto, str) or texto == "":
                            continue
                        if campo == "thinking":
                            pensamento_chars += len(texto)
                        sequencia += 1
                        yield CognitiveEvent(
                            provider=PROVIDER,
                            endpoint_id=endpoint_id,
                            kind=tipo,
                            text=texto,
                            raw_field=f"message.{campo}",
                            sequence=sequencia,
                        )
                    if quadro.get("done") is True:
                        sequencia += 1
                        # O quadro final do NDJSON tem a mesma forma do corpo de
                        # `stream: false`: as contagens vêm nos mesmos campos, e por isso
                        # o consumo aqui é o mesmo que `generate` reportaria. O que ali é
                        # medido depois, aqui é somado à medida que os pedaços chegam.
                        uso = _usage(quadro)
                        if pensamento_chars:
                            uso["thinking_chars"] = pensamento_chars
                        yield CognitiveEvent(
                            provider=PROVIDER,
                            endpoint_id=endpoint_id,
                            kind=CognitiveKind.FINAL,
                            raw_field="done",
                            sequence=sequencia,
                            detail={
                                "done_reason": str(quadro.get("done_reason") or ""),
                                "usage": uso,
                            },
                        )
        except httpx.RequestError as error:
            raise ProviderUnavailable(f"Ollama Cloud inalcançável: {error}") from error
        self._backoff.succeeded()

    def get_observed_limits(self) -> ObservedLimits:
        if self._last_limits is not None:
            return self._last_limits
        return ObservedLimits(
            provider=PROVIDER,
            source="desconhecido",
            note="Nenhuma resposta observada ainda nesta sessão.",
        )


# Campos de uso que a API documenta. Duração em nanossegundos, contagem em tokens; os
# nomes ficam como vieram para que ninguém os confunda com o vocabulário da OpenAI.
_USAGE_FIELDS = (
    "total_duration",
    "load_duration",
    "prompt_eval_count",
    "prompt_eval_duration",
    "eval_count",
    "eval_duration",
    "done_reason",
)


def _usage(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        return {}
    return {field: body[field] for field in _USAGE_FIELDS if field in body}


def _context_length(model_info: object) -> int | None:
    """A janela chega chaveada pela arquitetura, não por um nome fixo.

    `gptoss.context_length`, `qwen3.5.context_length`, `deepseek4.context_length`: o
    prefixo é o da arquitetura do modelo, então procurar a chave exata `context_length`
    não acharia nada. O sufixo é o que se pode afirmar sobre o formato.
    """
    if not isinstance(model_info, dict):
        return None
    for key, value in model_info.items():
        if not (isinstance(key, str) and key.endswith("context_length")):
            continue
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def _capabilities(described: dict[str, Any] | None) -> list[str]:
    """As capacidades declaradas, ordenadas.

    A API devolve a mesma lista em ordens diferentes entre chamadas. Ordenar aqui faz
    com que dois retratos da descoberta só difiram quando o provedor mudou de fato —
    do contrário, comparar duas datas acusaria mudança onde houve só embaralhamento.
    """
    if described is None:
        return []
    declared = described.get("capabilities")
    if not isinstance(declared, list):
        return []
    return sorted(item for item in declared if isinstance(item, str) and item)


def _model_info(
    endpoint_id: str,
    entry: dict[str, Any],
    described: dict[str, Any] | None,
) -> ModelInfo:
    """Junta o que a listagem deu com o que `/api/show` declarou sobre o modelo."""
    details = described.get("details") if isinstance(described, dict) else None
    details = details if isinstance(details, dict) else {}
    # A família declarada tem precedência sobre a lida do nome, e a diferença é real:
    # o catálogo diz `gptoss` onde o identificador sugere `gpt`, e `nemotron_h_moe`
    # onde ele sugere `nemotron`. Nem todo modelo a declara — `nemotron-3-ultra` veio
    # com o campo vazio —, e aí o palpite pelo nome volta a ser o melhor disponível.
    declared_family = details.get("family")
    family = (
        declared_family
        if isinstance(declared_family, str) and declared_family
        else infer_family(endpoint_id)
    )
    return ModelInfo(
        provider=PROVIDER,
        endpoint_id=endpoint_id,
        family=family,
        capabilities=_capabilities(described),
        context_window=_context_length(
            described.get("model_info") if isinstance(described, dict) else None
        ),
        # A API não declara teto de saída por modelo; quem o define é `num_predict`,
        # que é escolha de quem chama e não propriedade do endpoint.
        max_output_tokens=None,
        declared_limits={},
        raw={
            "digest": entry.get("digest"),
            "modified_at": entry.get("modified_at"),
            "size": entry.get("size"),
            "parameter_size": details.get("parameter_size"),
            "quantization_level": details.get("quantization_level"),
            # Distingue "o modelo não declara" de "ninguém perguntou": sem esta marca,
            # uma janela ausente por falha de `/api/show` seria lida como janela que o
            # provedor não informa.
            "described": described is not None,
        },
    )
