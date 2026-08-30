# Comandos do projeto. Cada alvo é uma linha legível: nada de orquestração
# escondida. `uv run` resolve o ambiente a partir de uv.lock antes de executar.

.PHONY: setup audit audit-reducao test lint dev icon retire-tasks outcomes promote worker backend frontend discover-models endpoints probe-streams smoke-providers work quorum corpus-graph workspace-oauth

setup:  ## Cria .venv e instala dependências Python e Node pelos lockfiles
	uv sync --frozen --all-groups
	cd frontend && pnpm install --frozen-lockfile
	mkdir -p runtime/proposals runtime/logs runtime/state runtime/quorum

# `python3` do sistema, de propósito: o auditor é stdlib puro e precisa rodar
# mesmo antes de existir .venv — é o gate que decide se o resto pode existir.
audit:  ## Auditoria estrutural + guarda de redução contra HEAD (somente leitura)
	python3 tools/audit.py --contra=HEAD

audit-reducao:  ## Redução medida contra outra referência (REF=HEAD)
	python3 tools/audit.py --contra=$(or $(REF),HEAD)

test:  ## Testes Python e TypeScript
	uv run pytest -q
	uv run python tools/corpus_graph.py
	cd frontend && pnpm run typecheck && pnpm run test

lint:  ## Ruff, mypy e ESLint
	uv run ruff check .
	uv run mypy
	cd frontend && pnpm run lint

icon:  ## Instala o lançador do Atlas no menu de aplicativos do GNOME
	@mkdir -p $(HOME)/.local/share/applications $(HOME)/.local/share/icons/hicolor/scalable/apps
	@cp tools/atlas.svg $(HOME)/.local/share/icons/hicolor/scalable/apps/vault-atlas.svg
	@printf '%s\n' \
		'[Desktop Entry]' \
		'Type=Application' \
		'Name=A.N.E.' \
		'Comment=Atlas Neural-Epistêmico — corpus interdisciplinar vivo' \
		'Exec=$(CURDIR)/tools/atlas.sh' \
		'Icon=vault-atlas' \
		'Terminal=true' \
		'Categories=Education;' \
		'Keywords=atlas;vault;corpus;conhecimento;grafo;3d;' \
		'StartupNotify=true' \
		> $(HOME)/.local/share/applications/vault-atlas.desktop
	@chmod +x $(HOME)/.local/share/applications/vault-atlas.desktop
	@update-desktop-database $(HOME)/.local/share/applications 2>/dev/null || true
	@gtk-update-icon-cache -f -t $(HOME)/.local/share/icons/hicolor 2>/dev/null || true
	@echo "lançador instalado: procure por \"A.N.E.\" no menu"

dev:  ## Sobe backend, frontend e worker (Ctrl-C encerra todos)
	@tools/atlas.sh

backend:  ## API FastAPI com reload
	uv run uvicorn vault.app:app --reload --timeout-graceful-shutdown 3 --port 8000

frontend:  ## Atlas Neural-Epistêmico em Vite
	cd frontend && pnpm run dev

corpus-graph:  ## Projeta knowledge/ em frontend/public/projection.json
	uv run python tools/corpus_graph.py

discover-models:  ## Inventaria os endpoints realmente disponíveis em cada provedor
	uv run python tools/discover_models.py $(ARGS)

endpoints:  ## Inventário classificado do que já foi descoberto, sem tocar na rede
	uv run python tools/endpoints.py $(ARGS)

probe-streams:  ## Classifica o que cada endpoint entrega durante a execução ([ARGS=--dry-run])
	uv run python tools/probe_streams.py $(ARGS)

smoke-providers:  ## Uma sonda dirigida por provedor, com limites observados
	uv run python tools/smoke_providers.py $(ARGS)

work:  ## Distribui uma tarefa entre os endpoints comprovados (TAREFA="..." [ARGS=...])
	uv run python tools/run_work.py $(ARGS) "$(TAREFA)"

quorum:  ## Propõe e avalia uma tarefa por quórum multimodelo (TAREFA="..." [ARGS=...])
	uv run python tools/run_quorum.py $(ARGS) "$(TAREFA)"

worker:  ## Mantém a fila autônoma viva ([ARGS=--once|--dry-run])
	uv run python tools/run_worker.py $(ARGS)

retire-tasks:  ## Lista (ou aposenta, com ARGS=--aplicar) meta sem nota na fila
	uv run python tools/retire_tasks.py $(ARGS)

outcomes:  ## Reconstrói o ledger de desfechos e imprime as superfícies ([ARGS=--json])
	uv run python tools/outcomes.py $(ARGS)

promote:  ## Promove um painel de quórum aprovado (PAINEL=<id>)
	uv run python tools/promote.py $(PAINEL)

workspace-oauth:  ## Consentimento OAuth local e uma leitura mínima no Workspace
	uv run python tools/workspace_oauth.py
