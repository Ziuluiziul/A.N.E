"""Deriva a fila do que o corpus e o runtime ainda não fecharam."""

from __future__ import annotations

import statistics
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from providers.registry import EndpointRegistry
from vault.autonomy.models import (
    PANEL_ROLES,
    AutonomousTask,
    TaskBudget,
    TaskKind,
    TaskOrigin,
    stable_task_id,
)
from vault.corpus import CorpusReader
from vault.promotion.patch import latex_break_reason, minutes_reason
from vault.quorum import QuorumStore

WEAK_STATUSES = {
    "open": 92,
    "hypothesis": 82,
    "speculative": 76,
    "model-dependent": 68,
}
_MAX_PER_SOURCE = 32
_META_PANEL_KINDS = frozenset(
    {TaskKind.DIVERGENCE_REVIEW.value, TaskKind.PROPOSAL_REVISION.value}
)
# Fan-out da capacidade ociosa: quantos painéis nascem por refresh, e com quantos
# endpoints cada um. Painel exige 4 endpoints; o lote de 4 deixa os revisores
# escolherem dentro dele sem disputar com as outras tarefas do mesmo refresh.
_IDLE_FAN_OUT = 8
_IDLE_ENDPOINTS_POR_TAREFA = 4
# Muda o fingerprint: tarefas antigas (sem criar nota) não bloqueiam as novas.
_REGIME = "liberdade-com-rigor-20260817"


def _idle_wave() -> str:
    """Onda UTC da capacidade ociosa: mesmo claim, outro dia → identidade nova.

    Tarefas antigas (sem `wave`, ou onda anterior) continuam terminais; `add_new`
    só aceita identidade inédita. Não inclui o lote de endpoints — isso inundou
    a fila com 2083 `idle_capacity`. Teto: `_IDLE_FAN_OUT` painéis por dia UTC.
    """
    return datetime.now(UTC).strftime("%Y-%m-%d")


class TaskGenerator:
    def __init__(
        self,
        reader: CorpusReader,
        *,
        quorum_root: Path,
        models_root: Path,
        registry: EndpointRegistry | None = None,
        idle_endpoints: list[str] | None = None,
    ) -> None:
        self.reader = reader
        self.quorum_root = Path(quorum_root)
        self.models_root = Path(models_root)
        self.registry = registry or EndpointRegistry()
        self.idle_endpoints = sorted(set(idle_endpoints or []))

    def generate(self) -> list[AutonomousTask]:
        notes = self.reader.list_notes()
        candidates = [
            *self._weak_claims(notes),
            *self._isolated_notes(notes),
            *self._underrepresented_domains(notes),
            *self._rejected_and_divergent_panels(),
            *self._endpoint_failures(),
            *self._idle_capacity(notes),
            *self._policy_review(notes),
            *self._corpus_expansion(notes),
            *self._corpus_defects(notes),
        ]
        unique: dict[str, AutonomousTask] = {}
        for task in candidates:
            current = unique.get(task.id)
            if current is None or task.priority > current.priority:
                unique[task.id] = task
        return sorted(unique.values(), key=lambda task: (-task.priority, task.id))

    def _task(
        self,
        *,
        origin: TaskOrigin,
        source: dict[str, Any],
        objective: str,
        priority: int,
        domain: str,
        kind: TaskKind,
        corpus_entity: str | None = None,
        metadata: dict[str, Any] | None = None,
        max_calls: int = 5,
        max_output_tokens: int = 4096,
    ) -> AutonomousTask:
        identifier, fingerprint = stable_task_id(origin, source)
        return AutonomousTask(
            id=identifier,
            origin=origin,
            objective=objective,
            priority=priority,
            domain=domain,
            kind=kind,
            required_roles=list(PANEL_ROLES),
            budget=TaskBudget(max_calls=max_calls, max_output_tokens=max_output_tokens),
            corpus_entity=corpus_entity,
            source_fingerprint=fingerprint,
            metadata=metadata or {},
        )

    def _weak_claims(self, notes: list[Any]) -> list[AutonomousTask]:
        found: list[AutonomousTask] = []
        for note in notes:
            for claim in self.reader.extract_claims(note):
                priority = WEAK_STATUSES.get(claim.status)
                if priority is None:
                    continue
                source = {
                    "note": note.id,
                    "claim": claim.id,
                    "status": claim.status,
                    "statement": claim.statement,
                    "evidence": claim.evidence,
                    "regime": _REGIME,
                }
                objective = (
                    f"Reavalie o claim {claim.id} em {note.path.as_posix()}. "
                    f"Estado atual: {claim.status}. Afirmação: "
                    f"{claim.statement}. Evidência/limite registrado: {claim.evidence}. "
                    "Pode alterar esta nota, criar nota completa que a fundamente, "
                    "ou reconsiderar a Política se o vocabulário for o obstáculo. "
                    "Identificador só entra resolvido; ausência de evidência não é "
                    "refutação; analogia não cria aresta."
                )
                found.append(
                    self._task(
                        origin=TaskOrigin.WEAK_CLAIM,
                        source=source,
                        objective=objective,
                        priority=priority,
                        domain=note.domain,
                        kind=TaskKind.CORPUS_REVIEW,
                        corpus_entity=note.path.as_posix(),
                        metadata={"claim_id": claim.id, "claim_status": claim.status},
                    )
                )
        return sorted(found, key=lambda task: (-task.priority, task.id))[:_MAX_PER_SOURCE]

    def _isolated_notes(self, notes: list[Any]) -> list[AutonomousTask]:
        """Ilha = zero wikilink resolvido para outro domínio, não grau global.

        Física com 5 arestas internas era pulada (`degree > 1`) e nunca virava
        tarefa: a fila ficava só em identidades já terminais. A ponte que o
        corpus precisa é inter-domínio; DOI/ISBN/arXiv, não analogia.
        """
        index = self.reader.index(notes)
        by_id = {note.id: note for note in notes}
        degree: Counter[str] = Counter()
        inter: Counter[str] = Counter()
        for note in notes:
            for link in self.reader.extract_links(note):
                resolution = self.reader.resolve_link(link, index)
                if resolution.target_id is None:
                    continue
                degree[note.id] += 1
                degree[resolution.target_id] += 1
                alvo = by_id.get(resolution.target_id)
                if alvo is not None and alvo.domain_id != note.domain_id:
                    inter[note.id] += 1
        destinos_por_dominio: dict[str, list[str]] = {}
        for outra in notes:
            if outra.kind == "moc":
                continue
            destinos_por_dominio.setdefault(outra.domain_id, []).append(outra.stem)
        found: list[AutonomousTask] = []
        for note in notes:
            if note.kind == "moc" or inter[note.id] > 0:
                continue
            source = {
                "note": note.id,
                "inter_domain": 0,
                "regime": _REGIME,
                "kind": "inter-domain-bridge-v3",
                "wave": _idle_wave(),
            }
            alvo = note.path.as_posix()
            destinos: list[str] = []
            for dominio, stems in sorted(destinos_por_dominio.items()):
                if dominio == note.domain_id:
                    continue
                destinos.extend(stems[:3])
                if len(destinos) >= 8:
                    break
            lista = ", ".join(f"[[{stem}]]" for stem in destinos[:8]) or "(nenhuma)"
            found.append(
                self._task(
                    origin=TaskOrigin.ISOLATED_NOTE,
                    source=source,
                    objective=(
                        f"A nota {alvo} não liga a outro domínio "
                        f"(grau interno {degree[note.id]}, inter-domínio 0). "
                        f"Um único replace do path {alvo} (relativo a knowledge/, "
                        "sem prefixo knowledge/), conteúdo Markdown integral. "
                        "Acrescente no máximo um wikilink na forma "
                        "[[Stem]] <!-- relation:TIPO --> usando um Stem já existente "
                        f"de outro domínio (exemplos: {lista}) e TIPO em "
                        "navigation, prerequisite, extends, contrasts, evidence, "
                        "operational ou historical. Só se o conteúdo de uma for "
                        "usado pela outra. Fonte: DOI, ISBN ou arXiv já na nota "
                        "alvo ou na destino. Não use create. Não invente Stem. "
                        "Não reduza claims, wikilinks nem identificadores. "
                        "Wikilink sem relation: ou quebrado reprova."
                    ),
                    priority=64,
                    domain=note.domain,
                    kind=TaskKind.CORPUS_REVIEW,
                    corpus_entity=alvo,
                    metadata={
                        "degree": degree[note.id],
                        "inter_domain": 0,
                        "bridge": "inter-domain",
                        "lock_targets": True,
                    },
                )
            )
        return found[:_MAX_PER_SOURCE]

    def _underrepresented_domains(self, notes: list[Any]) -> list[AutonomousTask]:
        counts = Counter(note.domain for note in notes if note.domain != "raiz")
        if not counts:
            return []
        median = statistics.median(counts.values())
        threshold = max(2, int(median // 2))
        found: list[AutonomousTask] = []
        for domain, count in sorted(counts.items()):
            if count > threshold:
                continue
            source = {
                "domain": domain,
                "notes": count,
                "median": median,
                "regime": _REGIME,
            }
            found.append(
                self._task(
                    origin=TaskOrigin.UNDERREPRESENTED_DOMAIN,
                    source=source,
                    objective=(
                        f"O domínio {domain} tem {count} notas diante de mediana {median:g}. "
                        "Preencha a lacuna com no máximo uma nota nova completa "
                        "(frontmatter, claims com ID único, wikilinks tipados, sem "
                        "placeholder) ou fortaleça uma existente. Identificador só "
                        "entra resolvido. A Política pode ser emendada se for ela "
                        "que impede a lacuna honesta."
                    ),
                    priority=58,
                    domain=domain,
                    kind=TaskKind.CORPUS_REVIEW,
                    metadata={"note_count": count, "median_note_count": median},
                )
            )
        return found

    def _rejected_and_divergent_panels(self) -> list[AutonomousTask]:
        revisions: list[AutonomousTask] = []
        divergences: list[AutonomousTask] = []
        store = QuorumStore(self.quorum_root)
        for panel in store.list_panels():
            decision = panel.decision
            if decision is None or panel.task.kind in _META_PANEL_KINDS:
                continue
            entity = self._context_entity(panel.task.context)
            if entity is None:
                continue
            vote_decisions = {
                vote.structured_vote.decision.value
                for vote in panel.votes
                if vote.schema_valid
            }
            if decision.outcome.value == "reject":
                issues = [
                    issue
                    for vote in panel.votes
                    for issue in vote.structured_vote.blocking_issues
                ]
                source = {
                    "panel": panel.id,
                    "decision": decision.id,
                    "outcome": decision.outcome.value,
                    "issues": issues,
                }
                revisions.append(
                    self._task(
                        origin=TaskOrigin.REJECTED_PROPOSAL,
                        source=source,
                        objective=(
                            f"Reformule a proposta rejeitada no painel {panel.id}. Preserve "
                            f"o que era verificável e corrija apenas estes bloqueios: "
                            f"{'; '.join(issues) if issues else decision.reason}."
                        ),
                        priority=88,
                        domain=str(panel.task.context.get("domain") or "operacional"),
                        kind=TaskKind.PROPOSAL_REVISION,
                        corpus_entity=entity,
                        metadata={"panel_id": panel.id, "blocking_issues": issues[:20]},
                    )
                )
            if decision.outcome.value == "escalate" and len(vote_decisions) > 1:
                source = {
                    "panel": panel.id,
                    "decision": decision.id,
                    "votes": sorted(vote_decisions),
                }
                divergences.append(
                    self._task(
                        origin=TaskOrigin.MODEL_DIVERGENCE,
                        source=source,
                        objective=(
                            f"Explique e resolva a divergência do painel {panel.id}: decisões "
                            f"válidas {', '.join(sorted(vote_decisions))}. Não escolha por "
                            "maioria nominal; identifique qual diferença de evidência decide."
                        ),
                        priority=80,
                        domain=str(panel.task.context.get("domain") or "operacional"),
                        kind=TaskKind.DIVERGENCE_REVIEW,
                        corpus_entity=entity,
                        metadata={
                            "panel_id": panel.id,
                            "vote_decisions": sorted(vote_decisions),
                        },
                    )
                )
        return [
            *revisions[:_MAX_PER_SOURCE],
            *divergences[:_MAX_PER_SOURCE],
        ]

    @staticmethod
    def _context_entity(context: dict[str, Any]) -> str | None:
        raw = (
            context.get("corpus_path")
            or context.get("corpus_entity")
            or context.get("target")
        )
        return raw if isinstance(raw, str) and len(raw) <= 500 else None

    def _endpoint_failures(self) -> list[AutonomousTask]:
        found: list[AutonomousTask] = []
        for key, record in sorted(self.registry.records.items()):
            if record.observed_status in {"ok", "reachable"}:
                continue
            source = {
                "endpoint": key,
                "status": record.observed_status,
                "observed_at": record.observed_at,
                "detail": record.detail,
            }
            found.append(
                self._task(
                    origin=TaskOrigin.ENDPOINT_FAILURE,
                    source=source,
                    objective=(
                        f"Diagnostique a observação {record.observed_status} de {key}: "
                        f"{record.detail[:500]}. Não tente o mesmo endpoint nesta tarefa e "
                        "não trate falha de endpoint como falha do provedor inteiro."
                    ),
                    priority=44,
                    domain="operacional",
                    kind=TaskKind.ENDPOINT_DIAGNOSIS,
                    metadata={
                        "failed_endpoint": key,
                        "observed_status": record.observed_status,
                    },
                    max_calls=1,
                    max_output_tokens=768,
                )
            )
        return found[:_MAX_PER_SOURCE]

    def _idle_capacity(self, notes: list[Any]) -> list[AutonomousTask]:
        if not self.idle_endpoints:
            return []
        abertos = [
            (note, claim)
            for note in notes
            for claim in self.reader.extract_claims(note)
            if claim.status == "open"
        ]
        if not abertos:
            return []
        # Identidade é o claim, não o lote de endpoints. Incluir o lote no source
        # fazia cada rotação do acervo ocioso nascer tarefa nova — 2083 `idle_capacity`
        # na fila, a maioria já terminal, sem o corpus ter ganhado claim nenhum.
        lote = self.idle_endpoints[:_IDLE_ENDPOINTS_POR_TAREFA]
        tarefas: list[AutonomousTask] = []
        for note, claim in abertos[:_IDLE_FAN_OUT]:
            source = {
                "claim": claim.id,
                "note": note.id,
                "kind": "idle",
                "regime": _REGIME,
                "wave": _idle_wave(),
            }
            tarefas.append(
                self._task(
                    origin=TaskOrigin.IDLE_CAPACITY,
                    source=source,
                    objective=(
                        f"Há capacidade produtiva sem chamada recente em "
                        f"{', '.join(lote)}. Use uma única execução para "
                        f"procurar evidência que feche ou delimite {claim.id} em "
                        f"{note.path.as_posix()}; ausência de resultado mantém `open`."
                    ),
                    priority=52,
                    domain=note.domain,
                    kind=TaskKind.CORPUS_REVIEW,
                    corpus_entity=note.path.as_posix(),
                    metadata={"idle_endpoints": lote, "claim_id": claim.id},
                )
            )
        return tarefas

    def _policy_review(self, notes: list[Any]) -> list[AutonomousTask]:
        politica = next(
            (
                note
                for note in notes
                if "política epistêmica" in note.title.casefold()
                or note.path.as_posix().endswith("Política Epistêmica e de Linkagem.md")
            ),
            None,
        )
        if politica is None:
            return []
        texto = _texto_da_nota(self.reader, politica)
        if not _politica_omite_quorum(texto):
            return []
        caminho = politica.path.as_posix()
        return [
            self._task(
                origin=TaskOrigin.POLICY_REVIEW,
                source={
                    "note": politica.id,
                    "regime": _REGIME,
                    "defect": "regime-2026-08-03-ausente",
                },
                objective=(
                    f"Emende {caminho}: ainda exige revisão humana e não registra o "
                    "regime de 2026-08-03. Altere só as seções «Promoção e revisão» e "
                    "«Nota sobre esta política». Promoção de conhecimento é decidida "
                    "por quórum multimodelo (proponente fora da contagem; pelo menos "
                    "dois provedores). O Promoter é o único escritor de knowledge/. "
                    "Humano só em credenciais, OAuth interativo, comando "
                    "administrativo ou destrutivo, e consumo acima do orçamento. "
                    "`updated` muda a cada edição; `verified_at` só após verificação "
                    "real de fontes. Não afrouxar identificador resolvido, wikilink "
                    "tipado, claim com ID, nem placeholder. replace integral; só o "
                    "campo updated no frontmatter."
                ),
                priority=96,
                domain=politica.domain,
                kind=TaskKind.CORPUS_REVIEW,
                corpus_entity=caminho,
                metadata={"lock_targets": True, "allow_create": False},
            )
        ]

    def _corpus_defects(self, notes: list[Any]) -> list[AutonomousTask]:
        found: list[AutonomousTask] = []
        for note in notes:
            texto = _texto_da_nota(self.reader, note)
            motivos = [
                motivo
                for motivo in (
                    minutes_reason(texto),
                    latex_break_reason(texto),
                    _titulo_klein_corrompido(texto),
                )
                if motivo
            ]
            if not motivos:
                continue
            caminho = note.path.as_posix()
            found.append(
                self._task(
                    origin=TaskOrigin.CORPUS_DEFECT,
                    source={
                        "note": note.id,
                        "defects": motivos,
                        "regime": _REGIME,
                    },
                    objective=(
                        f"Restaure {caminho}. Defeitos: {'; '.join(motivos)}. "
                        "replace integral desta nota apenas. Recupere LaTeX íntegro, "
                        "apague ata de painel, restaure título canônico. O julgamento "
                        "do quórum fica no painel, não na nota. Atualize só `updated`. "
                        "Não mude status de claim, `verified_at`, nem invente "
                        "identificador."
                    ),
                    priority=97,
                    domain=note.domain,
                    kind=TaskKind.CORPUS_REVIEW,
                    corpus_entity=caminho,
                    metadata={
                        "lock_targets": True,
                        "allow_create": False,
                        "defects": motivos,
                    },
                )
            )
        return found[:_MAX_PER_SOURCE]

    def _corpus_expansion(self, notes: list[Any]) -> list[AutonomousTask]:
        found: list[AutonomousTask] = []
        for note in notes:
            if note.kind != "moc":
                continue
            trecho = _trecho_de_lacunas(note.body)
            if not trecho:
                continue
            found.append(
                self._task(
                    origin=TaskOrigin.CORPUS_EXPANSION,
                    source={"moc": note.id, "lacuna": trecho[:400], "regime": _REGIME},
                    objective=(
                        f"O MOC {note.path.as_posix()} declara estas lacunas: {trecho} "
                        "Crie no máximo uma nota NOVA completa que preencha a primeira "
                        "lacuna com consumidor real neste domínio. Frontmatter, claims "
                        "com ID único no formato CLM-DOMINIO-TOPICO-NNN, wikilinks com "
                        "relation do vocabulário, sem placeholder. Atualize o MOC só se "
                        "a nota nascer completa. Identificador só entra resolvido."
                    ),
                    priority=74,
                    domain=note.domain,
                    kind=TaskKind.CORPUS_REVIEW,
                    corpus_entity=note.path.as_posix(),
                    metadata={"lacuna": trecho[:400]},
                )
            )
        return found


def _texto_da_nota(reader: CorpusReader, note: Any) -> str:
    try:
        return (reader.root / note.path).read_text(encoding="utf-8")
    except OSError:
        return note.body


def _politica_omite_quorum(texto: str) -> bool:
    baixo = texto.casefold()
    return "quórum" not in baixo and "quorum" not in baixo


def _titulo_klein_corrompido(texto: str) -> str | None:
    if "cinco-dimensional Relativit" in texto:
        return "título alemão de Klein corrompido"
    return None


def _trecho_de_lacunas(body: str) -> str:
    linhas = body.splitlines()
    captura: list[str] = []
    ativo = False
    for linha in linhas:
        if linha.startswith("## ") and "lacuna" in linha.casefold():
            ativo = True
            continue
        if ativo and linha.startswith("## "):
            break
        if ativo:
            texto = linha.strip()
            if texto:
                captura.append(texto)
    return " ".join(captura).strip()

