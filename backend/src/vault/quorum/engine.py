"""Cálculo determinístico do quórum; confiança nunca vale como voto."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from vault.quorum.models import (
    DecisionStatus,
    Panel,
    ParseResult,
    QuorumDecision,
    RecommendedAction,
    StructuralFailure,
    VoteDecision,
    VoteSnapshot,
)

MIN_VALID_VOTES = 3
MIN_PROVIDERS = 2
MIN_FAMILIES = 2

# Um gateway identifica a fronteira contratada, não necessariamente uma origem de
# inferência independente. Enquanto o painel não persistir e comparar o upstream
# efetivo, contar esse rótulo como outro provedor poderia duplicar uma NVIDIA (ou
# qualquer rota direta) sob dois nomes. O gateway ainda pode propor e executar
# trabalho comum; apenas não prova diversidade epistemológica por si.
UNVERIFIED_GATEWAY_PROVIDERS = frozenset({"openrouter"})


def provider_counts_for_quorum(provider: str) -> bool:
    """Se a identidade atual prova uma origem independente para voto de quórum."""
    return provider not in UNVERIFIED_GATEWAY_PROVIDERS


def _counted(vote: ParseResult) -> bool:
    return (
        provider_counts_for_quorum(vote.reviewer.provider)
        and vote.schema_valid
        and vote.structured_vote.decision != VoteDecision.ABSTAIN
    )


def counted_vote(vote: ParseResult) -> bool:
    """Voto que entra no quórum: schema válido, não-abstenção, provedor que conta."""
    return _counted(vote)


def vote_snapshots(votes: Sequence[ParseResult]) -> list[VoteSnapshot]:
    return [
        VoteSnapshot(
            reviewer=result.reviewer,
            decision=result.structured_vote.decision,
            confidence=result.structured_vote.confidence,
            recommended_action=result.structured_vote.recommended_action,
            schema_valid=result.schema_valid,
            counted=_counted(result),
        )
        for result in votes
    ]


def _decision(
    panel: Panel,
    *,
    outcome: RecommendedAction,
    status: DecisionStatus,
    reason: str,
    valid: list[ParseResult],
    tally: Counter[VoteDecision],
    structural_failures: Sequence[StructuralFailure] = (),
) -> QuorumDecision:
    return QuorumDecision(
        panel_id=panel.id,
        outcome=outcome,
        status=status,
        reason=reason,
        valid_vote_count=len(valid),
        provider_count=len({vote.reviewer.provider for vote in valid}),
        family_count=len({vote.reviewer.family for vote in valid}),
        tally={decision: tally.get(decision, 0) for decision in VoteDecision},
        votes=vote_snapshots(panel.votes),
        structural_failures=list(structural_failures),
    )


def decide_panel(
    panel: Panel,
    *,
    structural_failures: Sequence[StructuralFailure] = (),
) -> QuorumDecision:
    """Decide por maioria estrita dos votos válidos, depois dos gates objetivos."""
    valid = [vote for vote in panel.votes if _counted(vote)]
    tally: Counter[VoteDecision] = Counter(
        result.structured_vote.decision for result in valid
    )

    if structural_failures:
        return _decision(
            panel,
            outcome=RecommendedAction.REJECT,
            status=DecisionStatus.DECIDED,
            reason="falha estrutural objetiva registrada",
            valid=valid,
            tally=tally,
            structural_failures=structural_failures,
        )
    if len(valid) < MIN_VALID_VOTES:
        return _decision(
            panel,
            outcome=RecommendedAction.ESCALATE,
            status=DecisionStatus.DECIDED,
            reason=f"{len(valid)} avaliações válidas; mínimo é {MIN_VALID_VOTES}",
            valid=valid,
            tally=tally,
        )
    providers = {vote.reviewer.provider for vote in valid}
    families = {vote.reviewer.family for vote in valid}
    if len(providers) < MIN_PROVIDERS or len(families) < MIN_FAMILIES:
        return _decision(
            panel,
            outcome=RecommendedAction.ESCALATE,
            status=DecisionStatus.DECIDED,
            reason=(
                f"diversidade insuficiente: {len(providers)} provedor(es), "
                f"{len(families)} família(s)"
            ),
            valid=valid,
            tally=tally,
        )

    winner, count = max(tally.items(), key=lambda item: item[1])
    if count <= len(valid) / 2:
        return _decision(
            panel,
            outcome=RecommendedAction.ESCALATE,
            status=DecisionStatus.NEEDS_SYNTHESIS,
            reason="nenhuma decisão obteve maioria simples; síntese independente necessária",
            valid=valid,
            tally=tally,
        )
    outcomes = {
        VoteDecision.APPROVE: RecommendedAction.PROMOTE,
        VoteDecision.REVISE: RecommendedAction.REVISE,
        VoteDecision.REJECT: RecommendedAction.REJECT,
    }
    return _decision(
        panel,
        outcome=outcomes[winner],
        status=DecisionStatus.DECIDED,
        reason=f"{winner.value} obteve {count} de {len(valid)} votos válidos",
        valid=valid,
        tally=tally,
    )
