"""Identidade das notas e resolução de wikilinks.

Dois riscos moram aqui, e nenhum deles é visível no corpus de hoje — o que os torna
mais perigosos, não menos, porque só aparecem quando uma nota nova entra.

**Sobrescrita silenciosa.** Enquanto a identidade for o nome do arquivo,
`Física/Entropia.md` e `Dados/Entropia.md` são a mesma nota para o grafo: a segunda
apaga a primeira sem erro. A identidade passa a ser o caminho relativo normalizado,
o que elimina a classe inteira em vez de detectá-la.

**Escolha arbitrária.** Quando um wikilink casa com mais de uma nota, escolher uma
delas produz um grafo plausível e errado. Aqui a ambiguidade reprova a projeção e
devolve todos os candidatos.

A normalização é NFC em tudo: no Linux o mesmo nome acentuado pode existir em bytes
diferentes conforme quem o escreveu, e `Física` decomposto não pode virar uma nota
distinta de `Física` composto.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from pathlib import PurePosixPath

MARKDOWN_SUFFIX = ".md"


class CorpusIdentityError(RuntimeError):
    """A projeção não pode continuar sem escolher uma nota arbitrariamente."""


def nfc(text: str) -> str:
    """Forma canônica composta. Duas grafias do mesmo nome viram a mesma string."""
    return unicodedata.normalize("NFC", text)


def fold(text: str) -> str:
    """Chave tolerante para o último recurso: sem caixa e sem acento."""
    decomposed = unicodedata.normalize("NFD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).strip()


def note_id(relative_path: str) -> str:
    """Identidade estável: caminho relativo POSIX, em NFC, sem a extensão.

    `Física/Entropia.md` → `Física/Entropia`. Independe do diretório de trabalho e da
    máquina, e distingue duas notas de mesmo nome em domínios diferentes.
    """
    posix = PurePosixPath(nfc(str(relative_path).replace("\\", "/")))
    if posix.suffix.lower() == MARKDOWN_SUFFIX:
        posix = posix.with_suffix("")
    return posix.as_posix()


def domain_slug(domain: str) -> str:
    """Identificador estável de domínio, para o contrato não depender do rótulo."""
    ascii_only = fold(domain).replace("—", "-").replace("/", "-")
    partes = [part for part in ascii_only.split() if part]
    return "-".join(partes) or "sem-dominio"


def split_target(raw: str) -> tuple[str, str | None]:
    """Separa `Nota#Seção` em alvo e fragmento. O fragmento não muda a nota."""
    text = nfc(raw).strip()
    if "#" not in text:
        return text, None
    base, _, fragment = text.partition("#")
    return base.strip(), fragment.strip() or None


@dataclass(frozen=True, slots=True)
class Resolution:
    """Resultado de resolver um wikilink. `target_id` só existe se for inequívoco."""

    target_id: str | None
    matched_by: str
    candidates: tuple[str, ...] = ()
    fragment: str | None = None

    @property
    def resolved(self) -> bool:
        return self.target_id is not None

    @property
    def ambiguous(self) -> bool:
        return self.target_id is None and len(self.candidates) > 1


@dataclass(frozen=True, slots=True)
class IndexedNote:
    """O mínimo que o índice precisa saber de uma nota para resolvê-la."""

    id: str
    relative_path: str
    stem: str
    title: str
    aliases: tuple[str, ...] = ()


# Ordem de precedência. Cada degrau só é tentado se o anterior não casou, e um degrau
# com mais de um candidato interrompe a busca em vez de descer para o próximo: descer
# esconderia a ambiguidade atrás de um critério mais frouxo.
PRECEDENCE = (
    "id",
    "relative-path",
    "filename",
    "title",
    "alias",
    "folded-filename",
    "folded-title",
    "folded-alias",
)


@dataclass
class CorpusIndex:
    """Índice de resolução construído uma vez por leitura do corpus."""

    notes: tuple[IndexedNote, ...]
    by_id: dict[str, IndexedNote] = field(default_factory=dict)
    by_stem: dict[str, list[IndexedNote]] = field(default_factory=dict)
    by_title: dict[str, list[IndexedNote]] = field(default_factory=dict)
    by_alias: dict[str, list[IndexedNote]] = field(default_factory=dict)
    by_folded_stem: dict[str, list[IndexedNote]] = field(default_factory=dict)
    by_folded_title: dict[str, list[IndexedNote]] = field(default_factory=dict)
    by_folded_alias: dict[str, list[IndexedNote]] = field(default_factory=dict)

    @classmethod
    def build(cls, notes: list[IndexedNote]) -> CorpusIndex:
        index = cls(notes=tuple(notes))
        for note in notes:
            if note.id in index.by_id:
                other = index.by_id[note.id]
                raise CorpusIdentityError(
                    "duas notas colidem na mesma identidade após normalização NFC: "
                    f"{other.relative_path!r} e {note.relative_path!r} → {note.id!r}. "
                    "Renomeie uma delas; o grafo não pode representar as duas."
                )
            index.by_id[note.id] = note
            index.by_stem.setdefault(nfc(note.stem), []).append(note)
            index.by_title.setdefault(nfc(note.title), []).append(note)
            index.by_folded_stem.setdefault(fold(note.stem), []).append(note)
            index.by_folded_title.setdefault(fold(note.title), []).append(note)
            for alias in note.aliases:
                index.by_alias.setdefault(nfc(alias), []).append(note)
                index.by_folded_alias.setdefault(fold(alias), []).append(note)
        return index

    # --- diagnóstico -------------------------------------------------------

    def collisions(self) -> dict[str, dict[str, list[str]]]:
        """Chaves que apontam para mais de uma nota, por família.

        Colidir não é, por si, defeito: duas notas podem ter o mesmo nome de arquivo em
        domínios diferentes sem que nada as referencie por nome. Vira defeito no
        momento em que um wikilink precisa escolher — e é lá que a projeção reprova.
        """
        familias = {
            "filename": self.by_stem,
            "title": self.by_title,
            "alias": self.by_alias,
        }
        return {
            nome: {
                chave: [n.id for n in notas] for chave, notas in mapa.items() if len(notas) > 1
            }
            for nome, mapa in familias.items()
            if any(len(notas) > 1 for notas in mapa.values())
        }

    # --- resolução ---------------------------------------------------------

    def resolve(self, raw_target: str, *, source_id: str) -> Resolution:
        """Resolve um alvo de wikilink na perspectiva da nota que o escreveu.

        A precedência é fixa e documentada em `PRECEDENCE`: do mais específico
        (identidade e caminho) ao mais frouxo (nome sem caixa nem acento). O primeiro
        degrau que produzir candidatos decide — e se produzir mais de um, ninguém
        decide.
        """
        base, fragment = split_target(raw_target)

        # Fragmento sozinho (`[[#Seção]]`) aponta para dentro da própria nota.
        if not base:
            return Resolution(source_id, "self", (source_id,), fragment)

        for step in PRECEDENCE:
            candidates = self._candidates(step, base, source_id)
            if not candidates:
                continue
            unique = sorted({note.id for note in candidates})
            if len(unique) == 1:
                return Resolution(unique[0], step, tuple(unique), fragment)
            return Resolution(None, step, tuple(unique), fragment)

        return Resolution(None, "unresolved", (), fragment)

    def _candidates(self, step: str, base: str, source_id: str) -> list[IndexedNote]:
        match step:
            case "id":
                note = self.by_id.get(note_id(base))
                return [note] if note else []
            case "relative-path":
                parent = PurePosixPath(source_id).parent
                relative = note_id((parent / base).as_posix()) if str(parent) != "." else ""
                if not relative:
                    return []
                # Normaliza `..` e `.` sem tocar no disco.
                parts: list[str] = []
                for part in PurePosixPath(relative).parts:
                    if part == "..":
                        if parts:
                            parts.pop()
                    elif part != ".":
                        parts.append(part)
                note = self.by_id.get(PurePosixPath(*parts).as_posix() if parts else "")
                return [note] if note else []
            case "filename":
                return self.by_stem.get(nfc(base), [])
            case "title":
                return self.by_title.get(nfc(base), [])
            case "alias":
                return self.by_alias.get(nfc(base), [])
            case "folded-filename":
                return self.by_folded_stem.get(fold(base), [])
            case "folded-title":
                return self.by_folded_title.get(fold(base), [])
            case "folded-alias":
                return self.by_folded_alias.get(fold(base), [])
            case _:  # pragma: no cover — PRECEDENCE é fechada
                raise AssertionError(f"degrau desconhecido: {step}")
