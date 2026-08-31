#!/usr/bin/env python3
"""Uma chamada mínima por provedor. Verifica que o caminho existe, não mede modelo.

Regras desta fase, deliberadas: no máximo um endpoint por provedor, prompt trivial,
nenhum conteúdo do corpus enviado a serviço externo, e nenhum benchmark. O objetivo é
distinguir quatro respostas — funcionou, credencial recusada, indisponível, limite
atingido — sem traceback e sem gastar cota.

A sonda é dirigida: `providers.aptitude` descarta o que não é geração de texto e
ordena o resto, e `providers.registry` tira da frente o que já foi observado. Ordem
alfabética escolhia `antigravity-preview` e `01-ai/yi-large`, endpoints que a conta
não serve — o que media a seleção, não o provedor.

Continua valendo uma chamada por provedor por execução. Quando a sonda falha, o
registro guarda a falha e a execução seguinte tenta o próximo candidato: convergência
entre execuções, não retry escondido dentro de uma.

A exceção é `--sweep PROVEDOR`, que sonda todos os elegíveis de um provedor só. Existe
porque um catálogo público pode listar o que a conta não alcança — é o caso da Ollama,
onde os modelos fora do plano lideram o ranking por declararem as maiores janelas — e
aí a convergência entre execuções custaria mais do que perguntar de uma vez. É decisão
de consumo, e por isso precisa ser pedida pelo nome.

`--provider PROVEDOR` conserva o limite normal: escolhe exatamente um endpoint e não
toca nenhum outro provedor. É a forma dirigida de ativar uma integração sem consumir
cota das demais.
"""

from __future__ import annotations

import argparse
import asyncio
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import orjson

from providers import (
    ObservedLimits,
    ProbeResult,
    ProviderAccountExhausted,
    ProviderAdapter,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimited,
    ProviderUnavailable,
    build_adapters,
)
from providers.aptitude import Aptitude, classify_all, select_for_probe
from providers.base import PROBE_MAX_OUTPUT_TOKENS, PROBE_PROMPT
from providers.catalog import (
    DiscoverySnapshot,
    DiscoverySnapshotError,
    load_discovery_manifest,
    load_discovery_snapshot,
)
from providers.registry import REGISTRY_NAME, EndpointRegistry
from vault.config import SECRETS_FILE_HINT, get_settings
from vault.runtime_io import read_private_json, redact_json, write_private_json
from vault.work.quota_store import load_ledger, persist_ledger
from vault.work.quotas import QuotaLedger

PROBE_ESTIMATED_TOKENS = PROBE_MAX_OUTPUT_TOKENS + len(PROBE_PROMPT.encode("utf-8"))


@dataclass(frozen=True, slots=True)
class SmokeResult:
    provider: str
    listing: str
    limits: ObservedLimits
    probe: ProbeResult | None = None
    selection: Aptitude | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "listing": self.listing,
            "selection": asdict(self.selection) if self.selection else None,
            "probe": asdict(self.probe) if self.probe else None,
            "limits": asdict(self.limits),
        }


def _probe_recorder(
    ledger: QuotaLedger,
    path: Path,
    redact: Callable[[str], str],
) -> Callable[[str, str], None]:
    """Persiste uma tentativa nos escopos do endpoint e do provedor."""

    def record(provider: str, endpoint_id: str) -> None:
        ledger.record_call(
            endpoint=f"{provider}/{endpoint_id}",
            provider=provider,
            tokens=PROBE_ESTIMATED_TOKENS,
        )
        persist_ledger(ledger, path, redact)

    return record


def _redact_limits(
    limits: ObservedLimits,
    redact: Callable[[str], str],
) -> ObservedLimits:
    return replace(
        limits,
        note=redact(limits.note),
        raw={redact(key): redact(value) for key, value in limits.raw.items()},
    )


def _redact_aptitude(aptitude: Aptitude, redact: Callable[[str], str]) -> Aptitude:
    """O identificador vem da listagem externa: passa pela redação como o resto."""
    return replace(
        aptitude,
        endpoint_id=redact(aptitude.endpoint_id),
        family=redact(aptitude.family),
        reason=redact(aptitude.reason),
    )


def _listing(snapshot: DiscoverySnapshot) -> tuple[str, list[Aptitude]]:
    models = snapshot.models
    eligible = [aptitude for aptitude in classify_all(models) if aptitude.eligible]
    return (
        f"{len(models)} endpoints em {snapshot.path.name}, {len(eligible)} aptos a texto"
    ), eligible


async def smoke(
    name: str,
    adapter: ProviderAdapter,
    snapshot: DiscoverySnapshot,
    *,
    statuses: dict[str, str] | None = None,
    redact: Callable[[str], str] = lambda text: text,
    record_call: Callable[[str, str], None] | None = None,
) -> SmokeResult:
    """Sonda exatamente um endpoint do retrato, sem repetir a listagem."""
    models = snapshot.models
    listing, _ = _listing(snapshot)
    choice = select_for_probe(models, statuses)
    if choice is None:
        return SmokeResult(
            provider=name,
            listing=listing,
            limits=_redact_limits(adapter.get_observed_limits(), redact),
        )
    return await probe_one(name, adapter, choice, listing, redact, record_call=record_call)


async def probe_one(
    name: str,
    adapter: ProviderAdapter,
    choice: Aptitude,
    listing: str,
    redact: Callable[[str], str],
    *,
    record_call: Callable[[str, str], None] | None = None,
) -> SmokeResult:
    """Sonda um endpoint já escolhido e embrulha o desfecho, sem deixar traceback subir."""
    started = time.perf_counter()

    def elapsed_ms() -> int:
        return int((time.perf_counter() - started) * 1000)

    try:
        probe = await adapter.probe_model(choice.endpoint_id)
    except ProviderError as error:
        outcome = (
            "account_exhausted"
            if isinstance(error, ProviderAccountExhausted)
            else "rate_limited"
            if isinstance(error, ProviderRateLimited)
            else (
                "auth"
                if isinstance(error, ProviderAuthError)
                else "unavailable"
                if isinstance(error, ProviderUnavailable)
                else "error"
            )
        )
        result = SmokeResult(
            provider=name,
            listing=listing,
            selection=_redact_aptitude(choice, redact),
            limits=_redact_limits(adapter.get_observed_limits(), redact),
            probe=ProbeResult(
                provider=name,
                endpoint_id=redact(choice.endpoint_id),
                outcome=outcome,
                detail=redact(f"{type(error).__name__}: {error}")[:400],
                latency_ms=elapsed_ms(),
            ),
        )
    except Exception as error:  # noqa: BLE001 — fronteira da CLI, sem traceback
        detail = redact(f"{type(error).__name__}: {error}")[:400]
        result = SmokeResult(
            provider=name,
            listing=listing,
            selection=_redact_aptitude(choice, redact),
            limits=_redact_limits(adapter.get_observed_limits(), redact),
            probe=ProbeResult(
                provider=name,
                endpoint_id=redact(choice.endpoint_id),
                outcome="error",
                detail=detail,
                latency_ms=elapsed_ms(),
            ),
        )
    else:
        result = SmokeResult(
            provider=name,
            listing=listing,
            selection=_redact_aptitude(choice, redact),
            limits=_redact_limits(adapter.get_observed_limits(), redact),
            probe=replace(
                probe,
                endpoint_id=redact(probe.endpoint_id),
                detail=redact(probe.detail),
            ),
        )
    finally:
        if record_call is not None:
            record_call(name, choice.endpoint_id)
    return result


async def sweep(
    name: str,
    adapter: ProviderAdapter,
    snapshot: DiscoverySnapshot,
    *,
    redact: Callable[[str], str] = lambda text: text,
    record_call: Callable[[str, str], None] | None = None,
) -> list[SmokeResult]:
    """Sonda **todos** os elegíveis de um provedor, e não um por execução.

    O padrão existe por um bom motivo e continua sendo o padrão: uma falha condiciona a
    execução seguinte em vez de virar retry escondido dentro de uma. A varredura existe
    porque há uma pergunta que o padrão responde devagar demais — quais endpoints esta
    conta realmente alcança.

    Na Ollama a pergunta é inevitável: o catálogo é público e lista o que o plano não
    inclui, e os modelos pagos ficam no topo do ranking justamente por declararem as
    maiores janelas. Medido em 2026-08-05, onze dos dezoito respondem 403; partindo do
    topo, o padrão levaria mais de dez execuções para alcançar um endpoint utilizável, e
    gastaria uma chamada em cada outro provedor a cada volta.

    Não é o modo normal e não vira o modo normal: exige `--sweep` com o nome do
    provedor e toca só esse provedor.     Para no primeiro bloqueio que vale para o
    provedor inteiro (`auth`, 429 ou crédito esgotado); falhas específicas de
    endpoint continuam a varredura.
    """
    listing, eligible = _listing(snapshot)
    resultados: list[SmokeResult] = []
    for choice in eligible:
        resultado = await probe_one(
            name,
            adapter,
            choice,
            listing,
            redact,
            record_call=record_call,
        )
        resultados.append(resultado)
        if resultado.probe is not None and resultado.probe.outcome in {
            "auth",
            "rate_limited",
            "account_exhausted",
        }:
            break
    return resultados


def report(result: SmokeResult) -> bool:
    """Imprime o resultado e devolve se ele conta como sucesso.

    `reachable` não conta. O comando sai diferente de zero enquanto houver provedor
    cujo endpoint respondeu sem escrever nada: é pendência aberta, não sucesso.
    """
    print(f"{result.provider:8} .. {result.listing}")
    if result.selection is not None:
        choice = result.selection
        print(
            f"{'':8}    escolha: {choice.endpoint_id} "
            f"[{choice.purpose}/{choice.stability}] — {choice.reason}"
        )
    ok = False
    if result.probe is None:
        print(f"{'':8}    sem sondagem")
    else:
        probe = result.probe
        mark = "ok" if probe.ok else probe.outcome.upper()
        latency = f"{probe.latency_ms} ms" if probe.latency_ms is not None else "—"
        print(f"{'':8}    {mark} em {probe.endpoint_id} ({latency}): {probe.detail}")
        if probe.outcome == "reachable":
            print(
                f"{'':8}    alcançado, não comprovado: falta saída textual sob "
                f"orçamento maior antes de receber trabalho"
            )
        ok = probe.ok

    limits = result.limits
    print(f"{'':8}    limites [{limits.source}]: {limits.note}")
    if limits.raw:
        print(f"{'':8}    headers: {orjson.dumps(limits.raw).decode()}")
    return ok


def _args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--provider",
        metavar="PROVEDOR",
        help="sonda um único endpoint somente deste provedor",
    )
    mode.add_argument(
        "--sweep",
        metavar="PROVEDOR",
        help=(
            "sonda todos os endpoints elegíveis deste provedor, em vez de um por "
            "provedor. Gasta uma chamada por endpoint: é decisão de consumo, por isso "
            "precisa ser pedida pelo nome."
        ),
    )
    return parser.parse_args(argv)


async def _sweep_provider(
    nome: str,
    settings: Any,
    registry: EndpointRegistry,
    record_call: Callable[[str, str], None],
) -> int:
    adapters = build_adapters(settings)
    adapter = adapters.get(nome)
    if adapter is None:
        conhecidos = ", ".join(sorted(adapters)) or "nenhum"
        print(f"sem credencial para {nome} (há: {conhecidos})")
        return 1
    try:
        snapshot = load_discovery_snapshot(settings.state_dir, nome)
    except DiscoverySnapshotError as error:
        print(str(error))
        return 1

    resultados = await sweep(
        nome,
        adapter,
        snapshot,
        redact=settings.redact,
        record_call=record_call,
    )
    for resultado in resultados:
        if resultado.probe is not None:
            registry.record_probe(resultado.probe, resultado.limits)
    # Lista, não gerador: `all` curto-circuitaria e esconderia endpoints do relatório.
    todos_ok = all([report(resultado) for resultado in resultados])

    registry_path = settings.state_dir / REGISTRY_NAME
    write_private_json(registry_path, redact_json(registry.to_dict(), settings.redact))
    log = settings.logs_dir / f"smoke-sweep-{nome}.json"
    write_private_json(log, [resultado.to_dict() for resultado in resultados])
    aptos = sum(1 for r in resultados if r.probe is not None and r.probe.ok)
    print(f"\n{aptos} de {len(resultados)} endpoints produziram texto")
    print(f"registro operacional: {registry_path}")
    print(f"evidência desta execução: {log}")
    return 0 if todos_ok else 1


async def main(argv: Sequence[str] | None = None) -> int:
    """`argv` explícito porque quem chama nem sempre é a linha de comando.

    Com `parse_args()` lendo `sys.argv` direto, um teste que chama `main()` recebia os
    argumentos do pytest e morria em `unrecognized arguments`. O padrão `None` preserva
    o comportamento de CLI; quem chama de dentro passa a própria lista.
    """
    args = _args(argv)
    settings = get_settings()
    adapters = build_adapters(settings)
    if not adapters:
        print(f"nenhuma credencial de provedor em {SECRETS_FILE_HINT}")
        return 1
    if args.provider:
        adapter = adapters.get(args.provider)
        if adapter is None:
            conhecidos = ", ".join(sorted(adapters)) or "nenhum"
            print(f"sem credencial para {args.provider} (há: {conhecidos})")
            return 1
        adapters = {args.provider: adapter}

    try:
        manifest = load_discovery_manifest(settings.state_dir)
    except DiscoverySnapshotError as error:
        print(str(error))
        return 1

    registry_path = settings.state_dir / REGISTRY_NAME
    registry = EndpointRegistry.from_dict(read_private_json(registry_path))
    ledger, ledger_path = load_ledger(settings.state_dir)
    record_call = _probe_recorder(ledger, ledger_path, settings.redact)

    if args.sweep:
        return await _sweep_provider(args.sweep, settings, registry, record_call)

    results: list[SmokeResult] = []
    stopped = False
    for name, adapter in adapters.items():
        if stopped:
            results.append(
                SmokeResult(
                    provider=name,
                    listing="não executado: ciclo interrompido após 429",
                    limits=_redact_limits(adapter.get_observed_limits(), settings.redact),
                )
            )
            continue
        try:
            snapshot = load_discovery_snapshot(settings.state_dir, name, manifest)
        except DiscoverySnapshotError as error:
            results.append(
                SmokeResult(
                    provider=name,
                    listing=str(error),
                    limits=_redact_limits(adapter.get_observed_limits(), settings.redact),
                )
            )
            continue
        result = await smoke(
            name,
            adapter,
            snapshot,
            statuses=registry.statuses(name),
            redact=settings.redact,
            record_call=record_call,
        )
        results.append(result)
        if result.probe is not None:
            # Os limites vão junto com a sonda: eles pertencem ao endpoint que acabou
            # de responder, não ao provedor inteiro.
            registry.record_probe(result.probe, result.limits)
        stopped = result.probe is not None and result.probe.outcome == "rate_limited"
    # Lista, não gerador: `all` curto-circuitaria e deixaria provedores sem relatório.
    todos_ok = all([report(result) for result in results])

    write_private_json(registry_path, redact_json(registry.to_dict(), settings.redact))
    log = settings.logs_dir / "smoke-providers.json"
    write_private_json(log, [result.to_dict() for result in results])
    print(f"\nregistro operacional: {registry_path}")
    print(f"evidência desta execução: {log}")
    return 0 if todos_ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
