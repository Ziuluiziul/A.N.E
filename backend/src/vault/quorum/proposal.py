"""Contrato entre a resposta do proponente e o ``CorpusPatch`` votado.

O quórum genérico continua aceitando proposta textual. Quando a tarefa declara uma
base Git em ``corpus_patch_base_commit``, porém, a resposta deixa de ser prosa: ela
precisa ser exatamente um ``CorpusPatch`` do schema fechado que o Promoter consome.
Não há reparo heurístico nessa fronteira; envelope malformado encerra a execução.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

import orjson
from pydantic import ValidationError

from vault.quorum.parser import json_candidates, strip_reasoning

if TYPE_CHECKING:
    from vault.promotion.patch import CorpusPatch

CORPUS_PATCH_BASE_KEY = "corpus_patch_base_commit"
PATCH_DIGEST_KEY = "patch_digest"
CORPUS_PATCH_ALLOWED_TARGETS_KEY = "corpus_patch_allowed_targets"
CORPUS_PATCH_ALLOW_CREATE_KEY = "corpus_patch_allow_create"


class ProposalEnvelopeError(ValueError):
    """O proponente não entregou o patch fechado que a tarefa exigia."""


@dataclass(frozen=True, slots=True)
class ParsedCorpusPatch:
    patch: CorpusPatch
    canonical_response: str
    reasoning_block_detected: bool
    reasoning_block_removed: bool


def canonical_patch_response(patch: CorpusPatch) -> str:
    """Representação única apresentada aos revisores e ligada pelo digest."""
    return orjson.dumps(patch.to_dict(), option=orjson.OPT_SORT_KEYS).decode("utf-8")


def corpus_patch_prompt(
    request: str,
    *,
    proposal_id: str,
    base_commit: str,
    allowed_targets: list[str] | None = None,
    allow_create: bool = True,
) -> str:
    """Especializa a tarefa do proponente com o schema exato do Promoter.

    O alvo entra literal, como já entravam `proposal_id` e `base_commit`. Sem isso o
    modelo deduz o caminho do título da nota e devolve variantes que não existem no
    disco — `fisica/Selecao-Natural-Cosmologica.md` por `Física/Seleção Natural
    Cosmológica.md`. Resolver a variante depois é remendo; não obrigar ao palpite é
    a correção.
    """
    from vault.promotion.patch import CorpusPatch

    schema = json.dumps(
        CorpusPatch.model_json_schema(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    escopo = ""
    if allowed_targets:
        alvos = ", ".join(f"{alvo!r}" for alvo in allowed_targets)
        escopo = (
            f"\nalvo(s) exato(s) autorizado(s), copie byte a byte: {alvos}\n"
            "Patch que mire qualquer outro caminho é recusado sem ser avaliado.\n"
        )
    if not allow_create:
        escopo += "Esta tarefa não autoriza criar nota: use somente replace.\n"
    return (
        "Produza uma alteração aplicável ao corpus. Sua resposta final deve ser "
        "EXATAMENTE um objeto JSON, sem bloco Markdown, comentário ou campo extra. "
        "Esse objeto será validado como CorpusPatch, mostrado sem alteração aos "
        "avaliadores e, se aprovado, aplicado pelo Proposal Promoter.\n\n"
        "Regras do patch:\n"
        "- use exatamente o proposal_id e o base_commit fornecidos abaixo;\n"
        "- paths são relativos a knowledge/, sem o prefixo knowledge/;\n"
        "- use create somente para nota nova explicitamente pedida;\n"
        "- use replace somente quando fornecer o conteúdo integral da nota existente;\n"
        "- content é Markdown integral, não diff, não reticências, não 'resto mantido';\n"
        "- replace que reduza claims, wikilinks ou o volume da nota exige "
        "allows_reduction: true;\n"
        "- não invente alvo, identificador, fonte ou relação; se a tarefa não contém "
        "contexto suficiente para um patch íntegro, não fabrique uma alteração.\n\n"
        f"proposal_id exato: {proposal_id}\n"
        f"base_commit exato: {base_commit}\n"
        f"{escopo}\n"
        f"JSON Schema fechado:\n{schema}\n\n"
        f"Pedido original:\n{request}\n\n"
        "Emita agora somente o objeto JSON de CorpusPatch."
    )


def _strict_json_document(text: str) -> str:
    """Aceita JSON puro ou um único fence JSON; rejeita prosa ao redor."""
    candidate = text.strip()
    if (
        len(candidate) >= 2
        and candidate.startswith("`")
        and candidate.endswith("`")
        and not candidate.startswith("```")
        and candidate.count("`") == 2
    ):
        candidate = candidate[1:-1].strip()
    if not candidate.startswith("```"):
        return candidate

    lines = candidate.splitlines()
    first = lines[0].strip().lower()
    if first not in {"```", "```json"}:
        raise ProposalEnvelopeError("envelope de patch tem fence inválido")
    if len(lines) < 2:
        raise ProposalEnvelopeError("envelope de patch tem fence inválido")
    body = lines[1:]
    if body and body[-1].strip() == "```":
        body = body[:-1]
    inner = "\n".join(body).strip()
    if not inner:
        raise ProposalEnvelopeError("envelope de patch tem fence inválido")
    return inner


def _escape_raw_controls_in_strings(text: str) -> str:
    """Escapa newline/tab crus dentro de strings JSON. Não inventa conteúdo."""
    out: list[str] = []
    quoted = False
    escaped = False
    for char in text:
        if quoted:
            if escaped:
                out.append(char)
                escaped = False
                continue
            if char == "\\":
                out.append(char)
                escaped = True
                continue
            if char == '"':
                quoted = False
                out.append(char)
                continue
            if char == "\n":
                out.append("\\n")
                continue
            if char == "\r":
                out.append("\\r")
                continue
            if char == "\t":
                out.append("\\t")
                continue
            out.append(char)
            continue
        if char == '"':
            quoted = True
        out.append(char)
    return "".join(out)


def _load_json_object(candidate: str) -> object:
    try:
        return orjson.loads(candidate)
    except orjson.JSONDecodeError:
        return orjson.loads(_escape_raw_controls_in_strings(candidate))


def _patch_within_reasoning(text: str) -> CorpusPatch | None:
    """O patch fechado dentro do próprio bloco de raciocínio, se houver exatamente um.

    Mesmo defeito que atingiu o voto, do lado do proponente: um modelo ajustado para
    raciocinar fecha o JSON dentro do ``<think>`` e a resposta sanitizada fica vazia.
    A proposta existia e era válida — descartá-la custa a tarefa inteira.

    Só se olha aqui quando nada sobreviveu fora do raciocínio, e só se aceita quando
    há um único candidato válido: rascunho não se sobrepõe a conclusão declarada, e
    dois patches na mesma resposta não deixam o orquestrador escolher qual vale.
    """
    from vault.promotion.patch import CorpusPatch

    encontrados: list[CorpusPatch] = []
    for candidate in json_candidates(text):
        try:
            encontrados.append(CorpusPatch.model_validate(orjson.loads(candidate)))
        except (orjson.JSONDecodeError, ValidationError, TypeError):
            continue
    return encontrados[0] if len(encontrados) == 1 else None


def parse_corpus_patch(
    text: str,
    *,
    expected_proposal_id: str,
    expected_base_commit: str,
) -> ParsedCorpusPatch:
    """Valida sem adivinhar e devolve o objeto canônico que será votado."""
    from vault.promotion.patch import CorpusPatch

    sanitized = strip_reasoning(text)
    candidate = _strict_json_document(sanitized.final_response)
    try:
        patch = CorpusPatch.model_validate(_load_json_object(candidate))
    except (orjson.JSONDecodeError, ValidationError, TypeError) as error:
        recuperado = (
            _patch_within_reasoning(text)
            if sanitized.reasoning_block_removed and not sanitized.final_response.strip()
            else None
        )
        if recuperado is None:
            raise ProposalEnvelopeError(
                f"resposta do proponente não obedece ao CorpusPatch: {error}"
            ) from error
        patch = recuperado

    if patch.proposal_id != expected_proposal_id:
        raise ProposalEnvelopeError(
            "proposal_id do patch diverge do identificador atribuído à proposta"
        )
    if patch.base_commit != expected_base_commit:
        raise ProposalEnvelopeError("base_commit do patch diverge da base entregue ao modelo")

    return ParsedCorpusPatch(
        patch=patch,
        canonical_response=canonical_patch_response(patch),
        reasoning_block_detected=sanitized.reasoning_block_detected,
        reasoning_block_removed=sanitized.reasoning_block_removed,
    )
