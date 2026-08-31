"""Política de orçamento adaptativo — o A' do caminho autônomo.

O orçamento deixa de ser só o `RunBudget` fixo da execução e passa a ser decisão
de política sobre observáveis, com a tabela de decisão determinística e versionada
em dado (o bloco `budget` de `runtime/promotion/policy.json`), não em arquitetura:

- **DEFER**: a diversidade mínima é impossível com o acervo elegível — não gastar
  nenhuma chamada; a tarefa volta à fila (adiamento, não veredito).
- **SWITCH**: falha de schema persistente aponta endpoint inapto; a troca já existe
  no mecanismo de `failed_endpoint` — aqui a regra fica explícita e registrada.
- **EXPAND_BUDGET**: o fechamento é viável, mas o orçamento restante não cobre o
  custo esperado mais a margem — estender até o teto duro da política.
- **STOP**: o quórum já tem votos válidos suficientes — não planejar mais chamadas.

O teto duro (24 chamadas) é autoridade externa e mora em código; a política só
pode usar menos. O teto macio deixa de ser constante: vira o teto duro da política,
aplicado pela tabela. Cada decisão vai para o ledger `policy-decisions.jsonl`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from vault.work.quotas import RunBudget

# O teto que nenhuma política pode cruzar. Autoridade externa: mudá-lo é decisão
# humana, não ajuste de dado.
HARD_CEILING_CALLS = 24

LEDGER_NAME = "policy-decisions.jsonl"

# Limiar da janela de observação do ledger de desfechos para achar falha de schema
# persistente (SWITCH). Janela e limiar são defaults de código; a política pode
# declará-los no bloco `budget`.
OBSERVATION_WINDOW = 8
SCHEMA_FAILURE_THRESHOLD = 0.5


@dataclass(frozen=True, slots=True)
class DiversityReport:
    """Quantos provedores, famílias e endpoints distintos o painel ainda pode usar."""

    providers: int = 0
    endpoints: int = 0
    families: int = 0

    @property
    def viável(self) -> bool:
        # Painel = proponente + 3 avaliadores, todos distintos, 2 provedores.
        # Família é desempate, não silo: Groq vazio não adia o acervo vivo.
        return self.providers >= 2 and self.endpoints >= 4


@dataclass(frozen=True, slots=True)
class Observables:
    """O que a política vê no momento da decisão; nada além do estado vivo."""

    expected_calls: float = 4.0
    observed_sample_size: int = 0
    remaining_calls: int = 0
    valid_votes: int = 0
    required_votes: int = 3
    eligible_diversity: DiversityReport = field(default_factory=DiversityReport)
    schema_failure_rate: float = 0.0
    closure_probability: float = 0.0


class PolicyDecision(StrEnum):
    DEFER = "defer"
    SWITCH = "switch"
    EXPAND_BUDGET = "expand_budget"
    STOP = "stop"


@dataclass(frozen=True, slots=True)
class BudgetRules:
    """O bloco `budget` da política ativa. Defaults são a política em branco."""

    hard_ceiling_calls: int = HARD_CEILING_CALLS
    expansion_margin_calls: int = 2
    observation_window: int = OBSERVATION_WINDOW
    schema_failure_threshold: float = SCHEMA_FAILURE_THRESHOLD


class BudgetPolicy:
    """Lê o bloco `budget` do arquivo de política e aplica a tabela de decisão.

    Política em branco (sem bloco `budget`) age como a anterior: orçamento fixo,
    sem expansão. Com bloco, as quatro decisões valem — e o ledger registra todas.
    """

    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.rules = self._load()

    @property
    def active(self) -> bool:
        """Há bloco `budget` no arquivo? Sem bloco, a política em branco não muda nada."""
        if self.path is None:
            return False
        caminho = self.path
        if not caminho.is_file():
            return False
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return isinstance(dados.get("budget"), dict)

    def _load(self) -> BudgetRules:
        if not self.active:
            return BudgetRules()
        caminho = self.path
        assert caminho is not None
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return BudgetRules()
        bloco = dados.get("budget")
        if not isinstance(bloco, dict):
            return BudgetRules()
        ceiling = bloco.get("hard_ceiling_calls", HARD_CEILING_CALLS)
        if not isinstance(ceiling, int) or not 1 <= ceiling <= HARD_CEILING_CALLS:
            ceiling = HARD_CEILING_CALLS
        margem = bloco.get("expansion_margin_calls", 2)
        if not isinstance(margem, int) or not 0 <= margem <= 8:
            margem = 2
        janela = bloco.get("observation_window", OBSERVATION_WINDOW)
        if not isinstance(janela, int) or not 1 <= janela <= 64:
            janela = OBSERVATION_WINDOW
        limiar = bloco.get("schema_failure_threshold", SCHEMA_FAILURE_THRESHOLD)
        if not isinstance(limiar, (int, float)) or not 0.0 <= limiar <= 1.0:
            limiar = SCHEMA_FAILURE_THRESHOLD
        return BudgetRules(
            hard_ceiling_calls=ceiling,
            expansion_margin_calls=margem,
            observation_window=janela,
            schema_failure_threshold=limiar,
        )

    @property
    def version(self) -> str:
        if self.path is None:
            return "em-branco"
        caminho = self.path
        if not caminho.is_file():
            return "em-branco"
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return "ilegível"
        return str(dados.get("policy_version") or "indefinido")

    def decide(self, observáveis: Observables) -> PolicyDecision | None:
        """A tabela, na ordem: impossibilidade > inaptidão > escassez > suficiência."""
        if not observáveis.eligible_diversity.viável:
            return PolicyDecision.DEFER
        if (
            observáveis.observed_sample_size >= self.rules.observation_window
            and observáveis.schema_failure_rate >= self.rules.schema_failure_threshold
        ):
            return PolicyDecision.SWITCH
        necessario = observáveis.expected_calls + self.rules.expansion_margin_calls
        if observáveis.remaining_calls < necessario:
            return PolicyDecision.EXPAND_BUDGET
        if observáveis.valid_votes >= observáveis.required_votes:
            return PolicyDecision.STOP
        return None

    def effective_budget(
        self,
        observáveis: Observables,
        process_budget: RunBudget,
    ) -> RunBudget:
        """O orçamento que o ciclo efetivamente usa.

        Sem expansão aplicável, devolve o orçamento do processo sem tocar em nada.
        Com expansão, estende até o teto duro da política, nunca além dele, e nunca
        abaixo do teto do processo.
        """
        if not observáveis.eligible_diversity.viável:
            return process_budget
        necessario = observáveis.expected_calls + self.rules.expansion_margin_calls
        if observáveis.remaining_calls >= necessario:
            return process_budget
        estendido = int(
            min(
                self.rules.hard_ceiling_calls,
                observáveis.remaining_calls + necessario,
            )
        )
        if estendido <= process_budget.max_calls:
            return process_budget
        return RunBudget(max_calls=estendido)


class DecisionLedger:
    """Registro append-only das decisões de política, sem reescrita de passado."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def record(
        self,
        *,
        task_id: str,
        policy_version: str,
        decision: PolicyDecision | None,
        reason: str,
        observáveis: Observables,
        effective_budget: RunBudget | None = None,
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entrada = {
            "at": datetime.now(UTC).isoformat(),
            "task_id": task_id,
            "policy_version": policy_version,
            "decision": None if decision is None else decision.value,
            "reason": reason[:500],
            "observables": {
                "expected_calls": observáveis.expected_calls,
                "observed_sample_size": observáveis.observed_sample_size,
                "remaining_calls": observáveis.remaining_calls,
                "valid_votes": observáveis.valid_votes,
                "required_votes": observáveis.required_votes,
                "eligible_diversity": {
                    "providers": observáveis.eligible_diversity.providers,
                    "endpoints": observáveis.eligible_diversity.endpoints,
                    "families": observáveis.eligible_diversity.families,
                },
                "schema_failure_rate": round(observáveis.schema_failure_rate, 4),
                "closure_probability": round(observáveis.closure_probability, 4),
            },
            "effective_budget": (
                None if effective_budget is None else effective_budget.max_calls
            ),
        }
        temporario = self.path.with_name(f".{self.path.name}.tmp")
        temporario.write_text(
            json.dumps(entrada, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        with temporario.open("rb") as origem, self.path.open("ab") as destino:
            destino.write(origem.read())
        temporario.unlink(missing_ok=True)


def observables_for(
    *,
    remaining_calls: int,
    eligible_providers: int,
    eligible_endpoints: int,
    eligible_families: int = 0,
    expected_calls: float = 4.0,
    observed_sample_size: int = 0,
    schema_failures: int = 0,
    valid_votes: int = 0,
    required_votes: int = 3,
    total_attempts: int = 0,
) -> Observables:
    """Monta os observáveis a partir das contagens já apuradas pelo chamador."""
    amostra = observed_sample_size or total_attempts
    taxa = (
        (schema_failures / amostra) if amostra > 0 and schema_failures > 0 else 0.0
    )
    diversidade = DiversityReport(
        providers=eligible_providers,
        endpoints=eligible_endpoints,
        families=eligible_families,
    )
    viável = diversidade.viável
    fechamento = (
        1.0
        if viável and remaining_calls >= expected_calls
        else 0.0 if not viável else max(0.0, remaining_calls / max(expected_calls, 1))
    )
    return Observables(
        expected_calls=expected_calls,
        observed_sample_size=amostra,
        remaining_calls=remaining_calls,
        valid_votes=valid_votes,
        required_votes=required_votes,
        eligible_diversity=diversidade,
        schema_failure_rate=taxa,
        closure_probability=round(fechamento, 4),
    )
