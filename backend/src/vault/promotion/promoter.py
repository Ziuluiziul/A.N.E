"""Proposal Promoter: o único componente autorizado a escrever em `knowledge/`.

Ele existe porque o corpus é fechado à escrita direta. Nenhum agente edita a nota;
o caminho é sempre proposta → quórum → Promoter. E como é o único que escreve, ele é
o lugar onde uma decisão inválida precisa morrer.

O que ele recusa, e por que cada recusa existe:

- **decisão gravada que não confere.** O quórum é recomputado a partir dos votos, não
  lido de `decision.json`. Confiar no arquivo faria bastar editá-lo para promover.
- **proponente entre os avaliadores.** Um modelo que valida a própria proposta produz
  concordância, não verificação.
- **diversidade abaixo do mínimo.** Três instâncias do mesmo modelo concordariam
  consigo mesmas.
- **patch diferente do avaliado.** O digest viaja no painel; qualquer byte trocado
  depois do voto muda o digest e o Promoter para.
- **alvo mudou desde a base.** Commit alheio não invalida o patch; o que invalida é
  a nota votada ter sido reescrita. HEAD diferente sem tocar os alvos ainda é o
  contexto que os avaliadores leram.
- **diff além dos alvos declarados.** O que entra tem que ser exatamente o que foi
  declarado, arquivo por arquivo.

A aplicação acontece numa árvore de trabalho temporária do Git. O corpus vivo só se
move por avanço rápido, depois de auditoria e projeção terem passado sobre o
resultado — nunca fica meio escrito. Reversão é `git revert`, commit compensatório
que preserva o histórico.
"""

from __future__ import annotations

import fcntl
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vault.events import EventType
from vault.promotion.code_patch import CodePatch, CodePatchRefused
from vault.promotion.patch import CorpusPatch, PatchRefused
from vault.quorum.engine import MIN_FAMILIES, MIN_PROVIDERS, MIN_VALID_VOTES, decide_panel
from vault.quorum.models import DecisionStatus, Panel, RecommendedAction

PATCH_DIGEST_KEY = "patch_digest"
PROVENANCE_NAME = "promotion.json"

EventEmitter = Callable[[EventType, dict[str, Any]], None]


def _silent_event(_kind: EventType, _payload: dict[str, Any]) -> None:
    return None


class PromotionRefused(RuntimeError):
    """A promoção não acontece. A mensagem diz qual guarda recusou."""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _git(*args: str, cwd: Path) -> str:
    resultado = subprocess.run(  # noqa: S603 — argumentos fixos, sem shell
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if resultado.returncode != 0:
        detalhe = (resultado.stderr or resultado.stdout).strip()
        raise PromotionRefused(f"git {' '.join(args)} falhou: {detalhe}")
    return resultado.stdout.strip()


@dataclass(frozen=True, slots=True)
class PromotionResult:
    panel_id: str
    proposal_id: str
    commit: str
    base_commit: str
    targets: list[str]
    patch_digest: str
    reviewers: list[str]
    providers: list[str]
    families: list[str]
    decided_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "panel_id": self.panel_id,
            "proposal_id": self.proposal_id,
            "commit": self.commit,
            "base_commit": self.base_commit,
            "targets": self.targets,
            "patch_digest": self.patch_digest,
            "reviewers": self.reviewers,
            "providers": self.providers,
            "families": self.families,
            "decided_at": self.decided_at,
        }


def verify_quorum(panel: Panel, patch: CorpusPatch) -> None:
    """Recomputa o quórum e confere a amarra entre painel, votos e patch."""
    if patch.proposal_id != panel.proposal.id:
        raise PromotionRefused(
            f"patch pertence a outra proposta: {patch.proposal_id} ≠ {panel.proposal.id}"
        )

    esperado = panel.task.context.get(PATCH_DIGEST_KEY)
    if not isinstance(esperado, str) or not esperado:
        raise PromotionRefused("o painel não registrou o digest do patch avaliado")
    if esperado != patch.digest():
        raise PromotionRefused(
            "o patch não é o que foi avaliado: digest diverge do registrado no painel"
        )

    proponente = panel.proposal.proposer.key
    avaliadores = [vote.reviewer.key for vote in panel.votes]
    if proponente in avaliadores:
        raise PromotionRefused(
            f"o proponente {proponente} aparece entre os avaliadores da própria proposta"
        )
    if len(set(avaliadores)) != len(avaliadores):
        raise PromotionRefused("há voto duplicado do mesmo endpoint no painel")

    decisao = decide_panel(panel)
    if decisao.status is not DecisionStatus.DECIDED:
        raise PromotionRefused(f"quórum não concluiu: {decisao.reason}")
    if decisao.outcome is not RecommendedAction.PROMOTE:
        raise PromotionRefused(
            f"quórum não aprovou: {decisao.outcome.value} — {decisao.reason}"
        )
    if decisao.valid_vote_count < MIN_VALID_VOTES:
        raise PromotionRefused(
            f"{decisao.valid_vote_count} votos válidos; mínimo é {MIN_VALID_VOTES}"
        )
    if decisao.provider_count < MIN_PROVIDERS or decisao.family_count < MIN_FAMILIES:
        raise PromotionRefused(
            f"diversidade insuficiente: {decisao.provider_count} provedor(es), "
            f"{decisao.family_count} família(s)"
        )


@dataclass(frozen=True, slots=True)
class ProposalPromoter:
    """Aplica um patch aprovado. Só isso, e só quando todas as guardas passam."""

    repo_root: Path
    corpus_relative: str = "knowledge"
    audit_script: str = "tools/audit.py"
    emit: EventEmitter = _silent_event

    @contextmanager
    def _promotion_lock(self) -> Iterator[None]:
        """Trava exclusiva de repositório: o avanço do `main` é atômico.

        A validação do patch ocorre contra um `HEAD` capturado; o commit nasce numa
        worktree e o corpus vivo só avança por `merge --ff-only`. Sem serialização,
        dois promotores podem ler o mesmo `HEAD`, produzir filhos diferentes dele e
        apenas o primeiro consegue avançar `main` — o segundo falha com "diverging
        branches". O lock cobre o trecho inteiro cuja atomicidade depende do `HEAD`
        (pré-condição → capturar HEAD → worktree → commit → ff-update → resultado),
        então o commit validado é precisamente aquele que ganha autoridade para
        avançar o corpus. Padrão idêntico ao de `proposals/store.py`/`queue.py`.

        A trava vive no *common dir* do Git (``git rev-parse --git-common-dir``), não em
        ``.git`` fixo, para ser compartilhada entre worktrees ligados ao mesmo repositório
        e entre processos distintos (``flock`` é por descritor, válido entre processos).
        O arquivo fica dentro da área do Git, ignorado pelo ``git status``. A promoção
        não inspeciona a working tree do operador: commit nasce na worktree temporária
        e o corpus vivo avança por ``merge --ff-only``. ``_exige_arvore_limpa`` resta
        só para ``revert``, que escreve no checkout do operador.
        """
        common = Path(
            _git("rev-parse", "--git-common-dir", cwd=self.repo_root).strip()
        )
        if not common.is_absolute():
            common = self.repo_root / common
        common.mkdir(parents=True, exist_ok=True)
        lock_path = common / "promotion.lock"
        flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW
        descritor = os.open(lock_path, flags, 0o600)
        try:
            os.fchmod(descritor, 0o600)
            fcntl.flock(descritor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descritor, fcntl.LOCK_UN)
            os.close(descritor)

    def _corpus(self, tree: Path) -> Path:
        return tree / self.corpus_relative

    def head(self) -> str:
        return _git("rev-parse", "HEAD", cwd=self.repo_root)

    def _exige_arvore_limpa(self) -> None:
        sujo = _git("status", "--porcelain", cwd=self.repo_root)
        if sujo:
            raise PromotionRefused(
                "árvore de trabalho suja; promoção automática exige repositório limpo"
            )

    def _resolver_base(self, patch: CorpusPatch, head: str) -> str:
        try:
            return _git(
                "rev-parse",
                "--verify",
                f"{patch.base_commit}^{{commit}}",
                cwd=self.repo_root,
            )
        except PromotionRefused as error:
            raise PromotionRefused(
                f"base divergente: patch feito sobre {patch.base_commit}, HEAD é {head}"
            ) from error

    def _alvos_tocados_desde_a_base(self, patch: CorpusPatch, head: str) -> list[str]:
        base = self._resolver_base(patch, head)
        if head.startswith(base) or base.startswith(head):
            return []
        caminhos = [f"{self.corpus_relative}/{alvo}" for alvo in patch.targets]
        tocados = _git(
            "diff",
            "--name-only",
            f"{base}..{head}",
            "--",
            *caminhos,
            cwd=self.repo_root,
        )
        return [linha for linha in tocados.splitlines() if linha]

    def _conferir_precondicoes(self, panel: Panel, patch: CorpusPatch) -> str:
        verify_quorum(panel, patch)
        head = self.head()
        tocados = self._alvos_tocados_desde_a_base(patch, head)
        if tocados:
            raise PromotionRefused(
                f"alvo mudou desde a base {patch.base_commit[:12]}: {', '.join(tocados)}"
            )
        return head

    def validate(self, panel: Panel, patch: CorpusPatch) -> None:
        """Roda as guardas reais sem commitar e sem avançar o corpus vivo."""
        head = self._conferir_precondicoes(panel, patch)
        temporario = Path(tempfile.mkdtemp(prefix="vault-promotion-"))
        arvore = temporario / "tree"
        worktree_created = False
        try:
            _git("worktree", "add", "--detach", str(arvore), head, cwd=self.repo_root)
            worktree_created = True
            self._aplicar_e_validar(arvore, patch)
        finally:
            if worktree_created:
                _git("worktree", "remove", "--force", str(arvore), cwd=self.repo_root)
            shutil.rmtree(temporario, ignore_errors=True)

    def admit_patch(self, patch: CorpusPatch) -> str | None:
        """Guarda pré-quórum: só entra no painel o que poderia ser promovido.

        Roda as mesmas guardas do commit (`_aplicar_e_validar`) contra uma
        worktree temporária: diff real, só alvos declarados, sem redução não
        autorizada, auditoria estrutural e projeção. Devolve a razão da recusa,
        ou None para admitir.

        Não exige árvore de trabalho limpa nem painel — aqui não há commit ainda.
        O quórum deve julgar mérito epistêmico, não gastar três avaliadores para
        descobrir que o patch é vazio, toca um alvo errado ou quebra um wikilink.
        """
        try:
            head = self.head()
        except PromotionRefused as error:
            return str(error)
        temporario = Path(tempfile.mkdtemp(prefix="vault-admission-"))
        arvore = temporario / "tree"
        worktree_created = False
        try:
            _git("worktree", "add", "--detach", str(arvore), head, cwd=self.repo_root)
            worktree_created = True
            self._aplicar_e_validar(arvore, patch)
        except PromotionRefused as error:
            return str(error)
        finally:
            if worktree_created:
                _git("worktree", "remove", "--force", str(arvore), cwd=self.repo_root)
            shutil.rmtree(temporario, ignore_errors=True)
        return None

    def promote(
        self,
        panel: Panel,
        patch: CorpusPatch,
        *,
        message: str | None = None,
    ) -> PromotionResult:
        """Do quórum ao commit. Levanta `PromotionRefused` antes de qualquer escrita."""
        with self._promotion_lock():
            head = self._conferir_precondicoes(panel, patch)

            event_base = {
                "actor": "proposal-promoter",
                "task": panel.task.id,
                # Um evento possui um único alvo espacial. Os demais continuam na lista
                # estruturada de targets, mas não viram uma identidade concatenada falsa.
                "entity": patch.targets[0].removesuffix(".md"),
            }
            self.emit(
                "promotion_started",
                {
                    **event_base,
                    "before": {"state": "approved", "commit": head},
                    "after": {"state": "validating"},
                    "metadata": {
                        "panel_id": panel.id,
                        "proposal_id": panel.proposal.id,
                        "patch_digest": patch.digest(),
                        "targets": patch.targets,
                    },
                },
            )

            temporario = Path(tempfile.mkdtemp(prefix="vault-promotion-"))
            arvore = temporario / "tree"
            completed = False
            worktree_created = False
            try:
                _git("worktree", "add", "--detach", str(arvore), head, cwd=self.repo_root)
                worktree_created = True
                self.emit(
                    "temporary_created",
                    {
                        **event_base,
                        "before": {},
                        "after": {"state": "worktree_ready"},
                        "metadata": {"panel_id": panel.id, "artifact": "promotion-worktree"},
                    },
                )
                try:
                    commit = self._validar_e_commitar(arvore, patch, panel, message)
                    self.emit(
                        "commit_created",
                        {
                            **event_base,
                            "before": {"commit": head},
                            "after": {"commit": commit},
                            "metadata": {"panel_id": panel.id, "targets": patch.targets},
                        },
                    )
                    # Avanço rápido: o corpus vivo nunca fica meio escrito, porque o que
                    # se move é o ponteiro, e só depois de tudo ter passado na temporária.
                    _git("merge", "--ff-only", commit, cwd=self.repo_root)
                    self.emit(
                        "corpus_changed",
                        {
                            **event_base,
                            "before": {"commit": head},
                            "after": {"commit": commit},
                            "metadata": {"panel_id": panel.id, "targets": patch.targets},
                        },
                    )
                    completed = True
                finally:
                    _git("worktree", "remove", "--force", str(arvore), cwd=self.repo_root)
            except Exception as error:
                self.emit(
                    "promotion_completed",
                    {
                        **event_base,
                        "before": {"state": "validating", "commit": head},
                        "after": {"state": "refused"},
                        "metadata": {
                            "panel_id": panel.id,
                            "error_type": type(error).__name__,
                            "detail": str(error)[:1_000],
                        },
                    },
                )
                raise
            finally:
                shutil.rmtree(temporario, ignore_errors=True)
                if worktree_created:
                    self.emit(
                        "temporary_discarded",
                        {
                            **event_base,
                            "before": {"state": "worktree_ready"},
                            "after": {"state": "discarded"},
                            "metadata": {
                                "panel_id": panel.id,
                                "artifact": "promotion-worktree",
                            },
                        },
                    )

            if not completed:
                # Fluxos excepcionais não chegam aqui, mas a guarda documenta que um
                # resultado nunca pode ser devolvido sem o avanço rápido ter ocorrido.
                raise PromotionRefused("promoção terminou sem avançar o corpus")

            result = PromotionResult(
                panel_id=panel.id,
                proposal_id=panel.proposal.id,
                commit=commit,
                base_commit=head,
                targets=patch.targets,
                patch_digest=patch.digest(),
                reviewers=sorted({vote.reviewer.key for vote in panel.votes}),
                providers=sorted({vote.reviewer.provider for vote in panel.votes}),
                families=sorted({vote.reviewer.family for vote in panel.votes}),
            )
            self.emit(
                "promotion_completed",
                {
                    **event_base,
                    "before": {"state": "validating", "commit": head},
                    "after": {"state": "promoted", "commit": result.commit},
                    "metadata": {
                        "panel_id": panel.id,
                        "proposal_id": panel.proposal.id,
                        "targets": result.targets,
                        "providers": result.providers,
                        "families": result.families,
                    },
                },
            )
            return result

    def _aplicar_e_validar(self, arvore: Path, patch: CorpusPatch) -> None:
        try:
            patch.apply_to(self._corpus(arvore))
        except PatchRefused as error:
            raise PromotionRefused(str(error)) from error

        self._auditar(arvore)
        self._projetar(arvore)

        _git("add", "-A", "--", self.corpus_relative, cwd=arvore)
        tocados = sorted(
            linha
            for linha in _git("diff", "--cached", "--name-only", cwd=arvore).splitlines()
        )
        declarados = sorted(f"{self.corpus_relative}/{alvo}" for alvo in patch.targets)
        if tocados != declarados:
            raise PromotionRefused(
                f"diff fora dos alvos declarados: {tocados} ≠ {declarados}"
            )
        residuo = _git("status", "--porcelain", cwd=arvore).splitlines()
        fora = [linha for linha in residuo if not linha.strip().startswith(("A ", "M "))]
        if fora:
            raise PromotionRefused(f"a árvore temporária tem alteração inesperada: {fora}")

    def _validar_e_commitar(
        self,
        arvore: Path,
        patch: CorpusPatch,
        panel: Panel,
        message: str | None,
    ) -> str:
        self._aplicar_e_validar(arvore, patch)
        _git("commit", "-m", message or self._mensagem(panel, patch), cwd=arvore)
        return _git("rev-parse", "HEAD", cwd=arvore)

    def validate_code(self, patch: CodePatch) -> None:
        """Aplica um patch de código na worktree e **exige os três gates** — ADR-006.

        O corpus é julgado por quórum porque não há como uma máquina dizer se uma
        afirmação é verdadeira. Código não tem esse problema: `audit`, `test` e `lint`
        respondem sozinhos, e é por isso que a autonomia sobre o próprio código é segura
        antes de o julgamento amadurecer.

        Nada aqui commita. Reprovar em qualquer um dos três é recusar, sem exceção e sem
        caminho de força — um gate que se pode contornar não é gate.
        """
        head = self.head()
        if not head.startswith(patch.base_commit) and not patch.base_commit.startswith(head):
            raise PromotionRefused(
                f"base divergente: patch feito sobre {patch.base_commit}, HEAD é {head}"
            )
        temporario = Path(tempfile.mkdtemp(prefix="vault-code-"))
        arvore = temporario / "tree"
        criada = False
        try:
            _git("worktree", "add", "--detach", str(arvore), head, cwd=self.repo_root)
            criada = True
            try:
                patch.apply_to(arvore)
            except CodePatchRefused as error:
                raise PromotionRefused(str(error)) from error
            for alvo in ("audit", "test", "lint"):
                self._gate(arvore, alvo)
        finally:
            if criada:
                _git("worktree", "remove", "--force", str(arvore), cwd=self.repo_root)
            shutil.rmtree(temporario, ignore_errors=True)

    def _gate(self, arvore: Path, alvo: str) -> None:
        """Um gate do Makefile, na worktree, com o código de saída mandando.

        Sem pipe e sem filtro: já houve nesta casa um commit passar com ESLint vermelho
        porque a saída foi para um `tail` e o `tail` devolveu zero. O que decide aqui é
        `returncode`, e a saída só serve para dizer o que falhou.
        """
        resultado = subprocess.run(  # noqa: S603 — alvo fixo, árvore do próprio repo
            ["make", alvo],
            cwd=arvore,
            capture_output=True,
            text=True,
            check=False,
        )
        if resultado.returncode != 0:
            saida = (resultado.stdout + resultado.stderr).strip()[-1500:]
            raise PromotionRefused(f"gate `make {alvo}` reprovou o patch de código:\n{saida}")

    def _auditar(self, arvore: Path) -> None:
        """A auditoria roda sobre o resultado, não sobre a intenção."""
        resultado = subprocess.run(  # noqa: S603 — caminho fixo do próprio repositório
            ["python3", str(self.repo_root / self.audit_script), str(self._corpus(arvore))],
            capture_output=True,
            text=True,
            check=False,
        )
        if resultado.returncode != 0:
            saida = (resultado.stdout + resultado.stderr).strip()[-1200:]
            raise PromotionRefused(f"auditoria estrutural reprovou o resultado:\n{saida}")

    def _projetar(self, arvore: Path) -> None:
        """Projeção sem ambiguidade é condição de entrada, não consequência."""
        from vault.corpus import CorpusReader
        from vault.projection import build_projection

        try:
            build_projection(CorpusReader(self._corpus(arvore)))
        except Exception as error:  # noqa: BLE001 — qualquer falha aqui barra a promoção
            raise PromotionRefused(
                f"a projeção não pôde ser construída sobre o resultado: {error}"
            ) from error

    def _mensagem(self, panel: Panel, patch: CorpusPatch) -> str:
        avaliadores = sorted({vote.reviewer.key for vote in panel.votes})
        alvos = ", ".join(patch.targets)
        return (
            f"Promove proposta {panel.proposal.id} por quórum multimodelo\n"
            "\n"
            f"Alvos: {alvos}\n"
            f"Painel: {panel.id}\n"
            f"Proponente: {panel.proposal.proposer.key}\n"
            f"Avaliadores: {', '.join(avaliadores)}\n"
            f"Digest do patch avaliado: {patch.digest()}\n"
            "\n"
            "Promoção automática: a decisão é do quórum, com diversidade mínima de\n"
            "provedores e famílias, e o proponente fora da própria contagem."
        )

    def revert(self, commit: str, *, reason: str) -> str:
        """Reversão por commit compensatório. Histórico não se apaga."""
        self._exige_arvore_limpa()
        _git("revert", "--no-commit", commit, cwd=self.repo_root)
        _git(
            "commit",
            "-m",
            f"Reverte promoção {commit[:12]}\n\n{reason}",
            cwd=self.repo_root,
        )
        return self.head()
