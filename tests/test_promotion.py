"""O Promoter é o único que escreve em `knowledge/`. Cada guarda tem que morder."""

from __future__ import annotations

import subprocess
from multiprocessing import Queue
from pathlib import Path

import pytest

from vault.promotion import (
    PATCH_DIGEST_KEY,
    CorpusPatch,
    PatchOperation,
    PatchRefused,
    PromotionRefused,
    ProposalPromoter,
    verify_quorum,
)
from vault.promotion.patch import content_defect, reduction_reason
from vault.quorum.models import (
    Panel,
    PanelMember,
    PanelTask,
    ParseResult,
    Proposal,
    RecommendedAction,
    Vote,
    VoteDecision,
)

NOTA = """---
id: nota-de-teste
title: Nota de teste
domain: teste
kind: fundamento
epistemic_status: supported
updated: 2026-08-04
verified_at: 2026-08-04
---

# Nota de teste

Conteúdo mínimo para o auditor estrutural.
"""


def membro(provider: str, endpoint: str, family: str, papel: str = "critico") -> PanelMember:
    return PanelMember(
        provider=provider,
        endpoint_id=endpoint,
        family=family,
        role_name=papel,
    )


def voto(reviewer: PanelMember, decision: VoteDecision = VoteDecision.APPROVE) -> ParseResult:
    return ParseResult(
        reviewer=reviewer,
        schema_valid=True,
        structured_vote=Vote(
            decision=decision,
            confidence=0.8,
            recommended_action=(
                RecommendedAction.PROMOTE
                if decision is VoteDecision.APPROVE
                else RecommendedAction.REJECT
            ),
        ),
    )


def patch_simples(base: str = "0" * 40, caminho: str = "teste/Nota de teste.md") -> CorpusPatch:
    return CorpusPatch(
        proposal_id="prop-1",
        base_commit=base,
        operations=[PatchOperation(action="create", path=caminho, content=NOTA)],
    )


def painel(
    patch: CorpusPatch,
    *,
    proponente: PanelMember | None = None,
    votos: list[ParseResult] | None = None,
    digest: str | None = None,
) -> Panel:
    autor = proponente or membro("groq", "qwen/qwen3.6-27b", "qwen3", "proponente")
    avaliadores = votos or [
        voto(membro("nvidia", "z-ai/glm-5.2", "glm")),
        voto(membro("groq", "llama-3.3-70b-versatile", "llama")),
        voto(membro("nvidia", "deepseek-ai/deepseek-v4-pro", "deepseek")),
    ]
    return Panel(
        id="painel1",
        task=PanelTask(
            kind="proposta",
            prompt="proponha a nota de teste",
            context={PATCH_DIGEST_KEY: digest if digest is not None else patch.digest()},
        ),
        proposal=Proposal(id="prop-1", proposer=autor, final_response="proposta de teste"),
        members=[v.reviewer for v in avaliadores],
        votes=avaliadores,
    )


# --- amarra entre painel, votos e patch --------------------------------------


def test_patch_trocado_depois_do_voto_e_recusado() -> None:
    """Se bastasse trocar o conteúdo depois do voto, o quórum não valeria nada."""
    avaliado = patch_simples()
    panel = painel(avaliado)
    adulterado = CorpusPatch(
        proposal_id="prop-1",
        base_commit=avaliado.base_commit,
        operations=[
            PatchOperation(
                action="create",
                path="teste/Nota de teste.md",
                content=NOTA + "\nextra",
            )
        ],
    )
    with pytest.raises(PromotionRefused, match="não é o que foi avaliado"):
        verify_quorum(panel, adulterado)


def test_proponente_nao_valida_a_propria_proposta() -> None:
    """O `Panel` já barra na construção; o Promoter confere de novo ao decidir.

    A dupla checagem não é redundância inútil: o painel pode chegar ao Promoter vindo
    do disco, montado por outro processo, e a garantia não pode depender de quem o
    construiu.
    """
    autor = membro("groq", "qwen/qwen3.6-27b", "qwen3", "proponente")
    patch = patch_simples()
    with pytest.raises(ValueError, match="proponente não avalia"):
        painel(
            patch,
            proponente=autor,
            votos=[
                voto(autor),
                voto(membro("nvidia", "z-ai/glm-5.2", "glm")),
                voto(membro("groq", "llama-3.3-70b-versatile", "llama")),
            ],
        )

    # E o Promoter recusa mesmo que um painel assim apareça montado de fora.
    panel = painel(patch)
    forjado = panel.model_copy(update={"votes": [voto(autor), *panel.votes[1:]]})
    with pytest.raises(PromotionRefused, match="aparece entre os avaliadores"):
        verify_quorum(forjado, patch)


def test_diversidade_insuficiente_barra_a_promocao() -> None:
    """Três instâncias do mesmo provedor concordariam consigo mesmas."""
    patch = patch_simples()
    monoprovedor = [
        voto(membro("groq", "a", "llama")),
        voto(membro("groq", "b", "llama")),
        voto(membro("groq", "c", "llama")),
    ]
    with pytest.raises(ValueError, match="dois provedores"):
        painel(patch, votos=monoprovedor)

    # O Promoter recompõe a conta em vez de confiar em quem montou o painel.
    panel = painel(patch)
    forjado = panel.model_copy(update={"votes": monoprovedor})
    with pytest.raises(PromotionRefused, match="diversidade insuficiente"):
        verify_quorum(forjado, patch)


def test_gateway_sem_upstream_comprovado_nao_prova_segundo_provedor() -> None:
    patch = patch_simples()
    votos = [
        voto(membro("openrouter", "vendor/modelo:free", "modelo")),
        voto(membro("nvidia", "modelo-b", "familia-b")),
        voto(membro("nvidia", "modelo-c", "familia-c")),
    ]
    panel = painel(patch, votos=votos)

    with pytest.raises(PromotionRefused, match="não aprovou"):
        verify_quorum(panel, patch)


def test_maioria_contraria_nao_promove() -> None:
    patch = patch_simples()
    panel = painel(
        patch,
        votos=[
            voto(membro("nvidia", "z-ai/glm-5.2", "glm"), VoteDecision.REJECT),
            voto(membro("groq", "llama-3.3-70b-versatile", "llama"), VoteDecision.REJECT),
            voto(membro("nvidia", "deepseek-ai/deepseek-v4-pro", "deepseek")),
        ],
    )
    with pytest.raises(PromotionRefused, match="não aprovou"):
        verify_quorum(panel, patch)


def test_painel_sem_digest_registrado_e_recusado() -> None:
    patch = patch_simples()
    panel = painel(patch, digest="")
    with pytest.raises(PromotionRefused, match="não registrou o digest"):
        verify_quorum(panel, patch)


def test_quorum_aprovado_passa_pela_verificacao() -> None:
    patch = patch_simples()
    verify_quorum(painel(patch), patch)


# --- o patch em si -----------------------------------------------------------


def test_caminho_nao_escapa_do_corpus() -> None:
    for caminho in ("../fora.md", "/etc/passwd.md", "teste/../../fora.md"):
        with pytest.raises(ValueError, match="sai do corpus|caminho"):
            PatchOperation(action="create", path=caminho, content="x")


def test_promoter_so_escreve_markdown() -> None:
    with pytest.raises(ValueError, match="só escreve"):
        PatchOperation(action="create", path="tools/audit.py", content="x")


def test_create_sobre_existente_e_replace_sobre_ausente_falham(tmp_path: Path) -> None:
    (tmp_path / "existe.md").write_text("antes", encoding="utf-8")

    criar = CorpusPatch(
        proposal_id="p",
        base_commit="0" * 40,
        operations=[PatchOperation(action="create", path="existe.md", content="novo")],
    )
    with pytest.raises(PatchRefused, match="create sobre arquivo existente"):
        criar.apply_to(tmp_path)
    assert (tmp_path / "existe.md").read_text(encoding="utf-8") == "antes"

    trocar = CorpusPatch(
        proposal_id="p",
        base_commit="0" * 40,
        operations=[PatchOperation(action="replace", path="ausente.md", content="novo")],
    )
    with pytest.raises(PatchRefused, match="replace sobre arquivo ausente"):
        trocar.apply_to(tmp_path)


def test_patch_invalido_nao_escreve_nada(tmp_path: Path) -> None:
    """Conferência antes de escrita: um alvo ruim não deixa o outro pela metade."""
    (tmp_path / "existe.md").write_text("antes", encoding="utf-8")
    patch = CorpusPatch(
        proposal_id="p",
        base_commit="0" * 40,
        operations=[
            PatchOperation(action="create", path="nova.md", content="conteúdo"),
            PatchOperation(action="create", path="existe.md", content="conflito"),
        ],
    )
    with pytest.raises(PatchRefused):
        patch.apply_to(tmp_path)
    assert not (tmp_path / "nova.md").exists()
    assert (tmp_path / "existe.md").read_text(encoding="utf-8") == "antes"


def test_digest_muda_com_qualquer_byte() -> None:
    a = patch_simples()
    b = CorpusPatch(
        proposal_id=a.proposal_id,
        base_commit=a.base_commit,
        operations=[
            PatchOperation(action="create", path=a.operations[0].path, content=NOTA + " ")
        ],
    )
    assert a.digest() != b.digest()
    # E não muda com a ordem das operações, que não é informação.
    assert a.digest() == CorpusPatch(**a.to_dict()).digest()


NOTA_CHEIA = """---
id: nota-cheia
title: Nota cheia
domain: teste
kind: fundamento
epistemic_status: mixed
updated: 2026-08-04
verified_at: 2026-08-04
---

# Nota cheia

[[Semente]] <!-- relation:navigation -->
[[Outra]] <!-- relation:extends -->

Texto suficiente para o volume não ser o de um stub.

## Estado epistêmico

| ID | Afirmação | Status | Evidência |
| --- | --- | --- | --- |
| `CLM-TST-AAA-001` | Primeira afirmação. | `open` | Falta fonte. |
| `CLM-TST-AAA-002` | Segunda afirmação. | `open` | Falta fonte. |
"""

STUB = """Especificação do conteúdo não solicitada, apenas o patch.
… (resto do conteúdo mantido igual, apenas a seção relevante alterada) …
"""


def _replace(conteudo: str, *, reduz: bool = False) -> CorpusPatch:
    return CorpusPatch(
        proposal_id="p",
        base_commit="0" * 40,
        operations=[
            PatchOperation(
                action="replace",
                path="cheia.md",
                content=conteudo,
                allows_reduction=reduz,
            )
        ],
    )


def test_replace_sem_reducao_declarada_recusa_apagar_claims(tmp_path: Path) -> None:
    (tmp_path / "cheia.md").write_text(NOTA_CHEIA, encoding="utf-8")
    sem_claim = NOTA_CHEIA.replace(
        "| `CLM-TST-AAA-002` | Segunda afirmação. | `open` | Falta fonte. |\n",
        "",
    )
    with pytest.raises(PatchRefused, match="claims 2→1"):
        _replace(sem_claim).apply_to(tmp_path)
    assert (tmp_path / "cheia.md").read_text(encoding="utf-8") == NOTA_CHEIA


def test_replace_sem_reducao_declarada_recusa_apagar_wikilink(tmp_path: Path) -> None:
    (tmp_path / "cheia.md").write_text(NOTA_CHEIA, encoding="utf-8")
    sem_link = NOTA_CHEIA.replace("[[Outra]] <!-- relation:extends -->\n", "")
    with pytest.raises(PatchRefused, match="wikilinks 2→1"):
        _replace(sem_link).apply_to(tmp_path)


def test_replace_stub_sem_reducao_declarada_e_recusado(tmp_path: Path) -> None:
    (tmp_path / "cheia.md").write_text(NOTA_CHEIA, encoding="utf-8")
    with pytest.raises(PatchRefused, match="allows_reduction"):
        _replace(STUB).apply_to(tmp_path)
    assert (tmp_path / "cheia.md").read_text(encoding="utf-8") == NOTA_CHEIA


def test_replace_redutor_com_intencao_declarada_aplica(tmp_path: Path) -> None:
    (tmp_path / "cheia.md").write_text(NOTA_CHEIA, encoding="utf-8")
    escritos = _replace(STUB, reduz=True).apply_to(tmp_path)
    assert escritos == [tmp_path / "cheia.md"]
    assert "resto do conteúdo mantido" in (tmp_path / "cheia.md").read_text(
        encoding="utf-8"
    )


def test_replace_que_nao_reduz_nao_precisa_de_bandeira(tmp_path: Path) -> None:
    (tmp_path / "cheia.md").write_text(NOTA_CHEIA, encoding="utf-8")
    maior = NOTA_CHEIA + "\nParágrafo extra que não apaga nada.\n"
    _replace(maior).apply_to(tmp_path)
    assert "Parágrafo extra" in (tmp_path / "cheia.md").read_text(encoding="utf-8")


def test_replace_recusa_ata_de_painel(tmp_path: Path) -> None:
    (tmp_path / "cheia.md").write_text(NOTA_CHEIA, encoding="utf-8")
    com_ata = NOTA_CHEIA + "\n## Decisão do painel 63ef290b6f3d\n\nMinuta.\n"
    with pytest.raises(PatchRefused, match="ata de painel"):
        _replace(com_ata).apply_to(tmp_path)
    assert content_defect(NOTA_CHEIA, com_ata, allows_reduction=False) == (
        "ata de painel no corpo da nota"
    )


def test_replace_recusa_latex_mutilado(tmp_path: Path) -> None:
    (tmp_path / "cheia.md").write_text(NOTA_CHEIA, encoding="utf-8")
    quebrado = NOTA_CHEIA + "\n$$\n\\rho=\\operatorname{Tr}_E\\! ig[U]\\big].\n$$\n"
    with pytest.raises(PatchRefused, match="LaTeX mutilado"):
        _replace(quebrado).apply_to(tmp_path)


def test_replace_recusa_isbn_removido(tmp_path: Path) -> None:
    com_isbn = NOTA_CHEIA + "\n- Peter Godfrey-Smith. ISBN 978-0-226-61865-4.\n"
    (tmp_path / "cheia.md").write_text(com_isbn, encoding="utf-8")
    sem_isbn = NOTA_CHEIA + "\n- Peter Godfrey-Smith.\n"
    with pytest.raises(PatchRefused, match="identificadores removidos"):
        _replace(sem_isbn).apply_to(tmp_path)
    _replace(sem_isbn, reduz=True).apply_to(tmp_path)


def test_create_nao_passa_pela_guarda_de_delta(tmp_path: Path) -> None:
    patch = CorpusPatch(
        proposal_id="p",
        base_commit="0" * 40,
        operations=[PatchOperation(action="create", path="nova.md", content=STUB)],
    )
    patch.apply_to(tmp_path)
    assert (tmp_path / "nova.md").is_file()


def test_digest_ignora_allows_reduction_falso_e_muda_quando_e_verdadeiro() -> None:
    base = _replace(NOTA_CHEIA)
    explicito_falso = _replace(NOTA_CHEIA)
    assert base.digest() == explicito_falso.digest()
    assert base.digest() == CorpusPatch(
        proposal_id=base.proposal_id,
        base_commit=base.base_commit,
        operations=[
            PatchOperation(action="replace", path="cheia.md", content=NOTA_CHEIA)
        ],
    ).digest()
    assert base.digest() != _replace(NOTA_CHEIA, reduz=True).digest()


def test_edicao_curta_sem_apagar_claim_nem_link_nao_e_destruicao() -> None:
    motivo = reduction_reason(NOTA_CHEIA, NOTA_CHEIA.replace("suficiente", "bastante"))
    assert motivo is None


# --- o fluxo inteiro, contra um repositório Git de verdade -------------------


def repo_de_teste(raiz: Path) -> Path:
    """Um repositório mínimo com a mesma forma do Vault: corpus e auditor."""
    subprocess.run(["git", "init", "-q", "-b", "main", str(raiz)], check=True)
    subprocess.run(["git", "-C", str(raiz), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(raiz), "config", "user.name", "teste"], check=True)
    (raiz / "knowledge").mkdir()
    (raiz / "knowledge" / "Semente.md").write_text(NOTA, encoding="utf-8")
    (raiz / "tools").mkdir()
    (raiz / "tools" / "audit.py").write_text(
        "import sys\nraise SystemExit(0)\n", encoding="utf-8"
    )
    subprocess.run(["git", "-C", str(raiz), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(raiz), "commit", "-qm", "base"], check=True)
    return raiz


def test_promocao_completa_cria_commit_com_procedencia(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raiz = repo_de_teste(tmp_path / "repo")
    events: list[tuple[str, dict[str, object]]] = []
    promoter = ProposalPromoter(
        repo_root=raiz,
        emit=lambda kind, payload: events.append((kind, payload)),
    )
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)

    patch = patch_simples(base=promoter.head(), caminho="Nota nova.md")
    panel = painel(patch)

    resultado = promoter.promote(panel, patch)

    assert (raiz / "knowledge" / "Nota nova.md").is_file()
    assert resultado.targets == ["Nota nova.md"]
    assert resultado.commit == promoter.head()
    assert set(resultado.providers) == {"groq", "nvidia"}
    assert len(resultado.families) >= 2

    mensagem = subprocess.run(
        ["git", "-C", str(raiz), "log", "-1", "--pretty=%B"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert panel.proposal.proposer.key in mensagem
    assert patch.digest() in mensagem
    kinds = [kind for kind, _ in events]
    assert kinds == [
        "promotion_started",
        "temporary_created",
        "commit_created",
        "corpus_changed",
        "temporary_discarded",
        "promotion_completed",
    ]


def test_base_divergente_nao_promove(tmp_path: Path) -> None:
    """Base que o git não resolve não é contexto de ninguém."""
    raiz = repo_de_teste(tmp_path / "repo")
    promoter = ProposalPromoter(repo_root=raiz)
    patch = patch_simples(base="a" * 40, caminho="Outra.md")
    with pytest.raises(PromotionRefused, match="base divergente"):
        promoter.promote(painel(patch), patch)


def _commit(raiz: Path, relativo: str, texto: str, mensagem: str) -> None:
    destino = raiz / relativo
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")
    subprocess.run(["git", "-C", str(raiz), "add", "--", relativo], check=True)
    subprocess.run(["git", "-C", str(raiz), "commit", "-qm", mensagem], check=True)


def test_commit_alheio_nao_invalida_patch_de_alvo_intacto(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raiz = repo_de_teste(tmp_path / "repo")
    promoter = ProposalPromoter(repo_root=raiz)
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    base = promoter.head()
    patch = patch_simples(base=base, caminho="Nota nova.md")
    _commit(raiz, "frontend/src/style.css", "body{}\n", "css alheio")

    resultado = promoter.promote(painel(patch), patch)

    assert (raiz / "knowledge" / "Nota nova.md").is_file()
    assert resultado.commit == promoter.head()
    assert resultado.commit != base


def test_alvo_reestrito_desde_a_base_recusa_promocao(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raiz = repo_de_teste(tmp_path / "repo")
    promoter = ProposalPromoter(repo_root=raiz)
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    base = promoter.head()
    patch = CorpusPatch(
        proposal_id="prop-1",
        base_commit=base,
        operations=[
            PatchOperation(
                action="replace",
                path="Semente.md",
                content=NOTA + "\nparágrafo votado\n",
            )
        ],
    )
    _commit(raiz, "knowledge/Semente.md", NOTA + "\noutra edição\n", "nota reescrita")

    with pytest.raises(PromotionRefused, match="alvo mudou"):
        promoter.promote(painel(patch), patch)
    assert "outra edição" in (raiz / "knowledge" / "Semente.md").read_text(
        encoding="utf-8"
    )


def test_validate_aceita_head_novo_se_o_alvo_nao_mudou(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raiz = repo_de_teste(tmp_path / "repo")
    promoter = ProposalPromoter(repo_root=raiz)
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    base = promoter.head()
    patch = patch_simples(base=base, caminho="SoDry.md")
    _commit(
        raiz,
        "tools/audit.py",
        "import sys\nraise SystemExit(0)\n# toque alheio\n",
        "toque no auditor",
    )

    promoter.validate(painel(patch), patch)

    assert promoter.head() != base
    assert not (raiz / "knowledge" / "SoDry.md").exists()


def test_auditoria_reprovada_deixa_o_corpus_intacto(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raiz = repo_de_teste(tmp_path / "repo")
    (raiz / "tools" / "audit.py").write_text(
        "import sys\nprint('defeito estrutural')\nraise SystemExit(1)\n", encoding="utf-8"
    )
    subprocess.run(["git", "-C", str(raiz), "commit", "-aqm", "auditor severo"], check=True)

    promoter = ProposalPromoter(repo_root=raiz)
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    antes = promoter.head()
    patch = patch_simples(base=antes, caminho="Reprovada.md")

    with pytest.raises(PromotionRefused, match="auditoria estrutural reprovou"):
        promoter.promote(painel(patch), patch)

    assert promoter.head() == antes
    assert not (raiz / "knowledge" / "Reprovada.md").exists()
    assert subprocess.run(
        ["git", "-C", str(raiz), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip() == ""


def test_arvore_suja_nao_impede_promocao(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O checkout do operador sujo não é guarda: o commit nasce na worktree isolada."""
    raiz = repo_de_teste(tmp_path / "repo")
    (raiz / "knowledge" / "Semente.md").write_text(NOTA + "\nrascunho", encoding="utf-8")
    promoter = ProposalPromoter(repo_root=raiz)
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    patch = patch_simples(base=promoter.head(), caminho="Qualquer.md")
    resultado = promoter.promote(painel(patch), patch)
    assert (raiz / "knowledge" / "Qualquer.md").is_file()
    assert resultado.commit == promoter.head()


def test_reversao_e_commit_compensatorio(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Histórico não se apaga: reverter cria commit novo e a nota some do corpus."""
    raiz = repo_de_teste(tmp_path / "repo")
    promoter = ProposalPromoter(repo_root=raiz)
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)

    patch = patch_simples(base=promoter.head(), caminho="Temporaria.md")
    promovido = promoter.promote(painel(patch), patch)
    assert (raiz / "knowledge" / "Temporaria.md").is_file()

    (raiz / "rascunho.txt").write_text("sujo", encoding="utf-8")
    with pytest.raises(PromotionRefused, match="árvore de trabalho suja"):
        promoter.revert(promovido.commit, reason="teste de reversão")
    (raiz / "rascunho.txt").unlink()
    promoter.revert(promovido.commit, reason="teste de reversão")
    assert not (raiz / "knowledge" / "Temporaria.md").exists()

    historico = subprocess.run(
        ["git", "-C", str(raiz), "log", "--oneline"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert promovido.commit[:7] in historico  # o commit promovido continua no histórico


def _worktrees(raiz: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(raiz), "worktree", "list"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def test_validate_nao_avanca_head_nem_deixa_arquivo_no_corpus(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raiz = repo_de_teste(tmp_path / "repo")
    promoter = ProposalPromoter(repo_root=raiz)
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    antes = promoter.head()
    patch = patch_simples(base=antes, caminho="SoDry.md")

    promoter.validate(painel(patch), patch)

    assert promoter.head() == antes
    assert not (raiz / "knowledge" / "SoDry.md").exists()
    assert "vault-promotion-" not in _worktrees(raiz)


def test_validate_recusa_base_divergente(tmp_path: Path) -> None:
    raiz = repo_de_teste(tmp_path / "repo")
    promoter = ProposalPromoter(repo_root=raiz)
    patch = patch_simples(base="a" * 40, caminho="Outra.md")
    with pytest.raises(PromotionRefused, match="base divergente"):
        promoter.validate(painel(patch), patch)


def test_validate_aceita_arvore_suja(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raiz = repo_de_teste(tmp_path / "repo")
    (raiz / "knowledge" / "Semente.md").write_text(NOTA + "\nrascunho", encoding="utf-8")
    promoter = ProposalPromoter(repo_root=raiz)
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    patch = patch_simples(base=promoter.head(), caminho="Qualquer.md")
    promoter.validate(painel(patch), patch)
    assert not (raiz / "knowledge" / "Qualquer.md").exists()


def test_validate_recusa_auditoria_e_nao_toca_o_corpus(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raiz = repo_de_teste(tmp_path / "repo")
    (raiz / "tools" / "audit.py").write_text(
        "import sys\nprint('defeito estrutural')\nraise SystemExit(1)\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(raiz), "commit", "-aqm", "auditor severo"], check=True)
    promoter = ProposalPromoter(repo_root=raiz)
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    antes = promoter.head()
    patch = patch_simples(base=antes, caminho="Reprovada.md")

    with pytest.raises(PromotionRefused, match="auditoria estrutural reprovou"):
        promoter.validate(painel(patch), patch)

    assert promoter.head() == antes
    assert not (raiz / "knowledge" / "Reprovada.md").exists()
    assert "vault-promotion-" not in _worktrees(raiz)


def test_validate_recusa_replace_destrutivo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raiz = repo_de_teste(tmp_path / "repo")
    (raiz / "knowledge" / "Cheia.md").write_text(NOTA_CHEIA, encoding="utf-8")
    subprocess.run(["git", "-C", str(raiz), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(raiz), "commit", "-qm", "nota cheia"], check=True)
    promoter = ProposalPromoter(repo_root=raiz)
    monkeypatch.setattr(ProposalPromoter, "_projetar", lambda self, arvore: None)
    patch = CorpusPatch(
        proposal_id="prop-1",
        base_commit=promoter.head(),
        operations=[
            PatchOperation(action="replace", path="Cheia.md", content=STUB)
        ],
    )

    with pytest.raises(PromotionRefused, match="allows_reduction"):
        promoter.validate(painel(patch), patch)

    assert (raiz / "knowledge" / "Cheia.md").read_text(encoding="utf-8") == NOTA_CHEIA


# --- concorrência real: processos distintos, worktrees ligados, lock no common dir


def _promote_process(
    queue: Queue[tuple[str, str] | tuple[str, str, str]],
    repo_root: str,
    caminho: str,
    proposal_id: str,
) -> None:
    """Alvo de processo isolado: reconstrói o promoter e promove uma nota.

    Roda num processo à parte para provar que o ``flock`` no common dir serializa
    promoções mesmo entre processos (não só entre threads do mesmo processo).
    """
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))
    from vault.promotion import CorpusPatch, PatchOperation, ProposalPromoter
    from vault.promotion.promoter import PromotionRefused
    from vault.quorum.models import (
        Panel,
        PanelMember,
        PanelTask,
        ParseResult,
        Proposal,
        RecommendedAction,
        Vote,
        VoteDecision,
    )

    # Repo de teste mínimo não tem o Atlas; a projeção é irrelevante aqui.
    class _PromoterSemProjecao(ProposalPromoter):
        def _projetar(self, arvore: Path) -> None:  # type: ignore[override]
            return None

    promoter = _PromoterSemProjecao(repo_root=Path(repo_root))
    base = promoter.head()
    patch = CorpusPatch(
        proposal_id=proposal_id,
        base_commit=base,
        operations=[PatchOperation(action="create", path=caminho, content=NOTA)],
    )
    membros = [
        PanelMember(
            provider="nvidia", endpoint_id="z-ai/glm-5.2", family="glm", role_name="critico"
        ),
        PanelMember(
            provider="groq",
            endpoint_id="llama-3.3-70b-versatile",
            family="llama",
            role_name="critico",
        ),
        PanelMember(
            provider="nvidia",
            endpoint_id="deepseek-ai/deepseek-v4-pro",
            family="deepseek",
            role_name="critico",
        ),
    ]
    votos = [
        ParseResult(
            reviewer=m,
            schema_valid=True,
            structured_vote=Vote(
                decision=VoteDecision.APPROVE,
                confidence=0.8,
                recommended_action=RecommendedAction.PROMOTE,
            ),
        )
        for m in membros
    ]
    painel = Panel(
        id=f"painel-{proposal_id}",
        task=PanelTask(kind="proposta", prompt="x", context={PATCH_DIGEST_KEY: patch.digest()}),
        proposal=Proposal(
            id=proposal_id,
            proposer=PanelMember(
                provider="groq",
                endpoint_id="qwen/qwen3.6-27b",
                family="qwen3",
                role_name="proponente",
            ),
            final_response="x",
        ),
        members=membros,
        votes=votos,
    )
    try:
        promoter.promote(painel, patch)
        queue.put(("ok", proposal_id))
    except PromotionRefused as error:
        queue.put(("refused", proposal_id, str(error)))
    except Exception as error:  # noqa: BLE001
        queue.put(("error", proposal_id, repr(error)))


def test_dois_processos_no_mesmo_repo_promovem_ambos(
    tmp_path: Path,
) -> None:
    """Prova a serialização entre processos no mesmo repositório.

    Dois processos distintos promovem notas diferentes do mesmo ``repo_root``. Sem o lock
    (``flock`` no common dir, válido entre processos), o segundo ``merge --ff-only`` falharia
    com 'diverging branches' e deixaria a nota de fora. Com o lock, ambos avançam o main.

    Invariantes:
    - nenhum promote falha (nem "diverging", nem erro);
    - o main avança exatamente 2 commits desde ``base``;
    - ambas as notas existem no corpus vivo;
    - a árvore termina limpa.
    """
    import multiprocessing

    raiz = repo_de_teste(tmp_path / "repo")
    base = ProposalPromoter(repo_root=raiz).head()
    wt_a = tmp_path / "wt-a"
    wt_b = tmp_path / "wt-b"
    subprocess.run(
        ["git", "-C", str(raiz), "worktree", "add", "-q", str(wt_a), base], check=True
    )
    subprocess.run(
        ["git", "-C", str(raiz), "worktree", "add", "-q", str(wt_b), base], check=True
    )

    ctx = multiprocessing.get_context("spawn")
    fila: Queue[tuple[str, str] | tuple[str, str, str]] = ctx.Queue()
    # Ambos promovem DO MESMO repo_root (não dos worktrees) — é aqui que a contenção
    # pelo main ocorre e o lock no common dir precisa serializar.
    p1 = ctx.Process(
        target=_promote_process,
        args=(fila, str(raiz), "Processo A.md", "prop-p-a"),
    )
    p2 = ctx.Process(
        target=_promote_process,
        args=(fila, str(raiz), "Processo B.md", "prop-p-b"),
    )
    p1.start()
    p2.start()
    p1.join()
    p2.join()

    resultados = [fila.get() for _ in range(2)]
    tipos = [r[0] for r in resultados]
    assert tipos == ["ok", "ok"], f"promoção concorrente falhou: {resultados}"

    novos_commits = subprocess.run(
        ["git", "-C", str(raiz), "rev-list", "--count", f"{base}..HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert novos_commits == "2", f"esperava 2 commits no main, veio {novos_commits}"
    assert (raiz / "knowledge" / "Processo A.md").is_file()
    assert (raiz / "knowledge" / "Processo B.md").is_file()

    sujo = subprocess.run(
        ["git", "-C", str(raiz), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert sujo == "", f"árvore suja após promoções: {sujo}"


def test_lock_fica_no_common_dir_e_e_compartilhado_entre_worktrees(
    tmp_path: Path,
) -> None:
    """O lock deve viver no common dir (ignorado pelo git) e serializar worktrees.

    Cria dois linked worktrees e dispara, em processos distintos, uma promoção de cada.
    Cada worktree tem seu próprio HEAD, mas o arquivo de trava é único no common dir — se
    dois promotes simultâneos não geram 'diverging branches' nem corruptela, o lock está
    cumprindo seu papel entre worktrees.
    """
    import multiprocessing

    raiz = repo_de_teste(tmp_path / "repo")
    base = ProposalPromoter(repo_root=raiz).head()
    wt_a = tmp_path / "wt-a"
    wt_b = tmp_path / "wt-b"
    subprocess.run(
        ["git", "-C", str(raiz), "worktree", "add", "-q", str(wt_a), base], check=True
    )
    subprocess.run(
        ["git", "-C", str(raiz), "worktree", "add", "-q", str(wt_b), base], check=True
    )

    ctx = multiprocessing.get_context("spawn")
    fila: Queue[tuple[str, str] | tuple[str, str, str]] = ctx.Queue()
    p1 = ctx.Process(
        target=_promote_process,
        args=(fila, str(wt_a), "Worktree A.md", "prop-wt-a"),
    )
    p2 = ctx.Process(
        target=_promote_process,
        args=(fila, str(wt_b), "Worktree B.md", "prop-wt-b"),
    )
    p1.start()
    p2.start()
    p1.join()
    p2.join()

    resultados = [fila.get() for _ in range(2)]
    tipos = [r[0] for r in resultados]
    assert tipos == ["ok", "ok"], f"promoção em worktrees falhou: {resultados}"

    # O arquivo de trava está no common dir, não dentro de nenhum worktree.
    common = subprocess.run(
        ["git", "-C", str(raiz), "rev-parse", "--git-common-dir"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    lock_path = (raiz / common / "promotion.lock")
    if not lock_path.is_absolute():
        lock_path = raiz / common / "promotion.lock"
    assert lock_path.exists(), "trava não está no common dir"

    # Cada worktree tem a nota que promoveu e nenhum lixo de worktree de promoção.
    assert (wt_a / "knowledge" / "Worktree A.md").is_file()
    assert (wt_b / "knowledge" / "Worktree B.md").is_file()
    worktrees = subprocess.run(
        ["git", "-C", str(raiz), "worktree", "list", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "vault-promotion-" not in worktrees

