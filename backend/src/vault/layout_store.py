"""Memória espacial do Atlas. Fora do corpus, sempre.

Um mapa só é navegável se as coisas continuarem onde estavam. O layout é
determinístico, então a cena reabre igual enquanto o corpus não muda — mas basta uma
nota nova para o território ser recalculado, e é aí que a memória de quem já sabia
onde as coisas ficavam se perde. Este módulo guarda as posições para que só o que
mudou mude.

Três limites que o código impõe:

**Nada disto é conhecimento.** Posição não mede verdade, importância nem confiança. O
arquivo vive em `runtime/state/layout/`, que não é versionado, e o store se recusa a
escrever em qualquer outro lugar.

**Corrupção não derruba a aplicação.** Arquivo truncado, JSON inválido ou schema de
outra versão devolvem `None`, e o Atlas recalcula. Perder a memória espacial é um
aborrecimento; não abrir é uma falha.

**Impressão diferente não reaproveita cegamente.** As posições são gravadas sob a
impressão digital do corpus que as gerou. Um corpus diferente é outro mapa.
"""

from __future__ import annotations

import fcntl
import os
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson

SCHEMA_VERSION = 2
POINTER_SCHEMA_VERSION = 1
OPERATIONAL_SLOTS_SCHEMA_VERSION = 1
MAX_OPERATIONAL_SLOTS = 10_000
MAX_OPERATIONAL_ORDINAL = 1_000_000
FINGERPRINT_RE = re.compile(r"\A[0-9a-f]{64}\Z")
ALGORITHM_VERSION_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


def validate_algorithm_version(algorithm_version: str) -> str:
    """Versão lógica do algoritmo, nunca parte de um caminho.

    Mesmo armazenada no JSON, ela cruza a rede e precisa de vocabulário fechado:
    limite e alfabeto evitam lixo não comparável e mensagens sem teto.

    **O que ela não faz é enumerar versões conhecidas.** A versão é decisão de quem
    calcula a geometria — o frontend —, e o store só a compara com a que gravou. A API
    chegou a fixá-la em `Literal["1"]`, e o resultado foi que subir a versão no frontend
    derrubou a memória espacial inteira em silêncio por seis commits: `GET` e `PUT`
    passaram a responder 422, e o cliente, que trata erro como "não havia nada gravado",
    não tinha como distinguir contrato incompatível de backend ausente.
    """
    if not ALGORITHM_VERSION_RE.match(algorithm_version):
        raise LayoutStoreError(
            "versão de algoritmo inválida; esperado 1 a 64 caracteres "
            "alfanuméricos, ponto, hífen ou sublinhado"
        )
    return algorithm_version

# Nome fixo, e deliberadamente fora do formato de 64 hexadecimais: assim `save` nunca
# consegue sobrescrever o ponteiro, porque `_path` recusa qualquer nome que não seja
# uma impressão digital.
POINTER_NAME = "last-fingerprint.json"


class LayoutStoreError(RuntimeError):
    """Pedido que o store se recusa a atender — nunca uma falha de leitura."""


def _write_atomic(directory: Path, path: Path, payload: bytes, *, prefix: str) -> None:
    """Escreve um JSON por substituição atômica dentro do diretório declarado."""
    directory.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=directory, prefix=prefix)
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


@dataclass(frozen=True, slots=True)
class Position:
    x: float
    y: float
    z: float
    pinned: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"x": self.x, "y": self.y, "z": self.z, "pinned": self.pinned}

    @classmethod
    def parse(cls, raw: Any) -> Position | None:
        if not isinstance(raw, dict):
            return None
        try:
            return cls(
                x=float(raw["x"]),
                y=float(raw["y"]),
                z=float(raw["z"]),
                pinned=bool(raw.get("pinned", False)),
            )
        except (KeyError, TypeError, ValueError):
            return None


@dataclass(frozen=True, slots=True)
class LayoutSnapshot:
    schema_version: int
    corpus_fingerprint: str
    algorithm_version: str
    updated_at: str
    positions: dict[str, Position]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "corpusFingerprint": self.corpus_fingerprint,
            "algorithmVersion": self.algorithm_version,
            "updatedAt": self.updated_at,
            "positions": {
                identidade: posicao.to_dict()
                for identidade, posicao in sorted(self.positions.items())
            },
        }


class LayoutStore:
    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory).resolve()

    def _path(self, fingerprint: str) -> Path:
        """Caminho do arquivo. A impressão é validada como hexadecimal de 64 dígitos.

        A validação não é cosmética: sem ela, uma impressão vinda da rede poderia
        conter `../` e fazer o store escrever fora do diretório dele.
        """
        if not FINGERPRINT_RE.match(fingerprint):
            raise LayoutStoreError(
                f"impressão digital inválida: {fingerprint[:24]!r}; "
                "esperado hexadecimal de 64 dígitos"
            )
        destino = (self.directory / f"{fingerprint}.json").resolve()
        if destino.parent != self.directory:
            raise LayoutStoreError("caminho de layout fora do diretório do store")
        return destino

    _validate_algorithm_version = staticmethod(validate_algorithm_version)

    # --- leitura -------------------------------------------------------------

    def load(
        self, fingerprint: str, algorithm_version: str | None = None
    ) -> LayoutSnapshot | None:
        """Posições gravadas, ou `None`. Nunca levanta por conteúdo do arquivo.

        A API sempre fornece ``algorithm_version``. ``None`` existe só para a
        reconciliação interna do watcher, que precisa descobrir qual versão válida
        havia na origem para carregá-la adiante sem reinterpretar a geometria.
        """
        try:
            path = self._path(fingerprint)
            expected_algorithm = (
                self._validate_algorithm_version(algorithm_version)
                if algorithm_version is not None
                else None
            )
        except LayoutStoreError:
            return None
        if not path.is_file():
            return None

        try:
            raw = orjson.loads(path.read_bytes())
        except (orjson.JSONDecodeError, OSError):
            return None
        if not isinstance(raw, dict) or raw.get("schemaVersion") != SCHEMA_VERSION:
            return None
        if raw.get("corpusFingerprint") != fingerprint:
            # Arquivo renomeado à mão ou impressão trocada: o mapa não é deste corpus.
            return None
        stored_algorithm = raw.get("algorithmVersion")
        if not isinstance(stored_algorithm, str):
            return None
        try:
            stored_algorithm = self._validate_algorithm_version(stored_algorithm)
        except LayoutStoreError:
            return None
        if expected_algorithm is not None and stored_algorithm != expected_algorithm:
            # Mesma impressão com outra geometria é cache obsoleto, não memória válida.
            return None

        cruas = raw.get("positions")
        if not isinstance(cruas, dict):
            return None
        posicoes: dict[str, Position] = {}
        for identidade, valor in cruas.items():
            posicao = Position.parse(valor)
            # Entrada podre é descartada uma a uma: perder uma posição é melhor que
            # descartar o mapa inteiro por causa dela.
            if isinstance(identidade, str) and posicao is not None:
                posicoes[identidade] = posicao

        updated_at = raw.get("updatedAt")
        return LayoutSnapshot(
            schema_version=SCHEMA_VERSION,
            corpus_fingerprint=fingerprint,
            algorithm_version=stored_algorithm,
            updated_at=updated_at if isinstance(updated_at, str) else "",
            positions=posicoes,
        )

    # --- escrita -------------------------------------------------------------

    def save(
        self,
        fingerprint: str,
        positions: dict[str, Position],
        *,
        algorithm_version: str,
        known_ids: set[str] | None = None,
    ) -> LayoutSnapshot:
        """Grava atomicamente. `known_ids` poda o que saiu do corpus.

        A poda evita que o arquivo cresça para sempre guardando notas apagadas, e
        evita que uma nota removida e recriada em outro domínio herde a posição antiga.
        """
        path = self._path(fingerprint)
        validated_algorithm = self._validate_algorithm_version(algorithm_version)
        efetivas = (
            positions
            if known_ids is None
            else {i: p for i, p in positions.items() if i in known_ids}
        )
        snapshot = LayoutSnapshot(
            schema_version=SCHEMA_VERSION,
            corpus_fingerprint=fingerprint,
            algorithm_version=validated_algorithm,
            updated_at=datetime.now(UTC).isoformat(timespec="seconds"),
            positions=efetivas,
        )

        self._write_atomic(path, orjson.dumps(snapshot.to_dict(), option=orjson.OPT_INDENT_2))
        return snapshot

    def _write_atomic(self, path: Path, payload: bytes) -> None:
        """Temporário no mesmo diretório mais `os.replace`.

        Um corte de energia deixa o arquivo antigo intacto, nunca um meio-arquivo.
        """
        _write_atomic(self.directory, path, payload, prefix=".layout-")

    def carry_forward(
        self,
        source_fingerprint: str,
        target_fingerprint: str,
        *,
        known_ids: set[str],
    ) -> LayoutSnapshot | None:
        """Leva posições conhecidas por uma transição explícita de corpus.

        A origem não é inferida pelo horário dos arquivos nem por uma busca pelo
        snapshot "mais recente": quem observou a mudança precisa fornecer os dois
        fingerprints. Isso mantém a barreira entre corpora distintos e, ao mesmo
        tempo, permite que o watcher preserve o mapa mental numa transição que ele
        acabou de validar.

        Se a origem não existe ou está corrompida, não inventa memória. O destino
        exato, se já existir, também não é apagado: ele continua sendo um snapshot
        válido para aquele fingerprint, apenas não foi derivado desta transição.
        """
        # Valida ambos mesmo quando a origem não existe; parâmetros vindos de rede
        # nunca podem virar caminhos antes de passar pelo mesmo gate de ``save``.
        self._path(source_fingerprint)
        self._path(target_fingerprint)
        source = self.load(source_fingerprint)
        target = self.load(target_fingerprint)
        if source is None and target is None:
            return None

        # Se o destino já tem posições próprias, elas vencem. A origem só completa
        # identidades ausentes **da mesma geometria**. Misturar versões manteria
        # coordenadas que o cliente acabou de declarar obsoletas.
        same_algorithm = (
            source is not None
            and target is not None
            and source.algorithm_version == target.algorithm_version
        )
        merged = (
            dict(source.positions)
            if source is not None and (target is None or same_algorithm)
            else {}
        )
        if target is not None:
            merged.update(target.positions)
        effective = {
            identity: position for identity, position in merged.items() if identity in known_ids
        }
        if target is not None and effective == target.positions:
            return target
        if target is not None:
            algorithm_version = target.algorithm_version
        else:
            assert source is not None  # ambos ausentes retornaram acima
            algorithm_version = source.algorithm_version
        return self.save(
            target_fingerprint,
            effective,
            algorithm_version=algorithm_version,
            known_ids=known_ids,
        )

    # --- última impressão conhecida ------------------------------------------

    def remember_fingerprint(self, fingerprint: str) -> None:
        """Anota qual impressão o layout gravado descreve.

        Sem este ponteiro, a origem da reconciliação só existe na memória do processo:
        depois de um reinício o watcher não teria de onde partir, e um corpus editado
        com o backend desligado nasceria sem posição alguma. Buscar o arquivo "mais
        recente" por data resolveria o sintoma e quebraria a barreira entre corpora
        distintos — a origem precisa ser declarada, não adivinhada.
        """
        if not FINGERPRINT_RE.match(fingerprint):
            raise LayoutStoreError(
                f"impressão digital inválida: {fingerprint[:24]!r}; "
                "esperado hexadecimal de 64 dígitos"
            )
        payload = {
            "schemaVersion": POINTER_SCHEMA_VERSION,
            "corpusFingerprint": fingerprint,
            "updatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        self._write_atomic(
            self.directory / POINTER_NAME, orjson.dumps(payload, option=orjson.OPT_INDENT_2)
        )

    def last_fingerprint(self) -> str | None:
        """Impressão anotada, ou `None`. Nunca levanta por conteúdo do arquivo.

        Validação estrita: schema conhecido e 64 hexadecimais. Qualquer outra coisa é
        tratada como ausência — o Atlas recalcula o layout, que é aborrecimento, em
        vez de não abrir, que seria falha.
        """
        path = self.directory / POINTER_NAME
        if not path.is_file():
            return None
        try:
            raw = orjson.loads(path.read_bytes())
        except (orjson.JSONDecodeError, OSError):
            return None
        if not isinstance(raw, dict) or raw.get("schemaVersion") != POINTER_SCHEMA_VERSION:
            return None
        fingerprint = raw.get("corpusFingerprint")
        if not isinstance(fingerprint, str) or not FINGERPRINT_RE.match(fingerprint):
            return None
        return fingerprint

    def forget(self, fingerprint: str) -> bool:
        path = self._path(fingerprint)
        if not path.is_file():
            return False
        path.unlink()
        return True


@dataclass(frozen=True, slots=True)
class OperationalSlotSnapshot:
    schema_version: int
    algorithm_version: int
    updated_at: str
    slots: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "algorithmVersion": self.algorithm_version,
            "updatedAt": self.updated_at,
            "slots": dict(sorted(self.slots.items())),
        }


class OperationalSlotStore:
    """Ordinais imutáveis das execuções, separados de coordenadas do corpus.

    O cliente propõe ordinais, mas o store preserva toda atribuição já aceita e resolve
    colisões de novos painéis sob um lock de processo. Assim duas abas não conseguem
    deslocar uma execução existente nem gravar duas no mesmo lugar.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory).resolve()

    def _path(self, algorithm_version: int) -> Path:
        if (
            isinstance(algorithm_version, bool)
            or not isinstance(algorithm_version, int)
            or algorithm_version < 1
            or algorithm_version > 10_000
        ):
            raise LayoutStoreError(
                "versão do layout operacional precisa ser inteiro entre 1 e 10000"
            )
        destination = (self.directory / f"v{algorithm_version}.json").resolve()
        if destination.parent != self.directory:
            raise LayoutStoreError("caminho de ordinais fora do diretório do store")
        return destination

    @contextmanager
    def _exclusive(self) -> Iterator[None]:
        self.directory.mkdir(parents=True, exist_ok=True)
        lock_path = self.directory / ".lock"
        with lock_path.open("a+b") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def load(self, algorithm_version: int) -> OperationalSlotSnapshot | None:
        try:
            path = self._path(algorithm_version)
        except LayoutStoreError:
            return None
        if not path.is_file():
            return None
        try:
            raw = orjson.loads(path.read_bytes())
        except (orjson.JSONDecodeError, OSError):
            return None
        if not isinstance(raw, dict):
            return None
        if raw.get("schemaVersion") != OPERATIONAL_SLOTS_SCHEMA_VERSION:
            return None
        if raw.get("algorithmVersion") != algorithm_version:
            return None
        try:
            slots = slots_from_payload(raw.get("slots"))
        except LayoutStoreError:
            return None
        if len(set(slots.values())) != len(slots):
            return None
        updated_at = raw.get("updatedAt")
        return OperationalSlotSnapshot(
            schema_version=OPERATIONAL_SLOTS_SCHEMA_VERSION,
            algorithm_version=algorithm_version,
            updated_at=updated_at if isinstance(updated_at, str) else "",
            slots=slots,
        )

    def save(self, algorithm_version: int, slots: dict[str, int]) -> OperationalSlotSnapshot:
        path = self._path(algorithm_version)
        validated = slots_from_payload(slots)
        if len(set(validated.values())) != len(validated):
            raise LayoutStoreError("dois painéis operacionais não podem ocupar o mesmo ordinal")
        snapshot = OperationalSlotSnapshot(
            schema_version=OPERATIONAL_SLOTS_SCHEMA_VERSION,
            algorithm_version=algorithm_version,
            updated_at=datetime.now(UTC).isoformat(timespec="seconds"),
            slots=validated,
        )
        _write_atomic(
            self.directory,
            path,
            orjson.dumps(snapshot.to_dict(), option=orjson.OPT_INDENT_2),
            prefix=".operational-slots-",
        )
        return snapshot

    def merge(
        self, algorithm_version: int, proposed: dict[str, int]
    ) -> OperationalSlotSnapshot:
        """Preserva o existente e atribui lugar único a cada painel novo."""
        validated = slots_from_payload(proposed)
        with self._exclusive():
            current = self.load(algorithm_version)
            effective = dict(current.slots) if current is not None else {}
            occupied = set(effective.values())
            for panel_id, requested in sorted(
                validated.items(), key=lambda item: (item[1], item[0])
            ):
                if panel_id in effective:
                    continue
                ordinal = requested
                if ordinal in occupied:
                    ordinal = 0
                    while ordinal in occupied:
                        ordinal += 1
                effective[panel_id] = ordinal
                occupied.add(ordinal)
            if current is not None and effective == current.slots:
                return current
            return self.save(algorithm_version, effective)


def positions_from_payload(raw: Any) -> dict[str, Position]:
    """Converte o corpo de um PUT em posições, ignorando o que não for posição."""
    if not isinstance(raw, dict):
        raise LayoutStoreError("corpo do layout precisa ser um objeto de posições")
    posicoes: dict[str, Position] = {}
    for identidade, valor in raw.items():
        posicao = Position.parse(valor)
        if not isinstance(identidade, str) or posicao is None:
            raise LayoutStoreError(f"posição inválida para {identidade!r}")
        posicoes[identidade] = posicao
    return posicoes


def slots_from_payload(raw: Any) -> dict[str, int]:
    """Valida o contrato painel → ordinal sem fingir coordenada tridimensional."""
    if not isinstance(raw, dict):
        raise LayoutStoreError("corpo dos ordinais precisa ser um objeto")
    if len(raw) > MAX_OPERATIONAL_SLOTS:
        raise LayoutStoreError(f"ordinais excedem o limite de {MAX_OPERATIONAL_SLOTS} painéis")
    slots: dict[str, int] = {}
    for panel_id, ordinal in raw.items():
        if not isinstance(panel_id, str) or not 1 <= len(panel_id) <= 64:
            raise LayoutStoreError("identificador de painel inválido nos ordinais")
        if (
            isinstance(ordinal, bool)
            or not isinstance(ordinal, int)
            or ordinal < 0
            or ordinal > MAX_OPERATIONAL_ORDINAL
        ):
            raise LayoutStoreError(f"ordinal inválido para {panel_id!r}")
        slots[panel_id] = ordinal
    return slots
