"""Camada operacional: procedência, não conhecimento.

O dossiê pede duas redes coordenadas e **não misturadas**. A epistêmica é persistente
e vem de `knowledge/`; a operacional é temporal e registra o que os agentes fizeram —
`agente → atividade → evidência → proposta → validação → commit ou rejeição`.

Em produção essa rede nasce da persistência estruturada em `runtime/quorum/`. O Atlas
recebe apenas uma lista branca de metadados: identidade operacional, voto, confiança,
contagem e decisão. Respostas livres nunca atravessam esta fronteira. Sob
`VAULT_DEMO_OPERATIONAL=1` continua existindo uma trilha sintética explicitamente
marcada como demonstração; ela nunca é consequência de falha de leitura.

Duas coisas que esta camada nunca representa: raciocínio interno de modelo, e
qualquer coisa dentro de `knowledge/`.
"""

from __future__ import annotations

import hashlib
import re
import stat
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import orjson

from vault.events import OperationalEvent
from vault.work.roles import ROLES

OperationalKind = Literal[
    "agent",
    "activity",
    "evidence",
    "proposal",
    "commit",
    "rejection",
    "temporary-file",
    "quorum-panel",
    "quorum-member",
    "quorum-vote",
    "quorum-decision",
]

OPERATIONAL_KINDS: tuple[OperationalKind, ...] = (
    "agent",
    "activity",
    "evidence",
    "proposal",
    "commit",
    "rejection",
    "temporary-file",
    "quorum-panel",
    "quorum-member",
    "quorum-vote",
    "quorum-decision",
)

# Estado canônico por tipo operacional. Proposta é vazada, temporário é hachurado,
# rejeição é preservada com corte — nenhum deles pode parecer nota canônica.
STATE_BY_KIND: dict[OperationalKind, str] = {
    "agent": "temporary",
    "activity": "temporary",
    "evidence": "temporary",
    "proposal": "proposed",
    "commit": "canonical",
    "rejection": "rejected",
    "temporary-file": "temporary",
    "quorum-panel": "temporary",
    "quorum-member": "temporary",
    "quorum-vote": "temporary",
    "quorum-decision": "temporary",
}

DEMO_DOMAIN = {"id": "operacional", "label": "operacional"}
QUORUM_DOMAIN = {"id": "operacional/quorum", "label": "quórum"}
MODEL_DOMAIN = {"id": "operacional/modelos", "label": "modelos"}
# Provedor tem domínio próprio desde que o acervo passou de 30 para 193 modelos: como
# satélite de si mesmo dentro da nuvem de modelos, a âncora sumia no meio dos filhos.
PROVIDER_DOMAIN = {"id": "operacional/provedores", "label": "provedores"}
# O trabalhador ganhou domínio próprio quando a configuração dele saiu do menu e virou
# painel: até aqui os sete papéis só existiam na cena como votos dentro de centenas de
# painéis de quórum, e não havia nenhum nó que fosse **o** verificador factual — logo,
# nenhuma placa a que ancorar "ativo", "simultâneas" e "raciocínio".
WORKER_DOMAIN = {"id": "operacional/trabalhadores", "label": "trabalhadores"}

# A cor da nuvem de modelos é a **da marca do provedor**, e não uma posição numa lista.
#
# Ela era atribuída por ordem alfabética a partir de uma lista fechada de tokens de
# domínio: dizia de quem é o painel, mas dizia por convenção interna — e mudava de cor
# quando um provedor novo entrava antes dele no alfabeto. O token de marca é estável e
# reconhecível sem aprender nada.
#
# `P:` é resolvido em `palette.ts`, que guarda o matiz oficial de cada provedor na
# luminosidade da cena. Provedor sem marca declarada cai na lista ciclada de antes, que
# continua existindo para nunca deixar um nó sem cor.
_PROVIDER_TOKENS = {
    "groq": "P:groq",
    "google": "P:google",
    "nvidia": "P:nvidia",
    "nous": "P:nous",
    "ollama": "P:ollama",
    "openrouter": "P:openrouter",
}
_MODEL_TOKENS = ("D02", "D07", "D10", "D04", "D12", "D08")


def worker_palette_token(ordem: int, *, reviews_others: bool) -> str:
    """A cor de um trabalhador. Uma regra só, para dois consumidores.

    Avaliador e produtor se distinguem pela cor porque é a distinção que governa o
    quórum: só quem avalia conta para o mínimo de votos. A função existe porque o
    snapshot de controle passou a carregar o mesmo token — o runtime possui a entidade
    e portanto a descreve —, e duas implementações da mesma cor divergiriam no dia em
    que alguém mexesse numa delas.
    """
    return "D08" if reviews_others else _MODEL_TOKENS[ordem % len(_MODEL_TOKENS)]


def _palette_token(provider: str, ordem: int) -> str:
    """O token de cor de um provedor: o da marca, ou o da lista quando não há marca."""
    return _PROVIDER_TOKENS.get(provider.lower(), _MODEL_TOKENS[ordem % len(_MODEL_TOKENS)])


def _model_id(provider: str, endpoint: str) -> str:
    """Identidade canônica de um modelo, uma só para todas as execuções."""
    return f"op/model/{provider}/{endpoint}"


def _provider_id(provider: str) -> str:
    return f"op/provider/{provider}"


VOTE_DECISIONS = frozenset({"approve", "reject", "revise", "abstain"})
QUORUM_ACTIONS = frozenset({"promote", "revise", "reject", "escalate"})
_PANEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_SECRET = re.compile(
    r"AIza[0-9A-Za-z_\-]{20,}|gsk_[0-9A-Za-z]{20,}|nvapi-[0-9A-Za-z_\-]{20,}"
    r"|sk-(?:or-v1-)?[0-9A-Za-z_\-]{20,}|ya29\.[0-9A-Za-z_\-]{20,}"
)
_FORBIDDEN_TEXT = re.compile(r"<\s*/?\s*think\b|raw_response", re.IGNORECASE)
_MAX_JSON_BYTES = 2_000_000
_MAX_MEMBERS = 64
# Teto por provedor: um catálogo corrompido não vira uma nuvem de dezenas de milhares.
_MAX_MODELOS_POR_PROVEDOR = 400
_ARQUIVO_DE_MODELOS = re.compile(r"models-[A-Za-z0-9][A-Za-z0-9._:-]{0,120}\.json")
_MAX_VOTES = 256

_EVENT_KIND: dict[str, OperationalKind] = {
    "task_created": "activity",
    "task_assigned": "activity",
    "call_started": "activity",
    "call_completed": "activity",
    "temporary_created": "temporary-file",
    "temporary_discarded": "temporary-file",
    "evidence_recorded": "evidence",
    "proposal_created": "proposal",
    "quorum_started": "quorum-panel",
    "vote_requested": "quorum-vote",
    "vote_received": "quorum-vote",
    "quorum_decided": "quorum-decision",
    "promotion_started": "activity",
    "promotion_completed": "activity",
    "commit_created": "commit",
    "corpus_changed": "commit",
}

_EVENT_LABEL = {
    "task_created": "Tarefa criada",
    "task_assigned": "Tarefa atribuída",
    "call_started": "Chamada iniciada",
    "call_completed": "Chamada concluída",
    "temporary_created": "Temporário criado",
    "temporary_discarded": "Temporário descartado",
    "evidence_recorded": "Evidência registrada",
    "proposal_created": "Proposta criada",
    "quorum_started": "Quórum iniciado",
    "vote_requested": "Voto solicitado",
    "vote_received": "Voto recebido",
    "quorum_decided": "Quórum decidido",
    "promotion_started": "Promoção iniciada",
    "promotion_completed": "Promoção concluída",
    "commit_created": "Commit criado",
    "corpus_changed": "Corpus alterado",
}

_EVENT_PALETTE = {
    "activity": "D06",
    "temporary-file": "D03",
    "evidence": "D05",
    "proposal": "D09",
    "quorum-panel": "D08",
    "quorum-vote": "D06",
    "quorum-decision": "D04",
    "commit": "D04",
}


def _node(
    identifier: str,
    kind: OperationalKind,
    title: str,
    *,
    palette_token: str,
    short: str | None = None,
    at: str = "2026-08-02T12:00:00+00:00",
    domain: dict[str, str] = DEMO_DOMAIN,
    canonical_state: str | None = None,
    operational: dict[str, Any] | None = None,
) -> dict[str, Any]:
    node: dict[str, Any] = {
        "id": identifier,
        "title": title,
        "shortLabel": short or title,
        "path": None,
        "kind": kind,
        "layer": "operational",
        "canonicalState": canonical_state or STATE_BY_KIND[kind],
        "epistemicStatus": "not-specified",
        "domainId": domain["id"],
        "domainLabel": domain["label"],
        "anchorMocId": None,
        "mocIds": [],
        "claimCount": 0,
        "incomingDegree": 0,
        "outgoingDegree": 0,
        "degreeByRelation": {},
        "createdAt": at,
        "updatedAt": at,
        "verifiedAt": None,
        "visual": {
            "paletteToken": palette_token,
            "lodClass": 1,
            "labelPriority": 1,
            "isAnchor": False,
        },
    }
    if operational:
        node["operational"] = operational
    return node


def _edge(
    source: str,
    target: str,
    relation: str,
    *,
    matched_by: str = "demo",
) -> dict[str, Any]:
    return {
        "source": source,
        "target": target,
        "kind": "operational",
        "layer": "operational",
        "relations": [relation],
        "primaryRelation": relation,
        "weight": 1,
        "matchedBy": matched_by,
    }


def demo_trail() -> dict[str, list[dict[str, Any]]]:
    """Uma execução que deu commit e outra que foi rejeitada.

    Duas trilhas, porque um único caminho feliz não mostraria que atividade pode
    terminar em rejeição — que é justamente o que o observador precisa reconhecer.
    """
    nodes = [
        _node("op/agente/revisor", "agent", "Agente revisor", palette_token="D06"),
        _node(
            "op/atividade/varredura",
            "activity",
            "Varredura de lacunas",
            palette_token="D06",
        ),
        _node("op/evidencia/doi", "evidence", "DOI resolvido", palette_token="D05"),
        _node("op/proposta/claim-novo", "proposal", "Claim candidato", palette_token="D09"),
        _node("op/commit/aceito", "commit", "Commit consolidado", palette_token="D04"),
        _node("op/atividade/segunda", "activity", "Segunda varredura", palette_token="D06"),
        _node("op/proposta/recusada", "proposal", "Claim sem fonte", palette_token="D09"),
        _node(
            "op/rejeicao/sem-fonte",
            "rejection",
            "Rejeitado: DOI não resolveu",
            palette_token="D01",
        ),
        _node("op/temp/rascunho", "temporary-file", "Rascunho", palette_token="D03"),
        _node(
            "op/demo/quorum/panel",
            "quorum-panel",
            "Painel de demonstração",
            palette_token="D08",
            domain=QUORUM_DOMAIN,
            operational={"panelId": "demo"},
        ),
        _node(
            "op/demo/quorum/member",
            "quorum-member",
            "groq · modelo-demo",
            palette_token="D06",
            domain=QUORUM_DOMAIN,
            operational={
                "panelId": "demo",
                "provider": "groq",
                "endpoint": "modelo-demo",
                "family": "demo",
            },
        ),
        _node(
            "op/demo/quorum/vote",
            "quorum-vote",
            "Voto: approve",
            palette_token="D04",
            domain=QUORUM_DOMAIN,
            operational={
                "panelId": "demo",
                "decision": "approve",
                "confidence": 0.8,
                "reasoningBlockDetected": False,
                "reasoningBlockRemoved": False,
            },
        ),
        _node(
            "op/demo/quorum/decision",
            "quorum-decision",
            "Decisão: promote",
            palette_token="D04",
            domain=QUORUM_DOMAIN,
            operational={
                "panelId": "demo",
                "action": "promote",
                "tally": {"approve": 1},
            },
        ),
    ]
    edges = [
        _edge("op/agente/revisor", "op/atividade/varredura", "operational"),
        _edge("op/atividade/varredura", "op/evidencia/doi", "evidence"),
        _edge("op/evidencia/doi", "op/proposta/claim-novo", "evidence"),
        _edge("op/proposta/claim-novo", "op/commit/aceito", "operational"),
        _edge("op/agente/revisor", "op/atividade/segunda", "operational"),
        _edge("op/atividade/segunda", "op/proposta/recusada", "operational"),
        _edge("op/proposta/recusada", "op/rejeicao/sem-fonte", "operational"),
        _edge("op/atividade/segunda", "op/temp/rascunho", "operational"),
        _edge("op/demo/quorum/panel", "op/demo/quorum/member", "operational"),
        _edge("op/demo/quorum/member", "op/demo/quorum/vote", "operational"),
        _edge("op/demo/quorum/vote", "op/demo/quorum/decision", "operational"),
    ]
    return {"nodes": nodes, "edges": edges}


def event_trails(events: Sequence[OperationalEvent]) -> dict[str, list[dict[str, Any]]]:
    """Projeta eventos sanitizados sem reler ou reconstruir o corpus.

    O próprio evento vira nó temporal. Atores são compartilhados e a sequência só
    cria aresta quando dois passos declaram a mesma tarefa ou entidade; proximidade no
    relógio, sozinha, não fabrica relação operacional.
    """
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    actors: dict[str, str] = {}
    last_by_task: dict[str, str] = {}
    last_by_entity: dict[str, str] = {}

    for event in sorted(events, key=lambda item: item.revision):
        event_node_id = f"op/event/{event.id}"
        if event.actor is not None:
            actor_node_id = actors.get(event.actor)
            if actor_node_id is None:
                digest = hashlib.sha256(event.actor.encode()).hexdigest()[:12]
                actor_node_id = f"op/actor/{digest}"
                actors[event.actor] = actor_node_id
                nodes.append(
                    _node(
                        actor_node_id,
                        "agent",
                        event.actor,
                        short=event.actor[:48],
                        at=event.timestamp,
                        palette_token="D06",
                        operational={"actor": event.actor},
                    )
                )
            edges.append(
                _edge(actor_node_id, event_node_id, "operational", matched_by="event")
            )

        kind = _EVENT_KIND[event.type]
        operational: dict[str, Any] = {
            "eventId": event.id,
            "runtimeRevision": event.revision,
            "eventType": event.type,
        }
        for key in ("actor", "provider", "endpoint", "task", "entity"):
            value = getattr(event, key)
            if value is not None:
                operational[key] = value
        if event.before:
            operational["before"] = event.before
        if event.after:
            operational["after"] = event.after
        if event.metadata:
            operational["metadata"] = event.metadata

        subject = event.entity or event.task or event.provider
        label = _EVENT_LABEL[event.type]
        title = f"{label}: {subject}" if subject else label
        nodes.append(
            _node(
                event_node_id,
                kind,
                title,
                short=label,
                at=event.timestamp,
                palette_token=_EVENT_PALETTE[kind],
                operational=operational,
            )
        )

        predecessors: set[str] = set()
        if event.task is not None and event.task in last_by_task:
            predecessors.add(last_by_task[event.task])
        if event.entity is not None and event.entity in last_by_entity:
            predecessors.add(last_by_entity[event.entity])
        edges.extend(
            _edge(source, event_node_id, "operational", matched_by="event")
            for source in sorted(predecessors)
        )
        if event.task is not None:
            last_by_task[event.task] = event_node_id
        if event.entity is not None:
            last_by_entity[event.entity] = event_node_id

    return _with_degrees({"nodes": nodes, "edges": edges})


def runtime_snapshot(events: Sequence[OperationalEvent]) -> dict[str, Any]:
    """Snapshot próprio do runtime; sua revisão nunca deriva do fingerprint do corpus."""
    ordered = sorted(events, key=lambda item: item.revision)
    return {
        "runtimeRevision": ordered[-1].revision if ordered else 0,
        "events": [event.to_dict() for event in ordered],
        "operational": event_trails(ordered),
    }


def _catalogo_de_endpoints(state_dir: Path | None) -> list[tuple[str, str, str]]:
    """O acervo de modelos, do **catálogo descoberto** cruzado com a sonda.

    Havia duas fontes e só uma estava sendo lida. O registro de endpoints guarda o que
    já foi **sondado** — 30 modelos —, e a descoberta guarda o que cada provedor
    **oferece**: 193, com 102 só na nvidia. Mostrar apenas o sondado dava a impressão de
    um acervo de poucas unidades quando ele tem centenas.

    As duas se somam, e cada uma responde pelo que sabe: a descoberta diz o que existe, a
    sonda diz o que respondeu. Modelo descoberto e nunca sondado entra como
    `not_tested` — que é a verdade sobre ele, e é diferente de estar fora do plano.

    Fora do plano é o que a sonda observou como `unavailable`, e esses **saem de cena**:
    o acervo é o que está à disposição, e listar o que não atende com o mesmo peso do que
    atende é o tipo de omissão que faz a nuvem mentir.
    """
    if state_dir is None:
        return []
    sondados: dict[tuple[str, str], str] = {}
    registro = _read_json(state_dir / "endpoints.json", state_dir)
    if isinstance(registro, dict) and isinstance(registro.get("endpoints"), dict):
        for item in registro["endpoints"].values():
            if not isinstance(item, dict):
                continue
            provider = _safe_text(item.get("provider"), limit=80)
            endpoint = _safe_text(item.get("endpoint_id"), limit=180)
            estado = _safe_text(item.get("observed_status"), limit=40)
            if provider is None or endpoint is None:
                continue
            sondados[(provider, endpoint)] = estado or "desconhecido"

    descobertos: list[tuple[str, str]] = []
    indice = _read_json(state_dir / "models-discovery.json", state_dir)
    if isinstance(indice, dict) and isinstance(indice.get("providers"), dict):
        for arquivo in indice["providers"].values():
            nome = _safe_text(arquivo, limit=180)
            if nome is None or _ARQUIVO_DE_MODELOS.fullmatch(nome) is None:
                continue
            pagina = _read_json(state_dir / nome, state_dir)
            if not isinstance(pagina, dict) or not isinstance(pagina.get("models"), list):
                continue
            for modelo in pagina["models"][:_MAX_MODELOS_POR_PROVEDOR]:
                if not isinstance(modelo, dict) or modelo.get("available") is False:
                    continue
                provider = _safe_text(modelo.get("provider"), limit=80)
                endpoint = _safe_text(modelo.get("endpoint_id"), limit=180)
                if provider is None or endpoint is None:
                    continue
                descobertos.append((provider, endpoint))

    catalogo: list[tuple[str, str, str]] = []
    vistos: set[tuple[str, str]] = set()
    for chave in [*descobertos, *sondados]:
        if chave in vistos:
            continue
        vistos.add(chave)
        estado = sondados.get(chave, "not_tested")
        # Fora do plano gratuito não entra em cena.
        if estado == "unavailable":
            continue
        catalogo.append((chave[0], chave[1], estado))
    return catalogo


# Quantos painéis persistidos entram na projeção. A trilha SSE mostra o que
# está acontecendo agora; isto é o observatório recente, não o arquivo inteiro.
_MAX_PAINEIS_NA_PROJECAO = 24


def _paineis_para_projetar(raiz: Path, *, include_history: bool, limit: int) -> list[Path]:
    try:
        candidatos = [path for path in raiz.iterdir() if _safe_panel_directory(path, raiz)]
    except OSError:
        return []
    if include_history:
        return sorted(candidatos, key=lambda path: path.name)
    if limit <= 0:
        return []
    def recencia(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0
    candidatos.sort(key=recencia, reverse=True)
    return candidatos[:limit]


def quorum_trails(
    root: Path,
    state_dir: Path | None = None,
    *,
    include_history: bool = False,
    limit: int = _MAX_PAINEIS_NA_PROJECAO,
) -> dict[str, list[dict[str, Any]]]:
    """Catálogo de modelos e o observatório recente de quórum.

    Relê no máximo ``limit`` painéis, os mais recentes por mtime. Sem teto o GET
    lia 1712 diretórios e a cena caía. ``include_history`` desliga o teto — só
    teste e auditoria.

    Diretórios, links simbólicos, arquivos grandes e JSON parcial são tratados como
    entrada hostil: o painel afetado é ignorado e a projeção do corpus continua viva.
    """
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    raiz = root.resolve(strict=False)
    if not raiz.is_dir() or root.is_symlink():
        return {"nodes": nodes, "edges": edges}

    for directory in _paineis_para_projetar(
        raiz, include_history=include_history, limit=limit
    ):
        panel = _project_panel(directory, raiz)
        nodes.extend(panel["nodes"])
        edges.extend(panel["edges"])

    registro = _model_registry(edges, _catalogo_de_endpoints(state_dir))
    nodes.extend(registro["nodes"])
    edges.extend(registro["edges"])
    return _with_degrees({"nodes": nodes, "edges": edges})


# Como cada estado observado se lê, e com que solidez o painel é desenhado.
#
# O terceiro elemento é o `canonicalState`, que já governa a opacidade da placa: um
# modelo confirmado é sólido, um que responde sem entregar texto é translúcido, e um
# fora do plano é o mais fraco dos três. Assim o acervo se lê em silhueta, antes de
# qualquer palavra — e um catálogo que mostrasse todos com o mesmo peso mentiria.
_ESTADO_DO_ENDPOINT: dict[str, tuple[str, str]] = {
    "ok": ("Responde no plano gratuito.", "canonical"),
    "reachable": ("Alcançável, mas não devolveu texto na sonda.", "proposed"),
    "rate_limited": ("Alcançável, com limite de taxa atingido na sonda.", "proposed"),
    "account_exhausted": ("Conta sem crédito neste provedor.", "temporary"),
    "auth": ("Recusado por credencial.", "temporary"),
    "unavailable": ("Fora do plano gratuito neste provedor.", "temporary"),
    "error": ("A sonda falhou.", "temporary"),
}


def _model_registry(
    edges: list[dict[str, Any]],
    catalogo: list[tuple[str, str, str]],
) -> dict[str, list[dict[str, Any]]]:
    """A nuvem de modelos: um nó por provedor, um por modelo, e nada repetido.

    Ela nasce do **acervo** — o registro de endpoints, que é o que existe à disposição —
    e a participação em quóruns entra por cima, contada das arestas já emitidas. As duas
    fontes se somam em vez de se substituírem: um modelo do acervo que nunca foi chamado
    aparece com zero execuções, e um que participou sem estar no acervo aparece assim
    mesmo, porque escondê-lo esconderia justamente a divergência entre os dois registros.

    A contagem de execuções vira conteúdo do painel, que é o que dá ao provedor a mesma
    leitura que um MOC tem no corpus: quantos e quais estão sob ele.
    """
    usos: dict[str, int] = {}
    for edge in edges:
        if edge.get("matchedBy") != "quorum-model":
            continue
        usos[edge["target"]] = usos.get(edge["target"], 0) + 1

    # provedor -> endpoint -> (execuções, estado observado)
    por_provedor: dict[str, dict[str, tuple[int, str]]] = {
        nome: {} for nome in _PROVIDER_TOKENS
    }
    for provider, endpoint, estado in catalogo:
        por_provedor.setdefault(provider, {})[endpoint] = (
            usos.get(_model_id(provider, endpoint), 0),
            estado,
        )
    for identifier, contagem in usos.items():
        provider, endpoint = identifier[len("op/model/") :].split("/", 1)
        modelos = por_provedor.setdefault(provider, {})
        if endpoint in modelos:
            modelos[endpoint] = (contagem, modelos[endpoint][1])
        else:
            # Participou sem constar do acervo: o registro de endpoints está atrasado,
            # e é melhor a nuvem mostrar a divergência do que escondê-la.
            modelos[endpoint] = (contagem, "desconhecido")
    if not por_provedor:
        return {"nodes": [], "edges": []}

    nodes: list[dict[str, Any]] = []
    novas: list[dict[str, Any]] = []
    for ordem, provider in enumerate(sorted(por_provedor)):
        modelos = por_provedor[provider]
        token = _palette_token(provider, ordem)
        execucoes = sum(contagem for contagem, _ in modelos.values())
        disponiveis = sum(1 for _, estado in modelos.values() if estado == "ok")
        provider_node_id = _provider_id(provider)
        nodes.append(
            _node(
                provider_node_id,
                "agent",
                f"Provedor — {provider}",
                short=provider,
                domain=PROVIDER_DOMAIN,
                palette_token=token,
                canonical_state="canonical",
                operational={
                    "provider": provider,
                    "modelCount": len(modelos),
                    "availableCount": disponiveis,
                    "executionCount": execucoes,
                },
            )
        )
        nodes[-1]["visual"]["isAnchor"] = True
        for endpoint in sorted(modelos):
            contagem, estado = modelos[endpoint]
            _, solidez = _ESTADO_DO_ENDPOINT.get(estado, ("", "temporary"))
            nodes.append(
                _node(
                    _model_id(provider, endpoint),
                    "quorum-member",
                    f"{provider} · {endpoint}",
                    short=endpoint,
                    domain=MODEL_DOMAIN,
                    palette_token=token,
                    canonical_state=solidez,
                    operational={
                        "provider": provider,
                        "endpoint": endpoint,
                        "executionCount": contagem,
                        "endpointStatus": estado,
                    },
                )
            )
            novas.append(
                _edge(
                    _model_id(provider, endpoint),
                    provider_node_id,
                    "operational",
                    matched_by="model-provider",
                )
            )
    return {"nodes": nodes, "edges": novas}


def worker_nodes() -> list[dict[str, Any]]:
    """Um nó por papel do trabalho, para a configuração dele ter placa.

    A identidade é estática — nome, classe, resumo e área saem de `roles.py` — e o
    estado vivo não entra aqui de propósito: quem está rodando, com que modelo e com
    quantas simultâneas é o painel de controle que responde, e ele responde agora,
    não na hora em que a projeção foi gravada. Repetir esse estado no arquivo faria a
    placa afirmar uma resolução que pode ter mudado desde então.

    Sem aresta estática por escolha: o provedor a que um papel é resolvido depende do
    AUTO e do catálogo do instante, e uma linha gravada aqui apontaria para o modelo de
    ontem.
    """
    nodes: list[dict[str, Any]] = []
    for ordem, role in enumerate(ROLES.values()):
        avalia = role.reviews_others
        nodes.append(
            _node(
                f"op/worker/{role.name}",
                "agent",
                f"Trabalhador — {role.name}",
                short=role.name,
                domain=WORKER_DOMAIN,
                # Avaliador e produtor se distinguem pela cor porque é a distinção que
                # governa o quórum: só quem avalia conta para o mínimo de votos.
                palette_token=worker_palette_token(ordem, reviews_others=avalia),
                canonical_state="canonical",
                operational={
                    "role": role.name,
                    "workerClass": "avaliador" if avalia else "produtor",
                    "summary": role.summary,
                    "area": role.area,
                    "concurrencyMax": role.max_concurrency,
                },
            )
        )
        nodes[-1]["visual"]["isAnchor"] = True
    return nodes


def _safe_panel_directory(path: Path, root: Path) -> bool:
    if _PANEL_ID.fullmatch(path.name) is None or path.is_symlink():
        return False
    try:
        return path.resolve(strict=True).is_relative_to(root) and path.is_dir()
    except OSError:
        return False


def _read_json(path: Path, root: Path) -> Any | None:
    """Lê JSON regular, confinado e pequeno; qualquer desvio é ausência."""
    try:
        resolved = path.resolve(strict=True)
        info = path.lstat()
        if (
            path.is_symlink()
            or not resolved.is_relative_to(root)
            or not stat.S_ISREG(info.st_mode)
            or info.st_size > _MAX_JSON_BYTES
        ):
            return None
        payload = orjson.loads(path.read_bytes())
    except (OSError, orjson.JSONDecodeError):
        return None
    return payload


def _safe_text(value: object, *, limit: int = 180) -> str | None:
    if not isinstance(value, str):
        return None
    compact = " ".join(value.split()).strip()
    if not compact or len(compact) > limit:
        return None
    if _FORBIDDEN_TEXT.search(compact) or _SECRET.search(compact):
        return None
    return compact


def _resumo(value: object, *, limit: int = 180) -> str | None:
    """Uma frase legível a partir de um campo de texto do artefato.

    Diferente de `_safe_text`, que recusa texto acima do limite, aqui o texto longo é
    **cortado na fronteira de frase**. A diferença importa: a avaliação de um voto tem
    parágrafos, e recusá-la inteira por ser longa era o que deixava o painel sem nada
    a dizer enquanto o dado existia em disco.

    O que não muda é a recusa: bloco de raciocínio e coisa parecida com segredo
    continuam derrubando o campo, e nenhum texto passa sem essa checagem.
    """
    if not isinstance(value, str):
        return None
    compact = " ".join(value.split()).strip()
    if not compact:
        return None
    if _FORBIDDEN_TEXT.search(compact) or _SECRET.search(compact):
        return None
    if len(compact) <= limit:
        return compact
    corte = compact[:limit]
    ponto = max(corte.rfind(". "), corte.rfind("; "))
    return (corte[: ponto + 1] if ponto > limit // 2 else corte.rstrip() + "…").strip()


def _primeiro_texto(items: object, *chaves: str, limit: int = 180) -> str | None:
    """A primeira frase utilizável de uma lista de evidências ou de questões."""
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, str):
            frase = _resumo(item, limit=limit)
            if frase:
                return frase
        elif isinstance(item, dict):
            for chave in chaves:
                frase = _resumo(item.get(chave), limit=limit)
                if frase:
                    return frase
    return None


def _avaliacao(evidence: object) -> str | None:
    """A primeira evidência, dita como frase.

    O esquema guarda `claim` com a afirmação e `assessment` com o veredicto — muitas
    vezes uma palavra só, como `supported`. Projetar o veredicto sozinho produzia um
    painel que dizia "Examinou: supported", que é pior que não dizer nada. A frase junta
    os dois, e cai para o que existir se um deles faltar.
    """
    if not isinstance(evidence, list):
        return None
    for item in evidence:
        if isinstance(item, str):
            frase = _resumo(item)
            if frase:
                return frase
        if not isinstance(item, dict):
            continue
        claim = _resumo(item.get("claim"), limit=160)
        veredicto = _safe_text(item.get("assessment"), limit=160)
        if claim and veredicto:
            return f"{claim} — {veredicto}"
        if claim:
            return claim
        avaliado = _resumo(item.get("assessment"))
        if avaliado:
            return avaliado
    return None


def _safe_time(value: object) -> str | None:
    text = _safe_text(value, limit=64)
    return text if text and "T" in text else None


def _file_time(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(timespec="seconds")
    except OSError:
        return datetime.now(UTC).isoformat(timespec="seconds")


def _confidence(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if 0 <= number <= 1 else None


def _reasoning_flags(record: dict[str, Any]) -> dict[str, bool]:
    result: dict[str, bool] = {}
    detected = record.get("reasoning_block_detected")
    removed = record.get("reasoning_block_removed")
    if isinstance(detected, bool):
        result["reasoningBlockDetected"] = detected
    if isinstance(removed, bool):
        result["reasoningBlockRemoved"] = removed
    return result


def _reviewer(record: dict[str, Any]) -> tuple[str, str, str] | None:
    candidate = record.get("reviewer")
    source = candidate if isinstance(candidate, dict) else record
    provider = _safe_text(source.get("provider"), limit=80)
    endpoint = _safe_text(source.get("endpoint_id", source.get("endpoint")), limit=180)
    family = _safe_text(source.get("family"), limit=100)
    if provider is None or endpoint is None or family is None:
        return None
    return provider, endpoint, family


def _panel_operational(
    panel_id: str,
    task_payload: dict[str, Any],
    proposal: dict[str, Any],
    proposer: tuple[str, str, str],
) -> dict[str, Any]:
    """O que o painel tem a dizer sobre a própria execução, em linguagem natural.

    A tarefa e a proposta já estavam gravadas; o painel chegava à cena declarando só o
    `panelId` e por isso aparecia como caixa sem conteúdo. O que entra aqui é o pedido,
    quem propôs e o começo do que foi proposto — nada de resposta bruta de modelo, que
    `_resumo` recusaria de qualquer forma ao encontrar bloco de raciocínio.
    """
    operational: dict[str, Any] = {"panelId": panel_id}
    tarefa = _resumo(task_payload.get("prompt"), limit=220)
    if tarefa:
        operational["task"] = tarefa
    entidade = _safe_text(
        (task_payload.get("context") or {}).get("corpus_entity")
        if isinstance(task_payload.get("context"), dict)
        else None,
        limit=180,
    )
    if entidade:
        operational["entity"] = entidade
    candidato = _resumo(proposal.get("final_response"), limit=240)
    if candidato:
        operational["candidate"] = candidato
    operational["provider"], operational["endpoint"], operational["family"] = proposer
    operational["role"] = "proponente"
    return operational


def _project_panel(directory: Path, root: Path) -> dict[str, list[dict[str, Any]]]:
    panel_id = directory.name
    task = _read_json(directory / "task.json", root)
    members_file = _read_json(directory / "members.json", root)
    if not isinstance(task, dict) or not isinstance(members_file, list):
        return {"nodes": [], "edges": []}
    persisted_id = _safe_text(task.get("panel_id"), limit=128)
    if persisted_id != panel_id:
        return {"nodes": [], "edges": []}
    task_payload = task.get("task")
    proposal = task.get("proposal")
    if not isinstance(task_payload, dict) or not isinstance(proposal, dict):
        return {"nodes": [], "edges": []}
    proposer_payload = proposal.get("proposer")
    if not isinstance(proposer_payload, dict):
        return {"nodes": [], "edges": []}
    proposer = _reviewer(proposer_payload)
    if proposer is None or proposer_payload.get("role_name") != "proponente":
        return {"nodes": [], "edges": []}

    created_at = _file_time(directory / "task.json")
    panel_node_id = f"op/quorum/{panel_id}/panel"
    nodes = [
        _node(
            panel_node_id,
            "quorum-panel",
            f"Painel {panel_id}",
            short=f"Painel {panel_id[:18]}",
            at=created_at,
            domain=QUORUM_DOMAIN,
            operational=_panel_operational(panel_id, task_payload, proposal, proposer),
            palette_token="D08",
        )
    ]
    edges: list[dict[str, Any]] = []

    # A ligação entre as nuvens: a execução aponta para a nota que ela delibera.
    #
    # Cada frame era um mundo fechado — o observatório se ligava por dentro e o corpus
    # também, e nada dizia sobre **o que** uma execução tratava. A aresta atravessa os
    # dois: quem olha o painel de quórum vê de onde ele veio, e quem olha a nota vê que
    # ela foi discutida. Se a nota não estiver na projeção, a aresta é descartada pelo
    # filtro de `with_runtime_quorum` em vez de apontar para o vazio.
    entidade = _safe_text(
        (task_payload.get("context") or {}).get("corpus_entity")
        if isinstance(task_payload.get("context"), dict)
        else None,
        limit=300,
    )
    if entidade:
        edges.append(
            _edge(
                panel_node_id,
                entidade.removesuffix(".md"),
                "operational",
                matched_by="quorum-entity",
            )
        )

    members = members_file
    member_ids: dict[tuple[str, str, str], str] = {}
    for item in members[:_MAX_MEMBERS]:
        if not isinstance(item, dict):
            continue
        reviewer = _reviewer(item)
        if (
            reviewer is None
            or reviewer in member_ids
            or _safe_text(item.get("role_name"), limit=80) is None
        ):
            continue
        # O membro **não** vira painel próprio. Eram 114 placas para 7 modelos: cada
        # execução redesenhava os mesmos avaliadores, e a nuvem de modelos era uma
        # repetição, não um mapa. A identidade agora é canônica — um nó por modelo, no
        # registro montado em `quorum_trails` — e a execução apenas aponta para ele.
        provider, endpoint, _family = reviewer
        member_ids[reviewer] = _model_id(provider, endpoint)
        edges.append(
            _edge(
                panel_node_id,
                _model_id(provider, endpoint),
                "operational",
                matched_by="quorum-model",
            )
        )

    if (
        len(member_ids) < 3
        or proposer in member_ids
        or len({member[0] for member in member_ids}) < 2
        or len({member[2] for member in member_ids}) < 2
    ):
        return {"nodes": [], "edges": []}

    votes_dir = directory / "votes"
    votes: list[dict[str, Any]] = []
    vote_node_ids: list[str] = []
    voted: set[tuple[str, str, str]] = set()
    if _safe_subdirectory(votes_dir, root):
        try:
            vote_paths = sorted(votes_dir.glob("*.json"), key=lambda path: path.name)
        except OSError:
            vote_paths = []
        for vote_path in vote_paths[:_MAX_VOTES]:
            if _PANEL_ID.fullmatch(vote_path.stem) is None:
                continue
            record = _read_json(vote_path, root)
            if not isinstance(record, dict):
                continue
            structured = record.get("structured_vote")
            if not isinstance(structured, dict):
                continue
            decision = structured.get("decision")
            confidence = _confidence(structured.get("confidence"))
            schema_valid = record.get("schema_valid")
            if (
                decision not in VOTE_DECISIONS
                or confidence is None
                or not isinstance(schema_valid, bool)
                or structured.get("recommended_action") not in QUORUM_ACTIONS
                or (not schema_valid and decision != "abstain")
            ):
                continue
            reviewer = _reviewer(record)
            if reviewer is None or reviewer not in member_ids or reviewer in voted:
                continue
            voted.add(reviewer)
            vote_provider, vote_endpoint, vote_family = reviewer
            vote_node_id = f"op/quorum/{panel_id}/vote/{vote_path.stem}"
            vote_operational: dict[str, Any] = {
                "panelId": panel_id,
                "decision": decision,
                "confidence": confidence,
                **_reasoning_flags(record),
            }
            vote_operational["provider"] = vote_provider
            vote_operational["endpoint"] = vote_endpoint
            vote_operational["family"] = vote_family
            # A deliberação em linguagem natural, que já estava em disco e não chegava
            # à cena: o que o avaliador examinou, e o que o incomodou.
            avaliacao = _avaliacao(structured.get("evidence"))
            if avaliacao:
                vote_operational["assessment"] = avaliacao
            dificuldade = _primeiro_texto(
                structured.get("blocking_issues"), "issue", "description", "text"
            )
            if dificuldade:
                vote_operational["blockingIssue"] = dificuldade
            papel = _safe_text(record.get("reviewer", {}).get("role_name"), limit=64)
            if papel:
                vote_operational["role"] = papel
            nodes.append(
                _node(
                    vote_node_id,
                    "quorum-vote",
                    f"Voto: {decision} · {vote_provider}",
                    short=decision,
                    at=created_at,
                    domain=QUORUM_DOMAIN,
                    operational=vote_operational,
                    palette_token={
                        "approve": "D04",
                        "revise": "D03",
                        "reject": "D01",
                        "abstain": "D06",
                    }[decision],
                )
            )
            # O voto pende do **painel**, não do modelo. Ligá-lo ao modelo canônico
            # mandava 112 arestas atravessarem a cena até a nuvem de modelos, e a
            # execução deixava de ser um conjunto fechado. Quem votou continua dito
            # pelo próprio voto, que carrega provedor e endpoint.
            edges.append(
                _edge(panel_node_id, vote_node_id, "operational", matched_by="quorum")
            )
            votes.append(structured)
            vote_node_ids.append(vote_node_id)

    decision_file = _read_json(directory / "decision.json", root)
    if (
        isinstance(decision_file, dict)
        and _safe_text(decision_file.get("panel_id"), limit=128) == panel_id
    ):
        payload = decision_file
        if isinstance(payload, dict):
            action = payload.get(
                "outcome", payload.get("action", payload.get("recommended_action"))
            )
            if action in QUORUM_ACTIONS:
                decision_node_id = f"op/quorum/{panel_id}/decision"
                tally = _tally(payload.get("tally"), votes)
                decision_operational: dict[str, Any] = {
                    "panelId": panel_id,
                    "action": action,
                    "tally": tally,
                }
                confidence = _confidence(payload.get("confidence"))
                if confidence is not None:
                    decision_operational["confidence"] = confidence
                motivo = _resumo(payload.get("reason"))
                if motivo:
                    decision_operational["reason"] = motivo
                # A recusa estrutural mora em `structural_failures`, não no `reason`.
                # Sem isto o painel de decisão dizia só "falha estrutural objetiva
                # registrada" — o rótulo do gate — e a regra da política que quebrou
                # (wikilink sem relation, claim sem ID) ficava no disco.
                dificuldade = _primeiro_texto(
                    payload.get("structural_failures"), "issue"
                )
                if dificuldade:
                    decision_operational["blockingIssue"] = dificuldade
                sintese = _resumo(payload.get("synthesis"), limit=260)
                if sintese:
                    decision_operational["synthesis"] = sintese
                for campo, chave in (
                    ("valid_vote_count", "validVotes"),
                    ("provider_count", "providerCount"),
                    ("family_count", "familyCount"),
                ):
                    valor = payload.get(campo)
                    if isinstance(valor, int) and 0 <= valor <= 99:
                        decision_operational[chave] = valor
                nodes.append(
                    _node(
                        decision_node_id,
                        "quorum-decision",
                        f"Decisão: {action}",
                        short=action,
                        at=_safe_time(payload.get("decided_at")) or created_at,
                        domain=QUORUM_DOMAIN,
                        operational=decision_operational,
                        palette_token={
                            "promote": "D04",
                            "revise": "D03",
                            "reject": "D01",
                            "escalate": "D09",
                        }[action],
                    )
                )
                sources = vote_node_ids or [panel_node_id]
                edges.extend(
                    _edge(source, decision_node_id, "operational", matched_by="quorum")
                    for source in sources
                )

    return {"nodes": nodes, "edges": edges}


def _safe_subdirectory(path: Path, root: Path) -> bool:
    try:
        return (
            not path.is_symlink()
            and path.is_dir()
            and path.resolve(strict=True).is_relative_to(root)
        )
    except OSError:
        return False


def _tally(raw: object, votes: list[dict[str, Any]]) -> dict[str, int]:
    if isinstance(raw, dict):
        parsed = {
            decision: count
            for decision, count in raw.items()
            if decision in VOTE_DECISIONS
            and isinstance(count, int)
            and not isinstance(count, bool)
            and count >= 0
        }
        if parsed:
            return dict(sorted(parsed.items()))
    counts = Counter(vote.get("decision") for vote in votes)
    return {decision: counts.get(decision, 0) for decision in sorted(VOTE_DECISIONS)}


def _with_degrees(
    layer: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    incoming: Counter[str] = Counter()
    outgoing: Counter[str] = Counter()
    relations: dict[str, Counter[str]] = {}
    for edge in layer["edges"]:
        outgoing[edge["source"]] += 1
        incoming[edge["target"]] += 1
        relation = edge["primaryRelation"]
        relations.setdefault(edge["source"], Counter())[relation] += 1
        relations.setdefault(edge["target"], Counter())[relation] += 1
    for node in layer["nodes"]:
        identifier = node["id"]
        node["incomingDegree"] = incoming[identifier]
        node["outgoingDegree"] = outgoing[identifier]
        node["degreeByRelation"] = dict(sorted(relations.get(identifier, {}).items()))
        node["visual"]["labelPriority"] = incoming[identifier] + outgoing[identifier]
    return layer


def build_operational(
    *,
    demo: bool,
    quorum_root: Path | None = None,
    state_dir: Path | None = None,
    include_history: bool = False,
) -> tuple[dict[str, list[dict[str, Any]]], str]:
    """Camada operacional e sua origem explícita; falha de leitura nunca vira demo."""
    demo_layer = demo_trail() if demo else {"nodes": [], "edges": []}
    quorum_layer = (
        quorum_trails(quorum_root, state_dir, include_history=include_history)
        if quorum_root
        else {"nodes": [], "edges": []}
    )
    # Os trabalhadores acompanham a existência da camada operacional, e não a de uma
    # execução deles: um papel que nunca rodou continua sendo configurável, e é a placa
    # dele que responde por isso. Sem camada operacional nenhuma, porém, eles não
    # entram — projeção de corpus limpo não inventa operação, e sete nós fixos seriam
    # exatamente o dado de exemplo que a fronteira proíbe.
    operacional = bool(demo_layer["nodes"] or quorum_layer["nodes"])
    layer = _with_degrees(
        {
            "nodes": [
                *demo_layer["nodes"],
                *quorum_layer["nodes"],
                *(worker_nodes() if operacional else []),
            ],
            "edges": [*demo_layer["edges"], *quorum_layer["edges"]],
        }
    )
    if demo and quorum_layer["nodes"]:
        return layer, "mixed"
    if demo:
        return layer, "demo"
    if quorum_layer["nodes"]:
        return layer, "quorum"
    return layer, "none"
