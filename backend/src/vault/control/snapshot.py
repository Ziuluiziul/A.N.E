"""Monta o snapshot a partir das fontes canônicas. Não cria uma sexta verdade.

Cada coisa que o painel mostra já tem dono neste repositório:

- credencial e orçamento — `vault.config`;
- catálogo de endpoints — `providers.catalog`, com a classificação de
  `providers.aptitude` e o observado de `providers.registry`, juntos em
  `providers.inventory`;
- papéis — `vault.work.roles`;
- fila e execuções — `vault.autonomy.PersistentTaskQueue`;
- preferência manual e AUTO — `vault.control.preferences`.

Este módulo lê essas fontes e as arruma; ele não decide política. Em particular, o
provedor e o modelo que o AUTO resolve saem de `Inventory.select(usable=True)`, que já
devolve na ordem de preferência canônica — reimplementar a escolha aqui criaria uma
segunda política que divergiria da primeira no primeiro ajuste.

Quando uma fonte não está disponível, o campo correspondente vira `None` e o motivo
entra em `unavailable`. Nenhum caminho deste arquivo produz zero para dizer "não sei".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from providers.catalog import DiscoverySnapshotError, load_all_snapshots
from providers.inventory import EndpointProfile, Inventory, build_inventory
from providers.registry import EndpointRegistry
from vault.autonomy import PersistentTaskQueue, TaskState
from vault.config import Settings
from vault.control.credentials import ENV_VAR_BY_PROVIDER, PROVIDER_LABEL, mask
from vault.control.models import (
    ControlSnapshot,
    OperationState,
    ProviderState,
    ReasoningSupport,
    WorkerState,
)
from vault.control.preferences import ControlPreferences
from vault.operational import worker_palette_token
from vault.work.ceilings import WorkCeilings, ceilings_from_declared, effective_max_calls
from vault.work.roles import ROLES

# Provedores que aceitam endpoint próprio. Nenhum deles hoje: os adaptadores falam
# com a API oficial e não têm campo de URL base. Declarado explicitamente para que a
# interface não ofereça um campo que não vai a lugar nenhum.
#
# O Ollama é o primeiro que teria o que colocar aqui — o mesmo protocolo atende numa
# instalação local e em qualquer host remoto —, e continua de fora porque o campo não
# existe em lugar nenhum do caminho: nem na preferência, nem na rota, nem no adaptador.
# Oferecer a caixa antes disso prometeria um controle que não liga em nada.
CUSTOM_ENDPOINT_PROVIDERS: frozenset[str] = frozenset()

# Chaves em que um catálogo pode declarar os níveis de raciocínio de um endpoint.
# Nenhum provedor as declara hoje no nível canônico; o mecanismo existe para que,
# quando declararem, o seletor apareça sozinho e correto.
_REASONING_KEYS = ("reasoning_levels", "thinking_levels", "reasoning_effort_levels")


def reasoning_support(profile: EndpointProfile | None, chosen: str | None) -> ReasoningSupport:
    """Níveis de raciocínio **declarados** pelo endpoint, e nada além disso."""
    if profile is None:
        return ReasoningSupport(reason="sem endpoint resolvido")
    fontes: tuple[dict[str, Any], ...] = (profile.model.declared_limits, profile.model.raw)
    for fonte in fontes:
        for chave in _REASONING_KEYS:
            niveis = fonte.get(chave)
            if (
                isinstance(niveis, list)
                and niveis
                and all(isinstance(item, str) and item for item in niveis)
            ):
                opcoes = [str(item) for item in niveis][:16]
                return ReasoningSupport(
                    supported=True,
                    options=opcoes,
                    value=chosen if chosen in opcoes else None,
                    reason="",
                )
    return ReasoningSupport(
        reason="o catálogo não declara níveis de raciocínio para este endpoint"
    )


def _inventory(settings: Settings) -> tuple[Inventory | None, frozenset[str], str]:
    """O inventário corrente, quem ele cobre, ou o motivo pelo qual não há um.

    A cobertura sai do manifesto, e não dos perfis encontrados, porque as duas coisas
    divergem: um provedor descoberto cujo catálogo veio vazio está coberto e tem zero
    endpoints, enquanto um provedor que a descoberta nunca visitou não tem contagem
    nenhuma. Sem essa distinção, os dois casos chegariam ao painel como o mesmo zero.
    """
    try:
        snapshots = load_all_snapshots(settings.state_dir)
    except DiscoverySnapshotError as error:
        return None, frozenset(), str(error)
    registry = EndpointRegistry.from_dict(_read_json(settings.state_dir / "endpoints.json"))
    return build_inventory(snapshots, registry), frozenset(snapshots), ""


def _read_json(path: Path) -> object:
    import orjson

    try:
        return orjson.loads(path.read_bytes())
    except (OSError, orjson.JSONDecodeError):
        return {}


def _providers(
    settings: Settings,
    inventory: Inventory | None,
    cobertos: frozenset[str],
    motivo_catalogo: str,
) -> list[ProviderState]:
    credenciais = settings.credential_status()
    # `credential_status` usa o nome do adaptador do Google como "gemini"; o catálogo
    # o chama de "google". A correspondência mora aqui, uma vez.
    status_por_provedor = {
        "google": credenciais.get("gemini", False),
        "groq": credenciais.get("groq", False),
        "nvidia": credenciais.get("nvidia", False),
        "ollama": credenciais.get("ollama", False),
        "nous": credenciais.get("nous", False),
        "openrouter": credenciais.get("openrouter", False),
    }
    segredos = {
        "google": settings.gemini_api_key,
        "groq": settings.groq_api_key,
        "nvidia": settings.nvidia_api_key,
        "ollama": settings.ollama_api_key,
        "nous": settings.nous_api_key,
        "openrouter": settings.openrouter_api_key,
    }

    linhas: list[ProviderState] = []
    for provider_id in sorted(ENV_VAR_BY_PROVIDER):
        configurada = status_por_provedor.get(provider_id, False)
        segredo = segredos.get(provider_id)
        detalhes: list[str] = []
        if not configurada:
            detalhes.append("nenhuma credencial no arquivo de segredos")
        if provider_id == "openrouter" and settings.openrouter_allow_uncapped_free_tier:
            detalhes.append(
                "opt-in free-tier sem teto configurado; sujeito à validação /key; "
                "uso BYOK fica fora de qualquer teto"
            )
        indisponivel: dict[str, str] = {}
        if inventory is None:
            contagem = None
            indisponivel["endpoint_count"] = motivo_catalogo
        elif provider_id not in cobertos:
            # Provedor novo, ou credencial que só entrou depois da última descoberta.
            # Zero aqui diria que o provedor não oferece nada, quando o que houve é que
            # ninguém perguntou a ele.
            contagem = None
            indisponivel["endpoint_count"] = (
                "a última descoberta não cobriu este provedor; rode `make discover-models`"
            )
        else:
            contagem = len(inventory.select(provider=provider_id))
        linhas.append(
            ProviderState(
                id=provider_id,
                name=PROVIDER_LABEL.get(provider_id, provider_id),
                status="configurado" if configurada else "ausente",
                detail="; ".join(detalhes),
                key_configured=configurada,
                key_hint=mask(segredo.get_secret_value()) if segredo is not None else None,
                endpoint_count=contagem,
                enabled=configurada,
                supports_custom_endpoint=provider_id in CUSTOM_ENDPOINT_PROVIDERS,
                unavailable=indisponivel,
            )
        )
    return linhas


def concurrency_ceiling(role_max: int, budget_calls: int) -> int:
    """O menor entre o teto do papel e o orçamento efetivo da execução.

    O orçamento entra porque não adianta permitir seis tarefas simultâneas quando a
    execução inteira só pode fazer seis chamadas: o teto anunciado seria maior do que
    o que o sistema consegue honrar, e um limite que não se sustenta é pior que um
    limite apertado. O número é o teto do pool vivo, não o sandbox de
    `work_max_calls`.
    """
    return max(0, min(role_max, budget_calls))


def teto_do_inventario(inventory: Inventory | None) -> WorkCeilings | None:
    """O mesmo caminho de teto que o worker usa. Sem catálogo, não há pool."""
    if inventory is None or not inventory.profiles:
        return None
    return ceilings_from_declared(
        (profile.model for profile in inventory.profiles),
        eligible=(profile.aptitude.eligible for profile in inventory.profiles),
    )


def execution_budget(settings: Settings, inventory: Inventory | None = None) -> int:
    """Chamadas por execução visíveis no Atlas e honradas pelo worker."""
    if inventory is None:
        inventory, _, _ = _inventory(settings)
    return effective_max_calls(settings.work_max_calls, teto_do_inventario(inventory))


def _resolve_endpoint(
    inventory: Inventory | None,
    auto: bool,
    preferencia_provider: str | None,
    preferencia_endpoint: str | None,
) -> tuple[EndpointProfile | None, str, str]:
    """Devolve o endpoint efetivo, quem o decidiu e o detalhe da decisão."""
    if inventory is None:
        return None, "indisponivel", "catálogo de endpoints indisponível"
    if auto:
        # A política canônica é a ordem de preferência que o inventário já aplica.
        usaveis = inventory.select(usable=True)
        if not usaveis:
            return None, "indisponivel", "nenhum endpoint utilizável no catálogo"
        return usaveis[0], "auto", "resolvido pela política canônica"
    if preferencia_provider is None or preferencia_endpoint is None:
        return None, "indisponivel", "AUTO desligado e sem preferência manual declarada"
    escolhidos = [
        profile
        for profile in inventory.select(provider=preferencia_provider)
        if profile.endpoint_id == preferencia_endpoint
    ]
    if not escolhidos:
        return None, "indisponivel", "a preferência manual não existe no catálogo atual"
    return escolhidos[0], "manual", "escolha manual"


def _workers(
    preferences: ControlPreferences,
    inventory: Inventory | None,
    em_execucao: dict[str, int],
    budget_calls: int,
) -> list[WorkerState]:
    linhas: list[WorkerState] = []
    # `enumerate` na mesma ordem de `ROLES`, que é a que a projeção operacional usa para
    # escolher a cor do produtor. Ordem diferente aqui daria outro token para a mesma
    # entidade, e o gate de paridade da ADR-005 acusaria diferença de identidade visual.
    for ordem, role in enumerate(ROLES.values()):
        preferencia = preferences.for_worker(role.name)
        profile, resolvido_por, detalhe = _resolve_endpoint(
            inventory,
            preferences.auto,
            preferencia.provider,
            preferencia.endpoint_id,
        )
        teto = concurrency_ceiling(role.max_concurrency, budget_calls)
        # Sem preferência declarada, o efetivo é o teto do papel sob AUTO e zero sem
        # ele: ligar trabalho por omissão seria decidir no lugar do mantenedor.
        if preferencia.concurrency is not None:
            simultaneas = min(preferencia.concurrency, teto)
        else:
            simultaneas = teto if preferences.auto else 0
        rodando = em_execucao.get(role.name, 0)
        estado: Literal["ativo", "inativo", "espera", "erro", "desconhecido"]
        if not preferencia.enabled:
            estado = "inativo"
        elif rodando > 0:
            estado = "ativo"
        elif profile is None:
            estado = "erro"
        else:
            estado = "espera"

        linhas.append(
            WorkerState(
                id=role.name,
                role=role.name,
                palette_token=worker_palette_token(ordem, reviews_others=role.reviews_others),
                class_name="avaliador" if role.reviews_others else "produtor",
                summary=role.summary,
                area=role.area,
                status=estado,
                provider=profile.provider if profile else None,
                model=profile.endpoint_id if profile else None,
                resolved_by=resolvido_por,  # type: ignore[arg-type]
                reasoning=reasoning_support(profile, preferencia.reasoning),
                concurrency=simultaneas,
                concurrency_min=0,
                concurrency_max=teto,
                enabled=preferencia.enabled,
                running=rodando,
                detail=detalhe,
            )
        )
    return linhas


def _operation(
    settings: Settings,
    preferences: ControlPreferences,
    workers: list[WorkerState],
    budget_calls: int,
) -> tuple[OperationState, dict[str, int]]:
    indisponivel: dict[str, str] = {}
    fila: int | None = None
    rodando: int | None = None
    ultimo_ciclo: str | None = None
    falhas: list[str] = []
    por_papel: dict[str, int] = {}

    caminho = settings.state_dir / "autonomy" / "tasks.json"
    if caminho.exists():
        try:
            snapshot = PersistentTaskQueue(caminho).snapshot()
        except Exception as error:  # noqa: BLE001 — a fila não pode derrubar o painel
            indisponivel["queued"] = f"fila ilegível: {type(error).__name__}"
        else:
            fila = sum(1 for task in snapshot.tasks if task.state is TaskState.QUEUED)
            ativas = [
                task
                for task in snapshot.tasks
                if task.state in (TaskState.RUNNING, TaskState.ASSIGNED)
            ]
            rodando = len(ativas)
            for task in ativas:
                for papel in task.required_roles:
                    por_papel[papel] = por_papel.get(papel, 0) + 1
            marcas = [
                attempt.finished_at or attempt.started_at
                for task in snapshot.tasks
                for attempt in task.attempts
            ]
            ultimo_ciclo = max(marcas) if marcas else None
            if ultimo_ciclo is None:
                indisponivel["last_cycle"] = "nenhuma tentativa registrada ainda"
            falhas = [
                f"{task.id}: {task.attempts[-1].detail or task.state.value}"
                for task in snapshot.tasks
                if task.state in (TaskState.BLOCKED, TaskState.REJECTED) and task.attempts
            ][:5]
    else:
        motivo = "a fila autônoma ainda não foi criada; rode `make worker`"
        indisponivel["queued"] = motivo
        indisponivel["last_cycle"] = motivo

    # O worker é acionado por `make worker`, fora desta API: quando ele roda é decisão
    # de quem o iniciou, e afirmar um horário aqui seria previsão, não medida.
    indisponivel["next_run"] = "a próxima execução depende do worker, que roda fora da API"
    indisponivel["calls"] = "o consumo por execução não é persistido entre execuções"
    indisponivel["last_audit"] = "`make audit` roda fora da API e não deixa registro lido aqui"

    ativos = sum(1 for worker in workers if worker.enabled and worker.concurrency > 0)
    capacidade = sum(worker.concurrency_max for worker in workers)

    return (
        OperationState(
            auto=preferences.auto,
            active_workers=ativos,
            capacity=capacidade,
            queued=fila,
            running=rodando,
            last_cycle=ultimo_ciclo,
            next_run=None,
            calls=None,
            budget=f"{budget_calls} chamadas por execução",
            failures=falhas,
            last_audit=None,
            unavailable=indisponivel,
        ),
        por_papel,
    )


def build_snapshot(settings: Settings, preferences: ControlPreferences) -> ControlSnapshot:
    """Uma leitura coerente de tudo que o painel mostra, com a hora em que foi tirada."""
    inventory, cobertos, motivo_catalogo = _inventory(settings)
    notices = [motivo_catalogo] if motivo_catalogo else []
    budget_calls = execution_budget(settings, inventory)

    # Duas passagens: a primeira precisa da contagem por papel, que vem da fila; a
    # segunda precisa dos trabalhadores, que dependem da contagem. Montar a operação
    # com a lista vazia e refazê-la é mais barato que inverter a dependência.
    _, por_papel = _operation(settings, preferences, [], budget_calls)
    workers = _workers(preferences, inventory, por_papel, budget_calls)
    operation, _ = _operation(settings, preferences, workers, budget_calls)

    return ControlSnapshot(
        providers=_providers(settings, inventory, cobertos, motivo_catalogo),
        workers=workers,
        operation=operation,
        notices=notices,
    )
