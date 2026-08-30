"""A sonda SSE compartilha a contabilidade persistente dos executores."""

from __future__ import annotations

import json
import time
from argparse import Namespace
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from providers.base import ProviderError
from providers.cognitive import CognitiveEvent, CognitiveKind
from tools.probe_streams import STREAM_ESTIMATED_TOKENS, principal
from vault.runtime_io import write_private_json


def _estado_anterior(state_dir: Path) -> tuple[list[object], dict[str, object]]:
    evento: list[object] = [time.time(), 7]
    write_private_json(state_dir / "quotas.json", {"events": {"legado": [evento]}})
    probe: dict[str, object] = {
        "provider": "legado",
        "endpoint": "modelo-anterior",
        "outcome": "ok",
        "stream_class": "final-only",
        "events": 1,
    }
    write_private_json(state_dir / "streams.json", {"probes": [probe]})
    return evento, probe


def _configurar(
    monkeypatch: pytest.MonkeyPatch,
    state_dir: Path,
    adapter: object,
    redact: Callable[[str], str] | None = None,
) -> None:
    settings = SimpleNamespace(state_dir=state_dir, redact=redact or (lambda text: text))
    monkeypatch.setattr("vault.config.get_settings", lambda: settings)
    monkeypatch.setattr(
        "tools.probe_streams.build_adapters",
        lambda _settings: {"fake": adapter},
    )


def _args(*, endpoint: str | None = "modelo", dry_run: bool = False) -> Namespace:
    return Namespace(provider="fake", endpoint=endpoint, dry_run=dry_run)


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


async def test_sucesso_conta_uma_chamada_e_preserva_eventos(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evento_anterior, probe_anterior = _estado_anterior(tmp_path)

    class Adapter:
        provider = "fake"
        calls = 0

        async def stream_generate(
            self,
            endpoint_id: str,
            _prompt: str,
            *,
            max_output_tokens: int,
        ) -> AsyncIterator[CognitiveEvent]:
            assert max_output_tokens > 0
            self.calls += 1
            yield CognitiveEvent(
                provider=self.provider,
                endpoint_id=endpoint_id,
                kind=CognitiveKind.FINAL,
                text="391",
                raw_field="final",
            )

    adapter = Adapter()
    _configurar(monkeypatch, tmp_path, adapter)

    assert await principal(_args()) == 0
    assert adapter.calls == 1

    ledger = _json(tmp_path / "quotas.json")
    events = ledger["events"]
    assert isinstance(events, dict)
    assert events["legado"] == [evento_anterior]
    assert len(events["fake/modelo"]) == 1
    assert len(events["fake"]) == 1
    assert events["fake/modelo"] == events["fake"]
    assert events["fake/modelo"][0][1] == STREAM_ESTIMATED_TOKENS

    report = _json(tmp_path / "streams.json")
    probes = report["probes"]
    assert isinstance(probes, list)
    assert probe_anterior in probes
    novo = next(item for item in probes if item["provider"] == "fake")
    assert novo["outcome"] == "ok"
    assert novo["stream_class"] == "final-only"


async def test_falha_conta_uma_chamada_e_preserva_eventos(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evento_anterior, probe_anterior = _estado_anterior(tmp_path)

    class Adapter:
        provider = "fake"
        calls = 0

        async def stream_generate(
            self,
            _endpoint_id: str,
            _prompt: str,
            *,
            max_output_tokens: int,
        ) -> AsyncIterator[CognitiveEvent]:
            assert max_output_tokens > 0
            self.calls += 1
            raise ProviderError("falha simulada")
            yield  # pragma: no cover — mantém o contrato de gerador assíncrono

    adapter = Adapter()
    _configurar(monkeypatch, tmp_path, adapter)

    assert await principal(_args()) == 1
    assert adapter.calls == 1

    ledger = _json(tmp_path / "quotas.json")
    events = ledger["events"]
    assert isinstance(events, dict)
    assert events["legado"] == [evento_anterior]
    assert len(events["fake/modelo"]) == 1
    assert len(events["fake"]) == 1
    assert events["fake/modelo"] == events["fake"]
    assert events["fake/modelo"][0][1] == STREAM_ESTIMATED_TOKENS

    report = _json(tmp_path / "streams.json")
    probes = report["probes"]
    assert isinstance(probes, list)
    assert probe_anterior in probes
    novo = next(item for item in probes if item["provider"] == "fake")
    assert novo["outcome"] == "ProviderError"
    assert novo["stream_class"] is None


@pytest.mark.parametrize(
    ("error", "outcome"),
    [
        pytest.param(ProviderError("falha com {secret}"), "ProviderError", id="provider"),
        pytest.param(
            RuntimeError("falha com {secret}"),
            "nao_classificado:RuntimeError",
            id="unexpected",
        ),
    ],
)
async def test_falha_redige_segredo_antes_de_imprimir_e_persistir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
    outcome: str,
) -> None:
    secret = "sk-or-v1-valor-que-nao-pode-vazar"
    error.args = (str(error).format(secret=secret),)

    class Adapter:
        provider = "fake"

        async def stream_generate(
            self,
            _endpoint_id: str,
            _prompt: str,
            *,
            max_output_tokens: int,
        ) -> AsyncIterator[CognitiveEvent]:
            assert max_output_tokens > 0
            raise error
            yield  # pragma: no cover

    _configurar(
        monkeypatch,
        tmp_path,
        Adapter(),
        redact=lambda text: text.replace(secret, "[REDACTED]"),
    )

    assert await principal(_args()) == 1
    output = capsys.readouterr().out
    report = (tmp_path / "streams.json").read_text(encoding="utf-8")
    assert secret not in output
    assert secret not in report
    assert "[REDACTED]" in output
    assert "[REDACTED]" in report
    probes = _json(tmp_path / "streams.json")["probes"]
    assert isinstance(probes, list)
    probe = probes[0]
    assert isinstance(probe, dict)
    assert probe["outcome"] == outcome
    assert probe["detail"] == "falha com [REDACTED]"


async def test_dry_run_nao_conta_nem_substitui_eventos(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _estado_anterior(tmp_path)

    class Adapter:
        provider = "fake"

        async def stream_generate(
            self,
            _endpoint_id: str,
            _prompt: str,
            *,
            max_output_tokens: int,
        ) -> AsyncIterator[CognitiveEvent]:
            raise AssertionError(f"dry-run abriu stream com teto {max_output_tokens}")
            yield  # pragma: no cover

    _configurar(monkeypatch, tmp_path, Adapter())
    quota_antes = (tmp_path / "quotas.json").read_bytes()
    streams_antes = (tmp_path / "streams.json").read_bytes()

    assert await principal(_args(dry_run=True)) == 0

    assert (tmp_path / "quotas.json").read_bytes() == quota_antes
    assert (tmp_path / "streams.json").read_bytes() == streams_antes


async def test_sem_endpoint_nao_conta_e_preserva_eventos(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evento_anterior, probe_anterior = _estado_anterior(tmp_path)

    class Adapter:
        provider = "fake"

    _configurar(monkeypatch, tmp_path, Adapter())

    assert await principal(_args(endpoint=None)) == 1

    ledger = _json(tmp_path / "quotas.json")
    assert ledger == {"events": {"legado": [evento_anterior]}}
    report = _json(tmp_path / "streams.json")
    assert report == {"probes": [probe_anterior]}
