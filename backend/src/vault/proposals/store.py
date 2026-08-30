"""ProposalStore — o que os modelos produzem, antes de valer alguma coisa.

Uma proposta é saída de modelo: um texto, uma relação sugerida, um claim candidato.
Ela mora em `runtime/proposals/`, que não é versionado, e não é conhecimento. A
separação é o ponto: o corpus em `knowledge/` só recebe o que passou por decisão
humana, e esta classe não tem como escrever lá.

`promote_after_validation` registra o veredito de quem validou e devolve o caminho
da proposta aprovada. A aplicação da mudança em `knowledge/` é edição humana nesta
fase — a Política exige julgamento editorial, e um método não substitui isso.
"""

from __future__ import annotations

import fcntl
import hashlib
import os
import re
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import orjson

Status = Literal["pending", "approved", "rejected"]

_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,239}")
_UNSAFE_PROVIDER_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_LOCK_FILENAME = ".proposal-store.lock"
_PRIVATE_DIRECTORY_MODE = 0o700
_PRIVATE_FILE_MODE = 0o600


class PromotionRefused(RuntimeError):
    """Tentativa de tratar proposta como conhecimento sem validação humana."""


@dataclass(slots=True)
class Proposal:
    id: str
    created_at: str
    kind: str
    provider: str
    endpoint: str
    prompt_summary: str
    payload: dict[str, Any]
    status: Status = "pending"
    validated_by: str | None = None
    validated_at: str | None = None
    verdict_note: str | None = None
    targets: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class ProposalStore:
    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(
            mode=_PRIVATE_DIRECTORY_MODE,
            parents=True,
            exist_ok=True,
        )
        self.directory.chmod(_PRIVATE_DIRECTORY_MODE)
        self._lock_path = self.directory / _LOCK_FILENAME

    def _path(self, proposal_id: str) -> Path:
        if _ID_PATTERN.fullmatch(proposal_id) is None:
            raise ValueError(f"ID de proposta inválido: {proposal_id!r}")
        return self.directory / f"{proposal_id}.json"

    @contextmanager
    def _exclusive_lock(self) -> Iterator[None]:
        flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW
        descriptor = os.open(self._lock_path, flags, _PRIVATE_FILE_MODE)
        locked = False
        try:
            os.fchmod(descriptor, _PRIVATE_FILE_MODE)
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            locked = True
            yield
        finally:
            try:
                if locked:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)

    def save_proposal(
        self,
        *,
        kind: str,
        provider: str,
        endpoint: str,
        prompt_summary: str,
        payload: dict[str, Any],
        targets: list[str] | None = None,
    ) -> Proposal:
        """Grava uma proposta nova. O ID carrega a origem para leitura direta."""
        with self._exclusive_lock():
            created_at = _now()
            digest = hashlib.sha256(
                orjson.dumps([provider, endpoint, payload], option=orjson.OPT_SORT_KEYS)
            ).hexdigest()[:12]
            stamp = created_at.replace(":", "").replace("-", "")
            provider_component = _UNSAFE_PROVIDER_CHARS.sub("-", provider).strip("._-")
            provider_component = provider_component[:48] or "provider"
            base_id = f"{stamp}-{provider_component}-{digest}-{uuid.uuid4().hex}"
            proposal_id = base_id
            sequence = 0
            while os.path.lexists(self._path(proposal_id)):
                sequence += 1
                proposal_id = f"{base_id}-{sequence:x}"

            proposal = Proposal(
                id=proposal_id,
                created_at=created_at,
                kind=kind,
                provider=provider,
                endpoint=endpoint,
                prompt_summary=prompt_summary,
                payload=payload,
                targets=list(targets or []),
            )
            self._write(proposal)
        return proposal

    def _write(self, proposal: Proposal) -> Path:
        path = self._path(proposal.id)
        serialized = orjson.dumps(proposal.to_dict(), option=orjson.OPT_INDENT_2)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".proposal-",
            suffix=".tmp",
            dir=self.directory,
        )
        temporary_path = Path(temporary_name)
        try:
            os.fchmod(descriptor, _PRIVATE_FILE_MODE)
            stream = os.fdopen(descriptor, "wb")
            descriptor = -1
            with stream:
                stream.write(serialized)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, path)
            self._fsync_directory()
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            temporary_path.unlink(missing_ok=True)
        return path

    def _fsync_directory(self) -> None:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
        descriptor = os.open(self.directory, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def get(self, proposal_id: str) -> Proposal:
        path = self._path(proposal_id)
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags)
        except FileNotFoundError:
            raise KeyError(f"proposta inexistente: {proposal_id}") from None
        with os.fdopen(descriptor, "rb") as stream:
            return Proposal(**orjson.loads(stream.read()))

    def list_proposals(self, status: Status | None = None) -> list[Proposal]:
        proposals = [self.get(path.stem) for path in sorted(self.directory.glob("*.json"))]
        if status is None:
            return proposals
        return [p for p in proposals if p.status == status]

    def promote_after_validation(
        self,
        proposal_id: str,
        *,
        validated_by: str,
        verdict_note: str,
        approved: bool = True,
    ) -> Proposal:
        """Registra a decisão humana sobre uma proposta.

        Não escreve em `knowledge/`: aprovar significa que a proposta está liberada
        para ser editada no corpus por quem a validou, não que ela já entrou.
        """
        if not validated_by.strip():
            raise PromotionRefused("promoção exige identificar quem validou")
        if not verdict_note.strip():
            raise PromotionRefused("promoção exige registrar o motivo do veredito")

        with self._exclusive_lock():
            proposal = self.get(proposal_id)
            if proposal.status != "pending":
                raise PromotionRefused(
                    f"proposta {proposal_id} já foi decidida como {proposal.status}"
                )
            proposal.status = "approved" if approved else "rejected"
            proposal.validated_by = validated_by
            proposal.validated_at = _now()
            proposal.verdict_note = verdict_note
            self._write(proposal)
        return proposal
