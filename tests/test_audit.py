"""Regressões do gate estrutural independente e deliberadamente offline."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

NOTE_PATH = Path("Matemática/Álgebra Linear.md")
CLAIM_ID = "CLM-MAT-ALGLIN-001"


def run_audit(repo_root: Path, corpus: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — script e argumentos controlados pelo teste
        [sys.executable, str(repo_root / "tools" / "audit.py"), str(corpus)],
        capture_output=True,
        text=True,
        check=False,
    )


def corpus_copy(tmp_path: Path, corpus_dir: Path) -> Path:
    destination = tmp_path / "knowledge"
    shutil.copytree(corpus_dir, destination)
    return destination


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"trecho não único em {path}: {old!r}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def rewrite_claim(
    path: Path,
    transform: Callable[[str, str, str, str], tuple[str, str, str, str]],
) -> None:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^\|\s*`(?P<claim_id>{re.escape(CLAIM_ID)})`\s*\|"
        rf"\s*(?P<statement>.*?)\|\s*(?P<status>`?established`?)\s*\|"
        rf"(?P<evidence>.*)\|\s*$",
        re.M,
    )
    match = pattern.search(text)
    assert match is not None
    claim_id, statement, status, evidence = transform(
        match.group("claim_id"),
        match.group("statement").strip(),
        match.group("status").strip(),
        match.group("evidence").strip(),
    )
    id_cell = f"`{claim_id}`" if claim_id else ""
    replacement = f"| {id_cell} | {statement} | {status} | {evidence} |"
    path.write_text(text[: match.start()] + replacement + text[match.end() :], encoding="utf-8")


def assert_reproved(completed: subprocess.CompletedProcess[str], message: str) -> None:
    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "ESTRUTURA REPROVADA" in completed.stdout
    assert message in completed.stdout
    assert "FONTES EXTERNAS NÃO VERIFICADAS" in completed.stdout


def test_corpus_canonico_preserva_contagens_e_aprova_estrutura(
    tmp_path: Path,
    corpus_dir: Path,
    repo_root: Path,
) -> None:
    corpus = corpus_copy(tmp_path, corpus_dir)

    completed = run_audit(repo_root, corpus)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "notas markdown ................. 84" in completed.stdout
    assert "wikilinks ...................... 672" in completed.stdout
    assert "linhas definidoras de claims ... 267" in completed.stdout
    assert "claims inválidos ............... 0" in completed.stdout
    assert "ESTRUTURA APROVADA" in completed.stdout


@pytest.mark.parametrize("replacement", ["", "title:\n"])
def test_title_ausente_ou_vazio_reprova(
    replacement: str,
    tmp_path: Path,
    corpus_dir: Path,
    repo_root: Path,
) -> None:
    corpus = corpus_copy(tmp_path, corpus_dir)
    replace_once(corpus / NOTE_PATH, "title: Álgebra Linear\n", replacement)

    completed = run_audit(repo_root, corpus)

    assert_reproved(completed, "campo obrigatório ausente ou vazio: title")
    assert "frontmatter ausente/inválido ... 1" in completed.stdout


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("kind: nota\n", "kind: esboço\n", "kind fora do vocabulário: esboço"),
        ("status: active\n", "status: provisório\n", "status fora do vocabulário"),
        (
            "epistemic_status: established\n",
            "epistemic_status: certeza\n",
            "epistemic_status fora do vocabulário",
        ),
    ],
)
def test_vocabularios_do_frontmatter_sao_fechados(
    old: str,
    new: str,
    message: str,
    tmp_path: Path,
    corpus_dir: Path,
    repo_root: Path,
) -> None:
    corpus = corpus_copy(tmp_path, corpus_dir)
    replace_once(corpus / NOTE_PATH, old, new)

    completed = run_audit(repo_root, corpus)

    assert_reproved(completed, message)


def test_data_impossivel_reprova(
    tmp_path: Path,
    corpus_dir: Path,
    repo_root: Path,
) -> None:
    corpus = corpus_copy(tmp_path, corpus_dir)
    replace_once(corpus / NOTE_PATH, "updated: 2026-07-18\n", "updated: 2026-02-30\n")

    completed = run_audit(repo_root, corpus)

    assert_reproved(completed, "updated não é uma data ISO válida: 2026-02-30")


def test_claim_sem_id_reprova(
    tmp_path: Path,
    corpus_dir: Path,
    repo_root: Path,
) -> None:
    corpus = corpus_copy(tmp_path, corpus_dir)
    rewrite_claim(
        corpus / NOTE_PATH,
        lambda _claim_id, statement, status, evidence: ("", statement, status, evidence),
    )

    completed = run_audit(repo_root, corpus)

    assert_reproved(completed, "ID de claim ausente")
    assert "linhas definidoras de claims ... 267" in completed.stdout
    assert "claims inválidos ............... 1" in completed.stdout
    assert "IDs de claim únicos ............ 266" in completed.stdout


def test_claim_com_id_malformado_reprova(
    tmp_path: Path,
    corpus_dir: Path,
    repo_root: Path,
) -> None:
    corpus = corpus_copy(tmp_path, corpus_dir)
    rewrite_claim(
        corpus / NOTE_PATH,
        lambda _claim_id, statement, status, evidence: (
            "CLM-MAT-ALGLIN-1",
            statement,
            status,
            evidence,
        ),
    )

    completed = run_audit(repo_root, corpus)

    assert_reproved(completed, "ID de claim inválido: CLM-MAT-ALGLIN-1")


def test_claim_com_status_inventado_reprova(
    tmp_path: Path,
    corpus_dir: Path,
    repo_root: Path,
) -> None:
    corpus = corpus_copy(tmp_path, corpus_dir)
    rewrite_claim(
        corpus / NOTE_PATH,
        lambda claim_id, statement, _status, evidence: (
            claim_id,
            statement,
            "invented",
            evidence,
        ),
    )

    completed = run_audit(repo_root, corpus)

    assert_reproved(completed, "status de claim fora do vocabulário: invented")


def test_separador_invalido_da_tabela_de_claims_reprova(
    tmp_path: Path,
    corpus_dir: Path,
    repo_root: Path,
) -> None:
    corpus = corpus_copy(tmp_path, corpus_dir)
    replace_once(
        corpus / NOTE_PATH,
        "|---|---|---|---|\n",
        "|---|---|---|\n",
    )

    completed = run_audit(repo_root, corpus)

    assert_reproved(completed, "separador da tabela de claims é inválido")
    assert "claims inválidos ............... 1" in completed.stdout


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("statement", "afirmação da claim está vazia"),
        ("evidence", "evidência/escopo da claim está vazio"),
    ],
)
def test_claim_sem_afirmacao_ou_evidencia_reprova(
    field: str,
    message: str,
    tmp_path: Path,
    corpus_dir: Path,
    repo_root: Path,
) -> None:
    corpus = corpus_copy(tmp_path, corpus_dir)

    def remove_field(
        claim_id: str,
        statement: str,
        status: str,
        evidence: str,
    ) -> tuple[str, str, str, str]:
        if field == "statement":
            statement = ""
        else:
            evidence = ""
        return claim_id, statement, status, evidence

    rewrite_claim(corpus / NOTE_PATH, remove_field)

    completed = run_audit(repo_root, corpus)

    assert_reproved(completed, message)


def test_claim_aceita_crases_e_pipes_internos(
    tmp_path: Path,
    corpus_dir: Path,
    repo_root: Path,
) -> None:
    corpus = corpus_copy(tmp_path, corpus_dir)
    rewrite_claim(
        corpus / NOTE_PATH,
        lambda claim_id, _statement, _status, _evidence: (
            claim_id,
            "Relação `A | B`.",
            "`supported`",
            "Fonte `C | D`; A | B.",
        ),
    )

    completed = run_audit(repo_root, corpus)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "claims inválidos ............... 0" in completed.stdout
    assert "linhas definidoras de claims ... 267" in completed.stdout


def test_auditor_declara_fontes_externas_nao_verificadas(
    tmp_path: Path,
    corpus_dir: Path,
    repo_root: Path,
) -> None:
    corpus = corpus_copy(tmp_path, corpus_dir)
    note = corpus / NOTE_PATH
    note.write_text(
        note.read_text(encoding="utf-8") + "\nReferência estrutural: DOI 10.0000/audit-fake.\n",
        encoding="utf-8",
    )

    completed = run_audit(repo_root, corpus)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (
        "FONTES EXTERNAS NÃO VERIFICADAS — nenhuma resolução DOI/arXiv/ISBN "
        "ou conferência de título foi executada."
    ) in completed.stdout


class TestGuardaDeReducao:
    """O auditor confere se o que sobrou está bem formado; não se algo sumiu.

    A guarda equivalente já existia no `ProposalPromoter` e cobria só o caminho da
    promoção. Edição direta de `knowledge/` não passa por ele — e foi por isso que um
    stub de dez linhas no lugar de uma nota de 73 reprovava por um único sinal.
    """

    def _repo(self, tmp_path: Path, corpus_dir: Path) -> Path:
        repo = tmp_path / "repo"
        (repo / "knowledge").mkdir(parents=True)
        shutil.copytree(corpus_dir, repo / "knowledge", dirs_exist_ok=True)
        for comando in (
            ["git", "init", "-q"],
            ["git", "config", "user.email", "t@t"],
            ["git", "config", "user.name", "t"],
            ["git", "add", "-A"],
            ["git", "commit", "-qm", "base"],
        ):
            subprocess.run(comando, cwd=repo, check=True, capture_output=True)  # noqa: S603
        return repo

    def _auditar(
        self, repo_root: Path, corpus: Path, ref: str | None
    ) -> subprocess.CompletedProcess[str]:
        argumentos = [sys.executable, str(repo_root / "tools" / "audit.py"), str(corpus)]
        if ref:
            argumentos.append(f"--contra={ref}")
        return subprocess.run(argumentos, capture_output=True, text=True, check=False)  # noqa: S603

    def test_stub_no_lugar_da_nota_e_reprovado_pelos_tres_sinais(
        self, tmp_path: Path, repo_root: Path, corpus_dir: Path
    ) -> None:
        repo = self._repo(tmp_path, corpus_dir)
        alvo = repo / "knowledge" / NOTE_PATH
        alvo.write_text(
            "Especificação não solicitada.\n\n... (resto mantido igual) ...\n",
            encoding="utf-8",
        )
        resultado = self._auditar(repo_root, repo / "knowledge", "HEAD")
        assert resultado.returncode == 1
        assert "REDUÇÃO" in resultado.stdout
        assert "claims" in resultado.stdout
        assert "wikilinks" in resultado.stdout
        assert "reduções não declaradas" in resultado.stdout

    def test_sem_a_flag_a_reducao_nao_e_medida(
        self, tmp_path: Path, repo_root: Path, corpus_dir: Path
    ) -> None:
        """O script continua opt-in; o `make audit` é que passou a optar por HEAD."""
        repo = self._repo(tmp_path, corpus_dir)
        (repo / "knowledge" / NOTE_PATH).write_text("Só isto.\n", encoding="utf-8")
        assert "REDUÇÃO" not in self._auditar(repo_root, repo / "knowledge", None).stdout

    def test_corpus_intacto_nao_acusa_reducao(
        self, tmp_path: Path, repo_root: Path, corpus_dir: Path
    ) -> None:
        repo = self._repo(tmp_path, corpus_dir)
        resultado = self._auditar(repo_root, repo / "knowledge", "HEAD")
        assert resultado.returncode == 0
        assert "perderam conteúdo desde HEAD ... 0" in resultado.stdout

    def test_referencia_inexistente_diz_que_nao_mediu(
        self, tmp_path: Path, repo_root: Path, corpus_dir: Path
    ) -> None:
        """Não saber é diferente de não haver perda, e a saída precisa distinguir."""
        repo = self._repo(tmp_path, corpus_dir)
        resultado = self._auditar(repo_root, repo / "knowledge", "nao-existe")
        assert "REDUÇÃO NÃO MEDIDA" in resultado.stdout


def nota_minima(
    diretorio: Path,
    nome: str,
    *,
    extra: str = "",
    corpo: str = "",
) -> Path:
    """Uma nota com o frontmatter mínimo que o auditor exige, para corpora sintéticos."""
    nota = diretorio / f"{nome}.md"
    nota.write_text(
        "---\n"
        "title: T\n"
        "domain: teste\n"
        "kind: nota\n"
        "status: active\n"
        "epistemic_status: operational\n"
        "updated: 2026-08-16\n"
        f"{extra}"
        "---\n"
        f"{corpo}",
        encoding="utf-8",
    )
    return nota


def test_review_after_vencido_reprova(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    corpus = tmp_path / "knowledge"
    corpus.mkdir()
    nota_minima(corpus, "Índice", extra="review_after: 2020-01-01\n")

    completed = run_audit(repo_root, corpus)

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "review_after vencidos ........... 1" in completed.stdout
    assert "!! VENCIDO: Índice.md:8: review_after vencido" in completed.stdout
    assert "review_after vencidos: 1" in completed.stdout


def test_review_after_futuro_passa_e_review_after_invalido_reprova(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    futuro = tmp_path / "futuro"
    futuro.mkdir()
    nota_minima(futuro, "Índice", extra="review_after: 2099-01-01\n")
    completed = run_audit(repo_root, futuro)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "review_after vencidos ........... 0" in completed.stdout

    invalido = tmp_path / "invalido"
    invalido.mkdir()
    nota_minima(invalido, "Índice", extra="review_after: 2026-13-40\n")
    completed = run_audit(repo_root, invalido)
    assert completed.returncode == 1
    assert "review_after não é uma data ISO válida: 2026-13-40" in completed.stdout


def test_nomes_de_nota_duplicados_reprovam(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Mesmo stem em pastas diferentes torna o wikilink ambíguo; o auditor acusa."""
    corpus = tmp_path / "knowledge"
    (corpus / "A").mkdir(parents=True)
    (corpus / "B").mkdir()
    nota_minima(corpus / "A", "Índice")
    nota_minima(corpus / "A", "X", corpo="[[Índice]] <!-- relation:navigation -->\n")
    nota_minima(corpus / "B", "X", corpo="[[Índice]] <!-- relation:navigation -->\n")

    completed = run_audit(repo_root, corpus)

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "nomes de nota duplicados ....... 1" in completed.stdout
    assert "!! NOMES DUPLICADOS: ['X']" in completed.stdout
    assert "nomes de nota duplicados: 1" in completed.stdout
