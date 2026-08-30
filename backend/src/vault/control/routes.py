"""As rotas do painel de controle. Leitura separada de mutação, credencial isolada.

A separação não é estética. O snapshot é barato, idempotente e pode ser buscado em
laço; a mutação muda estado durável e precisa devolver a leitura nova para que o
frontend não fique adivinhando o efeito; a credencial toca o arquivo de segredos e
tem regras que não valem para o resto — corpo que nunca é registrado, resposta que
nunca devolve o valor, e erro que passa por redação antes de virar mensagem.

Não há WebSocket aqui de propósito. O painel busca depois de cada mutação e em
intervalo curto enquanto está aberto; um canal permanente por um dado que muda a cada
poucos segundos custaria mais do que resolve.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Path
from pydantic import SecretStr

from providers import ProviderAuthError, build_adapters
from vault.config import Settings, get_settings
from vault.control.credentials import (
    ENV_VAR_BY_PROVIDER,
    CredentialError,
    provider_env_var,
    remove_credential,
    write_credential,
)
from vault.control.models import (
    AutoPatch,
    ControlSnapshot,
    CredentialBody,
    CredentialResult,
    WorkerPatch,
)
from vault.control.preferences import PreferenceStore
from vault.control.snapshot import build_snapshot, concurrency_ceiling
from vault.work.roles import ROLES

router = APIRouter(prefix="/api/control", tags=["control"])

ProviderId = Annotated[str, Path(min_length=1, max_length=64)]
WorkerId = Annotated[str, Path(min_length=1, max_length=80)]


def _settings() -> Settings:
    return get_settings()


def _forget_settings() -> None:
    """Esquece o cache de configuração, quando há um.

    `get_settings` é `lru_cache`, e sem esquecer o valor a resposta logo depois de
    gravar diria "ausente" para a credencial que acabou de entrar. O `getattr` existe
    porque o teste substitui a função por uma sem cache.
    """
    limpar = getattr(get_settings, "cache_clear", None)
    if callable(limpar):
        limpar()


def _store(settings: Settings) -> PreferenceStore:
    return PreferenceStore(settings.state_dir / "control.json")


def _snapshot(settings: Settings) -> ControlSnapshot:
    return build_snapshot(settings, _store(settings).load())


@router.get("/snapshot", response_model=ControlSnapshot)
def read_snapshot() -> ControlSnapshot:
    return _snapshot(_settings())


@router.patch("/auto", response_model=ControlSnapshot)
def patch_auto(body: AutoPatch) -> ControlSnapshot:
    settings = _settings()
    # Desligar o AUTO não encerra o que já está correndo: a fila não é tocada aqui, e
    # tarefa em execução drena pelo caminho normal do worker. O que muda é que nada
    # novo é alocado automaticamente.
    _store(settings).set_auto(body.auto)
    return _snapshot(settings)


@router.patch("/workers/{worker_id}", response_model=ControlSnapshot)
def patch_worker(worker_id: WorkerId, body: WorkerPatch) -> ControlSnapshot:
    settings = _settings()
    role = ROLES.get(worker_id)
    if role is None:
        raise HTTPException(status_code=404, detail=f"trabalhador desconhecido: {worker_id}")

    # O limite é revalidado aqui porque o frontend não é autoridade sobre teto. Um
    # cliente desatualizado, ou um pedido montado à mão, não pode conceder mais
    # simultaneidade do que o papel e o orçamento admitem.
    if body.concurrency is not None:
        teto = concurrency_ceiling(role.max_concurrency, settings)
        if body.concurrency > teto:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"simultaneidade {body.concurrency} acima do teto de {teto} "
                    f"para {worker_id}"
                ),
            )

    if body.provider is not None and body.provider not in ENV_VAR_BY_PROVIDER:
        raise HTTPException(status_code=422, detail=f"provedor desconhecido: {body.provider}")

    _store(settings).update_worker(
        worker_id,
        enabled=body.enabled,
        provider=body.provider,
        endpoint_id=body.endpoint_id,
        reasoning=body.reasoning,
        concurrency=body.concurrency,
    )
    return _snapshot(settings)


def _credential_result(
    settings: Settings,
    provider_id: str,
    status: str,
    detail: str,
) -> CredentialResult:
    atual = _snapshot(settings)
    linha = next((item for item in atual.providers if item.id == provider_id), None)
    return CredentialResult(
        provider=provider_id,
        key_configured=linha.key_configured if linha else False,
        key_hint=linha.key_hint if linha else None,
        status=status,  # type: ignore[arg-type]
        detail=detail,
    )


async def _probe(settings: Settings, provider_id: str, key: str | None) -> tuple[str, str]:
    """Autentica sem gerar nada. Devolve estado e detalhe já sanitizados.

    Quem escolhe a chamada é o adaptador, em `verify_credential`, e não esta rota. A
    razão é concreta: durante três provedores a chamada certa foi sempre `list_models`,
    barata e autenticada, e o Ollama Cloud quebrou a coincidência — lá a listagem é
    pública e responde 200 para qualquer chave. Com a decisão aqui, este teste diria
    "disponível" para uma credencial que o provedor recusa.

    Uma chave passada no corpo é testada sem ser persistida — é isso que separa
    `Testar` de `Aplicar`.

    A configuração chega por parâmetro, e não de `get_settings()`. Ler a global aqui
    fazia esta função ignorar a configuração que a rota estava usando — e num teste
    isso significava sair pela rede com a credencial real do mantenedor.

    **A redação usa a configuração que carrega a candidata, não a do processo.** Uma
    chave em teste ainda não está gravada, então ela não estava entre os segredos que
    `redact` conhecia: uma exceção de SDK que ecoasse o pedido devolvia a candidata
    inteira. Só escapavam as que casavam por acaso com `SECRET_SHAPE`, e a do Ollama
    não casa com nenhuma das três formas conhecidas.
    """
    if key is not None:
        # Adaptador descartável, construído só para esta verificação. Ele não é
        # guardado em lugar nenhum e some com o escopo.
        campo = {
            "google": "gemini_api_key",
            "groq": "groq_api_key",
            "nvidia": "nvidia_api_key",
            "ollama": "ollama_api_key",
            "nous": "nous_api_key",
            "openrouter": "openrouter_api_key",
        }[provider_id]
        # `SecretStr` porque é assim que `redact` lê o campo; `build_adapters` aceita
        # os dois e converte no limite do SDK.
        sanitizador = settings.model_copy(update={campo: SecretStr(key)})
        adapters = build_adapters(sanitizador)
    else:
        sanitizador = settings
        adapters = build_adapters(settings)

    adapter = adapters.get(provider_id)
    if adapter is None:
        return "ausente", "não há credencial para testar"
    try:
        detalhe = await adapter.verify_credential()
    except ProviderAuthError as error:
        return "invalido", sanitizador.redact(f"{type(error).__name__}: {error}")[:300]
    except Exception as error:  # noqa: BLE001 — a mensagem do SDK é sempre sanitizada
        texto = sanitizador.redact(f"{type(error).__name__}: {error}")[:300]
        minusculo = texto.lower()
        if "auth" in minusculo or "401" in texto or "403" in texto:
            return "invalido", texto
        return "erro", texto
    return "disponivel", detalhe


@router.post("/providers/{provider_id}/test", response_model=CredentialResult)
async def test_provider(
    provider_id: ProviderId,
    body: Annotated[CredentialBody | None, Body()] = None,
) -> CredentialResult:
    settings = _settings()
    try:
        provider_env_var(provider_id)
    except CredentialError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    status, detalhe = await _probe(settings, provider_id, body.key if body else None)
    return _credential_result(settings, provider_id, status, detalhe)


@router.put("/providers/{provider_id}/credential", response_model=CredentialResult)
def put_credential(provider_id: ProviderId, body: CredentialBody) -> CredentialResult:
    """Persiste a credencial. O corpo não é registrado em log algum.

    `get_settings` é cacheado, então o processo precisa reler o arquivo para que o
    estado devolvido reflita a gravação que acabou de acontecer — sem isso a resposta
    diria "ausente" logo depois de gravar.
    """
    settings = _settings()
    try:
        write_credential(settings.secrets_file, provider_id, body.key)
    except CredentialError as error:
        raise HTTPException(status_code=422, detail=settings.redact(str(error))) from None
    _forget_settings()
    return _credential_result(_settings(), provider_id, "configurado", "credencial gravada")


@router.delete("/providers/{provider_id}/credential", response_model=CredentialResult)
def delete_credential(provider_id: ProviderId) -> CredentialResult:
    settings = _settings()
    try:
        removida = remove_credential(settings.secrets_file, provider_id)
    except CredentialError as error:
        raise HTTPException(status_code=422, detail=settings.redact(str(error))) from None
    _forget_settings()
    detalhe = "credencial removida" if removida else "não havia credencial para remover"
    return _credential_result(_settings(), provider_id, "ausente", detalhe)
