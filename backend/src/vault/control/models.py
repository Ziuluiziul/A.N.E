"""O contrato do painel de controle. Uma leitura só, com a ausência declarada.

**Por que um snapshot e não várias rotas.** Provedor, catálogo, trabalhador, cota e
fila mudam em ritmos diferentes. Se o frontend montasse a verdade a partir de cinco
respostas, ele montaria cinco instantes diferentes: mostraria um trabalhador ligado a
um endpoint que a resposta seguinte já não lista. O snapshot é uma leitura coerente,
tirada de uma vez, com a hora em que foi tirada.

**A ausência tem campo.** Todo valor que pode faltar é `None` e vem acompanhado de um
motivo em `unavailable`. Zero e "não sei" não compartilham representação em lugar
nenhum deste arquivo — é a mesma regra epistêmica do corpus aplicada à telemetria.

**Segredo não tem campo.** Não existe atributo que carregue uma credencial. Existe
`key_configured`, que é booleano, e `key_hint`, que são no máximo quatro caracteres
finais. Nenhuma resposta desta API pode conter o valor integral, e não há caminho de
código por onde ele passaria.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProviderStatus = Literal[
    "configurado",  # há credencial; ninguém testou ainda
    "ausente",  # não há credencial
    "invalido",  # o provedor recusou a credencial
    "disponivel",  # o provedor respondeu com a credencial atual
    "erro",  # falhou por outro motivo, com detalhe sanitizado
]

WorkerStatus = Literal["ativo", "inativo", "espera", "erro", "desconhecido"]


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReasoningSupport(Frozen):
    """Capacidade de raciocínio **declarada**. Nunca inferida do nome do modelo.

    `supported` só é verdadeiro quando o catálogo declara os níveis. Um endpoint que
    apenas mencione raciocínio, sem dizer quais níveis aceita, continua `False`:
    oferecer um seletor exigiria inventar as opções, e opção inventada é pior que
    seletor ausente — ela promete um controle que não existe.
    """

    supported: bool = False
    options: list[str] = Field(default_factory=list, max_length=16)
    value: str | None = Field(default=None, max_length=64)
    reason: str = ""


class ProviderState(Frozen):
    id: str
    name: str
    status: ProviderStatus
    detail: str = ""
    key_configured: bool
    key_hint: str | None = Field(default=None, max_length=4)
    endpoint_count: int | None = None
    enabled: bool = True
    supports_custom_endpoint: bool = False
    unavailable: dict[str, str] = Field(default_factory=dict)


class WorkerState(Frozen):
    id: str
    role: str
    class_name: str
    summary: str
    area: str
    status: WorkerStatus
    provider: str | None = None
    model: str | None = None
    # Quem decidiu provedor e modelo desta linha. `indisponivel` quer dizer que
    # ninguém decidiu — nem a política, nem o mantenedor —, e é diferente de ter
    # decidido por nada.
    resolved_by: Literal["auto", "manual", "indisponivel"] = "indisponivel"
    reasoning: ReasoningSupport = Field(default_factory=ReasoningSupport)
    concurrency: int = 0
    concurrency_min: int = 0
    concurrency_max: int = 1
    enabled: bool = True
    running: int = 0
    detail: str = ""
    # O token de paleta desta linha, na mesma regra que a projeção operacional aplica.
    #
    # Ele viaja aqui porque a ADR-005 decidiu que o runtime possui a entidade — e quem
    # possui descreve. Sem isto o cliente teria de reimplementar a regra de cor para
    # desenhar o trabalhador que ele passou a possuir, e uma tabela duplicada quebra a
    # identidade visual em silêncio, que é exatamente o que o gate de paridade procura.
    palette_token: str = "D02"


class OperationState(Frozen):
    auto: bool
    active_workers: int | None = None
    capacity: int | None = None
    queued: int | None = None
    running: int | None = None
    last_cycle: str | None = None
    next_run: str | None = None
    calls: int | None = None
    budget: str | None = None
    failures: list[str] = Field(default_factory=list, max_length=20)
    last_audit: str | None = None
    unavailable: dict[str, str] = Field(default_factory=dict)


class ControlSnapshot(Frozen):
    schema_version: Literal[1] = 1
    generated_at: str = Field(default_factory=now)
    providers: list[ProviderState] = Field(default_factory=list)
    workers: list[WorkerState] = Field(default_factory=list)
    operation: OperationState
    notices: list[str] = Field(default_factory=list, max_length=20)


# --- corpos de mutação -------------------------------------------------------


class WorkerPatch(Frozen):
    """Só o que mudou. Campo ausente é "não mexa", não "apague"."""

    enabled: bool | None = None
    provider: str | None = Field(default=None, max_length=64)
    endpoint_id: str | None = Field(default=None, max_length=200)
    reasoning: str | None = Field(default=None, max_length=64)
    concurrency: int | None = Field(default=None, ge=0, le=64)


class AutoPatch(Frozen):
    auto: bool


class CredentialBody(Frozen):
    """O único lugar do backend por onde uma credencial entra.

    Ela não é guardada em nenhum atributo depois de gravada, e o modelo não é
    devolvido em resposta alguma — o que volta é `CredentialResult`.
    """

    key: str = Field(min_length=1, max_length=512, repr=False)


class CredentialResult(Frozen):
    provider: str
    key_configured: bool
    key_hint: str | None = Field(default=None, max_length=4)
    status: ProviderStatus
    detail: str = ""
