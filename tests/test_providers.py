"""Os adaptadores não são chamados aqui: nenhum teste gasta cota nem exige rede.

O que se testa é a parte que decide como um número é interpretado — porque é aí que
um limite suposto poderia se disfarçar de limite observado.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Callable
from types import SimpleNamespace
from typing import Any, cast

import httpx
import orjson
import pytest
from pydantic import SecretStr

from providers import _plain_secret, build_adapters, limits_from_headers
from providers.aptitude import classify
from providers.base import (
    PROBE_MAX_OUTPUT_TOKENS,
    AdaptiveBackoff,
    GenerationResult,
    ObservedLimits,
    ProviderAccountExhausted,
    ProviderAdapter,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimited,
    ProviderUnavailable,
    infer_family,
    parse_retry_after,
    probe_via_generate,
)
from providers.cognitive import CognitiveKind
from providers.google.adapter import GoogleAdapter
from providers.groq.adapter import GroqAdapter
from providers.nous.adapter import (
    BASE_URL,
    SENTINEL,
    NousAdapter,
)
from providers.nous.adapter import (
    DECLARED_BUDGET as NOUS_BUDGET,
)
from providers.nvidia.adapter import DECLARED_BUDGET, NvidiaAdapter
from providers.ollama.adapter import VERIFY_MODEL, OllamaAdapter
from providers.openrouter.adapter import (
    DECLARED_FREE_BUDGET,
    OpenRouterAdapter,
)

ADAPTERS = (
    GoogleAdapter,
    GroqAdapter,
    NvidiaAdapter,
    OllamaAdapter,
    NousAdapter,
    OpenRouterAdapter,
)
OPERACOES = (
    "list_models",
    "probe_model",
    "generate",
    "stream_generate",
    "verify_credential",
    "get_observed_limits",
)


def test_os_adaptadores_cumprem_a_interface() -> None:
    """`issubclass` não serve: `ProviderAdapter` tem `provider`, que não é método."""
    for adapter in ADAPTERS:
        assert isinstance(adapter.provider, str)
        for operacao in OPERACOES:
            assert callable(getattr(adapter, operacao)), f"{adapter.__name__}.{operacao}"


def test_provedores_tem_identidade_distinta() -> None:
    assert {adapter.provider for adapter in ADAPTERS} == {
        "google",
        "groq",
        "nvidia",
        "ollama",
        "nous",
        "openrouter",
    }


def test_sem_credencial_nao_se_constroi_adaptador() -> None:
    class SemChaves:
        gemini_api_key = None
        groq_api_key = None
        nvidia_api_key = None
        ollama_api_key = None
        nous_api_key = None
        openrouter_api_key = None

    assert build_adapters(SemChaves()) == {}


async def test_chave_openrouter_constroi_so_o_quinto_adaptador() -> None:
    class SomenteOpenRouter:
        gemini_api_key = None
        groq_api_key = None
        nvidia_api_key = None
        ollama_api_key = None
        openrouter_api_key = SecretStr("sk-or-v1-sintetica")

    adapters = build_adapters(SomenteOpenRouter())

    assert set(adapters) == {"openrouter"}
    adapter = cast(OpenRouterAdapter, adapters["openrouter"])
    assert (  # noqa: SLF001
        adapter._client.headers["authorization"] == "Bearer sk-or-v1-sintetica"
    )
    await adapter._client.aclose()  # noqa: SLF001


async def test_build_adapters_propaga_opt_in_openrouter_sem_teto() -> None:
    class OpenRouterComOptIn:
        gemini_api_key = None
        groq_api_key = None
        nvidia_api_key = None
        ollama_api_key = None
        openrouter_api_key = SecretStr("sk-or-v1-sintetica")
        openrouter_allow_uncapped_free_tier = True

    adapter = cast(OpenRouterAdapter, build_adapters(OpenRouterComOptIn())["openrouter"])

    assert adapter._allow_uncapped_free_tier is True  # noqa: SLF001
    await adapter._client.aclose()  # noqa: SLF001


def test_familia_sai_do_id_do_endpoint() -> None:
    assert infer_family("meta/llama-3.3-70b-instruct") == "llama"
    assert infer_family("models/gemini-2.5-flash") == "gemini"
    assert infer_family("qwen/qwen3-235b") == "qwen3"


def test_etiqueta_da_ollama_nao_entra_no_nome_da_familia() -> None:
    """`:` abre o tamanho, não a família: sem separá-lo cada etiqueta viraria um grupo."""
    assert infer_family("gemma4:31b") == "gemma4"
    assert infer_family("qwen3.5:397b") == "qwen3"
    assert infer_family("deepseek-v4-flash:0731") == "deepseek"


def test_headers_dizem_o_que_sobrou_sem_inventar_janela() -> None:
    limits = limits_from_headers(
        "groq",
        {
            "x-ratelimit-limit-requests": "1000",
            "x-ratelimit-limit-tokens": "18000",
            "x-ratelimit-remaining-requests": "998",
            "x-ratelimit-remaining-tokens": "17500",
            "x-ratelimit-reset-requests": "2m59s",
            "retry-after": "12",
            "content-type": "application/json",
        },
    )
    assert limits.source == "headers"
    assert limits.requests_remaining == 998
    assert limits.tokens_remaining == 17500
    assert limits.retry_after_s == 12.0
    # A Groq documenta requisições em RPD e tokens em TPM.
    assert limits.requests_per_minute is None
    assert limits.requests_per_day == 1000
    assert limits.tokens_per_minute == 18000
    assert limits.raw["x-ratelimit-limit-requests"] == "1000"
    assert limits.raw["x-ratelimit-reset-requests"] == "2m59s"
    assert "content-type" not in limits.raw


def test_resposta_sem_headers_nao_finge_conhecer_limite() -> None:
    limits = limits_from_headers("nvidia", {"content-type": "application/json"})
    assert limits.source == "desconhecido"
    assert limits.requests_remaining is None


def test_retry_after_invalido_nao_vira_numero() -> None:
    assert parse_retry_after(None) is None
    assert parse_retry_after("") is None
    assert parse_retry_after("Wed, 21 Oct 2026 07:28:00 GMT") is None
    assert parse_retry_after("3.5") == 3.5


def test_groq_declara_rpm_porque_o_header_nao_traz() -> None:
    """Sem RPM declarado a cota só vê RPD/TPM e estoura 30 req/min."""
    from providers.groq.limits import ORIGEM, SHUT_DOWN, declared_limits, parse_reset_duration
    from vault.work.quotas import EndpointLimits

    teto = declared_limits("openai/gpt-oss-20b")
    assert teto["requests_per_minute"] == 30
    assert teto["requests_per_day"] == 1_000
    assert teto["tokens_per_minute"] == 8_000
    assert ORIGEM in str(teto["origem"])
    assert declared_limits("llama-3.3-70b-versatile") == {}
    assert "llama-3.3-70b-versatile" in SHUT_DOWN
    assert parse_reset_duration("7.66s") == pytest.approx(7.66)
    assert parse_reset_duration("2m59.56s") == pytest.approx(179.56)
    assert parse_reset_duration("2m59s") == pytest.approx(179.0)
    assert parse_reset_duration("não é duração") is None

    lido = EndpointLimits.from_observed({}, teto)
    assert lido.requests_per_minute == 30
    assert lido.requests_per_day == 1_000
    assert lido.tokens_per_minute == 8_000


def test_hold_atrasa_sem_contar_falha() -> None:
    espera = AdaptiveBackoff(max_delay_s=60.0)
    espera.hold(0.05)
    inicio = time.monotonic()
    import asyncio

    asyncio.run(espera.wait())
    assert time.monotonic() - inicio >= 0.04


def test_orcamento_da_nvidia_declara_a_origem() -> None:
    """40 RPM é informação do mantenedor, não medição — e o código precisa dizê-lo."""
    assert DECLARED_BUDGET["requests_per_minute_aggregate"] == 40
    assert "confirmado pelo mantenedor" in str(DECLARED_BUDGET["origem"])


def test_google_declara_teto_por_modelo_do_painel() -> None:
    """Flash Lite tem 500 RPD; Flash tem 20. Misturar os dois esgota o Flash."""
    from providers.google.limits import ORIGEM, declared_limits
    from vault.work.quotas import EndpointLimits

    lite = declared_limits("gemini-3.5-flash-lite")
    flash = declared_limits("gemini-3.6-flash")
    assert lite["requests_per_minute"] == 15
    assert lite["requests_per_day"] == 500
    assert flash["requests_per_minute"] == 5
    assert flash["requests_per_day"] == 20
    assert declared_limits("gemini-3.5-flash-lite") != declared_limits("gemini-3.5-flash")
    assert declared_limits("gemini-3.1-flash-lite-image") == {}
    assert ORIGEM in str(lite["origem"])
    lido = EndpointLimits.from_observed({}, lite)
    assert lido.requests_per_minute == 15
    assert lido.requests_per_day == 500


def test_chave_so_vira_texto_no_limite_do_sdk() -> None:
    secret = SecretStr("nao-exibir")
    assert "nao-exibir" not in repr(secret)
    assert _plain_secret(secret) == "nao-exibir"


def test_sdks_nao_fazem_retries_escondidos() -> None:
    google = GoogleAdapter("dummy")
    groq = GroqAdapter("dummy")
    nvidia = NvidiaAdapter("dummy")
    retry_options = google._client._api_client._http_options.retry_options  # noqa: SLF001
    assert retry_options is not None and retry_options.attempts == 1
    assert groq._client.max_retries == 0  # noqa: SLF001
    assert nvidia._client.max_retries == 0  # noqa: SLF001


def test_backoff_prefere_retry_after_sem_criar_retry() -> None:
    backoff = AdaptiveBackoff()
    backoff.rate_limited(7.0)
    backoff.succeeded()


async def test_sonda_mede_latencia_tambem_na_falha() -> None:
    class Adapter:
        provider = "fake"

        async def generate(
            self,
            _endpoint_id: str,
            _prompt: str,
            *,
            max_output_tokens: int = 256,
        ) -> object:
            assert max_output_tokens == PROBE_MAX_OUTPUT_TOKENS
            raise ProviderRateLimited("limite", 7.0)

    result = await probe_via_generate(cast(ProviderAdapter, Adapter()), "modelo")
    assert result.outcome == "rate_limited"
    assert result.latency_ms is not None
    assert result.latency_ms >= 0


async def test_sonda_separa_credito_esgotado_de_limite_de_taxa() -> None:
    class Adapter:
        provider = "google"

        async def generate(
            self,
            _endpoint_id: str,
            _prompt: str,
            *,
            max_output_tokens: int = 256,
        ) -> object:
            raise ProviderAccountExhausted("crédito da conta Google esgotado")

    result = await probe_via_generate(cast(ProviderAdapter, Adapter()), "modelo")
    assert result.outcome == "account_exhausted"


def test_nvidia_preserva_orcamento_declarado_sem_header() -> None:
    adapter = NvidiaAdapter("dummy")
    adapter._last_limits = ObservedLimits(  # noqa: SLF001
        provider="nvidia",
        source="desconhecido",
        note="sem headers",
    )
    limits = adapter.get_observed_limits()
    assert limits.source == "desconhecido"
    assert limits.declared_requests_per_minute == 40
    assert "confirmado pelo mantenedor" in limits.note


def test_nvidia_classifica_410_como_indisponivel() -> None:
    class Falha(Exception):
        status_code = 410

    classified = NvidiaAdapter._classify(Falha("Gone: end of life"))  # noqa: SLF001
    assert isinstance(classified, ProviderUnavailable)


def test_google_preserva_retry_after_e_classifica_5xx() -> None:
    class Response:
        status_code = 429
        headers = {"retry-after": "7"}

    class Falha(Exception):
        code = 429
        response = Response()

    limited = GoogleAdapter._classify(Falha("quota"))  # noqa: SLF001
    assert isinstance(limited, ProviderRateLimited)
    assert limited.retry_after_s == 7.0

    Falha.code = 429
    Falha.response.status_code = 429
    exhausted = GoogleAdapter._classify(  # noqa: SLF001
        Falha("Your prepayment credits are depleted")
    )
    assert isinstance(exhausted, ProviderAccountExhausted)
    assert not isinstance(exhausted, ProviderRateLimited)

    Falha.code = 502
    Falha.response.status_code = 502
    unavailable = GoogleAdapter._classify(Falha("gateway"))  # noqa: SLF001
    assert isinstance(unavailable, ProviderUnavailable)


async def test_google_lista_so_a_primeira_pagina_sem_requisicao_escondida() -> None:
    model = SimpleNamespace(
        name="models/gemini-teste",
        supported_actions=["generateContent"],
        input_token_limit=100,
        output_token_limit=20,
        display_name="Teste",
    )

    class Pager:
        page = [model]
        config = {"page_token": None}

        def __aiter__(self) -> object:  # pragma: no cover
            raise AssertionError("iterou o pager e poderia buscar outra página")

    class Models:
        calls = 0

        async def list(self, *, config: Any) -> Pager:
            self.calls += 1
            assert config.page_size == 1000
            return Pager()

    models_api = Models()
    adapter = GoogleAdapter("dummy")
    adapter._client = SimpleNamespace(  # type: ignore[assignment]  # noqa: SLF001
        aio=SimpleNamespace(models=models_api)
    )
    listing = await adapter.list_models()
    assert models_api.calls == 1
    assert [item.endpoint_id for item in listing] == ["gemini-teste"]


async def test_google_recusa_catalogo_maior_que_uma_pagina() -> None:
    class Pager:
        page: list[object] = []
        config = {"page_token": "continua"}

    class Models:
        async def list(self, *, config: Any) -> Pager:
            assert config.page_size == 1000
            return Pager()

    adapter = GoogleAdapter("dummy")
    adapter._client = SimpleNamespace(  # type: ignore[assignment]  # noqa: SLF001
        aio=SimpleNamespace(models=Models())
    )
    with pytest.raises(ProviderError, match="excede a primeira página"):
        await adapter.list_models()


def test_retry_after_absurdo_nao_pendura_o_processo() -> None:
    """Reporta a espera íntegra, mas nunca bloqueia além do teto.

    Um `retry-after: 3600` vindo do servidor viraria uma hora de `asyncio.sleep`
    dentro do comando. O número segue no relatório; o bloqueio, não.
    """
    backoff = AdaptiveBackoff(max_delay_s=60.0)
    backoff.rate_limited(3600.0)
    assert backoff._not_before - time.monotonic() <= 60.0  # noqa: SLF001


async def test_resposta_sem_texto_e_alcance_nao_sucesso() -> None:
    """200 vazio prova que o caminho existe; não prova que o endpoint serve."""

    class Adapter:
        provider = "fake"

        def __init__(self, text: str) -> None:
            self.text = text

        async def generate(
            self, endpoint_id: str, prompt: str, *, max_output_tokens: int = 256
        ) -> GenerationResult:
            return GenerationResult(
                provider="fake", endpoint_id=endpoint_id, text=self.text
            )

    vazio = await probe_via_generate(cast(ProviderAdapter, Adapter("")), "modelo")
    assert vazio.outcome == "reachable"
    assert vazio.reachable and not vazio.ok
    assert str(PROBE_MAX_OUTPUT_TOKENS) in vazio.detail

    cheio = await probe_via_generate(cast(ProviderAdapter, Adapter("ok")), "modelo")
    assert cheio.outcome == "ok"
    assert cheio.reachable and cheio.ok


def test_nim_espera_mais_que_os_outros_dois_provedores() -> None:
    """O GLM respondeu em 25,2s e 25,8s antes de estourar em 30,8s.

    Sendo o único endpoint nvidia usável, derrubá-lo por latência de fila custa a
    diversidade de provedor que o quórum exige — e o painel inteiro junto.
    """
    nvidia = cast(httpx.Timeout, NvidiaAdapter("dummy")._client.timeout)  # noqa: SLF001
    groq = cast(httpx.Timeout, GroqAdapter("dummy")._client.timeout)  # noqa: SLF001
    assert nvidia.read == 60.0
    assert groq.read == 30.0


def test_google_espera_o_mesmo_que_o_nim() -> None:
    """3.7 Flash e Gemma 4 estouraram 504 em ~34 s com timeout de 30 s."""
    from providers.google.adapter import HTTP_TIMEOUT_MS, GoogleAdapter

    assert HTTP_TIMEOUT_MS == 60_000
    timeout = GoogleAdapter("dummy")._client._api_client._http_options.timeout  # noqa: SLF001
    assert timeout == HTTP_TIMEOUT_MS


# --- Ollama Cloud ------------------------------------------------------------
#
# O adaptador é o único que não tem SDK, então o transporte é dele e precisa de teste
# próprio. `MockTransport` responde no lugar da rede: nenhum destes testes sai da
# máquina nem gasta cota.


def ollama_com(
    rota: dict[str, httpx.Response | Callable[[httpx.Request], httpx.Response]],
) -> tuple[OllamaAdapter, list[httpx.Request]]:
    """Adaptador com transporte fingido, e o registro do que ele pediu."""
    pedidos: list[httpx.Request] = []

    def responder(request: httpx.Request) -> httpx.Response:
        pedidos.append(request)
        resposta = rota.get(request.url.path)
        assert resposta is not None, f"rota não esperada: {request.url.path}"
        return resposta(request) if callable(resposta) else resposta

    adapter = OllamaAdapter("dummy")
    adapter._client = httpx.AsyncClient(  # noqa: SLF001
        base_url=adapter._client.base_url,  # noqa: SLF001
        headers=adapter._client.headers,  # noqa: SLF001
        transport=httpx.MockTransport(responder),
    )
    return adapter, pedidos


TAGS_DA_NUVEM = {
    "models": [
        {
            "name": "qwen3.5:397b",
            "model": "qwen3.5:397b",
            "modified_at": "2026-06-16T08:00:00-07:00",
            "size": 0,
            "digest": "f553240f6dc4",
            "details": {"family": "", "parameter_size": "", "quantization_level": ""},
        },
        {"name": "gpt-oss:120b", "model": "gpt-oss:120b", "digest": "d98fe6ba01e6"},
        {"sem": "identificador"},
    ]
}

SHOW_POR_MODELO = {
    "qwen3.5:397b": {
        "capabilities": ["thinking", "completion", "tools", "vision"],
        "details": {"family": "qwen3.5", "parameter_size": "397B"},
        "model_info": {"qwen3.5.context_length": 262144, "qwen3.5.block_count": 94},
    },
    "gpt-oss:120b": {
        "capabilities": ["completion", "tools", "thinking"],
        "details": {"family": "gptoss", "parameter_size": "116829156672"},
        "model_info": {"gptoss.context_length": 131072},
    },
}


def show_do_corpo(request: httpx.Request) -> httpx.Response:
    modelo = orjson.loads(request.content)["model"]
    return httpx.Response(200, json=SHOW_POR_MODELO[modelo])


async def test_ollama_completa_a_listagem_com_o_que_show_declara() -> None:
    """`/api/tags` só dá nomes; janela, família e capacidades vêm de `/api/show`."""
    adapter, pedidos = ollama_com(
        {"/api/tags": httpx.Response(200, json=TAGS_DA_NUVEM), "/api/show": show_do_corpo}
    )
    modelos = await adapter.list_models()

    assert [item.endpoint_id for item in modelos] == ["gpt-oss:120b", "qwen3.5:397b"]
    assert [item.context_window for item in modelos] == [131072, 262144]
    # A família declarada vence a lida do nome: `gptoss`, e não o `gpt` do palpite.
    assert [item.family for item in modelos] == ["gptoss", "qwen3.5"]
    assert modelos[0].capabilities == ["completion", "thinking", "tools"]
    assert all(item.raw["described"] is True for item in modelos)
    assert all(item.declared_limits == {} for item in modelos)
    assert all(item.max_output_tokens is None for item in modelos)
    assert pedidos[0].headers["authorization"] == "Bearer dummy"
    assert sorted(p.url.path for p in pedidos) == ["/api/show", "/api/show", "/api/tags"]


async def test_ollama_classifica_como_elegivel_o_que_declara_completion() -> None:
    """Vocabulário da Ollama, não do Google: `completion` é o `generateContent` dela.

    Enquanto `classify` lia só `generateContent`, os dezoito modelos da nuvem viravam
    `retrieval` inelegível — o AUTO não teria escolhido nenhum deles nunca.
    """
    adapter, _ = ollama_com(
        {"/api/tags": httpx.Response(200, json=TAGS_DA_NUVEM), "/api/show": show_do_corpo}
    )
    modelos = await adapter.list_models()
    aptidoes = [classify(modelo) for modelo in modelos]

    assert all(aptidao.eligible for aptidao in aptidoes)
    assert all(aptidao.purpose == "general" for aptidao in aptidoes)
    assert all(aptidao.modality == "text" for aptidao in aptidoes)


async def test_ollama_sem_show_mantem_o_modelo_e_declara_a_ausencia() -> None:
    """Um `/api/show` que falha tira a janela daquele modelo, não a descoberta inteira."""
    adapter, _ = ollama_com(
        {
            "/api/tags": httpx.Response(200, json=TAGS_DA_NUVEM),
            "/api/show": httpx.Response(404, json={"error": "model not found"}),
        }
    )
    modelos = await adapter.list_models()

    assert len(modelos) == 2
    assert all(item.context_window is None for item in modelos)
    assert all(item.raw["described"] is False for item in modelos)
    # Sem descrição, a família volta ao palpite pelo nome.
    assert [item.family for item in modelos] == ["gpt", "qwen3"]


async def test_ollama_nao_engole_credencial_recusada_no_show() -> None:
    """404 num modelo é local; 401 é da conta e não pode virar dezoito janelas vazias."""
    adapter, _ = ollama_com(
        {
            "/api/tags": httpx.Response(200, json=TAGS_DA_NUVEM),
            "/api/show": httpx.Response(401, json={"error": "unauthorized"}),
        }
    )
    with pytest.raises(ProviderAuthError):
        await adapter.list_models()


async def test_ollama_valida_credencial_sem_listar_e_sem_gerar() -> None:
    """`/api/tags` responde 200 para qualquer chave; a prova é um `/api/chat` sem mensagens.

    O pedido carrega um modelo-sentinela e nenhuma mensagem: a nuvem para em
    `done_reason: load`, sem `eval_count`, antes de resolver modelo e antes de gerar.
    """
    adapter, pedidos = ollama_com(
        {
            "/api/tags": httpx.Response(200, json={"models": []}),
            "/api/chat": httpx.Response(
                200,
                json={"message": {"role": "assistant", "content": ""}, "done_reason": "load"},
            ),
        }
    )
    detalhe = await adapter.verify_credential()

    assert [pedido.url.path for pedido in pedidos] == ["/api/chat"]
    enviado = orjson.loads(pedidos[0].content)
    assert enviado["messages"] == []
    assert enviado["model"] == VERIFY_MODEL
    assert "sem gerar tokens" in detalhe


async def test_ollama_recusada_e_credencial_invalida_nao_erro_generico() -> None:
    adapter, _ = ollama_com({"/api/chat": httpx.Response(401, json={"error": "Unauthorized"})})
    with pytest.raises(ProviderAuthError, match="Unauthorized"):
        await adapter.verify_credential()


async def test_ollama_gera_com_num_predict_e_le_o_uso_documentado() -> None:
    """A API da Ollama não tem `max_tokens`: o teto de saída é `options.num_predict`."""
    corpo = {
        "model": "gemma4:31b",
        "message": {"role": "assistant", "content": "ok"},
        "done_reason": "stop",
        "total_duration": 174560334,
        "prompt_eval_count": 11,
        "eval_count": 18,
        "campo_que_nao_documentado": 1,
    }
    adapter, pedidos = ollama_com({"/api/chat": httpx.Response(200, json=corpo)})
    resultado = await adapter.generate("gemma4:31b", "diga ok", max_output_tokens=32)

    enviado = orjson.loads(pedidos[0].content)
    assert enviado["options"]["num_predict"] == 32
    assert enviado["stream"] is False
    assert "max_tokens" not in enviado
    assert resultado.text == "ok"
    assert resultado.usage["eval_count"] == 18
    assert resultado.usage["prompt_eval_count"] == 11
    assert "campo_que_nao_documentado" not in resultado.usage
    assert "thinking_chars" not in resultado.usage


async def test_ollama_conta_a_deliberacao_sem_deixa_la_virar_texto() -> None:
    """200 sem texto num modelo que pensa tem causa: o orçamento foi para `thinking`."""
    corpo = {
        "model": "gpt-oss:120b",
        "message": {"role": "assistant", "content": "", "thinking": "deixa eu ver..."},
        "done_reason": "length",
        "eval_count": 512,
    }
    adapter, _ = ollama_com({"/api/chat": httpx.Response(200, json=corpo)})
    resultado = await adapter.generate("gpt-oss:120b", "diga ok", max_output_tokens=512)

    assert resultado.text == ""
    assert resultado.usage["thinking_chars"] == len("deixa eu ver...")
    assert "deixa eu ver" not in resultado.text


async def test_ollama_traduz_os_status_que_a_documentacao_lista() -> None:
    """429 preserva o `retry-after` do servidor; 502 é gateway sem modelo, não erro nosso."""
    limite = httpx.Response(429, headers={"retry-after": "9"}, json={"error": "limite"})
    adapter, _ = ollama_com({"/api/chat": limite})
    with pytest.raises(ProviderRateLimited) as limitado:
        await adapter.generate("gemma4:31b", "oi")
    assert limitado.value.retry_after_s == 9.0
    assert adapter.get_observed_limits().retry_after_s == 9.0

    adapter, _ = ollama_com({"/api/chat": httpx.Response(502, json={"error": "gateway"})})
    with pytest.raises(ProviderUnavailable, match="gateway"):
        await adapter.generate("gemma4:31b", "oi")


async def test_ollama_modelo_fora_do_plano_nao_difama_a_credencial() -> None:
    """403 é o endpoint não atender a esta conta; 401 é a chave não valer.

    Medido em 2026-08-05: com chave boa, `deepseek-v4-flash` devolve 403 e
    `gpt-oss:20b` gera. Se 403 virasse `auth`, o painel mandaria recadastrar uma
    credencial perfeita por causa de um modelo pago.
    """
    pago = httpx.Response(403, json={"error": "this model requires a subscription"})
    adapter, _ = ollama_com({"/api/chat": pago})
    with pytest.raises(ProviderUnavailable, match="subscription"):
        await adapter.generate("deepseek-v4-flash", "oi")

    recusada = httpx.Response(401, json={"error": "Unauthorized"})
    adapter, _ = ollama_com({"/api/chat": recusada})
    with pytest.raises(ProviderAuthError):
        await adapter.generate("deepseek-v4-flash", "oi")


async def test_ollama_sem_headers_de_limite_nao_finge_conhecer_cota() -> None:
    """A Ollama não documenta `x-ratelimit-*`. O silêncio fica registrado como silêncio."""
    adapter, _ = ollama_com({"/api/tags": httpx.Response(200, json={"models": []})})
    await adapter.list_models()
    limites = adapter.get_observed_limits()

    assert limites.source == "desconhecido"
    assert limites.requests_per_minute is None
    assert limites.tokens_remaining is None


# --- OpenRouter ---------------------------------------------------------------


def openrouter_com(
    responder: Callable[[httpx.Request], httpx.Response],
    *,
    zero_spend_verified: bool = True,
    allow_uncapped_free_tier: bool = False,
) -> tuple[OpenRouterAdapter, list[httpx.Request]]:
    """OpenRouter com transporte local; nenhuma chave ou chamada sai da máquina."""
    pedidos: list[httpx.Request] = []

    def registrar(request: httpx.Request) -> httpx.Response:
        pedidos.append(request)
        if zero_spend_verified and request.url.path == "/api/v1/key":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "is_management_key": False,
                        "is_provisioning_key": False,
                        "limit": 0,
                        "include_byok_in_limit": True,
                    }
                },
            )
        return responder(request)

    adapter = OpenRouterAdapter(
        "sk-or-v1-sintetica",
        allow_uncapped_free_tier=allow_uncapped_free_tier,
    )
    adapter._client = httpx.AsyncClient(  # noqa: SLF001
        base_url=adapter._client.base_url,  # noqa: SLF001
        headers=adapter._client.headers,  # noqa: SLF001
        transport=httpx.MockTransport(registrar),
    )
    return adapter, pedidos


def modelo_openrouter(
    endpoint_id: str,
    *,
    prompt: str = "0",
    completion: str = "0",
    request: str = "0",
    output_modalities: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": endpoint_id,
        "canonical_slug": endpoint_id.removesuffix(":free"),
        "name": "Modelo de teste",
        "context_length": 131072,
        "architecture": {
            "input_modalities": ["text"],
            "output_modalities": output_modalities or ["text"],
        },
        "pricing": {"prompt": prompt, "completion": completion, "request": request},
        "supported_parameters": ["reasoning", "tools", "structured_outputs"],
        "top_provider": {"max_completion_tokens": 32768},
        "reasoning": {"supported_efforts": ["high", "medium", "low"]},
    }


async def test_openrouter_descobre_so_variantes_textuais_gratuitas_publicadas() -> None:
    entries = [
        modelo_openrouter("openai/gpt-oss-20b:free"),
        modelo_openrouter("openai/gpt-oss-20b"),
        modelo_openrouter("openrouter/free"),
        modelo_openrouter("vendor/composto:online:free"),
        modelo_openrouter("vendor/imagem:free", output_modalities=["image"]),
        modelo_openrouter("vendor/entrada-cobrada:free", prompt="0.0001"),
        modelo_openrouter("vendor/cobrado:free", completion="0.0001"),
        modelo_openrouter("vendor/pedido-cobrado:free", request="0.005"),
        {"sem": "id"},
    ]

    def responder(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/models"
        return httpx.Response(
            200,
            json={"data": entries, "total_count": len(entries), "links": {"next": None}},
        )

    adapter, pedidos = openrouter_com(responder)
    models = await adapter.list_models()

    assert [model.endpoint_id for model in models] == ["openai/gpt-oss-20b:free"]
    model = models[0]
    assert model.family == "gpt"
    assert model.context_window == 131072
    assert model.max_output_tokens == 32768
    assert model.capabilities == ["completion", "reasoning", "tools", "structured_outputs"]
    assert model.raw["canonical_slug"] == "openai/gpt-oss-20b"
    assert model.raw["supported_parameters"] == [
        "reasoning",
        "tools",
        "structured_outputs",
    ]
    assert model.declared_limits["requests_per_minute_aggregate"] == 20
    assert model.declared_limits["requests_per_day_aggregate"] == 50
    assert pedidos[0].url.params["limit"] == "1000"
    assert pedidos[0].url.params["output_modalities"] == "text"


async def test_openrouter_recusa_catalogo_paginado_em_vez_de_persistir_parcial() -> None:
    adapter, _ = openrouter_com(
        lambda _request: httpx.Response(
            200,
            json={
                "data": [modelo_openrouter("openai/gpt-oss-20b:free")],
                "total_count": 2,
                "links": {"next": "https://openrouter.ai/api/v1/models?offset=1"},
            },
        )
    )
    with pytest.raises(ProviderError, match="inventário parcial"):
        await adapter.list_models()


async def test_openrouter_valida_em_key_sem_listar_nem_gerar() -> None:
    adapter, pedidos = openrouter_com(
        lambda request: httpx.Response(
            200,
            json={
                "data": {
                    "is_management_key": False,
                    "is_provisioning_key": False,
                    "limit": 0,
                    "include_byok_in_limit": True,
                }
            },
        ),
        zero_spend_verified=False,
    )
    detalhe = await adapter.verify_credential()

    assert [request.url.path for request in pedidos] == ["/api/v1/key"]
    assert "teto de gasto USD 0" in detalhe
    assert pedidos[0].headers["authorization"] == "Bearer sk-or-v1-sintetica"


async def test_openrouter_nao_aceita_chave_administrativa_para_inferencia() -> None:
    adapter, _ = openrouter_com(
        lambda _request: httpx.Response(200, json={"data": {"is_management_key": True}}),
        zero_spend_verified=False,
    )
    with pytest.raises(ProviderAuthError, match="administrativa"):
        await adapter.verify_credential()


@pytest.mark.parametrize("administrative_field", ["is_management_key", "is_provisioning_key"])
async def test_openrouter_opt_in_nao_aceita_chave_administrativa(
    administrative_field: str,
) -> None:
    adapter, _ = openrouter_com(
        lambda _request: httpx.Response(
            200,
            json={
                "data": {
                    "is_management_key": False,
                    "is_provisioning_key": False,
                    administrative_field: True,
                    "is_free_tier": True,
                    "limit": None,
                    "include_byok_in_limit": False,
                }
            },
        ),
        zero_spend_verified=False,
        allow_uncapped_free_tier=True,
    )

    with pytest.raises(ProviderAuthError, match="administrativa"):
        await adapter.verify_credential()


@pytest.mark.parametrize(
    "administrative_state",
    [
        {"is_provisioning_key": False},
        {"is_management_key": False},
        {"is_management_key": None, "is_provisioning_key": False},
        {"is_management_key": False, "is_provisioning_key": None},
        {"is_management_key": 1, "is_provisioning_key": False},
        {"is_management_key": False, "is_provisioning_key": "false"},
    ],
)
async def test_openrouter_recusa_estado_administrativo_ausente_ou_inexato(
    administrative_state: dict[str, object],
) -> None:
    data: dict[str, object] = {
        "limit": 0,
        "include_byok_in_limit": True,
        **administrative_state,
    }
    adapter, _ = openrouter_com(
        lambda _request: httpx.Response(200, json={"data": data}),
        zero_spend_verified=False,
    )

    with pytest.raises(ProviderAuthError, match="explicitamente"):
        await adapter.verify_credential()


@pytest.mark.parametrize("limit", [None, 1, 0.01, "sem limite"])
async def test_openrouter_recusa_chave_sem_teto_zero(limit: object) -> None:
    adapter, _ = openrouter_com(
        lambda _request: httpx.Response(
            200,
            json={
                "data": {
                    "is_management_key": False,
                    "is_provisioning_key": False,
                    "limit": limit,
                }
            },
        ),
        zero_spend_verified=False,
    )

    with pytest.raises(ProviderAuthError, match="teto de gasto USD 0"):
        await adapter.verify_credential()


async def test_openrouter_recusa_free_tier_sem_teto_sem_opt_in() -> None:
    adapter, _ = openrouter_com(
        lambda _request: httpx.Response(
            200,
            json={
                "data": {
                    "is_management_key": False,
                    "is_provisioning_key": False,
                    "is_free_tier": True,
                    "limit": None,
                    "include_byok_in_limit": False,
                }
            },
        ),
        zero_spend_verified=False,
    )

    with pytest.raises(ProviderAuthError, match="teto de gasto USD 0"):
        await adapter.verify_credential()


async def test_openrouter_opt_in_aceita_so_free_tier_sem_teto_e_avisa_sobre_byok() -> None:
    adapter, pedidos = openrouter_com(
        lambda _request: httpx.Response(
            200,
            json={
                "data": {
                    "is_management_key": False,
                    "is_provisioning_key": False,
                    "is_free_tier": True,
                    "limit": None,
                    "include_byok_in_limit": False,
                }
            },
        ),
        zero_spend_verified=False,
        allow_uncapped_free_tier=True,
    )

    detalhe = await adapter.verify_credential()

    assert [request.url.path for request in pedidos] == ["/api/v1/key"]
    assert "opt-in" in detalhe
    assert "BYOK fica fora" in detalhe


@pytest.mark.parametrize(
    "data",
    [
        {"is_free_tier": False, "limit": None, "include_byok_in_limit": False},
        {"is_free_tier": None, "limit": None, "include_byok_in_limit": False},
        {"is_free_tier": 1, "limit": None, "include_byok_in_limit": False},
        {"is_free_tier": True, "include_byok_in_limit": False},
        {"is_free_tier": True, "limit": 1, "include_byok_in_limit": False},
        {"is_free_tier": True, "limit": None, "include_byok_in_limit": None},
        {"is_free_tier": True, "limit": None, "include_byok_in_limit": True},
    ],
)
async def test_openrouter_opt_in_recusa_estado_que_nao_seja_free_tier_exato(
    data: dict[str, object],
) -> None:
    data = {
        "is_management_key": False,
        "is_provisioning_key": False,
        **data,
    }
    adapter, _ = openrouter_com(
        lambda _request: httpx.Response(200, json={"data": data}),
        zero_spend_verified=False,
        allow_uncapped_free_tier=True,
    )

    with pytest.raises(ProviderAuthError, match="só aceita /key"):
        await adapter.verify_credential()


async def test_openrouter_opt_in_nao_relaxa_byok_do_modo_forte() -> None:
    adapter, _ = openrouter_com(
        lambda _request: httpx.Response(
            200,
            json={
                "data": {
                    "is_management_key": False,
                    "is_provisioning_key": False,
                    "is_free_tier": True,
                    "limit": 0,
                    "include_byok_in_limit": False,
                }
            },
        ),
        zero_spend_verified=False,
        allow_uncapped_free_tier=True,
    )

    with pytest.raises(ProviderAuthError, match="incluir uso BYOK"):
        await adapter.verify_credential()


@pytest.mark.parametrize("include_byok", [False, None, "true"])
async def test_openrouter_recusa_byok_fora_do_teto_zero(include_byok: object) -> None:
    adapter, _ = openrouter_com(
        lambda _request: httpx.Response(
            200,
            json={
                "data": {
                    "is_management_key": False,
                    "is_provisioning_key": False,
                    "limit": 0,
                    "include_byok_in_limit": include_byok,
                }
            },
        ),
        zero_spend_verified=False,
    )

    with pytest.raises(ProviderAuthError, match="incluir uso BYOK"):
        await adapter.verify_credential()


async def test_openrouter_nunca_envia_modelo_pago_ou_router_aleatorio() -> None:
    adapter, pedidos = openrouter_com(
        lambda _request: pytest.fail("um ID proibido não deve chegar ao transporte")
    )
    for endpoint in (
        "openai/gpt-oss-20b",
        "openrouter/free",
        "openai/gpt-oss-20b:free:online",
        "openai/gpt-oss-20b:online:free",
    ):
        with pytest.raises(ProviderError, match="author/slug:free"):
            await adapter.generate(endpoint, "oi")
    assert pedidos == []


async def test_openrouter_gera_com_id_exato_e_preserva_rota_observada() -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/chat/completions"
        body = orjson.loads(request.content)
        assert body == {
            "model": "openai/gpt-oss-20b:free",
            "messages": [{"role": "user", "content": "diga ok"}],
            "max_tokens": 32,
            "stream": False,
            "plugins": [{"id": "web", "enabled": False}],
            "provider": {
                "max_price": {
                    "prompt": 0,
                    "completion": 0,
                    "request": 0,
                    "image": 0,
                }
            },
        }
        assert request.headers["x-openrouter-metadata"] == "enabled"
        return httpx.Response(
            200,
            headers={"x-generation-id": "gen-teste"},
            json={
                "model": "openai/gpt-oss-20b:free",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
                "openrouter_metadata": {
                    "strategy": "direct",
                    "attempt": 2,
                    "endpoints": {
                        "available": [
                            {
                                "provider": "Chutes",
                                "model": "openai/gpt-oss-20b",
                                "selected": True,
                            }
                        ]
                    },
                },
            },
        )

    adapter, _ = openrouter_com(responder)
    result = await adapter.generate("openai/gpt-oss-20b:free", "diga ok", max_output_tokens=32)

    assert result.text == "ok"
    assert result.usage["total_tokens"] == 4
    assert result.usage["openrouter_model"] == "openai/gpt-oss-20b:free"
    assert result.usage["openrouter_upstream_provider"] == "Chutes"
    assert result.usage["openrouter_strategy"] == "direct"
    assert result.usage["openrouter_attempt"] == 2
    assert result.usage["openrouter_generation_id"] == "gen-teste"


async def test_openrouter_preflight_zero_impede_chat_com_chave_sem_teto() -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/key"
        return httpx.Response(
            200,
            json={
                "data": {
                    "is_management_key": False,
                    "is_provisioning_key": False,
                    "limit": 10,
                }
            },
        )

    adapter, pedidos = openrouter_com(responder, zero_spend_verified=False)

    with pytest.raises(ProviderAuthError, match="teto de gasto USD 0"):
        await adapter.generate("openai/gpt-oss-20b:free", "oi")
    assert [pedido.url.path for pedido in pedidos] == ["/api/v1/key"]


async def test_openrouter_preflight_zero_libera_chat_sem_inferencia_extra() -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/key":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "is_management_key": False,
                        "is_provisioning_key": False,
                        "limit": 0,
                        "include_byok_in_limit": True,
                    }
                },
            )
        assert request.url.path == "/api/v1/chat/completions"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}], "usage": {"cost": 0}},
        )

    adapter, pedidos = openrouter_com(responder, zero_spend_verified=False)

    result = await adapter.generate("openai/gpt-oss-20b:free", "oi")

    assert result.text == "ok"
    assert [pedido.url.path for pedido in pedidos] == [
        "/api/v1/key",
        "/api/v1/chat/completions",
    ]


async def test_openrouter_recusa_custo_na_resposta_mesmo_com_guardas() -> None:
    adapter, _ = openrouter_com(
        lambda _request: httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "não aceitar"}}],
                "usage": {"cost": 0.005},
            },
        )
    )

    with pytest.raises(ProviderError, match="custo não zero"):
        await adapter.generate("openai/gpt-oss-20b:free", "oi")


@pytest.mark.parametrize(
    ("status", "exception"),
    [
        (401, ProviderAuthError),
        (402, ProviderAccountExhausted),
        (403, ProviderUnavailable),
        (502, ProviderUnavailable),
    ],
)
async def test_openrouter_classifica_status_sem_difamar_a_chave(
    status: int, exception: type[Exception]
) -> None:
    adapter, _ = openrouter_com(
        lambda _request: httpx.Response(status, json={"error": {"message": "falha"}})
    )
    with pytest.raises(exception):
        await adapter.generate("openai/gpt-oss-20b:free", "oi")


async def test_openrouter_429_preserva_retry_after_e_escopo_agregado() -> None:
    adapter, _ = openrouter_com(
        lambda _request: httpx.Response(
            429,
            headers={"retry-after": "9", "x-ratelimit-remaining": "0"},
            json={"error": {"message": "Rate limit exceeded"}},
        )
    )
    with pytest.raises(ProviderRateLimited) as limited:
        await adapter.generate("openai/gpt-oss-20b:free", "oi")
    assert limited.value.retry_after_s == 9.0
    limits = adapter.get_observed_limits()
    assert limits.retry_after_s == 9.0
    assert limits.raw["x-ratelimit-remaining"] == "0"
    assert "agregada" in limits.note


async def test_openrouter_stream_classifica_sem_persistir_argumentos_ou_cifra() -> None:
    segredo = "ARGUMENTO_INTERNO_NAO_PERSISTIR"
    sse = "\n\n".join(
        [
            ": OPENROUTER PROCESSING",
            "data: "
            + orjson.dumps(
                {
                    "model": "openai/gpt-oss-20b:free",
                    "choices": [
                        {
                            "delta": {
                                "reasoning": "duplicado",
                                "reasoning_details": [
                                    {"type": "reasoning.text", "text": "pensando"},
                                    {"type": "reasoning.summary", "summary": "resumo"},
                                    {
                                        "type": "reasoning.encrypted",
                                        "data": segredo,
                                        "format": "openai-responses-v1",
                                        "index": 2,
                                    },
                                ],
                                "content": "ok",
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "function": {"name": "buscar", "arguments": segredo},
                                    }
                                ],
                            },
                            "finish_reason": None,
                        }
                    ],
                }
            ).decode(),
            "data: "
            + orjson.dumps(
                {
                    "choices": [],
                    "openrouter_metadata": {
                        "strategy": "direct",
                        "attempt": 1,
                        "endpoints": {"available": [{"provider": "Chutes", "selected": True}]},
                    },
                }
            ).decode(),
            "data: [DONE]",
            "",
        ]
    )
    adapter, pedidos = openrouter_com(
        lambda _request: httpx.Response(
            200,
            headers={"content-type": "text/event-stream", "x-generation-id": "gen-stream"},
            content=sse,
        )
    )

    events = [event async for event in adapter.stream_generate("openai/gpt-oss-20b:free", "oi")]

    assert [event.kind for event in events] == [
        CognitiveKind.REASONING,
        CognitiveKind.REASONING_SUMMARY,
        CognitiveKind.PROGRESS,
        CognitiveKind.OUTPUT_DELTA,
        CognitiveKind.TOOL_CALL,
        CognitiveKind.FINAL,
    ]
    assert "duplicado" not in [event.text for event in events]
    assert events[-2].detail == {"name": "buscar", "index": 0}
    assert events[-1].detail["openrouter_upstream_provider"] == "Chutes"
    assert events[-1].detail["openrouter_generation_id"] == "gen-stream"
    assert segredo not in orjson.dumps([event.detail for event in events]).decode()
    body = orjson.loads(pedidos[-1].content)
    assert body["stream"] is True
    assert body["plugins"] == [{"id": "web", "enabled": False}]
    assert body["provider"]["max_price"] == {
        "prompt": 0,
        "completion": 0,
        "request": 0,
        "image": 0,
    }


async def test_openrouter_erro_no_sse_200_nao_vira_final() -> None:
    sse = (
        'data: {"error":{"code":429,"message":"limit"},'
        '"choices":[{"delta":{},"finish_reason":"error"}]}\n\n'
        "data: [DONE]\n\n"
    )
    adapter, _ = openrouter_com(lambda _request: httpx.Response(200, content=sse))
    with pytest.raises(ProviderRateLimited):
        _ = [event async for event in adapter.stream_generate("openai/gpt-oss-20b:free", "oi")]


async def test_openrouter_stream_recusa_custo_na_resposta() -> None:
    sse = (
        'data: {"choices":[],"usage":{"cost":0.005}}\n\n'
        "data: [DONE]\n\n"
    )
    adapter, _ = openrouter_com(lambda _request: httpx.Response(200, content=sse))

    with pytest.raises(ProviderError, match="custo não zero"):
        _ = [event async for event in adapter.stream_generate("vendor/modelo:free", "oi")]


async def test_openrouter_classifica_http_de_stream_antes_de_ler_eventos() -> None:
    class CorpoNaoLido(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield b'{"error":{"message":"invalid key"}}'

    adapter, _ = openrouter_com(
        lambda _request: httpx.Response(401, stream=CorpoNaoLido())
    )

    with pytest.raises(ProviderAuthError, match="credencial rejeitada"):
        _ = [event async for event in adapter.stream_generate("vendor/modelo:free", "oi")]


async def test_openrouter_stream_sem_done_nao_vira_sucesso() -> None:
    adapter, _ = openrouter_com(
        lambda _request: httpx.Response(
            200,
            content='data: {"choices":[{"delta":{"content":"incompleto"}}]}\n\n',
        )
    )

    with pytest.raises(ProviderUnavailable, match=r"sem data: \[DONE\]"):
        _ = [event async for event in adapter.stream_generate("vendor/modelo:free", "oi")]


def test_orcamento_openrouter_e_agregado_e_conservador() -> None:
    assert DECLARED_FREE_BUDGET["requests_per_minute_aggregate"] == 20
    assert DECLARED_FREE_BUDGET["requests_per_day_aggregate"] == 50
    assert "conservadora" in str(DECLARED_FREE_BUDGET["origem"])


# ---------------------------------------------------------------------------
# Consumo reportado no stream. Sem ele, quem consome o intervalo em vez da chamada
# única perde a medida e o ledger de cota passa a gastar orçamento contra estimativa.
# ---------------------------------------------------------------------------


def _uso_sdk(**campos: Any) -> SimpleNamespace:
    """Um objeto de uso como as SDKs entregam: com `model_dump`, e não um dicionário."""
    return SimpleNamespace(model_dump=lambda: dict(campos))


def _stream_sdk(pedacos: list[Any]) -> Callable[..., Any]:
    async def create(**_kwargs: Any) -> AsyncIterator[Any]:
        async def gerar() -> AsyncIterator[Any]:
            for pedaco in pedacos:
                yield pedaco

        return gerar()

    return create


def _delta(**campos: Any) -> SimpleNamespace:
    return SimpleNamespace(model_dump=lambda: dict(campos), tool_calls=None, **campos)


async def test_groq_final_carrega_o_consumo_ainda_que_venha_em_x_groq() -> None:
    """A SDK 1.6 declara `usage` no topo e em `x_groq`; o pedaço que o traz vem sem escolha."""
    pedacos = [
        SimpleNamespace(
            choices=[SimpleNamespace(delta=_delta(content="ok", reasoning=None))],
            usage=None,
            x_groq=None,
        ),
        SimpleNamespace(
            choices=[],
            usage=None,
            x_groq=SimpleNamespace(usage=_uso_sdk(total_tokens=91, prompt_tokens=12)),
        ),
    ]
    adapter = GroqAdapter("dummy")
    adapter._client = SimpleNamespace(  # type: ignore[assignment]  # noqa: SLF001
        chat=SimpleNamespace(completions=SimpleNamespace(create=_stream_sdk(pedacos)))
    )

    eventos = [evento async for evento in adapter.stream_generate("qwen/qwen3.6-27b", "oi")]

    assert eventos[-1].kind is CognitiveKind.FINAL
    assert eventos[-1].detail["usage"] == {"total_tokens": 91, "prompt_tokens": 12}


async def test_groq_sem_consumo_no_stream_nao_inventa_a_chave() -> None:
    pedacos = [
        SimpleNamespace(
            choices=[SimpleNamespace(delta=_delta(content="ok", reasoning=None))],
            usage=None,
            x_groq=None,
        )
    ]
    adapter = GroqAdapter("dummy")
    adapter._client = SimpleNamespace(  # type: ignore[assignment]  # noqa: SLF001
        chat=SimpleNamespace(completions=SimpleNamespace(create=_stream_sdk(pedacos)))
    )

    eventos = [evento async for evento in adapter.stream_generate("qwen/qwen3.6-27b", "oi")]

    assert eventos[-1].kind is CognitiveKind.FINAL
    assert eventos[-1].detail == {}


async def test_nvidia_final_carrega_o_consumo_sem_pedir_stream_options() -> None:
    """A NVIDIA não documenta `stream_options`; a requisição não muda para provocá-lo."""
    pedidos: list[dict[str, Any]] = []

    async def create(**kwargs: Any) -> AsyncIterator[Any]:
        pedidos.append(kwargs)

        async def gerar() -> AsyncIterator[Any]:
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=_delta(content="ok"))],
                usage=None,
            )
            yield SimpleNamespace(choices=[], usage=_uso_sdk(total_tokens=77))

        return gerar()

    adapter = NvidiaAdapter("dummy")
    adapter._client = SimpleNamespace(  # type: ignore[assignment]  # noqa: SLF001
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )

    eventos = [evento async for evento in adapter.stream_generate("z-ai/glm-5.2", "oi")]

    assert eventos[-1].detail["usage"] == {"total_tokens": 77}
    assert "stream_options" not in pedidos[0]


async def test_google_final_carrega_a_contagem_do_ultimo_pedaco() -> None:
    """`usage_metadata` chega parcial durante o stream: vale a última contagem."""

    async def generate_content_stream(**_kwargs: Any) -> AsyncIterator[Any]:
        async def gerar() -> AsyncIterator[Any]:
            yield SimpleNamespace(
                candidates=[
                    SimpleNamespace(
                        content=SimpleNamespace(
                            parts=[SimpleNamespace(text="ok", thought=None)]
                        )
                    )
                ],
                usage_metadata=SimpleNamespace(
                    prompt_token_count=5,
                    candidates_token_count=1,
                    total_token_count=6,
                ),
            )
            yield SimpleNamespace(
                candidates=[],
                usage_metadata=SimpleNamespace(
                    prompt_token_count=5,
                    candidates_token_count=9,
                    total_token_count=14,
                ),
            )

        return gerar()

    adapter = GoogleAdapter("dummy")
    adapter._client = SimpleNamespace(  # type: ignore[assignment]  # noqa: SLF001
        aio=SimpleNamespace(
            models=SimpleNamespace(generate_content_stream=generate_content_stream)
        )
    )

    eventos = [evento async for evento in adapter.stream_generate("gemini-3.6-flash", "oi")]

    assert eventos[-1].kind is CognitiveKind.FINAL
    assert eventos[-1].detail["usage"] == {
        "prompt_tokens": 5,
        "output_tokens": 9,
        "total_tokens": 14,
    }


async def test_ollama_final_reporta_o_mesmo_consumo_que_a_chamada_unica() -> None:
    """O quadro `done` do NDJSON tem a forma do corpo de `stream: false`."""
    linhas = "\n".join(
        [
            orjson.dumps({"message": {"thinking": "penso", "content": ""}}).decode(),
            orjson.dumps({"message": {"content": "ok"}}).decode(),
            orjson.dumps(
                {
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 13,
                    "eval_count": 21,
                    "total_duration": 1234,
                }
            ).decode(),
        ]
    )
    adapter, _ = ollama_com({"/api/chat": httpx.Response(200, content=linhas)})

    eventos = [evento async for evento in adapter.stream_generate("gemma4:31b", "oi")]

    final = eventos[-1]
    assert final.kind is CognitiveKind.FINAL
    assert final.detail["done_reason"] == "stop"
    assert final.detail["usage"]["prompt_eval_count"] == 13
    assert final.detail["usage"]["eval_count"] == 21
    # `generate` conta o tamanho do pensamento porque `num_predict` é gasto por ele
    # também; no stream a contagem é somada à medida que os pedaços chegam.
    assert final.detail["usage"]["thinking_chars"] == len("penso")


async def test_openrouter_final_carrega_consumo_e_proveniencia_como_generate() -> None:
    """A documentação diz que o consumo vem na última mensagem do SSE, sem parâmetro."""
    sse = "\n\n".join(
        [
            "data: "
            + orjson.dumps(
                {
                    "model": "vendor/modelo:free",
                    "choices": [{"delta": {"content": "ok"}, "finish_reason": None}],
                }
            ).decode(),
            "data: "
            + orjson.dumps(
                {
                    "choices": [],
                    "usage": {
                        "prompt_tokens": 8,
                        "completion_tokens": 3,
                        "total_tokens": 11,
                        "cost": 0,
                    },
                }
            ).decode(),
            "data: [DONE]",
            "",
        ]
    )
    adapter, _ = openrouter_com(
        lambda _request: httpx.Response(
            200,
            headers={"content-type": "text/event-stream", "x-generation-id": "gen-uso"},
            content=sse,
        )
    )

    eventos = [evento async for evento in adapter.stream_generate("vendor/modelo:free", "oi")]

    uso = eventos[-1].detail["usage"]
    assert uso["total_tokens"] == 11
    assert uso["cost"] == 0
    # Proveniência entra no mesmo dicionário porque é assim que `generate` a devolve, e
    # é esse dicionário que o painel grava.
    assert uso["openrouter_model"] == "vendor/modelo:free"
    assert uso["openrouter_generation_id"] == "gen-uso"


# --- Nous Research -----------------------------------------------------------
#
# O catálogo é público e a chave não se prova listando; os testes usam transporte
# fingido como os da Ollama — nenhum sai da máquina nem gasta cota.


def nous_com(
    rota: dict[str, httpx.Response | Callable[[httpx.Request], httpx.Response]],
) -> tuple[NousAdapter, list[httpx.Request]]:
    from openai import AsyncOpenAI

    pedidos: list[httpx.Request] = []

    def responder(request: httpx.Request) -> httpx.Response:
        pedidos.append(request)
        resposta = rota.get(request.url.path)
        assert resposta is not None, f"rota não esperada: {request.url.path}"
        return resposta(request) if callable(resposta) else resposta

    adapter = NousAdapter("dummy")
    adapter._client = AsyncOpenAI(  # noqa: SLF001
        api_key="dummy",
        base_url=BASE_URL,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(responder)),
    )
    return adapter, pedidos


def _modelos_nous() -> httpx.Response:
    payload = {
        "object": "list",
        "data": [
            {
                "id": "poolside/laguna-s-2.1:free",
                "object": "model",
                "created": 1,
                "owned_by": "nous",
                "pricing": {"prompt": "0", "completion": "0"},
                "context_length": 262144,
            },
            {
                "id": "tencent/hy3:free",
                "object": "model",
                "created": 1,
                "owned_by": "nous",
                "pricing": {"prompt": "0.0000000000", "completion": "0.0000000000"},
                "context_length": 262144,
            },
            # Variante :free com saída paga: o sufixo sozinho não basta.
            {
                "id": "poolside/laguna-xs-2.1:free",
                "object": "model",
                "created": 1,
                "owned_by": "nous",
                "pricing": {"prompt": "0", "completion": "0.00001"},
                "context_length": 262144,
            },
            # Modelo pago, sem sufixo: nunca entra.
            {
                "id": "google/gemini-3.7-flash",
                "object": "model",
                "created": 1,
                "owned_by": "nous",
                "pricing": {"prompt": "0.00001234", "completion": "0.00005"},
                "context_length": 1048576,
            },
        ],
    }
    return httpx.Response(200, json=payload)


async def test_nous_lista_so_variantes_free_com_preco_zero() -> None:
    adapter, _pedidos = nous_com({"/v1/models": _modelos_nous()})

    modelos = await adapter.list_models()

    assert [m.endpoint_id for m in modelos] == [
        "poolside/laguna-s-2.1:free",
        "tencent/hy3:free",
    ]
    assert all(m.context_window is not None for m in modelos)


async def test_nous_geracao_recusa_modelo_pago() -> None:
    adapter, _pedidos = nous_com({})

    with pytest.raises(ProviderError, match="author/slug:free"):
        await adapter.generate("google/gemini-3.7-flash", "oi")


async def test_nous_verifica_chave_com_um_token_no_sentinela() -> None:
    def completar(request: httpx.Request) -> httpx.Response:
        corpo = orjson.loads(request.content)
        assert corpo["model"] == SENTINEL
        assert corpo["max_tokens"] == 1
        assert corpo["messages"] == []
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "created": 1,
                "model": SENTINEL,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": ""},
                        "finish_reason": "length",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 1, "total_tokens": 1},
            },
        )

    adapter, _pedidos = nous_com({"/v1/chat/completions": completar})

    detalhe = await adapter.verify_credential()

    assert "credencial aceita" in detalhe
    assert SENTINEL in detalhe


def test_nous_declara_o_teto_do_free_tier_da_documentacao() -> None:
    adapter = NousAdapter("dummy")

    limites = adapter.get_observed_limits()

    assert limites.declared_requests_per_minute == 50
    assert "500.000" in limites.note or "500,000" in limites.note
    assert NOUS_BUDGET["tokens_per_minute"] == 500_000
