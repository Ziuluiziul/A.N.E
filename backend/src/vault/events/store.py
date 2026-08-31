"""Log privado, append-only e monotônico dos eventos operacionais."""

from __future__ import annotations

try:
    import fcntl
except ImportError:  # NT
    fcntl = None  # type: ignore[assignment]

import math
import os
import re
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import orjson
from pydantic import ValidationError

from vault.events.models import OperationalEvent, OperationalEventDraft, event_id

_PRIVATE_DIRECTORY_MODE = 0o700
_PRIVATE_FILE_MODE = 0o600
_LOCK_FILENAME = ".events.lock"
_LOG_FILENAME = "events.jsonl"
_MAX_EVENT_BYTES = 64_000
_MAX_JSON_DEPTH = 8
_MAX_COLLECTION_ITEMS = 256
_MAX_TEXT_LENGTH = 4_000
_FORBIDDEN_KEY_FRAGMENTS = (
    "rawresponse",
    "finalresponse",
    "reasoning",
    "scratchpad",
    "chainofthought",
    "think",
    "prompt",
)
_THINK_TAG = re.compile(r"<\s*(/?)\s*think\b[^>]*>", re.IGNORECASE)
_THINK_PREFIX = re.compile(r"<\s*/?\s*think\b", re.IGNORECASE)


class OperationalEventStoreError(RuntimeError):
    """Persistência ou payload não preservariam o contrato do event log."""


def _identity(text: str) -> str:
    return text


def _without_reasoning(text: str) -> str:
    """Remove blocos ``<think>`` sem interpretar o conteúdo removido."""
    pieces: list[str] = []
    depth = 0
    cursor = 0
    for match in _THINK_TAG.finditer(text):
        if depth == 0:
            pieces.append(text[cursor : match.start()])
        if match.group(1):
            depth = max(depth - 1, 0)
        else:
            depth += 1
        cursor = match.end()
    if depth == 0:
        pieces.append(text[cursor:])
    clean = "".join(pieces)
    incomplete = _THINK_PREFIX.search(clean)
    if incomplete is not None:
        clean = clean[: incomplete.start()]
    return clean


def _clean_text(value: str, redact: Callable[[str], str], *, limit: int) -> str:
    clean = _without_reasoning(redact(value))
    clean = " ".join(clean.split()).strip()
    return clean[:limit]


def _clean_optional(
    value: str | None,
    redact: Callable[[str], str],
    *,
    limit: int,
) -> str | None:
    if value is None:
        return None
    clean = _clean_text(value, redact, limit=limit)
    return clean or None


def _forbidden_key(value: str) -> bool:
    canonical = re.sub(r"[^a-z0-9]", "", value.casefold())
    return any(fragment in canonical for fragment in _FORBIDDEN_KEY_FRAGMENTS)


def _sanitize_json(
    value: Any,
    redact: Callable[[str], str],
    *,
    depth: int = 0,
) -> Any:
    if depth > _MAX_JSON_DEPTH:
        raise OperationalEventStoreError("metadado operacional excede profundidade máxima")
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise OperationalEventStoreError("metadado operacional contém número não finito")
        return value
    if isinstance(value, str):
        return _clean_text(value, redact, limit=_MAX_TEXT_LENGTH)
    if isinstance(value, list | tuple):
        if len(value) > _MAX_COLLECTION_ITEMS:
            raise OperationalEventStoreError("metadado operacional contém coleção excessiva")
        return [_sanitize_json(item, redact, depth=depth + 1) for item in value]
    if isinstance(value, dict):
        if len(value) > _MAX_COLLECTION_ITEMS:
            raise OperationalEventStoreError("metadado operacional contém objeto excessivo")
        sanitized: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = _clean_text(str(raw_key), redact, limit=120)
            if not key or _forbidden_key(key):
                continue
            sanitized[key] = _sanitize_json(raw_value, redact, depth=depth + 1)
        return sanitized
    raise OperationalEventStoreError(
        f"metadado operacional contém tipo não serializável: {type(value).__name__}"
    )


def sanitize_draft(
    draft: OperationalEventDraft,
    redact: Callable[[str], str],
) -> OperationalEventDraft:
    """Lista branca recursiva aplicada antes de qualquer byte chegar ao log."""
    return OperationalEventDraft(
        type=draft.type,
        actor=_clean_optional(draft.actor, redact, limit=240),
        provider=_clean_optional(draft.provider, redact, limit=80),
        endpoint=_clean_optional(draft.endpoint, redact, limit=300),
        task=_clean_optional(draft.task, redact, limit=160),
        entity=_clean_optional(draft.entity, redact, limit=300),
        before=_sanitize_json(draft.before, redact),
        after=_sanitize_json(draft.after, redact),
        metadata=_sanitize_json(draft.metadata, redact),
    )


def _strictly_increasing(events: Iterable[OperationalEvent]) -> list[OperationalEvent]:
    """Mantém só a subsequência gulosa de revisões estritamente crescentes."""
    accepted: list[OperationalEvent] = []
    last_revision = 0
    for event in events:
        if event.revision <= last_revision:
            continue
        last_revision = event.revision
        accepted.append(event)
    return accepted


def _chmod_private_file(descriptor: int) -> None:
    """Ajusta modo do arquivo aberto. No NT não chmod — Errno 13 mesmo com Full control."""
    if os.name == "nt":
        return
    fchmod = getattr(os, "fchmod", None)
    if fchmod is None:
        return
    try:
        fchmod(descriptor, _PRIVATE_FILE_MODE)
    except OSError:
        return


class OperationalEventStore:
    """Persiste eventos entre processos sem criar diretório enquanto o fluxo está vazio."""

    def __init__(
        self,
        directory: Path,
        *,
        redact: Callable[[str], str] | None = None,
    ) -> None:
        self.directory = Path(directory)
        self.log_path = self.directory / _LOG_FILENAME
        self.lock_path = self.directory / _LOCK_FILENAME
        self.redact = redact or _identity

    def append(self, draft: OperationalEventDraft) -> OperationalEvent:
        sanitized = sanitize_draft(draft, self.redact)
        self._prepare_directory()
        with self._exclusive_lock():
            latest = self._latest_valid_event()
            revision = latest.revision + 1 if latest is not None else 1
            event = OperationalEvent(
                id=event_id(revision),
                revision=revision,
                timestamp=self._next_timestamp(latest),
                **sanitized.model_dump(),
            )
            line = orjson.dumps(event.to_dict()) + b"\n"
            if len(line) > _MAX_EVENT_BYTES:
                raise OperationalEventStoreError("evento operacional excede 64 KB")
            self._append_line(line)
            self._fsync_directory()
            return event

    def load(
        self,
        *,
        after_revision: int = 0,
        limit: int | None = None,
    ) -> list[OperationalEvent]:
        """Lê somente linhas válidas e estritamente crescentes.

        Uma cauda parcial após queda de energia é ausência temporária, não motivo para
        derrubar o Atlas. A próxima leitura a verá completa; uma linha adulterada nunca
        é projetada nem governa a próxima revisão válida.

        ``after_revision == 0`` com ``limit`` lê da cauda: o snapshot do Atlas não
        varre o jsonl inteiro. ``after_revision > 0`` permanece o scan linear que
        pára ao completar o lote.
        """
        if not self.log_path.is_file() or self.log_path.is_symlink():
            return []
        if after_revision == 0 and limit is not None:
            return self._load_from_tail(limit)
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        try:
            descriptor = os.open(self.log_path, flags)
        except OSError as error:
            raise OperationalEventStoreError(
                "event log não pôde ser lido com segurança"
            ) from error

        events: list[OperationalEvent] = []
        last_revision = 0
        with os.fdopen(descriptor, "rb") as stream:
            for line in stream:
                event = self._validated_line(line)
                if event is None:
                    continue
                if event.revision <= last_revision:
                    continue
                last_revision = event.revision
                if event.revision <= after_revision:
                    continue
                events.append(event)
                if limit is not None and after_revision > 0 and len(events) >= limit:
                    break
        return events

    def _load_from_tail(self, limit: int) -> list[OperationalEvent]:
        """Últimos ``limit`` eventos válidos, sem varrer o arquivo desde o início."""
        if limit <= 0:
            return []
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        try:
            descriptor = os.open(self.log_path, flags)
        except OSError as error:
            raise OperationalEventStoreError(
                "event log não pôde ser lido com segurança"
            ) from error
        try:
            size = os.fstat(descriptor).st_size
            cursor = size
            pending = b""
            chunk_size = 64 * 1024
            newest_first: list[OperationalEvent] = []
            while cursor > 0:
                amount = min(chunk_size, cursor)
                cursor -= amount
                os.lseek(descriptor, cursor, os.SEEK_SET)
                pending = os.read(descriptor, amount) + pending
                lines = pending.splitlines()
                # O primeiro fragmento pode estar incompleto enquanto ainda há bytes
                # à esquerda. Todas as demais linhas já são candidatas completas.
                if cursor > 0:
                    complete = lines[1:]
                    pending = lines[0] if lines else pending
                else:
                    complete = lines
                    pending = b""
                for line in reversed(complete):
                    event = self._validated_line(line)
                    if event is None:
                        continue
                    newest_first.append(event)
                    accepted = _strictly_increasing(reversed(newest_first))
                    if len(accepted) >= limit:
                        return accepted[-limit:]
            trailing = self._validated_line(pending)
            if trailing is not None:
                newest_first.append(trailing)
            accepted = _strictly_increasing(reversed(newest_first))
            return accepted[-limit:]
        finally:
            os.close(descriptor)

    def latest_revision(self) -> int:
        event = self._latest_valid_event()
        return event.revision if event is not None else 0

    @staticmethod
    def _next_timestamp(latest: OperationalEvent | None) -> str:
        moment = datetime.now(UTC)
        if latest is not None:
            previous = datetime.fromisoformat(latest.timestamp)
            if moment <= previous:
                moment = previous + timedelta(microseconds=1)
        return moment.isoformat(timespec="microseconds")

    def _latest_valid_event(self) -> OperationalEvent | None:
        """Lê da cauda para trás; o caminho comum não cresce com o histórico."""
        if not self.log_path.is_file() or self.log_path.is_symlink():
            return None
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        try:
            descriptor = os.open(self.log_path, flags)
        except OSError as error:
            raise OperationalEventStoreError(
                "event log não pôde ser lido com segurança"
            ) from error
        try:
            size = os.fstat(descriptor).st_size
            cursor = size
            pending = b""
            chunk_size = 64 * 1024
            while cursor > 0:
                amount = min(chunk_size, cursor)
                cursor -= amount
                os.lseek(descriptor, cursor, os.SEEK_SET)
                pending = os.read(descriptor, amount) + pending
                lines = pending.splitlines()
                # O primeiro fragmento pode estar incompleto enquanto ainda há bytes
                # à esquerda. Todas as demais linhas já são candidatas completas.
                start = 1 if cursor > 0 else 0
                for line in reversed(lines[start:]):
                    event = self._validated_line(line)
                    if event is not None:
                        return event
                pending = lines[0] if lines else pending
            return self._validated_line(pending)
        finally:
            os.close(descriptor)

    def _validated_line(self, line: bytes) -> OperationalEvent | None:
        if not line.strip():
            return None
        try:
            raw = orjson.loads(line)
            event = OperationalEvent.model_validate(raw)
            sanitized = sanitize_draft(
                OperationalEventDraft(
                    type=event.type,
                    actor=event.actor,
                    provider=event.provider,
                    endpoint=event.endpoint,
                    task=event.task,
                    entity=event.entity,
                    before=event.before,
                    after=event.after,
                    metadata=event.metadata,
                ),
                self.redact,
            )
        except (
            orjson.JSONDecodeError,
            ValidationError,
            OperationalEventStoreError,
            TypeError,
        ):
            return None
        return event.model_copy(update=sanitized.model_dump())

    def _prepare_directory(self) -> None:
        if self.directory.is_symlink():
            raise OperationalEventStoreError("diretório de eventos não pode ser link simbólico")
        if self.directory.exists():
            # Dir já existe: nunca mkdir, nunca chmod. Append só no jsonl.
            return
        try:
            self.directory.mkdir(parents=True, mode=_PRIVATE_DIRECTORY_MODE)
        except FileExistsError:
            # Corrida: outro processo criou o dir. Não chmod no caminho existente.
            return
        if os.name != "nt":
            try:
                os.chmod(self.directory, _PRIVATE_DIRECTORY_MODE)
            except OSError:
                return

    def _open_lock_descriptor(self) -> int | None:
        """Abre ``.events.lock`` se já existir; senão trava o jsonl.

        Dir + jsonl existentes: nenhum arquivo novo. No NT, lock ausente não
        é criado — o append segue. Bootstrap POSIX (dir recém-criado, jsonl
        ainda ausente) ainda pode criar o lock.
        """
        cloexec = getattr(os, "O_CLOEXEC", 0)
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        existing = os.O_RDWR | cloexec | nofollow
        jsonl_ready = self.log_path.is_file() and not self.log_path.is_symlink()
        lock_ready = self.lock_path.exists() and not self.lock_path.is_symlink()
        if lock_ready:
            try:
                return os.open(self.lock_path, existing)
            except OSError:
                return None
        if jsonl_ready:
            if os.name == "nt" or fcntl is None:
                return None
            try:
                return os.open(self.log_path, existing)
            except OSError:
                return None
        if os.name == "nt":
            return None
        try:
            return os.open(
                self.lock_path,
                os.O_RDWR | os.O_CREAT | cloexec | nofollow,
                _PRIVATE_FILE_MODE,
            )
        except OSError:
            return None

    @contextmanager
    def _exclusive_lock(self):
        descriptor = self._open_lock_descriptor()
        if descriptor is None:
            yield
            return
        locked = False
        try:
            _chmod_private_file(descriptor)
            if fcntl is not None:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX)
                    locked = True
                except OSError:
                    pass
            yield
        finally:
            try:
                if locked and fcntl is not None:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)

    def _append_line(self, line: bytes) -> None:
        separator = b"\n" if self._log_needs_separator() else b""
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_CLOEXEC | os.O_NOFOLLOW
        existed = self.log_path.is_file() and not self.log_path.is_symlink()
        try:
            descriptor = os.open(self.log_path, flags, _PRIVATE_FILE_MODE)
        except OSError as error:
            raise OperationalEventStoreError("event log não pôde ser aberto") from error
        try:
            if not existed:
                _chmod_private_file(descriptor)
            with os.fdopen(descriptor, "ab", closefd=False) as stream:
                stream.write(separator + line)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            os.close(descriptor)

    def _log_needs_separator(self) -> bool:
        if not self.log_path.exists():
            return False
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        try:
            descriptor = os.open(self.log_path, flags)
        except OSError as error:
            raise OperationalEventStoreError("event log não pôde ser inspecionado") from error
        try:
            size = os.fstat(descriptor).st_size
            if size == 0:
                return False
            os.lseek(descriptor, -1, os.SEEK_END)
            return os.read(descriptor, 1) != b"\n"
        finally:
            os.close(descriptor)

    def _fsync_directory(self) -> None:
        if os.name == "nt":
            return
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
        try:
            descriptor = os.open(self.directory, flags)
        except OSError:
            return
        try:
            os.fsync(descriptor)
        except OSError:
            return
        finally:
            os.close(descriptor)
