"""Configuração: caminhos previsíveis e nenhuma chave em lugar visível."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr

from vault.config import ANE_SECRETS_FILE, LEGACY_SECRETS_FILE, REPO_ROOT, SECRETS_FILE, Settings


def settings_isoladas(**overrides: Any) -> Settings:
    """`Settings` sem ler o secrets.env da máquina.

    Um teste que enxergasse as chaves reais passaria ou falharia conforme o que Luiz
    tem preenchido no momento. `_env_file` é argumento de runtime do
    pydantic-settings e não aparece na assinatura tipada, daí o ignore.
    """
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


def test_caminhos_padrao_apontam_para_dentro_do_repositorio(repo_root: Path) -> None:
    settings = settings_isoladas()
    assert repo_root == REPO_ROOT
    assert settings.corpus_dir == repo_root / "knowledge"
    assert settings.runtime_dir == repo_root / "runtime"
    assert settings.proposals_dir == repo_root / "runtime" / "proposals"


def test_segredos_moram_fora_do_repositorio(repo_root: Path) -> None:
    esperado = ANE_SECRETS_FILE if ANE_SECRETS_FILE.is_file() else LEGACY_SECRETS_FILE
    assert SECRETS_FILE == esperado
    assert SECRETS_FILE in {ANE_SECRETS_FILE, LEGACY_SECRETS_FILE}
    assert repo_root not in SECRETS_FILE.parents


def test_status_de_credencial_diz_se_existe_e_nao_qual_e() -> None:
    """Nem `repr`, nem `model_dump_json`, nem o status podem revelar a chave."""
    segredo = "valor-que-nao-deve-aparecer"
    settings = settings_isoladas(
        gemini_api_key=SecretStr(segredo),
        groq_api_key=None,
        nvidia_api_key=None,
        ollama_api_key=None,
        openrouter_api_key=None,
    )
    status = settings.credential_status()
    assert status == {
        "gemini": True,
        "groq": False,
        "nvidia": False,
        "ollama": False,
        "openrouter": False,
        "nous": False,
        "google_workspace": False,
    }
    assert segredo not in str(status)
    assert segredo not in repr(settings)
    assert segredo not in settings.model_dump_json()
    assert isinstance(settings.gemini_api_key, SecretStr)
    # E o valor continua acessível a quem precisa dele de fato.
    assert settings.gemini_api_key.get_secret_value() == segredo


def test_redacao_cobre_valor_literal_e_codificado() -> None:
    settings = settings_isoladas(gemini_api_key=SecretStr("segredo com espaço"))
    mensagem = "literal=segredo com espaço url=segredo%20com%20espa%C3%A7o"
    redigida = settings.redact(mensagem)
    assert "segredo" not in redigida
    assert redigida == "literal=[REDACTED] url=[REDACTED]"


def test_redacao_alcanca_chave_de_formato_nao_documentado() -> None:
    """A chave do Ollama não tem prefixo publicado, então `SECRET_SHAPE` não a pega.

    Quem a protege é a substituição do valor literal, e é justamente por isso que ela
    precisa estar na lista de `redact` — um padrão inventado daria falsa cobertura.
    """
    chave = "chave-do-ollama-sem-prefixo-conhecido"
    settings = settings_isoladas(ollama_api_key=SecretStr(chave))
    redigida = settings.redact(f"Authorization: Bearer {chave}")
    assert redigida == "Authorization: Bearer [REDACTED]"


def test_redacao_reconhece_formato_openrouter_mesmo_sem_settings() -> None:
    chave = "sk-or-v1-" + "A1b2" * 12
    settings = settings_isoladas()
    assert settings.redact(f"falha ao usar {chave}") == "falha ao usar [REDACTED]"


def test_redacao_literal_da_chave_openrouter_configurada() -> None:
    chave = "sk-or-v1-" + "Z9y8" * 12
    settings = settings_isoladas(openrouter_api_key=SecretStr(chave))
    assert settings.redact(f"Authorization: Bearer {chave}").endswith("[REDACTED]")


def test_opt_in_openrouter_sem_teto_e_desligado_por_padrao() -> None:
    assert settings_isoladas().openrouter_allow_uncapped_free_tier is False


def test_opt_in_openrouter_sem_teto_exige_variavel_explicita() -> None:
    settings = settings_isoladas(OPENROUTER_ALLOW_UNCAPPED_FREE_TIER="1")
    assert settings.openrouter_allow_uncapped_free_tier is True


def test_concorrencia_por_provedor_le_objeto_json_e_aceita_pausa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "VAULT_PROVIDER_CONCURRENCY",
        '{"google":0,"groq":4,"nvidia":4,"ollama":1,"openrouter":1}',
    )
    settings = settings_isoladas()
    assert settings.provider_concurrency == {
        "google": 0,
        "groq": 4,
        "nvidia": 4,
        "ollama": 1,
        "openrouter": 1,
    }


@pytest.mark.parametrize(
    "raw",
    (
        '{"Google":1}',
        '{"groq":-1}',
        '{"groq":513}',
        '{"groq":true}',
    ),
)
def test_concorrencia_por_provedor_recusa_forma_insegura(
    raw: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VAULT_PROVIDER_CONCURRENCY", raw)
    with pytest.raises(ValueError):
        settings_isoladas()


def test_valores_vazios_de_ambiente_usam_defaults(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Variável presente e vazia é ausência, não caminho vazio."""
    for nome in (
        "VAULT_CORPUS_DIR",
        "VAULT_RUNTIME_DIR",
        "GOOGLE_WORKSPACE_CLIENT_SECRET_FILE",
        "GOOGLE_WORKSPACE_TOKEN_FILE",
    ):
        monkeypatch.setenv(nome, "")
    settings = settings_isoladas()
    assert settings.corpus_dir == repo_root / "knowledge"
    assert settings.runtime_dir == repo_root / "runtime"
    assert settings.google_workspace_client_secret_file is None
    assert settings.google_workspace_token_file is None


def test_caminhos_podem_ser_injetados_programaticamente(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    runtime = tmp_path / "runtime"
    settings = settings_isoladas(corpus_dir=corpus, runtime_dir=runtime)
    assert settings.corpus_dir == corpus
    assert settings.runtime_dir == runtime
