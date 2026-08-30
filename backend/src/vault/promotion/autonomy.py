"""O caminho nativo quórum → promoção.

O quórum é a segunda autoridade legítima de promoção, ao lado do veredito humano
(`proposals.store`). A autorização nasce do painel decidido, não de uma identidade
pessoal — `PromotionAuthorization(source="quorum", ...)` — e o Promoter continua
dono de todas as guardas: alvo inalterado, digest intacto, auditoria
estrutural, proveniência completa. Este módulo só decide **quem** autoriza e
registra **o que** foi tentado num diário durável, o que torna a assimilação
idempotente — o mesmo fechamento não produz dois commits por replay de evento,
restart do worker ou recuperação de processo.

Contrato de ativação: apenas decisões fechadas **depois** da ativação da política
entram no caminho automático. Os painéis anteriores são uma coorte histórica —
valiosos para benchmark e calibração, fora da assimilação automática.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vault.promotion.patch import CorpusPatch
from vault.promotion.promoter import PATCH_DIGEST_KEY, PromotionRefused, ProposalPromoter
from vault.quorum.models import Panel

POLICY_VERSION = "quorum-v2"
POLICY_SCHEMA = 2
JOURNAL_SCHEMA = 1
POLICY_BUDGET_DEFAULTS = {
    "hard_ceiling_calls": 24,
    "expansion_margin_calls": 2,
    "observation_window": 8,
    "schema_failure_threshold": 0.5,
}

TERMINAL_STATES = frozenset({"promoted", "stale", "rejected"})
"""Estados finais do diário: um fechamento decidido não volta a ser promovido.

`failed` fica de fora de propósito: recusa operacional (working tree do operador,
falha transitória) pode ser reaplicada. Queimar a chave por árvore suja foi o
defeito que incinerou 43 aprovações em 2026-08.
"""


def _estado_da_recusa(mensagem: str) -> str:
    """Recusa epistêmica/estrutural é terminal; recusa operacional não."""
    if "alvo mudou desde a base" in mensagem:
        return "stale"
    operacional = (
        "árvore de trabalho suja",
        "local changes",
        "would be overwritten",
        "your local changes",
    )
    if any(marca in mensagem.casefold() for marca in operacional):
        return "failed"
    return "rejected"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _parse_iso(valor: str) -> datetime:
    return datetime.fromisoformat(valor.replace("Z", "+00:00"))


def _git(*args: str, cwd: Path) -> str:
    resultado = subprocess.run(  # noqa: S603 — argumentos fixos, sem shell
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if resultado.returncode != 0:
        detalhe = (resultado.stderr or resultado.stdout).strip()
        raise PromotionRefused(f"git {' '.join(args)} falhou: {detalhe}")
    return resultado.stdout.strip()


@dataclass(frozen=True, slots=True)
class PromotionAuthorization:
    """Quem autorizou e o que exatamente foi autorizado.

    `source` é a autoridade: `quorum` neste caminho, `human` no veredito manual do
    `proposals.store`. A promoção não acopla o commit à identidade de quem validou.
    """

    source: str
    policy_version: str
    decision_id: str
    panel_id: str
    proposal_id: str
    patch_digest: str


@dataclass(frozen=True, slots=True)
class Eligibility:
    """Veredito da política: entra no Promoter, ou por que não entra."""

    authorized: bool
    reason: str
    authorization: PromotionAuthorization | None = None


@dataclass(frozen=True, slots=True)
class PromotionReport:
    """Desfecho de uma tentativa de assimilação, para o worker registrar."""

    state: str
    detail: str
    commit: str | None = None


class PromotionJournal:
    """Diário append-only e fsyncado das tentativas de promoção autônoma.

    A chave — proposta + digest do patch + impressão dos alvos — é a identidade da
    tentativa. `promoted` é terminal; os demais terminais documentam por que a
    assimilação não aconteceu. Replay lê o diário antes de agir.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    @staticmethod
    def targets_fingerprint(targets: list[str]) -> str:
        canonico = json.dumps(sorted(targets), ensure_ascii=True)
        return hashlib.sha256(canonico.encode()).hexdigest()[:16]

    @staticmethod
    def key(proposal_id: str, patch_digest: str, targets_fingerprint: str) -> str:
        material = f"{proposal_id}\n{patch_digest}\n{targets_fingerprint}"
        return hashlib.sha256(material.encode()).hexdigest()[:32]

    def append(self, entry: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        linha = json.dumps(
            {**entry, "schema_version": JOURNAL_SCHEMA}, ensure_ascii=False
        )
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(linha + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def entries(self, key: str) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        lidas: list[dict[str, Any]] = []
        for linha in self.path.read_text(encoding="utf-8").splitlines():
            if not linha.strip():
                continue
            try:
                entrada = json.loads(linha)
            except json.JSONDecodeError:
                continue
            if entrada.get("key") == key:
                lidas.append(entrada)
        return lidas

    def current(self, key: str) -> dict[str, Any] | None:
        estado = self.entries(key)
        return estado[-1] if estado else None


class PromotionPolicy:
    """Decide se um fechamento entra no caminho autônomo.

    A ativação é idempotente e grava o momento em que a política entrou em vigor:
    decisões anteriores a ele são coorte histórica e ficam de fora, mesmo que o
    painel ainda esteja no disco. A política é ativada na subida do worker, antes
    de qualquer fechamento do ciclo, para que a primeira decisão do mesmo ciclo
    já esteja dentro do contrato.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def activate(self) -> str:
        """Grava o momento de ativação na primeira chamada; preserva o já gravado.

        Política legada (schema 1, sem bloco `budget`) é promovida a schema 2 **no
        lugar**, preservando o `activated_at` original: o contrato de causalidade
        (decisão posterior à ativação) não pode mudar de referência só porque o
        orçamento ganhou regras. O bloco `budget` entra com os defaults de código.
        """
        if self.path.is_file():
            dados = self._read()
            if dados.get("schema_version") == 1:
                dados = {
                    "schema_version": POLICY_SCHEMA,
                    "policy_version": POLICY_VERSION,
                    "activated_at": dados.get("activated_at") or _now(),
                    "budget": dict(POLICY_BUDGET_DEFAULTS),
                }
                self._escreve(dados, exclusivo=False)
                return str(dados["activated_at"])
            return dados["activated_at"]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        dados = {
            "schema_version": POLICY_SCHEMA,
            "policy_version": POLICY_VERSION,
            "activated_at": _now(),
            "budget": dict(POLICY_BUDGET_DEFAULTS),
        }
        self._escreve(dados, exclusivo=True)
        return dados["activated_at"]  # type: ignore[return-value]

    def _escreve(self, dados: dict[str, Any], *, exclusivo: bool) -> None:
        temporario = self.path.with_name(f".{self.path.name}.tmp")
        temporario.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        modo = "xb" if exclusivo else "wb"
        with temporario.open("rb") as origem, self.path.open(modo) as destino:
            destino.write(origem.read())
            destino.flush()
            os.fsync(destino.fileno())
        temporario.unlink(missing_ok=True)

    def _read(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def authorize(self, panel: Panel, patch: CorpusPatch) -> Eligibility:
        decisao = panel.decision
        if decisao is None or decisao.outcome.value != "promote":
            return Eligibility(False, "quórum não aprovou a promoção")
        esperado = panel.task.context.get(PATCH_DIGEST_KEY)
        if not isinstance(esperado, str) or esperado != patch.digest():
            return Eligibility(
                False, "digest do patch diverge do registrado no painel"
            )
        if not self.path.is_file():
            return Eligibility(False, "política de promoção ainda não ativada")
        ativada = _parse_iso(self._read()["activated_at"])
        if _parse_iso(decisao.decided_at) < ativada:
            return Eligibility(
                False,
                f"coorte pré-ativação: decisão de {decisao.decided_at} "
                f"anterior à ativação de {ativada.isoformat(timespec='seconds')}",
            )
        return Eligibility(
            True,
            "quórum autoriza a promoção",
            PromotionAuthorization(
                source="quorum",
                policy_version=POLICY_VERSION,
                decision_id=decisao.id,
                panel_id=panel.id,
                proposal_id=patch.proposal_id,
                patch_digest=patch.digest(),
            ),
        )


class QuorumPromotion:
    """Conduz um fechamento aprovado do quórum até o Promoter, uma única vez.

    O diário é a autoridade de idempotência: antes de agir, consulta-se o estado
    da tentativa. Depois do `promotion_pending`, o commit pode já ter existido
    antes do diário registrá-lo — a recuperação pergunta ao próprio repositório,
    pela mensagem padrão que carrega o id da proposta, em vez de reaplicar.
    """

    def __init__(
        self,
        *,
        journal: PromotionJournal,
        policy: PromotionPolicy,
        promoter: ProposalPromoter,
    ) -> None:
        self.journal = journal
        self.policy = policy
        self.promoter = promoter

    def promote(self, panel: Panel, patch: CorpusPatch) -> PromotionReport:
        elegibilidade = self.policy.authorize(panel, patch)
        if not elegibilidade.authorized:
            return PromotionReport("skipped", elegibilidade.reason)
        autorizacao = elegibilidade.authorization
        assert autorizacao is not None
        chave = PromotionJournal.key(
            autorizacao.proposal_id,
            autorizacao.patch_digest,
            PromotionJournal.targets_fingerprint(patch.targets),
        )
        base = {
            "key": chave,
            "source": autorizacao.source,
            "policy_version": autorizacao.policy_version,
            "decision_id": autorizacao.decision_id,
            "panel_id": autorizacao.panel_id,
            "proposal_id": autorizacao.proposal_id,
            "patch_digest": autorizacao.patch_digest,
        }
        atual = self.journal.current(chave)
        if atual is not None:
            if atual["state"] in TERMINAL_STATES:
                return PromotionReport(
                    "already_promoted",
                    f"diário registra {atual['state']} para este fechamento",
                    commit=atual.get("commit"),
                )
            # Crash entre o diário e o commit: o commit pode ter acontecido. O
            # repositório é a testemunha mais fiel — a mensagem padrão do Promoter
            # carrega o id da proposta.
            commit = self._commit_da_proposta(autorizacao.proposal_id)
            if commit is not None:
                self.journal.append(
                    {
                        **base,
                        "state": "promoted",
                        "commit": commit,
                        "at": _now(),
                        "detail": "recuperado de crash: o commit já existia",
                    }
                )
                return PromotionReport(
                    "already_promoted",
                    "recuperado de crash: o commit já existia",
                    commit=commit,
                )
        self.journal.append(
            {**base, "state": "eligible", "at": _now(), "detail": "autorizado pelo quórum"}
        )
        self.journal.append(
            {
                **base,
                "state": "promotion_pending",
                "at": _now(),
                "detail": "reivindicado para aplicação",
            }
        )
        self.journal.append(
            {**base, "state": "applying", "at": _now(), "detail": "promoter em andamento"}
        )
        try:
            resultado = self.promoter.promote(panel, patch)
        except PromotionRefused as recusa:
            mensagem = str(recusa)
            estado = _estado_da_recusa(mensagem)
            self.journal.append(
                {**base, "state": estado, "at": _now(), "detail": mensagem[:500]}
            )
            return PromotionReport(estado, mensagem)
        except Exception as erro:  # noqa: BLE001 — a promoção não pode derrubar o ciclo
            self.journal.append(
                {**base, "state": "failed", "at": _now(), "detail": str(erro)[:500]}
            )
            return PromotionReport("failed", str(erro)[:500])
        self.journal.append(
            {
                **base,
                "state": "promoted",
                "commit": resultado.commit,
                "at": _now(),
                "detail": "promoção aplicada e commitada",
            }
        )
        return PromotionReport(
            "promoted",
            f"promovido em {resultado.commit[:12]}",
            commit=resultado.commit,
        )

    def _commit_da_proposta(self, proposal_id: str) -> str | None:
        try:
            commits = _git(
                "log",
                "--all",
                "--format=%H",
                f"--grep=Promove proposta {proposal_id}",
                cwd=self.promoter.repo_root,
            )
        except PromotionRefused:
            return None
        linhas = [linha for linha in commits.splitlines() if linha]
        return linhas[0] if linhas else None