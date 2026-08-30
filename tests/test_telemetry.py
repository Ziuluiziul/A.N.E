"""O M0 lê de volta o que o sistema já gravou, sem inventar o que não foi medido."""

from __future__ import annotations

import json
from pathlib import Path

from vault.telemetry import (
    AMOSTRA_MINIMA,
    OutcomeClass,
    Stage,
    build_records,
    build_surfaces,
    classify,
    read_ledger,
    write_ledger,
)


def _fila(runtime: Path, tarefas: list[dict]) -> None:
    destino = runtime / "state" / "autonomy" / "tasks.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps({"schema_version": 1, "revision": 1, "tasks": tarefas}),
        encoding="utf-8",
    )


def _painel(runtime: Path, painel_id: str, *, votos: list[dict], decisao: dict) -> Path:
    pasta = runtime / "quorum" / painel_id
    (pasta / "votes").mkdir(parents=True, exist_ok=True)
    (pasta / "task.json").write_text(
        json.dumps(
            {
                "panel_id": painel_id,
                "task": {
                    "id": f"aut-{painel_id}",
                    "kind": "corpus_review",
                    "prompt": "reavalie",
                    "created_at": "2026-08-14T10:00:00+00:00",
                    "context": {"domain": "Física", "corpus_entity": "Física/Nota.md"},
                },
                "proposal": {
                    "id": "prop-1",
                    "proposer": {
                        "provider": "groq",
                        "endpoint_id": "modelo-a",
                        "family": "llama",
                        "role_name": "proponente",
                    },
                    "final_response": "texto",
                },
            }
        ),
        encoding="utf-8",
    )
    (pasta / "decision.json").write_text(json.dumps(decisao), encoding="utf-8")
    for indice, voto in enumerate(votos):
        (pasta / "votes" / f"{indice}.json").write_text(
            json.dumps(voto), encoding="utf-8"
        )
    return pasta


def _voto(endpoint: str, *, valido: bool, decisao: str = "approve") -> dict:
    return {
        "reviewer": {
            "provider": "groq",
            "endpoint_id": endpoint,
            "family": "qwen",
            "role_name": "verificador-factual",
        },
        "schema_valid": valido,
        "structured_vote": {"decision": decisao, "confidence": 0.9} if valido else None,
        "error": None if valido else "envelope malformado",
    }


class TestClassificacao:
    def test_reduz_mensagem_real_ao_vocabulario_fechado(self) -> None:
        assert classify("error", "ProviderRateLimited: 429") is OutcomeClass.RATE_LIMIT
        assert (
            classify("error", "proponente produziu patch inválido: ...")
            is OutcomeClass.ENVELOPE_INVALIDO
        )
        assert classify("completed", "") is OutcomeClass.OK

    def test_teto_de_prompt_nao_e_confundido_com_rate_limit(self) -> None:
        """`Request Entity Too Large` fala de tamanho e vem de 4xx: é teto, não cota."""
        assert (
            classify("error", "APIError: Request Entity Too Large")
            is OutcomeClass.PROMPT_ACIMA_DO_TETO
        )

    def test_mensagem_desconhecida_vira_outro_em_vez_de_sumir(self) -> None:
        assert classify("error", "algo que nunca vimos") is OutcomeClass.OUTRO


class TestConstrucao:
    def test_cada_tentativa_da_fila_vira_um_registro(self, tmp_path: Path) -> None:
        _fila(
            tmp_path,
            [
                {
                    "id": "aut-1",
                    "kind": "corpus_review",
                    "domain": "Física",
                    "corpus_entity": "Física/Nota.md",
                    "attempts": [
                        {
                            "started_at": "2026-08-14T10:00:00+00:00",
                            "finished_at": "2026-08-14T10:00:02+00:00",
                            "endpoints": ["google/gemini-3.6-flash"],
                            "outcome": "error",
                            "detail": "ProviderRateLimited: 429",
                        }
                    ],
                }
            ],
        )
        registros = build_records(tmp_path)
        assert len(registros) == 1
        registro = registros[0]
        assert registro.stage is Stage.ATTEMPT
        assert registro.outcome_class is OutcomeClass.RATE_LIMIT
        assert registro.key == "google/gemini-3.6-flash"
        assert registro.latency_ms == 2000
        assert registro.corpus_entity == "Física/Nota.md"

    def test_validade_do_voto_sai_de_votes_e_nao_da_decisao(self, tmp_path: Path) -> None:
        """A decisão só lista voto contado; medir validade por ela responde sempre 100%.

        Esta é a regressão que a primeira versão da superfície teve: aptidão saía 100%
        para todo endpoint porque a pergunta era circular.
        """
        _painel(
            tmp_path,
            "p1",
            votos=[
                _voto("modelo-bom", valido=True),
                _voto("modelo-ruim", valido=False),
            ],
            decisao={
                "outcome": "escalate",
                "reason": "2 avaliações válidas; mínimo é 3",
                "decided_at": "2026-08-14T10:05:00+00:00",
                # a decisão conhece só o voto contado — de propósito, como no real
                "votes": [
                    {
                        "reviewer": {
                            "provider": "groq",
                            "endpoint_id": "modelo-bom",
                            "family": "qwen",
                            "role_name": "verificador-factual",
                        },
                        "decision": "approve",
                        "confidence": 0.9,
                    }
                ],
            },
        )
        votos = [r for r in build_records(tmp_path) if r.stage is Stage.VOTE]
        assert len(votos) == 2
        validade = {registro.endpoint: registro.schema_valid for registro in votos}
        assert validade == {"modelo-bom": True, "modelo-ruim": False}

    def test_painel_sem_pasta_de_votos_ainda_entra(self, tmp_path: Path) -> None:
        pasta = _painel(
            tmp_path,
            "p2",
            votos=[],
            decisao={
                "outcome": "reject",
                "reason": "recusado",
                "decided_at": "2026-08-14T11:00:00+00:00",
                "votes": [],
            },
        )
        (pasta / "votes").rmdir()
        estagios = {registro.stage for registro in build_records(tmp_path)}
        assert Stage.DECISION in estagios
        assert Stage.PROPOSAL in estagios

    def test_decisao_de_admissao_entra_sem_virar_tentativa(self, tmp_path: Path) -> None:
        """Quem decide não gastar precisa ser auditável como quem gasta."""
        _fila(
            tmp_path,
            [
                {
                    "id": "aut-1",
                    "kind": "corpus_review",
                    "domain": "Física",
                    "attempts": [],
                    "updated_at": "2026-08-15T03:40:00+00:00",
                    "metadata": {
                        "last_backpressure": "quorum_capacity:call_budget — 5 para 9.7"
                    },
                }
            ],
        )
        registros = build_records(tmp_path)
        assert [r.stage for r in registros] == [Stage.ADMISSION]
        assert registros[0].outcome_class is OutcomeClass.ADIADO
        assert "9.7" in registros[0].detail

    def test_runtime_vazio_nao_quebra(self, tmp_path: Path) -> None:
        assert build_records(tmp_path) == []


class TestSuperficies:
    def test_taxa_fica_oculta_abaixo_da_amostra_minima(self, tmp_path: Path) -> None:
        _fila(
            tmp_path,
            [
                {
                    "id": "aut-1",
                    "kind": "corpus_review",
                    "attempts": [
                        {
                            "finished_at": "2026-08-14T10:00:00+00:00",
                            "endpoints": ["groq/raro"],
                            "outcome": "completed",
                            "detail": "",
                        }
                    ],
                }
            ],
        )
        capacidade = build_surfaces(build_records(tmp_path)).capacidade
        assert capacidade[0].tentativas < AMOSTRA_MINIMA
        assert capacidade[0].taxa_ok is None

    def test_taxa_aparece_quando_a_amostra_sustenta(self, tmp_path: Path) -> None:
        tentativas = [
            {
                "finished_at": f"2026-08-14T10:0{indice}:00+00:00",
                "endpoints": ["groq/muito-usado"],
                "outcome": "completed" if indice % 2 == 0 else "error",
                "detail": "" if indice % 2 == 0 else "ProviderRateLimited: 429",
            }
            for indice in range(AMOSTRA_MINIMA + 1)
        ]
        _fila(tmp_path, [{"id": "aut-1", "kind": "corpus_review", "attempts": tentativas}])
        capacidade = build_surfaces(build_records(tmp_path)).capacidade
        assert capacidade[0].taxa_ok is not None
        assert capacidade[0].por_classe["rate-limit"] == 3

    def test_lacunas_declaram_o_que_falta_para_calibrar(self, tmp_path: Path) -> None:
        _fila(tmp_path, [{"id": "aut-1", "kind": "corpus_review", "attempts": []}])
        nomes = {lacuna.nome for lacuna in build_surfaces(build_records(tmp_path)).lacunas}
        assert "validation_outcome" in nomes
        assert "promotion_outcome" in nomes
        assert "tokens por chamada" in nomes

    def test_aptidao_separa_proposta_de_voto(self, tmp_path: Path) -> None:
        """Sintetizar e julgar não compartilham a mesma taxa."""
        tentativas = [
            {
                "finished_at": f"2026-08-14T10:0{indice}:00+00:00",
                "endpoints": ["groq/modelo-a"],
                "outcome": "error",
                "detail": "proponente produziu patch inválido",
            }
            for indice in range(4)
        ]
        _fila(
            tmp_path,
            [
                {
                    "id": "aut-falhou",
                    "kind": "corpus_review",
                    "domain": "Física",
                    "attempts": tentativas,
                }
            ],
        )
        _painel(
            tmp_path,
            "p-ok",
            votos=[_voto("modelo-bom", valido=True)],
            decisao={
                "outcome": "promote",
                "reason": "promovido",
                "decided_at": "2026-08-14T10:05:00+00:00",
                "votes": [],
            },
        )
        superficies = build_surfaces(build_records(tmp_path))
        proposta = next(a for a in superficies.aptidao if a.stage is Stage.PROPOSAL)
        voto = next(a for a in superficies.aptidao if a.stage is Stage.VOTE)
        assert proposta.endpoint == "groq/modelo-a"
        assert proposta.role == "proponente"
        assert proposta.observacoes == 5
        assert proposta.utilizaveis == 1
        assert voto.endpoint == "groq/modelo-bom"
        assert voto.utilizaveis == 1
        assert superficies.custo.decisoes_promote == 1
        assert superficies.custo.propostas_parseaveis == 1
        decisao = next(r for r in build_records(tmp_path) if r.stage is Stage.DECISION)
        assert decisao.decision_outcome == "promote"

    def test_diario_de_promocao_preenche_os_desfechos(self, tmp_path: Path) -> None:
        """As promoções já existiam; o ledger fingia que não."""
        _painel(
            tmp_path,
            "p-promo",
            votos=[_voto("modelo-bom", valido=True)],
            decisao={
                "outcome": "promote",
                "reason": "promovido",
                "decided_at": "2026-08-17T16:43:28+00:00",
                "votes": [],
            },
        )
        diario = tmp_path / "promotion"
        diario.mkdir()
        diario.joinpath("promotions.jsonl").write_text(
            json.dumps(
                {
                    "state": "promoted",
                    "panel_id": "p-promo",
                    "commit": "7829edd",
                    "detail": "promoção aplicada e commitada",
                    "at": "2026-08-17T16:43:28+00:00",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        registros = build_records(tmp_path)
        decisao = next(r for r in registros if r.stage is Stage.DECISION)
        assert decisao.promotion_outcome == "promoted"
        assert decisao.validation_outcome == "passed"
        nomes = {lacuna.nome for lacuna in build_surfaces(registros).lacunas}
        assert "promotion_outcome" not in nomes
        assert "validation_outcome" not in nomes

    def test_recusa_de_admissao_e_validacao_estrutural(self, tmp_path: Path) -> None:
        _fila(
            tmp_path,
            [
                {
                    "id": "aut-recusado",
                    "kind": "corpus_review",
                    "attempts": [
                        {
                            "finished_at": "2026-08-17T10:00:00+00:00",
                            "endpoints": ["groq/modelo-a"],
                            "outcome": "rejected",
                            "detail": "auditoria estrutural reprovou o resultado:\nfrontmatter",
                        }
                    ],
                }
            ],
        )
        _painel(
            tmp_path,
            "p-recusa",
            votos=[],
            decisao={
                "outcome": "promote",
                "reason": "promovido",
                "decided_at": "2026-08-17T11:00:00+00:00",
                "votes": [],
            },
        )
        diario = tmp_path / "promotion"
        diario.mkdir()
        diario.joinpath("promotions.jsonl").write_text(
            json.dumps(
                {
                    "state": "rejected",
                    "panel_id": "p-recusa",
                    "detail": "auditoria estrutural reprovou o resultado:\nfrontmatter",
                    "at": "2026-08-17T11:00:01+00:00",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        registros = build_records(tmp_path)
        tentativa = next(r for r in registros if r.stage is Stage.ATTEMPT)
        decisao = next(r for r in registros if r.stage is Stage.DECISION)
        assert tentativa.validation_outcome == "structural_validation"
        assert decisao.promotion_outcome == "rejected"
        assert decisao.validation_outcome == "structural_validation"


class TestSerializacao:
    def test_toda_superficie_vira_json(self) -> None:
        """As superfícies usam `slots=True`; `vars()` levanta TypeError sobre elas.

        A primeira versão do `--json` usava `vars` e quebrava na primeira execução, sem
        que nenhum teste percorresse o ramo. Serializar é contrato da ferramenta.
        """
        import dataclasses

        superficies = build_surfaces([])
        carga = {
            "capacidade": [dataclasses.asdict(c) for c in superficies.capacidade],
            "aptidao": [dataclasses.asdict(a) for a in superficies.aptidao],
            "custo": dataclasses.asdict(superficies.custo),
            "lacunas": [dataclasses.asdict(lac) for lac in superficies.lacunas],
        }
        assert json.loads(json.dumps(carga, ensure_ascii=False))["lacunas"]


class TestLedger:
    def test_ida_e_volta_preserva_o_registro(self, tmp_path: Path) -> None:
        _fila(
            tmp_path,
            [
                {
                    "id": "aut-1",
                    "kind": "corpus_review",
                    "domain": "Física",
                    "attempts": [
                        {
                            "finished_at": "2026-08-14T10:00:00+00:00",
                            "endpoints": ["groq/modelo"],
                            "outcome": "error",
                            "detail": "ProviderRateLimited: 429",
                        }
                    ],
                }
            ],
        )
        originais = build_records(tmp_path)
        destino = write_ledger(tmp_path, originais)
        assert destino.stat().st_mode & 0o777 == 0o600
        assert read_ledger(tmp_path) == originais

    def test_linha_ilegivel_e_descartada_sem_derrubar_a_leitura(
        self, tmp_path: Path
    ) -> None:
        _fila(
            tmp_path,
            [
                {
                    "id": "aut-1",
                    "kind": "corpus_review",
                    "attempts": [
                        {
                            "finished_at": "2026-08-14T10:00:00+00:00",
                            "endpoints": ["groq/modelo"],
                            "outcome": "completed",
                            "detail": "",
                        }
                    ],
                }
            ],
        )
        write_ledger(tmp_path, build_records(tmp_path))
        caminho = tmp_path / "state" / "outcomes.jsonl"
        caminho.write_text(caminho.read_text(encoding="utf-8") + "{lixo\n", encoding="utf-8")
        assert len(read_ledger(tmp_path)) == 1

    def test_reconstruir_e_idempotente(self, tmp_path: Path) -> None:
        """Apagar o ledger não perde nada: a fonte continua sendo a origem."""
        _fila(
            tmp_path,
            [
                {
                    "id": "aut-1",
                    "kind": "corpus_review",
                    "attempts": [
                        {
                            "finished_at": "2026-08-14T10:00:00+00:00",
                            "endpoints": ["groq/modelo"],
                            "outcome": "completed",
                            "detail": "",
                        }
                    ],
                }
            ],
        )
        primeiro = build_records(tmp_path)
        write_ledger(tmp_path, primeiro)
        (tmp_path / "state" / "outcomes.jsonl").unlink()
        assert build_records(tmp_path) == primeiro
