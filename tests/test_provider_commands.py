"""As fronteiras de CLI classificam falhas sem traceback."""

from __future__ import annotations

import json
import stat
import time
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from providers.base import (
    ModelInfo,
    ObservedLimits,
    ProbeResult,
    ProviderAdapter,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimited,
    ProviderUnavailable,
)
from providers.catalog import DiscoverySnapshot, load_discovery_snapshot
from tools.discover_models import main as discover_main
from tools.smoke_providers import PROBE_ESTIMATED_TOKENS, smoke, sweep
from tools.smoke_providers import main as smoke_main
from tools.workspace_oauth import main as workspace_main
from vault.runtime_io import redact_json, write_private_json


class AdapterComErro:
    provider = "fake"

    async def probe_model(self, _endpoint_id: str) -> ProbeResult:
        raise ValueError("resposta inesperada segredo")

    def get_observed_limits(self) -> ObservedLimits:
        return ObservedLimits(provider=self.provider, source="desconhecido")


async def test_smoke_contem_erro_nao_classificado() -> None:
    snapshot = DiscoverySnapshot(
        path=Path("models-fake-2026.json"),
        models=[ModelInfo(provider="fake", endpoint_id="modelo", family="modelo")],
    )
    result = await smoke(
        "fake",
        cast(ProviderAdapter, AdapterComErro()),
        snapshot,
        redact=lambda text: text.replace("segredo", "[REDACTED]"),
    )
    assert result.probe is not None
    assert result.probe.outcome == "error"
    assert result.probe.detail == "ValueError: resposta inesperada [REDACTED]"


async def test_sweep_para_apos_primeiro_auth_provider_wide() -> None:
    snapshot = DiscoverySnapshot(
        path=Path("models-fake-2026.json"),
        models=[
            ModelInfo(provider="fake", endpoint_id=endpoint_id, family="modelo")
            for endpoint_id in ("modelo-a", "modelo-b")
        ],
    )
    calls: list[str] = []

    class Adapter:
        provider = "fake"

        async def probe_model(self, endpoint_id: str) -> ProbeResult:
            calls.append(endpoint_id)
            raise ProviderAuthError("credencial rejeitada")

        def get_observed_limits(self) -> ObservedLimits:
            return ObservedLimits(provider=self.provider, source="desconhecido")

    results = await sweep("fake", cast(ProviderAdapter, Adapter()), snapshot)

    assert len(calls) == 1
    assert len(results) == 1
    assert results[0].probe is not None
    assert results[0].probe.outcome == "auth"


async def test_sweep_continua_apos_falha_especifica_de_endpoint() -> None:
    snapshot = DiscoverySnapshot(
        path=Path("models-fake-2026.json"),
        models=[
            ModelInfo(provider="fake", endpoint_id=endpoint_id, family="modelo")
            for endpoint_id in ("modelo-a", "modelo-b")
        ],
    )
    calls: list[str] = []

    class Adapter:
        provider = "fake"

        async def probe_model(self, endpoint_id: str) -> ProbeResult:
            calls.append(endpoint_id)
            if len(calls) == 1:
                raise ProviderUnavailable("endpoint fora do plano")
            return ProbeResult(self.provider, endpoint_id, "ok", "ok")

        def get_observed_limits(self) -> ObservedLimits:
            return ObservedLimits(provider=self.provider, source="desconhecido")

    results = await sweep("fake", cast(ProviderAdapter, Adapter()), snapshot)

    assert len(calls) == 2
    assert [result.probe.outcome if result.probe else None for result in results] == [
        "unavailable",
        "ok",
    ]


async def test_smoke_grava_o_registro_e_muda_de_alvo_na_execucao_seguinte(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Duas execuções, duas chamadas, dois endpoints — sem retry dentro de uma delas."""
    snapshot = tmp_path / "models-nvidia-2026.json"
    write_private_json(
        snapshot,
        {
            "provider": "nvidia",
            "models": [
                {
                    "provider": "nvidia",
                    "endpoint_id": endpoint_id,
                    "family": "teste",
                    "available": True,
                }
                # Alfabeticamente `01-ai/yi-large` viria primeiro; ele é o endpoint que
                # a conta não serve. A sonda dirigida não deve tocá-lo.
                for endpoint_id in (
                    "01-ai/yi-large",
                    "baai/bge-m3",
                    "meta/llama-3.1-8b-instruct",
                    "meta/llama-3.3-70b-instruct",
                )
            ],
        },
    )
    write_private_json(
        tmp_path / "models-discovery.json",
        {"schema_version": 1, "status": "complete", "providers": {"nvidia": snapshot.name}},
    )

    sondados: list[str] = []

    class Adapter:
        provider = "nvidia"

        async def probe_model(self, endpoint_id: str) -> ProbeResult:
            sondados.append(endpoint_id)
            return ProbeResult(
                "nvidia", endpoint_id, "unavailable", "404", 5, "2026-08-03T00:00:00"
            )

        def get_observed_limits(self) -> ObservedLimits:
            return ObservedLimits(provider="nvidia", source="desconhecido")

    settings = SimpleNamespace(
        state_dir=tmp_path,
        logs_dir=tmp_path / "logs",
        redact=lambda text: text,
    )
    monkeypatch.setattr("tools.smoke_providers.get_settings", lambda: settings)
    monkeypatch.setattr(
        "tools.smoke_providers.build_adapters",
        lambda _s: {"nvidia": Adapter()},
    )

    assert await smoke_main([]) == 1
    assert await smoke_main([]) == 1

    assert sondados == ["meta/llama-3.3-70b-instruct", "meta/llama-3.1-8b-instruct"]
    registry = json.loads((tmp_path / "endpoints.json").read_text(encoding="utf-8"))
    assert set(registry["endpoints"]) == {
        "nvidia/meta/llama-3.3-70b-instruct",
        "nvidia/meta/llama-3.1-8b-instruct",
    }
    gravado = registry["endpoints"]["nvidia/meta/llama-3.3-70b-instruct"]
    assert gravado["observed_status"] == "unavailable"
    assert gravado["last_success"] is None


async def test_smoke_usa_retrato_e_faz_uma_unica_sonda() -> None:
    class Adapter:
        provider = "fake"

        def __init__(self) -> None:
            self.calls = 0

        async def list_models(self) -> list[object]:  # pragma: no cover
            raise AssertionError("o smoke repetiu a listagem")

        async def probe_model(self, endpoint_id: str) -> ProbeResult:
            self.calls += 1
            return ProbeResult("fake", endpoint_id, "ok", "ok", 1)

        def get_observed_limits(self) -> ObservedLimits:
            return ObservedLimits(provider=self.provider, source="desconhecido")

    adapter = Adapter()
    snapshot = DiscoverySnapshot(
        path=Path("models-fake-2026.json"),
        models=[
            ModelInfo(provider="fake", endpoint_id="embedding", family="embedding"),
            ModelInfo(provider="fake", endpoint_id="modelo-texto", family="modelo"),
        ],
    )
    result = await smoke("fake", cast(ProviderAdapter, adapter), snapshot)
    assert adapter.calls == 1
    assert result.probe is not None
    assert result.probe.endpoint_id == "modelo-texto"


async def test_smoke_redige_resposta_endpoint_e_headers() -> None:
    segredo = "gsk_" + "x" * 32

    class Adapter:
        provider = "fake"

        async def probe_model(self, endpoint_id: str) -> ProbeResult:
            return ProbeResult("fake", endpoint_id, "ok", f"resposta {segredo}", 1)

        def get_observed_limits(self) -> ObservedLimits:
            return ObservedLimits(
                provider="fake",
                source="headers",
                raw={f"x-ratelimit-{segredo}": segredo},
            )

    snapshot = DiscoverySnapshot(
        path=Path("models-fake-2026.json"),
        models=[ModelInfo(provider="fake", endpoint_id=segredo, family="modelo")],
    )
    result = await smoke(
        "fake",
        cast(ProviderAdapter, Adapter()),
        snapshot,
        redact=lambda text: text.replace(segredo, "[REDACTED]"),
    )
    serialized = json.dumps(result.to_dict())
    assert segredo not in serialized


def test_retrato_de_descoberta_e_validado(tmp_path: Path) -> None:
    path = tmp_path / "models-fake-2026-08-02T000000Z.json"
    write_private_json(
        path,
        {
            "provider": "fake",
            "models": [
                {
                    "provider": "fake",
                    "endpoint_id": "modelo",
                    "family": "modelo",
                    "available": True,
                }
            ],
        },
    )
    write_private_json(
        tmp_path / "models-discovery.json",
        {
            "schema_version": 1,
            "observed_at": "2026-08-02T000000Z",
            "status": "complete",
            "providers": {"fake": path.name},
        },
    )
    snapshot = load_discovery_snapshot(tmp_path, "fake")
    assert snapshot.path == path
    assert [model.endpoint_id for model in snapshot.models] == ["modelo"]


def test_json_de_runtime_e_privado_e_atomico(tmp_path: Path) -> None:
    path = tmp_path / "privado" / "evidencia.json"
    write_private_json(path, {"estado": "primeiro"})
    write_private_json(path, {"estado": "final"})
    assert json.loads(path.read_text(encoding="utf-8")) == {"estado": "final"}
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert list(path.parent.glob(f".{path.name}.*")) == []


def test_redacao_de_json_cobre_chaves_e_valores_aninhados() -> None:
    payload = {"segredo": [{"campo": "antes segredo depois"}]}
    assert redact_json(payload, lambda text: text.replace("segredo", "[REDACTED]")) == {
        "[REDACTED]": [{"campo": "antes [REDACTED] depois"}]
    }


async def test_descoberta_redige_metadados_antes_de_persistir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    segredo = "gsk_" + "x" * 32

    class Adapter:
        provider = "fake"

        async def list_models(self) -> list[ModelInfo]:
            return [
                ModelInfo(
                    provider="fake",
                    endpoint_id="modelo",
                    family="modelo",
                    raw={"externo": segredo},
                )
            ]

    settings = SimpleNamespace(
        state_dir=tmp_path,
        redact=lambda text: text.replace(segredo, "[REDACTED]"),
    )
    monkeypatch.setattr("tools.discover_models.get_settings", lambda: settings)
    monkeypatch.setattr(
        "tools.discover_models.build_adapters",
        lambda _settings: {"fake": Adapter()},
    )

    assert await discover_main([]) == 0
    snapshot = next(tmp_path.glob("models-fake-*.json"))
    assert segredo not in snapshot.read_text(encoding="utf-8")


async def test_descoberta_filtrada_toca_so_provedor_e_preserva_retratos_validos(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    previous_snapshot = tmp_path / "models-groq-anterior.json"
    write_private_json(
        previous_snapshot,
        {
            "provider": "groq",
            "models": [
                {
                    "provider": "groq",
                    "endpoint_id": "modelo-anterior",
                    "family": "modelo",
                    "available": True,
                }
            ],
        },
    )
    invalid_snapshot = tmp_path / "models-invalido.json"
    write_private_json(invalid_snapshot, {"provider": "outro", "models": []})
    write_private_json(
        tmp_path / "models-discovery.json",
        {
            "schema_version": 1,
            "observed_at": "2026-08-10T000000Z",
            "status": "complete",
            "providers": {
                "groq": previous_snapshot.name,
                "invalido": invalid_snapshot.name,
            },
        },
    )
    previous_bytes = previous_snapshot.read_bytes()
    calls = {"groq": 0, "openrouter": 0}

    class Adapter:
        def __init__(self, provider: str) -> None:
            self.provider = provider

        async def list_models(self) -> list[ModelInfo]:
            calls[self.provider] += 1
            return [ModelInfo(self.provider, "modelo-novo", "modelo")]

    settings = SimpleNamespace(state_dir=tmp_path, redact=lambda text: text)
    adapters = {provider: Adapter(provider) for provider in calls}
    monkeypatch.setattr("tools.discover_models.get_settings", lambda: settings)
    monkeypatch.setattr("tools.discover_models.build_adapters", lambda _settings: adapters)

    assert await discover_main(["--provider", "openrouter"]) == 0
    assert calls == {"groq": 0, "openrouter": 1}
    assert previous_snapshot.read_bytes() == previous_bytes

    manifest = json.loads((tmp_path / "models-discovery.json").read_text())
    assert manifest["status"] == "complete"
    assert manifest["providers"]["groq"] == previous_snapshot.name
    assert "invalido" not in manifest["providers"]
    new_name = manifest["providers"]["openrouter"]
    assert new_name.startswith("models-openrouter-")
    assert load_discovery_snapshot(tmp_path, "openrouter").models[0].endpoint_id == (
        "modelo-novo"
    )


async def test_descoberta_filtrada_recusa_provedor_ausente_sem_alterar_manifesto(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifest_path = tmp_path / "models-discovery.json"
    write_private_json(
        manifest_path,
        {"schema_version": 1, "status": "complete", "providers": {}},
    )
    previous_bytes = manifest_path.read_bytes()
    calls = 0

    class Adapter:
        provider = "groq"

        async def list_models(self) -> list[ModelInfo]:
            nonlocal calls
            calls += 1
            return []

    settings = SimpleNamespace(state_dir=tmp_path, redact=lambda text: text)
    monkeypatch.setattr("tools.discover_models.get_settings", lambda: settings)
    monkeypatch.setattr(
        "tools.discover_models.build_adapters", lambda _settings: {"groq": Adapter()}
    )

    assert await discover_main(["--provider", "openrouter"]) == 1
    assert calls == 0
    assert manifest_path.read_bytes() == previous_bytes
    assert capsys.readouterr().out == "sem credencial para openrouter (há: groq)\n"


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ProviderError("falha do provedor"), id="provider-error"),
        pytest.param(
            ProviderRateLimited("limite do provedor", retry_after_s=7.0),
            id="rate-limit",
        ),
        pytest.param(RuntimeError("falha inesperada"), id="unexpected-error"),
    ],
)
async def test_descoberta_filtrada_preserva_inventario_em_qualquer_falha(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    snapshots: list[Path] = []
    providers: dict[str, str] = {}
    for provider in ("groq", "openrouter"):
        snapshot = tmp_path / f"models-{provider}-anterior.json"
        write_private_json(
            snapshot,
            {
                "provider": provider,
                "models": [
                    {
                        "provider": provider,
                        "endpoint_id": f"{provider}/modelo-anterior",
                        "family": "modelo",
                        "available": True,
                    }
                ],
            },
        )
        snapshots.append(snapshot)
        providers[provider] = snapshot.name

    manifest_path = tmp_path / "models-discovery.json"
    write_private_json(
        manifest_path,
        {
            "schema_version": 1,
            "observed_at": "2026-08-10T000000Z",
            "status": "complete",
            "providers": providers,
        },
    )
    manifest_before = manifest_path.read_bytes()
    snapshots_before = {path: path.read_bytes() for path in snapshots}

    class Adapter:
        provider = "openrouter"

        async def list_models(self) -> list[ModelInfo]:
            raise error

        def get_observed_limits(self) -> ObservedLimits:
            return ObservedLimits(
                provider=self.provider,
                source="resposta",
                retry_after_s=7.0,
            )

    settings = SimpleNamespace(state_dir=tmp_path, redact=lambda text: text)
    monkeypatch.setattr("tools.discover_models.get_settings", lambda: settings)
    monkeypatch.setattr(
        "tools.discover_models.build_adapters",
        lambda _settings: {"openrouter": Adapter()},
    )

    assert await discover_main(["--provider", "openrouter"]) == 1
    assert manifest_path.read_bytes() == manifest_before
    assert {path: path.read_bytes() for path in snapshots} == snapshots_before
    assert sorted(tmp_path.glob("models-*.json")) == sorted([manifest_path, *snapshots])


async def test_429_na_descoberta_interrompe_provedores_seguintes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"google": 0, "groq": 0, "nvidia": 0}

    class Adapter:
        def __init__(self, provider: str) -> None:
            self.provider = provider

        async def list_models(self) -> list[ModelInfo]:
            calls[self.provider] += 1
            if self.provider == "groq":
                raise ProviderRateLimited("limite", 7.0)
            return [ModelInfo(self.provider, "modelo", "modelo")]

        def get_observed_limits(self) -> ObservedLimits:
            return ObservedLimits(
                provider=self.provider,
                source="resposta",
                retry_after_s=7.0,
                raw={"retry-after": "7"},
            )

    settings = SimpleNamespace(state_dir=tmp_path, redact=lambda text: text)
    adapters = {provider: Adapter(provider) for provider in calls}
    monkeypatch.setattr("tools.discover_models.get_settings", lambda: settings)
    monkeypatch.setattr("tools.discover_models.build_adapters", lambda _settings: adapters)

    assert await discover_main([]) == 1
    assert calls == {"google": 1, "groq": 1, "nvidia": 0}
    manifest = json.loads((tmp_path / "models-discovery.json").read_text())
    assert manifest["status"] == "rate_limited"
    assert manifest["failed_provider"] == "groq"
    assert manifest["rate_limit"]["retry_after_s"] == 7.0
    assert manifest["rate_limit"]["raw"] == {"retry-after": "7"}


async def test_smoke_filtrado_sonda_um_endpoint_so_do_provedor_pedido(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    providers = ("groq", "openrouter")
    manifest: dict[str, str] = {}
    for provider in providers:
        snapshot = tmp_path / f"models-{provider}-2026.json"
        write_private_json(
            snapshot,
            {
                "provider": provider,
                "models": [
                    {
                        "provider": provider,
                        "endpoint_id": f"autor/modelo-{index}",
                        "family": "modelo",
                        "available": True,
                    }
                    for index in range(2)
                ],
            },
        )
        manifest[provider] = snapshot.name
    write_private_json(
        tmp_path / "models-discovery.json",
        {"schema_version": 1, "status": "complete", "providers": manifest},
    )
    previous_at = time.time()
    write_private_json(
        tmp_path / "quotas.json",
        {"events": {"google/existente": [[previous_at, 3]], "google": [[previous_at, 3]]}},
    )
    calls: dict[str, list[str]] = {provider: [] for provider in providers}

    class Adapter:
        def __init__(self, provider: str) -> None:
            self.provider = provider

        async def probe_model(self, endpoint_id: str) -> ProbeResult:
            calls[self.provider].append(endpoint_id)
            return ProbeResult(self.provider, endpoint_id, "ok", "ok", 1)

        def get_observed_limits(self) -> ObservedLimits:
            return ObservedLimits(provider=self.provider, source="desconhecido")

    settings = SimpleNamespace(
        state_dir=tmp_path,
        logs_dir=tmp_path / "logs",
        redact=lambda text: text,
    )
    adapters = {provider: Adapter(provider) for provider in providers}
    monkeypatch.setattr("tools.smoke_providers.get_settings", lambda: settings)
    monkeypatch.setattr("tools.smoke_providers.build_adapters", lambda _settings: adapters)

    assert await smoke_main(["--provider", "openrouter"]) == 0
    assert calls["groq"] == []
    assert len(calls["openrouter"]) == 1
    log = json.loads((settings.logs_dir / "smoke-providers.json").read_text())
    assert [item["provider"] for item in log] == ["openrouter"]
    ledger = json.loads((tmp_path / "quotas.json").read_text())
    endpoint_scope = f"openrouter/{calls['openrouter'][0]}"
    assert ledger["events"]["google/existente"] == [[previous_at, 3]]
    assert ledger["events"]["google"] == [[previous_at, 3]]
    assert len(ledger["events"][endpoint_scope]) == 1
    assert len(ledger["events"]["openrouter"]) == 1
    assert ledger["events"][endpoint_scope][0] == ledger["events"]["openrouter"][0]
    assert ledger["events"][endpoint_scope][0][1] == PROBE_ESTIMATED_TOKENS


async def test_smoke_contabiliza_tentativa_que_falha(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = tmp_path / "models-openrouter-2026.json"
    write_private_json(
        snapshot,
        {
            "provider": "openrouter",
            "models": [
                {
                    "provider": "openrouter",
                    "endpoint_id": "autor/modelo:free",
                    "family": "modelo",
                    "available": True,
                }
            ],
        },
    )
    write_private_json(
        tmp_path / "models-discovery.json",
        {
            "schema_version": 1,
            "status": "complete",
            "providers": {"openrouter": snapshot.name},
        },
    )

    class Adapter:
        provider = "openrouter"

        async def probe_model(self, _endpoint_id: str) -> ProbeResult:
            raise ValueError("falha depois de abrir a tentativa")

        def get_observed_limits(self) -> ObservedLimits:
            return ObservedLimits(provider=self.provider, source="desconhecido")

    settings = SimpleNamespace(
        state_dir=tmp_path,
        logs_dir=tmp_path / "logs",
        redact=lambda text: text,
    )
    monkeypatch.setattr("tools.smoke_providers.get_settings", lambda: settings)
    monkeypatch.setattr(
        "tools.smoke_providers.build_adapters",
        lambda _settings: {"openrouter": Adapter()},
    )

    assert await smoke_main(["--provider", "openrouter"]) == 1
    ledger = json.loads((tmp_path / "quotas.json").read_text())
    assert len(ledger["events"]["openrouter/autor/modelo:free"]) == 1
    assert len(ledger["events"]["openrouter"]) == 1
    assert ledger["events"]["openrouter/autor/modelo:free"][0][1] == PROBE_ESTIMATED_TOKENS


async def test_smoke_sem_sonda_nao_altera_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = tmp_path / "models-openrouter-2026.json"
    write_private_json(
        snapshot,
        {
            "provider": "openrouter",
            "models": [
                {
                    "provider": "openrouter",
                    "endpoint_id": "autor/embedding:free",
                    "family": "embedding",
                    "available": True,
                }
            ],
        },
    )
    write_private_json(
        tmp_path / "models-discovery.json",
        {
            "schema_version": 1,
            "status": "complete",
            "providers": {"openrouter": snapshot.name},
        },
    )
    ledger_path = tmp_path / "quotas.json"
    write_private_json(
        ledger_path,
        {"events": {"google": [[time.time(), 0]]}},
    )
    previous_bytes = ledger_path.read_bytes()

    class Adapter:
        provider = "openrouter"

        async def probe_model(self, _endpoint_id: str) -> ProbeResult:
            raise AssertionError("não há endpoint elegível para sondar")

        def get_observed_limits(self) -> ObservedLimits:
            return ObservedLimits(provider=self.provider, source="desconhecido")

    settings = SimpleNamespace(
        state_dir=tmp_path,
        logs_dir=tmp_path / "logs",
        redact=lambda text: text,
    )
    monkeypatch.setattr("tools.smoke_providers.get_settings", lambda: settings)
    monkeypatch.setattr(
        "tools.smoke_providers.build_adapters",
        lambda _settings: {"openrouter": Adapter()},
    )

    assert await smoke_main(["--provider", "openrouter"]) == 1
    assert ledger_path.read_bytes() == previous_bytes


async def test_smoke_filtrado_recusa_provedor_ausente_antes_de_ler_manifesto(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = 0

    class Adapter:
        provider = "groq"

        async def probe_model(self, endpoint_id: str) -> ProbeResult:
            nonlocal calls
            calls += 1
            return ProbeResult(self.provider, endpoint_id, "ok", "ok", 1)

        def get_observed_limits(self) -> ObservedLimits:
            return ObservedLimits(provider=self.provider, source="desconhecido")

    settings = SimpleNamespace(
        state_dir=tmp_path,
        logs_dir=tmp_path / "logs",
        redact=lambda text: text,
    )
    monkeypatch.setattr("tools.smoke_providers.get_settings", lambda: settings)
    monkeypatch.setattr(
        "tools.smoke_providers.build_adapters", lambda _settings: {"groq": Adapter()}
    )

    assert await smoke_main(["--provider", "openrouter"]) == 1
    assert calls == 0
    assert not settings.logs_dir.exists()
    assert capsys.readouterr().out == "sem credencial para openrouter (há: groq)\n"


async def test_429_interrompe_as_sondas_seguintes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    providers = ("google", "groq", "nvidia")
    manifest: dict[str, str] = {}
    for provider in providers:
        snapshot = tmp_path / f"models-{provider}-2026.json"
        write_private_json(
            snapshot,
            {
                "provider": provider,
                "models": [
                    {
                        "provider": provider,
                        "endpoint_id": "modelo-texto",
                        "family": "modelo",
                        "available": True,
                    }
                ],
            },
        )
        manifest[provider] = snapshot.name
    write_private_json(
        tmp_path / "models-discovery.json",
        {
            "schema_version": 1,
            "status": "complete",
            "providers": manifest,
        },
    )

    calls = dict.fromkeys(providers, 0)

    class Adapter:
        def __init__(self, provider: str) -> None:
            self.provider = provider

        async def probe_model(self, endpoint_id: str) -> ProbeResult:
            calls[self.provider] += 1
            outcome = "rate_limited" if self.provider == "google" else "ok"
            return ProbeResult(self.provider, endpoint_id, outcome, "retry-after=7")

        def get_observed_limits(self) -> ObservedLimits:
            return ObservedLimits(
                provider=self.provider,
                source="resposta",
                retry_after_s=7.0 if self.provider == "google" else None,
            )

    adapters = {provider: Adapter(provider) for provider in providers}
    settings = SimpleNamespace(
        state_dir=tmp_path,
        logs_dir=tmp_path / "logs",
        redact=lambda text: text,
    )
    monkeypatch.setattr("tools.smoke_providers.get_settings", lambda: settings)
    monkeypatch.setattr("tools.smoke_providers.build_adapters", lambda _settings: adapters)

    assert await smoke_main([]) == 1
    assert calls == {"google": 1, "groq": 0, "nvidia": 0}
    log = settings.logs_dir / "smoke-providers.json"
    assert stat.S_IMODE(log.stat().st_mode) == 0o600
    payload = json.loads(log.read_text(encoding="utf-8"))
    assert payload[1]["listing"] == "não executado: ciclo interrompido após 429"


def test_workspace_oauth_contem_falha_sem_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret = tmp_path / "credentials.json"
    secret.write_text("{}", encoding="utf-8")
    settings = SimpleNamespace(
        google_workspace_client_secret_file=secret,
        google_workspace_token_file=tmp_path / "token.json",
    )

    class ClientComErro:
        def __init__(self, *_args, **_kwargs) -> None:
            raise RuntimeError("consentimento recusado\nsem detalhes adicionais")

    monkeypatch.setattr("tools.workspace_oauth.get_settings", lambda: settings)
    monkeypatch.setattr("tools.workspace_oauth.WorkspaceClient", ClientComErro)

    assert workspace_main() == 1
    output = capsys.readouterr().out
    assert output == (
        "workspace .. RuntimeError: consentimento recusado sem detalhes adicionais\n"
    )
    assert "Traceback" not in output
