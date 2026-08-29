#!/usr/bin/env python3
"""O que cada endpoint entrega **durante** uma execução. Uma chamada por provedor.

Esta sonda responde a uma pergunta que nenhuma outra respondia: entre o pedido e a
resposta, o que o endpoint deixa ver? A fronteira com os provedores era cega ao intervalo
— `generate()` bloqueia e devolve só o texto final —, e por isso a trilha canônica não
tinha texto de modelo para registrar. Ela transporta `metadata.narration`, mas essa frase é
do orquestrador e não do provedor: medido em 2026-08-11, 88 de 1265 eventos a carregam, e
nenhum traz raciocínio de endpoint — `strip_reasoning` o remove antes de gravar.

Quatro classes possíveis, e a resposta é **por endpoint**, nunca por modelo. O mesmo
modelo servido por dois provedores expõe streams diferentes, e é exatamente a isso que a
arquitetura já responde ao separar fabricante de servidor de inferência:

    A  reasoning-text     raciocínio textual explícito, como fluxo
    B  reasoning-summary  resumo de raciocínio, e não o fluxo
    C  observable         sem raciocínio, mas com ferramenta, progresso ou deltas
    D  final-only         só a resposta, nada no intervalo

A classe é **conclusão de observação**, não promessa de catálogo. Um endpoint que declara
raciocínio e não o emite sob o orçamento pedido sai como `observable`, porque foi isso que
ele fez — a mesma disciplina que separa `ok` de `reachable` na sonda de aptidão.

Regras de consumo, deliberadas e iguais às de `smoke_providers`: um endpoint por provedor
por execução, prompt trivial, nenhum conteúdo do corpus enviado a serviço externo.

Uso:
    python3 tools/probe_streams.py                # um endpoint por provedor
    python3 tools/probe_streams.py --provider groq --endpoint qwen/qwen3-32b
    python3 tools/probe_streams.py --dry-run      # o que seria sondado, sem rede
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import orjson

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from providers import ProviderAdapter, ProviderError, build_adapters  # noqa: E402
from providers.cognitive import (  # noqa: E402
    CognitiveEvent,
    classify_stream,
)
from vault.runtime_io import read_private_json  # noqa: E402
from vault.work.quota_store import load_ledger, persist_ledger  # noqa: E402
from vault.work.quotas import QuotaLedger  # noqa: E402

#: Prompt que provoca intervalo sem custar cota. Pede um passo de raciocínio trivial
#: porque um "responda ok" não dá ao modelo motivo nenhum para pensar — e a sonda mediria
#: o prompt, não o endpoint.
STREAM_PROMPT = "Quanto é 17 × 23? Pense passo a passo e responda só com o número."
STREAM_MAX_OUTPUT_TOKENS = 512
STREAM_ESTIMATED_TOKENS = STREAM_MAX_OUTPUT_TOKENS + len(STREAM_PROMPT.encode("utf-8"))

#: Quanto de cada texto é guardado. O suficiente para provar que veio texto e reconhecer
#: o que ele é; não o bastante para virar cópia da resposta do modelo em disco.
AMOSTRA_DE_TEXTO = 160

RELATORIO = "streams.json"


def _amostra(events: list[CognitiveEvent]) -> list[dict[str, Any]]:
    """Os primeiros pedaços de cada tipo, com o texto cortado.

    Guardar a execução inteira transformaria o relatório num arquivo de respostas de
    modelo. O que ele precisa provar é a **forma** do stream: que tipos vieram, de que
    campo do SDK, em que ordem.
    """
    porTipo: dict[str, int] = {}
    saida: list[dict[str, Any]] = []
    for event in events:
        visto = porTipo.get(event.kind, 0)
        porTipo[event.kind] = visto + 1
        if visto >= 2:
            continue
        item = asdict(event)
        item["kind"] = str(event.kind)
        item["text"] = event.text[:AMOSTRA_DE_TEXTO]
        item["text_length"] = len(event.text)
        saida.append(item)
    return saida


async def sondar(
    adapter: ProviderAdapter, endpoint_id: str, redact: Any
) -> dict[str, Any]:
    """Uma execução real, com o stream consumido até o fim e depois classificado."""
    events: list[CognitiveEvent] = []
    try:
        async for event in adapter.stream_generate(
            endpoint_id, STREAM_PROMPT, max_output_tokens=STREAM_MAX_OUTPUT_TOKENS
        ):
            events.append(event)
    except ProviderError as error:
        return {
            "provider": adapter.provider,
            "endpoint": endpoint_id,
            "outcome": type(error).__name__,
            "detail": redact(str(error))[:200],
            "stream_class": None,
        }
    except Exception as error:  # noqa: BLE001
        # Falha não classificada é resultado igualmente: ela diz que este caminho ainda
        # não está pronto, e escondê-la faria a auditoria afirmar cobertura que não tem.
        return {
            "provider": adapter.provider,
            "endpoint": endpoint_id,
            "outcome": f"nao_classificado:{type(error).__name__}",
            "detail": redact(str(error))[:200],
            "stream_class": None,
        }

    contagem: dict[str, int] = {}
    caracteres: dict[str, int] = {}
    for event in events:
        contagem[str(event.kind)] = contagem.get(str(event.kind), 0) + 1
        caracteres[str(event.kind)] = caracteres.get(str(event.kind), 0) + len(event.text)
    return {
        "provider": adapter.provider,
        "endpoint": endpoint_id,
        "outcome": "ok",
        "stream_class": str(classify_stream(events)),
        "events": len(events),
        "by_kind": contagem,
        "chars_by_kind": caracteres,
        "raw_fields": sorted({event.raw_field for event in events if event.raw_field}),
        "sample": _amostra(events),
    }


async def _sondar_contabilizado(
    adapter: ProviderAdapter,
    endpoint_id: str,
    ledger: QuotaLedger,
    ledger_path: Path,
    redact: Any,
) -> dict[str, Any]:
    """Conta uma tentativa de inferência, tenha ela respondido ou falhado.

    Alguns adaptadores validam a credencial com ``GET /key`` antes de abrir o SSE.
    Essa requisição é parte da mesma tentativa e não ganha um evento próprio: a unidade
    do ledger continua sendo uma chamada de inferência dirigida ao endpoint.
    """
    try:
        return await sondar(adapter, endpoint_id, redact)
    finally:
        ledger.record_call(
            endpoint=f"{adapter.provider}/{endpoint_id}",
            provider=adapter.provider,
            tokens=STREAM_ESTIMATED_TOKENS,
        )
        # Persistir aqui, e não só ao terminar o relatório, conserva a cota mesmo se
        # uma etapa posterior de apresentação ou gravação de evidência falhar.
        persist_ledger(ledger, ledger_path, redact)


def escolher_endpoint(provider: str, settings: Any) -> str | None:
    """Um endpoint que **já respondeu**, e não o primeiro do catálogo.

    Ordem alfabética sobre o catálogo escolhia `antigravity-preview` e `01-ai/yi-large`,
    que a conta não serve — é o mesmo erro que `smoke_providers` documenta, e ali a lição
    já custou uma execução inteira medindo a seleção em vez do provedor. O registro de
    endpoints guarda quem respondeu `ok` numa sonda real; é dele que a escolha sai.
    """
    from providers.registry import EndpointRegistry
    from vault.runtime_io import read_private_json

    bruto = read_private_json(settings.state_dir / "endpoints.json")
    registro = EndpointRegistry.from_dict(bruto)
    comprovados = sorted(
        record.endpoint_id
        for record in registro.records.values()
        if record.provider == provider and record.observed_status == "ok"
    )
    return comprovados[0] if comprovados else None


def _sem_sonda(provider: str, endpoint: str | None, outcome: str) -> dict[str, Any]:
    """Uma linha de relatório para o caso em que nenhuma chamada aconteceu."""
    return {
        "provider": provider,
        "endpoint": endpoint,
        "outcome": outcome,
        "stream_class": None,
    }


async def principal(args: argparse.Namespace) -> int:
    from vault.config import get_settings

    settings = get_settings()
    adapters = build_adapters(settings)
    if args.provider:
        adapters = {k: v for k, v in adapters.items() if k == args.provider}
    if not adapters:
        print("nenhum provedor com credencial — nada a sondar")
        return 1

    ledger, ledger_path = load_ledger(settings.state_dir)
    resultados: list[dict[str, Any]] = []
    for nome, adapter in sorted(adapters.items()):
        endpoint = args.endpoint or escolher_endpoint(nome, settings)
        if endpoint is None:
            resultados.append(_sem_sonda(nome, None, "sem_endpoint"))
            continue
        if args.dry_run:
            resultados.append(_sem_sonda(nome, endpoint, "dry_run"))
            continue
        resultados.append(
            await _sondar_contabilizado(
                adapter,
                endpoint,
                ledger,
                ledger_path,
                settings.redact,
            )
        )

    largura = max((len(str(r["provider"])) for r in resultados), default=8)
    print(f"{'provedor':<{largura}}  {'classe':<18} {'eventos':>7}  endpoint")
    for r in sorted(resultados, key=lambda x: str(x["provider"])):
        classe = r.get("stream_class") or r.get("outcome") or "?"
        print(
            f"{str(r['provider']):<{largura}}  {str(classe):<18} "
            f"{str(r.get('events', '—')):>7}  {r.get('endpoint') or '—'}"
        )
        if r.get("outcome") not in ("ok", "dry_run"):
            print(f"{'':<{largura}}  └─ {r.get('detail', '')[:88]}")

    if not args.dry_run:
        destino = settings.state_dir / RELATORIO
        destino.parent.mkdir(parents=True, exist_ok=True)
        # **O relatório acumula, e não substitui.**
        #
        # Sondar um endpoint dirigido apagava o que as sondas anteriores tinham medido, e
        # a auditoria de quatro provedores virava a auditoria do último comando. A chave é
        # `(provedor, endpoint)`, como no registro de endpoints: uma sonda nova do mesmo
        # endpoint é leitura mais recente e substitui a dele; a de outro endpoint entra ao
        # lado, porque a classe é por endpoint e não por provedor.
        acumulado: dict[tuple[str, str], dict[str, Any]] = {}
        anterior = read_private_json(destino) if destino.exists() else {}
        for item in anterior.get("probes", []) if isinstance(anterior, dict) else []:
            if isinstance(item, dict) and item.get("endpoint"):
                acumulado[(str(item.get("provider")), str(item["endpoint"]))] = item
        for item in resultados:
            if item.get("endpoint"):
                acumulado[(str(item["provider"]), str(item["endpoint"]))] = item
        probes = [acumulado[chave] for chave in sorted(acumulado)]
        corpo = orjson.dumps({"probes": probes}, option=orjson.OPT_INDENT_2)
        destino.write_bytes(corpo)
        # O arquivo guarda amostra de texto de modelo: mesmo modo restrito dos demais
        # relatórios de estado, e nunca versionado.
        destino.chmod(0o600)
        print(f"\ngravado em {destino}")

    faltando = [r for r in resultados if r.get("stream_class") is None and not args.dry_run]
    return 1 if faltando else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", help="sonda só este provedor")
    parser.add_argument("--endpoint", help="sonda este endpoint em vez do primeiro disponível")
    parser.add_argument(
        "--dry-run", action="store_true", help="mostra o que seria sondado, sem tocar a rede"
    )
    return asyncio.run(principal(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
