"""O painel de controle: credencial que não vaza, ausência que não vira zero.

**Nenhuma chave real aparece aqui.** Todos os valores são sintéticos e todos os
arquivos ficam em `tmp_path`. O arquivo de segredos do mantenedor não é lido nem
escrito por nenhum teste deste módulo — é o que separa exercitar o mecanismo de usar o
mecanismo.
"""

from __future__ import annotations

import os
import stat
import tempfile
from collections.abc import Iterator
from pathlib import Path

import orjson
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from providers.aptitude import classify
from providers.base import ModelInfo, ProviderAuthError
from providers.inventory import EndpointProfile
from vault.config import Settings
from vault.control.credentials import (
    ENV_VAR_BY_PROVIDER,
    CredentialError,
    mask,
    provider_env_var,
    remove_credential,
    validate,
    write_credential,
)
from vault.control.preferences import ControlPreferences, PreferenceStore, WorkerPreference
from vault.control.snapshot import (
    _auto_pool,
    build_snapshot,
    clear_control_snapshot_cache,
    concurrency_ceiling,
    reasoning_support,
)

# Sintéticos, com o formato de uma chave e nenhuma validade. O prefixo `gsk_` existe
# para exercitar a redação defensiva de `Settings.redact`.
CHAVE_SINTETICA = "gsk_" + "S1nteticaParaTeste" * 2
OUTRA_SINTETICA = "gsk_" + "OutraSinteticaTest" * 2
CHAVE_OPENROUTER = "sk-or-v1-" + "OpenRouterSintetica" * 2


@pytest.fixture(autouse=True)
def _limpa_cache_do_snapshot_de_controle() -> Iterator[None]:
    clear_control_snapshot_cache()
    yield
    clear_control_snapshot_cache()


@pytest.fixture
def secrets(tmp_path: Path) -> Path:
    tmp_path.chmod(0o700)
    caminho = tmp_path / "secrets.env"
    caminho.write_text(
        "# comentário do mantenedor\n"
        "OUTRA_COISA=preservar\n"
        "NVIDIA_API_KEY=nvapi-preexistente\n",
        encoding="utf-8",
    )
    return caminho


def settings_de_teste(tmp_path: Path, secrets_file: Path) -> Settings:
    """Configuração inteiramente contida em `tmp_path`.

    `_env_file` não é decoração: sem ele, `Settings()` continuaria lendo o arquivo
    que `default_secrets_file()` resolver (`~/.config/ane/secrets.env` ou o legado
    `~/.config/vault-autodidata/secrets.env`), porque é o que `model_config` declara.
    Um teste montado assim carregaria as credenciais reais do mantenedor para a
    memória e — no teste de conexão — sairia pela rede com elas. Foi exatamente o que
    aconteceu na primeira execução deste arquivo.
    """
    return Settings(
        VAULT_RUNTIME_DIR=tmp_path / "runtime",
        VAULT_SECRETS_FILE=secrets_file,
        VAULT_CORPUS_DIR=tmp_path / "knowledge",
        _env_file=secrets_file,
    )  # type: ignore[call-arg]


# --- credenciais -------------------------------------------------------------


class TestCredenciais:
    def test_grava_e_devolve_so_a_dica(self, secrets: Path) -> None:
        dica = write_credential(secrets, "groq", CHAVE_SINTETICA)
        assert dica == CHAVE_SINTETICA[-4:]
        assert len(dica or "") == 4

    def test_preserva_o_que_nao_e_dela(self, secrets: Path) -> None:
        write_credential(secrets, "groq", CHAVE_SINTETICA)
        conteudo = secrets.read_text(encoding="utf-8")
        # Comentário, variável alheia e credencial de outro provedor atravessam.
        assert "# comentário do mantenedor" in conteudo
        assert "OUTRA_COISA=preservar" in conteudo
        assert "NVIDIA_API_KEY=nvapi-preexistente" in conteudo
        assert f"GROQ_API_KEY={CHAVE_SINTETICA}" in conteudo

    def test_substitui_sem_duplicar(self, secrets: Path) -> None:
        write_credential(secrets, "groq", CHAVE_SINTETICA)
        write_credential(secrets, "groq", OUTRA_SINTETICA)
        linhas = secrets.read_text(encoding="utf-8").splitlines()
        assert sum(1 for linha in linhas if linha.startswith("GROQ_API_KEY=")) == 1
        assert CHAVE_SINTETICA not in secrets.read_text(encoding="utf-8")

    def test_termina_com_0600(self, secrets: Path) -> None:
        secrets.chmod(0o644)
        write_credential(secrets, "groq", CHAVE_SINTETICA)
        assert stat.S_IMODE(secrets.stat().st_mode) == 0o600

    def test_arquivo_novo_tambem_nasce_0600(self, tmp_path: Path) -> None:
        destino = tmp_path / "novo" / "secrets.env"
        write_credential(destino, "groq", CHAVE_SINTETICA)
        assert stat.S_IMODE(destino.stat().st_mode) == 0o600
        assert stat.S_IMODE(destino.parent.stat().st_mode) == 0o700

    def test_diretorio_e_privado_antes_de_criar_o_temporario(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        destino = tmp_path / "privado" / "secrets.env"
        original_mkstemp = tempfile.mkstemp

        def mkstemp_guardado(
            *, dir: str | Path, prefix: str, suffix: str
        ) -> tuple[int, str]:
            parent = Path(dir)
            assert stat.S_IMODE(parent.stat().st_mode) == 0o700
            return original_mkstemp(dir=parent, prefix=prefix, suffix=suffix)

        monkeypatch.setattr("vault.control.atomic.tempfile.mkstemp", mkstemp_guardado)
        write_credential(destino, "groq", CHAVE_SINTETICA)
        assert stat.S_IMODE(destino.stat().st_mode) == 0o600

    def test_recusa_diretorio_preexistente_permissivo_sem_tocar_nele(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        parent = tmp_path / "permissivo"
        parent.mkdir(mode=0o755)
        parent.chmod(0o755)
        destino = parent / "secrets.env"

        def mkstemp_proibido(*_args: object, **_kwargs: object) -> tuple[int, str]:
            pytest.fail("mkstemp não pode acontecer antes de validar o diretório")

        monkeypatch.setattr("vault.control.atomic.tempfile.mkstemp", mkstemp_proibido)
        with pytest.raises(CredentialError) as capturado:
            write_credential(destino, "groq", CHAVE_SINTETICA)

        assert not destino.exists()
        assert list(parent.iterdir()) == []
        assert stat.S_IMODE(parent.stat().st_mode) == 0o755
        assert CHAVE_SINTETICA not in str(capturado.value)
        assert "modo 0700" in str(capturado.value)

    def test_recusa_diretorio_privado_de_outro_usuario(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        parent = tmp_path / "de-outro-usuario"
        parent.mkdir(mode=0o700)
        parent.chmod(0o700)

        current_euid = os.geteuid()
        monkeypatch.setattr("vault.control.atomic.os.geteuid", lambda: current_euid + 1)
        with pytest.raises(CredentialError, match="outro usuário"):
            write_credential(parent / "secrets.env", "groq", CHAVE_SINTETICA)

        assert list(parent.iterdir()) == []

    def test_recusa_diretorio_simbolico_sem_escrever_no_alvo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real = tmp_path / "real"
        real.mkdir(mode=0o700)
        real.chmod(0o700)
        alias = tmp_path / "config"
        alias.symlink_to(real, target_is_directory=True)

        def mkstemp_proibido(*_args: object, **_kwargs: object) -> tuple[int, str]:
            pytest.fail("mkstemp não pode seguir o diretório simbólico")

        monkeypatch.setattr("vault.control.atomic.tempfile.mkstemp", mkstemp_proibido)
        with pytest.raises(CredentialError, match="link simbólico"):
            write_credential(alias / "secrets.env", "groq", CHAVE_SINTETICA)

        assert list(real.iterdir()) == []

    def test_recusa_destino_simbolico_antes_de_ler_ou_criar_temporario(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        parent = tmp_path / "privado"
        parent.mkdir(mode=0o700)
        parent.chmod(0o700)
        alvo = tmp_path / "alvo.env"
        original = b"OUTRA_COISA=intacta\n"
        alvo.write_bytes(original)
        destino = parent / "secrets.env"
        destino.symlink_to(alvo)

        def mkstemp_proibido(*_args: object, **_kwargs: object) -> tuple[int, str]:
            pytest.fail("mkstemp não pode seguir o destino simbólico")

        def leitura_proibida(_path: Path) -> list[str]:
            pytest.fail("o destino simbólico não pode ser lido")

        monkeypatch.setattr("vault.control.atomic.tempfile.mkstemp", mkstemp_proibido)
        monkeypatch.setattr("vault.control.credentials._linhas", leitura_proibida)
        with pytest.raises(CredentialError, match="arquivo de credenciais.*link simbólico"):
            write_credential(destino, "groq", CHAVE_SINTETICA)

        assert alvo.read_bytes() == original
        assert destino.is_symlink()

    def test_remove_recusa_parent_permissivo_sem_ler_nem_reescrever(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        parent = tmp_path / "permissivo"
        parent.mkdir(mode=0o755)
        parent.chmod(0o755)
        destino = parent / "secrets.env"
        original = b"NVIDIA_API_KEY=nvapi-sintetica\n"
        destino.write_bytes(original)
        destino.chmod(0o600)

        def mkstemp_proibido(*_args: object, **_kwargs: object) -> tuple[int, str]:
            pytest.fail("mkstemp não pode acontecer no parent permissivo")

        def leitura_proibida(_path: Path) -> list[str]:
            pytest.fail("o arquivo não pode ser lido antes de validar o parent")

        monkeypatch.setattr("vault.control.atomic.tempfile.mkstemp", mkstemp_proibido)
        monkeypatch.setattr("vault.control.credentials._linhas", leitura_proibida)
        with pytest.raises(CredentialError, match="modo 0700"):
            remove_credential(destino, "nvidia")

        assert destino.read_bytes() == original

    def test_gravacao_interrompida_nao_corrompe(
        self, secrets: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        original = secrets.read_text(encoding="utf-8")

        def explode(*_args: object, **_kwargs: object) -> None:
            raise OSError("disco cheio")

        monkeypatch.setattr("vault.control.atomic.os.replace", explode)
        with pytest.raises(CredentialError):
            write_credential(secrets, "groq", CHAVE_SINTETICA)

        # O original sobreviveu inteiro, e nenhum temporário ficou para trás com o
        # segredo dentro.
        assert secrets.read_text(encoding="utf-8") == original
        restos = [item for item in secrets.parent.iterdir() if item.name != secrets.name]
        assert restos == []

    def test_remove_e_diz_se_havia(self, secrets: Path) -> None:
        assert remove_credential(secrets, "nvidia") is True
        assert "NVIDIA_API_KEY" not in secrets.read_text(encoding="utf-8")
        assert remove_credential(secrets, "nvidia") is False
        # O que não era dela continua lá.
        assert "OUTRA_COISA=preservar" in secrets.read_text(encoding="utf-8")

    def test_erro_nunca_carrega_o_valor(self, tmp_path: Path) -> None:
        # Um diretório onde o arquivo deveria estar: a gravação falha e a mensagem
        # não pode conter a chave que ela tentou gravar.
        destino = tmp_path / "ocupado"
        destino.mkdir()
        with pytest.raises(CredentialError) as capturado:
            write_credential(destino, "groq", CHAVE_SINTETICA)
        assert CHAVE_SINTETICA not in str(capturado.value)

    def test_formato_e_recusado_antes_de_tocar_no_arquivo(self, secrets: Path) -> None:
        original = secrets.read_text(encoding="utf-8")
        for invalida in ("", "   ", "curta", "com\nquebra", "x" * 600):
            with pytest.raises(CredentialError):
                write_credential(secrets, "groq", invalida)
        assert secrets.read_text(encoding="utf-8") == original

    def test_dica_some_quando_o_segredo_e_curto(self) -> None:
        # Quatro de onze caracteres é fração grande demais para ser dica.
        assert mask("abcdefghijk") is None
        assert mask("abcdefghijkl") == "ijkl"
        assert mask(None) is None

    def test_provedor_desconhecido_nao_tem_variavel(self) -> None:
        with pytest.raises(CredentialError):
            provider_env_var("inexistente")
        assert provider_env_var("groq") == "GROQ_API_KEY"
        assert provider_env_var("ollama") == "OLLAMA_API_KEY"
        assert provider_env_var("openrouter") == "OPENROUTER_API_KEY"
        assert provider_env_var("nous") == "NOUS_API_KEY"

    def test_validate_devolve_o_valor_limpo(self) -> None:
        assert validate(f"  {CHAVE_SINTETICA}  ") == CHAVE_SINTETICA


# --- preferências ------------------------------------------------------------


class TestPreferencias:
    def test_nao_muda_permissao_do_diretorio_configuravel(self, tmp_path: Path) -> None:
        parent = tmp_path / "runtime-compartilhado"
        parent.mkdir(mode=0o755)
        parent.chmod(0o755)
        caminho = parent / "control.json"

        PreferenceStore(caminho).set_auto(False)

        assert stat.S_IMODE(parent.stat().st_mode) == 0o755
        assert stat.S_IMODE(caminho.stat().st_mode) == 0o600

    def test_desligar_auto_nao_materializa_configuracao(self, tmp_path: Path) -> None:
        store = PreferenceStore(tmp_path / "control.json")
        store.set_auto(False)
        depois = store.load()
        assert depois.auto is False
        # A preferência manual continua vazia: o que o AUTO resolvia era
        # circunstancial e não vira decisão declarada por desligar o modo.
        assert depois.workers == {}
        assert depois.for_worker("verificador-factual").provider is None

    def test_preferencia_sobrevive_ao_disco(self, tmp_path: Path) -> None:
        store = PreferenceStore(tmp_path / "control.json")
        store.update_worker("verificador-factual", provider="groq", concurrency=2)
        recarregado = PreferenceStore(tmp_path / "control.json").load()
        assert recarregado.for_worker("verificador-factual").provider == "groq"
        assert recarregado.for_worker("verificador-factual").concurrency == 2

    def test_arquivo_corrompido_volta_ao_padrao_sem_derrubar(self, tmp_path: Path) -> None:
        caminho = tmp_path / "control.json"
        caminho.write_text("{ isto não é json", encoding="utf-8")
        assert PreferenceStore(caminho).load() == ControlPreferences()

    def test_zero_e_preferencia_e_none_e_ausencia(self, tmp_path: Path) -> None:
        store = PreferenceStore(tmp_path / "control.json")
        store.update_worker("arbitro", concurrency=0)
        assert store.load().for_worker("arbitro").concurrency == 0
        assert ControlPreferences().for_worker("arbitro").concurrency is None


# --- capacidades de raciocínio ------------------------------------------------


def perfil(**raw: object) -> EndpointProfile:
    model = ModelInfo(
        provider="groq",
        endpoint_id="modelo/de-teste",
        family="teste",
        capabilities=["generateContent"],
        raw=dict(raw),
    )
    return EndpointProfile(aptitude=classify(model), model=model)


class TestRaciocinio:
    def test_sem_declaracao_nao_existe_seletor(self) -> None:
        suporte = reasoning_support(perfil(), None)
        assert suporte.supported is False
        assert suporte.options == []
        assert suporte.reason

    def test_mencionar_raciocinio_nao_basta(self) -> None:
        # Saber que o endpoint raciocina não diz quais níveis ele aceita. Oferecer um
        # seletor aqui exigiria inventar as opções.
        suporte = reasoning_support(perfil(display_name="Modelo com reasoning"), None)
        assert suporte.supported is False
        assert suporte.options == []

    def test_niveis_declarados_viram_exatamente_as_opcoes(self) -> None:
        suporte = reasoning_support(perfil(reasoning_levels=["low", "high"]), "high")
        assert suporte.supported is True
        assert suporte.options == ["low", "high"]
        assert suporte.value == "high"

    def test_nivel_escolhido_fora_do_declarado_nao_e_aceito(self) -> None:
        suporte = reasoning_support(perfil(reasoning_levels=["low"]), "altissimo")
        assert suporte.options == ["low"]
        assert suporte.value is None

    def test_sem_endpoint_resolvido_nao_ha_suporte(self) -> None:
        assert reasoning_support(None, "low").supported is False


# --- snapshot ----------------------------------------------------------------


class TestSnapshot:
    def test_segunda_leitura_nao_reabre_a_fila(
        self, tmp_path: Path, secrets: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O painel busca o snapshot em laço; reler tasks.json com LOCK_EX era o custo."""
        from vault.autonomy.queue import PersistentTaskQueue, QueueSnapshot

        settings = settings_de_teste(tmp_path, secrets)
        caminho = settings.state_dir / "autonomy" / "tasks.json"
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(
            orjson.dumps({"schema_version": 1, "revision": 0, "tasks": []})
        )

        chamadas = {"n": 0}
        original = PersistentTaskQueue.snapshot

        def contar(self: PersistentTaskQueue) -> QueueSnapshot:
            chamadas["n"] += 1
            return original(self)

        monkeypatch.setattr("vault.control.snapshot.PersistentTaskQueue.snapshot", contar)
        prefs = ControlPreferences()
        primeiro = build_snapshot(settings, prefs)
        assert chamadas["n"] == 1
        n_depois_da_montagem = chamadas["n"]
        segundo = build_snapshot(settings, prefs)
        assert chamadas["n"] == n_depois_da_montagem
        assert segundo is primeiro

        apertado = settings.model_copy(update={"work_max_calls": 1})
        terceiro = build_snapshot(apertado, prefs)
        assert chamadas["n"] > n_depois_da_montagem
        assert terceiro is not primeiro
        n_depois_do_apertado = chamadas["n"]

        caminho.write_bytes(
            orjson.dumps({"schema_version": 1, "revision": 1, "tasks": []})
        )
        quarto = build_snapshot(settings, prefs)
        assert quarto is not primeiro
        assert chamadas["n"] > n_depois_do_apertado

    def test_auto_espalha_provedores_no_cartao(self) -> None:
        """O Atlas não pode jurar que sete papéis usam o mesmo SKU."""
        from providers.base import ProbeResult
        from providers.catalog import DiscoverySnapshot
        from providers.inventory import build_inventory
        from providers.registry import EndpointRegistry
        from vault.work.roles import ROLES

        def snap(provider: str, endpoint: str) -> DiscoverySnapshot:
            return DiscoverySnapshot(
                path=Path(f"models-{provider}.json"),
                models=[
                    ModelInfo(
                        provider=provider,
                        endpoint_id=endpoint,
                        family=provider,
                        available=True,
                        context_window=8192,
                        capabilities=["generateContent"],
                    )
                ],
            )

        registry = EndpointRegistry()
        registry.record_probe(ProbeResult("groq", "qwen/qwen3.6-27b", "ok", "ok", 1))
        registry.record_probe(
            ProbeResult("nvidia", "meta/llama-3.3-70b-instruct", "ok", "ok", 1)
        )
        inventory = build_inventory(
            {
                "groq": snap("groq", "qwen/qwen3.6-27b"),
                "nvidia": snap("nvidia", "meta/llama-3.3-70b-instruct"),
            },
            registry,
        )
        pool = _auto_pool(inventory, len(ROLES))
        provedores = {profile.provider for profile, _, _ in pool if profile is not None}
        assert provedores == {"groq", "nvidia"}
        assert pool[0][0] is not None and pool[1][0] is not None
        assert pool[0][0].provider != pool[1][0].provider

    def test_ausencia_tem_motivo_e_nunca_vira_zero(self, tmp_path: Path, secrets: Path) -> None:
        settings = settings_de_teste(tmp_path, secrets)
        snapshot = build_snapshot(settings, ControlPreferences())

        operacao = snapshot.operation
        # Sem fila criada, `queued` é ausência declarada — não zero.
        assert operacao.queued is None
        assert "queued" in operacao.unavailable
        assert operacao.calls is None
        assert "calls" in operacao.unavailable
        assert operacao.last_audit is None
        assert "last_audit" in operacao.unavailable

    def test_catalogo_ausente_explica_em_vez_de_contar_zero(
        self, tmp_path: Path, secrets: Path
    ) -> None:
        snapshot = build_snapshot(settings_de_teste(tmp_path, secrets), ControlPreferences())
        assert snapshot.notices, "a indisponibilidade do catálogo precisa ser dita"
        for provedor in snapshot.providers:
            assert provedor.endpoint_count is None
            assert "endpoint_count" in provedor.unavailable

    def test_cada_provedor_com_variavel_vira_uma_linha(
        self, tmp_path: Path, secrets: Path
    ) -> None:
        """A lista do painel sai de `ENV_VAR_BY_PROVIDER`, não de um segundo elenco."""
        snapshot = build_snapshot(settings_de_teste(tmp_path, secrets), ControlPreferences())
        assert {provedor.id for provedor in snapshot.providers} == set(ENV_VAR_BY_PROVIDER)
        ollama = next(p for p in snapshot.providers if p.id == "ollama")
        nous = next(p for p in snapshot.providers if p.id == "nous")
        openrouter = next(p for p in snapshot.providers if p.id == "openrouter")
        assert ollama.name == "Ollama Cloud"
        assert ollama.key_configured is False
        assert ollama.supports_custom_endpoint is False
        assert nous.name == "Nous Research (:free)"
        assert nous.key_configured is False
        assert nous.supports_custom_endpoint is False
        assert openrouter.name == "OpenRouter (:free)"
        assert openrouter.key_configured is False
        assert openrouter.supports_custom_endpoint is False

    def test_status_avisa_quando_opt_in_openrouter_sem_teto_esta_ativo(
        self, tmp_path: Path, secrets: Path
    ) -> None:
        settings = settings_de_teste(tmp_path, secrets).model_copy(
            update={
                "openrouter_api_key": SecretStr(CHAVE_OPENROUTER),
                "openrouter_allow_uncapped_free_tier": True,
            }
        )

        openrouter = next(
            provider
            for provider in build_snapshot(settings, ControlPreferences()).providers
            if provider.id == "openrouter"
        )

        assert openrouter.status == "configurado"
        assert "opt-in free-tier sem teto configurado" in openrouter.detail
        assert "sujeito à validação /key" in openrouter.detail
        assert "BYOK fica fora" in openrouter.detail

    def test_provedor_fora_da_descoberta_nao_recebe_contagem_zero(
        self, tmp_path: Path, secrets: Path
    ) -> None:
        """Zero endpoints e provedor não visitado são coisas diferentes no painel.

        Um provedor recém-adicionado — ou uma credencial que entrou depois da última
        descoberta — não aparece no manifesto. Contá-lo como zero afirmaria que ele não
        oferece nada, quando o que houve é que ninguém perguntou.
        """
        settings = settings_de_teste(tmp_path, secrets)
        state = settings.state_dir
        state.mkdir(parents=True, exist_ok=True)
        (state / "models-groq-teste.json").write_bytes(
            orjson.dumps(
                {
                    "provider": "groq",
                    "models": [
                        {
                            "provider": "groq",
                            "endpoint_id": "modelo-de-teste",
                            "family": "teste",
                            "capabilities": [],
                            "declared_limits": {},
                            "raw": {},
                        }
                    ],
                }
            )
        )
        (state / "models-discovery.json").write_bytes(
            orjson.dumps(
                {
                    "schema_version": 1,
                    "status": "complete",
                    "providers": {"groq": "models-groq-teste.json"},
                }
            )
        )

        provedores = build_snapshot(settings, ControlPreferences()).providers
        groq = next(p for p in provedores if p.id == "groq")
        ollama = next(p for p in provedores if p.id == "ollama")

        assert groq.endpoint_count == 1
        assert "endpoint_count" not in groq.unavailable
        assert ollama.endpoint_count is None
        assert "não cobriu" in ollama.unavailable["endpoint_count"]

    def test_nenhum_campo_carrega_credencial(self, tmp_path: Path, secrets: Path) -> None:
        settings = settings_de_teste(tmp_path, secrets).model_copy(
            update={"groq_api_key": SecretStr(CHAVE_SINTETICA)}
        )
        serializado = build_snapshot(settings, ControlPreferences()).model_dump_json()
        assert CHAVE_SINTETICA not in serializado
        provedores = build_snapshot(settings, ControlPreferences()).providers
        groq = next(p for p in provedores if p.id == "groq")
        assert groq.key_configured is True
        assert groq.key_hint == CHAVE_SINTETICA[-4:]

    def test_auto_desligado_sem_preferencia_admite_que_falta_escolher(
        self, tmp_path: Path, secrets: Path
    ) -> None:
        settings = settings_de_teste(tmp_path, secrets)
        snapshot = build_snapshot(settings, ControlPreferences(auto=False))
        for worker in snapshot.workers:
            assert worker.resolved_by == "indisponivel"
            assert worker.provider is None
            assert worker.detail

    def test_todo_papel_do_registro_vira_trabalhador(
        self, tmp_path: Path, secrets: Path
    ) -> None:
        from vault.work.roles import ROLES

        snapshot = build_snapshot(settings_de_teste(tmp_path, secrets), ControlPreferences())
        assert {worker.id for worker in snapshot.workers} == set(ROLES)
        for worker in snapshot.workers:
            # Classe, função e área saem do registro canônico, não de uma lista fixa.
            assert worker.area
            assert worker.summary
            assert worker.class_name in {"avaliador", "produtor"}

    def test_teto_de_simultaneidade_respeita_orcamento(
        self, tmp_path: Path, secrets: Path
    ) -> None:
        apertado = settings_de_teste(tmp_path, secrets).model_copy(update={"work_max_calls": 1})
        assert concurrency_ceiling(3, apertado.work_max_calls) == 1
        snapshot = build_snapshot(apertado, ControlPreferences())
        for worker in snapshot.workers:
            assert worker.concurrency_max <= 1
            assert worker.concurrency <= worker.concurrency_max

    def test_orcamento_visivel_usa_teto_do_pool(
        self, tmp_path: Path, secrets: Path
    ) -> None:
        """O cartão não anuncia o sandbox de 6 quando o catálogo documenta mais."""
        settings = settings_de_teste(tmp_path, secrets)
        state = settings.state_dir
        state.mkdir(parents=True, exist_ok=True)
        (state / "models-groq-teste.json").write_bytes(
            orjson.dumps(
                {
                    "provider": "groq",
                    "models": [
                        {
                            "provider": "groq",
                            "endpoint_id": "llama-3.1-8b",
                            "family": "llama",
                            "capabilities": ["completion"],
                            "declared_limits": {
                                "requests_per_minute": 30,
                                "requests_per_day": 1_000,
                            },
                            "raw": {},
                            "available": True,
                        }
                    ],
                }
            )
        )
        (state / "models-discovery.json").write_bytes(
            orjson.dumps(
                {
                    "schema_version": 1,
                    "status": "complete",
                    "providers": {"groq": "models-groq-teste.json"},
                }
            )
        )
        from providers.base import ProbeResult
        from providers.registry import EndpointRegistry
        from vault.runtime_io import write_private_json

        registry = EndpointRegistry()
        registry.record_probe(ProbeResult("groq", "llama-3.1-8b", "ok", "ok", 1))
        write_private_json(state / "endpoints.json", registry.to_dict())
        snapshot = build_snapshot(settings, ControlPreferences())
        assert snapshot.operation.budget == "30 chamadas por execução"
        assert "6 chamadas" not in snapshot.operation.budget
        inflado = settings.model_copy(update={"work_max_calls": 91_020})
        assert build_snapshot(inflado, ControlPreferences()).operation.budget == (
            "30 chamadas por execução"
        )
        verificador = next(w for w in snapshot.workers if w.id == "verificador-factual")
        assert verificador.concurrency_max == 3
        assert concurrency_ceiling(3, 30) == 3

    def test_orcamento_sem_rpm_declarado_fica_no_piso(
        self, tmp_path: Path, secrets: Path
    ) -> None:
        snapshot = build_snapshot(settings_de_teste(tmp_path, secrets), ControlPreferences())
        assert snapshot.operation.budget == "6 chamadas por execu\u00e7\u00e3o"

    def test_preferencia_acima_do_teto_e_aparada(self, tmp_path: Path, secrets: Path) -> None:
        settings = settings_de_teste(tmp_path, secrets).model_copy(update={"work_max_calls": 2})
        preferencias = ControlPreferences(
            workers={"verificador-factual": WorkerPreference(concurrency=9)}
        )
        snapshot = build_snapshot(settings, preferencias)
        verificador = next(w for w in snapshot.workers if w.id == "verificador-factual")
        assert verificador.concurrency == 2


# --- rotas -------------------------------------------------------------------


@pytest.fixture
def cliente(
    tmp_path: Path, secrets: Path, monkeypatch: pytest.MonkeyPatch
) -> TestClient:
    from vault.app import app
    from vault.control import routes

    settings = settings_de_teste(tmp_path, secrets)
    estado: dict[str, Settings] = {"atual": settings}

    def falso_settings() -> Settings:
        return estado["atual"]

    def recarrega() -> None:
        estado["atual"] = settings_de_teste(tmp_path, secrets)

    monkeypatch.setattr(routes, "_settings", falso_settings)
    monkeypatch.setattr(routes, "_forget_settings", recarrega)
    return TestClient(app)


class TestRotas:
    def test_snapshot_responde_com_o_contrato(self, cliente: TestClient) -> None:
        resposta = cliente.get("/api/control/snapshot")
        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo["schema_version"] == 1
        assert {"providers", "workers", "operation", "generated_at"} <= set(corpo)

    def test_simultaneidade_invalida_e_recusada_pelo_backend(self, cliente: TestClient) -> None:
        resposta = cliente.patch(
            "/api/control/workers/verificador-factual", json={"concurrency": 9}
        )
        assert resposta.status_code == 422
        assert "teto" in resposta.json()["detail"]

    def test_trabalhador_desconhecido_nao_e_inventado(self, cliente: TestClient) -> None:
        resposta = cliente.patch("/api/control/workers/inexistente", json={"enabled": False})
        assert resposta.status_code == 404

    def test_desligar_trabalhador_nao_toca_na_fila(
        self, cliente: TestClient, tmp_path: Path
    ) -> None:
        fila = tmp_path / "runtime" / "state" / "autonomy" / "tasks.json"
        fila.parent.mkdir(parents=True, exist_ok=True)
        fila.write_bytes(orjson.dumps({"schema_version": 1, "revision": 3, "tasks": []}))
        antes = fila.read_bytes()

        resposta = cliente.patch(
            "/api/control/workers/verificador-factual", json={"enabled": False}
        )
        assert resposta.status_code == 200
        verificador = next(
            w for w in resposta.json()["workers"] if w["id"] == "verificador-factual"
        )
        assert verificador["enabled"] is False
        # Desligar impede alocação nova; não encerra nem invalida trabalho em curso.
        assert fila.read_bytes() == antes

    def test_auto_alterna_e_o_snapshot_conta(self, cliente: TestClient) -> None:
        desligado = cliente.patch("/api/control/auto", json={"auto": False})
        assert desligado.status_code == 200
        assert desligado.json()["operation"]["auto"] is False
        ligado = cliente.patch("/api/control/auto", json={"auto": True})
        assert ligado.json()["operation"]["auto"] is True

    def test_credencial_grava_sem_devolver_o_valor(
        self, cliente: TestClient, secrets: Path
    ) -> None:
        resposta = cliente.put(
            "/api/control/providers/groq/credential", json={"key": CHAVE_SINTETICA}
        )
        assert resposta.status_code == 200
        corpo = resposta.text
        assert CHAVE_SINTETICA not in corpo
        assert resposta.json()["key_hint"] == CHAVE_SINTETICA[-4:]
        assert f"GROQ_API_KEY={CHAVE_SINTETICA}" in secrets.read_text(encoding="utf-8")
        assert stat.S_IMODE(secrets.stat().st_mode) == 0o600

    def test_credencial_openrouter_usa_variavel_propria_sem_vazar(
        self, cliente: TestClient, secrets: Path
    ) -> None:
        resposta = cliente.put(
            "/api/control/providers/openrouter/credential", json={"key": CHAVE_OPENROUTER}
        )
        assert resposta.status_code == 200
        assert CHAVE_OPENROUTER not in resposta.text
        assert resposta.json()["key_hint"] == CHAVE_OPENROUTER[-4:]
        assert f"OPENROUTER_API_KEY={CHAVE_OPENROUTER}" in secrets.read_text(encoding="utf-8")

    def test_credencial_nous_usa_variavel_propria_sem_vazar(
        self, cliente: TestClient, secrets: Path
    ) -> None:
        chave = "nous-sk-" + "abcd" * 8
        resposta = cliente.put(
            "/api/control/providers/nous/credential", json={"key": chave}
        )
        assert resposta.status_code == 200
        assert chave not in resposta.text
        assert resposta.json()["key_hint"] == chave[-4:]
        assert f"NOUS_API_KEY={chave}" in secrets.read_text(encoding="utf-8")

    def test_credencial_malformada_e_recusada_sem_gravar(
        self, cliente: TestClient, secrets: Path
    ) -> None:
        original = secrets.read_text(encoding="utf-8")
        resposta = cliente.put("/api/control/providers/groq/credential", json={"key": "curta"})
        assert resposta.status_code == 422
        detalhe = resposta.json()["detail"]
        assert "caracteres" in detalhe
        assert secrets.read_text(encoding="utf-8") == original

    def test_rota_recusa_parent_permissivo_com_diagnostico_sem_chave(
        self,
        cliente: TestClient,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from vault.control import routes

        parent = tmp_path / "config-permissiva"
        parent.mkdir(mode=0o755)
        parent.chmod(0o755)
        settings = settings_de_teste(tmp_path, parent / "secrets.env")
        monkeypatch.setattr(routes, "_settings", lambda: settings)

        resposta = cliente.put(
            "/api/control/providers/groq/credential",
            json={"key": CHAVE_SINTETICA},
        )

        assert resposta.status_code == 422
        assert "modo 0700" in resposta.json()["detail"]
        assert CHAVE_SINTETICA not in resposta.text
        assert list(parent.iterdir()) == []
        assert stat.S_IMODE(parent.stat().st_mode) == 0o755

    def test_apagar_credencial_diz_o_que_aconteceu(
        self, cliente: TestClient, secrets: Path
    ) -> None:
        primeira = cliente.delete("/api/control/providers/nvidia/credential")
        assert primeira.status_code == 200
        assert primeira.json()["detail"] == "credencial removida"
        segunda = cliente.delete("/api/control/providers/nvidia/credential")
        assert segunda.json()["detail"] == "não havia credencial para remover"

    def test_provedor_desconhecido_nao_ganha_rota(self, cliente: TestClient) -> None:
        assert cliente.post("/api/control/providers/inexistente/test").status_code == 404
        assert (
            cliente.put(
                "/api/control/providers/inexistente/credential",
                json={"key": CHAVE_SINTETICA},
            ).status_code
            == 422
        )

    def test_validacao_de_chave_e_do_adaptador_nao_da_rota(
        self, cliente: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Listar não vale como prova em toda parte, então a rota não pode escolher.

        No Ollama Cloud `GET /api/tags` responde 200 para qualquer chave. Se esta rota
        continuasse decidindo por `list_models`, ela diria "disponível" para uma
        credencial recusada — o pior defeito possível num painel de credencial.
        """
        from vault.control import routes

        class AdaptadorFalso:
            provider = "ollama"

            async def list_models(self) -> list[ModelInfo]:
                raise AssertionError("a rota validou credencial listando modelos")

            async def verify_credential(self) -> str:
                raise ProviderAuthError("credencial rejeitada pelo Ollama Cloud: unauthorized")

        monkeypatch.setattr(routes, "build_adapters", lambda *_: {"ollama": AdaptadorFalso()})
        resposta = cliente.post(
            "/api/control/providers/ollama/test", json={"key": CHAVE_SINTETICA}
        )
        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo["status"] == "invalido"
        assert CHAVE_SINTETICA not in corpo["detail"]

    def test_teste_sem_credencial_nao_chama_ninguem(self, cliente: TestClient) -> None:
        # Sem chave configurada e sem chave no corpo, não há o que testar: a resposta
        # é estado, não uma chamada externa às cegas.
        resposta = cliente.post("/api/control/providers/groq/test")
        assert resposta.status_code == 200
        assert resposta.json()["status"] == "ausente"


# Sem prefixo conhecido e sem forma que `SECRET_SHAPE` reconheça — é assim que uma chave
# do Ollama Cloud se parece, e é o caso em que a redação por forma não salva ninguém.
CANDIDATA_SEM_FORMA = "b7e3" + "d9a1c4f6e8b2" * 4


class TestCandidataNuncaVolta:
    """A candidata não sai por resposta nenhuma — nem quando o Pydantic a recusa.

    Estes testes existem por um defeito real, achado na auditoria de 2026-08-09: uma
    chave acima de `max_length` era recusada pelo Pydantic **antes** de a rota rodar, e
    o handler 422 padrão devolvia `input` — o valor inteiro. Toda a disciplina de
    `credentials.py` continuava valendo e não adiantava nada, porque o segredo voltava
    numa camada acima dela.

    Nenhuma chave real aqui: as duas candidatas são sintéticas.
    """

    def test_chave_longa_demais_nao_volta_no_422(self, cliente: TestClient) -> None:
        candidata = "gsk_" + "S1nteticaLongaDemais" * 30
        assert len(candidata) > 512
        resposta = cliente.put(
            "/api/control/providers/groq/credential", json={"key": candidata}
        )
        assert resposta.status_code == 422
        assert candidata not in resposta.text
        # O 422 continua dizendo o que houve: campo e regra sobrevivem à limpeza.
        detalhe = resposta.json()["detail"][0]
        assert detalhe["loc"] == ["body", "key"]
        assert "512" in detalhe["msg"]
        assert "input" not in detalhe

    def test_excecao_do_adaptador_nao_ecoa_a_candidata(
        self, cliente: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Um SDK que ecoa o pedido não pode transformar isso em vazamento.

        A candidata ainda não foi gravada, então ela não estava entre os segredos que
        `redact` conhecia. Antes da correção só escapavam as chaves que casavam por
        acaso com `SECRET_SHAPE` — e esta, de propósito, não casa com nenhuma.
        """
        from vault.control import routes

        class AdaptadorTagarela:
            provider = "ollama"

            async def verify_credential(self) -> str:
                raise ProviderAuthError(
                    f"401 ao chamar https://ollama.com/api?key={CANDIDATA_SEM_FORMA}"
                )

        monkeypatch.setattr(
            routes, "build_adapters", lambda *_: {"ollama": AdaptadorTagarela()}
        )
        resposta = cliente.post(
            "/api/control/providers/ollama/test", json={"key": CANDIDATA_SEM_FORMA}
        )
        assert resposta.status_code == 200
        assert CANDIDATA_SEM_FORMA not in resposta.text
        assert "[REDACTED]" in resposta.json()["detail"]

    @pytest.mark.parametrize(
        "candidata",
        [
            "",  # vazia: recusada pelo modelo
            # Curta para `validate`, e sem nenhuma palavra que apareça numa mensagem de
            # erro em português — uma agulha que colide com o palheiro não prova nada.
            "x7k2q9",
            CANDIDATA_SEM_FORMA,
            "gsk_" + "S1nteticaLongaDemais" * 30,  # acima de `max_length`
        ],
    )
    def test_nenhum_corpo_de_erro_carrega_a_candidata(
        self, cliente: TestClient, candidata: str
    ) -> None:
        """A varredura que fecha o achado: nenhuma resposta 4xx/5xx repete o que entrou.

        Inclui o provedor inexistente de propósito — é o caminho em que a rota morre
        antes de qualquer validação de chave.
        """
        for rota in (
            "/api/control/providers/groq/credential",
            "/api/control/providers/inexistente/credential",
        ):
            resposta = cliente.put(rota, json={"key": candidata})
            if resposta.status_code >= 400 and candidata:
                assert candidata not in resposta.text, f"{rota} devolveu a candidata"


class TestDescritorVisualDoTrabalhador:
    """Quem possui a entidade descreve a entidade — ADR-005.

    O token de paleta viaja no snapshot de controle para o cliente não precisar
    reimplementar a regra de cor do trabalhador que ele passou a possuir. Uma tabela
    duplicada quebraria a identidade visual em silêncio, que é exatamente o que o gate
    de paridade da migração procura.
    """

    def test_o_token_do_controle_e_o_mesmo_da_projecao_operacional(self) -> None:
        from vault.operational import worker_nodes, worker_palette_token
        from vault.work.roles import ROLES

        nos = {no["id"]: no for no in worker_nodes()}
        for ordem, role in enumerate(ROLES.values()):
            esperado = worker_palette_token(ordem, reviews_others=role.reviews_others)
            no = nos[f"op/worker/{role.name}"]
            assert no["visual"]["paletteToken"] == esperado, role.name

    def test_avaliador_e_produtor_nao_compartilham_cor(self) -> None:
        from vault.operational import worker_palette_token

        avaliador = worker_palette_token(0, reviews_others=True)
        produtor = worker_palette_token(0, reviews_others=False)
        assert avaliador != produtor
