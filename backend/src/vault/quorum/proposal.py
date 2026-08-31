"""Contrato entre a resposta do proponente e o ``CorpusPatch`` votado.

O quórum genérico continua aceitando proposta textual. Quando a tarefa declara uma
base Git em ``corpus_patch_base_commit``, porém, a resposta deixa de ser prosa: ela
precisa ser um ``CorpusPatch`` do schema fechado que o Promoter consome.

Há extração do único objeto válido — prosa à volta, fence, vírgula pendente — e o
orquestrador pode retentar o envelope uma vez. Não se inventa chave, conteúdo nem
fechamento: JSON truncado continua erro; dois objetos válidos continuam ambíguos;
campo extra continua recusado.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

import orjson
from pydantic import ValidationError

from vault.quorum.parser import (
    _balanced_end,
    json_candidates,
    repair_trailing_commas,
    strip_reasoning,
)

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
        "- todo wikilink novo é [[Stem]] <!-- relation:TIPO --> com Stem igual ao "
        "stem/título de uma nota já existente e TIPO em navigation, prerequisite, "
        "extends, contrasts, evidence, operational ou historical;\n"
        "- wikilink sem relation:, relation fora do vocabulário, ou Stem que não "
        "resolve, reprova a auditoria estrutural;\n"
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


def _try_load_patch(candidate: str) -> CorpusPatch | None:
    """Decodifica um candidato; a única reparação é vírgula pendente."""
    from vault.promotion.patch import CorpusPatch

    blobs = [candidate]
    repaired = repair_trailing_commas(candidate)
    if repaired != candidate:
        blobs.append(repaired)
    for blob in blobs:
        try:
            return CorpusPatch.model_validate(_load_json_object(blob))
        except (orjson.JSONDecodeError, ValidationError, TypeError):
            continue
    return None


def _extract_valid_patches(text: str) -> list[CorpusPatch]:
    """Todo CorpusPatch válido delimitado no texto, na ordem em que aparece."""
    encontrados: list[CorpusPatch] = []
    for candidate in json_candidates(text):
        patch = _try_load_patch(candidate)
        if patch is not None:
            encontrados.append(patch)
    return encontrados


def _truncated_object(text: str) -> bool:
    """Há `{` sem objeto fechado. Não se completa o JSON daqui."""
    start = text.find("{")
    if start == -1:
        return False
    return _balanced_end(text, start) is None


def envelope_needs_repair(error: BaseException) -> bool:
    """Só envelope incompleto: truncado ou JSON cortado. Ambiguidade e id não."""
    if not isinstance(error, ProposalEnvelopeError):
        return False
    texto = str(error).casefold()
    if "ambíguo" in texto or "diverge" in texto:
        return False
    return "truncad" in texto or "unexpected end" in texto


def envelope_repair_prompt(
    *,
    error: str,
    failed_response: str,
    proposal_id: str,
    base_commit: str,
    original_request: str,
    original_prompt: str | None = None,
) -> str:
    """Mesmo contrato do proponente, mais a ordem de emitir só o JSON fechado."""
    base = original_prompt or corpus_patch_prompt(
        original_request,
        proposal_id=proposal_id,
        base_commit=base_commit,
    )
    return (
        f"{base}\n\n"
        "A resposta anterior não era um CorpusPatch fechado "
        "(truncado ou prosa à volta). Emita SOMENTE o objeto JSON "
        "completo, sem Markdown, ata ou comentário.\n"
        f"Erro de envelope: {error}\n"
        f"Resposta a reparar:\n{failed_response}"
    )


def parse_corpus_patch(
    text: str,
    *,
    expected_proposal_id: str,
    expected_base_commit: str,
) -> ParsedCorpusPatch:
    """Valida sem adivinhar e devolve o objeto canônico que será votado.

    O caminho estrito continua o preferido. Se ele falhar, extrai-se o único
    CorpusPatch delimitado no texto sanitizado. Zero candidatos mantém o erro de
    envelope; dois ou mais são ambíguos. Truncamento não se fecha localmente.
    """
    from vault.promotion.patch import CorpusPatch

    sanitized = strip_reasoning(text)
    patch: CorpusPatch | None = None
    strict_error: Exception | None = None
    try:
        candidate = _strict_json_document(sanitized.final_response)
        patch = CorpusPatch.model_validate(_load_json_object(candidate))
    except (
        orjson.JSONDecodeError,
        ValidationError,
        TypeError,
        ProposalEnvelopeError,
    ) as error:
        strict_error = error
        encontrados = _extract_valid_patches(sanitized.final_response)
        if len(encontrados) == 1:
            patch = encontrados[0]
        elif len(encontrados) > 1:
            raise ProposalEnvelopeError(
                f"{len(encontrados)} objetos válidos na mesma resposta: patch ambíguo"
            ) from error
        elif sanitized.reasoning_block_removed and not sanitized.final_response.strip():
            recuperados = _extract_valid_patches(text)
            if len(recuperados) > 1:
                raise ProposalEnvelopeError(
                    f"{len(recuperados)} objetos válidos na mesma resposta: patch ambíguo"
                ) from error
            if len(recuperados) == 1:
                patch = recuperados[0]

    if patch is None:
        fonte = sanitized.final_response or text
        truncado = _truncated_object(fonte)
        detalhe = strict_error if strict_error is not None else "nenhum objeto válido"
        prefixo = "resposta do proponente truncada" if truncado else "resposta do proponente"
        raise ProposalEnvelopeError(
            f"{prefixo} não obedece ao CorpusPatch: {detalhe}"
        ) from strict_error

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
