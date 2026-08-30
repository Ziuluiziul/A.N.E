"""Camada operacional: procedência, não conhecimento.

O dossiê pede duas redes coordenadas e **não misturadas**. A epistêmica é persistente
e vem de `knowledge/`; a operacional é temporal e registra o que os agentes fizeram —
`agente → atividade → evidência → proposta → validação → commit ou rejeição`.

Em produção essa rede nasce da persistência estruturada em `runtime/quorum/`. O Atlas
recebe apenas uma lista branca de metadados: identidade operacional, voto, confiança,
contagem e decisão. Respostas livres nunca atravessam esta fronteira. Sob
`VAULT_DEMO_OPERATIONAL=1` continua existindo uma trilha sintética explicitamente
marcada como demonstração; ela nunca é consequência de falha de leitura.

Duas coisas que esta camada nunca representa: raciocínio interno de modelo, e
qualquer coisa dentro de `knowledge/`.
"""

from __future__ import annotations

import hashlib
import re
import stat
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import orjson

from vault.events import OperationalEvent
from vault.work.roles import ROLES

OperationalKind = Literal[
    "agent",
    "activity",
    "evidence",
    "proposal",
    "commit",
    "rejection",
    "temporary-file",
    "quorum-panel",
    "quorum-member",
    "quorum-vote",
    "quorum-decision",
]

OPERATIONAL_KINDS: tuple[OperationalKind, ...] = (
    "agent",
    "activity",
    "evidence",
    "proposal",
    "commit",
    "rejection",
    "temporary-file",
    "quorum-panel",
    "quorum-member",
    "quorum-vote",
    "quorum-decision",
)

# Estado canônico por tipo operacional. Proposta é vazada, temporário é hachurado,
# rejeição é preservada com corte — nenhum deles pode parecer nota canônica.
STATE_BY_KIND: dict[OperationalKind, str] = {
    "agent": "temporary",
    "activity": "temporary",
    "evidence": "temporary",
    "proposal": "proposed",
    "commit": "canonical",
    "rejection": "rejected",
    "temporary-file": "temporary",
    "quorum-panel": "temporary",
    "quorum-member": "temporary",
    "quorum-vote": "temporary",
    "quorum-decision": "temporary",
}

DEMO_DOMAIN = {"id": "operacional", "label": "operacional"}
QUORUM_DOMAIN = {"id": "operacional/quorum", "label": "quórum"}
MODEL_DOMAIN = {"id": "operacional/modelos", "label": "modelos"}
# Provedor tem domínio próprio desde que o acervo passou de 30 para 193 modelos: como
# satélite de si mesmo dentro da nuvem de modelos, a âncora sumia no meio dos filhos.
PROVIDER_DOMAIN = {"id": "operacional/provedores", "label": "provedores"}
# O trabalhador ganhou domínio próprio quando a configuração dele saiu do menu e virou
# painel: até aqui os sete papéis só existiam na cena como votos dentro de centenas de
# painéis de quórum, e não havia nenhum nó que fosse **o** verificador factual — logo,
# nenhuma placa a que ancorar "ativo", "simultâneas" e "raciocínio".
WORKER_DOMAIN = {"id": "operacional/trabalhadores", "label": "trabalhadores"}

# A cor da nuvem de modelos é a **da marca do provedor**, e não uma posição numa lista.
#
# Ela era atribuída por ordem alfabética a partir de uma lista fechada de tokens de
# domínio: dizia de quem é o painel, mas dizia por convenção interna — e mudava de cor
# quando um provedor novo entrava antes dele no alfabeto. O token de marca é estável e
# reconhecível sem aprender nada.
#
# `P:` é resolvido em `palette.ts`, que guarda o matiz oficial de cada provedor na
# luminosidade da cena. Provedor sem marca declarada cai na lista ciclada de antes, que
# continua existindo para nunca deixar um nó sem cor.
_PROVIDER_TOKENS = {
    "groq": "P:groq",
    "google": "P:google",
    "nvidia": "P:nvidia",
    "nous": "P:nous",
    "ollama": "P:ollama",
    "openrouter": "P:openrouter",
}
_MODEL_TOKENS = ("D02", "D07", "D10", "D04", "D12", "D08")


def worker_palette_token(ordem: int, *, reviews_others: bool) -> str:
    """A cor de um trabalhador. Uma regra só, para dois consumidores.

    Avaliador e produtor se distinguem pela cor porque é a distinção que governa o
    quórum: só quem avalia conta para o mínimo de votos. A função existe porque o
    snapshot de controle passou a carregar o mesmo token — o runtime possui a entidade
    e portanto a descreve —, e duas implementações da mesma cor divergiriam no dia em
    que alguém mexesse numa delas.
    """
    return "D08" if reviews_others else _MODEL_TOKENS[ordem % len(_MODEL_TOKENS)]
