#!/usr/bin/env python3
"""Congela a evidência de ponta a ponta de uma promoção autônoma.

Uso:
    python3 tools/evidencia_de_promocao.py            # última promoção promovida
    python3 tools/evidencia_de_promocao.py PANEL_ID   # painel específico

O artefato junta o que cada peça registrou por conta própria — diário de promoção,
painel do quórum, decisão, histórico git e auditoria pós-commit — sem reescrever
nenhuma delas. Saída: stdout e docs/audits/<data>-primeira-promocao/evidencia.json.
Somente leitura sobre runtime/ e o repositório.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RUNTIME = RAIZ / "runtime"
DIARIO = RUNTIME / "promotion" / "promotions.jsonl"
QUORUM = RUNTIME / "quorum"
AUDIT_SCRIPT = RAIZ / "tools" / "audit.py"


def _ler_json(caminho: Path) -> dict | None:
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(RAIZ), *args],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _entradas_do_diario() -> list[dict]:
    linhas: list[dict] = []
    for linha in DIARIO.read_text(encoding="utf-8").splitlines():
        if linha.strip():
            linhas.append(json.loads(linha))
    return linhas


def _revisao_da_projecao() -> dict | None:
    """O que o navegador vê da projeção depois do commit: impressão digital + hora."""
    try:
        with urllib.request.urlopen(
            "http://localhost:8000/corpus/projection", timeout=5
        ) as resposta:
            payload = json.loads(resposta.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 — serviço fora do ar não derruba a evidência
        return None
    meta = payload.get("meta") or {}
    return {
        "corpus_fingerprint": meta.get("corpusFingerprint"),
        "generated_at": meta.get("generatedAt"),
    }


def _auditoria_pos_commit() -> dict:
    try:
        resultado = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT)],
            check=False,
            capture_output=True,
            text=True,
            cwd=RAIZ,
            timeout=120,
        )
    except Exception as erro:  # noqa: BLE001
        return {"ok": False, "erro": str(erro)}
    return {"ok": resultado.returncode == 0, "saida": resultado.stdout.strip()}


def congelar(panel_id: str | None) -> int:
    entradas = _entradas_do_diario()
    promovidas = [
        e for e in entradas if e.get("state") == "promoted" and e.get("commit")
    ]
    if not promovidas:
        print("nenhuma promoção concluída no diário", file=sys.stderr)
        return 1
    alvo = next(
        (e for e in promovidas if e.get("panel_id") == panel_id),
        None,
    ) if panel_id else promovidas[-1]
    if alvo is None:
        print(f"nenhuma promoção com panel_id {panel_id}", file=sys.stderr)
        return 1

    painel_dir = QUORUM / alvo["panel_id"]
    tarefa = _ler_json(painel_dir / "task.json")
    decisao = _ler_json(painel_dir / "decision.json")
    patch = _ler_json(painel_dir / "patch.json")
    alvos = (
        sorted({op.get("path") for op in patch.get("operations", []) if op.get("path")})
        if patch
        else []
    )
    commit = alvo["commit"]
    mensagem = _git("log", "-1", "--format=%s", commit) or ""

    # O caminho de estados no diário, para este panel, em ordem.
    transicoes = [
        {
            "state": e["state"],
            "at": e.get("at"),
            "detail": e.get("detail", ""),
        }
        for e in entradas
        if e.get("panel_id") == alvo["panel_id"]
    ]
    autorizacao = next(
        (e for e in transicoes if e["state"] == "eligible"), None
    )
    fingerprint = alvo.get("targets_fingerprint")
    tarefa_panel = (tarefa or {}).get("task") or {}

    artefato = {
        "schema_version": 1,
        "capturado_em": datetime.now(UTC).isoformat(),
        "panel_id": alvo["panel_id"],
        "task_id": tarefa_panel.get("id")
        or (tarefa or {}).get("context", {}).get("autonomous_task_id"),
        "proposal_id": alvo.get("proposal_id"),
        "quorum_id": alvo["panel_id"],
        "decision_id": alvo.get("decision_id"),
        "policy_version": alvo.get("policy_version"),
        "authorization_timestamp": (autorizacao or {}).get("at"),
        "patch_digest": alvo.get("patch_digest"),
        "targets_fingerprint": fingerprint
        or alvo.get("key"),
        "targets": alvos,
        "promotion_state_transitions": transicoes,
        "commit_sha": commit,
        "commit_message": mensagem,
        "knowledge_entity_changed": alvos,
        "post_commit_audit": _auditoria_pos_commit(),
        "reprojection": _revisao_da_projecao(),
        "decisao": {
            "outcome": (decisao or {}).get("outcome"),
            "status": (decisao or {}).get("status"),
            "valid_vote_count": (decisao or {}).get("valid_vote_count"),
            "provider_count": (decisao or {}).get("provider_count"),
            "decided_at": (decisao or {}).get("decided_at"),
        },
    }

    destino_dir = RAIZ / "docs" / "audits" / (
        f"{datetime.now(UTC).strftime('%Y-%m-%d')}-primeira-promocao"
    )
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / "evidencia.json"
    destino.write_text(json.dumps(artefato, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(artefato, ensure_ascii=False, indent=2))
    print(f"\nevidência gravada em {destino}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    panel = sys.argv[1] if len(sys.argv) > 1 else None
    raise SystemExit(congelar(panel))
