"""Separa a conclusão do raciocínio interno e valida o voto explícito."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import orjson
from pydantic import ValidationError

from vault.quorum.models import PanelMember, ParseResult, Vote, abstention

_THINK_TAG = re.compile(r"<\s*(/?)\s*think\b[^>]*>", re.IGNORECASE)
_THINK_PREFIX = re.compile(r"<\s*/?\s*think\b", re.IGNORECASE)
_DECODER = json.JSONDecoder()


def _without_length_bounds(node: Any) -> Any:
    """Remove ``maxLength`` do schema que vai ao modelo.

    Transformador nenhum decide sobre caracteres: ele emite tokens, e nenhum provedor
    impõe limite de caractere na decodificação. Anunciar o teto só produziu voto
    correto descartado por um byte — 213 caracteres contra 120. O teto continua
    valendo no servidor, que é onde ele é verificável.
    """
    if isinstance(node, dict):
        return {
            key: _without_length_bounds(value)
            for key, value in node.items()
            if key != "maxLength"
        }
    if isinstance(node, list):
        return [_without_length_bounds(item) for item in node]
    return node


def vote_contract() -> str:
    """Instrução derivada do mesmo schema fechado que valida o voto.

    O contrato explicita especialmente a correspondência entre decisão e ação. Foi
    essa fresta que apareceu na execução real: JSON sintaticamente correto, mas com
    uma explicação anexada ao enum de ``recommended_action``.
    """
    schema = json.dumps(
        _without_length_bounds(Vote.model_json_schema()),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        "Responda diretamente com EXATAMENTE um objeto JSON, sem Markdown, prosa "
        "antes/depois ou raciocínio interno. Emita um único objeto: dois objetos "
        "válidos na mesma resposta tornam o voto ambíguo e ele vira abstenção.\n"
        "A correspondência é obrigatória e literal:\n"
        '- decision="approve" exige recommended_action="promote";\n'
        '- decision="reject" exige recommended_action="reject";\n'
        '- decision="revise" exige recommended_action="revise";\n'
        '- decision="abstain" exige recommended_action="escalate".\n'
        "recommended_action aceita somente o enum exato, sem justificativa anexada. "
        "Escreva toda justificativa apenas em blocking_issues, non_blocking_issues ou "
        "evidence. Declare todos os campos, usando listas vazias quando necessário.\n"
        f"JSON Schema fechado:\n{schema}"
    )


@dataclass(frozen=True, slots=True)
class SanitizedResponse:
    final_response: str
    reasoning_block_detected: bool
    reasoning_block_removed: bool


def strip_reasoning(text: str) -> SanitizedResponse:
    """Remove blocos ``<think>`` sem tentar interpretá-los.

    Um bloco aberto e não fechado consome o restante da resposta. Isso pode descartar
    uma conclusão, mas nunca vaza scratchpad como se fosse conclusão.
    """
    pieces: list[str] = []
    depth = 0
    cursor = 0
    detected = False
    for match in _THINK_TAG.finditer(text):
        detected = True
        if depth == 0:
            pieces.append(text[cursor : match.start()])
        closing = bool(match.group(1))
        if closing:
            depth = max(depth - 1, 0)
        else:
            depth += 1
        cursor = match.end()
    if depth == 0:
        pieces.append(text[cursor:])
    final_response = "".join(pieces).strip()
    # Marca incompleta (por exemplo ``<think`` sem ``>``) não é um bloco que o
    # scanner acima consiga fechar. Truncar no início é o único tratamento seguro:
    # pode perder conclusão, mas nunca deixa raciocínio atravessar.
    incomplete = _THINK_PREFIX.search(final_response)
    if incomplete is not None:
        detected = True
        final_response = final_response[: incomplete.start()].strip()
    return SanitizedResponse(
        final_response=final_response,
        reasoning_block_detected=detected,
        reasoning_block_removed=detected,
    )


def _balanced_end(text: str, start: int) -> int | None:
    """Índice logo após a chave que fecha o objeto aberto em ``start``.

    Existe para o caso que ``raw_decode`` recusa e o reparo ainda pode salvar: uma
    vírgula pendente não desequilibra chaves, mas impede a decodificação. Sem esta
    delimitação o candidato nunca chegaria ao reparo. Devolve ``None`` quando o objeto
    não fecha — aí não há candidato, e não se arrasta o resto da resposta para dentro.
    """
    depth = 0
    quoted = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index + 1
    return None


def json_candidates(text: str) -> list[str]:
    """Todo objeto delimitado do texto, na ordem em que aparece.

    ``raw_decode`` valida enquanto percorre, então ele dá o fim exato do que já é JSON
    válido e nunca confunde uma chave dentro de string com início de objeto. Quando
    ele recusa, a delimitação por balanceamento assume, porque o objeto pode estar a
    uma vírgula de ser válido. Objeto aninhado dentro de outro já aceito não é
    recontado: a varredura salta para depois do que consumiu.
    """
    candidates: list[str] = []
    index = text.find("{")
    while index != -1:
        try:
            _, end = _DECODER.raw_decode(text, index)
        except ValueError:
            balanced = _balanced_end(text, index)
            if balanced is None:
                index = text.find("{", index + 1)
                continue
            end = balanced
        candidates.append(text[index:end])
        index = text.find("{", end)
    return candidates


def _decode(candidate: str) -> Vote:
    raw = orjson.loads(candidate)
    return Vote.model_validate(raw)


def repair_trailing_commas(candidate: str) -> str:
    """A única reparação permitida: retirar vírgula antes de ``}`` ou ``]``."""
    repaired: list[str] = []
    quoted = False
    escaped = False
    for index, char in enumerate(candidate):
        if quoted:
            repaired.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
            repaired.append(char)
            continue
        if char == ",":
            lookahead = index + 1
            while lookahead < len(candidate) and candidate[lookahead].isspace():
                lookahead += 1
            if lookahead < len(candidate) and candidate[lookahead] in "}]":
                continue
        repaired.append(char)
    return "".join(repaired)


@dataclass(frozen=True, slots=True)
class _Extraction:
    votes: tuple[Vote, ...]
    repaired: bool


def _extract(text: str) -> _Extraction:
    """Vota tudo que casa com o schema fechado, com o reparo de vírgula pendente."""
    votes: list[Vote] = []
    repaired = False
    for candidate in json_candidates(text):
        try:
            votes.append(_decode(candidate))
            continue
        except (orjson.JSONDecodeError, ValidationError, TypeError):
            pass
        try:
            votes.append(_decode(repair_trailing_commas(candidate)))
        except (orjson.JSONDecodeError, ValidationError, TypeError):
            continue
        repaired = True
    return _Extraction(tuple(votes), repaired)


def parse_vote(text: str, *, reviewer: PanelMember) -> ParseResult:
    """Extrai o voto explícito; ausência e ambiguidade viram abstenção.

    A conclusão é procurada primeiro fora do raciocínio, que é onde ela deveria
    estar. Só quando não há voto algum ali a busca desce à resposta bruta: modelos
    ajustados para raciocinar às vezes fecham o JSON dentro do próprio ``<think>``, e
    descartar isso custou seis votos válidos numa execução real. A ordem importa —
    rascunho dentro do raciocínio nunca se sobrepõe a uma conclusão declarada fora.

    Aceita-se somente quando existe exatamente um objeto válido. Dois votos válidos
    na mesma resposta não são um voto com redundância: são duas conclusões possíveis,
    e escolher uma delas seria o orquestrador votando no lugar do avaliador.
    """
    sanitized = strip_reasoning(text)
    extraction = _extract(sanitized.final_response)
    recovered = False
    if not extraction.votes:
        extraction = _extract(text)
        recovered = bool(extraction.votes)

    if len(extraction.votes) == 1:
        return ParseResult(
            reviewer=reviewer,
            final_response=sanitized.final_response,
            reasoning_block_detected=sanitized.reasoning_block_detected,
            reasoning_block_removed=sanitized.reasoning_block_removed,
            structured_vote=extraction.votes[0],
            schema_valid=True,
            repair_attempted=extraction.repaired,
            repair_succeeded=extraction.repaired,
            recovered_from_reasoning=recovered,
        )
    error = (
        f"{len(extraction.votes)} objetos válidos na mesma resposta: voto ambíguo"
        if extraction.votes
        else "nenhum objeto obedece ao schema fechado do voto"
    )
    return ParseResult(
        reviewer=reviewer,
        final_response=sanitized.final_response,
        reasoning_block_detected=sanitized.reasoning_block_detected,
        reasoning_block_removed=sanitized.reasoning_block_removed,
        structured_vote=abstention(),
        schema_valid=False,
        repair_attempted=True,
        repair_succeeded=False,
        error=error,
    )
