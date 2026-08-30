"""Fronteira entre cognição (conteúdo não confiável) e autoridade operacional externa.

O A.N.E. lerá, cedo ou tarde, coisas que não devem comandá-lo: notas do corpus,
issues, PRs, e-mails, documentos do Drive, páginas web. Qualquer uma pode carregar
uma instrução adversarial — um "prompt injection". O quórum e o promoter protegem a
*integridade do patch*; eles não protegem contra um texto que convence o agente a
*solicitar* uma capability legítima porém perigosa (abrir PR, deletar repo, ampliar
scope). Essa é uma fronteira diferente, e tem de ser explícita.

Princípios deste módulo:

- **Conteúdo não confiável é dado, jamais autoridade.** `UntrustedContent` carrega o
  texto e a origem, mas não tem poder de comando.
- **Autoridade via operação estruturada, com schema de argumentos.** `CapabilityRequest`
  traz `operation` (do conjunto conhecido) + `target` (recurso) + `args`, e **cada
  operation tem um schema próprio de argumentos**. Argumentos fora do schema, ou ausentes
  obrigatórios, são recusados — isso impede "smuggling" de parâmetros via `args`.
- **A policy decide allow/deny por allowlist versionada, e nunca recebe o texto de origem.**
  Ela também valida o `target` contra uma lista de recursos autorizados (defesa de
  *confused deputy*: um conteúdo não confiável não pode apontar a ação para um recurso
  privilegiado que o agente não deveria tocar).
- **`AuthorizedCapability` é distinta de `CapabilityRequest`.** A request é a *intenção*
  (pode ser negada); a `AuthorizedCapability` é o *poder concedido* — carrega grant id,
  escopo vinculado e validade. A Tool Layer consome só `AuthorizedCapability`; confundir
  as duas seria tratar "quero" como "autorizado".
- **O mapper é a única ponte texto→request.** Ele só emite operations conocidas; texto que
  peça "altere a política" ou "conceda admin" não vira request algum.

Fluxo:

```
UntrustedContent (corpus/issue/doc/email)
   ↓  mapper estrito (só operations conhecidas, args no schema)
CapabilityRequest[]  (estruturado, validado contra schema)
   ↓  AuthorizationPolicy.authorize  (allowlist + target binding + schema)
AuthorizedCapability | DENY
   ↓  só se AuthorizedCapability
Capability Tool Layer → Credential Broker → API externa
```
"""

from __future__ import annotations

import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

# Argumentos como tupla de pares ordenada: imutável e canônica. A fronteira aceita
# Mapping[str, str] externamente, mas canonicaliza para esta forma na construção.
Args = tuple[tuple[str, str], ...]

# Operations conhecidas. Tudo que não estiver aqui é, por construção, recusado.
KNOWN_OPERATIONS: frozenset[str] = frozenset(
    {
        "read_repository",
        "read_commits",
        "read_branches",
        "read_issues",
        "read_pull_requests",
        "read_checks",
        "read_workflows",
        "create_branch",
        "prepare_commit",
        "open_pull_request",
        "track_ci",
    }
)

# Operations que, por padrão, NUNCA entram na allowlist mesmo se alguém as listar num
# arquivo de política. São as que mais ampliariam autoridade se fossem concedidas por
# engano ou por injeção.
FORBIDDEN_OPERATIONS: frozenset[str] = frozenset(
    {
        "delete_repository",
        "admin_repository",
        "write_workflow",
        "modify_policy",
        "grant_scope",
        "push_to_protected",
    }
)


class AuthorityError(RuntimeError):
    """A fronteira de autoridade recusou a operação ou rejeitou a entrada."""


@dataclass(frozen=True, slots=True)
class UntrustedContent:
    """Texto de origem não confiável. Dado, jamais autoridade.

    ``source`` identifica de onde veio para auditoria — não para decidir permissão.
    """

    text: str
    source: str

    def __post_init__(self) -> None:
        if not self.source:
            raise AuthorityError("conteúdo não confiável precisa de uma origem declarada")


@dataclass(frozen=True, slots=True)
class ArgSpec:
    """Descreve um argumento de uma capability.

    ``required`` sem default é obrigatório; ``allowed`` restringe os valores (se dado).
    ``secret`` marca argumentos que nunca devem aparecer em log (ex.: token de callback).
    """

    name: str
    required: bool = False
    allowed: frozenset[str] | None = None
    secret: bool = False


# Schema de argumentos por operation. Só estes nomes são aceitos; qualquer outro em
# `args` é recusado (defesa contra smuggling de parâmetros). Operations puramente
# read-only não exigem argumentos.
ARG_SCHEMAS: dict[str, tuple[ArgSpec, ...]] = {
    "read_repository": (),
    "read_commits": (),
    "read_branches": (),
    "read_issues": (),
    "read_pull_requests": (),
    "read_checks": (),
    "read_workflows": (),
    "track_ci": (),
    "create_branch": (
        ArgSpec(name="branch", required=True),
        ArgSpec(name="base", required=False),
    ),
    "prepare_commit": (
        ArgSpec(name="branch", required=True),
    ),
    "open_pull_request": (
        ArgSpec(name="branch", required=True),
        ArgSpec(name="base", required=False, allowed=frozenset({"main"})),
    ),
}


def _canon_args(raw: Mapping[str, str] | Args) -> Args:
    """Converte em tupla de pares ordenada (canônica e imutável).

    Aceita ``Mapping[str, str]`` ou ``Args`` (tupla de pares). Tipo errado ou chave
    duplicada é DENY, não coerção/silenciamento.
    """
    if isinstance(raw, tuple):
        pares = list(raw)
    else:
        if not isinstance(raw, Mapping):
            raise AuthorityError("args deve ser um Mapping de str->str")
        for k, v in raw.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise AuthorityError(
                    f"args exige str->str; recebeu {type(k).__name__}->{type(v).__name__}"
                )
        pares = list(raw.items())
    chaves = [k for k, _ in pares]
    if len(chaves) != len(set(chaves)):
        raise AuthorityError("args contém chave duplicada; representação não é canônica")
    return tuple(sorted(pares))


def _validate_args(operation: str, args: Mapping[str, str] | Args) -> None:
    """Recusa argumentos fora do schema ou obrigatórios ausentes.

    Preserva o modelo real `ARG_SCHEMAS: dict[str, tuple[ArgSpec, ...]]`. Schema vazio
    (``()``) significa "nenhum argumento permitido", não "sem schema".
    """
    if isinstance(args, tuple):
        args = {k: v for k, v in args}
    schema: tuple[ArgSpec, ...] = ARG_SCHEMAS.get(operation, ())
    conhecidos = {spec.name for spec in schema}
    for nome, valor in args.items():
        if nome not in conhecidos:
            raise AuthorityError(
                f"argumento '{nome}' não pertence ao schema de '{operation}'"
            )
        spec = next(s for s in schema if s.name == nome)
        if spec.allowed is not None and valor not in spec.allowed:
            raise AuthorityError(
                f"argumento '{nome}={valor}' fora dos valores permitidos para '{operation}'"
            )
    ausentes = [spec.name for spec in schema if spec.required and spec.name not in args]
    if ausentes:
        raise AuthorityError(
            f"argumentos obrigatórios ausentes para '{operation}': {', '.join(ausentes)}"
        )


@dataclass(frozen=True, slots=True)
class CapabilityRequest:
    """Intenção de operação, vinda do mapper. Pode ser negada.

    Sem texto livre: ``operation`` vem de ``KNOWN_OPERATIONS``, ``target`` é um recurso
    identificado, e ``args`` só traz nomes do schema da operation. Os args são
    canonicalizados para ``Args`` (tupla imutável) já na construção.
    """

    operation: str
    target: str
    args: Args | Mapping[str, str] = ()

    def __post_init__(self) -> None:
        if self.operation not in KNOWN_OPERATIONS:
            raise AuthorityError(f"operation fora do conjunto conhecido: {self.operation!r}")
        # Sempre canonicaliza para Args (tupla imutável), detectando chave duplicada.
        object.__setattr__(self, "args", _canon_args(self.args))
        _validate_args(self.operation, self.args)


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class AuthorizedCapability:
    """Poder efetivamente concedido, após a policy aprovar.

    Distinta de `CapabilityRequest`: a request é o que *se quer*; esta é o que *se pode*.
    Carrega grant id (auditoria) e o escopo de recurso vinculado. A Tool Layer consome só
    isto — nunca confunde intenção com autorização. Os args são a mesma tupla imutável
    da request (seguro compartilhar a referência).
    """

    grant_id: str
    operation: str
    target: str
    args: Args = ()
    policy_version: str = "indefinido"


@dataclass(frozen=True, slots=True)
class AuthorizationPolicy:
    """Allowlist determinística, carregada de dados versionados.

    Decide allow/deny a partir de um arquivo (``load``), não de texto de origem. ``authorize``
    recebe só a `CapabilityRequest` — o conteúdo que a originou não entra aqui. Operations
    proibidas são barradas mesmo que o arquivo as liste. O ``target`` é conferido contra
    ``allowed_targets``: defesa de *confused deputy* — um texto injetado não direciona a
    ação a um recurso privilegiado fora da lista do agente. ``allowed_targets`` vazio
    significa **deny-all** (nenhum target autorizado), não allow-all.
    """

    allowed: frozenset[str] = frozenset()
    allowed_targets: frozenset[str] = frozenset()
    version: str = "indefinido"

    @classmethod
    def load(cls, path: Path | None) -> AuthorizationPolicy:
        if path is None or not path.is_file():
            return cls(version="em-branco")
        try:
            import json

            dados = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls(version="ilegível")
        permitidas = dados.get("allowed_capabilities")
        if not isinstance(permitidas, list):
            permitidas = []
        limpas = {
            op
            for op in permitidas
            if isinstance(op, str)
            and op in KNOWN_OPERATIONS
            and op not in FORBIDDEN_OPERATIONS
        }
        alvos = dados.get("allowed_targets")
        if not isinstance(alvos, list):
            alvos = []
        alvos_limpos = {a for a in alvos if isinstance(a, str)}
        versao = str(dados.get("policy_version") or "indefinido")
        return cls(
            allowed=frozenset(limpas),
            allowed_targets=frozenset(alvos_limpos),
            version=versao,
        )

    def authorize(self, request: CapabilityRequest) -> AuthorizedCapability | None:
        """Devolve uma `AuthorizedCapability` se aprovada, ou `None` (DENY)."""
        if request.operation in FORBIDDEN_OPERATIONS:
            return None
        if request.operation not in self.allowed:
            return None
        # Confused deputy: o target tem de estar na lista vinculada ao agente. allowed_targets
        # vazio significa deny-all (não há target autorizado). Sem exceção silenciosa.
        if request.target not in self.allowed_targets:
            return None
        # Revalida os argumentos canônicos antes de fabricar o grant, para que uma mutação
        # da request após a construção não contamine a autorização.
        _validate_args(request.operation, request.args)
        args = request.args if isinstance(request.args, tuple) else _canon_args(request.args)
        return AuthorizedCapability(
            grant_id=secrets.token_hex(16),
            operation=request.operation,
            target=request.target,
            args=args,
            policy_version=self.version,
        )


# O mapper é a ÚNICA ponte de texto para request. Estrito: só operations conocidas e
# argumentos dentro do schema. Assinatura: UntrustedContent -> list[CapabilityRequest].
ContentMapper = Callable[[UntrustedContent], list[CapabilityRequest]]


def map_content_to_requests(
    content: UntrustedContent,
    mapper: ContentMapper,
    policy: AuthorizationPolicy,
) -> list[AuthorizedCapability]:
    """Ponte texto→autoridade, com a policy aplicada a cada request.

    O mapper produz candidates (já validadas contra o schema de args em `CapabilityRequest`);
    a policy filtra por allowlist e por target binding. O resultado contém só
    `AuthorizedCapability` — objetos de poder efetivo, não meras intenções. O texto de
    origem nunca alcança a policy.
    """
    aprovadas: list[AuthorizedCapability] = []
    for req in mapper(content):
        concedida = policy.authorize(req)
        if concedida is not None:
            aprovadas.append(concedida)
    return aprovadas
