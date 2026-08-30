"""Os papéis do trabalho autodidata, e o que cada um instrui o modelo a fazer.

Papel é atribuído por capacidade, não por prestígio nominal do modelo. Um papel é
apenas três coisas: um nome estável que o quórum possa contar, uma instrução que diga
ao modelo o que produzir, e a informação de se ele pode avaliar proposta alheia.

As instruções carregam a política epistêmica do projeto porque é ela que separa
trabalho útil de texto plausível: identificador não verificado é omitido, ausência de
evidência não é refutação, e analogia não cria aresta. Um modelo que não receba isso
vai devolver exatamente o tipo de material que o corpus recusa.
"""

from __future__ import annotations

from dataclasses import dataclass

# Repetida em todo papel: é a regra que mais custa caro quando um modelo a ignora.
EPISTEMIC_FLOOR = """
Regras inegociáveis deste corpus:
- Nunca cite DOI, arXiv, ISBN ou URL que você não tenha certeza de estar correto.
  Na dúvida, omita a afirmação inteira. Identificador plausível e errado é pior que
  lacuna, porque passa por auditado.
- Ausência de evidência nunca é refutação. Se falta apoio, diga `open`, `hypothesis`
  ou `speculative` — nunca `refuted`.
- Analogia, metáfora e vocabulário compartilhado não criam relação entre notas.
- Se você não sabe, escreva que não sabe. Isso é resposta aceita e esperada.
""".strip()


# Teto de tarefas simultâneas por papel.
#
# Não é número escolhido por gosto: sai da forma do painel. Um painel mínimo tem três
# avaliadores, então três é o máximo de revisões que podem correr em paralelo sem que
# a quarta esteja esperando um painel que ainda não existe. O proponente produz uma
# proposta por tarefa e não se acumula; síntese e arbitragem acontecem depois de o
# painel fechar, uma vez cada. Quem manda no fim é o orçamento da execução
# (`work_max_calls`), que é menor que isto na configuração padrão.
REVIEW_CONCURRENCY = 3
SINGLE = 1


@dataclass(frozen=True, slots=True)
class Role:
    name: str
    summary: str
    instruction: str
    reviews_others: bool = False
    # Onde no Vault o papel age. É o que o painel de controle mostra como "área", e
    # vem daqui porque é aqui que a função do papel está declarada.
    area: str = "knowledge/"
    max_concurrency: int = SINGLE

    def system_prompt(self) -> str:
        return f"{self.instruction}\n\n{EPISTEMIC_FLOOR}"


PROPONENTE = Role(
    name="proponente",
    summary="produz a alteração",
    instruction=(
        "Você propõe uma alteração para um corpus acadêmico interdisciplinar em "
        "português. Produza a proposta mais enxuta que resolva o que foi pedido: o "
        "texto, as relações que ele cria e os claims que ele sustenta. Declare o "
        "status epistêmico de cada claim. Não proponha o que não puder sustentar."
    ),
    area="runtime/proposals/",
)

VERIFICADOR = Role(
    name="verificador-factual",
    summary="procura erros objetivos",
    instruction=(
        "Você verifica fatos. Procure erros objetivos: número errado, atribuição "
        "errada, data errada, identificador que não corresponde ao trabalho citado. "
        "Aponte cada erro com precisão e não comente estilo. Se não encontrar erro "
        "objetivo, diga isso claramente em vez de inventar uma ressalva."
    ),
    reviews_others=True,
    max_concurrency=REVIEW_CONCURRENCY,
)

CRITICO = Role(
    name="critico-epistemologico",
    summary="avalia força de claims e relações",
    instruction=(
        "Você avalia força epistêmica. Para cada claim, julgue se o status declarado "
        "corresponde ao apoio apresentado, e aponte quando um `established` deveria "
        "ser `supported`, `model-dependent` ou `open`. Superdeclaração de certeza é "
        "o defeito que você existe para pegar."
    ),
    reviews_others=True,
    max_concurrency=REVIEW_CONCURRENCY,
)

REVISOR_ESTRUTURAL = Role(
    name="revisor-estrutural",
    summary="verifica compatibilidade com o Vault",
    instruction=(
        "Você verifica forma. Confira se cada wikilink declara relação do vocabulário "
        "permitido (navigation, prerequisite, extends, contrasts, evidence, "
        "operational, historical), se cada claim tem ID único no formato "
        "CLM-DOMINIO-TOPICO-NNN com status do vocabulário fechado, e se nada é "
        "esboço ou placeholder. Aponte violação por violação."
    ),
    reviews_others=True,
    max_concurrency=REVIEW_CONCURRENCY,
)

REVISOR_INTERDISCIPLINAR = Role(
    name="revisor-interdisciplinar",
    summary="avalia se as conexões são reais",
    instruction=(
        "Você avalia se as conexões entre disciplinas são reais ou apenas verbais. "
        "Uma relação vale quando o conteúdo de uma nota é usado pela outra; não vale "
        "quando as duas apenas compartilham uma palavra ou uma metáfora. Seja "
        "específico sobre qual mecanismo liga os dois lados, ou recuse a conexão."
    ),
    reviews_others=True,
    max_concurrency=REVIEW_CONCURRENCY,
)

SINTETIZADOR = Role(
    name="sintetizador",
    summary="resolve divergências entre avaliações",
    instruction=(
        "Você recebe avaliações independentes sobre uma mesma proposta. Diga onde "
        "elas concordam, onde divergem e qual divergência é substantiva em vez de "
        "verbal. Não vote: descreva o estado do desacordo e o que o resolveria."
    ),
    reviews_others=True,
    area="runtime/quorum/",
)

ARBITRO = Role(
    name="arbitro",
    summary="decide apenas quando o quórum empata",
    instruction=(
        "Você decide um empate entre avaliações. Escolha o lado mais bem sustentado "
        "pela evidência apresentada e diga em uma frase por quê. Se nenhum lado se "
        "sustenta, adie por falta de evidência — adiar é decisão válida."
    ),
    reviews_others=True,
    area="runtime/quorum/",
)

ROLES: dict[str, Role] = {
    role.name: role
    for role in (
        PROPONENTE,
        VERIFICADOR,
        CRITICO,
        REVISOR_ESTRUTURAL,
        REVISOR_INTERDISCIPLINAR,
        SINTETIZADOR,
        ARBITRO,
    )
}

REVIEW_ROLES: tuple[Role, ...] = tuple(role for role in ROLES.values() if role.reviews_others)


def get_role(name: str) -> Role:
    try:
        return ROLES[name]
    except KeyError:
        conhecidos = ", ".join(sorted(ROLES))
        raise KeyError(f"papel desconhecido: {name} (há {conhecidos})") from None
