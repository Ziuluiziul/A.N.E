"""O envelope canônico do que um endpoint entrega **durante** uma execução.

Até aqui a fronteira com os provedores era cega ao intervalo: `generate()` faz uma
chamada bloqueante e devolve `GenerationResult` com o texto final. Tudo que acontece
entre o pedido e a resposta — raciocínio, resumo de raciocínio, chamada de ferramenta,
resultado de ferramenta, progresso, pedaço de saída — é descartado no ponto em que chega,
quando chega. A trilha canônica, por consequência, não tem **texto do modelo** para
registrar: ela transporta `metadata.narration`, e essa frase é composta pelo orquestrador
em f-strings sobre o próprio processo — "Consultando groq/qwen3.6-27b como
revisor-estrutural". Medido em 2026-08-11, 88 de 1265 eventos a carregam, e nenhum traz o
raciocínio de um provedor: `strip_reasoning` o **remove** antes de gravar.

(Uma versão anterior deste texto dizia que nenhum evento carregava narração. Era falso —
a contagem olhava a chave no topo do evento, e ela mora em `metadata`. O que continua
verdadeiro, e é o que importa aqui, é a outra metade: nada do que o provedor emite no
intervalo chega à trilha.)

Este módulo é o envelope, e nada além dele. Ele não sintetiza cadeia de pensamento, não
resume, não infere: cada valor aqui corresponde a um campo que um endpoint de fato emitiu.
Onde o provedor não entrega raciocínio, não há `REASONING` — há a ausência dele, que é uma
informação verdadeira sobre aquele endpoint e precisa poder ser registrada como tal.

**A classificação é por endpoint, nunca por modelo.** O mesmo modelo servido por dois
provedores expõe streams diferentes, e é a isso que a arquitetura do Vault já responde ao
separar fabricante de servidor de inferência: `(provider, endpoint_id)` é a chave.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class CognitiveKind(StrEnum):
    """O que um pedaço de stream é. Fechado de propósito.

    Vocabulário pequeno porque precisa valer para todos os provedores. Cada entrada
    corresponde a algo que um endpoint emite; nenhuma corresponde a algo que se possa
    deduzir.
    """

    #: Texto de raciocínio, como o provedor o emite. Groq o chama `reasoning`; a Ollama,
    #: `thinking`. É o próprio fluxo, não um resumo dele.
    REASONING = "reasoning"
    #: Resumo de raciocínio, quando o provedor entrega resumo em vez do fluxo. É o caso
    #: do Google, cujas partes vêm marcadas com `thought=True`.
    REASONING_SUMMARY = "reasoning-summary"
    #: O modelo pediu uma ferramenta.
    TOOL_CALL = "tool-call"
    #: A ferramenta respondeu.
    TOOL_RESULT = "tool-result"
    #: Sinal de andamento sem texto — o que existe quando só há atividade a mostrar.
    PROGRESS = "progress"
    #: Pedaço da resposta final, à medida que ela é escrita.
    OUTPUT_DELTA = "output-delta"
    #: A resposta terminada.
    FINAL = "final"


@dataclass(frozen=True, slots=True)
class CognitiveEvent:
    """Um pedaço de stream, já classificado e ainda atribuído ao endpoint que o emitiu.

    `raw_field` é o nome do campo de origem no SDK ou na API — `delta.reasoning`,
    `message.thinking`, `part.thought`. Ele não é decorativo: é o que permite auditar
    depois se uma classificação corresponde ao que o provedor de fato mandou, sem ter de
    reconstituir a versão do SDK daquele dia.
    """

    provider: str
    endpoint_id: str
    kind: CognitiveKind
    #: Texto do pedaço, quando ele tem texto. `PROGRESS` costuma não ter.
    text: str = ""
    #: O campo de origem, como o SDK o nomeia.
    raw_field: str = ""
    #: Ordem de chegada dentro da execução. Cresce monotonicamente.
    sequence: int = 0
    observed_at: str = field(default_factory=now)
    #: Escalares extras que o pedaço trouxe — nome da ferramenta, índice, motivo de fim.
    #:
    #: Em `FINAL`, a chave `usage` carrega o consumo que o provedor reportou, no mesmo
    #: formato que `generate` devolve. Ela existe porque quem consome o stream em vez da
    #: chamada única não pode ficar sem o número medido: o ledger de cota lê `total_tokens`
    #: e, sem ele, passa a estimar. Trocar medida por estimativa caladamente é o que o
    #: orçamento não pode herdar — e orçamento é um dos casos que exigem confirmação.
    #:
    #: Onde o provedor não reporta consumo no intervalo, a chave não existe. A ausência é
    #: dele, e descrevê-la como ausência é mais honesto que preenchê-la com estimativa.
    detail: dict[str, Any] = field(default_factory=dict)


class StreamClass(StrEnum):
    """O que um endpoint entrega, medido numa execução real.

    A classe é conclusão de observação, e não promessa de catálogo: um endpoint que
    declara raciocínio e não o emite sob o orçamento pedido é `OBSERVABLE`, porque foi
    isso que ele fez. É a mesma disciplina que separa `ok` de `reachable` na sonda.
    """

    #: A — raciocínio textual explícito, emitido como fluxo.
    REASONING_TEXT = "reasoning-text"
    #: B — resumo de raciocínio, e não o fluxo.
    REASONING_SUMMARY = "reasoning-summary"
    #: C — nada de raciocínio, mas eventos observáveis: ferramenta, progresso, deltas.
    OBSERVABLE = "observable"
    #: D — só a resposta final, sem nada no intervalo.
    FINAL_ONLY = "final-only"


#: De que classe cada tipo de evento é evidência. Ausente daqui: `FINAL`, que todo
#: endpoint emite e portanto não distingue nenhum.
_EVIDENCIA: dict[CognitiveKind, StreamClass] = {
    CognitiveKind.REASONING: StreamClass.REASONING_TEXT,
    CognitiveKind.REASONING_SUMMARY: StreamClass.REASONING_SUMMARY,
    CognitiveKind.TOOL_CALL: StreamClass.OBSERVABLE,
    CognitiveKind.TOOL_RESULT: StreamClass.OBSERVABLE,
    CognitiveKind.PROGRESS: StreamClass.OBSERVABLE,
    CognitiveKind.OUTPUT_DELTA: StreamClass.OBSERVABLE,
}

#: Ordem de força da evidência. A vence B, que vence C, que vence D.
_FORCA: dict[StreamClass, int] = {
    StreamClass.REASONING_TEXT: 3,
    StreamClass.REASONING_SUMMARY: 2,
    StreamClass.OBSERVABLE: 1,
    StreamClass.FINAL_ONLY: 0,
}


def classify_stream(events: list[CognitiveEvent]) -> StreamClass:
    """A classe de um endpoint, a partir do que uma execução dele produziu.

    A evidência mais forte vence: um endpoint que emitiu raciocínio **e** deltas é classe
    A, porque a pergunta que a classe responde é "o que dá para mostrar de mais rico".
    Sem nenhuma evidência além do final, é D — e D não é falha: é a descrição correta de
    um endpoint que só entrega resposta.

    Texto vazio não conta como evidência. Um campo `reasoning` presente e vazio em todos
    os pedaços é exatamente o caso que faria o Atlas prometer um fluxo que não existe.
    """
    melhor = StreamClass.FINAL_ONLY
    for event in events:
        classe = _EVIDENCIA.get(event.kind)
        if classe is None:
            continue
        # Evento de texto sem texto não é evidência de nada; `PROGRESS` e `TOOL_CALL`
        # valem por si, porque a atividade é o que eles afirmam.
        se_texto = event.kind in {
            CognitiveKind.REASONING,
            CognitiveKind.REASONING_SUMMARY,
            CognitiveKind.OUTPUT_DELTA,
        }
        if se_texto and not event.text.strip():
            continue
        if _FORCA[classe] > _FORCA[melhor]:
            melhor = classe
    return melhor
