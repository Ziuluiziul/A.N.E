"""A CLI do quórum é exercitada sem rede nem credencial real."""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from providers.base import GenerationResult, ModelInfo, ProbeResult, ProviderAdapter
from providers.catalog import DiscoverySnapshot
from providers.inventory import build_inventory
from providers.registry import EndpointRegistry
from tools.run_quorum import main
from vault.promotion import CorpusPatch, verify_quorum
from vault.quorum import (
    CORPUS_PATCH_ALLOW_CREATE_KEY,
    CORPUS_PATCH_ALLOWED_TARGETS_KEY,
    PATCH_DIGEST_KEY,
    QuorumStore,
)
from vault.work.orchestrator import QuorumExecutionError, QuorumOrchestrator


def fake_inventory() -> object:
    entries = (
        ("groq", "alpha-4", "alpha"),
        ("groq", "beta-3", "beta"),
        ("nvidia", "gamma-2", "gamma"),
        ("nvidia", "delta-1", "delta"),
    )
    registry = EndpointRegistry()
    models: dict[str, list[ModelInfo]] = {}
    for provider, endpoint, family in entries:
        models.setdefault(provider, []).append(ModelInfo(provider, endpoint, family))
        registry.record_probe(ProbeResult(provider, endpoint, "ok", "ok", 1))
    snapshots = {
        provider: DiscoverySnapshot(Path(f"{provider}.json"), provider_models)
        for provider, provider_models in models.items()
    }
    return build_inventory(snapshots, registry)


class CliAdapter:
    def __init__(self, provider: str) -> None:
        self.provider = provider

    async def generate(
        self,
        endpoint_id: str,
        prompt: str,
        *,
        max_output_tokens: int = 256,
    ) -> GenerationResult:
        if "Você propõe uma alteração" in prompt:
            proposal_id = re.search(r"proposal_id exato: ([0-9a-f]+)", prompt)
            base_commit = re.search(r"base_commit exato: ([0-9a-f]+)", prompt)
            if proposal_id is not None and base_commit is not None:
                action = "replace" if "não autoriza criar nota" in prompt else "create"
                text = json.dumps(
                    {
                        "proposal_id": proposal_id.group(1),
                        "base_commit": base_commit.group(1),
                        "operations": [
                            {
                                "action": action,
                                "path": "Teste.md",
                                "content": "# Teste\n\nConteúdo integral.",
                            }
                        ],
                    }
                )
            else:
                text = "proposta final"
        else:
            decision = "revise" if "Você verifica forma" in prompt else "approve"
            action = "revise" if decision == "revise" else "promote"
            text = json.dumps(
                {
                    "decision": decision,
                    "confidence": 0.9,
                    "blocking_issues": [],
                    "non_blocking_issues": [],
                    "evidence": [],
                    "recommended_action": action,
                }
            )
        return GenerationResult(self.provider, endpoint_id, text, {"total_tokens": 8})


def settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        state_dir=tmp_path / "state",
        runtime_dir=tmp_path,
        models_dir=tmp_path / "modelos",
        corpus_dir=tmp_path / "repo" / "knowledge",
        work_max_calls=6,
        redact=lambda text: text,
    )


def patch_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configured = settings(tmp_path)
    inventory = fake_inventory()
    adapters = {
        provider: cast(ProviderAdapter, CliAdapter(provider)) for provider in ("groq", "nvidia")
    }
    monkeypatch.setattr("tools.run_quorum.get_settings", lambda: configured)
    monkeypatch.setattr("tools.run_quorum.load_all_snapshots", lambda _path: {})
    monkeypatch.setattr(
        "tools.run_quorum.build_inventory",
        lambda _snapshots, _registry: inventory,
    )
    monkeypatch.setattr("tools.run_quorum.build_adapters", lambda _settings: adapters)
    monkeypatch.setattr("tools.run_quorum.current_head", lambda _root: "d" * 40)


async def test_cli_executa_fluxo_e_imprime_acao(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    patch_runtime(monkeypatch, tmp_path)

    assert await main(["proponha algo pequeno"]) == 0

    output = capsys.readouterr().out
    assert "decisão: promote" in output
    assert "avaliadores:" in output
    ledger = json.loads((tmp_path / "state" / "quotas.json").read_text())
    endpoint_events = [key for key in ledger["events"] if "/" in key]
    assert len(endpoint_events) == 4
    decisions = list((tmp_path / "quorum").glob("*/decision.json"))
    assert len(decisions) == 1
    panel_dir = decisions[0].parent
    raw_patch = json.loads((panel_dir / "patch.json").read_text())
    patch = CorpusPatch.model_validate(raw_patch)
    task = json.loads((panel_dir / "task.json").read_text())
    assert task["task"]["context"][PATCH_DIGEST_KEY] == patch.digest()
    verify_quorum(QuorumStore(tmp_path / "quorum").load_panel(panel_dir.name), patch)
    assert "patch: Teste.md" in output
    assert f"make promote PAINEL={panel_dir.name}" in output


async def test_cli_preserva_quorum_generico_sem_patch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    patch_runtime(monkeypatch, tmp_path)

    assert await main(["--texto-livre", "avalie uma proposição textual"]) == 0

    output = capsys.readouterr().out
    assert "decisão: promote" in output
    assert "patch:" not in output
    assert list((tmp_path / "quorum").glob("*/patch.json")) == []


async def test_cli_persiste_ledger_mesmo_quando_fluxo_falha(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    patch_runtime(monkeypatch, tmp_path)

    async def fail_after_call(self: QuorumOrchestrator, _task: object) -> object:
        self.ledger.record_call(endpoint="groq/falhou", provider="groq", tokens=7)
        raise QuorumExecutionError("falha simulada")

    monkeypatch.setattr(QuorumOrchestrator, "run", fail_after_call)

    assert await main(["proponha algo pequeno"]) == 1

    assert "quórum não concluído: falha simulada" in capsys.readouterr().out
    ledger = json.loads((tmp_path / "state" / "quotas.json").read_text())
    assert "groq/falhou" in ledger["events"]
    assert "groq" in ledger["events"]


async def test_cli_trava_alvo_e_anexa_conteudo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    knowledge = tmp_path / "repo" / "knowledge"
    knowledge.mkdir(parents=True)
    (knowledge / "Teste.md").write_text("# Teste\n\nCanônico.\n", encoding="utf-8")
    patch_runtime(monkeypatch, tmp_path)

    assert await main(["--alvo", "Teste.md", "corrija só este alvo"]) == 0

    capsys.readouterr()
    task = json.loads(next((tmp_path / "quorum").glob("*/task.json")).read_text())
    contexto = task["task"]["context"]
    assert contexto[CORPUS_PATCH_ALLOWED_TARGETS_KEY] == ["Teste.md"]
    assert contexto[CORPUS_PATCH_ALLOW_CREATE_KEY] is False
    assert "CONTEÚDO CANÔNICO ATUAL de Teste.md" in task["task"]["prompt"]
    assert "Canônico." in task["task"]["prompt"]


def test_makefile_expoe_comando_quorum(repo_root: Path) -> None:
    makefile = (repo_root / "Makefile").read_text(encoding="utf-8")
    assert "quorum:" in makefile
    assert 'tools/run_quorum.py $(ARGS) "$(TAREFA)"' in makefile
