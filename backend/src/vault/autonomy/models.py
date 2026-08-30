"""Contratos persistentes do trabalho autônomo.

Uma tarefa autônoma não é um ``vault.work.Task`` em espera. O contrato daqui
registra por que ela existe, quanto pode gastar e todas as tentativas que já
aconteceram. Só quando uma tentativa começa ela vira a tarefa efêmera que o
orquestrador já sabe distribuir.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import orjson
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class TaskOrigin(StrEnum):
    WEAK_CLAIM = "weak_claim"
    ISOLATED_NOTE = "isolated_note"
    UNDERREPRESENTED_DOMAIN = "underrepresented_domain"
    MODEL_DIVERGENCE = "model_divergence"
    REJECTED_PROPOSAL = "rejected_proposal"
    ENDPOINT_FAILURE = "endpoint_failure"
    IDLE_CAPACITY = "idle_capacity"
    POLICY_REVIEW = "policy_review"
    CORPUS_EXPANSION = "corpus_expansion"
    CORPUS_DEFECT = "corpus_defect"


class TaskState(StrEnum):
    QUEUED = "queued"
    ASSIGNED = "assigned"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    COMPLETED = "completed"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class TaskKind(StrEnum):
    CORPUS_REVIEW = "corpus_review"
    PROPOSAL_REVISION = "proposal_revision"
    DIVERGENCE_REVIEW = "divergence_review"
    ENDPOINT_DIAGNOSIS = "endpoint_diagnosis"


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TaskBudget(FrozenModel):
    # Quatro chamadas fecham o painel mínimo (proponente + três revisores). A
    # quinta é a única arbitragem permitida quando há empate; não é retry.
    max_calls: int = Field(default=5, ge=1, le=32)
    max_output_tokens: int = Field(default=2048, ge=64, le=32_768)


class TaskAttempt(FrozenModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12], min_length=1, max_length=64)
    started_at: str = Field(default_factory=now, min_length=1, max_length=80)
    finished_at: str | None = Field(default=None, max_length=80)
    endpoints: list[str] = Field(default_factory=list, max_length=32)
    outcome: str | None = Field(default=None, max_length=80)
    detail: str = Field(default="", max_length=1_000)
    panel_id: str | None = Field(default=None, max_length=64)

    @field_validator("endpoints")
    @classmethod
    def endpoints_are_unique(cls, value: list[str]) -> list[str]:
        if any(not endpoint.strip() or len(endpoint) > 400 for endpoint in value):
            raise ValueError("endpoint vazio ou longo demais")
        if len(value) != len(set(value)):
            raise ValueError("uma tentativa não repete endpoint")
        return value


# Janela do histórico de tentativas. O teto existe para o estado persistido não
# crescer sem limite; a janela é o mesmo número declarado uma vez só, porque o
# validador e a transição de `start` precisam concordar sobre ele.
ATTEMPTS_WINDOW = 100


class AutonomousTask(BaseModel):
    """Item durável da fila; mutável somente por transições validadas do store."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(min_length=12, max_length=64)
    origin: TaskOrigin
    objective: str = Field(min_length=1, max_length=16_000)
    priority: int = Field(ge=0, le=100)
    domain: str = Field(min_length=1, max_length=120)
    kind: TaskKind
    required_roles: list[str] = Field(min_length=1, max_length=8)
    budget: TaskBudget = Field(default_factory=TaskBudget)
    state: TaskState = TaskState.QUEUED
    corpus_entity: str | None = Field(default=None, max_length=500)
    source_fingerprint: str = Field(min_length=16, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)
    attempts: list[TaskAttempt] = Field(default_factory=list, max_length=ATTEMPTS_WINDOW)

    @field_validator("attempts", mode="before")
    @classmethod
    def attempts_fit_the_window(cls, value: object) -> object:
        """História além da janela cai, e a mais antiga cai primeiro.

        Sem isto, uma tarefa que acumulasse 101 tentativas — como a fila real
        alcançou em 2026-08-16 — deixava de carregar, e o worker caía no próprio
        estado persistido: o teto protegia o tamanho do arquivo, mas matava o
        processo. O teto continua valendo; o que muda é o excesso ser aparado na
        leitura em vez de explodir nela.
        """
        if isinstance(value, list) and len(value) > ATTEMPTS_WINDOW:
            return value[-ATTEMPTS_WINDOW:]
        return value
    next_eligible_at: str | None = Field(default=None, max_length=80)
    created_at: str = Field(default_factory=now, min_length=1, max_length=80)
    updated_at: str = Field(default_factory=now, min_length=1, max_length=80)

    @field_validator("required_roles")
    @classmethod
    def roles_are_unique(cls, value: list[str]) -> list[str]:
        roles = [role.strip() for role in value]
        if any(not role or len(role) > 80 for role in roles):
            raise ValueError("papel vazio ou longo demais")
        if len(roles) != len(set(roles)):
            raise ValueError("papel repetido na tarefa")
        return roles

    @model_validator(mode="after")
    def wait_has_a_time(self) -> AutonomousTask:
        if self.state is TaskState.RETRY_WAIT and self.next_eligible_at is None:
            raise ValueError("retry_wait exige próxima janela elegível")
        return self

    @property
    def attempted_endpoints(self) -> set[str]:
        return {endpoint for attempt in self.attempts for endpoint in attempt.endpoints}


def stable_task_id(origin: TaskOrigin, source: dict[str, Any]) -> tuple[str, str]:
    """Identidade estável enquanto a evidência de origem não mudar."""
    canonical = orjson.dumps(
        {"origin": origin.value, "source": source},
        option=orjson.OPT_SORT_KEYS,
    )
    fingerprint = hashlib.sha256(canonical).hexdigest()
    return f"aut-{fingerprint[:20]}", fingerprint


PANEL_ROLES = [
    "verificador-factual",
    "critico-epistemologico",
    "revisor-estrutural",
]
