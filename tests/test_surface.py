"""A superfície do produto não versiona o diário que a construiu."""

from __future__ import annotations

from pathlib import Path

from tools.surface import arquivos_proibidos, e_construcao, verificar


def test_padroes_de_construcao() -> None:
    assert e_construcao("docs/HANDOFF-GROK-4.6-2026-08-14.md")
    assert e_construcao("docs/CICLO-1.1-FECHAMENTO-ATLAS-2026-08-02.md")
    assert e_construcao("docs/PROMPT-A-QWEN3.8MAX-AUTOCONTIDO-2026-08-04.md")
    assert e_construcao("docs/BOOTSTRAP-2026-07-30.md")
    assert e_construcao("docs/FRENTE-MORFOGENICA-2026-08-14.md")
    assert e_construcao("docs/audits/2026-08-31-ane-completa/AUDITORIA.md")
    assert e_construcao("docs/X-MCP.md")
    assert e_construcao(".claude/launch.json")


def test_produto_permanece() -> None:
    assert not e_construcao("docs/ADR-001-paleta-oklch.md")
    assert not e_construcao("docs/WORKER.md")
    assert not e_construcao("docs/SOURCE-RESOLVER.md")
    assert not e_construcao("docs/README.md")
    assert not e_construcao("AGENTS.md")
    assert not e_construcao("tools/audit.py")
    assert not e_construcao("knowledge/Índice.md")


def test_indice_git_esta_limpo(repo_root: Path) -> None:
    assert verificar(repo_root) == []
    assert arquivos_proibidos(["docs/WORKER.md", "docs/HANDOFF-x.md"]) == [
        "docs/HANDOFF-x.md"
    ]
