"""Gravação de credencial no arquivo de segredos, sem que ela apareça em lugar nenhum.

O mecanismo canônico é `~/.config/ane/secrets.env`; o legado
`~/.config/vault-autodidata/secrets.env` só entra se o arquivo canônico não existir.
É o mesmo arquivo que `vault.config` já lê. Este módulo só acrescenta o caminho de
escrita, com quatro cuidados que não são opcionais:

1. **Atômica.** Uma gravação interrompida não pode deixar o arquivo truncado — isso
   apagaria credenciais de outros provedores que ninguém pediu para apagar.
2. **`0600`.** O arquivo e o diretório pertencem só ao dono, e a permissão é aplicada
   antes de o conteúdo entrar.
3. **Preserva o que não é dela.** Variáveis de outros provedores, comentários e linhas
   em branco atravessam intactos. O arquivo é do mantenedor, não deste código.
4. **Nunca imprime.** Nem o valor antigo, nem o novo, nem o corpo do pedido. As
   exceções que sobem daqui carregam caminho e motivo, jamais conteúdo, e passam por
   `redact` defensivo antes de virar mensagem.

Um diretório preexistente precisa ser um diretório real, pertencer ao processo em
POSIX e já estar em `0700`. O módulo recusa com diagnóstico seguro se não estiver: não
faz `chmod` silencioso num caminho escolhido por configuração. O arquivo também não
pode ser link simbólico; essa guarda acontece antes de ler o conteúdo anterior.

**Sobre apagar da memória.** Não se alega isso. Em Python uma `str` é imutável e pode
ter sido copiada pelo interpretador, pelo servidor HTTP e pelo alocador; sobrescrever
a variável não apaga cópia nenhuma. O que dá para fazer é reter o mínimo: o valor entra
por parâmetro, é usado uma vez e sai de escopo, e nenhuma estrutura deste módulo o
guarda.
"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

from vault.control.atomic import (
    DIR_MODE,
    PrivateParentError,
    require_parent_mode,
    write_atomic,
)

# Provedor → variável de ambiente. É a mesma correspondência que `vault.config` usa
# para ler; declará-la aqui de novo em outra forma criaria duas verdades.
ENV_VAR_BY_PROVIDER: dict[str, str] = {
    "google": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "nvidia": "NVIDIA_API_KEY",
    "ollama": "OLLAMA_API_KEY",
    "nous": "NOUS_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}

PROVIDER_LABEL: dict[str, str] = {
    "google": "Google (Gemini)",
    "groq": "Groq",
    "nvidia": "NVIDIA",
    # "Cloud" no rótulo não é enfeite: a mesma API atende em localhost sem credencial
    # nenhuma, e é a nuvem que este painel configura.
    "ollama": "Ollama Cloud",
    "nous": "Nous Research (:free)",
    "openrouter": "OpenRouter (:free)",
}

# Sem espaço nas pontas, sem controle, sem quebra de linha. Um valor com `\n` quebraria
# o formato do arquivo e poderia injetar outra variável — é validação de formato, não
# de autenticidade.
_PROIBIDO = re.compile(r"[\x00-\x1f\x7f]")
MIN_LENGTH = 8
MAX_LENGTH = 512


class CredentialError(RuntimeError):
    """Falha ao ler ou gravar credencial. A mensagem nunca carrega o valor."""


def provider_env_var(provider_id: str) -> str:
    try:
        return ENV_VAR_BY_PROVIDER[provider_id]
    except KeyError:
        conhecidos = ", ".join(sorted(ENV_VAR_BY_PROVIDER))
        raise CredentialError(
            f"provedor desconhecido: {provider_id} (há {conhecidos})"
        ) from None


def mask(value: str | None) -> str | None:
    """Os quatro últimos caracteres, e só quando sobra o suficiente para esconder.

    Abaixo de doze caracteres os quatro finais são fração grande demais do segredo, e
    a dica passa a ser uma pista. Nesse caso não se mostra nada — estado sem dica ainda
    é estado útil.
    """
    if value is None or len(value) < 12:
        return None
    return value[-4:]


def validate(value: str) -> str:
    """Confere formato, nunca autenticidade. Quem diz se a chave vale é o provedor."""
    limpo = value.strip()
    if not limpo:
        raise CredentialError("credencial vazia")
    if len(limpo) < MIN_LENGTH:
        raise CredentialError(f"credencial curta demais (mínimo {MIN_LENGTH} caracteres)")
    if len(limpo) > MAX_LENGTH:
        raise CredentialError(f"credencial longa demais (máximo {MAX_LENGTH} caracteres)")
    if _PROIBIDO.search(limpo):
        raise CredentialError("credencial contém caractere de controle")
    return limpo


def _linhas(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        # `error` pode nomear o caminho; nunca o conteúdo. Ainda assim só o nome do
        # arquivo atravessa, porque o caminho completo revela o diretório do usuário.
        raise CredentialError(f"não foi possível ler {path.name}") from error


def _metadata_do_destino(path: Path) -> os.stat_result | None:
    """Inspeciona o nome final sem seguir um link simbólico."""
    try:
        return path.lstat()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise CredentialError(f"não foi possível inspecionar {path.name}") from error


def _require_regular_destination(metadata: os.stat_result | None) -> None:
    """Destino ausente é válido; destino existente precisa ser arquivo regular real."""
    if metadata is None:
        return
    if stat.S_ISLNK(metadata.st_mode):
        raise CredentialError("arquivo de credenciais não pode ser link simbólico")
    if not stat.S_ISREG(metadata.st_mode):
        raise CredentialError("destino de credenciais precisa ser arquivo regular")


def _require_private_parent(path: Path) -> None:
    """Valida um parent existente antes de qualquer leitura do arquivo de segredos."""
    try:
        require_parent_mode(path.parent, DIR_MODE)
    except FileNotFoundError:
        # O writer o criará com 0700 e repetirá a guarda antes de `mkstemp`.
        return
    except PrivateParentError as error:
        raise CredentialError(str(error)) from error
    except OSError as error:
        raise CredentialError(
            "não foi possível inspecionar o diretório de credenciais"
        ) from error


def _sem_a_variavel(linhas: list[str], var: str) -> list[str]:
    prefixos = (f"{var}=", f"export {var}=")
    return [linha for linha in linhas if not linha.strip().startswith(prefixos)]


def write_credential(path: Path, provider_id: str, value: str) -> str | None:
    """Grava a credencial do provedor e devolve **só** a dica mascarada.

    O valor de retorno é a dica de quatro caracteres, ou `None`. O valor integral não
    sai desta função por nenhum caminho.
    """
    var = provider_env_var(provider_id)
    limpo = validate(value)
    destino = Path(path)
    _require_private_parent(destino)
    metadata = _metadata_do_destino(destino)
    _require_regular_destination(metadata)
    linhas = _sem_a_variavel(_linhas(destino) if metadata is not None else [], var)
    linhas.append(f"{var}={limpo}")
    conteudo = "\n".join(linhas) + "\n"
    try:
        write_atomic(
            destino,
            conteudo.encode("utf-8"),
            required_parent_mode=DIR_MODE,
        )
    except PrivateParentError as error:
        raise CredentialError(str(error)) from error
    except OSError as error:
        raise CredentialError(f"não foi possível gravar {destino.name}") from error
    return mask(limpo)


def remove_credential(path: Path, provider_id: str) -> bool:
    """Remove a credencial. Devolve se havia alguma para remover."""
    var = provider_env_var(provider_id)
    destino = Path(path)
    metadata = _metadata_do_destino(destino)
    if metadata is None:
        return False
    _require_private_parent(destino)
    _require_regular_destination(metadata)
    linhas = _linhas(destino)
    restantes = _sem_a_variavel(linhas, var)
    if len(restantes) == len(linhas):
        return False
    conteudo = ("\n".join(restantes) + "\n") if restantes else ""
    try:
        write_atomic(
            destino,
            conteudo.encode("utf-8"),
            required_parent_mode=DIR_MODE,
        )
    except PrivateParentError as error:
        raise CredentialError(str(error)) from error
    except OSError as error:
        raise CredentialError(f"não foi possível gravar {destino.name}") from error
    return True
