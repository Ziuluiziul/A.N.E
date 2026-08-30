"""Resolução explícita de empate por um endpoint que não integrou o painel."""

from __future__ import annotations

from vault.quorum.engine import decide_panel, provider_counts_for_quorum, vote_snapshots
from vault.quorum.models import (
    DecisionStatus,
    Panel,
    PanelMember,
    ParseResult,
    QuorumDecision,
    RecommendedAction,
    VoteDecision,
)


def resolve_with_synthesis(
    panel: Panel,
    *,
    arbiter: PanelMember,
    result: ParseResult,
) -> QuorumDecision:
    base = decide_panel(panel)
    if base.status != DecisionStatus.NEEDS_SYNTHESIS:
        return base
    used = {panel.proposal.proposer.key, *(member.key for member in panel.members)}
    if arbiter.key in used:
        raise ValueError("sintetizador precisa ser independente do proponente e do painel")
    if arbiter.role_name not in {"arbitro", "sintetizador"}:
        raise ValueError("resolução de empate exige papel arbitro ou sintetizador")
    if not provider_counts_for_quorum(arbiter.provider):
        raise ValueError("sintetizador gateway não comprova origem independente")
    if result.reviewer != arbiter:
        raise ValueError("resultado de síntese pertence a outro endpoint")

    counted = result.schema_valid and result.structured_vote.decision != VoteDecision.ABSTAIN
    mapping = {
        VoteDecision.APPROVE: RecommendedAction.PROMOTE,
        VoteDecision.REVISE: RecommendedAction.REVISE,
        VoteDecision.REJECT: RecommendedAction.REJECT,
    }
    outcome = mapping.get(result.structured_vote.decision, RecommendedAction.ESCALATE)
    reason = (
        f"síntese independente decidiu {result.structured_vote.decision.value}"
        if counted
        else "síntese independente inválida ou abstida"
    )
    return QuorumDecision(
        panel_id=panel.id,
        outcome=outcome,
        status=DecisionStatus.DECIDED,
        reason=reason,
        valid_vote_count=base.valid_vote_count,
        provider_count=base.provider_count,
        family_count=base.family_count,
        tally=base.tally,
        votes=[*vote_snapshots(panel.votes), *vote_snapshots([result])],
        synthesized_by=arbiter,
    )
