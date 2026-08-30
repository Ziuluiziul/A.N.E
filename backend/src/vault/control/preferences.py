"""Preferência manual e estado do AUTO. Duráveis, e separados do estado resolvido.

**Por que os dois conceitos não se misturam.** O que o AUTO resolve é consequência do
catálogo, das cotas e da disponibilidade de agora; a preferência manual é o que o
mantenedor pediu. Copiar o primeiro para o segundo ao desligar o AUTO — que é a
tentação óbvia, porque deixa a interface preenchida — transformaria uma resolução
circunstancial em decisão declarada. Na próxima vez que o catálogo mudasse, o Vault
estaria seguindo uma escolha que ninguém fez.

Por isso preferência ausente é `None`, e `None` significa "não há preferência", nunca
"use o que estava aí". Com o AUTO desligado e sem preferência, o painel diz que falta
escolher — que é a verdade.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import orjson
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from vault.control.atomic import write_atomic


class WorkerPreference(BaseModel):
    """O que o mantenedor pediu para um trabalhador. Campo ausente é ausência."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = True
    provider: str | None = Field(default=None, max_length=64)
    endpoint_id: str | None = Field(default=None, max_length=200)
    reasoning: str | None = Field(default=None, max_length=64)
    # `None` é "sem preferência declarada"; zero é uma preferência legítima, e quer
    # dizer "não aloque nada para este papel".
    concurrency: int | None = Field(default=None, ge=0, le=64)


class ControlPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    # O AUTO nasce ligado: a política canônica é o padrão do projeto, e exigir
    # configuração manual antes do primeiro ciclo contradiria a direção de produto.
    auto: bool = True
    workers: dict[str, WorkerPreference] = Field(default_factory=dict)

    def for_worker(self, worker_id: str) -> WorkerPreference:
        return self.workers.get(worker_id, WorkerPreference())


class PreferenceStore:
    """Leitura tolerante, escrita atômica. Arquivo corrompido não derruba o painel."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self) -> ControlPreferences:
        try:
            raw = orjson.loads(self.path.read_bytes())
        except (OSError, orjson.JSONDecodeError):
            # Ausente e ilegível dão no mesmo: volta-se ao padrão. Derrubar o painel
            # de controle por causa de um arquivo de preferência seria trocar uma
            # inconveniência por uma indisponibilidade.
            return ControlPreferences()
        try:
            return ControlPreferences.model_validate(raw)
        except ValidationError:
            return ControlPreferences()

    def save(self, preferences: ControlPreferences) -> ControlPreferences:
        write_atomic(self.path, orjson.dumps(preferences.model_dump(mode="json")))
        return preferences

    def set_auto(self, auto: bool) -> ControlPreferences:
        atual = self.load()
        # Desligar o AUTO **não** materializa nada: os campos manuais continuam como
        # estavam, inclusive vazios.
        return self.save(atual.model_copy(update={"auto": auto}))

    def update_worker(self, worker_id: str, **changes: object) -> ControlPreferences:
        atual = self.load()
        anterior = atual.for_worker(worker_id)
        aplicaveis = {chave: valor for chave, valor in changes.items() if valor is not None}
        novo = anterior.model_copy(update=aplicaveis)
        workers = dict(atual.workers)
        workers[worker_id] = novo
        return self.save(atual.model_copy(update={"workers": workers}))
