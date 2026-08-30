"""Escrita atômica de arquivo sensível.

Dois arquivos deste pacote guardam coisas que não podem ficar pela metade: o arquivo
de segredos e as preferências de operação. Escrever por cima do original significa que
uma interrupção — disco cheio, processo morto, exceção no meio — deixa um arquivo
truncado onde antes havia um íntegro. No caso do arquivo de segredos isso apaga
credenciais que ninguém pediu para apagar.

O caminho seguro é o de sempre: escreve num temporário no **mesmo diretório**, força a
ida ao disco e troca por `os.replace`, que é atômico dentro de um sistema de arquivos.
Mesmo diretório porque `os.replace` entre sistemas de arquivos diferentes não é
atômico — e `/tmp` costuma ser outro.
"""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

# Todo arquivo escrito por este módulo nasce legível só pelo dono. Diretórios novos
# também nascem privados; exigir que um diretório **preexistente** já seja privado é
# opt-in, porque o mesmo mecanismo atende preferências sob um runtime configurável.
FILE_MODE = 0o600
DIR_MODE = 0o700


class PrivateParentError(PermissionError):
    """O pai de uma escrita privada não satisfaz o contrato, sem revelar o caminho."""


def require_parent_mode(parent: Path, required_mode: int) -> None:
    """Recusa um pai que não seja o diretório privado exato declarado pelo chamador."""
    metadata = parent.lstat()
    if stat.S_ISLNK(metadata.st_mode):
        raise PrivateParentError("diretório privado não pode ser link simbólico")
    if not stat.S_ISDIR(metadata.st_mode):
        raise PrivateParentError("pai da escrita privada não é um diretório")
    actual_mode = stat.S_IMODE(metadata.st_mode)
    if actual_mode != required_mode:
        raise PrivateParentError(
            f"diretório privado exige modo {required_mode:04o}; encontrado {actual_mode:04o}"
        )
    if hasattr(os, "geteuid") and metadata.st_uid != os.geteuid():
        raise PrivateParentError("diretório privado pertence a outro usuário")


def write_atomic(
    path: Path,
    data: bytes,
    *,
    mode: int = FILE_MODE,
    required_parent_mode: int | None = None,
) -> None:
    """Substitui `path` por `data`, ou não mexe em nada.

    `required_parent_mode` faz a verificação **antes** de `mkstemp`. O mecanismo não
    corrige um diretório existente com `chmod`: o caminho é configurável e pode ser
    compartilhado por decisão do chamador. Credenciais preferem recusar a mudar esse
    diretório silenciosamente.
    """
    destino = Path(path)
    creation_mode = required_parent_mode if required_parent_mode is not None else DIR_MODE
    destino.parent.mkdir(parents=True, mode=creation_mode, exist_ok=True)
    if required_parent_mode is not None:
        require_parent_mode(destino.parent, required_parent_mode)
    descritor, temporario = tempfile.mkstemp(
        dir=destino.parent, prefix=f".{destino.name}.", suffix=".tmp"
    )
    caminho_temporario = Path(temporario)
    try:
        # A permissão é aplicada antes de o conteúdo entrar: entre criar e proteger
        # não pode existir uma janela em que o segredo esteja legível por terceiros.
        os.fchmod(descritor, mode)
        with os.fdopen(descritor, "wb") as arquivo:
            arquivo.write(data)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(caminho_temporario, destino)
    except BaseException:
        # Inclui KeyboardInterrupt e SystemExit de propósito: um temporário com
        # segredo dentro não pode sobreviver a um Ctrl-C.
        caminho_temporario.unlink(missing_ok=True)
        raise
