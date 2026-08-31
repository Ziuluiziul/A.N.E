#!/usr/bin/env python3
"""Consentimento OAuth local do Workspace e uma leitura mínima para confirmá-lo.

Pede apenas os escopos de leitura do Drive: o consentimento falha inteiro se uma das
APIs pedidas não estiver habilitada, então ampliar escopo é decisão separada. Serviço
fora de alcance para o tipo de conta é registrado como restrição, não como falha.

Nada é escrito em serviço nenhum. Ver docs/GOOGLE-WORKSPACE.md para obter o
client_secret.
"""

from __future__ import annotations

from integrations.google_workspace import SERVICES, WorkspaceClient, default_scopes
from vault.config import SECRETS_FILE_HINT, get_settings


def main() -> int:
    """Executa o fluxo sem deixar falhas de OAuth ou transporte virarem traceback."""
    try:
        return _main()
    except Exception as error:  # noqa: BLE001 — fronteira humana da CLI
        detail = " ".join(str(error).split())[:400] or "sem detalhe"
        print(f"workspace .. {type(error).__name__}: {detail}")
        return 1


def _main() -> int:
    settings = get_settings()
    secret = settings.google_workspace_client_secret_file
    token = settings.google_workspace_token_file

    if secret is None or token is None:
        print("faltam GOOGLE_WORKSPACE_CLIENT_SECRET_FILE e/ou GOOGLE_WORKSPACE_TOKEN_FILE")
        print(f"em {SECRETS_FILE_HINT} — ver docs/GOOGLE-WORKSPACE.md")
        return 1
    if not secret.is_file():
        print(f"client_secret não encontrado: {secret}")
        print("baixe-o no Google Cloud Console — ver docs/GOOGLE-WORKSPACE.md")
        return 1

    client = WorkspaceClient(secret, token, default_scopes())
    print(f"escopos pedidos: {', '.join(client.scopes)}")
    client.authorize()
    print(f"token gravado com permissão 600 em {token}")

    result = client.probe_readonly("drive")
    print(f"drive .. {result['outcome']}: {result['detail']}")

    pendentes = [
        f"{s.key} ({s.availability})" for s in SERVICES.values() if s.key not in {"drive"}
    ]
    print("\npreparados, ainda sem consentimento nesta fase:")
    for item in pendentes:
        print(f"  - {item}")

    return 0 if result["outcome"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
