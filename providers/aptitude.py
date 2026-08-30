"""Classifica cada endpoint descoberto por modalidade, propósito e estabilidade.

A descoberta diz o que existe; esta camada diz para que serve. Nada aqui é medição:
são leituras do identificador e dos metadados que a própria API declarou. Por isso
toda exclusão carrega o motivo em texto — quem discordar da regra vê de onde ela veio
e corrige a regra, não o resultado.

A ordem de preferência não elege o "melhor modelo". Ela ordena candidatos para que a
sonda seja dirigida em vez de alfabética. Evidência mesmo só vem da sonda, e mora no
registro operacional (`providers.registry`), que tem precedência sobre qualquer
palpite feito a partir do nome.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from providers.base import ModelInfo

# --- vocabulários fechados ---------------------------------------------------

# Modalidade dominante da saída. `text` não afirma qualidade: afirma apenas que nada
# no catálogo indica que o endpoint produza outra coisa.
MODALITIES = ("text", "image", "video", "audio", "embedding", "ranking")

# Propósito declarado pelo nome. `general` é o único que não carrega especialização.
PURPOSES = (
    "general",
    "domain",
    "multimodal",
    "code",
    "translation",
    "transcription",
    "retrieval",
    "safety",
    "reward",
    "parsing",
    "robotics",
    "computer-use",
    "research-agent",
    "live",
)

STABILITIES = ("stable", "alias", "preview")

# Propósitos que ainda servem a trabalho textual geral, em ordem de preferência.
ELIGIBLE_PURPOSES = ("general", "domain", "multimodal", "code")

_PURPOSE_RANK = {purpose: index for index, purpose in enumerate(ELIGIBLE_PURPOSES)}
_STABILITY_RANK = {stability: index for index, stability in enumerate(STABILITIES)}


# --- sinais vindos das capabilities ------------------------------------------

# Google e Ollama declaram ações por endpoint. Quando elas existem, mandam mais que o
# nome — mas os dois vocabulários não se traduzem: `predict` e `embedContent` só
# existem de um lado, e `tools`, `thinking` e `vision` só do outro.
_ACTION_MODALITY = (
    ("embedcontent", "embedding", "declara embedContent"),
    ("predictlongrunning", "video", "declara predictLongRunning"),
    ("predict", "image", "declara predict"),
)

# Como cada provedor diz "este endpoint gera texto". Ler só `generateContent` foi
# correto enquanto o Google era o único a declarar ações: quando a Ollama passou a
# declarar as dela, todo modelo da nuvem virou `retrieval` inelegível por não falar uma
# palavra que a API dele não usa. O que importa é a capacidade, não o dialeto.
_GENERATION_ACTIONS = frozenset({"generatecontent", "completion"})


# --- sinais vindos do identificador ------------------------------------------

# Cada marcador é uma aposta explícita sobre o nome, não sobre o modelo. Ordem importa:
# o primeiro que casar decide, então o mais específico vem antes.
_PURPOSE_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("retrieval", ("embed", "retriev", "rerank", "bge-", "arctic", "nvclip")),
    ("safety", ("guard", "safety", "topic-control", "detector", "moderation")),
    ("reward", ("reward",)),
    ("parsing", ("parse", "deplot", "ocr")),
    ("translation", ("translate", "translation")),
    ("transcription", ("whisper", "transcri")),
    ("robotics", ("robotics",)),
    ("computer-use", ("computer-use",)),
    ("research-agent", ("deep-research", "antigravity", "compound")),
    ("code", ("code", "coder", "starcoder", "codestral")),
    ("multimodal", ("vision", "-vl-", "-vl", "vlm", "kosmos", "neva", "vila", "fuyu")),
)

# Domínio se reconhece por token inteiro, não por trecho: `mistral-medium` contém
# "med" e não é modelo médico. Substring aqui produziria exclusão errada e calada.
_DOMAIN_TOKENS = frozenset({"med", "medical", "fin", "finance", "bio", "legal", "creative"})

_MODALITY_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("image", ("imagen", "nano-banana", "-image", "diffusion", "nvclip")),
    ("video", ("veo",)),
    ("audio", ("tts", "native-audio", "orpheus", "lyria", "speech")),
    ("embedding", ("embed", "bge-", "arctic-embed")),
    ("ranking", ("rerank", "reward")),
)

_PREVIEW_MARKERS = ("preview", "experimental", "-exp", "-rc", "-beta", "-alpha")

# `-latest` resolve para outro modelo sem aviso. Num corpus que registra procedência,
# um apelido móvel não é instável nem estável: é irrastreável. Fica entre os dois.
_ALIAS_MARKERS = ("-latest", "latest-")

# Tamanho de parâmetros (`70b`, `8x22b`, `800m`) não é versão.
_SIZE_TOKEN = re.compile(r"^(?:\d+x)?\d+(?:\.\d+)?[bmk]$")
_TRAILING_NUMBER = re.compile(r"(\d+(?:\.\d+)?)$")


@dataclass(frozen=True, slots=True)
class Aptitude:
    """O que se pode dizer de um endpoint antes de gastar uma chamada nele."""

    provider: str
    endpoint_id: str
    family: str
    modality: str
    purpose: str
    stability: str
    context_window: int | None
    version: tuple[int, int]
    eligible: bool
    reason: str

    @property
    def key(self) -> str:
        return f"{self.provider}/{self.endpoint_id}"


def parse_version(endpoint_id: str) -> tuple[int, int]:
    """Extrai `major.minor` do identificador. Desempate, não taxonomia.

    Devolve `(0, 0)` quando o nome não carrega versão — `gpt-oss-120b` não declara
    nenhuma, e fingir que declara seria pior do que admitir a ausência. Comparar
    versões entre famílias diferentes não significa nada; só usamos a comparação
    dentro da mesma lista de candidatos, e a sonda corrige o que a ordem errar.

    `:` separa como `-` e `_` por causa da Ollama, que o usa para a etiqueta de
    tamanho. Sem ele `qwen3.5:397b` é um token só que termina em letra, e a versão
    declarada no nome se perderia inteira — não em favor de um palpite pior, mas de
    nenhum. Nos outros provedores nenhum identificador tem `:`.
    """
    tail = endpoint_id.rsplit("/", 1)[-1].lower()
    for token in re.split(r"[-_:]", tail):
        if not token or _SIZE_TOKEN.match(token):
            continue
        found = _TRAILING_NUMBER.search(token)
        if found is None:
            continue
        number = found.group(1)
        # `001` é revisão e `2026` é data; nenhum dos dois é versão de modelo.
        if "." not in number and len(number) >= 3:
            continue
        major, _, minor = number.partition(".")
        return int(major), int(minor or 0)
    return 0, 0


def _search(
    text: str,
    markers: tuple[tuple[str, tuple[str, ...]], ...],
) -> tuple[str, str] | None:
    for label, needles in markers:
        for needle in needles:
            if needle in text:
                return label, needle
    return None


def classify(model: ModelInfo) -> Aptitude:
    """Lê nome, capabilities e metadados; devolve a leitura junto com o motivo dela."""
    endpoint = model.endpoint_id.lower()
    display = str(model.raw.get("display_name") or "").lower()
    text = f"{endpoint} {display}"
    actions = {action.lower() for action in model.capabilities}

    modality = "text"
    purpose = "general"
    reason = "nada no catálogo indica saída não textual"

    if actions:
        for action, action_modality, motivo in _ACTION_MODALITY:
            if action in actions:
                modality, reason = action_modality, motivo
                break
        else:
            if not actions & _GENERATION_ACTIONS:
                # `aqa` só faz generateAnswer e os endpoints Live só fazem
                # bidiGenerateContent: nenhum atende a uma geração comum.
                purpose = "live" if "bidigeneratecontent" in actions else "retrieval"
                reason = f"não declara geração de texto: {', '.join(sorted(actions))}"

    if purpose == "general":
        found_purpose = _search(text, _PURPOSE_MARKERS)
        if found_purpose is not None:
            purpose, needle = found_purpose
            reason = f"o identificador contém '{needle}'"
        else:
            especialidade = _DOMAIN_TOKENS & set(re.split(r"[-_/.]", endpoint))
            if especialidade:
                purpose = "domain"
                reason = f"o identificador declara o domínio '{min(especialidade)}'"

    if modality == "text":
        found_modality = _search(text, _MODALITY_MARKERS)
        if found_modality is not None:
            modality, needle = found_modality
            reason = f"o identificador contém '{needle}'"

    stability = "stable"
    if any(marker in endpoint for marker in _ALIAS_MARKERS):
        stability = "alias"
    if any(marker in endpoint for marker in _PREVIEW_MARKERS):
        stability = "preview"

    eligible = model.available and modality == "text" and purpose in _PURPOSE_RANK
    if not model.available:
        reason = "o provedor não lista o endpoint como disponível"
    elif eligible and purpose == "general":
        reason = "texto geral, sem especialização declarada no nome"

    return Aptitude(
        provider=model.provider,
        endpoint_id=model.endpoint_id,
        family=model.family,
        modality=modality,
        purpose=purpose,
        stability=stability,
        context_window=model.context_window,
        version=parse_version(model.endpoint_id),
        eligible=eligible,
        reason=reason,
    )


def preference_key(aptitude: Aptitude) -> tuple[int, int, int, int, int, str]:
    """Ordem de preferência para trabalho textual. Menor é melhor.

    Propósito antes de estabilidade: um preview de propósito geral serve ao corpus
    melhor que um modelo médico estável. Janela declarada antes de versão porque a
    janela vem da API e a versão vem do nome.
    """
    major, minor = aptitude.version
    return (
        _PURPOSE_RANK.get(aptitude.purpose, len(_PURPOSE_RANK)),
        _STABILITY_RANK.get(aptitude.stability, len(_STABILITY_RANK)),
        -(aptitude.context_window or 0),
        -major,
        -minor,
        aptitude.endpoint_id,
    )


# Quanto uma observação anterior adia uma nova sonda. Nunca proíbe: um 404 de
# ontem pode ser um endpoint que voltou, e o registro precisa poder ser corrigido.
#
# A ordem é por incerteza decrescente. `reachable` vem antes de `ok` porque dele ainda
# não se sabe o principal: sob orçamento maior, escreveria algo útil?
_PROBE_ORDER = {None: 0, "rate_limited": 1, "reachable": 2, "ok": 3}
_PROBE_LAST = 4


def classify_all(models: list[ModelInfo]) -> list[Aptitude]:
    return [classify(model) for model in models]


def ranked_candidates(models: list[ModelInfo]) -> list[Aptitude]:
    """Elegíveis a trabalho textual, do mais preferido ao menos."""
    return sorted(
        (aptitude for aptitude in classify_all(models) if aptitude.eligible),
        key=preference_key,
    )


def select_for_probe(
    models: list[ModelInfo],
    statuses: dict[str, str] | None = None,
) -> Aptitude | None:
    """Escolhe onde gastar a única chamada desta execução.

    Prefere o melhor candidato ainda não sondado: reconfirmar o que já respondeu não
    produz informação nova. Endpoints que falharam entram por último, e entram — se
    ficassem fora para sempre, o registro viraria uma sentença sem revisão.
    """
    observed = statuses or {}
    candidates = ranked_candidates(models)
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda aptitude: (
            _PROBE_ORDER.get(observed.get(aptitude.endpoint_id), _PROBE_LAST),
            preference_key(aptitude),
        ),
    )


def select_for_work(
    models: list[ModelInfo],
    statuses: dict[str, str],
) -> Aptitude | None:
    """Escolhe onde colocar trabalho de verdade: só o que já produziu texto.

    `reachable` não basta. Um endpoint que devolve 200 vazio está comprovadamente
    alcançável e não comprovadamente útil, e mandar trabalho para ele seria tratar a
    ausência de evidência como evidência.
    """
    confirmed = [
        aptitude
        for aptitude in ranked_candidates(models)
        if statuses.get(aptitude.endpoint_id) == "ok"
    ]
    return min(confirmed, key=preference_key) if confirmed else None
