"""O registro primário de desfecho — a unidade que o M0 torna legível de volta.

Um registro descreve **um evento que já aconteceu**: uma tentativa de tarefa, uma
proposta, um voto, uma decisão de painel. Nada aqui é derivado, agregado ou inferido;
médias e superfícies vivem em `surfaces.py`, sobre estes registros.

**Por que campos de token não existem aqui.** O ledger de cota grava `(instante, tokens)`
por endpoint, em janela deslizante, sem `task_id` nem `panel_id`. Ligar consumo a tarefa
exigiria correlacionar por horário, que erra sob concorrência — e o worker chama em
paralelo desde `2be6896`. Um campo sempre nulo seria pior que a ausência: pareceria
medido. A lacuna é reportada pelo próprio `make outcomes`, que é onde ela vira trabalho.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Stage(StrEnum):
    """Em que ponto do circuito o evento foi observado."""

    ADMISSION = "admission"
    ATTEMPT = "attempt"
    PROPOSAL = "proposal"
    VOTE = "vote"
    DECISION = "decision"


class OutcomeClass(StrEnum):
    """Classificação normalizada do desfecho.

    O vocabulário é fechado porque a superfície de capacidade conta por classe: um
    rótulo livre reapareceria com três grafias e dividiria a mesma causa em três linhas.
    `OUTRO` existe para não perder o evento quando a mensagem for nova — e a contagem
    dele é o sinal de que falta uma classe.
    """

    OK = "ok"
    ADIADO = "adiado-por-capacidade"
    RATE_LIMIT = "rate-limit"
    ENVELOPE_INVALIDO = "envelope-invalido"
    VOTOS_INSUFICIENTES = "votos-validos-insuficientes"
    PROMPT_ACIMA_DO_TETO = "prompt-acima-do-teto"
    ORCAMENTO_ESGOTADO = "orcamento-esgotado"
    SEM_DIVERSIDADE = "sem-diversidade"
    CREDENCIAL_IMPOSSIVEL = "credencial-impossivel"
    PROVEDOR_INDISPONIVEL = "provedor-indisponivel"
    RESPOSTA_VAZIA = "resposta-vazia"
    TEMPO_ESGOTADO = "tempo-esgotado"
    PATCH_FORA_DO_ALVO = "patch-fora-do-alvo"
    INTERROMPIDO = "interrompido"
    OUTRO = "outro"


# A ordem importa: a primeira chave encontrada na mensagem decide, e mensagens reais
# encaixam em mais de um padrão. `Request Entity Too Large` cita tamanho e vem de um 4xx;
# é teto de prompt, não rate limit.
_PADROES: tuple[tuple[str, OutcomeClass], ...] = (
    ("saiu dos alvos", OutcomeClass.PATCH_FORA_DO_ALVO),
    ("patch inválido", OutcomeClass.ENVELOPE_INVALIDO),
    ("ProposalEnvelope", OutcomeClass.ENVELOPE_INVALIDO),
    ("avaliações válidas", OutcomeClass.VOTOS_INSUFICIENTES),
    ("diversidade", OutcomeClass.SEM_DIVERSIDADE),
    ("Entity Too Large", OutcomeClass.PROMPT_ACIMA_DO_TETO),
    ("excede", OutcomeClass.PROMPT_ACIMA_DO_TETO),
    ("RateLimited", OutcomeClass.RATE_LIMIT),
    ("Rate limit", OutcomeClass.RATE_LIMIT),
    ("429", OutcomeClass.RATE_LIMIT),
    ("BYOK", OutcomeClass.CREDENCIAL_IMPOSSIVEL),
    ("AuthError", OutcomeClass.CREDENCIAL_IMPOSSIVEL),
    ("ProviderUnavailable", OutcomeClass.PROVEDOR_INDISPONIVEL),
    ("orçamento", OutcomeClass.ORCAMENTO_ESGOTADO),
    ("bloco de raciocínio", OutcomeClass.RESPOSTA_VAZIA),
    ("sem texto", OutcomeClass.RESPOSTA_VAZIA),
    ("Timeout", OutcomeClass.TEMPO_ESGOTADO),
    ("prazo", OutcomeClass.TEMPO_ESGOTADO),
    ("interrompid", OutcomeClass.INTERROMPIDO),
    ("processo terminou antes", OutcomeClass.INTERROMPIDO),
)


def classify(outcome: str | None, detail: str | None) -> OutcomeClass:
    """Reduz `(outcome, detail)` a uma classe do vocabulário fechado."""
    if outcome in {"completed", "promote", "ok"}:
        return OutcomeClass.OK
    texto = f"{outcome or ''} {detail or ''}"
    for chave, classe in _PADROES:
        if chave in texto:
            return classe
    return OutcomeClass.OUTRO


class OutcomeRecord(FrozenModel):
    """Um evento primário, como ele foi observado."""

    at: str
    stage: Stage
    outcome_class: OutcomeClass

    task_id: str
    panel_id: str | None = None
    task_kind: str | None = None
    domain: str | None = None
    corpus_entity: str | None = None

    role: str | None = None
    provider: str | None = None
    endpoint: str | None = None
    family: str | None = None

    latency_ms: int | None = None
    schema_valid: bool | None = None
    vote_decision: str | None = None
    confidence: float | None = None
    patch_digest: str | None = None
    # O rótulo bruto do desfecho do painel ("promote", "reject", "escalate"...).
    # `outcome_class` reduz ao vocabulário fechado; aqui fica o original, porque o
    # funil ("calls até promote") precisa contar o desfecho exato, não a classe.
    decision_outcome: str | None = None
    # Influência sobre a decisão, recalculada pela regra real do quórum. Mede peso, não
    # qualidade: um voto pode ser decisivo e estar errado — foi o caso do painel do stub.
    pivotal: str | None = None

    # Desfechos posteriores. Hoje quase sempre ausentes, e essa ausência é o achado:
    # sem eles não há contra o que calibrar revisor nenhum.
    validation_outcome: str | None = None
    promotion_outcome: str | None = None

    detail: str = Field(default="", max_length=400)

    @property
    def key(self) -> str:
        """Identidade do endpoint, no formato usado pelo inventário e pelo ledger."""
        return f"{self.provider}/{self.endpoint}"

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)
