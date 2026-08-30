"""O catálogo do Workspace precisa ser honesto sobre alcance e sobre leitura/escrita."""

from __future__ import annotations

import json
import stat

from integrations.google_workspace import SERVICES, default_scopes
from integrations.google_workspace.client import (
    DRIVE_METADATA_RO,
    REPO_ROOT,
    WorkspaceClient,
    _run_probe,
)

ESPERADOS = {
    "drive",
    "docs",
    "sheets",
    "slides",
    "gmail",
    "calendar",
    "tasks",
    "forms",
    "people",
    "script",
    "chat",
    "meet",
    "keep",
}


def test_os_treze_servicos_pedidos_estao_no_catalogo() -> None:
    assert set(SERVICES) == ESPERADOS


def test_todo_servico_declara_escopo_e_alcance() -> None:
    for service in SERVICES.values():
        assert service.scopes, f"{service.key} sem escopo"
        assert service.availability, f"{service.key} sem alcance declarado"


def test_nesta_fase_todo_escopo_e_de_leitura() -> None:
    for service in SERVICES.values():
        for scope in service.scopes:
            assert "readonly" in scope, f"{service.key} pede escopo de escrita: {scope}"


def test_servico_sem_sondagem_explica_por_que() -> None:
    for service in SERVICES.values():
        if service.probe is None:
            assert service.note, f"{service.key} não sonda e não diz por quê"


def test_toda_sondagem_declarada_esta_implementada() -> None:
    class Falha:
        def __getattr__(self, name: str) -> object:
            raise AssertionError(f"chamou {name} sem implementação prevista")

    for service in SERVICES.values():
        if service.probe is None:
            continue
        try:
            _run_probe(service.key, Falha())
        except NotImplementedError:  # pragma: no cover
            raise AssertionError(f"{service.key} declara sondagem sem implementá-la") from None
        except AssertionError as error:
            # Chegou a tocar no cliente: a implementação existe.
            assert "chamou" in str(error)


def test_consentimento_minimo_e_so_o_drive() -> None:
    """Pedir treze escopos de uma vez faz o consentimento falhar inteiro."""
    scopes = default_scopes()
    assert scopes == SERVICES["drive"].scopes
    assert len(scopes) == 1


def test_keep_e_chat_ficam_registrados_como_restritos() -> None:
    assert "Enterprise" in SERVICES["keep"].availability
    assert "Workspace" in SERVICES["chat"].availability


def test_token_com_escopo_diferente_exige_novo_consentimento(tmp_path) -> None:
    token = tmp_path / "token.json"
    token.write_text(
        json.dumps(
            {
                "token": "dummy",
                "refresh_token": "dummy",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "dummy.apps.googleusercontent.com",
                "client_secret": "dummy",
                "scopes": [DRIVE_METADATA_RO],
            }
        ),
        encoding="utf-8",
    )
    calendar_scope = SERVICES["calendar"].scopes
    client = WorkspaceClient(tmp_path / "credentials.json", token, calendar_scope)
    assert client.load_credentials() is None


def test_token_nasce_atomico_e_com_permissao_600(tmp_path) -> None:
    class Credenciais:
        @staticmethod
        def to_json() -> str:
            return '{"token":"segredo"}'

    token = tmp_path / "private" / "token.json"
    client = WorkspaceClient(tmp_path / "credentials.json", token)
    client._save(Credenciais())  # noqa: SLF001
    assert token.read_text(encoding="utf-8") == '{"token":"segredo"}'
    assert stat.S_IMODE(token.stat().st_mode) == 0o600
    assert not list(token.parent.glob(f".{token.name}.*"))


def test_credenciais_nunca_ficam_no_repositorio() -> None:
    try:
        WorkspaceClient(REPO_ROOT / "credentials.json", REPO_ROOT / "token.json")
    except ValueError as error:
        assert "fora do repositório" in str(error)
    else:  # pragma: no cover
        raise AssertionError("aceitou credenciais dentro do repositório")
