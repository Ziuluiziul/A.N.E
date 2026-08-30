"""CorpusReader — acesso somente-leitura ao corpus em knowledge/.

Este módulo lê; não julga. Quem decide se a estrutura está íntegra é
`tools/audit.py`, que continua independente e sem dependências de propósito: ele é
o gate, e um gate não deve quebrar porque o backend quebrou. A duplicação das
expressões regulares é deliberada, e `tests/test_corpus_reader.py` prende as duas
implementações às mesmas contagens para que uma não deslize sem a outra.

As regras de forma são as da Política: wikilink ativo declara `relation:` na mesma
linha, e claim se define numa linha de tabela que começa pelo seu ID.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx
import yaml

from vault.corpus.identity import (
    CorpusIdentityError,
    CorpusIndex,
    IndexedNote,
    Resolution,
    domain_slug,
    nfc,
    note_id,
    split_target,
)

WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
RELATION = re.compile(r"<!--\s*relation:([a-z_]+)\s*-->")
CLAIM_ROW = re.compile(r"^\|\s*`(CLM-[A-Z0-9-]+)`\s*\|(.*)$")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)

CLAIM_STATUSES = frozenset(
    {
        "established",
        "supported",
        "model-dependent",
        "hypothesis",
        "speculative",
        "open",
        "refuted",
        "operational",
        "out-of-scope",
        "quarantine",
    }
)
_CLAIM_STATUS_ALTERNATION = "|".join(
    re.escape(status) for status in sorted(CLAIM_STATUSES, key=len, reverse=True)
)
CLAIM_FIELDS = re.compile(
    rf"^(?P<statement>.*?)\|\s*"
    rf"(?P<status>(?:{_CLAIM_STATUS_ALTERNATION})|`(?:{_CLAIM_STATUS_ALTERNATION})`)"
    rf"\s*\|(?P<evidence>.*)$"
)

ALLOWED_RELATIONS = frozenset(
    {
        "navigation",
        "prerequisite",
        "extends",
        "contrasts",
        "evidence",
        "operational",
        "historical",
    }
)

# Arquivos de repositório que não são notas, caso o leitor seja apontado para uma
# raiz que os contenha. Mesma lista do auditor, pelo mesmo motivo.
EXCLUDED_DIRS = frozenset({".git", ".venv", "node_modules", "runtime", "dist"})
EXCLUDED_FILES = frozenset({"AGENTS.md", "CLAUDE.md", "README.md"})

ROOT_DOMAIN = "raiz"


@dataclass(frozen=True, slots=True)
class Claim:
    id: str
    statement: str
    status: str
    evidence: str
    note: str
    line: int


@dataclass(frozen=True, slots=True)
class Link:
    source: str
    target: str
    relation: str | None
    line: int
    fragment: str | None = None

    @property
    def declared(self) -> bool:
        return self.relation in ALLOWED_RELATIONS


@dataclass(frozen=True, slots=True)
class Note:
    id: str
    path: Path
    stem: str
    domain: str
    frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    body_start_line: int = 1

    @property
    def title(self) -> str:
        raw = self.frontmatter.get("title")
        return str(raw) if raw else self.stem

    @property
    def kind(self) -> str | None:
        raw = self.frontmatter.get("kind")
        return str(raw) if raw else None

    @property
    def epistemic_status(self) -> str | None:
        raw = self.frontmatter.get("epistemic_status")
        return str(raw) if raw else None

    @property
    def domain_id(self) -> str:
        return domain_slug(self.domain)

    @property
    def aliases(self) -> list[str]:
        raw = self.frontmatter.get("aliases")
        if isinstance(raw, list):
            return [str(a) for a in raw]
        if isinstance(raw, str):
            return [a.strip() for a in raw.split(",") if a.strip()]
        return []


class CorpusReader:
    """Lê notas, claims, links e o grafo de wikilinks de um diretório de corpus."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise FileNotFoundError(f"corpus não encontrado: {self.root}")

    # --- notas -------------------------------------------------------------

    def _markdown_paths(self) -> Iterator[Path]:
        """Somente `**/*.md` sob a raiz configurada. Symlink que sai do corpus reprova.

        Ignorar em silêncio seria pior que falhar: um symlink apontando para fora é
        ingestão de conteúdo não canônico, e o corpus tem de ser exatamente o que a
        configuração diz que é.
        """
        for path in sorted(self.root.rglob("*.md")):
            if EXCLUDED_DIRS & set(path.parts) or path.name in EXCLUDED_FILES:
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(self.root):
                raise CorpusIdentityError(
                    f"symlink sai do corpus: {path.relative_to(self.root)} → {resolved}"
                )
            yield path

    def list_notes(self) -> list[Note]:
        return [self._parse(path) for path in self._markdown_paths()]

    def read_note(self, ref: str | Path) -> Note:
        """Aceita o nome da nota (o stem, como o wikilink a escreve) ou um caminho."""
        candidate = Path(ref)
        path = candidate if candidate.is_absolute() else self.root / candidate
        resolved = path.resolve()
        if resolved.is_relative_to(self.root) and resolved.is_file():
            return self._parse(resolved)
        for path in self._markdown_paths():
            if path.stem == str(ref):
                return self._parse(path)
        raise KeyError(f"nota não encontrada no corpus: {ref}")

    def _parse(self, path: Path) -> Note:
        resolved = path.resolve()
        if not resolved.is_relative_to(self.root) or resolved.suffix.lower() != ".md":
            raise ValueError(f"nota fora do corpus: {path}")

        text = resolved.read_text(encoding="utf-8")
        match = FRONTMATTER.match(text)
        frontmatter: dict[str, Any] = {}
        body_start_line = 1
        if match:
            loaded = yaml.safe_load(match.group(1))
            if isinstance(loaded, dict):
                frontmatter = loaded
            body_start_line = text[: match.end()].count("\n") + 1
        body = text[match.end() :] if match else text
        relative = resolved.relative_to(self.root)
        domain = nfc(relative.parts[0]) if len(relative.parts) > 1 else ROOT_DOMAIN
        return Note(
            id=note_id(relative.as_posix()),
            path=relative,
            stem=nfc(resolved.stem),
            domain=domain,
            frontmatter=frontmatter,
            body=body,
            body_start_line=body_start_line,
        )

    # --- claims e links ----------------------------------------------------

    def extract_claims(self, note: Note) -> list[Claim]:
        claims: list[Claim] = []
        for number, line in enumerate(note.body.splitlines(), start=note.body_start_line):
            match = CLAIM_ROW.match(line)
            if not match:
                continue
            statement, status, evidence = self._claim_fields(match.group(2))
            claims.append(
                Claim(
                    id=match.group(1),
                    statement=statement,
                    status=status,
                    evidence=evidence,
                    note=note.id,
                    line=number,
                )
            )
        return claims

    @staticmethod
    def _claim_fields(raw: str) -> tuple[str, str, str]:
        """Separa as três células usando o status fechado como âncora.

        Afirmação e evidência são Markdown livre e podem conter ``|``. O status,
        ao contrário, pertence a um vocabulário fechado, então sua célula é o
        único separador confiável da linha.
        """
        payload = raw.rstrip()
        if payload.endswith("|"):
            payload = payload[:-1]

        match = CLAIM_FIELDS.match(payload)
        if match:
            status = match.group("status").strip("`")
            return (
                match.group("statement").strip(),
                status,
                match.group("evidence").strip(),
            )

        # Mantém o leitor tolerante a status ainda inválido: julgar a estrutura
        # continua sendo responsabilidade do auditor.
        cells = [cell.strip() for cell in payload.split("|", maxsplit=2)]
        cells.extend("" for _ in range(3 - len(cells)))
        return cells[0], cells[1], cells[2]

    def extract_links(self, note: Note) -> list[Link]:
        links: list[Link] = []
        for number, line in enumerate(note.body.splitlines(), start=note.body_start_line):
            targets = WIKILINK.findall(line)
            if not targets:
                continue
            # A relação vale para a linha: é assim que a Política a escreve e é
            # assim que o auditor a conta.
            relation = RELATION.search(line)
            for target in targets:
                base, fragment = split_target(target)
                links.append(
                    Link(
                        source=note.id,
                        target=base,
                        relation=relation.group(1) if relation else None,
                        line=number,
                        fragment=fragment,
                    )
                )
        return links

    def index(self, notes: list[Note] | None = None) -> CorpusIndex:
        """Índice de resolução. Reprova de saída se duas notas colidirem na identidade."""
        notes = notes if notes is not None else self.list_notes()
        return CorpusIndex.build(
            [
                IndexedNote(
                    id=note.id,
                    relative_path=note.path.as_posix(),
                    stem=note.stem,
                    title=note.title,
                    aliases=tuple(note.aliases),
                )
                for note in notes
            ]
        )

    def alias_index(self, notes: list[Note] | None = None) -> dict[str, list[str]]:
        """Alias para as identidades que o reivindicam. Lista, porque pode haver mais de uma."""
        index = self.index(notes)
        return {alias: [n.id for n in notas] for alias, notas in index.by_alias.items()}

    def resolve_link(self, link: Link, index: CorpusIndex) -> Resolution:
        return index.resolve(link.target, source_id=link.source)

    # --- grafo -------------------------------------------------------------

    def build_graph(self) -> nx.DiGraph:
        """Grafo dirigido de notas, com identidade por caminho e resolução explícita.

        Um wikilink que casa com mais de uma nota **reprova** a construção. A
        alternativa — escolher uma — produziria um grafo plausível e errado, que é o
        pior resultado possível para um corpus cuja finalidade é ser confiável.

        Link que não resolve não vira aresta nem nó fantasma: fica em
        `graph.graph["broken"]`, porque o grafo representa o corpus, não as intenções
        dele. Quem reprova link quebrado é o auditor.
        """
        notes = self.list_notes()
        index = self.index(notes)

        graph = nx.DiGraph()
        for note in notes:
            claims = self.extract_claims(note)
            graph.add_node(
                note.id,
                title=note.title,
                stem=note.stem,
                domain=note.domain,
                domain_id=note.domain_id,
                kind=note.kind,
                epistemic_status=note.epistemic_status,
                path=note.path.as_posix(),
                frontmatter=note.frontmatter,
                claims=len(claims),
            )

        broken: list[dict[str, Any]] = []
        undeclared: list[dict[str, Any]] = []
        ambiguous: list[dict[str, Any]] = []

        for note in notes:
            for link in self.extract_links(note):
                resolution = index.resolve(link.target, source_id=link.source)
                if resolution.ambiguous:
                    ambiguous.append(
                        {
                            "source": link.source,
                            "target": link.target,
                            "line": link.line,
                            "matched_by": resolution.matched_by,
                            "candidates": list(resolution.candidates),
                        }
                    )
                    continue
                if not resolution.resolved:
                    broken.append(
                        {"source": link.source, "target": link.target, "line": link.line}
                    )
                    continue
                if not link.declared:
                    undeclared.append(
                        {"source": link.source, "target": link.target, "line": link.line}
                    )

                resolved = resolution.target_id
                assert resolved is not None  # noqa: S101 — garantido por `resolved`
                if graph.has_edge(link.source, resolved):
                    data = graph[link.source][resolved]
                    if link.relation and link.relation not in data["relations"]:
                        data["relations"].append(link.relation)
                    data["weight"] += 1
                else:
                    graph.add_edge(
                        link.source,
                        resolved,
                        relations=[link.relation] if link.relation else [],
                        weight=1,
                        matched_by=resolution.matched_by,
                    )

        if ambiguous:
            detalhe = "; ".join(
                f"{item['source']} → {item['target']!r} por {item['matched_by']} "
                f"casa com {item['candidates']}"
                for item in ambiguous[:5]
            )
            raise CorpusIdentityError(
                f"{len(ambiguous)} wikilink(s) ambíguo(s); a projeção não escolhe por "
                f"você. {detalhe}"
            )

        graph.graph["broken"] = broken
        graph.graph["undeclared"] = undeclared
        graph.graph["collisions"] = index.collisions()
        return graph
