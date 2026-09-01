"""API do backend: leitura do corpus, e o painel de controle operacional.

O que esta API continua não fazendo, de propósito: não escreve no corpus e não promove
proposta. O que ela passou a fazer, com a direção de 3.4-D, é servir o estado
operacional e aceitar as mutações que o painel oferece — provedor, trabalhador e AUTO.
A única chamada externa que ela faz é o teste de credencial, que autentica sem gerar.

As rotas de controle vivem em `vault.control`, com leitura, mutação e credencial
separadas. A separação importa: só a última toca o arquivo de segredos, e só ela tem a
regra de nunca registrar o corpo do pedido nem devolver o valor gravado.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

import orjson
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from vault import __version__
from vault.cognition import CognitionBus, CognitionStore
from vault.cognition.models import revision_from_frame_id
from vault.config import get_settings
from vault.control import router as control_router
from vault.corpus import CorpusReader
from vault.corpus.identity import CorpusIdentityError
from vault.corpus.watcher import CorpusProjectionWatcher, ProjectionUnavailable
from vault.events import (
    OperationalEventBus,
    OperationalEventStore,
    revision_from_event_id,
)
from vault.layout_store import (
    OPERATIONAL_SLOTS_SCHEMA_VERSION,
    SCHEMA_VERSION,
    LayoutStore,
    LayoutStoreError,
    OperationalSlotStore,
    positions_from_payload,
    slots_from_payload,
    validate_algorithm_version,
)
from vault.projection import ProjectionError, build_projection, with_runtime_quorum
from vault.proposals import ProposalStore

RUNTIME_HEARTBEAT_SECONDS = 15.0
OPERATIONAL_LAYOUT_VERSION = 6


def _versao_do_algoritmo(valor: str) -> str:
    """O vocabulário é o que o store declara, e só ele.

    Estava fixo em `Literal["1"]` aqui e em `Query` abaixo — uma segunda lista, mais
    estreita que a do store, que precisava ser atualizada em duas casas a cada mudança de
    geometria no frontend. Não foi: a versão subiu para 2 e a memória espacial do corpus
    morreu em silêncio, com 422 em toda leitura e toda gravação.
    """
    try:
        return validate_algorithm_version(valor)
    except LayoutStoreError as error:
        raise ValueError(str(error)) from error


AlgorithmVersion = Annotated[str, AfterValidator(_versao_do_algoritmo)]


class LayoutWriteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    algorithm_version: AlgorithmVersion = Field(alias="algorithmVersion")
    positions: dict[str, Any]


class OperationalSlotsWriteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slots: dict[str, Any]


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Uma projeção de corpus e um fluxo operacional, encerrados junto com a API."""
    settings = get_settings()
    watcher = CorpusProjectionWatcher(
        settings.corpus_dir,
        LayoutStore(settings.state_dir / "layout"),
        demo_operational=settings.demo_operational,
    )
    event_bus = OperationalEventBus(
        OperationalEventStore(settings.runtime_dir / "events", redact=settings.redact)
    )
    cognition_bus = CognitionBus(
        CognitionStore(settings.cognition_dir, redact=settings.redact)
    )
    application.state.corpus_watcher = watcher
    application.state.operational_event_bus = event_bus
    application.state.cognition_bus = cognition_bus
    await watcher.start()
    try:
        await event_bus.start()
        await cognition_bus.start()
        try:
            yield
        finally:
            await cognition_bus.stop()
            await event_bus.stop()
    finally:
        await watcher.stop()


app = FastAPI(title="A.N.E.", version=__version__, lifespan=lifespan)

# A cena 3D roda no servidor de desenvolvimento do Vite, em outra porta.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    # O painel de controle acrescenta mutação e credencial ao que era só leitura.
    allow_methods=["GET", "PUT", "PATCH", "POST", "DELETE"],
    allow_headers=["*"],
)

app.include_router(control_router)


@app.exception_handler(RequestValidationError)
async def validation_without_echo(_: Request, error: RequestValidationError) -> JSONResponse:
    """422 que diz o que está errado sem repetir o que foi enviado.

    O handler padrão do FastAPI devolve `input` — o valor recebido — dentro do detalhe.
    Para todo campo do resto da API isso é conveniente; para `CredentialBody.key` é um
    vazamento: uma chave acima de `max_length` era recusada pelo Pydantic **antes** de a
    rota rodar, e voltava integral no corpo do 422. A promessa de nunca devolver o valor
    vivia uma camada abaixo de onde o segredo entrava, e por isso não valia.

    O que sobra — `type`, `loc` e `msg` — identifica o campo e diz a regra violada, que é
    tudo que um cliente precisa para corrigir o pedido. `ctx` cai junto porque alguns
    validadores embutem o valor recebido nele.
    """
    limpos = [
        {chave: valor for chave, valor in item.items() if chave in {"type", "loc", "msg"}}
        for item in error.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": limpos})


def reader() -> CorpusReader:
    return CorpusReader(get_settings().corpus_dir)


def layout_store() -> LayoutStore:
    return LayoutStore(get_settings().state_dir / "layout")


def operational_slot_store() -> OperationalSlotStore:
    return OperationalSlotStore(get_settings().state_dir / "operational-slots")


@app.get("/health")
async def health() -> dict[str, Any]:
    """Liveness no event loop: não disputa threadpool com a projeção."""
    settings = get_settings()
    corpus = settings.corpus_dir
    return {
        "version": __version__,
        "corpus": str(corpus),
        "corpus_present": corpus.is_dir(),
        # Só a presença da credencial. O valor nunca sai daqui.
        "credentials": settings.credential_status(),
    }


def _list_notes_payload() -> dict[str, Any]:
    notes = reader().list_notes()
    return {
        "count": len(notes),
        "notes": [
            {
                "id": note.id,
                "title": note.title,
                "domain": note.domain,
                "kind": note.kind,
                "epistemicStatus": note.epistemic_status,
                "path": str(note.path),
            }
            for note in notes
        ],
    }


@app.get("/corpus/notes")
async def list_notes() -> dict[str, Any]:
    """Índice do corpus: disco fora do event loop, como a projeção."""
    return await asyncio.to_thread(_list_notes_payload)


def _read_note_payload(name: str) -> dict[str, Any]:
    corpus = reader()
    try:
        note = corpus.read_note(name)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    claims = corpus.extract_claims(note)
    links = corpus.extract_links(note)
    return {
        "id": note.id,
        "title": note.title,
        "domain": note.domain,
        "kind": note.kind,
        "epistemicStatus": note.epistemic_status,
        "aliases": note.aliases,
        "path": str(note.path),
        "claims": [
            {"id": c.id, "statement": c.statement, "status": c.status, "evidence": c.evidence}
            for c in claims
        ],
        "links": [
            {"target": link.target, "relation": link.relation, "line": link.line}
            for link in links
        ],
    }


@app.get("/corpus/notes/{name}")
async def read_note(name: str) -> dict[str, Any]:
    """Nota única: disco fora do event loop, como o índice."""
    return await asyncio.to_thread(_read_note_payload, name)


def _read_document_payload(ref: str) -> dict[str, Any]:
    corpus = reader()
    for candidato in (ref, f"{ref}.md"):
        # A contenção acontece **antes** do leitor, e não dentro do `except` dele.
        #
        # `read_note` já resolve e confere, mas quando a conferência falha ele cai numa
        # varredura do corpus inteiro — e essa varredura recusa symlink que sai da raiz
        # levantando `CorpusIdentityError` com o caminho externo na mensagem. Uma
        # referência que escapa virava 500 com o caminho absoluto de fora do corpus
        # dentro da resposta. Barrando aqui, ela nunca chega lá.
        if not _dentro_do_corpus(corpus.root, candidato):
            continue
        try:
            note = corpus.read_note(candidato)
        except (KeyError, ValueError):
            continue
        except CorpusIdentityError as error:
            # Corpus malformado é condição real e merece aparecer — mas sem eco: a
            # mensagem carrega o caminho para onde o symlink aponta.
            raise HTTPException(
                status_code=409, detail="corpus inconsistente: veja /corpus/projection"
            ) from error
        return {"id": note.id, "title": note.title, "path": str(note.path), "body": note.body}
    raise HTTPException(status_code=404, detail=f"nota não encontrada no corpus: {ref}")


@app.get("/corpus/documents/{ref:path}")
async def read_document(ref: str) -> dict[str, Any]:
    """O corpo canônico de uma nota, até o EOF, para o painel aberto mostrá-la inteira.

    A projeção não leva isto e não deve levar: ela é um artefato em bloco, versionado e
    servido inteiro a cada abertura, e pôr 84 corpos dentro dela multiplicaria por seis o
    que trafega para que um único painel — o que estiver aberto — use um deles. Aqui o
    corpo é buscado sob demanda, um por vez, que é exatamente quantos se leem por vez.

    O caminho é `path` e não um segmento porque a identidade de uma nota **tem** barras:
    ela é o caminho relativo POSIX sem extensão, e é assim que o wikilink a escreve.

    A contenção é a do próprio leitor: `read_note` resolve o caminho e exige que ele caia
    dentro do corpus, e `_parse` confere de novo antes de ler. Referência que escape vira
    404 pelo mesmo caminho que uma nota inexistente — sem revelar o que existe fora.
    """
    return await asyncio.to_thread(_read_document_payload, ref)


def _dentro_do_corpus(root: Path, ref: str) -> bool:
    """A referência resolve para dentro da raiz do corpus?

    **Resolver, e não normalizar.** As duas coisas divergem exatamente onde importa: um
    symlink dentro do corpus é um caminho que normaliza para dentro e resolve para fora, e
    é essa diferença que transforma um leitor de notas em leitor arbitrário do sistema de
    arquivos. `Path.resolve` percorre os links; a comparação acontece depois dele.
    """
    try:
        alvo = Path(ref)
        resolvido = (alvo if alvo.is_absolute() else root / alvo).resolve()
    except (OSError, ValueError):
        # Caminho impronunciável para o sistema de arquivos — byte nulo, nome longo
        # demais, laço de symlinks. Nada disso é nota, e nenhum deles merece diagnóstico
        # próprio: o que se responde é o mesmo 404 de qualquer referência inválida.
        return False
    return resolvido.is_relative_to(root)


@app.get("/corpus/projection")
async def corpus_projection(request: Request) -> dict[str, Any]:
    """Projeção sanitizada e versionada. É tudo que o navegador recebe do corpus.

    Sem caminho absoluto, sem conteúdo de arquivo, sem credencial. Ambiguidade de
    identidade vira 409 com o diagnóstico, e não um grafo plausível e errado.

    O overlay de quórum é CPU-bound (mtime de painéis + JSON). Montá-lo neste
    coroutine bloquearia `/health` e os SSE; a montagem corre numa thread, com
    cache de overlay em `with_runtime_quorum`.
    """
    watcher: CorpusProjectionWatcher | None = getattr(
        request.app.state, "corpus_watcher", None
    )
    settings = get_settings()
    quorum_root = settings.runtime_dir / "quorum"
    state_dir = settings.state_dir
    demo = settings.demo_operational

    def assemble() -> dict[str, Any]:
        # O fallback só atende chamadas diretas sem lifespan (por exemplo, inspeção
        # isolada). No servidor, o endpoint e o SSE leem o mesmo snapshot validado.
        base = (
            build_projection(reader(), demo_operational=demo)
            if watcher is None
            else watcher.projection
        )
        return with_runtime_quorum(base, quorum_root, state_dir)

    try:
        return await asyncio.to_thread(assemble)
    except (CorpusIdentityError, ProjectionError, ProjectionUnavailable) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/corpus/events")
async def corpus_events(request: Request) -> StreamingResponse:
    """SSE: estado atual na conexão, seguido de mudança válida ou erro de leitura."""
    watcher: CorpusProjectionWatcher | None = getattr(
        request.app.state, "corpus_watcher", None
    )
    if watcher is None:
        raise HTTPException(status_code=503, detail="watcher do corpus ainda não iniciado")

    async def stream() -> AsyncIterator[str]:
        async for event in watcher.events():
            if await request.is_disconnected():
                break
            payload = orjson.dumps(event.to_dict()).decode("utf-8")
            yield f"event: {event.kind}\ndata: {payload}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse_open() -> str:
    """Primeiro byte do canal: o EventSource só dispara `open` depois do header+chunk.

    Comentário SSE não chega ao JavaScript; só abre o socket. O snapshot operacional
    ainda pode demorar (cauda jsonl + GIL do worker); `runtime_events` manda um
    heartbeat nomeado em seguida para o SharedWorker não cair no prazo de 8 s.
    """
    return ": connected\n\n"


def _sse_frame(*, event: str, data: dict[str, Any], identifier: str | None = None) -> str:
    lines = []
    if identifier is not None:
        lines.append(f"id: {identifier}")
    lines.append(f"event: {event}")
    lines.append(f"data: {orjson.dumps(data).decode('utf-8')}")
    return "\n".join(lines) + "\n\n"


@app.get("/runtime/events", response_class=StreamingResponse)
async def runtime_events(request: Request) -> StreamingResponse:
    """SSE operacional: snapshot inicial, replay por ID e atualizações persistidas."""
    event_bus: OperationalEventBus | None = getattr(
        request.app.state, "operational_event_bus", None
    )
    if event_bus is None:
        raise HTTPException(status_code=503, detail="event bus operacional ainda não iniciado")

    requested_revision = revision_from_event_id(request.headers.get("last-event-id"))

    async def stream() -> AsyncIterator[str]:
        yield _sse_open()
        # O SharedWorker só cancela o prazo de 8 s no primeiro evento *nomeado*.
        # Comentário abre o EventSource; heartbeat declara o canal vivo enquanto
        # ``snapshot()`` lê a cauda do jsonl (dezenas de segundos sob o worker).
        yield _sse_frame(
            event="runtime_heartbeat",
            data={"runtimeRevision": event_bus.revision},
        )
        snapshot = await event_bus.snapshot()
        if requested_revision is None or requested_revision > snapshot.runtime_revision:
            # O navegador deriva a camada visual dos eventos. Enviar aqui a projeção
            # operacional inteira duplicava esse trabalho e quadruplicava o primeiro
            # frame sem que o cliente consumisse o campo adicional.
            payload = snapshot.to_dict()
            yield _sse_frame(
                event="runtime_snapshot",
                data=payload,
                identifier=snapshot.latest_id,
            )
            cursor = snapshot.runtime_revision
        else:
            cursor = requested_revision

        while True:
            if await request.is_disconnected():
                break
            events = await event_bus.wait_after(
                cursor,
                timeout=RUNTIME_HEARTBEAT_SECONDS,
            )
            if not events:
                # Evento nomeado, não comentário: ``EventSource`` descarta comentários
                # antes que o JavaScript possa observá-los. A revisão prova de qual
                # cursor este sinal de vida parte sem inventar evento operacional nem
                # avançar o ``Last-Event-ID`` do navegador.
                yield _sse_frame(
                    event="runtime_heartbeat",
                    data={"runtimeRevision": cursor},
                )
                continue
            for event in events:
                yield _sse_frame(
                    event=event.type,
                    data=event.to_dict(),
                    identifier=event.id,
                )
                cursor = event.revision

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/runtime/cognition", response_class=StreamingResponse)
async def runtime_cognition(request: Request) -> StreamingResponse:
    """SSE do raciocínio ao vivo. Não é a trilha operacional e não entra no corpus."""
    cognition_bus: CognitionBus | None = getattr(request.app.state, "cognition_bus", None)
    if cognition_bus is None:
        raise HTTPException(status_code=503, detail="canal cognitivo ainda não iniciado")

    requested = revision_from_frame_id(request.headers.get("last-event-id"))

    async def stream() -> AsyncIterator[str]:
        yield _sse_open()
        snapshot = await cognition_bus.snapshot()
        if requested is None or requested > snapshot.revision:
            yield _sse_frame(
                event="cognition_snapshot",
                data=snapshot.to_dict(),
                identifier=snapshot.latest_id,
            )
            cursor = snapshot.revision
        else:
            cursor = requested
        while True:
            if await request.is_disconnected():
                break
            frames = await cognition_bus.wait_after(cursor, timeout=RUNTIME_HEARTBEAT_SECONDS)
            if not frames:
                yield _sse_frame(
                    event="cognition_heartbeat",
                    data={"revision": cursor},
                )
                continue
            for frame in frames:
                yield _sse_frame(
                    event=frame.kind,
                    data=frame.to_dict(),
                    identifier=frame.id,
                )
                cursor = frame.revision

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _list_proposals_payload() -> dict[str, Any]:
    store = ProposalStore(get_settings().proposals_dir)
    proposals = store.list_proposals()
    return {
        "count": len(proposals),
        "proposals": [
            {
                "id": p.id,
                "createdAt": p.created_at,
                "kind": p.kind,
                "provider": p.provider,
                "endpoint": p.endpoint,
                "status": p.status,
                "validatedBy": p.validated_by,
            }
            for p in proposals
        ],
    }


@app.get("/proposals")
async def list_proposals() -> dict[str, Any]:
    return await asyncio.to_thread(_list_proposals_payload)


# --- memória espacial -------------------------------------------------------
#
# Estes são os únicos verbos de escrita da API, e escrevem num único lugar:
# `runtime/state/layout/`. Posição não é conhecimento — não mede verdade, importância
# nem confiança —, e o corpus continua somente leitura para todo o sistema.


def _read_layout_payload(fingerprint: str, algorithm_version: str) -> dict[str, Any]:
    snapshot = layout_store().load(fingerprint, algorithm_version)
    if snapshot is None:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "corpusFingerprint": fingerprint,
            "algorithmVersion": algorithm_version,
            "positions": {},
        }
    return snapshot.to_dict()


@app.get("/layout/{fingerprint}")
async def read_layout(
    fingerprint: str,
    algorithm_version: Annotated[AlgorithmVersion, Query(alias="algorithmVersion")],
) -> dict[str, Any]:
    """Posições gravadas para esta impressão do corpus. Ausência não é erro."""
    return await asyncio.to_thread(_read_layout_payload, fingerprint, algorithm_version)


@app.put("/layout/{fingerprint}")
def write_layout(request: Request, fingerprint: str, body: LayoutWriteBody) -> dict[str, Any]:
    """Grava posições somente sob a impressão viva do corpus atual."""
    try:
        watcher: CorpusProjectionWatcher | None = getattr(
            request.app.state, "corpus_watcher", None
        )
        projection = (
            watcher.projection
            if watcher is not None
            else build_projection(
                reader(),
                demo_operational=get_settings().demo_operational,
            )
        )
        current_fingerprint = str(projection["meta"]["corpusFingerprint"])
        if fingerprint != current_fingerprint:
            raise HTTPException(
                status_code=409,
                detail="impressão do layout não corresponde à projeção viva",
            )
        # Fingerprint e identidades saem do mesmo snapshot validado. Reler o disco
        # aqui permitiria que uma gravação parcial podasse o layout da revisão viva.
        conhecidas = {
            str(node["id"])
            for node in projection["nodes"]
            if node.get("layer") == "epistemic"
        }
        snapshot = layout_store().save(
            fingerprint,
            positions_from_payload(body.positions),
            algorithm_version=body.algorithm_version,
            known_ids=conhecidas,
        )
    except LayoutStoreError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except (CorpusIdentityError, ProjectionError, ProjectionUnavailable) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {
        "stored": len(snapshot.positions),
        "corpusFingerprint": snapshot.corpus_fingerprint,
        "algorithmVersion": snapshot.algorithm_version,
        "updatedAt": snapshot.updated_at,
    }


def _read_operational_slots_payload(algorithm_version: int) -> dict[str, Any]:
    snapshot = operational_slot_store().load(algorithm_version)
    if snapshot is None:
        return {
            "schemaVersion": OPERATIONAL_SLOTS_SCHEMA_VERSION,
            "algorithmVersion": algorithm_version,
            "updatedAt": "",
            "slots": {},
        }
    return snapshot.to_dict()


@app.get("/operational-layout/{algorithm_version}")
async def read_operational_slots(algorithm_version: int) -> dict[str, Any]:
    """Ordinais globais das execuções para uma versão da geometria operacional.

    Versão nova não é erro: é ausência de memória para aquela geometria. O store
    já recusa inteiro fora de 1–10000; repetir um enum aqui derruba a cena quando
    o frontend sobe a versão — foi o 422 em `/operational-layout/6`.
    """
    return await asyncio.to_thread(_read_operational_slots_payload, algorithm_version)


@app.put("/operational-layout/{algorithm_version}")
def write_operational_slots(
    algorithm_version: int,
    body: OperationalSlotsWriteBody,
) -> dict[str, Any]:
    """Acrescenta painéis sem deslocar os ordinais já aceitos."""
    try:
        snapshot = operational_slot_store().merge(
            algorithm_version, slots_from_payload(body.slots)
        )
    except LayoutStoreError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return snapshot.to_dict()
