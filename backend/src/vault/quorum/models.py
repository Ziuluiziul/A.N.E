"""Contratos fechados do quórum multimodelo.

Os modelos desta camada representam somente conclusões explícitas. Resposta bruta e
conteúdo de ``<think>`` não têm campo aqui de propósito: o que não cabe no contrato
não pode atravessar por acidente a fronteira de persistência.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_REASONING_TAG = re.compile(r"<\s*/?\s*think\b", re.IGNORECASE)


def _identifier() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class VoteDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REVISE = "revise"
    ABSTAIN = "abstain"


class RecommendedAction(StrEnum):
    PROMOTE = "promote"
    REVISE = "revise"
    REJECT = "reject"
    ESCALATE = "escalate"


class DecisionStatus(StrEnum):
    DECIDED = "decided"
    NEEDS_SYNTHESIS = "needs_synthesis"


class EvidenceAssessment(FrozenModel):
    """Um par afirmação/avaliação vindo de um revisor.

    Os tetos são de armazenamento, não de estilo, e por isso são generosos: o schema
    transmitido ao modelo não os anuncia (ver ``parser._without_length_bounds``),
    porque nenhum provedor os impõe na decodificação. Teto apertado aqui reprovaria
    voto correto por diferença de bytes — foi como um voto de 213 caracteres virou
    abstenção contra um limite de 120. Estouro acima deste teto é falha de análise, e
    a avaliação do revisor nunca é truncada para caber.
    """

    claim: str = Field(min_length=1, max_length=2_048)
    assessment: str = Field(min_length=1, max_length=2_048)


class PanelTask(FrozenModel):
    id: str = Field(default_factory=_identifier, min_length=1, max_length=64)
    kind: str = Field(min_length=1, max_length=80)
    prompt: str = Field(min_length=1, max_length=48_000)
    created_at: str = Field(default_factory=_now, min_length=1, max_length=80)
    context: dict[str, Any] = Field(default_factory=dict)


class PanelMember(FrozenModel):
    provider: str = Field(min_length=1, max_length=80)
    endpoint_id: str = Field(min_length=1, max_length=300)
    family: str = Field(min_length=1, max_length=160)
    role_name: str = Field(min_length=1, max_length=80)

    @property
    def key(self) -> str:
        return f"{self.provider}/{self.endpoint_id}"


class Proposal(FrozenModel):
    id: str = Field(default_factory=_identifier, min_length=1, max_length=64)
    proposer: PanelMember
    final_response: str = Field(min_length=1, max_length=96_000)
    reasoning_block_detected: bool = False
    reasoning_block_removed: bool = False

    @field_validator("final_response")
    @classmethod
    def reasoning_never_survives(cls, value: str) -> str:
        if _REASONING_TAG.search(value):
            raise ValueError("final_response ainda contém marca de raciocínio")
        return value

    @model_validator(mode="after")
    def detected_reasoning_was_removed(self) -> Proposal:
        if self.reasoning_block_detected != self.reasoning_block_removed:
            raise ValueError("bloco detectado precisa ser removido antes da proposta")
        return self


class Vote(FrozenModel):
    decision: VoteDecision
    confidence: float = Field(ge=0.0, le=1.0)
    blocking_issues: list[str] = Field(default_factory=list, max_length=100)
    non_blocking_issues: list[str] = Field(default_factory=list, max_length=100)
    evidence: list[EvidenceAssessment] = Field(default_factory=list, max_length=200)
    recommended_action: RecommendedAction

    @field_validator("blocking_issues", "non_blocking_issues")
    @classmethod
    def issues_are_bounded(cls, value: list[str]) -> list[str]:
        if any(not item.strip() or len(item) > 1_000 for item in value):
            raise ValueError("issue vazia ou longa demais")
        return value

    @model_validator(mode="after")
    def action_matches_decision(self) -> Vote:
        expected = {
            VoteDecision.APPROVE: RecommendedAction.PROMOTE,
            VoteDecision.REJECT: RecommendedAction.REJECT,
            VoteDecision.REVISE: RecommendedAction.REVISE,
            VoteDecision.ABSTAIN: RecommendedAction.ESCALATE,
        }
        if self.recommended_action != expected[self.decision]:
            raise ValueError("recommended_action contradiz decision")
        return self


def abstention() -> Vote:
    return Vote(
        decision=VoteDecision.ABSTAIN,
        confidence=0.0,
        blocking_issues=[],
        non_blocking_issues=[],
        evidence=[],
        recommended_action=RecommendedAction.ESCALATE,
    )


class ParseResult(FrozenModel):
    reviewer: PanelMember
    final_response: str = Field(default="", max_length=96_000)
    structured_vote: Vote
    schema_valid: bool
    reasoning_block_detected: bool = False
    reasoning_block_removed: bool = False
    repair_attempted: bool = False
    repair_succeeded: bool = False
    # O voto veio de dentro do bloco de raciocínio, porque não havia nenhum fora dele.
    # É procedência, não conteúdo: o texto do raciocínio continua sem campo aqui.
    recovered_from_reasoning: bool = False
    error: str | None = Field(default=None, max_length=500)

    @field_validator("final_response")
    @classmethod
    def reasoning_never_survives(cls, value: str) -> str:
        if _REASONING_TAG.search(value):
            raise ValueError("final_response ainda contém marca de raciocínio")
        return value

    @model_validator(mode="after")
    def invalid_vote_is_abstention(self) -> ParseResult:
        if not self.schema_valid and self.structured_vote.decision != VoteDecision.ABSTAIN:
            raise ValueError("voto fora do schema precisa ser abstain")
        if self.reasoning_block_detected != self.reasoning_block_removed:
            raise ValueError("bloco detectado precisa ser removido antes do voto")
        if self.repair_succeeded and not self.repair_attempted:
            raise ValueError("reparo bem-sucedido sem tentativa")
        return self


class StructuralFailure(FrozenModel):
    source: str = Field(min_length=1, max_length=120)
    issue: str = Field(min_length=1, max_length=1_000)
    reviewer: PanelMember | None = None


class VoteSnapshot(FrozenModel):
    reviewer: PanelMember
    decision: VoteDecision
    confidence: float = Field(ge=0.0, le=1.0)
    recommended_action: RecommendedAction
    schema_valid: bool
    counted: bool


class QuorumDecision(FrozenModel):
    id: str = Field(default_factory=_identifier, min_length=1, max_length=64)
    panel_id: str = Field(min_length=1, max_length=64)
    outcome: RecommendedAction
    status: DecisionStatus
    reason: str = Field(min_length=1, max_length=2_000)
    valid_vote_count: int = Field(ge=0)
    provider_count: int = Field(ge=0)
    family_count: int = Field(ge=0)
    tally: dict[VoteDecision, int]
    votes: list[VoteSnapshot]
    structural_failures: list[StructuralFailure] = Field(default_factory=list)
    synthesized_by: PanelMember | None = None
    decided_at: str = Field(default_factory=_now)

    @property
    def requires_synthesis(self) -> bool:
        return self.status == DecisionStatus.NEEDS_SYNTHESIS

    @field_validator("tally")
    @classmethod
    def tally_is_closed_and_non_negative(
        cls, value: dict[VoteDecision, int]
    ) -> dict[VoteDecision, int]:
        if set(value) != set(VoteDecision):
            raise ValueError("tally precisa declarar todo o vocabulário de votos")
        if any(isinstance(count, bool) or count < 0 for count in value.values()):
            raise ValueError("tally não aceita contagem negativa")
        return value

    @model_validator(mode="after")
    def decision_invariants(self) -> QuorumDecision:
        if sum(self.tally.values()) != self.valid_vote_count:
            raise ValueError("tally não corresponde à quantidade de votos válidos")
        if self.status == DecisionStatus.NEEDS_SYNTHESIS and (
            self.outcome != RecommendedAction.ESCALATE or self.synthesized_by is not None
        ):
            raise ValueError("empate não sintetizado precisa permanecer escalate")
        return self


class Panel(BaseModel):
    """Painel mutável apenas nas coleções de votos/decisão durante uma execução."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(default_factory=_identifier, min_length=1, max_length=64)
    task: PanelTask
    proposal: Proposal
    members: list[PanelMember] = Field(min_length=3)
    votes: list[ParseResult] = Field(default_factory=list)
    decision: QuorumDecision | None = None

    @model_validator(mode="after")
    def panel_invariants(self) -> Panel:
        if self.proposal.proposer.role_name != "proponente":
            raise ValueError("proposer precisa exercer o papel proponente")
        member_keys = [member.key for member in self.members]
        if self.proposal.proposer.key in member_keys:
            raise ValueError("proponente não avalia a própria proposta")
        if len(member_keys) != len(set(member_keys)):
            raise ValueError("um endpoint não pode votar duas vezes no painel")
        if len({member.provider for member in self.members}) < 2:
            raise ValueError("painel precisa de ao menos dois provedores")

        known = set(member_keys)
        vote_keys = [vote.reviewer.key for vote in self.votes]
        if any(key not in known for key in vote_keys):
            raise ValueError("voto pertence a endpoint fora do painel")
        if len(vote_keys) != len(set(vote_keys)):
            raise ValueError("um endpoint não pode registrar dois votos")
        if self.decision is not None and self.decision.panel_id != self.id:
            raise ValueError("decisão pertence a outro painel")
        return self
