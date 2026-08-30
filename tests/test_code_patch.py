"""O patch que altera o próprio código — ADR-006.

A invariante central destes testes é uma só: o sistema não altera aquilo que o julga.
Ela não é verificável olhando a cena nem lendo o diff — é o tipo de coisa que só um teste
prende, porque um patch que enfraquece o gate e depois passa no gate enfraquecido não
falha em lugar nenhum.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from vault.promotion import CodePatch, CodePatchRefused, fora_de_alcance


def patch(*operations: dict[str, str]) -> dict[str, object]:
    return {
        "proposal_id": "proposta-1",
        "base_commit": "a" * 40,
        "operations": list(operations),
    }


def operacao(path: str, *, action: str = "replace", content: str = "x = 1\n") -> dict[str, str]:
    return {"action": action, "path": path, "content": content}


class TestForaDeAlcance:
    """A lista é de negação explícita: o alcance começa fechado."""

    @pytest.mark.parametrize(
        "caminho",
        [
            "tools/audit.py",
            "backend/src/vault/promotion/patch.py",
            "backend/src/vault/promotion/code_patch.py",
            "backend/src/vault/quorum/engine.py",
            "tests/test_code_patch.py",
            "Makefile",
            "docs/ADR-006-o-sistema-edita-o-proprio-codigo.md",
            "knowledge/Física/Nota.md",
        ],
    )
    def test_o_que_julga_o_sistema_nao_e_editavel_por_ele(self, caminho: str) -> None:
        assert fora_de_alcance(caminho) is not None
        with pytest.raises(ValidationError):
            CodePatch.model_validate(patch(operacao(caminho)))

    def test_o_proprio_promotor_esta_protegido(self) -> None:
        # É o caso mais importante da lista: quem aplica o patch não pode ser o alvo dele.
        assert fora_de_alcance("backend/src/vault/promotion/promoter.py") is not None

    @pytest.mark.parametrize(
        "caminho",
        [
            "backend/src/vault/work/capacity.py",
            "frontend/src/atlas.ts",
            "frontend/src/style.css",
            "tools/atlas.sh.py",
        ],
    )
    def test_o_resto_do_codigo_e_editavel(self, caminho: str) -> None:
        assert fora_de_alcance(caminho) is None


class TestFormaDoAlvo:
    def test_caminho_absoluto_e_travessia_sao_recusados(self) -> None:
        for ruim in ["/etc/passwd", "../fora.py", "backend/../../fora.py"]:
            with pytest.raises(ValidationError):
                CodePatch.model_validate(patch(operacao(ruim)))

    def test_extensao_fora_da_lista_e_recusada(self) -> None:
        """Um `.env` ou um `.json` passariam nos três gates sem ninguém verificar nada."""
        for ruim in ["config.json", "deploy.sh", ".env", "dados.bin"]:
            with pytest.raises(ValidationError):
                CodePatch.model_validate(patch(operacao(ruim)))

    def test_dois_alvos_no_mesmo_arquivo_sao_recusados(self) -> None:
        with pytest.raises(ValidationError):
            CodePatch.model_validate(
                patch(operacao("frontend/src/a.ts"), operacao("frontend/src/a.ts"))
            )

    def test_patch_grande_demais_e_recusado(self) -> None:
        """Trinta arquivos não é uma alteração, é uma reescrita, e ninguém a revisa."""
        muitas = [operacao(f"frontend/src/m{i}.ts") for i in range(12)]
        with pytest.raises(ValidationError):
            CodePatch.model_validate(patch(*muitas))


class TestAplicacao:
    def _arvore(self, tmp_path: Path) -> Path:
        (tmp_path / "frontend" / "src").mkdir(parents=True)
        (tmp_path / "frontend" / "src" / "existe.ts").write_text("antigo\n", encoding="utf-8")
        return tmp_path

    def test_replace_escreve_e_create_cria(self, tmp_path: Path) -> None:
        raiz = self._arvore(tmp_path)
        alterado = CodePatch.model_validate(
            patch(
                operacao("frontend/src/existe.ts", content="novo"),
                operacao("frontend/src/novo.ts", action="create", content="nascido"),
            )
        ).apply_to(raiz)
        assert len(alterado) == 2
        assert (raiz / "frontend/src/existe.ts").read_text(encoding="utf-8") == "novo\n"
        assert (raiz / "frontend/src/novo.ts").read_text(encoding="utf-8") == "nascido\n"

    def test_replace_ausente_e_create_existente_recusam(self, tmp_path: Path) -> None:
        raiz = self._arvore(tmp_path)
        with pytest.raises(CodePatchRefused):
            CodePatch.model_validate(patch(operacao("frontend/src/ausente.ts"))).apply_to(raiz)
        with pytest.raises(CodePatchRefused):
            CodePatch.model_validate(
                patch(operacao("frontend/src/existe.ts", action="create"))
            ).apply_to(raiz)

    def test_recusa_antes_de_tocar_em_qualquer_arquivo(self, tmp_path: Path) -> None:
        """Um patch que falha no segundo alvo não pode deixar o primeiro aplicado."""
        raiz = self._arvore(tmp_path)
        com_falha = CodePatch.model_validate(
            patch(
                operacao("frontend/src/existe.ts", content="mudado"),
                operacao("frontend/src/ausente.ts", content="nunca"),
            )
        )
        with pytest.raises(CodePatchRefused):
            com_falha.apply_to(raiz)
        assert (raiz / "frontend/src/existe.ts").read_text(encoding="utf-8") == "antigo\n"
        assert not (raiz / "frontend/src/ausente.ts").exists()

    def test_o_digest_muda_com_o_conteudo(self, tmp_path: Path) -> None:
        um = CodePatch.model_validate(patch(operacao("frontend/src/a.ts", content="um")))
        outro = CodePatch.model_validate(patch(operacao("frontend/src/a.ts", content="outro")))
        assert um.digest() != outro.digest()
