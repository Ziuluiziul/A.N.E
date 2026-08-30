#!/usr/bin/env python3
"""Auditoria estrutural e offline do corpus. Uso: audit.py [caminho-do-corpus].

Sem argumento, audita o ``knowledge/`` vizinho a este script — o corpus canônico.
Código e documentação de projeto vivem fora de ``knowledge/`` e por isso nunca
entram nas contagens.

AUDITOR ESTRUTURAL PARCIAL. Verifica forma, não verdade: contagens, integridade e
tipagem de wikilinks, órfãs, MOCs vazios, frontmatter, vencimento de ``review_after``,
unicidade de nomes de nota e linhas de claim. NÃO
resolve DOI/arXiv/ISBN, NÃO confere se um identificador corresponde ao título
canônico e NÃO avalia se uma afirmação é correta. Código de saída 0 significa
estrutura íntegra — nunca conteúdo aprovado. Isso continua sendo julgamento
humano.

Saída: 0 sem defeitos; 1 com qualquer defeito das categorias implementadas.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "knowledge"

# Rede de segurança para quem apontar o auditor à raiz do repositório por engano.
# Nenhum destes caminhos contém notas; ignorá-los não altera contagem alguma.
EXCLUDED_DIRS = frozenset({".git", ".venv", "node_modules", "runtime", "dist"})
EXCLUDED_FILES = frozenset({"AGENTS.md", "CLAUDE.md", "README.md"})

WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
RELATION = re.compile(r"<!--\s*relation:([a-z_]+)\s*-->")
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", re.S)
FRONTMATTER_FIELD = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:[ \t]*(.*))?$")
HEADING_LEVEL_ONE_OR_TWO = re.compile(r"^#{1,2}\s+")
CLAIM_ID = re.compile(r"^CLM-[A-Z0-9]+-[A-Z0-9]+-[0-9]{3}$")
TABLE_SEPARATOR = re.compile(
    r"^\s*\|\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*){3}\|\s*$"
)
ISO_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

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
REQUIRED_FRONTMATTER = (
    "title",
    "domain",
    "kind",
    "status",
    "epistemic_status",
    "updated",
)
KNOWN_FRONTMATTER = frozenset(
    (*REQUIRED_FRONTMATTER, "aliases", "verified_at", "review_after")
)
NOTE_KINDS = frozenset({"nota", "moc", "referência", "registro"})
NOTE_STATUSES = frozenset({"active", "archived", "quarantine"})
EPISTEMIC_STATUSES = frozenset(
    {
        "established",
        "supported",
        "model-dependent",
        "hypothesis",
        "speculative",
        "mixed",
        "operational",
        "quarantine",
    }
)
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
UNKNOWN_CLAIM_FIELDS = re.compile(
    r"^(?P<statement>.*?)\|\s*(?P<status>`?[a-z][a-z-]*`?)\s*\|(?P<evidence>.*)$"
)


@dataclass(frozen=True, slots=True)
class Finding:
    """Um defeito estrutural localizado, sem interpretar a verdade do conteúdo."""

    path: Path
    line: int
    message: str


@dataclass(frozen=True, slots=True)
class ClaimRow:
    """Os quatro campos estruturais de uma linha candidata a claim."""

    claim_id: str
    statement: str
    status: str
    evidence: str
    line: int


@dataclass(frozen=True, slots=True)
class ParsedFrontmatter:
    fields: dict[str, str]
    raw: str
    body: str
    body_start_line: int
    findings: tuple[Finding, ...]
    expirations: tuple[Finding, ...] = ()


def _scalar(raw: str) -> str:
    """Normaliza apenas aspas escalares; não finge ser um parser YAML."""

    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1].strip()
    if value == "~" or value.lower() == "null" or value.startswith("#"):
        return ""
    return value


def parse_frontmatter(text: str, path: Path) -> ParsedFrontmatter:
    """Lê os campos top-level necessários sem dependência ou resolução externa."""

    match = FRONTMATTER.match(text)
    if match is None:
        return ParsedFrontmatter(
            fields={},
            raw="",
            body=text,
            body_start_line=1,
            findings=(Finding(path, 1, "frontmatter ausente ou sem delimitador válido"),),
        )

    raw = match.group(1)
    fields: dict[str, str] = {}
    findings: list[Finding] = []
    seen: set[str] = set()
    field_lines: dict[str, int] = {}

    for line_number, line in enumerate(raw.splitlines(), start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        field_match = FRONTMATTER_FIELD.match(line)
        if field_match is None:
            if not line[:1].isspace():
                findings.append(
                    Finding(path, line_number, "linha top-level de frontmatter inválida")
                )
            continue
        key, raw_value = field_match.group(1), field_match.group(2) or ""
        if key in seen:
            if key in KNOWN_FRONTMATTER:
                findings.append(Finding(path, line_number, f"campo duplicado: {key}"))
            continue
        seen.add(key)
        fields[key] = _scalar(raw_value)
        field_lines[key] = line_number

    for key in REQUIRED_FRONTMATTER:
        if not fields.get(key, "").strip():
            findings.append(Finding(path, 1, f"campo obrigatório ausente ou vazio: {key}"))

    for key in (*REQUIRED_FRONTMATTER, "verified_at", "review_after"):
        if fields.get(key) in {"|", "|-", "|+", ">", ">-", ">+"}:
            findings.append(
                Finding(
                    path,
                    field_lines[key],
                    f"campo deve ser escalar em uma linha: {key}",
                )
            )

    enum_fields = {
        "kind": NOTE_KINDS,
        "status": NOTE_STATUSES,
        "epistemic_status": EPISTEMIC_STATUSES,
    }
    for key, allowed in enum_fields.items():
        value = fields.get(key)
        if value and value not in allowed:
            findings.append(
                Finding(path, field_lines[key], f"{key} fora do vocabulário: {value}")
            )

    parsed_dates: dict[str, date] = {}
    for key in ("updated", "verified_at", "review_after"):
        value = fields.get(key)
        if not value:
            continue
        try:
            if ISO_DATE.fullmatch(value) is None:
                raise ValueError
            parsed_dates[key] = date.fromisoformat(value)
        except ValueError:
            findings.append(
                Finding(path, field_lines[key], f"{key} não é uma data ISO válida: {value}")
            )

    if (
        "verified_at" in parsed_dates
        and "updated" in parsed_dates
        and parsed_dates["verified_at"] > parsed_dates["updated"]
    ):
        findings.append(
            Finding(
                path,
                field_lines["verified_at"],
                "verified_at não pode ser posterior a updated",
            )
        )

    expirations: tuple[Finding, ...] = ()
    if "review_after" in parsed_dates and parsed_dates["review_after"] < date.today():
        expirations = (
            Finding(
                path,
                field_lines["review_after"],
                "review_after vencido: a nota exige reconferência na fonte viva",
            ),
        )

    return ParsedFrontmatter(
        fields=fields,
        raw=raw,
        body=text[match.end() :],
        body_start_line=match.group(0).count("\n") + 1,
        findings=tuple(findings),
        expirations=expirations,
    )


def _without_code_ticks(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        return value[1:-1].strip()
    return value


def parse_claim_row(
    line: str,
    line_number: int,
    path: Path,
) -> tuple[ClaimRow | None, list[Finding]]:
    """Valida uma linha candidata usando o status como âncora para pipes internos."""

    findings: list[Finding] = []
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None, [
            Finding(path, line_number, "linha de claim deve começar e terminar com pipe")
        ]

    content = stripped[1:-1]
    raw_id, separator, remainder = content.partition("|")
    claim_id = _without_code_ticks(raw_id)
    if not claim_id:
        findings.append(Finding(path, line_number, "ID de claim ausente"))
    elif CLAIM_ID.fullmatch(claim_id) is None:
        findings.append(Finding(path, line_number, f"ID de claim inválido: {claim_id}"))

    fields_match = CLAIM_FIELDS.fullmatch(remainder.strip()) if separator else None
    if fields_match is None:
        fields_match = UNKNOWN_CLAIM_FIELDS.fullmatch(remainder.strip()) if separator else None

    if fields_match is None:
        findings.append(
            Finding(
                path,
                line_number,
                "linha de claim deve conter ID, afirmação, status e evidência",
            )
        )
        return None, findings

    statement = fields_match.group("statement").strip()
    status = _without_code_ticks(fields_match.group("status"))
    evidence = fields_match.group("evidence").strip()
    if not statement:
        findings.append(Finding(path, line_number, "afirmação da claim está vazia"))
    if status not in CLAIM_STATUSES:
        findings.append(
            Finding(path, line_number, f"status de claim fora do vocabulário: {status}")
        )
    if not evidence:
        findings.append(Finding(path, line_number, "evidência/escopo da claim está vazio"))

    return ClaimRow(claim_id, statement, status, evidence, line_number), findings


def iter_claim_rows(
    body: str,
    body_start_line: int,
    path: Path,
) -> tuple[list[ClaimRow], list[Finding], int, int, int]:
    """Percorre somente tabelas sob ``## Estado epistêmico``.

    Retorna linhas parseadas, achados, candidatas encontradas, candidatas inválidas
    e defeitos da tabela. Uma linha com ID ausente continua sendo candidata e
    portanto não some da contagem quando justamente é ela que está defeituosa.
    """

    rows: list[ClaimRow] = []
    findings: list[Finding] = []
    candidates = 0
    invalid_candidates = 0
    table_defects = 0
    in_section = False
    saw_header = False
    saw_separator = False
    section_line = 0

    def close_section() -> None:
        nonlocal table_defects
        if not in_section:
            return
        if not saw_header:
            findings.append(
                Finding(path, section_line, "seção Estado epistêmico não contém tabela")
            )
            table_defects += 1
        elif not saw_separator:
            findings.append(
                Finding(path, section_line, "tabela de claims não contém separador")
            )
            table_defects += 1

    for offset, line in enumerate(body.splitlines(), start=body_start_line):
        stripped = line.strip()
        if stripped == "## Estado epistêmico":
            close_section()
            in_section = True
            saw_header = False
            saw_separator = False
            section_line = offset
            continue
        if in_section and HEADING_LEVEL_ONE_OR_TWO.match(stripped):
            close_section()
            in_section = False
            continue
        if not in_section or not stripped.startswith("|"):
            continue
        if not saw_header:
            saw_header = True
            continue
        if not saw_separator:
            saw_separator = True
            if TABLE_SEPARATOR.fullmatch(stripped) is None:
                findings.append(
                    Finding(path, offset, "separador da tabela de claims é inválido")
                )
                table_defects += 1
            continue

        candidates += 1
        row, row_findings = parse_claim_row(line, offset, path)
        if row_findings:
            invalid_candidates += 1
            findings.extend(row_findings)
        if row is not None:
            rows.append(row)

    close_section()
    return rows, findings, candidates, invalid_candidates, table_defects


def _aliases(raw_frontmatter: str) -> list[str]:
    """Preserva a lista inline histórica sem reinterpretá-la como YAML."""

    match = re.search(r"^aliases:\s*\[(.*?)\]", raw_frontmatter, re.M)
    if match is None:
        return []
    return [
        alias
        for item in match.group(1).split(",")
        if (alias := item.strip().strip("'\""))
    ]


def _display_finding(root: Path, finding: Finding) -> str:
    try:
        path = finding.path.relative_to(root)
    except ValueError:
        path = finding.path
    return f"{path}:{finding.line}: {finding.message}"


CLAIM_ID_NA_LINHA = re.compile(r"CLM-[A-Z0-9]+-[A-Z0-9]+-[0-9]{3}")


def _volume_da_nota(texto: str) -> tuple[int, int, int]:
    """Claims, wikilinks e bytes de uma nota. É o que a redução apaga."""
    claims = len(set(CLAIM_ID_NA_LINHA.findall(texto)))
    return claims, len(WIKILINK.findall(texto)), len(texto.encode("utf-8"))


def _texto_na_referencia(repo: Path, ref: str, caminho: str) -> str | None:
    """A nota como ela estava naquela referência, ou `None` se ela não existia."""
    try:
        saida = subprocess.run(  # noqa: S603 — argumentos fixos, caminho do próprio repo
            ["git", "show", f"{ref}:{caminho}"],
            cwd=repo,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    return saida.stdout.decode("utf-8", "replace") if saida.returncode == 0 else None


def reducoes_desde(root: Path, ref: str) -> list[tuple[str, str]] | None:
    """O que cada nota perdeu desde `ref`.

    Existe porque o auditor é cego a destruição: ele confere se o que **sobrou** está bem
    formado, nunca se algo sumiu. Aplicando um patch que trocava uma nota de 73 linhas por
    um stub de dez, ele reprovava por um único sinal — frontmatter ausente —, enquanto os
    4 claims e os 5 wikilinks perdidos passavam calados. A guarda equivalente já existe no
    `ProposalPromoter`, e cobre só o caminho da promoção; edição direta de `knowledge/` não
    passa por ele.

    Devolve `None` quando não há repositório ou a referência não existe — não saber é
    diferente de não haver perda, e inventar aprovação seria pior que não medir.
    """
    repo = root
    while repo != repo.parent and not (repo / ".git").exists():
        repo = repo.parent
    if not (repo / ".git").exists():
        return None
    if subprocess.run(  # noqa: S603 — argumentos fixos
        ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
        cwd=repo,
        capture_output=True,
        check=False,
    ).returncode != 0:
        return None

    perdas: list[tuple[str, str]] = []
    for caminho in sorted(root.rglob("*.md")):
        if EXCLUDED_DIRS & set(caminho.parts) or caminho.name in EXCLUDED_FILES:
            continue
        relativo = caminho.relative_to(repo).as_posix()
        antes = _texto_na_referencia(repo, ref, relativo)
        if antes is None:
            continue
        c0, w0, b0 = _volume_da_nota(antes)
        c1, w1, b1 = _volume_da_nota(caminho.read_text(encoding="utf-8"))
        quedas = []
        if c1 < c0:
            quedas.append(f"claims {c0}→{c1}")
        if w1 < w0:
            quedas.append(f"wikilinks {w0}→{w1}")
        if b1 * 2 < b0:
            quedas.append(f"bytes {b0}→{b1}")
        if quedas:
            perdas.append((relativo, ", ".join(quedas)))
    return perdas


def audit(root: Path, *, contra: str | None = None) -> int:
    root = root.resolve()
    if not root.is_dir():
        print(f"corpus não encontrado: {root}", file=sys.stderr)
        return 1

    files = sorted(
        path
        for path in root.rglob("*.md")
        if not EXCLUDED_DIRS & set(path.parts) and path.name not in EXCLUDED_FILES
    )
    names = {path.stem for path in files}
    stem_counts = Counter(path.stem for path in files)
    duplicate_stems = sorted(stem for stem, count in stem_counts.items() if count > 1)
    aliases: dict[str, str] = {}
    fm_invalid_files: set[Path] = set()
    fm_kinds: dict[Path, str | None] = {}
    frontmatter_findings: list[Finding] = []
    review_expired: list[Finding] = []
    claim_findings: list[Finding] = []
    links_total = 0
    broken: list[tuple[Path, str]] = []
    no_relation: list[tuple[Path, str]] = []
    bad_relation: list[tuple[Path, str, str]] = []
    linked_to: set[str] = set()
    claim_lines = 0
    invalid_claim_rows = 0
    invalid_claim_tables = 0
    claim_ids: Counter[str] = Counter()
    moc_without_links: list[Path] = []

    for path in files:
        text = path.read_text(encoding="utf-8")
        parsed = parse_frontmatter(text, path)
        fm_kinds[path] = parsed.fields.get("kind")
        if parsed.findings:
            fm_invalid_files.add(path)
        frontmatter_findings.extend(parsed.findings)
        review_expired.extend(parsed.expirations)
        for alias in _aliases(parsed.raw):
            aliases[alias] = path.stem

        file_links = 0
        for line in parsed.body.splitlines():
            found = WIKILINK.findall(line)
            if not found:
                continue
            relation = RELATION.search(line)
            for target in found:
                links_total += 1
                file_links += 1
                normalized_target = target.strip()
                resolved = (
                    normalized_target
                    if normalized_target in names
                    else aliases.get(normalized_target)
                )
                if resolved is None:
                    broken.append((path, normalized_target))
                else:
                    linked_to.add(resolved)
                if relation is None:
                    no_relation.append((path, normalized_target))
                elif relation.group(1) not in ALLOWED_RELATIONS:
                    bad_relation.append((path, normalized_target, relation.group(1)))

        rows, findings, candidates, invalid, table_defects = iter_claim_rows(
            parsed.body,
            parsed.body_start_line,
            path,
        )
        claim_lines += candidates
        invalid_claim_rows += invalid
        invalid_claim_tables += table_defects
        claim_findings.extend(findings)
        for row in rows:
            if CLAIM_ID.fullmatch(row.claim_id):
                claim_ids[row.claim_id] += 1

        if fm_kinds.get(path) == "moc" and file_links == 0:
            moc_without_links.append(path)

    orphans = sorted(
        path.stem for path in files if path.stem not in linked_to and path.stem != "Índice"
    )

    manifest = "\n".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root)}"
        for path in files
    )
    manifest_sha = hashlib.sha256(manifest.encode()).hexdigest()

    print(f"notas markdown ................. {len(files)}")
    print(f"nomes de nota duplicados ....... {len(duplicate_stems)}")
    if duplicate_stems:
        print(f"  !! NOMES DUPLICADOS: {duplicate_stems}")
    print(f"documentos na raiz ............. {sum(1 for path in files if path.parent == root)}")
    print(f"wikilinks ...................... {links_total}")
    print(f"wikilinks quebrados ............ {len(broken)}")
    print(f"wikilinks sem relation: ........ {len(no_relation)}")
    print(f"relation: fora do vocabulário .. {len(bad_relation)}")
    print(f"notas órfãs .................... {len(orphans)}")
    print(f"MOCs sem links ................. {len(moc_without_links)}")
    print(f"frontmatter ausente/inválido ... {len(fm_invalid_files)}")
    print(f"linhas definidoras de claims ... {claim_lines}")
    claim_defects = invalid_claim_rows + invalid_claim_tables
    print(f"claims inválidos ............... {claim_defects}")
    print(f"IDs de claim únicos ............ {len(claim_ids)}")
    duplicates = {claim_id: count for claim_id, count in claim_ids.items() if count > 1}
    print(
        "IDs de claim duplicados ........ "
        f"{len(duplicates)} {sorted(duplicates) if duplicates else ''}"
    )
    print(f"review_after vencidos ........... {len(review_expired)}")
    for vencido in review_expired[:10]:
        print(f"  !! VENCIDO: {_display_finding(root, vencido)}")

    for label, items in (("QUEBRADO", broken), ("SEM RELATION", no_relation)):
        for entry in items[:10]:
            print(f"  !! {label}: {entry}")
    if orphans:
        print(f"  !! ÓRFÃS: {orphans}")
    all_findings = sorted(
        (*frontmatter_findings, *review_expired, *claim_findings),
        key=lambda finding: (finding.path.as_posix(), finding.line, finding.message),
    )
    for finding in all_findings[:20]:
        print(f"  !! ESTRUTURA: {_display_finding(root, finding)}")
    if len(all_findings) > 20:
        print(f"  !! ESTRUTURA: mais {len(all_findings) - 20} achado(s) omitido(s)")

    print(f"\nSHA-256 do manifesto ........... {manifest_sha}")

    reducoes = reducoes_desde(root, contra) if contra else None
    if contra:
        if reducoes is None:
            print(
                f"\nREDUÇÃO NÃO MEDIDA — sem repositório ou referência `{contra}` "
                "inexistente; não saber não é o mesmo que não haver perda."
            )
        else:
            print(f"\nnotas que perderam conteúdo desde {contra} ... {len(reducoes)}")
            for caminho, queda in reducoes[:20]:
                print(f"  !! REDUÇÃO: {caminho}: {queda}")

    defects = {
        "nomes de nota duplicados": len(duplicate_stems),
        "wikilinks quebrados": len(broken),
        "wikilinks sem relation:": len(no_relation),
        "relation: fora do vocabulário": len(bad_relation),
        "notas órfãs": len(orphans),
        "MOCs sem links": len(moc_without_links),
        "frontmatter ausente/inválido": len(fm_invalid_files),
        "claims inválidos": claim_defects,
        "IDs de claim duplicados": len(duplicates),
        "review_after vencidos": len(review_expired),
        **({"reduções não declaradas": len(reducoes)} if reducoes else {}),
    }
    failed = {label: count for label, count in defects.items() if count}
    if failed:
        print(
            "\nESTRUTURA REPROVADA — "
            + "; ".join(f"{label}: {count}" for label, count in sorted(failed.items()))
        )
    else:
        print(
            "\nESTRUTURA APROVADA — nenhuma das categorias estruturais "
            "implementadas acusou defeito."
        )
    print(
        "FONTES EXTERNAS NÃO VERIFICADAS — nenhuma resolução DOI/arXiv/ISBN "
        "ou conferência de título foi executada."
    )
    return 1 if failed else 0


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    contra: str | None = None
    restantes: list[str] = []
    for argumento in arguments:
        if argumento.startswith("--contra="):
            contra = argumento.split("=", 1)[1]
        else:
            restantes.append(argumento)
    if len(restantes) > 1:
        print("uso: audit.py [caminho-do-corpus] [--contra=REF]", file=sys.stderr)
        return 1
    root = Path(restantes[0]) if restantes else DEFAULT_ROOT
    return audit(root, contra=contra)


if __name__ == "__main__":
    raise SystemExit(main())
