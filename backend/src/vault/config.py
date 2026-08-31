"""Configuração do projeto.

As chaves vêm de ~/.config/ane/secrets.env (canônico). Se esse arquivo não
existir, cai no legado ~/.config/vault-autodidata/secrets.env. Ambos ficam fora
do repositório. O ambiente do processo tem precedência, o que permite sobrepor
um valor numa chamada isolada sem editar o arquivo.

As chaves são `SecretStr`, então `repr` e `model_dump_json` mostram `**********` em
vez do valor — um log ou um traceback não vaza credencial por acidente.
`credential_status()` diz se cada credencial existe, nunca qual é; quem precisa do
texto puro chama `get_secret_value()` no limite do SDK, e só lá.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


def default_secrets_file() -> Path:
    """Caminho do arquivo de segredos: override, canônico ane, depois legado."""
    override = os.environ.get("VAULT_SECRETS_FILE")
    if override:
        return Path(override)
    canonical = Path.home() / ".config" / "ane" / "secrets.env"
    if canonical.is_file():
        return canonical
    return Path.home() / ".config" / "vault-autodidata" / "secrets.env"


SECRETS_FILE = default_secrets_file()
SECRETS_FILE_HINT = (
    "~/.config/ane/secrets.env (legado ~/.config/vault-autodidata/secrets.env)"
)
SECRET_SHAPE = re.compile(
    r"AIza[0-9A-Za-z_\-]{20,}|gsk_[0-9A-Za-z]{20,}|nvapi-[0-9A-Za-z_\-]{20,}"
    r"|sk-or-v1-[0-9A-Za-z_\-]{20,}"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=SECRETS_FILE,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        populate_by_name=True,
        extra="ignore",
    )

    gemini_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    nvidia_api_key: SecretStr | None = None
    ollama_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    nous_api_key: SecretStr | None = None

    # Exceção operacional explícita para contas OpenRouter estritamente free-tier
    # cuja chave está sem teto configurado. O modo forte (teto USD 0 e BYOK
    # incluído) continua sendo o padrão; ligar isto não relaxa nenhuma guarda da
    # requisição nem aceita uma conta que `/key` não marque como gratuita.
    openrouter_allow_uncapped_free_tier: bool = Field(
        default=False,
        validation_alias="OPENROUTER_ALLOW_UNCAPPED_FREE_TIER",
    )

    google_workspace_client_secret_file: Path | None = None
    google_workspace_token_file: Path | None = None

    # O mesmo arquivo que `env_file` lê, agora também nomeável como campo. A escrita
    # de credencial precisa de um caminho que o teste possa apontar para um diretório
    # temporário; sem isso, testar a gravação exigiria escrever no arquivo real.
    secrets_file: Path = Field(
        default_factory=default_secrets_file,
        validation_alias="VAULT_SECRETS_FILE",
    )

    corpus_dir: Path = Field(
        default=REPO_ROOT / "knowledge",
        validation_alias="VAULT_CORPUS_DIR",
    )
    runtime_dir: Path = Field(
        default=REPO_ROOT / "runtime",
        validation_alias="VAULT_RUNTIME_DIR",
    )

    # Camada operacional sintética. Só nasce de pedido explícito: nunca é consequência
    # de o corpus falhar, e a projeção sempre declara que a origem é demonstração.
    demo_operational: bool = Field(default=False, validation_alias="VAULT_DEMO_OPERATIONAL")

    # Teto de chamadas externas por execução do orquestrador. É o limite que não
    # depende de header nenhum, e o único que o mantenedor controla diretamente.
    # Passar dele exige decisão humana, não ajuste de código.
    work_max_calls: int = Field(default=6, validation_alias="VAULT_WORK_MAX_CALLS")

    # Tarefas autônomas simultâneas por processo. Cada quórum consome ~4 chamadas;
    # o teto efetivo continua sendo work_max_calls.
    worker_concurrency: int = Field(default=3, validation_alias="VAULT_WORKER_CONCURRENCY")

    # Chamadas simultâneas por provedor dentro deste processo. O mapa é o piso;
    # o worker sobe até o RPM documentado. Zero desativa novas alocações sem
    # apagar credencial nem evidência de sonda. O teto 512 cabe dezenas/centenas
    # em voo (A.N.E); 64 matava a morfologia.
    provider_concurrency: dict[str, int] = Field(
        default_factory=dict,
        validation_alias="VAULT_PROVIDER_CONCURRENCY",
    )

    @field_validator("provider_concurrency", mode="before")
    @classmethod
    def _valid_provider_concurrency(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized: dict[str, int] = {}
        for provider, limit in value.items():
            if not isinstance(provider, str) or not re.fullmatch(
                r"[a-z][a-z0-9_-]{0,63}", provider
            ):
                raise ValueError(f"provedor inválido no mapa de concorrência: {provider!r}")
            if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 512:
                raise ValueError(f"concorrência de {provider} precisa estar entre 0 e 512")
            normalized[provider] = limit
        return normalized

    @property
    def proposals_dir(self) -> Path:
        return self.runtime_dir / "proposals"

    @property
    def logs_dir(self) -> Path:
        return self.runtime_dir / "logs"

    @property
    def state_dir(self) -> Path:
        return self.runtime_dir / "state"

    @property
    def models_dir(self) -> Path:
        """Histórico por endpoint. Sobrevive ao endpoint sair do catálogo."""
        return self.runtime_dir / "modelos"

    @property
    def cognition_dir(self) -> Path:
        """Raciocínio ao vivo. Efêmero; não entra no corpus nem no quórum."""
        return self.runtime_dir / "cognition"

    def credential_status(self) -> dict[str, bool]:
        """Quais credenciais existem. Nunca os valores."""
        return {
            "gemini": bool(self.gemini_api_key),
            "groq": bool(self.groq_api_key),
            "nvidia": bool(self.nvidia_api_key),
            "ollama": bool(self.ollama_api_key),
            "openrouter": bool(self.openrouter_api_key),
            "nous": bool(self.nous_api_key),
            "google_workspace": bool(
                self.google_workspace_client_secret_file
                and self.google_workspace_client_secret_file.is_file()
            ),
        }

    def redact(self, text: str) -> str:
        """Remove chaves conhecidas de mensagens vindas de SDKs e transporte.

        `SecretStr` protege representação e serialização, mas uma exceção de SDK pode
        carregar a URL ou o pedido que recebeu. A fronteira de CLI chama este método
        antes de imprimir ou persistir qualquer detalhe externo.
        """
        redacted = text
        for secret in (
            self.gemini_api_key,
            self.groq_api_key,
            self.nvidia_api_key,
            self.ollama_api_key,
            self.openrouter_api_key,
            self.nous_api_key,
        ):
            if secret is None:
                continue
            value = secret.get_secret_value()
            if not value:
                continue
            redacted = redacted.replace(value, "[REDACTED]")
            encoded = quote(value, safe="")
            if encoded != value:
                redacted = redacted.replace(encoded, "[REDACTED]")
        return SECRET_SHAPE.sub("[REDACTED]", redacted)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    caminho = default_secrets_file()
    return Settings(_env_file=caminho, secrets_file=caminho)  # type: ignore[call-arg]
