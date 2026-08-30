"""A seleção de endpoint precisa errar de forma visível, não silenciosa.

Os casos abaixo são os endpoints reais que a descoberta de 2026-08-02 devolveu. Eles
existem no teste porque a seleção alfabética escolheu justamente os dois piores —
`antigravity-preview-05-2026` e `01-ai/yi-large` — e nada no código impedia.
"""

from __future__ import annotations

from providers.aptitude import (
    classify,
    parse_version,
    preference_key,
    select_for_probe,
    select_for_work,
)
from providers.base import ModelInfo


def model(
    endpoint_id: str,
    *,
    provider: str = "nvidia",
    capabilities: list[str] | None = None,
    context_window: int | None = None,
    display_name: str = "",
    available: bool = True,
) -> ModelInfo:
    return ModelInfo(
        provider=provider,
        endpoint_id=endpoint_id,
        family="teste",
        capabilities=capabilities or [],
        context_window=context_window,
        available=available,
        raw={"display_name": display_name} if display_name else {},
    )


def test_capabilities_declaradas_vencem_o_nome() -> None:
    """O Google diz o que cada endpoint faz; ler o nome no lugar disso seria palpite."""
    imagem = classify(
        model("imagen-4.0-generate-001", provider="google", capabilities=["predict"])
    )
    assert imagem.modality == "image"
    assert not imagem.eligible
    assert "predict" in imagem.reason

    video = classify(
        model(
            "veo-3.1-generate-preview",
            provider="google",
            capabilities=["predictLongRunning"],
        )
    )
    assert video.modality == "video"

    embedding = classify(
        model("gemini-embedding-001", provider="google", capabilities=["embedContent"])
    )
    assert embedding.modality == "embedding"


def test_endpoint_sem_generate_content_nao_e_candidato() -> None:
    """`aqa` e os endpoints Live aparecem na listagem e não atendem geração comum."""
    aqa = classify(model("aqa", provider="google", capabilities=["generateAnswer"]))
    assert not aqa.eligible

    live = classify(
        model(
            "gemini-3.1-flash-live-preview",
            provider="google",
            capabilities=["bidiGenerateContent"],
        )
    )
    assert live.purpose == "live"
    assert not live.eligible


def test_modalidade_nao_textual_sai_mesmo_com_generate_content() -> None:
    """Nano Banana e TTS declaram generateContent e ainda assim não produzem texto."""
    for endpoint_id in (
        "gemini-2.5-flash-image",
        "gemini-2.5-flash-preview-tts",
        "lyria-3-pro-preview",
    ):
        aptitude = classify(
            model(
                endpoint_id,
                provider="google",
                capabilities=["generateContent", "countTokens"],
            )
        )
        assert not aptitude.eligible, endpoint_id


def test_propositos_especializados_saem_da_fila_textual() -> None:
    for endpoint_id, purpose in (
        ("nvidia/llama-3.1-nemoguard-8b-content-safety", "safety"),
        ("nvidia/nemotron-4-340b-reward", "reward"),
        ("nvidia/riva-translate-4b-instruct-v2", "translation"),
        ("nvidia/nemoretriever-parse", "retrieval"),
        ("whisper-large-v3", "transcription"),
        ("gemini-robotics-er-2-preview", "robotics"),
        ("deep-research-preview-04-2026", "research-agent"),
        ("antigravity-preview-05-2026", "research-agent"),
        ("groq/compound", "research-agent"),
        ("groq/compound-mini", "research-agent"),
    ):
        aptitude = classify(model(endpoint_id))
        assert aptitude.purpose == purpose, endpoint_id
        assert not aptitude.eligible, endpoint_id


def test_especializacao_util_continua_elegivel_mas_atras() -> None:
    """Modelo de código e de domínio servem ao corpus; só não servem primeiro."""
    geral = classify(model("meta/llama-3.3-70b-instruct"))
    codigo = classify(model("bigcode/starcoder2-15b"))
    dominio = classify(model("writer/palmyra-med-70b"))

    assert geral.eligible and codigo.eligible and dominio.eligible
    assert codigo.purpose == "code"
    assert dominio.purpose == "domain"
    assert preference_key(geral) < preference_key(dominio) < preference_key(codigo)

    # "medium" não é "med": substring aqui excluiria um modelo geral em silêncio.
    assert classify(model("mistralai/mistral-medium-3.5-128b")).purpose == "general"


def test_preview_e_apelido_perdem_para_estavel() -> None:
    """`-latest` troca de modelo sem aviso: num corpus com procedência, isso pesa."""
    estavel = classify(model("gemini-3.5-flash", provider="google", context_window=1_048_576))
    apelido = classify(
        model("gemini-flash-latest", provider="google", context_window=1_048_576)
    )
    preview = classify(
        model("gemini-3-flash-preview", provider="google", context_window=1_048_576)
    )

    assert (estavel.stability, apelido.stability, preview.stability) == (
        "stable",
        "alias",
        "preview",
    )
    assert preference_key(estavel) < preference_key(apelido) < preference_key(preview)


def test_versao_ignora_tamanho_e_data() -> None:
    assert parse_version("gemini-3.6-flash") == (3, 6)
    assert parse_version("gemini-2.0-flash-001") == (2, 0)
    assert parse_version("qwen/qwen3.6-27b") == (3, 6)
    assert parse_version("meta/llama-3.3-70b-instruct") == (3, 3)
    assert parse_version("nvidia/nemotron-3-super-120b-a12b") == (3, 0)
    assert parse_version("moonshotai/kimi-k2.6") == (2, 6)
    # Sem versão no nome é (0, 0), e não uma versão inventada.
    assert parse_version("openai/gpt-oss-120b") == (0, 0)
    assert parse_version("mistralai/mistral-large") == (0, 0)


def test_etiqueta_de_tamanho_da_ollama_nao_esconde_a_versao() -> None:
    """`:` fecha o nome e abre o tamanho; sem separá-lo a versão declarada se perde."""
    assert parse_version("qwen3.5:397b") == (3, 5)
    assert parse_version("gemma4:31b") == (4, 0)
    assert parse_version("deepseek-v4-flash:0731") == (4, 0)
    # E o tamanho continua não sendo versão, com ou sem etiqueta.
    assert parse_version("gpt-oss:120b") == (0, 0)


def test_sufixo_free_nao_muda_versao_e_parametros_nao_escondem_completion() -> None:
    endpoint = "openai/gpt-oss-20b:free"
    aptitude = classify(
        model(
            endpoint,
            provider="openrouter",
            capabilities=["completion", "reasoning", "tools", "structured_outputs"],
        )
    )
    assert parse_version(endpoint) == (0, 0)
    assert aptitude.family == "teste"
    assert aptitude.eligible is True
    assert aptitude.modality == "text"


def test_endpoint_indisponivel_no_catalogo_nao_e_sondado() -> None:
    aptitude = classify(model("meta/llama-3.3-70b-instruct", available=False))
    assert not aptitude.eligible
    assert "não lista" in aptitude.reason


def test_sonda_dirigida_prefere_texto_geral_e_estavel() -> None:
    """O caso que motivou tudo: alfabético escolhia yi-large, aptidão escolhe outro."""
    catalogo = [
        model("01-ai/yi-large"),
        model("baai/bge-m3"),
        model("meta/llama-3.3-70b-instruct"),
        model("nvidia/nemotron-4-340b-reward"),
    ]
    choice = select_for_probe(catalogo)
    assert choice is not None
    assert choice.endpoint_id == "meta/llama-3.3-70b-instruct"


def test_sonda_prefere_o_ainda_desconhecido_a_reconfirmar_o_conhecido() -> None:
    """Reconfirmar quem já respondeu gasta a única chamada sem produzir informação."""
    catalogo = [model("meta/llama-3.3-70b-instruct"), model("meta/llama-3.1-8b-instruct")]
    choice = select_for_probe(catalogo, {"meta/llama-3.3-70b-instruct": "ok"})
    assert choice is not None
    assert choice.endpoint_id == "meta/llama-3.1-8b-instruct"


def test_falha_anterior_adia_a_sonda_mas_nao_a_proibe() -> None:
    """Um 404 de ontem pode ser um endpoint que voltou; o registro precisa ser revisável."""
    catalogo = [model("meta/llama-3.3-70b-instruct")]
    choice = select_for_probe(catalogo, {"meta/llama-3.3-70b-instruct": "unavailable"})
    assert choice is not None
    assert choice.endpoint_id == "meta/llama-3.3-70b-instruct"


def test_trabalho_so_vai_para_endpoint_confirmado() -> None:
    """Aptidão pelo nome não autoriza trabalho: só sonda bem-sucedida autoriza."""
    catalogo = [model("z-ai/glm-5.2"), model("meta/llama-3.3-70b-instruct")]
    assert select_for_work(catalogo, {}) is None
    assert select_for_work(catalogo, {"z-ai/glm-5.2": "unavailable"}) is None

    escolhido = select_for_work(catalogo, {"meta/llama-3.3-70b-instruct": "ok"})
    assert escolhido is not None
    assert escolhido.endpoint_id == "meta/llama-3.3-70b-instruct"


def test_catalogo_sem_candidato_textual_nao_inventa_um() -> None:
    assert select_for_probe([model("baai/bge-m3"), model("whisper-large-v3")]) is None


def test_alcancado_sem_texto_nao_recebe_trabalho_e_e_resondado_antes() -> None:
    """Alcance não é utilidade: `reachable` fica na fila de dúvida, não na de trabalho."""
    catalogo = [model("z-ai/glm-5.2"), model("meta/llama-3.3-70b-instruct")]
    statuses = {"z-ai/glm-5.2": "reachable", "meta/llama-3.3-70b-instruct": "ok"}

    trabalho = select_for_work(catalogo, statuses)
    assert trabalho is not None
    assert trabalho.endpoint_id == "meta/llama-3.3-70b-instruct"

    # Entre os dois já sondados, o de maior incerteza volta primeiro.
    sonda = select_for_probe(catalogo, statuses)
    assert sonda is not None
    assert sonda.endpoint_id == "z-ai/glm-5.2"
