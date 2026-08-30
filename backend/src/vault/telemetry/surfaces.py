"""As superfícies que se derivam do ledger — e só as que a amostra sustenta.

A ADR-003 admitiu quatro e recusou o resto. Ficam de fora contribuição marginal
semântica, afinidade, score global e reputação única: com 296 observações e um único
painel concluído, produziriam número com aparência estatística e conteúdo quase nulo.

Todas as superfícies carregam a contagem que as sustenta. Uma taxa de sucesso sobre duas
observações não é uma taxa — e quem lê precisa ver isso na mesma linha, não numa nota de
rodapé.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from vault.telemetry.records import OutcomeClass, OutcomeRecord, Stage

# Abaixo disso a fração é ruído e o relatório diz isso em vez de imprimir um percentual.
AMOSTRA_MINIMA = 5

# O papel que propõe não está em `PANEL_ROLES` do orquestrador: é a ponta que produz a
# proposta, e a aptidão dele é a taxa de "conseguiu entregar patch parseável".
PAPEL_PROPONENTE = "proponente"

# Só tarefas de painel têm proponente; diagnóstico é chamada única e não propõe.
_KINDS_SEM_PROPOSICAO = frozenset({"endpoint_diagnosis"})


@dataclass(frozen=True, slots=True)
class Capacidade:
    """O que um endpoint entrega hoje, e o que o impede."""

    chave: str
    tentativas: int
    ok: int
    por_classe: dict[str, int]
    ultima_falha: str | None

    @property
    def taxa_ok(self) -> float | None:
        if self.tentativas < AMOSTRA_MINIMA:
            return None
        return self.ok / self.tentativas


@dataclass(frozen=True, slots=True)
class Aptidao:
    """Probabilidade de um endpoint entregar resposta **utilizável** num estágio, papel
    e domínio.

    Não é competência epistêmica, e o nome evita a promessa: mede-se se o voto chegou
    válido em Física — ou se a proposta chegou parseável —, não se ele julgou Física
    corretamente. A segunda coisa exige desfecho independente, que é o M3.

    `stage` separa as duas taxas que o seletor não pode misturar: um modelo pode
    sintetizar bem (propose) e julgar mal (review).
    """

    stage: Stage
    endpoint: str
    role: str
    domain: str
    observacoes: int
    utilizaveis: int

    @property
    def taxa(self) -> float | None:
        if self.observacoes < AMOSTRA_MINIMA:
            return None
        return self.utilizaveis / self.observacoes


@dataclass(frozen=True, slots=True)
class CustoDeFechamento:
    """Quantas chamadas o sistema gastou por painel que chegou a decidir, e o funil
    por estágio que mostra onde as chamadas morrem antes de fechar."""

    paineis_decididos: int
    registros_de_chamada: int
    tentativas_por_decisao: float | None
    propostas_tentadas: int = 0
    propostas_parseaveis: int = 0
    votos_tentados: int = 0
    votos_validos: int = 0
    decisoes_promote: int = 0


@dataclass(frozen=True, slots=True)
class Lacuna:
    """Um dado que a calibração vai exigir e que hoje não existe."""

    nome: str
    motivo: str


@dataclass(frozen=True, slots=True)
class Superficies:
    capacidade: list[Capacidade]
    aptidao: list[Aptidao]
    custo: CustoDeFechamento
    pivotalidade: dict[str, int]
    lacunas: list[Lacuna] = field(default_factory=list)


def _capacidade(records: list[OutcomeRecord]) -> list[Capacidade]:
    tentativas: dict[str, list[OutcomeRecord]] = defaultdict(list)
    for registro in records:
        if registro.stage is Stage.ATTEMPT and registro.provider:
            tentativas[registro.key].append(registro)
    saida: list[Capacidade] = []
    for chave, itens in tentativas.items():
        classes = Counter(item.outcome_class.value for item in itens)
        falhas = [i for i in itens if i.outcome_class is not OutcomeClass.OK and i.at]
        saida.append(
            Capacidade(
                chave=chave,
                tentativas=len(itens),
                ok=classes.get(OutcomeClass.OK.value, 0),
                por_classe=dict(classes.most_common()),
                ultima_falha=max((f.at for f in falhas), default=None),
            )
        )
    return sorted(saida, key=lambda c: (-c.tentativas, c.chave))


def _aptidao(records: list[OutcomeRecord]) -> list[Aptidao]:
    grupos: dict[tuple[str, str, str], list[OutcomeRecord]] = defaultdict(list)
    for registro in records:
        if registro.stage is not Stage.VOTE or not registro.endpoint or not registro.role:
            continue
        grupos[(registro.key, registro.role, registro.domain or "—")].append(registro)
    return sorted(
        (
            Aptidao(
                stage=Stage.VOTE,
                endpoint=endpoint,
                role=role,
                domain=domain,
                observacoes=len(itens),
                utilizaveis=sum(1 for i in itens if i.schema_valid),
            )
            for (endpoint, role, domain), itens in grupos.items()
        ),
        key=lambda a: (-a.observacoes, a.endpoint),
    )


def _proposicao(records: list[OutcomeRecord]) -> list[Aptidao]:
    """A aptidão de **produzir proposta**: tentativas de proponente × patches
    parseáveis.

    Tentativa é a chamada do proponente: o registro de `ATTEMPT` de tarefa de painel
    que morreu **antes** de criar o painel (sem `panel_id` — quem falhou foi o
    proponente) mais o registro de `PROPOSAL`, que só existe quando o envelope passou
    do proponente para o painel. Tentativa que morreu depois do painel existir não é
    culpa do proponente e não entra.
    """
    tentativas: dict[tuple[str, str], list[OutcomeRecord]] = defaultdict(list)
    sucessos: Counter[tuple[str, str]] = Counter()
    for registro in records:
        if registro.stage is Stage.PROPOSAL:
            if registro.endpoint:
                sucessos[(registro.key, registro.domain or "—")] += 1
        elif (
            registro.stage is Stage.ATTEMPT
            and registro.task_kind not in _KINDS_SEM_PROPOSICAO
            and not registro.panel_id
            and registro.endpoint
        ):
            tentativas[(registro.key, registro.domain or "—")].append(registro)
    chaves = {*tentativas, *sucessos}
    return sorted(
        (
            Aptidao(
                stage=Stage.PROPOSAL,
                endpoint=endpoint,
                role=PAPEL_PROPONENTE,
                domain=domain,
                observacoes=len(tentativas[(endpoint, domain)]) + sucessos[(endpoint, domain)],
                utilizaveis=sucessos[(endpoint, domain)],
            )
            for endpoint, domain in chaves
        ),
        key=lambda a: (-a.observacoes, a.endpoint),
    )


def _custo(records: list[OutcomeRecord]) -> CustoDeFechamento:
    decididos = sum(1 for r in records if r.stage is Stage.DECISION)
    chamadas = sum(
        1 for r in records if r.stage in {Stage.ATTEMPT, Stage.PROPOSAL, Stage.VOTE}
    )
    propostas = [r for r in records if r.stage is Stage.PROPOSAL]
    tentativas_de_proposta = [
        r
        for r in records
        if r.stage is Stage.ATTEMPT
        and r.task_kind not in _KINDS_SEM_PROPOSICAO
        and not r.panel_id
    ]
    votos = [r for r in records if r.stage is Stage.VOTE]
    return CustoDeFechamento(
        paineis_decididos=decididos,
        registros_de_chamada=chamadas,
        tentativas_por_decisao=(chamadas / decididos) if decididos else None,
        propostas_tentadas=len(propostas) + len(tentativas_de_proposta),
        propostas_parseaveis=len(propostas),
        votos_tentados=len(votos),
        votos_validos=sum(1 for v in votos if v.schema_valid),
        decisoes_promote=sum(
            1 for r in records if r.stage is Stage.DECISION and r.decision_outcome == "promote"
        ),
    )


def _lacunas(records: list[OutcomeRecord]) -> list[Lacuna]:
    faltas: list[Lacuna] = []
    if not any(r.validation_outcome for r in records):
        faltas.append(
            Lacuna(
                "validation_outcome",
                "nenhum patch passou pelas guardas reais; sem isso não há contra o que "
                "calibrar o revisor-estrutural",
            )
        )
    if not any(r.promotion_outcome for r in records):
        faltas.append(
            Lacuna(
                "promotion_outcome",
                "zero promoções: o desfecho canônico do corpus nunca ocorreu",
            )
        )
    faltas.append(
        Lacuna(
            "tokens por chamada",
            "o ledger de cota grava por endpoint em janela deslizante, sem task_id nem "
            "panel_id; correlacionar por horário erra sob concorrência",
        )
    )
    if not any(r.outcome_class is OutcomeClass.OK for r in records if r.stage is Stage.ATTEMPT):
        faltas.append(
            Lacuna("tentativa bem-sucedida", "nenhuma tentativa de tarefa terminou em ok")
        )
    return faltas


def build_surfaces(records: list[OutcomeRecord]) -> Superficies:
    aptidao = [*_aptidao(records), *_proposicao(records)]
    return Superficies(
        capacidade=_capacidade(records),
        aptidao=sorted(aptidao, key=lambda a: (-a.observacoes, a.stage.value, a.endpoint)),
        custo=_custo(records),
        pivotalidade=dict(
            Counter(r.pivotal for r in records if r.pivotal).most_common()
        ),
        lacunas=_lacunas(records),
    )
