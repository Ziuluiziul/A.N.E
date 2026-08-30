"""O patch que altera o próprio código — ADR-006.

**Tipo próprio, e não uma flexibilização do `CorpusPatch`.** Misturar os dois faria a
guarda de redução do corpus, que conta claims e wikilinks, opinar sobre Python; e faria a
guarda daqui, que é o gate mecânico, valer para nota. São duas coisas com o mesmo formato
e critérios de correção incompatíveis.

A inversão que justifica este arquivo existir está na ADR-006: o quórum não está pronto
para julgar verdade — 296 tentativas produziram uma decisão, e ela aprovou um stub —, mas
não precisa julgar verdade para editar código. Precisa produzir alteração que passe em
`audit`, `test` e `lint`, que são determinísticos e já rodam a cada commit desta casa.
Onde a correção é mecânica, a autonomia é segura antes de o julgamento amadurecer.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Literal

import orjson
from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_FILE_BYTES = 512_000
MAX_FILES_POR_PATCH = 6

# **A lista de negação da ADR-006.**
#
# O sistema não altera aquilo que o julga. É a regra da ADR-003 — nenhum score aprendido
# remove guarda determinística — elevada ao caso em que o autor da mudança é o próprio
# sistema: um patch que enfraquece o gate e depois passa no gate enfraquecido não foi
# verificado por nada.
#
# A lista é de **negação explícita**, e o alcance começa fechado: cada abertura é uma
# decisão registrada, não uma omissão que ninguém notou.
FORA_DE_ALCANCE: tuple[str, ...] = (
    "tools/audit.py",            # o gate estrutural do corpus
    "backend/src/vault/promotion/",  # a guarda que decide o que entra
    "backend/src/vault/quorum/engine.py",  # a regra de decisão do painel
    "tests/",                    # o que prova que o resto funciona
    "Makefile",                  # a definição dos próprios gates
    "docs/ADR-",                 # as decisões que o governam
    ".github/",                  # a automação, se existir
    "knowledge/",                # o corpus tem caminho próprio: `CorpusPatch`
)

# Só extensões cujo defeito o gate mecânico consegue acusar. Um `.env`, um `.json` de
# configuração ou um binário passariam nos três gates sem ninguém ter verificado nada.
EXTENSOES_PERMITIDAS: frozenset[str] = frozenset({".py", ".ts", ".css", ".md"})


class CodePatchRefused(ValueError):
    """O patch de código não pode ser aplicado, e a mensagem diz exatamente por quê."""


def fora_de_alcance(caminho: str) -> str | None:
    """O prefixo proibido que este caminho toca, ou `None` se ele é livre."""
    normalizado = caminho.replace("\\", "/")
    for proibido in FORA_DE_ALCANCE:
        if normalizado == proibido.rstrip("/") or normalizado.startswith(proibido):
            return proibido
    return None


class CodeOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action: Literal["create", "replace"]
    path: str = Field(min_length=1, max_length=400)
    content: str = Field(min_length=1, max_length=MAX_FILE_BYTES)

    @field_validator("path")
    @classmethod
    def _dentro_do_repositorio(cls, value: str) -> str:
        """Recusa caminho absoluto, travessia, extensão fora da lista e alvo protegido."""
        candidate = Path(value)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"caminho fora do repositório: {value!r}")
        if candidate.suffix not in EXTENSOES_PERMITIDAS:
            raise ValueError(
                f"extensão não editável por patch de código: {value!r} "
                f"(permitidas: {', '.join(sorted(EXTENSOES_PERMITIDAS))})"
            )
        proibido = fora_de_alcance(str(candidate))
        if proibido is not None:
            raise ValueError(
                f"{value!r} está fora de alcance: o sistema não altera o que o julga "
                f"(prefixo protegido: {proibido})"
            )
        return str(candidate)


class CodePatch(BaseModel):
    """A alteração de código que uma proposta pede, com a base sobre a qual foi feita."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: str = Field(min_length=6, max_length=64)
    base_commit: str = Field(min_length=7, max_length=64)
    operations: list[CodeOperation] = Field(min_length=1, max_length=MAX_FILES_POR_PATCH)

    @field_validator("operations")
    @classmethod
    def _um_alvo_por_arquivo(cls, value: list[CodeOperation]) -> list[CodeOperation]:
        caminhos = [operation.path for operation in value]
        if len(set(caminhos)) != len(caminhos):
            raise ValueError("duas operações para o mesmo arquivo")
        return value

    @property
    def targets(self) -> list[str]:
        return sorted(operation.path for operation in self.operations)

    def digest(self) -> str:
        return hashlib.sha256(
            orjson.dumps(self.to_dict(), option=orjson.OPT_SORT_KEYS)
        ).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "base_commit": self.base_commit,
            "operations": [
                {
                    "action": operation.action,
                    "path": operation.path,
                    "content": operation.content,
                }
                for operation in self.operations
            ],
        }

    def apply_to(self, repo_root: Path) -> list[Path]:
        """Escreve numa árvore. Recusa antes de tocar em qualquer arquivo.

        A verificação acontece inteira antes da primeira escrita: um patch de três
        arquivos que falha no terceiro não pode deixar os dois primeiros aplicados, ou o
        que sobra na árvore não é nem o estado antigo nem o novo.
        """
        planejadas: list[tuple[Path, str]] = []
        for operation in self.operations:
            destino = repo_root / operation.path
            proibido = fora_de_alcance(operation.path)
            if proibido is not None:
                raise CodePatchRefused(
                    f"{operation.path} está fora de alcance (prefixo {proibido})"
                )
            existe = destino.is_file()
            if operation.action == "create" and existe:
                raise CodePatchRefused(f"create sobre arquivo existente: {operation.path}")
            if operation.action == "replace" and not existe:
                raise CodePatchRefused(f"replace sobre arquivo ausente: {operation.path}")
            planejadas.append((destino, operation.content))

        escritas: list[Path] = []
        for destino, conteudo in planejadas:
            destino.parent.mkdir(parents=True, exist_ok=True)
            texto = conteudo if conteudo.endswith("\n") else conteudo + "\n"
            destino.write_text(texto, encoding="utf-8")
            escritas.append(destino)
        return escritas
