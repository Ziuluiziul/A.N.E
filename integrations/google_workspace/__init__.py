"""Google Workspace — projeto no Google Cloud, OAuth 2.0 e consentimento do usuário.

Nada a ver com a chave da API Gemini: aqui a autorização é do dono da conta, escopo
por escopo. Nesta fase só existe leitura; escrita em Gmail, Calendar, Drive ou Docs
não está automatizada.
"""

from integrations.google_workspace.client import (
    SERVICES,
    WorkspaceClient,
    WorkspaceService,
    default_scopes,
)

__all__ = ["SERVICES", "WorkspaceClient", "WorkspaceService", "default_scopes"]
