"""Log efêmero do raciocínio. Redige segredo; não remove pensamento."""

from __future__ import annotations

import fcntl
import os
from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import orjson
from pydantic import ValidationError

from vault.cognition.models import COGNITION_KINDS, CognitionFrame, frame_id

_PRIVATE_DIRECTORY_MODE = 0o700
_PRIVATE_FILE_MODE = 0o600
_LOCK_FILENAME = ".cognition.lock"
_LOG_FILENAME = "frames.jsonl"
_MAX_LINE_BYTES = 8_000
_MAX_TEXT = 360
_MAX_FRAMES = 240


class CognitionStoreError(RuntimeError):
    """Persistência cognitiva não pôde gravar ou ler um quadro."""


def _identity(text: str) -> str:
    return text


class CognitionStore:
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

    def append(
        self,
        *,
        kind: str,
        provider: str,
        endpoint: str,
        text: str = "",
        task: str | None = None,
    ) -> CognitionFrame:
        if kind not in COGNITION_KINDS:
            raise CognitionStoreError(f"tipo cognitivo desconhecido: {kind}")
        self._prepare_directory()
        with self._exclusive_lock():
            frames = self._read_all()
            revision = frames[-1].revision + 1 if frames else 1
            frame = CognitionFrame(
                id=frame_id(revision),
                revision=revision,
                timestamp=self._next_timestamp(frames[-1] if frames else None),
                kind=kind,  # type: ignore[arg-type]
                provider=self.redact(provider)[:80],
                endpoint=self.redact(endpoint)[:300],
                task=self.redact(task)[:160] if task else None,
                text=self._clip(text),
            )
            frames.append(frame)
            if len(frames) > _MAX_FRAMES:
                frames = frames[-_MAX_FRAMES:]
            self._rewrite(frames)
            return frame

    def load(
        self, *, after_revision: int = 0, limit: int | None = None
    ) -> list[CognitionFrame]:
        frames = [frame for frame in self._read_all() if frame.revision > after_revision]
        if limit is not None and after_revision == 0 and len(frames) > limit:
            return frames[-limit:]
        if limit is not None and after_revision > 0:
            return frames[:limit]
        return frames

    def latest_revision(self) -> int:
        frames = self._read_all()
        return frames[-1].revision if frames else 0

    def _clip(self, text: str) -> str:
        clean = " ".join(self.redact(text).split()).strip()
        if len(clean) <= _MAX_TEXT:
            return clean
        return clean[-_MAX_TEXT:]

    @staticmethod
    def _next_timestamp(latest: CognitionFrame | None) -> str:
        moment = datetime.now(UTC)
        if latest is not None:
            previous = datetime.fromisoformat(latest.timestamp)
            if moment <= previous:
                moment = previous + timedelta(microseconds=1)
        return moment.isoformat(timespec="microseconds")

    def _read_all(self) -> list[CognitionFrame]:
        if not self.log_path.is_file() or self.log_path.is_symlink():
            return []
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        try:
            descriptor = os.open(self.log_path, flags)
        except OSError as error:
            raise CognitionStoreError("log cognitivo não pôde ser lido") from error
        frames: list[CognitionFrame] = []
        last = 0
        with os.fdopen(descriptor, "rb") as stream:
            for line in stream:
                try:
                    raw: Any = orjson.loads(line)
                    frame = CognitionFrame.model_validate(raw)
                except (orjson.JSONDecodeError, ValidationError, TypeError):
                    continue
                if frame.revision <= last:
                    continue
                last = frame.revision
                frames.append(frame)
        return frames

    def _rewrite(self, frames: list[CognitionFrame]) -> None:
        payload = b"".join(orjson.dumps(frame.to_dict()) + b"\n" for frame in frames)
        tmp = self.log_path.with_suffix(".jsonl.tmp")
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_CLOEXEC | os.O_NOFOLLOW
        descriptor = os.open(tmp, flags, _PRIVATE_FILE_MODE)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, self.log_path)

    def _prepare_directory(self) -> None:
        self.directory.mkdir(mode=_PRIVATE_DIRECTORY_MODE, parents=True, exist_ok=True)
        os.chmod(self.directory, _PRIVATE_DIRECTORY_MODE)

    @contextmanager
    def _exclusive_lock(self):
        flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW
        descriptor = os.open(self.lock_path, flags, _PRIVATE_FILE_MODE)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
