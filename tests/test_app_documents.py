"""O corpo canônico de uma nota, servido sob demanda ao painel aberto.

A projeção leva `summary` — a abertura do corpo, cortada — e os claims. Um painel
expandido mostrava, portanto, frases *sobre* a nota e a primeira frase *dela*: o resto do
documento não existia no navegador, e por isso não havia o que rolar. Este endpoint é a
única porta por onde o corpo passa, e por isso é aqui que a contenção precisa valer.
"""

from __future__ import annotations

import warnings
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote

import pytest

with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message="Using `httpx` with `starlette.testclient` is deprecated.*",
    )
    from fastapi.testclient import TestClient

from vault.app import app
from vault.config import get_settings

CORPO = """
## Pergunta

Como uma experiência vira um traço durável?

- Primeiro item da lista
- Segundo item, com [[Outra Nota]] <!-- relation:prerequisite -->

```python
print("bloco de código no corpo")
```

Última linha antes do EOF.
"""


@pytest.fixture
def corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    raiz = tmp_path / "knowledge"
    # Nota em subdiretório de propósito: a identidade de uma nota tem barras, e é isso
    # que obriga a rota a receber `path` em vez de um segmento só.
    (raiz / "Cognição").mkdir(parents=True)
    (raiz / "Cognição" / "Memória.md").write_text(
        "---\ntitle: Memória\nkind: nota\nepistemic_status: supported\n---\n" + CORPO,
        encoding="utf-8",
    )
    (raiz / "Outra Nota.md").write_text(
        "---\ntitle: Outra Nota\nkind: nota\nepistemic_status: supported\n---\n\nCorpo.\n",
        encoding="utf-8",
    )
    (tmp_path / "fora-do-corpus.md").write_text("segredo\n", encoding="utf-8")
    monkeypatch.setenv("VAULT_CORPUS_DIR", str(raiz))
    monkeypatch.setenv("VAULT_RUNTIME_DIR", str(tmp_path / "runtime"))
    get_settings.cache_clear()
    yield raiz
    get_settings.cache_clear()


def test_serve_o_corpo_inteiro_pela_identidade_da_nota(corpus: Path) -> None:
    with TestClient(app) as client:
        # A identidade é o caminho relativo sem extensão — como o wikilink a escreve.
        resposta = client.get("/corpus/documents/Cognição/Memória")
        assert resposta.status_code == 200
        corpo = resposta.json()["body"]
        # Até o EOF, e com a estrutura preservada: heading, lista, wikilink e código.
        assert "## Pergunta" in corpo
        assert "- Primeiro item da lista" in corpo
        assert "[[Outra Nota]]" in corpo
        assert 'print("bloco de código no corpo")' in corpo
        assert corpo.rstrip().endswith("Última linha antes do EOF.")
        # O frontmatter não entra: ele é metadado, e o painel já diz o que dele importa.
        assert "epistemic_status" not in corpo


def test_aceita_tambem_o_caminho_com_extensao(corpus: Path) -> None:
    with TestClient(app) as client:
        pela_extensao = client.get("/corpus/documents/Cognição/Memória.md")
        pela_identidade = client.get("/corpus/documents/Cognição/Memória")
        assert pela_extensao.status_code == 200
        assert pela_extensao.json() == pela_identidade.json()


@pytest.mark.parametrize(
    "ref",
    [
        "../fora-do-corpus.md",
        "../../etc/passwd",
        "Cognição/../../fora-do-corpus.md",
        "/etc/passwd",
    ],
)
def test_recusa_referencia_que_escapa_do_corpus(corpus: Path, ref: str) -> None:
    # O escape vira 404 pelo mesmo caminho que uma nota inexistente: a resposta não
    # distingue "existe e não te mostro" de "não existe", e por isso não vaza o que há
    # fora do corpus.
    with TestClient(app) as client:
        resposta = client.get(f"/corpus/documents/{quote(ref)}")
        assert resposta.status_code == 404
        assert "fora-do-corpus" not in resposta.text
        assert "segredo" not in resposta.text


def test_recusa_symlink_que_aponta_para_fora_do_corpus(corpus: Path) -> None:
    # O caso que `..` não cobre. Um link dentro do corpus é um caminho que **normaliza**
    # para dentro dele e **resolve** para fora — e a diferença entre normalizar e resolver
    # é exatamente onde um leitor de notas vira leitor arbitrário do sistema de arquivos.
    # A contenção precisa acontecer depois de `resolve()`, e é o que este teste prende.
    #
    # O status é 409 e não 404 porque a afirmação verdadeira aqui é sobre o corpus, não
    # sobre a nota: ele contém um link que sai da raiz, e é assim que `/corpus/projection`
    # já reporta a mesma condição. O que o teste exige é o resto — nada do arquivo externo
    # sai, e nem o caminho dele.
    fora = corpus.parent / "fora-do-corpus.md"
    (corpus / "atalho.md").symlink_to(fora)
    assert (corpus / "atalho.md").is_file()  # o link está lá e aponta para um arquivo

    with TestClient(app) as client:
        resposta = client.get("/corpus/documents/atalho.md")
        assert resposta.status_code == 409
        assert "segredo" not in resposta.text
        assert str(fora) not in resposta.text
        assert "fora-do-corpus" not in resposta.text


def test_recusa_symlink_de_diretorio_que_sai_do_corpus(corpus: Path) -> None:
    # Mesma armadilha, um nível acima: o link é o diretório, e o arquivo pedido através
    # dele tem nome inocente.
    (corpus / "escapatoria").symlink_to(corpus.parent, target_is_directory=True)
    with TestClient(app) as client:
        resposta = client.get("/corpus/documents/escapatoria/fora-do-corpus.md")
        assert resposta.status_code == 404
        assert "segredo" not in resposta.text


def test_nota_inexistente_e_404(corpus: Path) -> None:
    with TestClient(app) as client:
        assert client.get("/corpus/documents/Cognição/Não Existe").status_code == 404
