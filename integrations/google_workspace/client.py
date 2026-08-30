"""Adaptador-base do Google Workspace: catálogo de serviços, OAuth local e sondagem.

Duas coisas que este módulo se recusa a confundir:

1. **Preparado não é habilitado.** O catálogo abaixo lista o que o projeto pretende
   alcançar; se a API não está habilitada no projeto do Cloud, ou se o serviço não
   existe para uma conta pessoal, isso é registrado como restrição daquele serviço —
   não como falha da integração.
2. **Ler não é escrever.** Nesta fase só há operação read-only. Escrita em Gmail,
   Calendar, Drive ou Docs não está automatizada, e os escopos pedidos por padrão
   são apenas os de leitura mínima.

O token do usuário é gravado com permissão 600, fora do repositório.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Escopos de leitura. `openid`/`userinfo` não entram: nada aqui precisa de identidade
# do usuário, e pedir escopo que não se usa é ruído no consentimento.
DRIVE_METADATA_RO = "https://www.googleapis.com/auth/drive.metadata.readonly"
REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class WorkspaceService:
    """Um serviço do Workspace e o que se sabe sobre alcançá-lo."""

    key: str
    api: str
    version: str
    scopes: tuple[str, ...]
    availability: str
    probe: str | None = None  # descrição da leitura mínima, quando existe uma sem ID
    note: str = ""


# Ordenado por quanto se espera usá-lo, não por importância do serviço.
SERVICES: dict[str, WorkspaceService] = {
    "drive": WorkspaceService(
        key="drive",
        api="drive",
        version="v3",
        scopes=(DRIVE_METADATA_RO,),
        availability="conta pessoal e Workspace",
        probe="files.list(pageSize=1, fields=files(id,name))",
        note="Escopo de metadados basta para inventariar; não lê conteúdo de arquivo.",
    ),
    "docs": WorkspaceService(
        key="docs",
        api="docs",
        version="v1",
        scopes=("https://www.googleapis.com/auth/documents.readonly",),
        availability="conta pessoal e Workspace",
        probe=None,
        note="A API só lê documento por ID; a descoberta passa pelo Drive.",
    ),
    "sheets": WorkspaceService(
        key="sheets",
        api="sheets",
        version="v4",
        scopes=("https://www.googleapis.com/auth/spreadsheets.readonly",),
        availability="conta pessoal e Workspace",
        probe=None,
        note="Também exige ID de planilha; descoberta pelo Drive.",
    ),
    "slides": WorkspaceService(
        key="slides",
        api="slides",
        version="v1",
        scopes=("https://www.googleapis.com/auth/presentations.readonly",),
        availability="conta pessoal e Workspace",
        probe=None,
        note="Exige ID de apresentação; descoberta pelo Drive.",
    ),
    "gmail": WorkspaceService(
        key="gmail",
        api="gmail",
        version="v1",
        scopes=("https://www.googleapis.com/auth/gmail.readonly",),
        availability="conta pessoal e Workspace",
        probe="users.getProfile(userId=me)",
        note="Escopo restrito pelo Google: pede tela de consentimento verificada ou "
        "usuário de teste declarado no projeto.",
    ),
    "calendar": WorkspaceService(
        key="calendar",
        api="calendar",
        version="v3",
        scopes=("https://www.googleapis.com/auth/calendar.readonly",),
        availability="conta pessoal e Workspace",
        probe="calendarList.list(maxResults=1)",
    ),
    "tasks": WorkspaceService(
        key="tasks",
        api="tasks",
        version="v1",
        scopes=("https://www.googleapis.com/auth/tasks.readonly",),
        availability="conta pessoal e Workspace",
        probe="tasklists.list(maxResults=1)",
    ),
    "forms": WorkspaceService(
        key="forms",
        api="forms",
        version="v1",
        scopes=("https://www.googleapis.com/auth/forms.body.readonly",),
        availability="conta pessoal e Workspace",
        probe=None,
        note="Exige ID de formulário; descoberta pelo Drive.",
    ),
    "people": WorkspaceService(
        key="people",
        api="people",
        version="v1",
        scopes=("https://www.googleapis.com/auth/contacts.readonly",),
        availability="conta pessoal e Workspace",
        probe="people.connections.list(resourceName=people/me, pageSize=1)",
    ),
    "script": WorkspaceService(
        key="script",
        api="script",
        version="v1",
        scopes=("https://www.googleapis.com/auth/script.projects.readonly",),
        availability="exige a Apps Script API ligada nas configurações do usuário",
        probe=None,
        note="Sem endpoint de listagem: projetos são lidos por ID.",
    ),
    "chat": WorkspaceService(
        key="chat",
        api="chat",
        version="v1",
        scopes=("https://www.googleapis.com/auth/chat.spaces.readonly",),
        availability="somente contas Google Workspace",
        probe="spaces.list(pageSize=1)",
        note="Indisponível em conta pessoal gmail.com — restrição do serviço.",
    ),
    "meet": WorkspaceService(
        key="meet",
        api="meet",
        version="v2",
        scopes=("https://www.googleapis.com/auth/meetings.space.readonly",),
        availability="conta pessoal e Workspace, com histórico de reuniões",
        probe="conferenceRecords.list(pageSize=1)",
    ),
    "keep": WorkspaceService(
        key="keep",
        api="keep",
        version="v1",
        scopes=("https://www.googleapis.com/auth/keep.readonly",),
        availability="somente Workspace Enterprise, com delegação em todo o domínio",
        probe=None,
        note="Fora de alcance para conta pessoal. Registrado, não tratado como falha.",
    ),
}


def default_scopes() -> tuple[str, ...]:
    """O consentimento mínimo desta fase: metadados do Drive, só leitura.

    Pedir os treze escopos de uma vez faz o consentimento falhar inteiro quando uma
    única API não está habilitada. Cada serviço a mais é uma decisão explícita.
    """
    return (DRIVE_METADATA_RO,)


class WorkspaceClient:
    def __init__(
        self,
        client_secret_file: Path,
        token_file: Path,
        scopes: tuple[str, ...] | None = None,
    ) -> None:
        self.client_secret_file = _external_path(client_secret_file, "client_secret")
        self.token_file = _external_path(token_file, "token OAuth")
        self.scopes = tuple(scopes) if scopes else default_scopes()
        self._credentials: Any = None

    # --- credenciais -------------------------------------------------------

    def load_credentials(self) -> Any | None:
        """Credencial já consentida, renovada se expirada. `None` se não houver."""
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        if not self.token_file.is_file():
            return None
        # Não injete os escopos desejados ao carregar: isso faria um token antigo
        # parecer autorizado para grants que o usuário nunca concedeu.
        credentials = Credentials.from_authorized_user_file(str(self.token_file))
        if not credentials.has_scopes(self.scopes):
            return None
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            self._save(credentials)
        self._credentials = credentials
        return credentials

    def authorize(self, *, port: int = 0) -> Any:
        """Fluxo OAuth local. Abre o navegador para o consentimento do usuário."""
        from google_auth_oauthlib.flow import InstalledAppFlow

        existing = self.load_credentials()
        if existing is not None and existing.valid:
            return existing
        if not self.client_secret_file.is_file():
            raise FileNotFoundError(
                f"client_secret não encontrado: {self.client_secret_file}. "
                "Ver docs/GOOGLE-WORKSPACE.md."
            )
        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.client_secret_file), list(self.scopes)
        )
        credentials = flow.run_local_server(port=port)
        self._save(credentials)
        self._credentials = credentials
        return credentials

    def _save(self, credentials: Any) -> None:
        self.token_file.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{self.token_file.name}.",
            dir=self.token_file.parent,
            text=True,
        )
        temporary_path = Path(temporary)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(credentials.to_json())
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, self.token_file)
            os.chmod(self.token_file, 0o600)
        finally:
            temporary_path.unlink(missing_ok=True)

    # --- serviços ----------------------------------------------------------

    def build(self, service_key: str) -> Any:
        from googleapiclient.discovery import build as discovery_build

        service = SERVICES[service_key]
        credentials = self._credentials or self.load_credentials()
        if credentials is None:
            raise PermissionError("sem token: rode `make workspace-oauth` primeiro")
        return discovery_build(
            service.api, service.version, credentials=credentials, cache_discovery=False
        )

    def probe_readonly(self, service_key: str) -> dict[str, Any]:
        """Executa a leitura mínima do serviço e classifica o resultado.

        Nunca escreve. Serviço sem leitura possível sem ID, ou fora de alcance para o
        tipo de conta, volta como `nao_aplicavel` — que é informação, não erro.
        """
        service = SERVICES[service_key]
        if service.probe is None:
            return {
                "service": service_key,
                "outcome": "nao_aplicavel",
                "detail": service.note or "sem leitura possível sem um ID",
            }
        try:
            client = self.build(service_key)
            result = _run_probe(service_key, client)
        except PermissionError as error:
            return {"service": service_key, "outcome": "sem_token", "detail": str(error)}
        except Exception as error:  # noqa: BLE001 — o relatório classifica, não estoura
            return {
                "service": service_key,
                "outcome": _classify_http(error),
                "detail": f"{type(error).__name__}: {error}"[:400],
            }
        return {"service": service_key, "outcome": "ok", "detail": result}


def _run_probe(service_key: str, client: Any) -> str:
    """A chamada read-only mínima de cada serviço, uma linha por serviço."""
    match service_key:
        case "drive":
            files = client.files().list(pageSize=1, fields="files(id,name)").execute()
            return f"{len(files.get('files', []))} arquivo(s) visível(is) na primeira página"
        case "gmail":
            profile = client.users().getProfile(userId="me").execute()
            return f"caixa com {profile.get('messagesTotal')} mensagens"
        case "calendar":
            listing = client.calendarList().list(maxResults=1).execute()
            return f"{len(listing.get('items', []))} agenda(s) na primeira página"
        case "tasks":
            listing = client.tasklists().list(maxResults=1).execute()
            return f"{len(listing.get('items', []))} lista(s) de tarefas"
        case "people":
            listing = (
                client.people()
                .connections()
                .list(resourceName="people/me", pageSize=1, personFields="names")
                .execute()
            )
            return f"{len(listing.get('connections', []))} contato(s) na primeira página"
        case "chat":
            listing = client.spaces().list(pageSize=1).execute()
            return f"{len(listing.get('spaces', []))} espaço(s) de Chat"
        case "meet":
            listing = client.conferenceRecords().list(pageSize=1).execute()
            return f"{len(listing.get('conferenceRecords', []))} registro(s) de reunião"
        case _:
            raise NotImplementedError(f"sem sondagem definida para {service_key}")


def _classify_http(error: Exception) -> str:
    status = getattr(getattr(error, "resp", None), "status", None)
    if status in (401, 403):
        return "sem_permissao"
    if status == 404:
        return "indisponivel"
    if status == 429:
        return "rate_limited"
    return "erro"


def _external_path(path: Path, label: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        raise ValueError(f"{label} deve ficar fora do repositório: {resolved}")
    return resolved
