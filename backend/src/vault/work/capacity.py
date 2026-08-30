"""M1 da ADR-003: quantos painéis completos cabem na capacidade de agora.

A pergunta que o sistema fazia era "quantos endpoints estão verdes?", e ela tem a
resposta errada. Um endpoint verde sozinho não fecha nada: o painel exige três votos
válidos, dois provedores e o mínimo de famílias que o motor de decisão aplica — e um
proponente fora dessa conta. A unidade certa é **painel fechável**, e é ela que este
módulo conta.

**Por que as constantes vêm de `vault.quorum.engine`.** Codificá-las aqui faria o
estimador responder uma pergunta e `decide_panel` responder outra. Foi o mesmo cuidado
que a pivotalidade do M0 tomou ao reusar `decide_panel` em vez de reimplementar a
maioria: se a política mudar, capacidade e decisão mudam juntas ou o controlador passa a
admitir o que o motor recusa.

**O resultado é um piso, não um teto.** O empacotamento é guloso, e um empacotamento
guloso pode deixar painel em cima da mesa. Para controle de admissão isso é a direção
segura do erro: subestimar adia trabalho, superestimar gasta chamada num painel que não
fecha — que é exatamente o desperdício que o M2 existe para eliminar.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from providers.inventory import EndpointProfile, Inventory
from vault.quorum.engine import (
    MIN_FAMILIES,
    MIN_PROVIDERS,
    MIN_VALID_VOTES,
    provider_counts_for_quorum,
)
from vault.work.quotas import EndpointLimits, QuotaLedger, RunBudget

# Proponente mais os revisores mínimos. É o menor painel que pode existir, e serve de
# piso para o custo esperado quando ainda não há histórico de fechamento.
CHAMADAS_MINIMAS_POR_PAINEL = MIN_VALID_VOTES + 1


class LimitingFactor(StrEnum):
    """O que impediu o próximo painel. É o que torna `complete_panels: 0` diagnosticável."""

    NONE = "none"
    QUOTA = "quota"
    DIVERSITY = "diversity"
    PROVIDER = "provider"
    FAMILY = "family"
    CONTEXT = "context"
    CALL_BUDGET = "call_budget"


@dataclass(frozen=True, slots=True)
class CapacityHints:
    """O que a telemetria informa ao estimador, e que ele não calcula sozinho.

    Vem do ledger de desfechos do M0. Fica separado do estimador porque reconstruir o
    ledger é caro e o ritmo dele é outro: capacidade muda a cada chamada, custo esperado
    e viabilidade mudam ao longo de horas.
    """

    expected_calls_per_closure: float | None = None
    unfit: frozenset[str] = frozenset()
    # Probabilidade observada de entrega utilizável, por (estágio, endpoint, papel,
    # domínio). Estágios: "proposal" (proponente) e "vote" (revisor). Só entra quem
    # tem amostra mínima; ausência significa "não medido", nunca "ruim" — preferência
    # é isso, não veredito. O piso de diversidade continua sendo do motor.
    aptitude: dict[tuple[str, str, str, str], float] = field(default_factory=dict)
    # Endpoints condenados **por estágio**: amostra longa e zero entregas utilizáveis.
    # É exclusão de preferência, não veredito — quem a diversidade precisar ainda
    # entra, porque o piso do motor vence a preferência do seletor.
    unfit_por_estagio: dict[str, frozenset[str]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class QuorumCapacity:
    """Quantos painéis completos cabem agora, e o que segura o próximo."""

    complete_panels: int
    reviewer_slots: int
    providers_available: int
    families_available: int
    calls_available: int
    calls_expected_per_closure: float
    limiting_factor: LimitingFactor
    next_eligible_at: str | None = None
    detail: str = ""
    # Os endpoints do primeiro painel empacotado. É o que a admissão segura: sem eles a
    # reserva existiria no nome da tarefa e não descontaria capacidade nenhuma, e dez
    # tarefas concorrentes voltariam a ler a mesma vaga.
    next_panel: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "complete_panels": self.complete_panels,
            "reviewer_slots": self.reviewer_slots,
            "providers_available": self.providers_available,
            "families_available": self.families_available,
            "calls_available": self.calls_available,
            "calls_expected_per_closure": round(self.calls_expected_per_closure, 2),
            "limiting_factor": self.limiting_factor.value,
            "next_eligible_at": self.next_eligible_at,
            "detail": self.detail,
            "next_panel": list(self.next_panel),
        }


def _diverso(grupo: Sequence[EndpointProfile]) -> bool:
    """A mesma diversidade que `decide_panel` exige dos votos válidos."""
    return (
        len({perfil.provider for perfil in grupo}) >= MIN_PROVIDERS
        and len({perfil.family for perfil in grupo}) >= MIN_FAMILIES
    )


def _montar_revisores(pool: list[EndpointProfile]) -> list[EndpointProfile] | None:
    """Um conjunto de revisores válido, gastando o pool na ordem de preferência.

    Começa pelos primeiros e troca o último por quem cubra a diversidade que falta. Não
    procura o conjunto ótimo: procura **um**, porque a pergunta é se existe.
    """
    if len(pool) < MIN_VALID_VOTES:
        return None
    base = pool[: MIN_VALID_VOTES]
    if _diverso(base):
        return base
    for candidato in pool[MIN_VALID_VOTES:]:
        for posicao in range(MIN_VALID_VOTES):
            tentativa = [*base[:posicao], candidato, *base[posicao + 1 :]]
            if _diverso(tentativa):
                return tentativa
    return None


def _fator_da_falta(pool: Sequence[EndpointProfile]) -> tuple[LimitingFactor, str]:
    """Por que este pool não fecha um painel."""
    if len(pool) < MIN_VALID_VOTES:
        return (
            LimitingFactor.QUOTA,
            f"{len(pool)} endpoint(s) elegíveis para {MIN_VALID_VOTES} votos",
        )
    provedores = len({perfil.provider for perfil in pool})
    familias = len({perfil.family for perfil in pool})
    if provedores < MIN_PROVIDERS:
        return LimitingFactor.PROVIDER, f"{provedores} provedor(es), mínimo {MIN_PROVIDERS}"
    if familias < MIN_FAMILIES:
        return LimitingFactor.FAMILY, f"{familias} família(s), mínimo {MIN_FAMILIES}"
    return (
        LimitingFactor.DIVERSITY,
        "há provedores e famílias suficientes no pool, mas não num mesmo conjunto",
    )


def estimate_quorum_capacity(
    inventory: Inventory,
    ledger: QuotaLedger,
    budget: RunBudget,
    *,
    reserved: Iterable[str] = (),
    unfit: Iterable[str] = (),
    estimated_tokens: int = 0,
    expected_calls_per_closure: float | None = None,
    limits_for: Callable[[EndpointProfile], EndpointLimits] | None = None,
    now: float | None = None,
) -> QuorumCapacity:
    """Quantos painéis completos podem ser admitidos agora.

    `reserved` são endpoints já prometidos a painéis admitidos e ainda não concluídos —
    sem isso, dez tarefas concorrentes leem `capacity=1` ao mesmo tempo e todas entram.

    `unfit` são endpoints operacionalmente mortos no horizonte, medidos pelo ledger de
    desfechos. Não é ranking, e não antecipa o M4: é um filtro binário de viabilidade,
    porque contar como reserva um endpoint com doze tentativas e nenhum sucesso é contar
    capacidade que não existe.
    """
    fora = {*reserved, *unfit}
    limites = limits_for or (
        lambda perfil: EndpointLimits.from_observed(
            perfil.observed_limits, perfil.model.declared_limits
        )
    )

    pool: list[EndpointProfile] = []
    sem_cota = 0
    for perfil in inventory.select(usable=True):
        if perfil.key in fora or not provider_counts_for_quorum(perfil.provider):
            continue
        if not ledger.allows(
            perfil.key, limites(perfil), estimated_tokens=estimated_tokens, now=now
        ):
            sem_cota += 1
            continue
        pool.append(perfil)

    provedores = len({perfil.provider for perfil in pool})
    familias = len({perfil.family for perfil in pool})

    # Custo esperado: medido, nunca constante. Sem histórico, o piso é o painel mínimo —
    # subestimar o custo é a direção errada do erro, então o piso é o menor valor honesto
    # e não um palpite otimista.
    esperado = max(
        float(expected_calls_per_closure or 0.0), float(CHAMADAS_MINIMAS_POR_PAINEL)
    )

    orcamento = budget.allows(ledger)
    disponiveis = _chamadas_disponiveis(budget, ledger)
    teto_por_chamada = int(disponiveis // esperado) if esperado > 0 else 0

    paineis = 0
    primeiro: tuple[str, ...] = ()
    restante = list(pool)
    while True:
        revisores = _montar_revisores(restante)
        if revisores is None:
            break
        usados = {perfil.key for perfil in revisores}
        sobra = [perfil for perfil in restante if perfil.key not in usados]
        if not sobra:  # sem proponente fora do painel, este conjunto não fecha
            break
        if not primeiro:
            primeiro = (*sorted(usados), sobra[0].key)
        paineis += 1
        restante = sobra[1:]

    limitado = min(paineis, teto_por_chamada) if orcamento else 0
    if not orcamento:
        fator, detalhe = LimitingFactor.CALL_BUDGET, orcamento.reason
    elif limitado == 0 and paineis == 0:
        fator, detalhe = _fator_da_falta(pool)
        if sem_cota and fator is LimitingFactor.QUOTA:
            detalhe = f"{detalhe}; {sem_cota} fora por cota"
    elif limitado < paineis:
        fator = LimitingFactor.CALL_BUDGET
        detalhe = f"{disponiveis} chamadas para {esperado:.1f} por fechamento"
    else:
        fator, detalhe = LimitingFactor.NONE, f"{limitado} painel(is) completo(s)"

    return QuorumCapacity(
        complete_panels=max(limitado, 0),
        reviewer_slots=len(pool),
        providers_available=provedores,
        families_available=familias,
        calls_available=disponiveis,
        calls_expected_per_closure=esperado,
        limiting_factor=fator,
        detail=detalhe,
        next_panel=primeiro if limitado > 0 else (),
    )


def _chamadas_disponiveis(budget: RunBudget, ledger: QuotaLedger) -> int:
    """Quantas chamadas o orçamento da execução ainda permite.

    Sai de `run_calls`, que é o mesmo contador que `RunBudget.allows` consulta. Somar os
    eventos do ledger daria outro número — eles são por escopo e por janela deslizante —
    e o estimador passaria a discordar do orçamento que ele deveria respeitar.
    """
    return max(budget.max_calls - ledger.run_calls, 0)
