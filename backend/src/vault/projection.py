"""Contrato de projeção: a única forma do corpus que sai do backend.

Três regras governam este módulo.

**O navegador não recebe a máquina.** Nada de caminho absoluto, nada de conteúdo de
arquivo, nada de segredo. O corpus é identificado por uma impressão digital — o mesmo
manifesto SHA-256 que o auditor calcula — e não pelo lugar onde ele mora.

**Derivado é declarado.** Domínio, MOC de ancoragem, token de paleta e classe de LOD
não existem no corpus: são cálculos desta camada. Todos aparecem em
`meta.computedFields`, para que ninguém leia inferência como se fosse frontmatter.

**Ontologia desconhecida reprova.** Um `kind` que não está no mapa é deriva
ontológica, não um caso a tratar com valor padrão. Ausência é `null` ou
`not-specified`; presença desconhecida é erro.

O contrato é versionado: mudança incompatível sobe `CONTRACT_VERSION`, e o frontend
recusa uma versão maior do que conhece em vez de renderizar campos que não entende.
"""

from __future__ import annotations

import hashlib
import re
import threading
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from vault.corpus import CorpusReader, Note
from vault.operational import _MAX_PAINEIS_NA_PROJECAO, OPERATIONAL_KINDS, build_operational

CONTRACT_VERSION = "1.1.0"

EpistemicKind = Literal["note", "moc", "reference", "register"]
EntityKind = EpistemicKind | Literal[
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
CanonicalState = Literal["canonical", "proposed", "temporary", "rejected", "archived"]

# O corpus escreve `kind` em português; o contrato usa o vocabulário do dossiê.
KIND_MAP: dict[str, EpistemicKind] = {
    "nota": "note",
    "moc": "moc",
    "referência": "reference",
    "registro": "register",
}

EPISTEMIC_STATUSES = frozenset(
    {
        "established",
        "supported",
        "model-dependent",
        "hypothesis",
        "speculative",
        "mixed",
        "operational",
        "quarantine",
        "not-specified",
    }
)

RELATION_FAMILIES = (
    "navigation",
    "prerequisite",
    "extends",
    "contrasts",
    "evidence",
    "operational",
    "historical",
)

# Tokens da paleta OKLCH do dossiê. A associação token↔domínio é calculada por ordem
# alfabética do identificador de domínio: estável entre execuções e sem depender de
# uma tabela que precisaria ser editada a cada domínio novo.
PALETTE_TOKENS = tuple(f"D{n:02d}" for n in range(1, 13))

# Quanto menor, mais cedo o rótulo aparece ao aproximar a câmera.
LOD_CLASS_BY_KIND: dict[EpistemicKind, int] = {
    "moc": 0,
    "register": 1,
    "reference": 1,
    "note": 2,
}

# Quanto de texto de claim e de resumo o contrato admite por campo. O corte é na
# fronteira de frase, e o que não coube fica declarado — nunca truncado em silêncio.
CLAIM_STATEMENT_LIMIT = 420
CLAIM_EVIDENCE_LIMIT = 320
SUMMARY_LIMIT = 700

COMPUTED_FIELDS = (
    "domainId",
    "domainLabel",
    "anchorMocId",
    "mocIds",
    "incomingDegree",
    "outgoingDegree",
    "degreeByRelation",
    "visual.paletteToken",
    "visual.lodClass",
    "visual.labelPriority",
    "visual.isAnchor",
    "edges[kind=aggregated]",
    "summary",
)


class ProjectionError(RuntimeError):
    """O corpus não pode ser projetado sem inventar informação."""


@dataclass(frozen=True, slots=True)
class ProjectionSource:
    """De onde a projeção veio. `demo` nunca é consequência de falha do corpus."""

    kind: Literal["corpus", "demo"]
    fingerprint: str


def _frontmatter_date(note: Note, campo: str) -> str | None:
    raw = note.frontmatter.get(campo)
    return str(raw) if raw not in (None, "") else None


def _entity_kind(note: Note) -> EpistemicKind:
    raw = note.kind
    if raw is None:
        raise ProjectionError(
            f"{note.id!r} não declara `kind` no frontmatter; o contrato não adivinha "
            "tipo de entidade a partir do nome do arquivo."
        )
    mapped = KIND_MAP.get(raw)
    if mapped is None:
        raise ProjectionError(
            f"{note.id!r} declara kind={raw!r}, fora do vocabulário conhecido "
            f"{sorted(KIND_MAP)}. Ontologia nova exige decisão, não valor padrão."
        )
    return mapped


def _epistemic_status(note: Note) -> str:
    raw = note.epistemic_status
    if raw is None:
        return "not-specified"
    if raw not in EPISTEMIC_STATUSES:
        raise ProjectionError(
            f"{note.id!r} declara epistemic_status={raw!r}, fora do vocabulário "
            f"{sorted(EPISTEMIC_STATUSES)}."
        )
    return raw


def corpus_fingerprint(reader: CorpusReader) -> str:
    """Mesmo manifesto que `tools/audit.py` calcula, pelo mesmo método.

    Coincidir com o auditor é a graça: a impressão digital que o frontend exibe é
    conferível com uma linha de terminal, e serve de chave de cache do layout.
    """
    linhas = []
    for path in sorted(reader.root.rglob("*.md")):
        try:
            relativo = path.relative_to(reader.root)
        except ValueError:  # pragma: no cover — rglob só devolve descendentes
            continue
        if any(parte.startswith(".") for parte in relativo.parts):
            continue
        if path.name in {"AGENTS.md", "CLAUDE.md", "README.md"}:
            continue
        linhas.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {relativo}")
    return hashlib.sha256("\n".join(linhas).encode()).hexdigest()


def _anchor_moc(
    note: Note,
    mocs_por_dominio: dict[str, list[str]],
    mocs_que_apontam: dict[str, list[str]],
) -> str | None:
    """MOC de ancoragem, para o layout. Dica visual calculada, não fato do corpus.

    Precedência: o único MOC do domínio; senão o MOC do domínio que de fato aponta
    para a nota; senão nenhum. Nunca um MOC de outro domínio, e nunca um desempate
    arbitrário entre dois MOCs que reivindicam a mesma nota — nesse caso a nota fica
    sem âncora e o layout a posiciona pelo domínio.

    Um MOC é âncora, não ancorado: sem isso o único MOC do domínio ancoraria em si
    mesmo e o layout tentaria orbitá-lo em torno do próprio centro.
    """
    if note.kind == "moc":
        return None
    do_dominio = mocs_por_dominio.get(note.domain_id, [])
    if len(do_dominio) == 1:
        return do_dominio[0]
    apontam = [moc for moc in mocs_que_apontam.get(note.id, []) if moc in do_dominio]
    return apontam[0] if len(apontam) == 1 else None


# Marcação que o painel não desenha: ele escreve texto puro, e deixar `**` passar fazia
# a ênfase aparecer como dois asteriscos no meio da frase.
_ENFASE = re.compile(r"\*\*|__|(?<!\w)[*_](?!\s)|(?<!\s)[*_](?!\w)")
_CODIGO = re.compile(r"`+")
_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_COMENTARIO = re.compile(r"<!--.*?-->", re.DOTALL)


def _texto_puro(texto: str) -> str:
    """Tira a marcação, preservando o que ela marcava.

    O painel escreve texto puro numa malha de glifos: não há negrito para aplicar, e o
    `**` sobrava na frase como dois asteriscos. Wikilink vira o alvo escrito, que é o
    que um leitor esperaria ver, e comentário de relação sai inteiro — ele é instrução
    para o auditor, não conteúdo da nota.
    """
    limpo = _COMENTARIO.sub(" ", texto)
    limpo = _WIKILINK.sub(r"\1", limpo)
    limpo = _LINK.sub(r"\1", limpo)
    limpo = _CODIGO.sub("", limpo)
    return _ENFASE.sub("", limpo)


def _corte(texto: str, limite: int) -> str:
    """Corta na fronteira de frase, e nunca no meio de uma palavra."""
    compacto = " ".join(_texto_puro(texto).split()).strip()
    if len(compacto) <= limite:
        return compacto
    fatia = compacto[:limite]
    ponto = max(fatia.rfind(". "), fatia.rfind("; "), fatia.rfind(": "))
    if ponto > limite // 2:
        return fatia[: ponto + 1].strip()
    return (fatia.rsplit(" ", 1)[0] + "…").strip()


def _abertura(note: Note) -> str | None:
    """O primeiro parágrafo de prosa do corpo, sem cabeçalho nem tabela.

    A projeção levava só metadado: título, contagens e datas. Um painel de nota
    aberto mostrava frases **sobre** a nota e nenhuma linha **da** nota, e não havia o
    que rolar porque não havia conteúdo. Isto é a abertura — a resposta à pergunta que
    a nota se propõe —, e os claims logo abaixo carregam o resto.
    """
    paragrafo: list[str] = []
    for linha in note.body.splitlines():
        despido = linha.strip()
        if despido.startswith("#") or despido.startswith("|") or despido.startswith("---"):
            if paragrafo:
                break
            continue
        if not despido:
            if paragrafo:
                break
            continue
        paragrafo.append(despido)
    texto = " ".join(paragrafo)
    return _corte(texto, SUMMARY_LIMIT) if texto else None


def build_projection(reader: CorpusReader, *, demo_operational: bool = False) -> dict[str, Any]:
    """Projeção completa e sanitizada do corpus configurado."""
    graph = reader.build_graph()
    notes = {note.id: note for note in reader.list_notes()}

    mocs_por_dominio: dict[str, list[str]] = {}
    for note in notes.values():
        if note.kind == "moc":
            mocs_por_dominio.setdefault(note.domain_id, []).append(note.id)
    for lista in mocs_por_dominio.values():
        lista.sort()

    mocs_que_apontam: dict[str, list[str]] = {}
    for origem, destino in graph.edges():
        if notes[origem].kind == "moc":
            mocs_que_apontam.setdefault(destino, []).append(origem)

    dominios = sorted({note.domain_id for note in notes.values()})
    if len(dominios) > len(PALETTE_TOKENS):
        raise ProjectionError(
            f"{len(dominios)} domínios para {len(PALETTE_TOKENS)} tokens de paleta; "
            "a paleta precisa crescer antes de o corpus crescer."
        )
    token_por_dominio = dict(zip(dominios, PALETTE_TOKENS, strict=False))
    rotulo_por_dominio = {note.domain_id: note.domain for note in notes.values()}

    grau_por_relacao: dict[str, Counter[str]] = {node: Counter() for node in graph.nodes}
    for origem, destino, data in graph.edges(data=True):
        for relacao in data["relations"]:
            grau_por_relacao[origem][relacao] += 1
            grau_por_relacao[destino][relacao] += 1

    nodes: list[dict[str, Any]] = []
    for node_id in sorted(graph.nodes):
        note = notes[node_id]
        kind = _entity_kind(note)
        claims = [
            {
                "id": claim.id,
                "statement": _corte(claim.statement, CLAIM_STATEMENT_LIMIT),
                "status": claim.status,
                "evidence": _corte(claim.evidence, CLAIM_EVIDENCE_LIMIT) or None,
            }
            for claim in reader.extract_claims(note)
        ]
        ancora = _anchor_moc(note, mocs_por_dominio, mocs_que_apontam)
        grau_entrada = graph.in_degree(node_id)
        grau_saida = graph.out_degree(node_id)
        nodes.append(
            {
                "id": note.id,
                "title": note.title,
                "shortLabel": note.stem,
                "path": note.path.as_posix(),
                "kind": kind,
                # A rede epistêmica é persistente; a operacional é temporal. Elas
                # coexistem na cena e não se misturam ontologicamente.
                "layer": "epistemic",
                # Tudo em knowledge/ já passou por decisão humana e commit.
                "canonicalState": "canonical",
                "epistemicStatus": _epistemic_status(note),
                "domainId": note.domain_id,
                "domainLabel": note.domain,
                "anchorMocId": ancora,
                "mocIds": sorted(mocs_que_apontam.get(note.id, [])),
                "claimCount": graph.nodes[node_id]["claims"],
                "incomingDegree": grau_entrada,
                "outgoingDegree": grau_saida,
                "degreeByRelation": dict(sorted(grau_por_relacao[node_id].items())),
                # O conteúdo da nota, e não apenas o que se sabe sobre ela. Os claims
                # são a unidade epistêmica do corpus: afirmação, status do vocabulário
                # fechado e evidência. Vão para o navegador somente-leitura.
                "summary": _abertura(note),
                "claims": claims,
                "createdAt": _frontmatter_date(note, "created"),
                "updatedAt": _frontmatter_date(note, "updated"),
                "verifiedAt": _frontmatter_date(note, "verified_at"),
                "visual": {
                    "paletteToken": token_por_dominio[note.domain_id],
                    "lodClass": LOD_CLASS_BY_KIND[kind],
                    "labelPriority": grau_entrada + grau_saida,
                    "isAnchor": kind == "moc",
                },
            }
        )

    edges: list[dict[str, Any]] = []
    for origem, destino, data in sorted(graph.edges(data=True)):
        relacoes = sorted(data["relations"])
        edges.append(
            {
                "source": origem,
                "target": destino,
                "kind": "canonical",
                "layer": "epistemic",
                "relations": relacoes,
                "primaryRelation": relacoes[0] if relacoes else None,
                "weight": data["weight"],
                "matchedBy": data["matched_by"],
            }
        )

    edges.extend(_aggregate_between_mocs(nodes, edges))

    operacional, origem_operacional = build_operational(demo=demo_operational)
    nodes.extend(operacional["nodes"])
    edges.extend(operacional["edges"])

    fingerprint = corpus_fingerprint(reader)
    return {
        "meta": {
            "contractVersion": CONTRACT_VERSION,
            "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
            # Origem explícita. Não existe caminho de código que produza `demo`
            # por falha do corpus: `demo` só nasce de um pedido explícito.
            "source": "corpus",
            # A camada operacional tem origem própria: `none` é o caso normal, e
            # `demo` só aparece se alguém pediu explicitamente.
            "operationalSource": origem_operacional,
            "operationalKinds": list(OPERATIONAL_KINDS),
            "corpusFingerprint": fingerprint,
            "computedFields": list(COMPUTED_FIELDS),
            "relationFamilies": list(RELATION_FAMILIES),
            "domains": [
                {
                    "id": dominio,
                    "label": rotulo_por_dominio[dominio],
                    "paletteToken": token_por_dominio[dominio],
                    "mocIds": mocs_por_dominio.get(dominio, []),
                }
                for dominio in dominios
            ],
            "counts": {
                "notes": sum(1 for n in nodes if n["layer"] == "epistemic"),
                "operationalNodes": sum(1 for n in nodes if n["layer"] == "operational"),
                "canonicalEdges": sum(1 for e in edges if e["kind"] == "canonical"),
                "aggregatedEdges": sum(1 for e in edges if e["kind"] == "aggregated"),
                "wikilinks": sum(e["weight"] for e in edges if e["kind"] == "canonical"),
                "claims": sum(n["claimCount"] for n in nodes),
                "mocs": sum(1 for n in nodes if n["kind"] == "moc"),
            },
            "diagnostics": {
                "broken": graph.graph["broken"],
                "undeclared": graph.graph["undeclared"],
                "collisions": graph.graph["collisions"],
            },
        },
        "nodes": nodes,
        "edges": edges,
    }


def _stat_signature(path: Path) -> tuple[int, int]:
    try:
        stat = path.stat()
    except OSError:
        return (0, 0)
    return (stat.st_mtime_ns, stat.st_size)


def runtime_overlay_signature(
    quorum_root: Path, state_dir: Path | None = None
) -> tuple[Any, ...]:
    """Assinatura barata do overlay: teto de painéis por mtime + catálogo em disco.

    Não lê JSON. Invalida quando nasce/some um painel ou quando o observatório
    recente (os ``_MAX_PAINEIS_NA_PROJECAO`` mais novos) muda de recência.
    """
    root = quorum_root.resolve(strict=False)
    parts: list[Any] = [str(root)]
    if not root.is_dir():
        return tuple(parts)
    try:
        children = list(root.iterdir())
    except OSError:
        return tuple(parts)
    parts.append(len(children))
    recency: list[tuple[int, str]] = []
    for path in children:
        try:
            recency.append((path.stat().st_mtime_ns, path.name))
        except OSError:
            recency.append((0, path.name))
    recency.sort(reverse=True)
    parts.append(tuple(recency[:_MAX_PAINEIS_NA_PROJECAO]))
    if state_dir is None:
        return tuple(parts)
    state = state_dir.resolve(strict=False)
    parts.append(str(state))
    parts.append(_stat_signature(state / "endpoints.json"))
    parts.append(_stat_signature(state / "models-discovery.json"))
    try:
        catalogos = tuple(
            sorted(
                (path.name, _stat_signature(path))
                for path in state.iterdir()
                if path.name.startswith("models-") and path.suffix == ".json"
            )
        )
    except OSError:
        catalogos = ()
    parts.append(catalogos)
    return tuple(parts)


_OVERLAY_LOCK = threading.Lock()
_OVERLAY_CACHE: tuple[tuple[Any, ...], dict[str, list[dict[str, Any]]], str] | None = None


def clear_runtime_overlay_cache() -> None:
    """Só testes: o cache é por processo, e um tmp_path reutilizado mentiria."""
    global _OVERLAY_CACHE
    with _OVERLAY_LOCK:
        _OVERLAY_CACHE = None


def _cached_operational(
    quorum_root: Path, state_dir: Path | None
) -> tuple[dict[str, list[dict[str, Any]]], str]:
    global _OVERLAY_CACHE
    key = runtime_overlay_signature(quorum_root, state_dir)
    with _OVERLAY_LOCK:
        cached = _OVERLAY_CACHE
        if cached is not None and cached[0] == key:
            return cached[1], cached[2]
    operational, source = build_operational(
        demo=False, quorum_root=quorum_root, state_dir=state_dir
    )
    with _OVERLAY_LOCK:
        _OVERLAY_CACHE = (key, operational, source)
    return operational, source


def with_runtime_quorum(
    projection: dict[str, Any],
    quorum_root: Path,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    """Acrescenta o snapshot temporal sem mutar o snapshot vivo do corpus.

    O fingerprint continua identificando apenas `knowledge/`. Atualizar um painel de
    quórum não finge ser uma revisão do corpus e não invalida a memória espacial.

    O overlay é cacheado pela assinatura de mtime: o GET não relê JSON enquanto o
    observatório recente e o catálogo não mudarem.
    """
    operational, source = _cached_operational(quorum_root, state_dir)
    if source == "none":
        return projection

    existing_nodes = list(projection["nodes"])
    existing_ids = {node["id"] for node in existing_nodes}
    runtime_nodes = [node for node in operational["nodes"] if node["id"] not in existing_ids]
    runtime_ids = {node["id"] for node in runtime_nodes}
    all_ids = existing_ids | runtime_ids
    runtime_edges = [
        edge
        for edge in operational["edges"]
        if edge["source"] in all_ids and edge["target"] in all_ids
    ]
    if not runtime_nodes:
        return projection

    nodes = [*existing_nodes, *runtime_nodes]
    edges = [*projection["edges"], *runtime_edges]
    previous_source = projection["meta"].get("operationalSource", "none")
    operational_source = "mixed" if previous_source == "demo" else "quorum"
    counts = {
        **projection["meta"]["counts"],
        "operationalNodes": sum(node["layer"] == "operational" for node in nodes),
    }
    meta = {
        **projection["meta"],
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "operationalSource": operational_source,
        "counts": counts,
    }
    return {**projection, "meta": meta, "nodes": nodes, "edges": edges}


def _aggregate_between_mocs(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Filamentos inter-MOC: **uma aresta por par não ordenado** de âncoras.

    A visão global mostra a ponte entre dois territórios, não as dezenas de arestas
    que a compõem. Cada agregado declara de quantas arestas canônicas ele nasceu, para
    que a legenda possa dizer que é agregação e não relação declarada.

    A chave é o par não ordenado, e a distinção custou um defeito para aparecer.
    Chaveando por `(origem, destino)`, um par de MOCs com tráfego nos dois sentidos
    produzia **duas** entradas: 75 filamentos para 52 pares, com 23 pares recebendo dois
    tubos de flecha e espessura diferentes — os feixes paralelos que a auditoria viu na
    ponte interdisciplinar. Pior, em 10 desses pares cada tubo elegia uma relação
    dominante própria, e a mesma ponte declarava `prerequisite` num sentido e
    `contrasts` no outro.

    A direção não se perde: ela vira dado do agregado. `weightByDirection` guarda o peso
    de cada sentido, `relationsByDirection` as famílias de cada sentido, e `reciprocal`
    diz se os dois existem. O renderizador desenha uma conexão e recupera de lá tudo o
    que ela representa.
    """
    ancora_de: dict[str, str | None] = {}
    for node in nodes:
        ancora_de[node["id"]] = node["id"] if node["kind"] == "moc" else node["anchorMocId"]

    agregados: dict[tuple[str, str], Counter[str]] = {}
    contagem: Counter[tuple[str, str]] = Counter()
    # Peso e famílias por sentido, para a direção sobreviver à unificação do par.
    por_sentido: dict[tuple[str, str], Counter[str]] = {}
    peso_por_sentido: Counter[tuple[str, str]] = Counter()
    for edge in edges:
        if edge["kind"] != "canonical":
            continue
        origem = ancora_de.get(edge["source"])
        destino = ancora_de.get(edge["target"])
        if origem is None or destino is None or origem == destino:
            continue
        chave = (origem, destino) if origem < destino else (destino, origem)
        contagem[chave] += edge["weight"]
        balde = agregados.setdefault(chave, Counter())
        for relacao in edge["relations"]:
            balde[relacao] += 1
        sentido = (origem, destino)
        peso_por_sentido[sentido] += edge["weight"]
        do_sentido = por_sentido.setdefault(sentido, Counter())
        for relacao in edge["relations"]:
            do_sentido[relacao] += 1

    resultado = []
    for (a, b), relacoes in sorted(agregados.items()):
        dominante = max(sorted(relacoes.items()), key=lambda item: item[1])[0]
        ida = peso_por_sentido.get((a, b), 0)
        volta = peso_por_sentido.get((b, a), 0)
        resultado.append(
            {
                "source": a,
                "target": b,
                "kind": "aggregated",
                "layer": "epistemic",
                "relations": sorted(relacoes),
                "primaryRelation": dominante,
                "weight": contagem[(a, b)],
                "matchedBy": "computed",
                # Proveniência da unificação: quem desenha uma linha só precisa poder
                # dizer de quantas relações, em que sentidos e de que famílias ela veio.
                "weightByDirection": {"forward": ida, "backward": volta},
                "relationsByDirection": {
                    "forward": sorted(por_sentido.get((a, b), Counter())),
                    "backward": sorted(por_sentido.get((b, a), Counter())),
                },
                "reciprocal": ida > 0 and volta > 0,
            }
        )
    return resultado
