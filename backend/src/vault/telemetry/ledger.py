"""Constrói o ledger de desfechos a partir do que o sistema já persistiu.

**O ledger é derivado, não emitido.** Os eventos primários já estão em disco desde
sempre: as tentativas em `runtime/state/autonomy/tasks.json`, os painéis em
`runtime/quorum/<id>/`, o diário em `runtime/promotion/promotions.jsonl`. O que
faltava não era gravar — era **ler de volta**. Acrescentar um segundo caminho de
escrita no caminho quente do orquestrador arriscaria exatamente as chamadas que se
quer medir, e criaria duas verdades sobre o mesmo evento.

A consequência prática é que reconstruir é barato e idempotente: apagar o ledger não
perde nada, porque a fonte continua sendo a origem. E os 296 fracassos que já estavam no
disco entram na primeira execução, sem esperar tráfego novo.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, TypedDict

import orjson

from vault.quorum.engine import decide_panel
from vault.quorum.models import Panel
from vault.telemetry.records import OutcomeClass, OutcomeRecord, Stage, classify

LEDGER_NAME = "outcomes.jsonl"
# O diário de assimilação: o Promoter já grava o desfecho; o ledger só lê.
_DIARIO_DE_PROMOCAO = Path("promotion") / "promotions.jsonl"
_ESTADOS_TERMINAIS = frozenset({"promoted", "stale", "rejected", "failed"})


class Identidade(TypedDict):
    """Os campos que todo registro de um painel compartilha.

    Existe para o `**` de baixo continuar tipado: desempacotar `dict[str, Any]` faz o
    verificador perder as assinaturas de `OutcomeRecord` e aceitar qualquer coisa.
    """

    task_id: str
    panel_id: str | None
    task_kind: str | None
    domain: str | None
    corpus_entity: str | None


def _texto(valor: Any) -> str | None:
    return valor if isinstance(valor, str) and valor else None


def _duracao_ms(inicio: str | None, fim: str | None) -> int | None:
    if not inicio or not fim:
        return None
    from datetime import datetime

    try:
        delta = datetime.fromisoformat(fim) - datetime.fromisoformat(inicio)
    except ValueError:
        return None
    ms = int(delta.total_seconds() * 1000)
    return ms if ms >= 0 else None


def _validacao_do_texto(detail: str | None) -> str | None:
    """Reduz a recusa das guardas ao vocabulário da ADR-003 (L1/L2), ou `refused`."""
    if not detail:
        return None
    if "auditoria estrutural" in detail:
        return "structural_validation"
    if "allows_reduction" in detail or "sem allows_reduction" in detail:
        return "preservation_validation"
    if "projeção" in detail.lower() or "projection" in detail.lower():
        return "projection_validation"
    return "refused"


def _diario_de_promocao(runtime_dir: Path) -> dict[str, dict[str, Any]]:
    """Último estado terminal do diário, por `panel_id`.

    `eligible`/`pending`/`applying` não fecham nada: um crash no meio deixa o
    painel sem desfecho, e o ledger não inventa um.
    """
    caminho = runtime_dir / _DIARIO_DE_PROMOCAO
    if not caminho.is_file():
        return {}
    ultimo: dict[str, dict[str, Any]] = {}
    try:
        linhas = caminho.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    for linha in linhas:
        if not linha.strip():
            continue
        try:
            entrada = json.loads(linha)
        except ValueError:
            continue
        painel = _texto(entrada.get("panel_id"))
        estado = _texto(entrada.get("state"))
        if painel is None or estado not in _ESTADOS_TERMINAIS:
            continue
        ultimo[painel] = entrada
    return ultimo


def _desfechos_do_diario(
    entrada: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    """`(promotion_outcome, validation_outcome)` a partir de um estado terminal."""
    if not entrada:
        return None, None
    estado = _texto(entrada.get("state"))
    if estado == "promoted":
        return estado, "passed"
    if estado == "rejected":
        return estado, _validacao_do_texto(_texto(entrada.get("detail"))) or "refused"
    if estado == "failed":
        return estado, "failed"
    return estado, None


def _registros_da_fila(tasks_path: Path) -> Iterator[OutcomeRecord]:
    """Uma tentativa de tarefa é um evento; cada uma vira um registro."""
    if not tasks_path.is_file():
        return
    dados = json.loads(tasks_path.read_text(encoding="utf-8"))
    for tarefa in dados.get("tasks", []):
        # A decisão do controlador de admissão não é tentativa e não cria uma — de
        # propósito, porque nenhum modelo foi chamado. Ela precisa aparecer aqui mesmo
        # assim, ou o único componente que decide **não** gastar seria o único que
        # ninguém consegue auditar. A fila guarda apenas a última, e é o que se tem.
        adiamento = _texto((tarefa.get("metadata") or {}).get("last_backpressure"))
        if adiamento:
            yield OutcomeRecord(
                at=_texto(tarefa.get("updated_at")) or "",
                stage=Stage.ADMISSION,
                outcome_class=OutcomeClass.ADIADO
                if adiamento.startswith("quorum_capacity:")
                else classify(None, adiamento),
                task_id=tarefa["id"],
                task_kind=_texto(tarefa.get("kind")),
                domain=_texto(tarefa.get("domain")),
                corpus_entity=_texto(tarefa.get("corpus_entity")),
                detail=adiamento[:400],
            )
        for tentativa in tarefa.get("attempts", []):
            endpoints = tentativa.get("endpoints") or []
            # Uma tentativa pode tocar mais de um endpoint; o primeiro é o do proponente,
            # que é quem de fato falhou quando a tentativa falhou antes do painel.
            alvo = endpoints[0] if endpoints else None
            provider, _, endpoint = (alvo or "").partition("/")
            panel_id = _texto(tentativa.get("panel_id"))
            detalhe = (tentativa.get("detail") or "")[:400]
            # Recusa de `admit_patch` não cria painel: a guarda rodou, e o desfecho
            # precisa aparecer aqui ou o M3 continua cego ao único sinal L1/L2 que já
            # existe em volume.
            validacao = (
                _validacao_do_texto(detalhe)
                if tentativa.get("outcome") == "rejected" and panel_id is None
                else None
            )
            yield OutcomeRecord(
                at=tentativa.get("finished_at") or tentativa.get("started_at") or "",
                stage=Stage.ATTEMPT,
                outcome_class=classify(
                    tentativa.get("outcome"), tentativa.get("detail")
                ),
                task_id=tarefa["id"],
                panel_id=panel_id,
                task_kind=_texto(tarefa.get("kind")),
                domain=_texto(tarefa.get("domain")),
                corpus_entity=_texto(tarefa.get("corpus_entity")),
                provider=_texto(provider),
                endpoint=_texto(endpoint),
                latency_ms=_duracao_ms(
                    tentativa.get("started_at"), tentativa.get("finished_at")
                ),
                validation_outcome=validacao,
                detail=detalhe,
            )


def _registros_do_painel(
    diretorio: Path,
    diario: dict[str, dict[str, Any]] | None = None,
) -> Iterator[OutcomeRecord]:
    """Proposta, votos e decisão de um painel, com a pivotalidade recalculada."""
    bruto = diretorio / "decision.json"
    tarefa_path = diretorio / "task.json"
    if not tarefa_path.is_file():
        return
    contexto = json.loads(tarefa_path.read_text(encoding="utf-8"))
    tarefa = contexto.get("task") or {}
    ctx = tarefa.get("context") or {}
    comum: Identidade = {
        "task_id": str(tarefa.get("id") or contexto.get("panel_id") or diretorio.name),
        "panel_id": str(contexto.get("panel_id") or diretorio.name),
        "task_kind": _texto(tarefa.get("kind")),
        "domain": _texto(ctx.get("domain")),
        "corpus_entity": _texto(ctx.get("corpus_entity")),
    }
    tem_patch = (diretorio / "patch.json").is_file()
    digest = _texto(ctx.get("patch_digest"))

    proposta = contexto.get("proposal") or {}
    proponente = proposta.get("proposer") or {}
    if proponente:
        yield OutcomeRecord(
            at=_texto(tarefa.get("created_at")) or "",
            stage=Stage.PROPOSAL,
            outcome_class=OutcomeClass.OK,
            role=_texto(proponente.get("role_name")),
            provider=_texto(proponente.get("provider")),
            endpoint=_texto(proponente.get("endpoint_id")),
            family=_texto(proponente.get("family")),
            patch_digest=digest if tem_patch else None,
            **comum,
        )

    if not bruto.is_file():
        return
    decisao = json.loads(bruto.read_text(encoding="utf-8"))
    pivotal = _pivotalidade(diretorio)
    quando = _texto(decisao.get("decided_at")) or ""
    # A fonte do voto é `votes/`, e não a lista de `decision.json`: a decisão só carrega
    # os votos que **foram contados**, então medir validade por ela responde sempre 100%.
    # Foi assim que a primeira versão desta superfície nasceu tautológica. O arquivo por
    # voto guarda o que interessa — `schema_valid`, o erro, e se houve reparo.
    for voto in _votos_brutos(diretorio, decisao):
        revisor = voto.get("reviewer") or {}
        chave = f"{revisor.get('provider')}/{revisor.get('endpoint_id')}"
        estruturado = voto.get("structured_vote") or {}
        valido = bool(voto.get("schema_valid"))
        yield OutcomeRecord(
            at=quando,
            stage=Stage.VOTE,
            outcome_class=OutcomeClass.OK
            if valido
            else classify(None, _texto(voto.get("error")) or "voto ilegível"),
            role=_texto(revisor.get("role_name")),
            provider=_texto(revisor.get("provider")),
            endpoint=_texto(revisor.get("endpoint_id")),
            family=_texto(revisor.get("family")),
            vote_decision=_texto(estruturado.get("decision")),
            confidence=estruturado.get("confidence"),
            schema_valid=valido,
            pivotal=pivotal.get(chave) if valido else None,
            detail=(_texto(voto.get("error")) or "")[:400],
            **comum,
        )

    promocao, validacao = _desfechos_do_diario(
        (diario or {}).get(str(comum["panel_id"] or diretorio.name))
    )
    yield OutcomeRecord(
        at=_texto(decisao.get("decided_at")) or "",
        stage=Stage.DECISION,
        outcome_class=classify(decisao.get("outcome"), decisao.get("reason")),
        decision_outcome=_texto(decisao.get("outcome")),
        patch_digest=digest if tem_patch else None,
        promotion_outcome=promocao,
        validation_outcome=validacao,
        detail=(decisao.get("reason") or "")[:400],
        **comum,
    )


def _votos_brutos(diretorio: Path, decisao: dict[str, Any]) -> list[dict[str, Any]]:
    """Os votos como o painel os recebeu, incluindo os que não puderam ser contados.

    Recorre a `decision.json` só quando `votes/` não existe — painel antigo, ou execução
    que morreu antes de gravar. Nesse caso o registro fica otimista, e é melhor dizer
    isso aqui do que descartar o painel inteiro.
    """
    pasta = diretorio / "votes"
    if pasta.is_dir():
        arquivos = sorted(p for p in pasta.iterdir() if p.suffix == ".json")
        if arquivos:
            brutos: list[dict[str, Any]] = []
            for arquivo in arquivos:
                try:
                    brutos.append(json.loads(arquivo.read_text(encoding="utf-8")))
                except (ValueError, OSError):
                    continue
            if brutos:
                return brutos
    return [
        {
            "reviewer": voto.get("reviewer") or {},
            "structured_vote": {
                "decision": voto.get("decision"),
                "confidence": voto.get("confidence"),
            },
            "schema_valid": voto.get("decision") is not None,
        }
        for voto in decisao.get("votes") or []
    ]


def _pivotalidade(diretorio: Path) -> dict[str, str]:
    """Recalcula a decisão retirando um voto por vez, pela regra real do quórum.

    Usa `decide_panel`, e não uma reimplementação da maioria: o valor só significa
    alguma coisa se for o mesmo critério que o sistema aplica de verdade. Mede
    **influência sobre a decisão**, nunca qualidade — o voto que derrubou o painel do
    stub e o que o aprovou têm o mesmo peso aqui.
    """
    try:
        painel = Panel.model_validate(
            json.loads((diretorio / "panel.json").read_text(encoding="utf-8"))
            if (diretorio / "panel.json").is_file()
            else _painel_reconstruido(diretorio)
        )
    except (ValueError, OSError, KeyError):
        return {}
    if len(painel.votes) < 2:
        return {}
    try:
        completo = decide_panel(painel).outcome
    except (ValueError, ZeroDivisionError):
        return {}
    resultado: dict[str, str] = {}
    for indice, voto in enumerate(painel.votes):
        restantes = [v for posicao, v in enumerate(painel.votes) if posicao != indice]
        reduzido = painel.model_copy(update={"votes": restantes})
        try:
            parcial = decide_panel(reduzido).outcome
        except (ValueError, ZeroDivisionError):
            continue
        chave = f"{voto.reviewer.provider}/{voto.reviewer.endpoint_id}"
        resultado[chave] = "pivotal" if parcial != completo else "redundant"
    return resultado


def _painel_reconstruido(diretorio: Path) -> dict[str, Any]:
    """Monta o painel a partir das partes, para os diretórios que não gravam `panel.json`."""
    contexto = json.loads((diretorio / "task.json").read_text(encoding="utf-8"))
    membros = json.loads((diretorio / "members.json").read_text(encoding="utf-8"))
    votos = []
    pasta = diretorio / "votes"
    if pasta.is_dir():
        for arquivo in sorted(pasta.iterdir()):
            votos.append(json.loads(arquivo.read_text(encoding="utf-8")))
    return {
        "id": contexto.get("panel_id", diretorio.name),
        "task": contexto["task"],
        "proposal": contexto["proposal"],
        "members": membros if isinstance(membros, list) else membros.get("members", []),
        "votes": votos,
    }


def build_records(runtime_dir: Path) -> list[OutcomeRecord]:
    """Todos os registros derivados do estado atual, ordenados no tempo."""
    diario = _diario_de_promocao(runtime_dir)
    registros = list(_registros_da_fila(runtime_dir / "state" / "autonomy" / "tasks.json"))
    quorum = runtime_dir / "quorum"
    if quorum.is_dir():
        for diretorio in sorted(quorum.iterdir()):
            if diretorio.is_dir():
                registros.extend(_registros_do_painel(diretorio, diario))
    return sorted(registros, key=lambda registro: (registro.at, registro.task_id))


def write_ledger(runtime_dir: Path, records: list[OutcomeRecord]) -> Path:
    """Grava o ledger inteiro, de uma vez, com permissão restrita como o resto do runtime."""
    destino = runtime_dir / "state" / LEDGER_NAME
    destino.parent.mkdir(parents=True, exist_ok=True)
    corpo = b"".join(
        orjson.dumps(registro.to_dict(), option=orjson.OPT_SORT_KEYS) + b"\n"
        for registro in records
    )
    temporario = destino.with_suffix(".jsonl.tmp")
    temporario.write_bytes(corpo)
    temporario.chmod(0o600)
    temporario.replace(destino)
    return destino


def read_ledger(runtime_dir: Path) -> list[OutcomeRecord]:
    """Lê o ledger gravado. Linha ilegível é descartada, nunca derruba a leitura."""
    origem = runtime_dir / "state" / LEDGER_NAME
    if not origem.is_file():
        return []
    registros: list[OutcomeRecord] = []
    for linha in origem.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        try:
            registros.append(OutcomeRecord.model_validate(orjson.loads(linha)))
        except ValueError:
            continue
    return registros
