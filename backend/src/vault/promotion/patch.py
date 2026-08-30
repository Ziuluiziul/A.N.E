"""O patch que o quórum avalia e o Promoter aplica. Conteúdo inteiro, não diff.

Um diff em hunks depende do estado do arquivo no momento da aplicação, e é aí que
mora a diferença silenciosa entre o que os avaliadores leram e o que entra no corpus.
Conteúdo integral fecha essa fresta: o que foi votado é exatamente o que o arquivo
passa a ser, e a verificação vira comparação de bytes.

O digest é a amarra. Ele é calculado sobre a serialização canônica do patch e viaja
no contexto do painel; o Promoter recusa qualquer patch cujo digest não seja o que os
avaliadores viram. Sem isso, trocar o conteúdo depois do voto seria indetectável.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath
from typing import Any, Literal

import orjson
from pydantic import BaseModel, ConfigDict, Field, field_validator

from vault.corpus.reader import CLAIM_ROW, WIKILINK

# O Promoter só escreve nota do corpus. Nem código, nem configuração, nem runtime.
CORPUS_SUFFIX = ".md"
MAX_NOTE_BYTES = 512_000
_STUB_PHRASES = (
    "resto do conteúdo mantido",
    "resto mantido igual",
    "conteúdo não solicitada",
    "conteudo nao solicitado",
    "especificação do conteúdo não solicitada",
)
_STUB_LINES = frozenset({".", "..", "...", "…", "[...]", "(...)"})
_ATA_HEADING = re.compile(
    r"(?im)^#{1,6}\s+(?:"
    r"Decisão do painel\b"
    r"|Painel de divergência\b"
    r"|Painel\s+[0-9a-f]{8,}\b"
    r")"
)
_HEX_HEADING = re.compile(r"(?im)^#{1,6}\s+[0-9a-f]{12}\s*$")
_OPERATORNAME = re.compile(r"\\operatorname\*?\s*")
_THIN_SPACE_JUNK = re.compile(r"\\[!,:;]\s+[A-Za-z]+[\[(]")
_DOI = re.compile(r"(?:doi\.org/|doi:\s*)?(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.I)
_ARXIV = re.compile(r"(?:arxiv\.org/abs/|arXiv:)\s*(\d{4}\.\d{4,5}(?:v\d+)?)", re.I)
_ISBN = re.compile(r"(?:ISBN(?:-1[03])?:?\s*)?((?:978|979)(?:[-\s]?\d){10})", re.I)


class PatchRefused(ValueError):
    """Patch que não pode ser aplicado sem sair dos alvos declarados."""


class PatchOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action: Literal["create", "replace"]
    path: str = Field(min_length=1, max_length=400)
    content: str = Field(min_length=1, max_length=MAX_NOTE_BYTES)
    allows_reduction: bool = False

    @field_validator("path")
    @classmethod
    def caminho_fica_dentro_do_corpus(cls, value: str) -> str:
        """Recusa caminho absoluto, travessia e qualquer coisa que não seja nota."""
        candidate = PurePosixPath(value)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"caminho sai do corpus: {value!r}")
        if candidate.suffix != CORPUS_SUFFIX:
            raise ValueError(f"o Promoter só escreve {CORPUS_SUFFIX}: {value!r}")
        if any(part.startswith(".") for part in candidate.parts):
            raise ValueError(f"caminho oculto recusado: {value!r}")
        return str(candidate)


def _normalized_bytes(text: str) -> bytes:
    texto = text if text.endswith("\n") else text + "\n"
    return texto.encode("utf-8")


def note_metrics(text: str) -> tuple[int, int, int]:
    claims = sum(1 for line in text.splitlines() if CLAIM_ROW.match(line))
    return claims, len(WIKILINK.findall(text)), len(_normalized_bytes(text))


def reduction_reason(old: str, new: str) -> str | None:
    """O que um replace apaga sem declarar. Edição curta não é destruição."""
    old_claims, old_links, old_bytes = note_metrics(old)
    new_claims, new_links, new_bytes = note_metrics(new)
    drops: list[str] = []
    if new_claims < old_claims:
        drops.append(f"claims {old_claims}→{new_claims}")
    if new_links < old_links:
        drops.append(f"wikilinks {old_links}→{new_links}")
    lowered = new.casefold()
    stub = any(phrase in lowered for phrase in _STUB_PHRASES) or any(
        line.strip() in _STUB_LINES for line in new.splitlines()
    )
    halved = new_bytes * 2 < old_bytes
    if new_bytes < old_bytes and (halved or stub):
        drops.append(f"bytes {old_bytes}→{new_bytes}")
    return ", ".join(drops) if drops else None


def minutes_reason(text: str) -> str | None:
    """Ata de painel no corpo da nota. O julgamento fica no runtime, não no corpus."""
    if _ATA_HEADING.search(text) or _HEX_HEADING.search(text):
        return "ata de painel no corpo da nota"
    return None


def latex_break_reason(text: str) -> str | None:
    """LaTeX que o quórum já quebrou na prática: delimitadores e comandos mutilados."""
    if text.count("$$") % 2:
        return "delimitadores $$ desbalanceados"
    sem_display = re.sub(r"\$\$.*?\$\$", "", text, flags=re.S)
    simples = 0
    indice = 0
    while indice < len(sem_display):
        if (
            sem_display[indice] == "\\"
            and indice + 1 < len(sem_display)
            and sem_display[indice + 1] == "$"
        ):
            indice += 2
            continue
        if sem_display[indice] == "$":
            simples += 1
        indice += 1
    if simples % 2:
        return "delimitadores $ desbalanceados"
    for achado in _OPERATORNAME.finditer(text):
        if not text[achado.end() :].startswith("{"):
            return r"\operatorname sem argumento"
    if _THIN_SPACE_JUNK.search(text):
        return "comando LaTeX mutilado após espaço fino"
    return None


def _identifiers(text: str) -> set[str]:
    encontrados: set[str] = set()
    for achado in _DOI.finditer(text):
        encontrados.add("doi:" + achado.group(1).casefold().rstrip(".,;"))
    for achado in _ARXIV.finditer(text):
        encontrados.add("arxiv:" + achado.group(1).casefold())
    for achado in _ISBN.finditer(text):
        digits = re.sub(r"\D", "", achado.group(1))
        if len(digits) == 13:
            encontrados.add("isbn:" + digits)
    return encontrados


def identifier_removal_reason(old: str, new: str) -> str | None:
    """DOI, arXiv ou ISBN que saíram do texto. Remoção exige allows_reduction."""
    perdidos = sorted(_identifiers(old) - _identifiers(new))
    if not perdidos:
        return None
    return "identificadores removidos: " + ", ".join(perdidos)


def content_defect(old: str | None, new: str, *, allows_reduction: bool) -> str | None:
    """Defeito de conteúdo que o auditor estrutural não vê."""
    ata = minutes_reason(new)
    if ata:
        return ata
    latex = latex_break_reason(new)
    if latex:
        return latex
    if old is not None and not allows_reduction:
        return identifier_removal_reason(old, new)
    return None


class CorpusPatch(BaseModel):
    """A alteração completa que uma proposta pede, com a base sobre a qual foi feita."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: str = Field(min_length=1, max_length=64)
    base_commit: str = Field(min_length=7, max_length=40)
    operations: list[PatchOperation] = Field(min_length=1, max_length=20)

    @field_validator("operations")
    @classmethod
    def alvo_nao_se_repete(cls, value: list[PatchOperation]) -> list[PatchOperation]:
        caminhos = [operation.path for operation in value]
        if len(set(caminhos)) != len(caminhos):
            raise ValueError("o mesmo alvo aparece duas vezes no patch")
        return value

    @property
    def targets(self) -> list[str]:
        """Os alvos declarados, na ordem canônica usada pela verificação do diff."""
        return sorted(operation.path for operation in self.operations)

    def digest(self) -> str:
        """Impressão do que foi avaliado. Muda com qualquer byte de conteúdo ou alvo."""
        canonical = orjson.dumps(
            {
                "proposal_id": self.proposal_id,
                "base_commit": self.base_commit,
                "operations": [
                    {
                        "action": operation.action,
                        "path": operation.path,
                        "content": operation.content,
                        **(
                            {"allows_reduction": True}
                            if operation.allows_reduction
                            else {}
                        ),
                    }
                    for operation in sorted(self.operations, key=lambda op: op.path)
                ],
            },
            option=orjson.OPT_SORT_KEYS,
        )
        return hashlib.sha256(canonical).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def apply_to(self, corpus_root: Path) -> list[Path]:
        """Escreve os alvos numa árvore de corpus. Devolve os caminhos tocados.

        Chamado somente contra a árvore temporária de validação e, depois de tudo
        passar, contra a árvore que vai virar commit. Nunca contra o corpus vivo em
        uso, e nunca parcialmente: cada operação é conferida antes de qualquer escrita.
        """
        raiz = corpus_root.resolve()
        planejado: list[tuple[Path, str]] = []

        for operation in self.operations:
            destino = (raiz / operation.path).resolve()
            if raiz not in destino.parents:
                raise PatchRefused(f"alvo escaparia do corpus: {operation.path}")
            existe = destino.is_file()
            if operation.action == "create" and existe:
                raise PatchRefused(f"create sobre arquivo existente: {operation.path}")
            if operation.action == "replace" and not existe:
                raise PatchRefused(f"replace sobre arquivo ausente: {operation.path}")
            atual = destino.read_text(encoding="utf-8") if existe else None
            if (
                operation.action == "replace"
                and atual is not None
                and not operation.allows_reduction
            ):
                motivo = reduction_reason(atual, operation.content)
                if motivo:
                    raise PatchRefused(
                        f"replace reduz {operation.path} sem allows_reduction: {motivo}"
                    )
            defeito = content_defect(
                atual,
                operation.content,
                allows_reduction=operation.allows_reduction,
            )
            if defeito:
                raise PatchRefused(f"{operation.path}: {defeito}")
            planejado.append((destino, operation.content))

        escritos: list[Path] = []
        for destino, conteudo in planejado:
            destino.parent.mkdir(parents=True, exist_ok=True)
            texto = conteudo if conteudo.endswith("\n") else conteudo + "\n"
            destino.write_text(texto, encoding="utf-8")
            escritos.append(destino)
        return escritos
