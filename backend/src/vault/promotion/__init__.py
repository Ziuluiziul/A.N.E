"""Promoção automática: do quórum ao commit, sem escrita direta no corpus."""

from vault.promotion.autonomy import (
    POLICY_VERSION,
    Eligibility,
    PromotionAuthorization,
    PromotionJournal,
    PromotionPolicy,
    PromotionReport,
    QuorumPromotion,
)
from vault.promotion.code_patch import (
    CodeOperation,
    CodePatch,
    CodePatchRefused,
    fora_de_alcance,
)
from vault.promotion.patch import (
    CorpusPatch,
    PatchOperation,
    PatchRefused,
    identifiers_in,
)
from vault.promotion.policy import (
    BudgetPolicy,
    BudgetRules,
    DecisionLedger,
    DiversityReport,
    Observables,
    PolicyDecision,
    observables_for,
)
from vault.promotion.promoter import (
    PATCH_DIGEST_KEY,
    PromotionRefused,
    PromotionResult,
    ProposalPromoter,
    verify_quorum,
)

__all__ = [
    "Eligibility",
    "POLICY_VERSION",
    "PromotionAuthorization",
    "PromotionJournal",
    "PromotionPolicy",
    "PromotionReport",
    "QuorumPromotion",
    "BudgetPolicy",
    "BudgetRules",
    "DecisionLedger",
    "DiversityReport",
    "Observables",
    "PolicyDecision",
    "observables_for",
    "fora_de_alcance",
    "PATCH_DIGEST_KEY",
    "CodeOperation",
    "CodePatch",
    "CodePatchRefused",
    "CorpusPatch",
    "PatchOperation",
    "PatchRefused",
    "identifiers_in",
    "PromotionRefused",
    "PromotionResult",
    "ProposalPromoter",
    "verify_quorum",
]
