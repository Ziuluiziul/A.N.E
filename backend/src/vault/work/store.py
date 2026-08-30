"""Onde entrada e saída de cada endpoint ficam depois da execução.

    runtime/modelos/<provedor>/<identificador-exato>/
        entrada/<tarefa>.json     o que foi enviado
        trabalho/<tarefa>.json    o que voltou
        falhas/<tarefa>.json      o que falhou, com a causa classificada
        log.jsonl                 uma linha por evento, em ordem

A pasta sobrevive ao endpoint: quando um modelo sai do catálogo, o histórico dele
continua legível. Mas ela só nasce quando há o que guardar — diretório à espera de
conteúdo é placeholder, e placeholder é proibido em todas as camadas deste projeto.

Painéis, votos e decisões vivem separadamente em `runtime/quorum/`, sob
``vault.quorum.QuorumStore``. Este store continua responsável apenas pelo histórico
de chamadas por endpoint.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import orjson

from vault.quorum.parser import strip_reasoning
from vault.work.tasks import WorkResult

_PRIVATE_DIR = 0o700
_PRIVATE_FILE = 0o600

# Identificador de endpoint vira caminho. `meta/llama-3.3-70b` são dois níveis, o que
# é desejável; `..` e absoluto não são, e é isso que a validação impede.
#
# `:` entra porque é como a Ollama separa modelo e tag — `gemma4:31b` é um nome legítimo
# de endpoint, e recusá-lo derrubava a execução inteira antes da primeira chamada. Ele
# não ajuda a escapar da raiz: quem escapa é `..` e a barra inicial, e os dois continuam
# recusados. A checagem de contenção logo abaixo permanece como segunda linha.
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


class UnsafeEndpointPath(ValueError):
    """Identificador que não pode virar caminho sem sair do diretório de trabalho."""


def endpoint_directory(root: Path, provider: str, endpoint_id: str) -> Path:
    """Traduz `(provedor, endpoint)` em caminho, recusando o que escaparia da raiz."""
    segments = [provider, *endpoint_id.split("/")]
    for segment in segments:
        if not _SAFE_SEGMENT.match(segment):
            raise UnsafeEndpointPath(f"segmento inválido em caminho de endpoint: {segment!r}")
    directory = root.joinpath(*segments)
    if root.resolve() not in directory.resolve().parents:
        raise UnsafeEndpointPath(f"caminho escaparia de {root}: {directory}")
    return directory


def _write_private(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, mode=_PRIVATE_DIR, exist_ok=True)
    path.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2))
    path.chmod(_PRIVATE_FILE)


@dataclass(frozen=True, slots=True)
class WorkStore:
    """Escreve o histórico por endpoint. Não decide nada; só registra."""

    root: Path

    def record(self, result: WorkResult) -> Path | None:
        """Guarda uma execução. Devolve o arquivo escrito, ou `None` se não houve chamada.

        Tarefa recusada antes de virar chamada não pertence a endpoint nenhum: atribuí-la
        a um deles sujaria um histórico que não tem culpa.
        """
        sanitized = strip_reasoning(result.text)
        detail = result.detail
        if sanitized.reasoning_block_detected and "reasoning_block_removed=true" not in detail:
            marker = "reasoning_block_detected=true; reasoning_block_removed=true"
            detail = f"{detail}; {marker}" if detail else marker
        result = replace(result, text=sanitized.final_response, detail=detail)
        assignment = result.assignment
        if not result.called or not assignment.provider:
            return None

        directory = endpoint_directory(self.root, assignment.provider, assignment.endpoint_id)
        pasta = "trabalho" if result.outcome in ("ok", "reachable") else "falhas"
        destino = directory / pasta / f"{assignment.task.id}.json"

        entrada = directory / "entrada" / f"{assignment.task.id}.json"
        _write_private(entrada, assignment.task.to_dict())
        _write_private(destino, result.to_dict())
        self._append_log(directory, result)
        return destino

    def _append_log(self, directory: Path, result: WorkResult) -> None:
        """Uma linha por evento. Append, nunca reescrita: histórico não se edita."""
        directory.mkdir(parents=True, mode=_PRIVATE_DIR, exist_ok=True)
        log = directory / "log.jsonl"
        linha = orjson.dumps(
            {
                "at": result.observed_at,
                "task_id": result.assignment.task.id,
                "kind": result.assignment.task.kind,
                "role": result.assignment.task.role_name,
                "outcome": result.outcome,
                "latency_ms": result.latency_ms,
                "detail": result.detail,
            }
        )
        existia = log.exists()
        with log.open("ab") as stream:
            stream.write(linha + b"\n")
        if not existia:
            log.chmod(_PRIVATE_FILE)

    def history(self, provider: str, endpoint_id: str) -> list[dict[str, Any]]:
        """Lê o log de um endpoint. Linha corrompida é pulada, não derruba a leitura."""
        log = endpoint_directory(self.root, provider, endpoint_id) / "log.jsonl"
        if not log.is_file():
            return []
        eventos: list[dict[str, Any]] = []
        for linha in log.read_bytes().splitlines():
            if not linha.strip():
                continue
            try:
                evento = orjson.loads(linha)
            except orjson.JSONDecodeError:
                continue
            if isinstance(evento, dict):
                eventos.append(evento)
        return eventos
