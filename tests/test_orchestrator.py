"""O orquestrador erra caro: cota gasta não volta e monopólio falseia quórum."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, cast

import pytest

import vault.work.orchestrator as orchestrator_module
from providers.base import (
    GenerationResult,
    ModelInfo,
    ObservedLimits,
    ProbeResult,
    ProviderAccountExhausted,
    ProviderAdapter,
    ProviderAuthError,
    ProviderRateLimited,
    ProviderUnavailable,
)
from providers.catalog import DiscoverySnapshot
from providers.cognitive import CognitiveEvent, CognitiveKind
from providers.inventory import build_inventory
from providers.registry import EndpointRegistry
from vault.work.call_gate import ProviderCallGate
from vault.work.orchestrator import estimate_tokens, execute, plan_batch
from vault.work.quotas import EndpointLimits, QuotaLedger, RunBudget
from vault.work.store import UnsafeEndpointPath, WorkStore, endpoint_directory
from vault.work.tasks import Task


def snapshot(provider: str, *endpoint_ids: str) -> DiscoverySnapshot:
    return DiscoverySnapshot(
        path=Path(f"models-{provider}-2026.json"),
        models=[
            ModelInfo(
                provider=provider,
                endpoint_id=endpoint_id,
                family=endpoint_id.split("/")[-1].split("-")[0],
                available=True,
                context_window=131072,
            )
            for endpoint_id in endpoint_ids
        ],
    )


def confirmado(
    *keys: tuple[str, str],
    limits: ObservedLimits | None = None,
) -> EndpointRegistry:
    registry = EndpointRegistry()
    for provider, endpoint_id in keys:
        registry.record_probe(ProbeResult(provider, endpoint_id, "ok", "ok", 1), limits)
    return registry


def tarefa(prompt: str = "pergunta") -> Task:
    return Task(kind="teste", role_name="proponente", prompt=prompt, max_output_tokens=64)


def test_voto_de_nota_grande_cabe_no_teto_do_prompt() -> None:
    texto = "x" * 34_000
    criado = Task(kind="voto", role_name="revisor-estrutural", prompt=texto)
    assert len(criado.prompt) == 34_000


def test_so_endpoint_comprovado_recebe_trabalho() -> None:
    """Aptidão pelo nome não basta, e `reachable` também não."""
    registry = EndpointRegistry()
    registry.record_probe(ProbeResult("google", "gemini-3.6-flash", "reachable", "vazio", 1))
    inventory = build_inventory(
        {
            "google": snapshot("google", "gemini-3.6-flash"),
            "groq": snapshot("groq", "qwen/qwen3.6-27b"),
        },
        registry,
    )

    plan = plan_batch([tarefa()], inventory, QuotaLedger(), RunBudget(max_calls=10))
    assert plan.assignments == []
    assert "nenhum endpoint produziu texto" in plan.refusals[0].reason


def test_lote_distribui_entre_provedores_antes_de_repetir_um() -> None:
    """Painel formado só de um provedor concordaria consigo mesmo."""
    inventory = build_inventory(
        {
            "groq": snapshot("groq", "qwen/qwen3.6-27b", "llama-3.3-70b-versatile"),
            "nvidia": snapshot("nvidia", "z-ai/glm-5.2"),
        },
        confirmado(
            ("groq", "qwen/qwen3.6-27b"),
            ("groq", "llama-3.3-70b-versatile"),
            ("nvidia", "z-ai/glm-5.2"),
        ),
    )

    plan = plan_batch(
        [tarefa("a"), tarefa("b"), tarefa("c")],
        inventory,
        QuotaLedger(),
        RunBudget(max_calls=10),
    )
    provedores = [assignment.provider for assignment in plan.assignments]
    assert len(plan.assignments) == 3
    # Os dois primeiros são de provedores distintos: só o terceiro repete, porque aí
    # não há mais provedor sem tarefa.
    assert provedores[0] != provedores[1]
    assert set(provedores) == {"groq", "nvidia"}
    assert provedores.count("nvidia") == 1

    # E a repetição escolhe outra família, não o mesmo modelo de novo.
    familias = [assignment.endpoint_id for assignment in plan.assignments]
    assert len(set(familias)) == 3


def test_orcamento_da_execucao_corta_o_lote() -> None:
    """O teto do mantenedor vale mesmo quando o provedor permitiria mais."""
    inventory = build_inventory(
        {"groq": snapshot("groq", "qwen/qwen3.6-27b")},
        confirmado(("groq", "qwen/qwen3.6-27b")),
    )
    plan = plan_batch(
        [tarefa("a"), tarefa("b"), tarefa("c")],
        inventory,
        QuotaLedger(),
        RunBudget(max_calls=2),
    )
    assert len(plan.assignments) == 2
    assert "orçamento da execução" in plan.refusals[0].reason


def test_planejar_nao_consome_cota_de_verdade() -> None:
    """Plano é intenção; só chamada gasta. Um dry-run não pode encarecer o próximo."""
    ledger = QuotaLedger()
    inventory = build_inventory(
        {"groq": snapshot("groq", "qwen/qwen3.6-27b")},
        confirmado(("groq", "qwen/qwen3.6-27b")),
    )
    plan_batch([tarefa()], inventory, ledger, RunBudget(max_calls=5))
    assert ledger.events == {}
    assert ledger.run_calls == 0


def test_teto_observado_do_endpoint_impede_a_atribuicao() -> None:
    limites = ObservedLimits(provider="groq", source="headers", requests_per_day=1)
    inventory = build_inventory(
        {"groq": snapshot("groq", "qwen/qwen3.6-27b")},
        confirmado(("groq", "qwen/qwen3.6-27b"), limits=limites),
    )
    ledger = QuotaLedger()
    ledger.record("groq/qwen/qwen3.6-27b", tokens=10)

    plan = plan_batch([tarefa()], inventory, ledger, RunBudget(max_calls=5))
    assert plan.assignments == []
    assert "req/dia" in plan.refusals[0].reason


async def test_falha_tira_o_endpoint_do_lote_sem_virar_retry() -> None:
    """Insistir no mesmo endpoint gastaria a cota que os outros ainda vão usar."""
    chamadas: list[str] = []

    class Adapter:
        provider = "groq"

        async def generate(
            self, endpoint_id: str, prompt: str, *, max_output_tokens: int = 256
        ) -> GenerationResult:
            chamadas.append(endpoint_id)
            raise ProviderUnavailable("503")

    inventory = build_inventory(
        {"groq": snapshot("groq", "qwen/qwen3.6-27b")},
        confirmado(("groq", "qwen/qwen3.6-27b")),
    )
    ledger = QuotaLedger()
    plan = plan_batch([tarefa("a"), tarefa("b")], inventory, ledger, RunBudget(max_calls=5))
    assert len(plan.assignments) == 2

    results = await execute(plan, {"groq": cast(ProviderAdapter, Adapter())}, ledger)
    assert chamadas == ["qwen/qwen3.6-27b"]
    assert [result.outcome for result in results] == ["unavailable", "skipped"]
    assert "não se insiste" in results[1].detail


async def test_falha_de_provedor_consome_cota_mesmo_assim() -> None:
    """429 gastou requisição. Não contar faria a execução seguinte estourar de novo."""

    class Adapter:
        provider = "groq"

        async def generate(
            self, endpoint_id: str, prompt: str, *, max_output_tokens: int = 256
        ) -> GenerationResult:
            raise ProviderRateLimited("limite", 7.0)

    inventory = build_inventory(
        {"groq": snapshot("groq", "qwen/qwen3.6-27b")},
        confirmado(("groq", "qwen/qwen3.6-27b")),
    )
    ledger = QuotaLedger()
    plan = plan_batch([tarefa()], inventory, ledger, RunBudget(max_calls=5))
    await execute(plan, {"groq": cast(ProviderAdapter, Adapter())}, ledger)

    # Uma chamada externa é um número no orçamento, mesmo contabilizada em dois
    # escopos: contar dois faria o teto do mantenedor valer metade.
    assert ledger.run_calls == 1
    assert "groq/qwen/qwen3.6-27b" in ledger.events
    assert "groq" in ledger.events


async def test_falha_de_conta_suspende_o_provedor_e_pula_a_proxima() -> None:
    chamadas: list[str] = []

    class Adapter:
        provider = "google"

        async def generate(
            self, endpoint_id: str, prompt: str, *, max_output_tokens: int = 256
        ) -> GenerationResult:
            chamadas.append(endpoint_id)
            raise ProviderAccountExhausted("crédito da conta Google esgotado")

    inventory = build_inventory(
        {"google": snapshot("google", "gemini-3.6-flash")},
        confirmado(("google", "gemini-3.6-flash")),
    )
    ledger = QuotaLedger()
    gate = ProviderCallGate({"google": 1})
    adapter = cast(ProviderAdapter, Adapter())
    first = plan_batch([tarefa()], inventory, ledger, RunBudget(max_calls=5))
    results = await execute(first, {"google": adapter}, ledger, gate=gate)

    assert results[0].outcome == "account_exhausted"
    assert gate.suspended("google")
    assert chamadas == ["gemini-3.6-flash"]

    second = plan_batch([tarefa("outra")], inventory, ledger, RunBudget(max_calls=5))
    skipped = await execute(second, {"google": adapter}, ledger, gate=gate)
    assert skipped[0].outcome == "skipped"
    assert "falha de conta" in skipped[0].detail
    assert chamadas == ["gemini-3.6-flash"]


async def test_byok_impossivel_suspende_o_openrouter_e_pula_a_proxima() -> None:
    chamadas: list[str] = []

    class Adapter:
        provider = "openrouter"

        async def generate(
            self, endpoint_id: str, prompt: str, *, max_output_tokens: int = 256
        ) -> GenerationResult:
            chamadas.append(endpoint_id)
            raise ProviderAuthError(
                "a chave precisa incluir uso BYOK no teto de gasto USD 0"
            )

    inventory = build_inventory(
        {"openrouter": snapshot("openrouter", "nvidia/nemotron-3.5-lightning:free")},
        confirmado(("openrouter", "nvidia/nemotron-3.5-lightning:free")),
    )
    ledger = QuotaLedger()
    gate = ProviderCallGate({"openrouter": 1})
    adapter = cast(ProviderAdapter, Adapter())
    first = plan_batch([tarefa()], inventory, ledger, RunBudget(max_calls=5))
    results = await execute(first, {"openrouter": adapter}, ledger, gate=gate)

    assert results[0].outcome == "auth"
    assert gate.suspended("openrouter")
    assert chamadas == ["nvidia/nemotron-3.5-lightning:free"]

    second = plan_batch([tarefa("outra")], inventory, ledger, RunBudget(max_calls=5))
    skipped = await execute(second, {"openrouter": adapter}, ledger, gate=gate)
    assert skipped[0].outcome == "skipped"
    assert "falha de conta" in skipped[0].detail
    assert chamadas == ["nvidia/nemotron-3.5-lightning:free"]


async def test_chamada_presa_ganha_fechamento_no_prazo_declarado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Adapter:
        provider = "groq"

        async def generate(
            self, endpoint_id: str, prompt: str, *, max_output_tokens: int = 256
        ) -> GenerationResult:
            await asyncio.Event().wait()
            raise AssertionError("inalcançável")

    monkeypatch.setattr(orchestrator_module, "CALL_DEADLINE_SECONDS", 0.01)
    inventory = build_inventory(
        {"groq": snapshot("groq", "qwen/qwen3.6-27b")},
        confirmado(("groq", "qwen/qwen3.6-27b")),
    )
    ledger = QuotaLedger()
    plan = plan_batch([tarefa()], inventory, ledger, RunBudget(max_calls=1))

    results = await execute(plan, {"groq": cast(ProviderAdapter, Adapter())}, ledger)

    assert results[0].outcome == "unavailable"
    assert "prazo total declarado" in results[0].detail
    assert ledger.run_calls == 1


async def test_resposta_vazia_no_trabalho_tambem_e_alcance() -> None:
    class Adapter:
        provider = "groq"

        async def generate(
            self, endpoint_id: str, prompt: str, *, max_output_tokens: int = 256
        ) -> GenerationResult:
            return GenerationResult(provider="groq", endpoint_id=endpoint_id, text="   ")

    inventory = build_inventory(
        {"groq": snapshot("groq", "qwen/qwen3.6-27b")},
        confirmado(("groq", "qwen/qwen3.6-27b")),
    )
    ledger = QuotaLedger()
    plan = plan_batch([tarefa()], inventory, ledger, RunBudget(max_calls=5))
    results = await execute(plan, {"groq": cast(ProviderAdapter, Adapter())}, ledger)

    assert results[0].outcome == "reachable"
    assert not results[0].ok


async def test_o_papel_chega_ao_modelo() -> None:
    """Sem a instrução do papel, o modelo devolve exatamente o que o corpus recusa."""
    recebidos: list[str] = []

    class Adapter:
        provider = "groq"

        async def generate(
            self, endpoint_id: str, prompt: str, *, max_output_tokens: int = 256
        ) -> GenerationResult:
            recebidos.append(prompt)
            return GenerationResult(provider="groq", endpoint_id=endpoint_id, text="ok")

    inventory = build_inventory(
        {"groq": snapshot("groq", "qwen/qwen3.6-27b")},
        confirmado(("groq", "qwen/qwen3.6-27b")),
    )
    task = Task(kind="t", role_name="critico-epistemologico", prompt="avalie isto")
    plan = plan_batch([task], inventory, QuotaLedger(), RunBudget(max_calls=5))
    await execute(plan, {"groq": cast(ProviderAdapter, Adapter())}, QuotaLedger())

    assert "força epistêmica" in recebidos[0]
    assert "nunca é refutação" in recebidos[0]
    assert recebidos[0].endswith("avalie isto")


def test_ledger_respeita_janela_e_diz_qual_teto_bloqueou() -> None:
    ledger = QuotaLedger()
    limites = EndpointLimits(requests_per_minute=2, source="headers")
    agora = 1_000_000.0

    ledger.record("groq/x", now=agora)
    ledger.record("groq/x", now=agora)
    bloqueio = ledger.allows("groq/x", limites, now=agora)
    assert not bloqueio
    assert "req/min" in bloqueio.reason

    # Um minuto depois a janela deslizou e a mesma chamada passa.
    assert ledger.allows("groq/x", limites, now=agora + 61)


def test_caminho_de_endpoint_nao_escapa_da_raiz(tmp_path: Path) -> None:
    assert endpoint_directory(tmp_path, "groq", "meta/llama-3.3-70b").is_relative_to(tmp_path)
    # Nome com tag da Ollama é legítimo e precisa passar: recusá-lo derrubava o quórum
    # inteiro antes da primeira chamada, com um erro que parecia de segurança.
    assert endpoint_directory(tmp_path, "ollama", "gemma4:31b").is_relative_to(tmp_path)
    for maldoso in ("../fora", "/etc/passwd", "..", "a/../../fora", ":oculto"):
        try:
            endpoint_directory(tmp_path, "groq", maldoso)
        except UnsafeEndpointPath:
            continue
        raise AssertionError(f"aceitou caminho inseguro: {maldoso}")


async def test_store_separa_trabalho_de_falha_e_acumula_log(tmp_path: Path) -> None:
    class Adapter:
        provider = "groq"

        def __init__(self) -> None:
            self.calls = 0

        async def generate(
            self, endpoint_id: str, prompt: str, *, max_output_tokens: int = 256
        ) -> GenerationResult:
            self.calls += 1
            return GenerationResult(provider="groq", endpoint_id=endpoint_id, text="resposta")

    inventory = build_inventory(
        {"groq": snapshot("groq", "qwen/qwen3.6-27b")},
        confirmado(("groq", "qwen/qwen3.6-27b")),
    )
    store = WorkStore(root=tmp_path)
    ledger = QuotaLedger()

    for _ in range(2):
        plan = plan_batch([tarefa()], inventory, ledger, RunBudget(max_calls=9))
        results = await execute(plan, {"groq": cast(ProviderAdapter, Adapter())}, ledger)
        for result in results:
            store.record(result)

    directory = endpoint_directory(tmp_path, "groq", "qwen/qwen3.6-27b")
    assert len(list((directory / "trabalho").glob("*.json"))) == 2
    assert len(list((directory / "entrada").glob("*.json"))) == 2
    assert not (directory / "falhas").exists()

    eventos = store.history("groq", "qwen/qwen3.6-27b")
    assert len(eventos) == 2
    assert {evento["outcome"] for evento in eventos} == {"ok"}


async def test_execucao_e_store_descartam_raciocinio_interno(tmp_path: Path) -> None:
    class Adapter:
        provider = "groq"

        async def generate(
            self, endpoint_id: str, prompt: str, *, max_output_tokens: int = 256
        ) -> GenerationResult:
            del prompt, max_output_tokens
            return GenerationResult(
                provider="groq",
                endpoint_id=endpoint_id,
                text="<think>não persista</think> conclusão verificável",
            )

    inventory = build_inventory(
        {"groq": snapshot("groq", "qwen/qwen3.6-27b")},
        confirmado(("groq", "qwen/qwen3.6-27b")),
    )
    ledger = QuotaLedger()
    plan = plan_batch([tarefa()], inventory, ledger, RunBudget(max_calls=1))

    results = await execute(
        plan,
        {"groq": cast(ProviderAdapter, Adapter())},
        ledger,
    )
    destination = WorkStore(tmp_path).record(results[0])

    assert results[0].text == "conclusão verificável"
    assert destination is not None
    persisted = destination.read_text(encoding="utf-8")
    assert "não persista" not in persisted
    assert "<think>" not in persisted


def test_tarefa_recusada_nao_suja_historico_de_endpoint(tmp_path: Path) -> None:
    """Recusa de cota não é falha do modelo e não entra na pasta dele."""
    from vault.work.tasks import Assignment, WorkResult

    store = WorkStore(root=tmp_path)
    resultado = WorkResult(
        assignment=Assignment(tarefa(), "", "", "sem endpoint apto"),
        outcome="skipped",
        detail="sem endpoint apto",
    )
    assert store.record(resultado) is None
    assert list(tmp_path.iterdir()) == []


def test_limites_declarados_por_provedor_nao_viram_teto_por_endpoint() -> None:
    """Os 40 RPM da NVIDIA são da conta inteira; aplicá-los por modelo multiplicaria."""
    limites: dict[str, Any] = {"requests_per_minute_aggregate": 40}
    lido = EndpointLimits.from_observed({}, limites)
    assert lido.requests_per_minute is None
    assert not lido.known


def test_modelos_openrouter_compartilham_a_cota_diaria_da_conta() -> None:
    """Dois IDs :free não recebem duas franquias de 2 chamadas cada."""
    models = [
        ModelInfo(
            provider="openrouter",
            endpoint_id=endpoint,
            family="teste",
            capabilities=["completion"],
            context_window=131072,
            declared_limits={"requests_per_day_aggregate": 2},
        )
        for endpoint in ("vendor/a:free", "vendor/b:free")
    ]
    inventory = build_inventory(
        {"openrouter": DiscoverySnapshot(path=Path("models-openrouter.json"), models=models)},
        confirmado(
            ("openrouter", "vendor/a:free"),
            ("openrouter", "vendor/b:free"),
        ),
    )
    ledger = QuotaLedger()
    ledger.record("openrouter")
    ledger.record("openrouter")

    plan = plan_batch([tarefa()], inventory, ledger, RunBudget(max_calls=10))

    assert plan.assignments == []
    assert "openrouter: 2/2 req/dia" in plan.refusals[0].reason


def _stream_adapter(
    eventos: list[CognitiveEvent],
    *,
    vistos: list[str] | None = None,
) -> type:
    """Adaptador que só entrega stream — o caminho que `_call` toma quando ele existe."""

    class Adapter:
        provider = "groq"

        async def generate(
            self, endpoint_id: str, prompt: str, *, max_output_tokens: int = 256
        ) -> GenerationResult:
            raise AssertionError("com stream disponível, `generate` não deve ser chamada")

        async def stream_generate(
            self, endpoint_id: str, prompt: str, *, max_output_tokens: int = 256
        ) -> AsyncIterator[CognitiveEvent]:
            if vistos is not None:
                vistos.append(endpoint_id)
            for evento in eventos:
                yield evento

    return Adapter


def _plano_de_uma_chamada(ledger: QuotaLedger) -> tuple[Any, Task]:
    inventory = build_inventory(
        {"groq": snapshot("groq", "qwen/qwen3.6-27b")},
        confirmado(("groq", "qwen/qwen3.6-27b")),
    )
    task = tarefa()
    return plan_batch([task], inventory, ledger, RunBudget(max_calls=5)), task


async def test_stream_leva_ao_ledger_o_consumo_que_o_provedor_reportou() -> None:
    """Sem isto, trocar `generate` por stream trocaria medida por estimativa em silêncio.

    O orçamento é um dos quatro casos que exigem confirmação humana. Ele passar a ser
    gasto contra `estimate_tokens` sem ninguém pedir seria afrouxar essa regra por
    efeito colateral de uma mudança sobre outra coisa.
    """
    eventos = [
        CognitiveEvent(
            provider="groq",
            endpoint_id="qwen/qwen3.6-27b",
            kind=CognitiveKind.OUTPUT_DELTA,
            text="resposta",
            raw_field="delta.content",
            sequence=1,
        ),
        CognitiveEvent(
            provider="groq",
            endpoint_id="qwen/qwen3.6-27b",
            kind=CognitiveKind.FINAL,
            raw_field="stream.end",
            sequence=2,
            detail={"usage": {"total_tokens": 4242, "prompt_tokens": 42}},
        ),
    ]
    ledger = QuotaLedger()
    plan, task = _plano_de_uma_chamada(ledger)
    adapter = _stream_adapter(eventos)()

    results = await execute(plan, {"groq": cast(ProviderAdapter, adapter)}, ledger)

    assert results[0].outcome == "ok"
    assert results[0].text == "resposta"
    assert results[0].usage == {"total_tokens": 4242, "prompt_tokens": 42}
    registrado = sum(tokens for _, tokens in ledger.events["groq/qwen/qwen3.6-27b"])
    assert registrado == 4242
    assert registrado != estimate_tokens(task)


async def test_stream_sem_consumo_reportado_estima_e_nao_finge_medida() -> None:
    """Provedor que não reporta consumo no intervalo não ganha número inventado.

    A estimativa aqui é a resposta certa, e é a mesma que `generate` daria com `usage`
    vazio: o que não pode acontecer é ela chegar disfarçada de medição.
    """
    eventos = [
        CognitiveEvent(
            provider="groq",
            endpoint_id="qwen/qwen3.6-27b",
            kind=CognitiveKind.FINAL,
            text="resposta",
            raw_field="stream.end",
            sequence=1,
        )
    ]
    ledger = QuotaLedger()
    plan, task = _plano_de_uma_chamada(ledger)

    results = await execute(
        plan, {"groq": cast(ProviderAdapter, _stream_adapter(eventos)())}, ledger
    )

    assert results[0].usage == {}
    registrado = sum(tokens for _, tokens in ledger.events["groq/qwen/qwen3.6-27b"])
    assert registrado == estimate_tokens(task)


async def test_raciocinio_do_stream_nao_entra_no_texto_do_resultado() -> None:
    """O canal cognitivo é outro tubo: `REASONING` não pode virar texto deliberado."""
    eventos = [
        CognitiveEvent(
            provider="groq",
            endpoint_id="qwen/qwen3.6-27b",
            kind=CognitiveKind.REASONING,
            text="deixa eu pensar em voz alta",
            raw_field="delta.reasoning",
            sequence=1,
        ),
        CognitiveEvent(
            provider="groq",
            endpoint_id="qwen/qwen3.6-27b",
            kind=CognitiveKind.OUTPUT_DELTA,
            text="a resposta",
            raw_field="delta.content",
            sequence=2,
        ),
        CognitiveEvent(
            provider="groq",
            endpoint_id="qwen/qwen3.6-27b",
            kind=CognitiveKind.FINAL,
            raw_field="stream.end",
            sequence=3,
        ),
    ]
    ledger = QuotaLedger()
    plan, _ = _plano_de_uma_chamada(ledger)

    results = await execute(
        plan, {"groq": cast(ProviderAdapter, _stream_adapter(eventos)())}, ledger
    )

    assert results[0].text == "a resposta"
    assert "voz alta" not in results[0].text
