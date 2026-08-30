"""Memória espacial: sobrevive ao reinício, tolera corrupção e não toca no corpus.

O roteiro que o ciclo pede está inteiro aqui — calcular, persistir, reconstruir o
processo, recarregar, comparar, acrescentar nota, comparar de novo, corromper,
recuperar, conferir que nenhum Markdown mudou.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from vault.layout_store import (
    SCHEMA_VERSION,
    LayoutStore,
    LayoutStoreError,
    Position,
    positions_from_payload,
)

IMPRESSAO = "a" * 64
OUTRA_IMPRESSAO = "b" * 64
ALGORITMO = "teste-1"


@pytest.fixture
def store(tmp_path: Path) -> LayoutStore:
    return LayoutStore(tmp_path / "layout")


def posicoes(**pontos: tuple[float, float, float]) -> dict[str, Position]:
    return {nome: Position(*valores) for nome, valores in pontos.items()}


# --- ida e volta -----------------------------------------------------------


def test_ausencia_nao_e_erro(store: LayoutStore) -> None:
    assert store.load(IMPRESSAO, ALGORITMO) is None


def test_grava_e_recupera(store: LayoutStore) -> None:
    gravadas = posicoes(moc=(1.5, -2.0, 3.25), nota=(0.0, 0.0, 0.0))
    store.save(IMPRESSAO, gravadas, algorithm_version=ALGORITMO)
    lidas = store.load(IMPRESSAO, ALGORITMO)
    assert lidas is not None
    assert lidas.positions == gravadas
    assert lidas.schema_version == SCHEMA_VERSION
    assert lidas.corpus_fingerprint == IMPRESSAO
    assert lidas.algorithm_version == ALGORITMO


def test_posicoes_sobrevivem_a_um_processo_novo(store: LayoutStore, tmp_path: Path) -> None:
    """Reconstrói o processo de verdade: um interpretador separado relê o arquivo."""
    store.save(
        IMPRESSAO,
        posicoes(moc=(10.0, 20.0, 1.8)),
        algorithm_version=ALGORITMO,
    )

    programa = (
        "from vault.layout_store import LayoutStore;"
        f"s = LayoutStore({str(store.directory)!r});"
        f"snap = s.load({IMPRESSAO!r}, {ALGORITMO!r});"
        "print(snap.positions['moc'].x, snap.positions['moc'].y, snap.positions['moc'].z)"
    )
    resultado = subprocess.run(  # noqa: S603 — interpretador do próprio ambiente
        [sys.executable, "-c", programa],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout.split() == ["10.0", "20.0", "1.8"]


def test_impressao_diferente_nao_reaproveita_posicoes(store: LayoutStore) -> None:
    store.save(
        IMPRESSAO,
        posicoes(moc=(1.0, 1.0, 1.0)),
        algorithm_version=ALGORITMO,
    )
    assert store.load(OUTRA_IMPRESSAO, ALGORITMO) is None


def test_algoritmo_diferente_nao_reaproveita_o_mesmo_corpus(store: LayoutStore) -> None:
    store.save(
        IMPRESSAO,
        posicoes(moc=(1.0, 1.0, 1.0)),
        algorithm_version=ALGORITMO,
    )

    assert store.load(IMPRESSAO, "teste-2") is None


def test_transicao_explicita_leva_so_entidades_que_continuaram(store: LayoutStore) -> None:
    origem = posicoes(moc=(10.0, 0.0, 1.8), fica=(12.0, 3.0, 0.0), some=(9.0, 4.0, 0.0))
    store.save(IMPRESSAO, origem, algorithm_version=ALGORITMO)

    destino = store.carry_forward(
        IMPRESSAO,
        OUTRA_IMPRESSAO,
        known_ids={"moc", "fica", "nova"},
    )

    assert destino is not None
    assert destino.corpus_fingerprint == OUTRA_IMPRESSAO
    assert destino.positions == {"moc": origem["moc"], "fica": origem["fica"]}
    preservada = store.load(IMPRESSAO, ALGORITMO)
    assert preservada is not None
    assert preservada.positions == origem


def test_transicao_sem_origem_nao_adivinha_snapshot(store: LayoutStore) -> None:
    terceira = "c" * 64
    store.save(
        terceira,
        posicoes(intrusa=(99.0, 99.0, 99.0)),
        algorithm_version=ALGORITMO,
    )

    assert store.carry_forward(IMPRESSAO, OUTRA_IMPRESSAO, known_ids={"intrusa"}) is None
    assert store.load(OUTRA_IMPRESSAO, ALGORITMO) is None


def test_transicao_nao_sobrescreve_memoria_ja_existente_no_destino(
    store: LayoutStore,
) -> None:
    store.save(
        IMPRESSAO,
        posicoes(moc=(1.0, 1.0, 1.0), fica=(2.0, 2.0, 2.0)),
        algorithm_version=ALGORITMO,
    )
    store.save(
        OUTRA_IMPRESSAO,
        posicoes(moc=(8.0, 8.0, 8.0), obsoleta=(9.0, 9.0, 9.0)),
        algorithm_version=ALGORITMO,
    )

    reconciliado = store.carry_forward(
        IMPRESSAO,
        OUTRA_IMPRESSAO,
        known_ids={"moc", "fica"},
    )

    assert reconciliado is not None
    assert reconciliado.positions == {
        "moc": Position(8.0, 8.0, 8.0),
        "fica": Position(2.0, 2.0, 2.0),
    }
    assert store.load(OUTRA_IMPRESSAO, ALGORITMO) == reconciliado


def test_transicao_poda_destino_mesmo_se_a_origem_sumiu(store: LayoutStore) -> None:
    store.save(
        OUTRA_IMPRESSAO,
        posicoes(fica=(8.0, 8.0, 8.0), obsoleta=(9.0, 9.0, 9.0)),
        algorithm_version=ALGORITMO,
    )

    reconciliado = store.carry_forward(
        IMPRESSAO,
        OUTRA_IMPRESSAO,
        known_ids={"fica"},
    )

    assert reconciliado is not None
    assert reconciliado.positions == {"fica": Position(8.0, 8.0, 8.0)}


def test_transicao_nao_mistura_algoritmos(store: LayoutStore) -> None:
    store.save(
        IMPRESSAO,
        posicoes(origem=(1.0, 1.0, 1.0)),
        algorithm_version=ALGORITMO,
    )
    store.save(
        OUTRA_IMPRESSAO,
        posicoes(destino=(2.0, 2.0, 2.0)),
        algorithm_version="teste-2",
    )

    reconciliado = store.carry_forward(
        IMPRESSAO,
        OUTRA_IMPRESSAO,
        known_ids={"origem", "destino"},
    )

    assert reconciliado is not None
    assert reconciliado.algorithm_version == "teste-2"
    assert reconciliado.positions == {"destino": Position(2.0, 2.0, 2.0)}


# --- poda e estabilidade ---------------------------------------------------


def test_entidade_removida_nao_permanece(store: LayoutStore) -> None:
    store.save(
        IMPRESSAO,
        posicoes(fica=(1.0, 1.0, 0.0), some=(2.0, 2.0, 0.0)),
        algorithm_version=ALGORITMO,
        known_ids={"fica"},
    )
    lidas = store.load(IMPRESSAO, ALGORITMO)
    assert lidas is not None
    assert set(lidas.positions) == {"fica"}


def test_nota_nova_nao_move_as_existentes(store: LayoutStore) -> None:
    antes = posicoes(moc=(10.0, 0.0, 1.8), nota=(12.0, 3.0, 0.0))
    store.save(IMPRESSAO, antes, algorithm_version=ALGORITMO)

    recuperadas = store.load(IMPRESSAO, ALGORITMO)
    assert recuperadas is not None
    depois = {**recuperadas.positions, "nota-nova": Position(15.0, 4.0, 0.0)}
    store.save(IMPRESSAO, depois, algorithm_version=ALGORITMO)

    final = store.load(IMPRESSAO, ALGORITMO)
    assert final is not None
    assert final.positions["moc"] == antes["moc"]
    assert final.positions["nota"] == antes["nota"]
    assert "nota-nova" in final.positions


# --- corrupção -------------------------------------------------------------


@pytest.mark.parametrize(
    ("nome", "conteudo"),
    [
        ("json inválido", b"{ isto nao e json"),
        (
            "truncado",
            b'{"schemaVersion": 2, "algorithmVersion": "teste-1", "positions": {"a": {"x": 1',
        ),
        ("vazio", b""),
        ("schema de outra versão", b'{"schemaVersion": 99, "positions": {}}'),
        (
            "positions do tipo errado",
            json.dumps(
                {
                    "schemaVersion": SCHEMA_VERSION,
                    "corpusFingerprint": IMPRESSAO,
                    "algorithmVersion": ALGORITMO,
                    "positions": [],
                }
            ).encode(),
        ),
    ],
)
def test_arquivo_corrompido_nao_derruba_a_aplicacao(
    store: LayoutStore, nome: str, conteudo: bytes
) -> None:
    """Perder a memória espacial é aborrecimento; não abrir seria falha."""
    store.directory.mkdir(parents=True, exist_ok=True)
    (store.directory / f"{IMPRESSAO}.json").write_bytes(conteudo)
    assert store.load(IMPRESSAO, ALGORITMO) is None, nome


def test_entrada_podre_descarta_so_a_si_mesma(store: LayoutStore) -> None:
    store.directory.mkdir(parents=True, exist_ok=True)
    (store.directory / f"{IMPRESSAO}.json").write_text(
        json.dumps(
            {
                "schemaVersion": SCHEMA_VERSION,
                "corpusFingerprint": IMPRESSAO,
                "algorithmVersion": ALGORITMO,
                "positions": {
                    "boa": {"x": 1, "y": 2, "z": 3},
                    "ruim": {"x": "dez", "y": 2, "z": 3},
                    "faltando": {"x": 1},
                },
            }
        ),
        encoding="utf-8",
    )
    lidas = store.load(IMPRESSAO, ALGORITMO)
    assert lidas is not None
    assert set(lidas.positions) == {"boa"}


def test_schema_legado_sem_algoritmo_vira_cache_miss(store: LayoutStore) -> None:
    store.directory.mkdir(parents=True, exist_ok=True)
    (store.directory / f"{IMPRESSAO}.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "corpusFingerprint": IMPRESSAO,
                "positions": {"talvez-operacional": {"x": 1, "y": 2, "z": 3}},
            }
        ),
        encoding="utf-8",
    )

    assert store.load(IMPRESSAO, ALGORITMO) is None


def test_gravacao_e_atomica_e_nao_deixa_temporario(store: LayoutStore) -> None:
    store.save(
        IMPRESSAO,
        posicoes(a=(1.0, 2.0, 3.0)),
        algorithm_version=ALGORITMO,
    )
    store.save(
        IMPRESSAO,
        posicoes(a=(4.0, 5.0, 6.0)),
        algorithm_version=ALGORITMO,
    )
    arquivos = sorted(p.name for p in store.directory.iterdir())
    assert arquivos == [f"{IMPRESSAO}.json"]


# --- fronteiras ------------------------------------------------------------


def test_impressao_com_travessia_de_diretorio_e_recusada(store: LayoutStore) -> None:
    with pytest.raises(LayoutStoreError, match="impressão digital inválida"):
        store.save(
            "../../etc/passwd",
            posicoes(a=(0.0, 0.0, 0.0)),
            algorithm_version=ALGORITMO,
        )
    assert store.load("../../etc/passwd", ALGORITMO) is None


def test_corpo_invalido_e_recusado() -> None:
    with pytest.raises(LayoutStoreError):
        positions_from_payload({"a": {"x": 1}})
    with pytest.raises(LayoutStoreError):
        positions_from_payload(["não é objeto"])
    assert positions_from_payload({"a": {"x": 1, "y": 2, "z": 3}})["a"] == Position(1, 2, 3)


def test_o_store_nunca_escreve_no_corpus(store: LayoutStore, corpus_dir: Path) -> None:
    """A garantia central: memória espacial não é conhecimento."""

    def impressao_do_corpus() -> str:
        digest = hashlib.sha256()
        for caminho in sorted(corpus_dir.rglob("*.md")):
            digest.update(caminho.read_bytes())
        return digest.hexdigest()

    antes = impressao_do_corpus()
    store.save(
        IMPRESSAO,
        posicoes(a=(1.0, 2.0, 3.0)),
        algorithm_version=ALGORITMO,
    )
    store.load(IMPRESSAO, ALGORITMO)
    store.forget(IMPRESSAO)
    assert impressao_do_corpus() == antes
    assert store.directory.is_relative_to(store.directory.parent)
    assert not store.directory.is_relative_to(corpus_dir)


def test_posicao_nao_carrega_significado_epistemico() -> None:
    """O tipo não tem campo de importância, confiança ou métrica. De propósito."""
    campos = set(Position.__slots__)
    assert campos == {"x", "y", "z", "pinned"}
