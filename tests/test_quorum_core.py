"""O quórum só conta conclusões explícitas e preserva a procedência da decisão."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from vault.promotion import CorpusPatch, PatchOperation
from vault.quorum import (
    PATCH_DIGEST_KEY,
    DecisionStatus,
    Panel,
    PanelMember,
    PanelTask,
    Proposal,
    ProposalEnvelopeError,
    QuorumStore,
    QuorumStoreError,
    StructuralFailure,
    VoteDecision,
    canonical_patch_response,
    corpus_patch_prompt,
    decide_panel,
    envelope_needs_repair,
    parse_corpus_patch,
    parse_vote,
    resolve_with_synthesis,
    strip_reasoning,
    vote_contract,
)


def member(
    provider: str,
    endpoint: str,
    family: str,
    role: str,
) -> PanelMember:
    return PanelMember(
        provider=provider,
        endpoint_id=endpoint,
        family=family,
        role_name=role,
    )


def panel() -> Panel:
    proposer = member("groq", "proposal-model", "llama", "proponente")
    reviewers = [
        member("groq", "fact-model", "qwen", "verificador-factual"),
        member("nvidia", "critical-model", "glm", "critico-epistemologico"),
        member("groq", "structure-model", "llama", "revisor-estrutural"),
    ]
    task = PanelTask(kind="teste", prompt="avalie a proposição")
    proposal = Proposal(proposer=proposer, final_response="proposta final")
    return Panel(id="panel-1", task=task, proposal=proposal, members=reviewers)


def payload(
    decision: str = "approve",
    *,
    confidence: float = 0.7,
    blocking: list[str] | None = None,
) -> str:
    actions = {
        "approve": "promote",
        "reject": "reject",
        "revise": "revise",
        "abstain": "escalate",
    }
    return json.dumps(
        {
            "decision": decision,
            "confidence": confidence,
            "blocking_issues": blocking or [],
            "non_blocking_issues": [],
            "evidence": [{"claim": "claim-id", "assessment": "supported"}],
            "recommended_action": actions[decision],
        }
    )


def add_votes(target: Panel, *decisions: str) -> None:
    for reviewer, decision in zip(target.members, decisions, strict=True):
        target.votes.append(parse_vote(payload(decision), reviewer=reviewer))


def test_think_e_removido_sem_ser_interpretado() -> None:
    response = strip_reasoning(
        "<think>segredo um</think> conclusão <THINK>segredo dois</THINK> final"
    )
    assert response.final_response == "conclusão  final"
    assert response.reasoning_block_detected
    assert response.reasoning_block_removed
    assert "segredo" not in response.final_response


def test_think_nao_fechado_descarta_o_resto() -> None:
    response = strip_reasoning("conclusão segura<think>interno sem fechamento")
    assert response.final_response == "conclusão segura"
    assert "interno" not in response.final_response


def test_marca_think_incompleta_tambem_nao_atravessa() -> None:
    reviewer = panel().members[0]
    result = parse_vote("conclusão segura <think segredo", reviewer=reviewer)
    assert not result.schema_valid
    assert result.reasoning_block_detected
    assert result.reasoning_block_removed
    assert result.final_response == "conclusão segura"


def test_parser_usa_so_json_final_e_registra_remocao() -> None:
    reviewer = panel().members[0]
    result = parse_vote(
        f"<think>não persista</think> observação descartável\n{payload()}",
        reviewer=reviewer,
    )
    assert result.schema_valid
    assert result.structured_vote.decision == VoteDecision.APPROVE
    assert result.reasoning_block_removed
    assert "não persista" not in result.final_response


def test_parser_faz_uma_reparacao_deterministica_de_virgula_final() -> None:
    reviewer = panel().members[0]
    malformed = payload().rsplit("}", 1)[0] + ",}"
    result = parse_vote(malformed, reviewer=reviewer)
    assert result.schema_valid
    assert result.repair_attempted
    assert result.repair_succeeded


def test_parser_invalido_vira_abstencao_e_nao_rejeicao() -> None:
    result = parse_vote("não há JSON", reviewer=panel().members[0])
    assert not result.schema_valid
    assert result.structured_vote.decision == VoteDecision.ABSTAIN
    assert result.structured_vote.recommended_action.value == "escalate"
    assert result.repair_attempted and not result.repair_succeeded


def test_schema_recusa_enum_e_campos_extras() -> None:
    wrong = json.loads(payload())
    wrong["decision"] = "maybe"
    wrong["raw_response"] = "não pode atravessar"
    result = parse_vote(json.dumps(wrong), reviewer=panel().members[0])
    assert not result.schema_valid


def test_acao_com_explicacao_nao_e_adivinhada_como_enum_valido() -> None:
    """Regressão do voto Groq real: JSON válido, contrato semântico inválido."""
    wrong = json.loads(payload("revise"))
    wrong["recommended_action"] = "revise porque o status está forte demais"

    result = parse_vote(json.dumps(wrong), reviewer=panel().members[0])

    assert not result.schema_valid
    assert result.structured_vote.decision == VoteDecision.ABSTAIN
    assert result.repair_attempted and not result.repair_succeeded


def test_prompt_de_voto_deriva_schema_e_mapeamento_literal() -> None:
    contract = vote_contract()
    assert 'decision="revise" exige recommended_action="revise"' in contract
    assert "recommended_action aceita somente o enum exato" in contract
    assert '"additionalProperties":false' in contract
    assert '"required"' in contract


def test_envelope_de_patch_e_fechado_canonico_com_extracao() -> None:
    proposal_id = "prop-patch"
    base = "a" * 40
    raw = json.dumps(
        {
            "proposal_id": proposal_id,
            "base_commit": base,
            "operations": [
                {
                    "action": "replace",
                    "path": "Teste.md",
                    "content": "# Teste\n\nConteúdo.",
                }
            ],
        }
    )

    parsed = parse_corpus_patch(
        f"```json\n{raw}\n```",
        expected_proposal_id=proposal_id,
        expected_base_commit=base,
    )

    assert json.loads(parsed.canonical_response) == parsed.patch.to_dict()
    assert parsed.patch.digest()
    prompt = corpus_patch_prompt("troque a nota", proposal_id=proposal_id, base_commit=base)
    assert '"additionalProperties":false' in prompt
    assert f"proposal_id exato: {proposal_id}" in prompt
    assert f"base_commit exato: {base}" in prompt

    trailing = parse_corpus_patch(
        raw + " explicação",
        expected_proposal_id=proposal_id,
        expected_base_commit=base,
    )
    assert trailing.patch.targets == ["Teste.md"]
    assert "explicação" not in trailing.patch.operations[0].content

    comma = parse_corpus_patch(
        raw.rsplit("}", 1)[0] + ",}",
        expected_proposal_id=proposal_id,
        expected_base_commit=base,
    )
    assert comma.patch.targets == ["Teste.md"]

    with pytest.raises(ProposalEnvelopeError, match="CorpusPatch"):
        parse_corpus_patch(
            json.dumps({**json.loads(raw), "campo_extra": True}),
            expected_proposal_id=proposal_id,
            expected_base_commit=base,
        )


def test_newline_cru_dentro_de_content_e_aceito() -> None:
    proposal_id = "prop-nl"
    base = "a" * 40
    cru = (
        '{"proposal_id":"'
        + proposal_id
        + '","base_commit":"'
        + base
        + '","operations":[{"action":"replace","path":"Teste.md",'
        + '"content":"# Teste\n\nCorpo."}]}'
    )
    parsed = parse_corpus_patch(
        cru, expected_proposal_id=proposal_id, expected_base_commit=base
    )
    assert parsed.patch.operations[0].content == "# Teste\n\nCorpo."


def test_fence_de_duas_linhas_sem_fecho_e_aceito() -> None:
    proposal_id = "prop-fence"
    base = "a" * 40
    raw = json.dumps(
        {
            "proposal_id": proposal_id,
            "base_commit": base,
            "operations": [
                {"action": "replace", "path": "Teste.md", "content": "# Teste\n\nCorpo."}
            ],
        }
    )
    parsed = parse_corpus_patch(
        f"```json\n{raw}",
        expected_proposal_id=proposal_id,
        expected_base_commit=base,
    )
    assert parsed.patch.targets == ["Teste.md"]


def test_prosa_com_stub_json_e_colhida() -> None:
    """Prosa ao redor não entra no content; o objeto único continua válido."""
    proposal_id = "prop-stub"
    base = "a" * 40
    stub = json.dumps(
        {
            "proposal_id": proposal_id,
            "base_commit": base,
            "operations": [
                {
                    "action": "replace",
                    "path": "Teste.md",
                    "content": "...full markdown...",
                }
            ],
        }
    )
    parsed = parse_corpus_patch(
        f"Aqui vai o patch:\n{stub}\nPronto.",
        expected_proposal_id=proposal_id,
        expected_base_commit=base,
    )
    assert parsed.patch.operations[0].content == "...full markdown..."
    assert "Aqui vai" not in parsed.patch.operations[0].content
    assert "Pronto" not in parsed.patch.operations[0].content


def test_store_persiste_exatamente_o_patch_mostrado_aos_revisores(tmp_path: Path) -> None:
    original = panel()
    patch = CorpusPatch(
        proposal_id=original.proposal.id,
        base_commit="b" * 40,
        operations=[
            PatchOperation(
                action="replace",
                path="Teste.md",
                content="# Teste\n\nConteúdo integral.",
            )
        ],
    )
    linked = Panel(
        id=original.id,
        task=original.task.model_copy(update={"context": {PATCH_DIGEST_KEY: patch.digest()}}),
        proposal=original.proposal.model_copy(
            update={"final_response": canonical_patch_response(patch)}
        ),
        members=original.members,
    )
    store = QuorumStore(tmp_path / "quorum")
    store.create_panel(linked)

    store.save_patch(linked.id, patch.to_dict())

    assert store.load_patch(linked.id) == patch.to_dict()
    persisted = json.loads((tmp_path / "quorum" / linked.id / "task.json").read_text())
    assert persisted["task"]["context"][PATCH_DIGEST_KEY] == patch.digest()


def test_store_recusa_patch_diferente_do_artefato_votado(tmp_path: Path) -> None:
    original = panel()
    patch = CorpusPatch(
        proposal_id=original.proposal.id,
        base_commit="c" * 40,
        operations=[PatchOperation(action="replace", path="Teste.md", content="primeiro")],
    )
    linked = Panel(
        id=original.id,
        task=original.task.model_copy(update={"context": {PATCH_DIGEST_KEY: patch.digest()}}),
        proposal=original.proposal.model_copy(update={"final_response": "{}"}),
        members=original.members,
    )
    store = QuorumStore(tmp_path / "quorum")
    store.create_panel(linked)

    with pytest.raises(QuorumStoreError, match="diverge do artefato"):
        store.save_patch(linked.id, patch.to_dict())
    assert store.load_patch(linked.id) is None


def test_painel_recusa_autoavaliacao_endpoint_duplicado_e_monocultura() -> None:
    valid = panel()
    with pytest.raises(ValidationError, match="própria proposta"):
        Panel(
            task=valid.task,
            proposal=valid.proposal,
            members=[valid.proposal.proposer, *valid.members[:2]],
        )
    with pytest.raises(ValidationError, match="duas vezes"):
        Panel(
            task=valid.task,
            proposal=valid.proposal,
            members=[valid.members[0], valid.members[0], valid.members[1]],
        )
    mono = [
        member("groq", f"m{index}", f"f{index}", "verificador-factual") for index in range(3)
    ]
    with pytest.raises(ValidationError, match="dois provedores"):
        Panel(task=valid.task, proposal=valid.proposal, members=mono)


def test_maioria_aprova_sem_ponderar_confianca() -> None:
    target = panel()
    target.votes.extend(
        [
            parse_vote(payload("approve", confidence=0.1), reviewer=target.members[0]),
            parse_vote(payload("approve", confidence=0.2), reviewer=target.members[1]),
            parse_vote(payload("reject", confidence=1.0), reviewer=target.members[2]),
        ]
    )
    decision = decide_panel(target)
    assert decision.outcome.value == "promote"
    assert decision.status == DecisionStatus.DECIDED
    assert decision.valid_vote_count == 3
    assert len(decision.votes) == 3
    assert all(vote.counted for vote in decision.votes)


def test_voto_invalido_nao_completa_minimo() -> None:
    target = panel()
    target.votes.extend(
        [
            parse_vote(payload(), reviewer=target.members[0]),
            parse_vote(payload(), reviewer=target.members[1]),
            parse_vote("inválido", reviewer=target.members[2]),
        ]
    )
    decision = decide_panel(target)
    assert decision.outcome.value == "escalate"
    assert decision.valid_vote_count == 2
    assert decision.status == DecisionStatus.DECIDED


def test_gateway_sem_upstream_comprovado_nao_completa_quorum() -> None:
    target = panel()
    gateway = member("openrouter", "vendor/modelo:free", "modelo", "verificador-factual")
    diretos = [
        member("nvidia", "modelo-b", "familia-b", "critico-epistemologico"),
        member("nvidia", "modelo-c", "familia-c", "revisor-estrutural"),
    ]
    target = Panel(
        id=target.id,
        task=target.task,
        proposal=target.proposal,
        members=[gateway, *diretos],
    )
    add_votes(target, "approve", "approve", "approve")

    decision = decide_panel(target)

    assert decision.outcome.value == "escalate"
    assert decision.valid_vote_count == 2
    assert decision.votes[0].counted is False


def test_falha_estrutural_objetiva_rejeita_automaticamente() -> None:
    target = panel()
    add_votes(target, "approve", "approve", "approve")
    failure = StructuralFailure(
        source="revisor-estrutural",
        issue="wikilink sem relação",
        reviewer=target.members[2],
    )
    decision = decide_panel(target, structural_failures=[failure])
    assert decision.outcome.value == "reject"
    assert decision.structural_failures == [failure]


def test_empate_exige_sintese_independente() -> None:
    target = panel()
    add_votes(target, "approve", "reject", "revise")
    unresolved = decide_panel(target)
    assert unresolved.requires_synthesis
    assert unresolved.outcome.value == "escalate"

    arbiter = member("nvidia", "arbiter-model", "nemotron", "arbitro")
    result = parse_vote(payload("revise"), reviewer=arbiter)
    resolved = resolve_with_synthesis(target, arbiter=arbiter, result=result)
    assert resolved.outcome.value == "revise"
    assert resolved.synthesized_by == arbiter
    assert len(resolved.votes) == 4


def test_sintetizador_nao_pode_ter_participado_do_painel() -> None:
    target = panel()
    add_votes(target, "approve", "reject", "revise")
    reviewer = target.members[0]
    result = parse_vote(payload("approve"), reviewer=reviewer)
    with pytest.raises(ValueError, match="independente"):
        resolve_with_synthesis(target, arbiter=reviewer, result=result)


def test_gateway_sem_upstream_comprovado_nao_arbitra_empate() -> None:
    target = panel()
    add_votes(target, "approve", "reject", "revise")
    arbiter = member("openrouter", "vendor/modelo:free", "modelo", "arbitro")
    result = parse_vote(payload("approve"), reviewer=arbiter)

    with pytest.raises(ValueError, match="gateway"):
        resolve_with_synthesis(target, arbiter=arbiter, result=result)


def test_store_persiste_layout_privado_sem_raw_ou_think(tmp_path: Path) -> None:
    target = panel()
    store = QuorumStore(tmp_path / "quorum")
    directory = store.create_panel(target)
    add_votes(target, "approve", "approve", "reject")
    for result in target.votes:
        store.save_vote(target.id, result)
    decision = decide_panel(target)
    target.decision = decision
    store.save_decision(target.id, decision)

    assert (directory / "task.json").is_file()
    assert (directory / "members.json").is_file()
    assert len(list((directory / "votes").glob("*.json"))) == 3
    assert (directory / "decision.json").is_file()
    assert (directory / "events.jsonl").is_file()
    assert (directory.stat().st_mode & 0o777) == 0o700
    assert all((path.stat().st_mode & 0o777) == 0o600 for path in directory.rglob("*.json"))

    serialized = " ".join(path.read_text() for path in directory.rglob("*.*"))
    assert "raw_response" not in serialized
    assert "<think" not in serialized.lower()
    loaded = store.load_panel(target.id)
    assert loaded.decision is not None
    assert loaded.decision.outcome.value == "promote"


def test_store_recusa_path_escape_e_voto_duplicado(tmp_path: Path) -> None:
    target = panel()
    store = QuorumStore(tmp_path)
    with pytest.raises(QuorumStoreError, match="inseguro"):
        store.load_panel("../fora")
    store.create_panel(target)
    result = parse_vote(payload(), reviewer=target.members[0])
    store.save_vote(target.id, result)
    with pytest.raises(QuorumStoreError, match="já votou"):
        store.save_vote(target.id, result)


# --- Modo 1: a conclusão que saiu dentro do raciocínio -----------------------


def test_voto_fechado_dentro_do_think_e_recuperado() -> None:
    """Modelo ajustado para raciocinar às vezes fecha o JSON dentro do próprio bloco.

    Descartar isso custou seis votos válidos numa execução real: a resposta inteira
    era raciocínio, e o que sobrava depois da remoção era string vazia.
    """
    reviewer = panel().members[0]
    result = parse_vote(f"<think>penso e concluo {payload()}</think>", reviewer=reviewer)
    assert result.schema_valid
    assert result.recovered_from_reasoning
    assert result.structured_vote.decision == VoteDecision.APPROVE
    assert "penso e concluo" not in result.final_response
    assert "<think" not in result.final_response.lower()


def test_conclusao_declarada_fora_vence_rascunho_dentro_do_think() -> None:
    reviewer = panel().members[0]
    result = parse_vote(
        f"<think>rascunho {payload('reject')}</think>{payload('approve')}",
        reviewer=reviewer,
    )
    assert result.schema_valid
    assert not result.recovered_from_reasoning
    assert result.structured_vote.decision == VoteDecision.APPROVE


def test_resposta_so_de_raciocinio_continua_sendo_falha() -> None:
    reviewer = panel().members[0]
    result = parse_vote("<think>penso muito e não concluo nada</think>", reviewer=reviewer)
    assert not result.schema_valid
    assert result.structured_vote.decision == VoteDecision.ABSTAIN
    assert result.error is not None
    assert "penso muito" not in (result.final_response + (result.error or ""))


def test_voto_dentro_de_fence_markdown_e_lido() -> None:
    reviewer = panel().members[0]
    result = parse_vote(f"```json\n{payload()}\n```", reviewer=reviewer)
    assert result.schema_valid
    assert result.structured_vote.decision == VoteDecision.APPROVE


def test_dois_votos_validos_na_mesma_resposta_sao_ambiguos() -> None:
    """Escolher entre duas conclusões seria o orquestrador votando pelo avaliador."""
    reviewer = panel().members[0]
    result = parse_vote(f"{payload('approve')}\n{payload('reject')}", reviewer=reviewer)
    assert not result.schema_valid
    assert result.structured_vote.decision == VoteDecision.ABSTAIN
    assert result.error is not None
    assert "ambíguo" in result.error


def test_objeto_incompleto_nao_arrasta_o_resto_da_resposta() -> None:
    reviewer = panel().members[0]
    result = parse_vote('{"decision":"approve", nunca fecha', reviewer=reviewer)
    assert not result.schema_valid
    assert result.structured_vote.decision == VoteDecision.ABSTAIN


# --- Modo 2: o teto que só o servidor conhece --------------------------------


def test_avaliacao_de_213_caracteres_e_aceita() -> None:
    """O comprimento exato que foi descartado contra o teto antigo de 120."""
    reviewer = panel().members[0]
    longa = "A dinâmica da LQG e sua recuperação de GR seguem em aberto. " * 4
    assert len(longa.strip()) > 120
    vote = json.loads(payload())
    vote["evidence"] = [{"claim": "CLM-FIS-LQG-004", "assessment": longa.strip()}]
    result = parse_vote(json.dumps(vote), reviewer=reviewer)
    assert result.schema_valid
    assert result.structured_vote.evidence[0].assessment == longa.strip()


def test_avaliacao_acima_do_teto_falha_sem_truncar() -> None:
    reviewer = panel().members[0]
    vote = json.loads(payload())
    vote["evidence"] = [{"claim": "CLM-FIS-LQG-004", "assessment": "x" * 2_049}]
    result = parse_vote(json.dumps(vote), reviewer=reviewer)
    assert not result.schema_valid
    assert result.structured_vote.evidence == []


def test_schema_transmitido_omite_maxlength_e_nao_pede_raciocinio() -> None:
    """O que o modelo não consegue obedecer não é anunciado como se fosse regra."""
    contrato = vote_contract()
    schema = json.loads(contrato.split("JSON Schema fechado:\n", 1)[1])
    serialized = json.dumps(schema)
    assert "maxLength" not in serialized
    assert "reasoning_log" not in contrato
    assert "chain_of_thought" not in contrato
    assert schema["properties"]["decision"]["$ref"].endswith("VoteDecision")


def test_invariantes_do_quorum_seguem_iguais() -> None:
    """Os reparos restauram a leitura do voto; nenhum deles afrouxa a decisão."""
    from vault.quorum.engine import MIN_FAMILIES, MIN_PROVIDERS, MIN_VALID_VOTES

    assert (MIN_VALID_VOTES, MIN_PROVIDERS, MIN_FAMILIES) == (3, 2, 2)

    proposer = member("groq", "fact-model", "qwen", "proponente")
    with pytest.raises(ValidationError, match="não avalia a própria proposta"):
        Panel(
            task=PanelTask(kind="teste", prompt="p"),
            proposal=Proposal(proposer=proposer, final_response="proposta"),
            members=panel().members,
        )


def test_nenhum_campo_de_raciocinio_atravessa_o_contrato_do_voto() -> None:
    from vault.quorum.models import Vote

    serialized = json.dumps(Vote.model_json_schema())
    for proibido in ("reasoning_log", "chain_of_thought", "reasoning", "think"):
        assert proibido not in serialized
    result = parse_vote(f"<think>interno</think>{payload()}", reviewer=panel().members[0])
    assert "reasoning_log" not in json.dumps(result.model_dump(mode="json"))


def test_patch_fechado_dentro_do_think_e_recuperado() -> None:
    """O proponente sofre do mesmo defeito do avaliador, e custa a tarefa inteira."""
    patch = CorpusPatch(
        proposal_id="abc123",
        base_commit="b" * 40,
        operations=[
            PatchOperation(action="create", path="Nota.md", content="# Nota\n\nTexto.")
        ],
    )
    bruto = f"<think>penso e concluo {json.dumps(patch.to_dict())}</think>"
    parsed = parse_corpus_patch(
        bruto,
        expected_proposal_id="abc123",
        expected_base_commit="b" * 40,
    )
    assert parsed.patch.targets == ["Nota.md"]
    assert parsed.reasoning_block_removed
    assert "penso e concluo" not in parsed.canonical_response


def test_patch_declarado_fora_vence_rascunho_dentro_do_think() -> None:
    rascunho = CorpusPatch(
        proposal_id="abc123",
        base_commit="b" * 40,
        operations=[
            PatchOperation(action="create", path="Rascunho.md", content="# Rascunho\n\nX.")
        ],
    )
    final = CorpusPatch(
        proposal_id="abc123",
        base_commit="b" * 40,
        operations=[PatchOperation(action="create", path="Final.md", content="# Final\n\nY.")],
    )
    parsed = parse_corpus_patch(
        f"<think>{json.dumps(rascunho.to_dict())}</think>{json.dumps(final.to_dict())}",
        expected_proposal_id="abc123",
        expected_base_commit="b" * 40,
    )
    assert parsed.patch.targets == ["Final.md"]


def test_dois_patches_dentro_do_think_nao_sao_desempatados() -> None:
    um = CorpusPatch(
        proposal_id="abc123",
        base_commit="b" * 40,
        operations=[PatchOperation(action="create", path="Um.md", content="# Um\n\nX.")],
    )
    outro = CorpusPatch(
        proposal_id="abc123",
        base_commit="b" * 40,
        operations=[PatchOperation(action="create", path="Outro.md", content="# Outro\n\nY.")],
    )
    bruto = f"<think>{json.dumps(um.to_dict())} ou {json.dumps(outro.to_dict())}</think>"
    with pytest.raises(ProposalEnvelopeError, match="ambíguo"):
        parse_corpus_patch(
            bruto,
            expected_proposal_id="abc123",
            expected_base_commit="b" * 40,
        )


def test_prompt_do_proponente_declara_o_alvo_exato_em_vez_de_exigir_palpite() -> None:
    """O proponente devolveu `fisica/Selecao-Natural-Cosmologica.md` por adivinhação."""
    prompt = corpus_patch_prompt(
        "Reavalie o claim",
        proposal_id="p1",
        base_commit="c" * 40,
        allowed_targets=["Física/Seleção Natural Cosmológica.md"],
        allow_create=False,
    )
    assert "'Física/Seleção Natural Cosmológica.md'" in prompt
    assert "copie byte a byte" in prompt
    assert "não autoriza criar nota" in prompt


def test_prompt_sem_escopo_declarado_nao_inventa_restricao() -> None:
    prompt = corpus_patch_prompt("Crie a nota", proposal_id="p1", base_commit="c" * 40)
    assert "autorizado" not in prompt
    assert "não autoriza criar nota" not in prompt


def _patch_json(proposal_id: str, base: str, content: str = "# Nota\n\nTexto.") -> str:
    return json.dumps(
        {
            "proposal_id": proposal_id,
            "base_commit": base,
            "operations": [{"action": "create", "path": "Nota.md", "content": content}],
        }
    )


def test_json_truncado_sem_fechar_objeto_falha() -> None:
    proposal_id = "prop-trunc"
    base = "c" * 40
    bruto = _patch_json(proposal_id, base)[:-12]
    with pytest.raises(ProposalEnvelopeError, match="truncad"):
        parse_corpus_patch(
            bruto,
            expected_proposal_id=proposal_id,
            expected_base_commit=base,
        )


def test_fence_markdown_com_prosa_depois_e_lida() -> None:
    proposal_id = "prop-fence-prosa"
    base = "c" * 40
    raw = _patch_json(proposal_id, base, "# Nota\n\nCorpo.")
    parsed = parse_corpus_patch(
        f"Segue o patch:\n```JSON\n{raw}\n```\nEspero que sirva.",
        expected_proposal_id=proposal_id,
        expected_base_commit=base,
    )
    assert parsed.patch.targets == ["Nota.md"]
    assert parsed.patch.operations[0].content == "# Nota\n\nCorpo."
    assert "Espero" not in parsed.patch.operations[0].content


def test_ata_e_prosa_ao_redor_nao_poluem_o_content() -> None:
    proposal_id = "prop-ata"
    base = "c" * 40
    raw = _patch_json(proposal_id, base, "# Nota\n\nSomente o corpus.")
    envelopado = (
        "# Decisão do painel\n\n"
        f"{raw}\n\n"
        "# Painel abcdef012345\n"
        r"comando $\operatorname x$ mutilado"
    )
    parsed = parse_corpus_patch(
        envelopado,
        expected_proposal_id=proposal_id,
        expected_base_commit=base,
    )
    content = parsed.patch.operations[0].content
    assert content == "# Nota\n\nSomente o corpus."
    assert "Decisão do painel" not in content
    assert "abcdef012345" not in content
    assert "operatorname" not in content


def test_fence_mutilado_ainda_entrega_o_objeto() -> None:
    proposal_id = "prop-fence-quebrado"
    base = "c" * 40
    raw = _patch_json(proposal_id, base)
    parsed = parse_corpus_patch(
        f"```json\n{raw}\n`` extra",
        expected_proposal_id=proposal_id,
        expected_base_commit=base,
    )
    assert parsed.patch.targets == ["Nota.md"]


def test_reparo_so_para_envelope_incompleto() -> None:
    assert envelope_needs_repair(
        ProposalEnvelopeError("resposta do proponente truncada não obedece ao CorpusPatch")
    )
    assert envelope_needs_repair(ProposalEnvelopeError("unexpected end of data"))
    assert not envelope_needs_repair(
        ProposalEnvelopeError("2 objetos válidos na mesma resposta: patch ambíguo")
    )
    assert not envelope_needs_repair(
        ProposalEnvelopeError("proposal_id do patch diverge do identificador atribuído")
    )


def test_dois_objetos_validos_na_mesma_resposta_sao_ambiguos() -> None:
    proposal_id = "prop-amb"
    base = "c" * 40
    um = _patch_json(proposal_id, base, "# Um\n\nX.")
    outro = json.dumps(
        {
            "proposal_id": proposal_id,
            "base_commit": base,
            "operations": [
                {"action": "create", "path": "Outra.md", "content": "# Outra\n\nY."}
            ],
        }
    )
    with pytest.raises(ProposalEnvelopeError, match="ambíguo"):
        parse_corpus_patch(
            f"{um}\n{outro}",
            expected_proposal_id=proposal_id,
            expected_base_commit=base,
        )
