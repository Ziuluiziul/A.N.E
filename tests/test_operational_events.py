"""Event bus operacional: ordem durável e SSE sem revisão falsa de corpus."""

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

from vault.app import runtime_events
from vault.corpus.watcher import CorpusProjectionWatcher
from vault.events import (
    OperationalEvent,
    OperationalEventBus,
    OperationalEventDraft,
    OperationalEventRecorder,
    OperationalEventStore,
    event_id,
)
from vault.layout_store import LayoutStore
from vault.operational import runtime_snapshot


def draft(
    event_type: str = "task_created",
    *,
    actor: str = "orquestrador",
    task: str = "task-001",
) -> OperationalEventDraft:
    return OperationalEventDraft.model_validate(
        {
            "type": event_type,
            "actor": actor,
            "provider": "groq",
            "endpoint": "qwen/qwen3",
            "task": task,
            "entity": "claim-001",
            "before": {"status": "pending"},
            "after": {"status": "running"},
            "metadata": {"attempt": 1},
        }
    )


class BarrierLike(Protocol):
    def wait(self) -> object: ...


def _append_in_process(directory: str, barrier: object) -> None:
    # `Barrier` é compartilhada pelo contexto multiprocessing; a anotação concreta
    # varia entre plataformas e não faz parte do contrato que este teste exerce.
    cast(BarrierLike, barrier).wait()
    OperationalEventStore(Path(directory)).append(draft())


def test_store_persiste_privado_sanitizado_e_monotonico(tmp_path: Path) -> None:
    secret = "segredo-que-nao-pode-persistir"
    directory = tmp_path / "runtime" / "events"
    store = OperationalEventStore(
        directory,
        redact=lambda text: text.replace(secret, "[REDACTED]"),
    )

    first = store.append(
        draft(
            actor=f"agente {secret}",
        ).model_copy(
            update={
                "metadata": {
                    "safe": "antes <think>raciocínio interno</think> depois",
                    "raw_response": f"<think>{secret}</think>",
                }
            }
        )
    )
    second = store.append(draft("task_assigned"))
    third = OperationalEventStore(directory).append(draft("call_started"))

    assert [first.revision, second.revision, third.revision] == [1, 2, 3]
    assert [first.id, second.id, third.id] == [event_id(1), event_id(2), event_id(3)]
    assert first.metadata == {"safe": "antes depois"}
    assert first.actor == "agente [REDACTED]"
    assert [event.revision for event in store.load(after_revision=1)] == [2, 3]

    required = {
        "id",
        "revision",
        "timestamp",
        "type",
        "actor",
        "provider",
        "endpoint",
        "task",
        "entity",
        "before",
        "after",
        "metadata",
    }
    assert set(first.to_dict()) == required
    serialized = store.log_path.read_text(encoding="utf-8")
    assert secret not in serialized
    assert "raciocínio interno" not in serialized
    assert "raw_response" not in serialized
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(store.log_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(store.lock_path.stat().st_mode) == 0o600


def test_sanitizador_bloqueia_variantes_camelcase_de_raciocinio(tmp_path: Path) -> None:
    store = OperationalEventStore(tmp_path / "events")
    event = store.append(
        draft().model_copy(
            update={
                "metadata": {
                    "rawResponse": "segredo",
                    "finalResponse": "texto",
                    "chainOfThought": "raciocínio",
                    "promptTokens": 123,
                    "safe": "visível",
                }
            }
        )
    )

    assert event.metadata == {"safe": "visível"}


def test_recorder_degrada_so_falha_de_persistencia(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "events"
    linked.symlink_to(real, target_is_directory=True)
    warnings: list[str] = []
    recorder = OperationalEventRecorder(
        OperationalEventStore(linked),
        warn=warnings.append,
    )
    payload = draft().model_dump(exclude={"type"})

    recorder("task_created", payload)

    assert recorder.failure_count == 1
    assert warnings and "event log indisponível" in warnings[0]


def test_processos_concorrentes_recebem_revisoes_unicas(tmp_path: Path) -> None:
    workers = 6
    directory = tmp_path / "events"
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

    events = OperationalEventStore(directory).load()
    assert [event.revision for event in events] == list(range(1, workers + 1))
    assert [event.id for event in events] == [
        event_id(index) for index in range(1, workers + 1)
    ]
    assert [event.timestamp for event in events] == sorted(event.timestamp for event in events)


def test_cauda_parcial_nao_engole_o_proximo_evento(tmp_path: Path) -> None:
    directory = tmp_path / "events"
    directory.mkdir()
    log = directory / "events.jsonl"
    log.write_text('{"revision":', encoding="utf-8")

    store = OperationalEventStore(directory)
    event = store.append(draft())

    assert event.revision == 1
    assert store.load() == [event]
    assert log.read_bytes().startswith(b'{"revision":\n')


def test_cauda_adulterada_nao_reinicia_a_revisao(tmp_path: Path) -> None:
    store = OperationalEventStore(tmp_path / "events")
    store.append(draft())
    store.append(draft("task_assigned"))
    with store.log_path.open("ab") as stream:
        stream.write(b'{"id":"runtime-99999999999999999999","revision":')

    third = store.append(draft("call_started"))

    assert third.revision == 3
    assert [event.revision for event in store.load()] == [1, 2, 3]


async def test_bus_nao_cria_placeholder_e_enxerga_produtor_externo(tmp_path: Path) -> None:
    directory = tmp_path / "runtime" / "events"
    store = OperationalEventStore(directory)
    bus = OperationalEventBus(store)
    await bus.start()
    try:
        assert not directory.exists()
        waiting = asyncio.create_task(bus.wait_after(0, timeout=2))
        external = OperationalEventStore(directory)
        written = await asyncio.to_thread(external.append, draft())
        received = await asyncio.wait_for(waiting, timeout=2)

        assert received == [written]
        assert bus.revision == 1
        own = await bus.publish(draft("task_assigned"))
        assert own.revision == 2
    finally:
        await bus.stop()

    restarted = OperationalEventBus(OperationalEventStore(directory))
    await restarted.start()
    try:
        assert restarted.revision == 2
        assert (await restarted.snapshot()).runtime_revision == 2
    finally:
        await restarted.stop()


async def test_snapshot_nao_avanca_cursor_alem_dos_eventos_carregados(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = OperationalEventStore(tmp_path / "events")
    first = store.append(draft())
    second = store.append(draft("task_assigned"))
    bus = OperationalEventBus(store)
    load = store.load

    # Simula o produtor que anexou a revisão 2 logo depois do load do snapshot. A
    # leitura seguinte do fluxo deve partir da revisão 1 e ainda enxergar a 2.
    def load_durante_corrida(
        *, after_revision: int = 0, limit: int | None = None
    ) -> list[OperationalEvent]:
        if after_revision == 0:
            return [first]
        return load(after_revision=after_revision, limit=limit)

    monkeypatch.setattr(store, "load", load_durante_corrida)

    snapshot = await bus.snapshot()
    replay = await bus.wait_after(snapshot.runtime_revision, timeout=0.1)

    assert snapshot.runtime_revision == first.revision
    assert snapshot.latest_id == first.id
    assert snapshot.to_dict() == {
        "runtimeRevision": first.revision,
        "events": [first.to_dict()],
    }
    assert replay == [second]


def test_snapshot_operacional_encadeia_apenas_tarefa_ou_entidade_iguais(
    tmp_path: Path,
) -> None:
    store = OperationalEventStore(tmp_path / "events")
    events = [
        store.append(draft("task_created")),
        store.append(draft("call_started")),
        store.append(draft("call_completed")),
    ]

    snapshot = runtime_snapshot(events)

    assert snapshot["runtimeRevision"] == 3
    assert [event["revision"] for event in snapshot["events"]] == [1, 2, 3]
    layer = snapshot["operational"]
    event_nodes = [node for node in layer["nodes"] if node["id"].startswith("op/event/")]
    actor_nodes = [node for node in layer["nodes"] if node["id"].startswith("op/actor/")]
    assert len(event_nodes) == 3
    assert len(actor_nodes) == 1
    assert all(node["path"] is None for node in layer["nodes"])
    assert all(node["layer"] == "operational" for node in layer["nodes"])
    # Três arestas do ator e duas da sequência compartilhada.
    assert len(layer["edges"]) == 5


def _request(bus: OperationalEventBus, *, last_event_id: str | None = None) -> Request:
    headers = []
    if last_event_id is not None:
        headers.append((b"last-event-id", last_event_id.encode("ascii")))
    application = SimpleNamespace(
        state=SimpleNamespace(operational_event_bus=bus),
    )
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/runtime/events",
        "raw_path": b"/runtime/events",
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
        line.removeprefix("data: ")
        for line in frame.splitlines()
        if line.startswith("data: ")
    )
    return cast(dict[str, object], json.loads(raw))


async def test_sse_entrega_snapshot_e_replay_por_last_event_id(tmp_path: Path) -> None:
    bus = OperationalEventBus(OperationalEventStore(tmp_path / "events"))
    await bus.start()
    try:
        first = await bus.publish(draft())
        second = await bus.publish(draft("task_assigned"))

        fresh_response = await runtime_events(_request(bus))
        fresh = cast(AsyncGenerator[str | bytes], fresh_response.body_iterator)
        snapshot_frame = _frame_text(await asyncio.wait_for(anext(fresh), timeout=1))

        assert "event: runtime_snapshot" in snapshot_frame
        assert f"id: {second.id}" in snapshot_frame
        snapshot_payload = _frame_data(snapshot_frame)
        assert snapshot_payload["runtimeRevision"] == 2
        assert len(cast(list[object], snapshot_payload["events"])) == 2
        assert "operational" not in snapshot_payload
        assert fresh_response.media_type == "text/event-stream"
        assert fresh_response.headers["cache-control"] == "no-cache"

        live_wait = asyncio.create_task(anext(fresh))
        third = await bus.publish(draft("call_started"))
        live_frame = _frame_text(await asyncio.wait_for(live_wait, timeout=1))
        assert "event: call_started" in live_frame
        assert f"id: {third.id}" in live_frame
        assert _frame_data(live_frame)["revision"] == 3
        await fresh.aclose()

        replay_response = await runtime_events(_request(bus, last_event_id=first.id))
        replay = cast(AsyncGenerator[str | bytes], replay_response.body_iterator)
        replay_frame = _frame_text(await asyncio.wait_for(anext(replay), timeout=1))
        await replay.aclose()

        assert "event: task_assigned" in replay_frame
        assert f"id: {second.id}" in replay_frame
        assert _frame_data(replay_frame)["revision"] == 2
        assert "runtime_snapshot" not in replay_frame
    finally:
        await bus.stop()


async def test_sse_emite_heartbeat_nomeado_sem_criar_revisao(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus = OperationalEventBus(OperationalEventStore(tmp_path / "events"))
    await bus.start()
    try:
        latest = await bus.publish(draft())
        monkeypatch.setattr("vault.app.RUNTIME_HEARTBEAT_SECONDS", 0.01)

        response = await runtime_events(_request(bus))
        stream = cast(AsyncGenerator[str | bytes], response.body_iterator)
        snapshot_frame = _frame_text(await asyncio.wait_for(anext(stream), timeout=1))
        heartbeat_frame = _frame_text(await asyncio.wait_for(anext(stream), timeout=1))
        await stream.aclose()

        assert "event: runtime_snapshot" in snapshot_frame
        assert "event: runtime_heartbeat" in heartbeat_frame
        assert "id:" not in heartbeat_frame
        assert _frame_data(heartbeat_frame) == {"runtimeRevision": latest.revision}
        assert bus.revision == latest.revision
    finally:
        await bus.stop()


async def test_runtime_revision_nao_move_corpus_revision(tmp_path: Path) -> None:
    corpus = tmp_path / "knowledge"
    corpus.mkdir()
    (corpus / "Nota.md").write_text(
        "---\ntitle: Nota\nkind: nota\nepistemic_status: supported\n---\n\nCorpo.\n",
        encoding="utf-8",
    )
    watcher = CorpusProjectionWatcher(corpus, LayoutStore(tmp_path / "layout"))
    assert await watcher.refresh()
    corpus_revision = watcher.revision
    corpus_fingerprint = watcher.fingerprint

    bus = OperationalEventBus(OperationalEventStore(tmp_path / "events"))
    await bus.start()
    try:
        await bus.publish(draft())
        await bus.publish(draft("task_assigned"))
        assert bus.revision == 2
        assert watcher.revision == corpus_revision
        assert watcher.fingerprint == corpus_fingerprint
    finally:
        await bus.stop()
