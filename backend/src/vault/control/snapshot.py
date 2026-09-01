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
provedor e o modelo que o AUTO resolve saem de `Inventory.for_work()`, que já
devolve na ordem de preferência canônica — reimplementar a escolha aqui criaria uma
segunda política que divergiria da primeira no primeiro ajuste.

Quando uma fonte não está disponível, o campo correspondente vira `None` e o motivo
entra em `unavailable`. Nenhum caminho deste arquivo produz zero para dizer "não sei".
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Literal

import orjson

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
    """Teto do pool que o AUTO realmente chama, não do catálogo inteiro.

    Somar RPM de preview/alias e de modelo nunca sondado inflava o cartão
    para dezenas de milhares de "chamadas por execução".
    """
    if inventory is None:
        return None
    usaveis = inventory.for_work()
    if not usaveis:
        return None
    return ceilings_from_declared(
        (profile.model for profile in usaveis),
        eligible=(True for _ in usaveis),
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
        usaveis = inventory.for_work()
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


def _auto_pool(
    inventory: Inventory | None, n: int
) -> list[tuple[EndpointProfile | None, str, str]]:
    """O AUTO do painel mostra o pool, não sete vezes o primeiro do ranking.

    O orquestrador espalha papéis por provedor distinto; pintar todo trabalhador
    com ``for_work()[0]`` fazia o Atlas jurar que só existia um SKU.
    """
    if inventory is None:
        return [(None, "indisponivel", "catálogo de endpoints indisponível")] * n
    usaveis = inventory.for_work()
    if not usaveis:
        return [(None, "indisponivel", "nenhum endpoint utilizável no catálogo")] * n
    distintos: list[EndpointProfile] = []
    vistos: set[str] = set()
    for profile in usaveis:
        if profile.provider in vistos:
            continue
        distintos.append(profile)
        vistos.add(profile.provider)
    ordered = [*distintos, *[p for p in usaveis if p not in distintos]]
    return [
        (ordered[i % len(ordered)], "auto", "resolvido pela política canônica")
        for i in range(n)
    ]


def _workers(
    preferences: ControlPreferences,
    inventory: Inventory | None,
    em_execucao: dict[str, int],
    budget_calls: int,
) -> list[WorkerState]:
    linhas: list[WorkerState] = []
    papeis = list(ROLES.values())
    auto_pool = (
        _auto_pool(inventory, len(papeis)) if preferences.auto else None
    )
    # `enumerate` na mesma ordem de `ROLES`, que é a que a projeção operacional usa para
    # escolher a cor do produtor. Ordem diferente aqui daria outro token para a mesma
    # entidade, e o gate de paridade da ADR-005 acusaria diferença de identidade visual.
    for ordem, role in enumerate(papeis):
        preferencia = preferences.for_worker(role.name)
        if auto_pool is not None:
            profile, resolvido_por, detalhe = auto_pool[ordem]
        else:
            profile, resolvido_por, detalhe = _resolve_endpoint(
                inventory,
                False,
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


def _carregar_fila(
    settings: Settings,
) -> tuple[Any | None, str | None]:
    """Uma leitura da fila. ``None, None`` = arquivo ainda não existe."""
    caminho = settings.state_dir / "autonomy" / "tasks.json"
    if not caminho.exists():
        return None, None
    try:
        return PersistentTaskQueue(caminho).snapshot(), None
    except Exception as error:  # noqa: BLE001 — a fila não pode derrubar o painel
        return None, f"fila ilegível: {type(error).__name__}"


def _operation(
    settings: Settings,
    preferences: ControlPreferences,
    workers: list[WorkerState],
    budget_calls: int,
    *,
    fila_snapshot: Any | None = None,
    fila_erro: str | None = None,
    fila_lida: bool = False,
) -> tuple[OperationState, dict[str, int]]:
    indisponivel: dict[str, str] = {}
    fila: int | None = None
    rodando: int | None = None
    ultimo_ciclo: str | None = None
    falhas: list[str] = []
    por_papel: dict[str, int] = {}

    if fila_lida:
        snapshot = fila_snapshot
        erro = fila_erro
        existe = snapshot is not None or erro is not None
    else:
        snapshot, erro = _carregar_fila(settings)
        existe = (settings.state_dir / "autonomy" / "tasks.json").exists()

    if erro is not None:
        indisponivel["queued"] = erro
    elif snapshot is not None:
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
    elif not existe:
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


def _stat_signature(path: Path) -> tuple[int, int]:
    try:
        stat = path.stat()
    except OSError:
        return (0, 0)
    return (stat.st_mtime_ns, stat.st_size)


def _catalog_signature(state_dir: Path) -> tuple[Any, ...]:
    try:
        return tuple(
            sorted(
                (path.name, _stat_signature(path))
                for path in state_dir.iterdir()
                if path.name.startswith("models-") and path.suffix == ".json"
            )
        )
    except OSError:
        return ()


def _credential_fingerprint(settings: Settings) -> tuple[Any, ...]:
    """Dica mascarada, nunca o valor. Dois Settings com a mesma dica batem."""
    pares = (
        ("google", settings.gemini_api_key),
        ("groq", settings.groq_api_key),
        ("nvidia", settings.nvidia_api_key),
        ("ollama", settings.ollama_api_key),
        ("nous", settings.nous_api_key),
        ("openrouter", settings.openrouter_api_key),
    )
    return tuple(
        (provedor, mask(chave.get_secret_value()) if chave is not None else None)
        for provedor, chave in pares
    )


def _snapshot_signature(
    settings: Settings, preferences: ControlPreferences
) -> tuple[Any, ...]:
    """Barato: mtime do que o snapshot lê. Não varre o quórum — isso é overlay."""
    state = settings.state_dir
    return (
        str(settings.runtime_dir.resolve(strict=False)),
        settings.work_max_calls,
        settings.worker_concurrency,
        settings.openrouter_allow_uncapped_free_tier,
        tuple(sorted(settings.provider_concurrency.items())),
        _credential_fingerprint(settings),
        _stat_signature(settings.secrets_file),
        _stat_signature(state / "autonomy" / "tasks.json"),
        _stat_signature(state / "control.json"),
        _stat_signature(state / "endpoints.json"),
        _catalog_signature(state),
        orjson.dumps(preferences.model_dump(mode="json"), option=orjson.OPT_SORT_KEYS),
    )


_SNAPSHOT_LOCK = threading.Lock()
_SNAPSHOT_CACHE: tuple[tuple[Any, ...], ControlSnapshot] | None = None


def clear_control_snapshot_cache() -> None:
    """Só testes: o cache é por processo, e um tmp_path reutilizado mentiria."""
    global _SNAPSHOT_CACHE
    with _SNAPSHOT_LOCK:
        _SNAPSHOT_CACHE = None


def _assemble_snapshot(
    settings: Settings, preferences: ControlPreferences
) -> ControlSnapshot:
    inventory, cobertos, motivo_catalogo = _inventory(settings)
    notices = [motivo_catalogo] if motivo_catalogo else []
    budget_calls = execution_budget(settings, inventory)

    fila_snapshot, fila_erro = _carregar_fila(settings)
    # Duas passagens sobre o **mesmo** retrato: a primeira precisa da contagem por
    # papel; a segunda, dos trabalhadores. Relê o disco uma vez, não duas.
    _, por_papel = _operation(
        settings,
        preferences,
        [],
        budget_calls,
        fila_snapshot=fila_snapshot,
        fila_erro=fila_erro,
        fila_lida=True,
    )
    workers = _workers(preferences, inventory, por_papel, budget_calls)
    operation, _ = _operation(
        settings,
        preferences,
        workers,
        budget_calls,
        fila_snapshot=fila_snapshot,
        fila_erro=fila_erro,
        fila_lida=True,
    )

    return ControlSnapshot(
        providers=_providers(settings, inventory, cobertos, motivo_catalogo),
        workers=workers,
        operation=operation,
        notices=notices,
    )


def build_snapshot(settings: Settings, preferences: ControlPreferences) -> ControlSnapshot:
    """Uma leitura coerente de tudo que o painel mostra, com a hora em que foi tirada.

    Recicla o objeto enquanto mtime e settings não mudam. O GET do painel chega a
    cada poucos segundos; reler ``tasks.json`` com ``LOCK_EX`` nessa cadência é o
    que saturava o threadpool. O rótulo de orçamento continua saindo de
    ``execution_budget`` — o cache não inventa número.
    """
    global _SNAPSHOT_CACHE
    key = _snapshot_signature(settings, preferences)
    with _SNAPSHOT_LOCK:
        cached = _SNAPSHOT_CACHE
        if cached is not None and cached[0] == key:
            return cached[1]
    snapshot = _assemble_snapshot(settings, preferences)
    with _SNAPSHOT_LOCK:
        _SNAPSHOT_CACHE = (key, snapshot)
    return snapshot
