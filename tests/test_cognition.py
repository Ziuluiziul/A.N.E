"""O canal cognitivo é efêmero e não é a trilha. O que ele grava, e o que ele recusa.

A trilha operacional existe para o corpus e o quórum, e por isso `strip_reasoning`
remove texto de modelo antes de gravar. Este canal é o oposto: ele existe **para**
carregar raciocínio. A fronteira que precisa ser testada, então, é a outra — que ele não
carregue a resposta deliberada, não persista fora de `runtime/`, e não derrube a chamada
quando o disco falhar.
"""

from __future__ import annotations

import asyncio
import json
import multiprocessing
import stat
from collections.abc import AsyncGenerator
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol, cast

import pytest
from fastapi import Request

from providers.cognitive import CognitiveEvent, CognitiveKind
from vault.app import runtime_cognition
from vault.cognition import (
    CognitionBus,
    CognitionRecorder,
    CognitionStore,
    CognitionStoreError,
)
from vault.cognition.models import frame_id, revision_from_frame_id
from vault.cognition.store import _MAX_FRAMES, _MAX_TEXT


def evento(
    kind: CognitiveKind = CognitiveKind.REASONING,
    *,
    provider: str = "groq",
    endpoint: str = "qwen/qwen3.6-27b",
    text: str = "pensando",
) -> CognitiveEvent:
    return CognitiveEvent(
        provider=provider,
        endpoint_id=endpoint,
        kind=kind,
        text=text,
        raw_field="delta.reasoning",
        sequence=1,
    )


class BarrierLike(Protocol):
    def wait(self, timeout: float | None = None) -> int: ...


def _append_in_process(directory: str, barrier: object) -> None:
    cast(BarrierLike, barrier).wait()
    CognitionStore(Path(directory)).append(
        kind="reasoning",
        provider="groq",
        endpoint="qwen/qwen3.6-27b",
        text="concorrente",
    )


def test_store_grava_privado_redigido_e_monotonico(tmp_path: Path) -> None:
    segredo = "chave-que-nao-pode-persistir"
    directory = tmp_path / "runtime" / "cognition"
    store = CognitionStore(
        directory,
        redact=lambda text: text.replace(segredo, "[REDACTED]"),
    )

    primeiro = store.append(
        kind="reasoning",
        provider="groq",
        endpoint=f"qwen/qwen3.6-27b?key={segredo}",
        text=f"vou usar {segredo} para isto",
        task="tarefa-1",
    )
    segundo = store.append(kind="reasoning-summary", provider="google", endpoint="gemini")
    terceiro = CognitionStore(directory).append(
        kind="final", provider="groq", endpoint="qwen/qwen3.6-27b"
    )

    assert [primeiro.revision, segundo.revision, terceiro.revision] == [1, 2, 3]
    assert [primeiro.id, segundo.id, terceiro.id] == [frame_id(1), frame_id(2), frame_id(3)]
    assert segredo not in primeiro.endpoint
    assert segredo not in primeiro.text
    # Raciocínio **não** é removido: é justamente o que este canal transporta. O que sai é
    # segredo, e é a redação da configuração que decide isso — não uma lista de campos.
    assert primeiro.text == "vou usar [REDACTED] para isto"
    assert [frame.revision for frame in store.load(after_revision=1)] == [2, 3]

    serializado = store.log_path.read_text(encoding="utf-8")
    assert segredo not in serializado
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(store.log_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(store.lock_path.stat().st_mode) == 0o600


def test_texto_longo_guarda_o_fim_porque_o_agora_e_o_que_a_cena_mostra(
    tmp_path: Path,
) -> None:
    store = CognitionStore(tmp_path / "cognition")

    frame = store.append(
        kind="reasoning",
        provider="groq",
        endpoint="qwen/qwen3.6-27b",
        text="começo   " + "x" * (_MAX_TEXT * 2) + " fim",
    )

    assert len(frame.text) == _MAX_TEXT
    assert frame.text.endswith(" fim")
    assert "começo" not in frame.text


def test_rotacao_descarta_quadro_antigo_sem_reiniciar_a_revisao(tmp_path: Path) -> None:
    """O log é uma janela, não um histórico: o que sai é o antigo, nunca o contador."""
    store = CognitionStore(tmp_path / "cognition")
    excedente = 3
    for indice in range(_MAX_FRAMES + excedente):
        store.append(
            kind="reasoning",
            provider="groq",
            endpoint="qwen/qwen3.6-27b",
            text=f"passo {indice}",
        )

    frames = store.load()
    assert len(frames) == _MAX_FRAMES
    assert frames[0].revision == excedente + 1
    assert frames[-1].revision == _MAX_FRAMES + excedente
    assert store.latest_revision() == _MAX_FRAMES + excedente


def test_tipo_fora_do_vocabulario_e_recusado(tmp_path: Path) -> None:
    store = CognitionStore(tmp_path / "cognition")

    with pytest.raises(CognitionStoreError, match="tipo cognitivo desconhecido"):
        store.append(kind="palpite", provider="groq", endpoint="qwen/qwen3.6-27b")


def test_cauda_adulterada_nao_reinicia_a_revisao(tmp_path: Path) -> None:
    store = CognitionStore(tmp_path / "cognition")
    store.append(kind="reasoning", provider="groq", endpoint="qwen")
    store.append(kind="reasoning", provider="groq", endpoint="qwen")
    with store.log_path.open("ab") as stream:
        stream.write(b'{"id":"cognition-99999999999999999999","revision":')

    terceiro = store.append(kind="final", provider="groq", endpoint="qwen")

    assert terceiro.revision == 3
    assert [frame.revision for frame in store.load()] == [1, 2, 3]


def test_processos_concorrentes_recebem_revisoes_unicas(tmp_path: Path) -> None:
    """Um worker por tarefa escreve no mesmo log: revisão repetida perderia quadro."""
    workers = 6
    directory = tmp_path / "cognition"
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(workers)
    processes = [
        context.Process(target=_append_in_process, args=(str(directory), barrier))
        for _ in range(workers)
    ]
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=10)
        assert all(process.exitcode == 0 for process in processes)
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)

    frames = CognitionStore(directory).load()
    assert [frame.revision for frame in frames] == list(range(1, workers + 1))
    assert [frame.timestamp for frame in frames] == sorted(frame.timestamp for frame in frames)


def test_identificador_de_retomada_so_aceita_a_forma_canonica() -> None:
    assert revision_from_frame_id(frame_id(7)) == 7
    assert revision_from_frame_id(" cognition-00000000000000000007 ") == 7
    assert revision_from_frame_id("runtime-00000000000000000007") is None
    assert revision_from_frame_id("cognition-7") is None
    assert revision_from_frame_id(None) is None


def test_recorder_nao_derruba_a_chamada_quando_o_log_falha(tmp_path: Path) -> None:
    """Perder o painel vivo é aceitável; perder a chamada do quórum, não."""
    ocupado = tmp_path / "cognition"
    ocupado.write_text("isto é um arquivo, não um diretório", encoding="utf-8")
    avisos: list[str] = []
    recorder = CognitionRecorder(CognitionStore(ocupado), warn=avisos.append)

    recorder(evento(), accumulated="pensando")

    assert avisos and "cognition log indisponível" in avisos[0]


def test_recorder_estrangula_o_fluxo_sem_perder_o_fim(tmp_path: Path) -> None:
    store = CognitionStore(tmp_path / "cognition")
    recorder = CognitionRecorder(store)

    recorder(evento(), accumulated="primeiro pedaço")
    recorder(evento(), accumulated="primeiro pedaço mais um pouco")
    recorder(evento(CognitiveKind.FINAL), accumulated="primeiro pedaço mais um pouco")

    frames = store.load()
    # O segundo quadro cresceu pouco e chegou cedo demais: gravá-lo faria o disco medir a
    # cadência do provedor em vez do raciocínio. O `final` passa sempre — ele fecha.
    assert [frame.kind for frame in frames] == ["reasoning", "final"]


def test_canal_cognitivo_nao_transporta_a_resposta_deliberada(tmp_path: Path) -> None:
    """`output-delta` é a resposta sendo escrita, e ela pertence ao quórum, não à cena.

    Deixá-la entrar aqui abriria um segundo caminho para texto de modelo — um que não
    passa por `strip_reasoning` nem pelo Proposal Promoter.
    """
    store = CognitionStore(tmp_path / "cognition")
    recorder = CognitionRecorder(store)

    recorder(evento(CognitiveKind.OUTPUT_DELTA, text="a resposta"), accumulated="")
    recorder(evento(CognitiveKind.TOOL_CALL, text=""), accumulated="")

    assert store.load() == []


async def test_bus_nao_cria_diretorio_e_enxerga_produtor_externo(tmp_path: Path) -> None:
    """O worker escreve de outro processo; a API só lê. O canal precisa ver isso."""
    directory = tmp_path / "runtime" / "cognition"
    bus = CognitionBus(CognitionStore(directory))
    await bus.start()
    try:
        assert not directory.exists()
        esperando = asyncio.create_task(bus.wait_after(0, timeout=2))
        externo = CognitionStore(directory)
        escrito = await asyncio.to_thread(
            externo.append,
            kind="reasoning",
            provider="groq",
            endpoint="qwen/qwen3.6-27b",
            text="do outro processo",
        )
        recebido = await asyncio.wait_for(esperando, timeout=2)

        assert recebido == [escrito]
    finally:
        await bus.stop()


async def test_snapshot_devolve_so_a_janela_e_nao_avanca_alem_dela(tmp_path: Path) -> None:
    store = CognitionStore(tmp_path / "cognition")
    for indice in range(3):
        store.append(
            kind="reasoning",
            provider="groq",
            endpoint="qwen/qwen3.6-27b",
            text=f"passo {indice}",
        )
    bus = CognitionBus(store)

    snapshot = await bus.snapshot()

    assert snapshot.revision == 3
    assert snapshot.latest_id == frame_id(3)
    assert [frame["revision"] for frame in cast(list, snapshot.to_dict()["frames"])] == [
        1,
        2,
        3,
    ]
    assert await bus.wait_after(3, timeout=0.05) == []


def _request(bus: CognitionBus, *, last_event_id: str | None = None) -> Request:
    headers = []
    if last_event_id is not None:
        headers.append((b"last-event-id", last_event_id.encode("ascii")))
    application = SimpleNamespace(state=SimpleNamespace(cognition_bus=bus))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/runtime/cognition",
        "raw_path": b"/runtime/cognition",
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 1234),
        "server": ("127.0.0.1", 8000),
        "app": application,
    }

    async def receive() -> dict[str, str]:
        await asyncio.sleep(60)
        return {"type": "http.disconnect"}

    return Request(scope, receive)


def _frame_text(chunk: str | bytes) -> str:
    return chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk


def _frame_data(frame: str) -> dict[str, object]:
    raw = next(
        line.removeprefix("data: ") for line in frame.splitlines() if line.startswith("data: ")
    )
    return cast(dict[str, object], json.loads(raw))


async def _next_named_frame(
    stream: AsyncGenerator[str | bytes], *, timeout: float = 1
) -> str:
    while True:
        frame = _frame_text(await asyncio.wait_for(anext(stream), timeout=timeout))
        if not frame.startswith(":"):
            return frame


async def test_sse_entrega_snapshot_e_retoma_por_last_event_id(tmp_path: Path) -> None:
    store = CognitionStore(tmp_path / "cognition")
    bus = CognitionBus(store)
    await bus.start()
    try:
        primeiro = store.append(kind="reasoning", provider="groq", endpoint="qwen", text="um")
        segundo = store.append(kind="reasoning", provider="groq", endpoint="qwen", text="dois")

        resposta = await runtime_cognition(_request(bus))
        fluxo = cast(AsyncGenerator[str | bytes], resposta.body_iterator)
        quadro = await _next_named_frame(fluxo)

        assert "event: cognition_snapshot" in quadro
        assert f"id: {segundo.id}" in quadro
        assert _frame_data(quadro)["revision"] == 2
        assert resposta.media_type == "text/event-stream"

        vivo = asyncio.create_task(anext(fluxo))
        terceiro = await asyncio.to_thread(
            store.append, kind="reasoning", provider="groq", endpoint="qwen", text="três"
        )
        quadro_vivo = _frame_text(await asyncio.wait_for(vivo, timeout=2))
        assert "event: reasoning" in quadro_vivo
        assert f"id: {terceiro.id}" in quadro_vivo
        await fluxo.aclose()

        retomada = await runtime_cognition(_request(bus, last_event_id=primeiro.id))
        replay = cast(AsyncGenerator[str | bytes], retomada.body_iterator)
        quadro_replay = await _next_named_frame(replay)
        await replay.aclose()

        assert "cognition_snapshot" not in quadro_replay
        assert f"id: {segundo.id}" in quadro_replay
        assert _frame_data(quadro_replay)["revision"] == 2
    finally:
        await bus.stop()


async def test_sse_emite_heartbeat_sem_criar_revisao(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = CognitionStore(tmp_path / "cognition")
    bus = CognitionBus(store)
    await bus.start()
    try:
        store.append(kind="reasoning", provider="groq", endpoint="qwen", text="um")
        monkeypatch.setattr("vault.app.RUNTIME_HEARTBEAT_SECONDS", 0.01)

        resposta = await runtime_cognition(_request(bus))
        fluxo = cast(AsyncGenerator[str | bytes], resposta.body_iterator)
        await _next_named_frame(fluxo)
        batida = await _next_named_frame(fluxo)
        await fluxo.aclose()

        assert "event: cognition_heartbeat" in batida
        assert _frame_data(batida) == {"revision": 1}
        assert store.latest_revision() == 1
    finally:
        await bus.stop()


async def test_canal_ausente_recusa_em_vez_de_fingir_fluxo() -> None:
    aplicacao = SimpleNamespace(state=SimpleNamespace())
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/runtime/cognition",
        "raw_path": b"/runtime/cognition",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 1234),
        "server": ("127.0.0.1", 8000),
        "app": aplicacao,
    }

    async def receive() -> dict[str, str]:
        return {"type": "http.disconnect"}

    with pytest.raises(Exception, match="canal cognitivo ainda não iniciado"):
        await runtime_cognition(Request(scope, receive))
