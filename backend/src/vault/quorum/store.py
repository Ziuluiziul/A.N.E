"""Persistência privada e auditável dos painéis em ``runtime/quorum``."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson

from vault.quorum.models import Panel, ParseResult, QuorumDecision
from vault.runtime_io import read_private_json, write_private_json

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class QuorumStoreError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True, slots=True)
class QuorumStore:
    root: Path

    def _directory(self, panel_id: str) -> Path:
        if not _SAFE_ID.fullmatch(panel_id):
            raise QuorumStoreError(f"identificador de painel inseguro: {panel_id!r}")
        directory = self.root / panel_id
        if self.root.resolve() not in directory.resolve().parents:
            raise QuorumStoreError("painel escaparia da raiz de runtime")
        return directory

    def create_panel(self, panel: Panel) -> Path:
        directory = self._directory(panel.id)
        if directory.exists():
            raise QuorumStoreError(f"painel já existe: {panel.id}")
        write_private_json(
            directory / "task.json",
            {
                "panel_id": panel.id,
                "task": panel.task.model_dump(mode="json"),
                "proposal": panel.proposal.model_dump(mode="json"),
            },
        )
        write_private_json(
            directory / "members.json",
            [member.model_dump(mode="json") for member in panel.members],
        )
        self._event(directory, "panel_created", {"members": len(panel.members)})
        return directory

    save_panel = create_panel

    def save_patch(self, panel_id: str, patch: dict[str, Any]) -> Path:
        """Guarda o patch que os avaliadores viram, ao lado do painel.

        Fica separado de `task.json` porque o digest no contexto do painel é a amarra:
        o patch pode ser lido e conferido sem que a leitura possa alterá-la.
        """
        from vault.promotion.patch import CorpusPatch

        directory = self._directory(panel_id)
        task_payload = read_private_json(directory / "task.json")
        if not isinstance(task_payload, dict):
            raise QuorumStoreError(f"painel não existe: {panel_id}")
        destination = directory / "patch.json"
        if destination.exists():
            raise QuorumStoreError(f"painel já tem patch: {panel_id}")

        try:
            artifact = CorpusPatch.model_validate(patch)
        except ValueError as error:
            raise QuorumStoreError("patch não obedece ao schema fechado") from error

        task = task_payload.get("task")
        proposal = task_payload.get("proposal")
        context = task.get("context") if isinstance(task, dict) else None
        expected_digest = context.get("patch_digest") if isinstance(context, dict) else None
        if expected_digest != artifact.digest():
            raise QuorumStoreError("digest do patch diverge do contexto persistido do painel")
        if not isinstance(proposal, dict) or proposal.get("id") != artifact.proposal_id:
            raise QuorumStoreError("patch pertence a outra proposta")

        reviewed = proposal.get("final_response")
        try:
            reviewed_artifact = orjson.loads(reviewed) if isinstance(reviewed, str) else None
        except orjson.JSONDecodeError as error:
            raise QuorumStoreError("proposta votada não contém um CorpusPatch JSON") from error
        payload = artifact.to_dict()
        if reviewed_artifact != payload:
            raise QuorumStoreError(
                "patch persistido diverge do artefato mostrado aos revisores"
            )

        write_private_json(destination, payload)
        self._event(
            directory,
            "patch_recorded",
            {"targets": len(artifact.operations), "digest": artifact.digest()},
        )
        return destination

    def load_patch(self, panel_id: str) -> dict[str, Any] | None:
        """O patch avaliado, ou `None` quando o painel não carrega alteração."""
        raw = read_private_json(self._directory(panel_id) / "patch.json")
        return raw if isinstance(raw, dict) else None

    def save_members(self, panel_id: str, members: list[Any]) -> Path:
        """Regrava o elenco depois de uma reposição de cadeira vazia."""
        directory = self._directory(panel_id)
        if not (directory / "task.json").is_file():
            raise QuorumStoreError(f"painel não existe: {panel_id}")
        destination = directory / "members.json"
        write_private_json(
            destination,
            [member.model_dump(mode="json") for member in members],
        )
        self._event(directory, "members_updated", {"members": len(members)})
        return destination

    def replace_decision(self, panel_id: str, decision: QuorumDecision) -> Path:
        """Substitui escalate por falta de voto. Não apaga promote/reject/revise."""
        directory = self._directory(panel_id)
        if decision.panel_id != panel_id:
            raise QuorumStoreError("decisão pertence a outro painel")
        if not (directory / "task.json").is_file():
            raise QuorumStoreError(f"painel não existe: {panel_id}")
        atual = read_private_json(directory / "decision.json")
        if isinstance(atual, dict) and atual.get("outcome") not in {None, "escalate"}:
            raise QuorumStoreError(
                f"painel {panel_id} já decidiu {atual.get('outcome')}; não substitui"
            )
        destination = directory / "decision.json"
        write_private_json(destination, decision.model_dump(mode="json"))
        self._event(
            directory,
            "decision_replaced",
            {"outcome": decision.outcome.value, "status": decision.status.value},
        )
        return destination

    def save_vote(self, panel_id: str, result: ParseResult) -> Path:
        directory = self._directory(panel_id)
        if not (directory / "task.json").is_file():
            raise QuorumStoreError(f"painel não existe: {panel_id}")
        digest = hashlib.sha256(result.reviewer.key.encode()).hexdigest()[:20]
        destination = directory / "votes" / f"{digest}.json"
        if destination.exists():
            raise QuorumStoreError(f"endpoint já votou no painel: {result.reviewer.key}")
        write_private_json(destination, result.model_dump(mode="json"))
        self._event(
            directory,
            "vote_recorded",
            {
                "reviewer": result.reviewer.key,
                "schema_valid": result.schema_valid,
                "decision": result.structured_vote.decision.value,
            },
        )
        return destination

    def save_decision(self, panel_id: str, decision: QuorumDecision) -> Path:
        directory = self._directory(panel_id)
        if decision.panel_id != panel_id:
            raise QuorumStoreError("decisão pertence a outro painel")
        if not (directory / "task.json").is_file():
            raise QuorumStoreError(f"painel não existe: {panel_id}")
        destination = directory / "decision.json"
        if destination.exists():
            raise QuorumStoreError(f"painel já possui decisão: {panel_id}")
        write_private_json(destination, decision.model_dump(mode="json"))
        self._event(
            directory,
            "decision_recorded",
            {"outcome": decision.outcome.value, "status": decision.status.value},
        )
        return destination

    def load_panel(self, panel_id: str) -> Panel:
        directory = self._directory(panel_id)
        task_payload = read_private_json(directory / "task.json")
        members = read_private_json(directory / "members.json")
        if not isinstance(task_payload, dict) or not isinstance(members, list):
            raise QuorumStoreError(f"painel ausente ou ilegível: {panel_id}")
        votes: list[Any] = []
        member_keys = {
            f"{member.get('provider')}/{member.get('endpoint_id')}"
            for member in members
            if isinstance(member, dict)
        }
        votes_dir = directory / "votes"
        if votes_dir.is_dir():
            for path in sorted(votes_dir.glob("*.json")):
                raw = read_private_json(path)
                reviewer = raw.get("reviewer") if isinstance(raw, dict) else None
                reviewer_key = (
                    f"{reviewer.get('provider')}/{reviewer.get('endpoint_id')}"
                    if isinstance(reviewer, dict)
                    else ""
                )
                # O árbitro é deliberadamente externo ao painel. Seu resultado fica
                # no diretório de votos e embutido em decision.json, mas não vira
                # membro retroativamente ao reconstruir o painel.
                if raw is not None and reviewer_key in member_keys:
                    votes.append(raw)
        decision = read_private_json(directory / "decision.json")
        try:
            return Panel.model_validate(
                {
                    "id": panel_id,
                    "task": task_payload.get("task"),
                    "proposal": task_payload.get("proposal"),
                    "members": members,
                    "votes": votes,
                    "decision": decision,
                }
            )
        except ValueError as error:
            raise QuorumStoreError(f"painel inválido: {panel_id}") from error

    def list_panels(self) -> list[Panel]:
        if not self.root.is_dir():
            return []
        panels: list[Panel] = []
        for directory in sorted(self.root.iterdir()):
            if not directory.is_dir() or not _SAFE_ID.fullmatch(directory.name):
                continue
            try:
                panels.append(self.load_panel(directory.name))
            except QuorumStoreError:
                continue
        return panels

    def _event(self, directory: Path, kind: str, detail: dict[str, Any]) -> None:
        directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        os.chmod(directory, 0o700)
        path = directory / "events.jsonl"
        line = orjson.dumps({"at": _now(), "kind": kind, **detail}) + b"\n"
        with path.open("ab") as stream:
            stream.write(line)
            stream.flush()
            os.fsync(stream.fileno())
        path.chmod(0o600)
