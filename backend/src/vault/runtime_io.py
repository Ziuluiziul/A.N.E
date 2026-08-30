"""Escrita privada e atômica para evidências locais ignoradas pelo Git."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import orjson


def redact_json(payload: Any, redact: Callable[[str], str]) -> Any:
    """Sanitiza recursivamente texto externo antes de serializar evidencias."""
    if isinstance(payload, str):
        return redact(payload)
    if isinstance(payload, dict):
        return {
            redact(str(key)): redact_json(value, redact)
            for key, value in payload.items()
        }
    if isinstance(payload, list | tuple):
        return [redact_json(value, redact) for value in payload]
    return payload


def read_private_json(path: Path) -> Any | None:
    """Lê estado acumulado entre execuções. Ausente ou ilegível devolve `None`.

    Quem chama decide o que fazer com a ausência. Nenhum comando deve morrer porque
    um arquivo de runtime — que o Git não versiona — foi apagado ou corrompido.
    """
    try:
        return orjson.loads(path.read_bytes())
    except (OSError, orjson.JSONDecodeError):
        return None


def write_private_json(path: Path, payload: Any) -> None:
    """Grava JSON com diretório 700 e arquivo 600, sem janela de truncamento."""
    payload_bytes = orjson.dumps(payload, option=orjson.OPT_INDENT_2)
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(path.parent, 0o700)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
    )
    temporary_path = Path(temporary)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        os.chmod(path, 0o600)
        if os.name != "nt":
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        temporary_path.unlink(missing_ok=True)
