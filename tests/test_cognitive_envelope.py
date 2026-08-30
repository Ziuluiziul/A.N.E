"""O envelope classifica o que chegou, e nunca o que se supôs que chegaria.

A regra que estes testes existem para prender é uma só: nada aqui pode transformar
ausência de raciocínio em raciocínio. É a diferença entre um Atlas que mostra o que os
endpoints entregam e um que promete um fluxo de pensamento onde não há nenhum.
"""

from __future__ import annotations

import pytest

from providers.cognitive import (
    CognitiveEvent,
    CognitiveKind,
    StreamClass,
    classify_stream,
)


def evento(kind: CognitiveKind, text: str = "", sequence: int = 1) -> CognitiveEvent:
    return CognitiveEvent(
        provider="groq",
        endpoint_id="qwen/qwen3",
        kind=kind,
        text=text,
        raw_field=f"delta.{kind}",
        sequence=sequence,
    )


def test_sem_intervalo_a_classe_e_final_only() -> None:
    # D não é falha: é a descrição correta de um endpoint que só entrega resposta.
    assert classify_stream([evento(CognitiveKind.FINAL)]) is StreamClass.FINAL_ONLY
    assert classify_stream([]) is StreamClass.FINAL_ONLY


def test_delta_de_saida_e_evidencia_de_observavel_e_nao_de_raciocinio() -> None:
    eventos = [evento(CognitiveKind.OUTPUT_DELTA, "39"), evento(CognitiveKind.FINAL)]
    assert classify_stream(eventos) is StreamClass.OBSERVABLE


def test_resumo_de_raciocinio_nao_vira_raciocinio() -> None:
    # A distinção A/B é o ponto: o que o Google entrega é o que ele escolheu contar sobre
    # o próprio raciocínio, não o raciocínio. Promover B a A faria o Atlas prometer um
    # fluxo que o provedor não dá.
    eventos = [
        evento(CognitiveKind.REASONING_SUMMARY, "Somando 17 vinte e três vezes."),
        evento(CognitiveKind.OUTPUT_DELTA, "391"),
    ]
    assert classify_stream(eventos) is StreamClass.REASONING_SUMMARY


def test_a_evidencia_mais_forte_vence() -> None:
    # Um endpoint que emitiu raciocínio **e** deltas é A: a pergunta que a classe responde
    # é "o que dá para mostrar de mais rico".
    eventos = [
        evento(CognitiveKind.OUTPUT_DELTA, "39"),
        evento(CognitiveKind.REASONING, "User asks 17×23."),
        evento(CognitiveKind.TOOL_CALL),
    ]
    assert classify_stream(eventos) is StreamClass.REASONING_TEXT


@pytest.mark.parametrize("vazio", ["", "   ", "\n"])
def test_campo_de_raciocinio_presente_e_vazio_nao_e_evidencia(vazio: str) -> None:
    # O caso que faria o Atlas mentir. Um `reasoning` que existe no esquema e chega vazio
    # em todos os pedaços descreve um endpoint **sem** raciocínio, e classificá-lo como A
    # prometeria um fluxo que nunca vai aparecer no painel.
    eventos = [
        evento(CognitiveKind.REASONING, vazio),
        evento(CognitiveKind.OUTPUT_DELTA, "391"),
    ]
    assert classify_stream(eventos) is StreamClass.OBSERVABLE


def test_ferramenta_vale_por_si_mesma_sem_texto() -> None:
    # `TOOL_CALL` afirma atividade, e atividade não precisa de texto para ser verdadeira —
    # ao contrário de um campo de raciocínio vazio, que não afirma nada.
    assert classify_stream([evento(CognitiveKind.TOOL_CALL)]) is StreamClass.OBSERVABLE
    assert classify_stream([evento(CognitiveKind.PROGRESS)]) is StreamClass.OBSERVABLE


def test_o_evento_guarda_de_que_campo_do_sdk_ele_veio() -> None:
    # Sem `raw_field` não há como auditar depois se a classificação corresponde ao que o
    # provedor mandou, sem reconstituir a versão do SDK daquele dia.
    e = CognitiveEvent(
        provider="ollama",
        endpoint_id="nemotron-3-nano:30b",
        kind=CognitiveKind.REASONING,
        text="User asks",
        raw_field="message.thinking",
    )
    assert e.raw_field == "message.thinking"
    assert str(e.kind) == "reasoning"
