"""M1 e M2: contar painel fechável, e não gastar chamada antes de saber que cabe.

Os testes deste arquivo respondem à lista de fechamento da ADR-003. Dois deles existem
por causa do A-10 da auditoria — três defeitos do ciclo passaram por suíte verde e só
apareceram ao usar a ferramenta —, e por isso o caminho de serialização e o do worker
são exercidos de verdade, não apenas construídos.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from providers.aptitude import classify
from providers.base import ModelInfo
from providers.inventory import EndpointProfile, Inventory
from providers.registry import EndpointRecord
from vault.quorum.engine import MIN_FAMILIES, MIN_PROVIDERS, MIN_VALID_VOTES
from vault.work.admission import AdmissionController
from vault.work.capacity import (
    CHAMADAS_MINIMAS_POR_PAINEL,
    CapacityHints,
    LimitingFactor,
    QuorumCapacity,
    estimate_quorum_capacity,
)
from vault.work.quotas import EndpointLimits, QuotaLedger, RunBudget


def perfil(provider: str, endpoint: str, family: str, *, status: str = "ok") -> EndpointProfile:
    model = ModelInfo(
        provider=provider,
        endpoint_id=endpoint,
        family=family,
        capabilities=["generateContent"],
        raw={},
    )
    registro = EndpointRecord(
        provider=provider, endpoint_id=endpoint, observed_status=status, probes=1
    )
    return EndpointProfile(aptitude=classify(model), model=model, record=registro)


def inventario(*perfis: EndpointProfile) -> Inventory:
    return Inventory(profiles=list(perfis))


SEM_LIMITE = EndpointLimits(source="teste")


def capacidade(
    inv: Inventory,
    *,
    ledger: QuotaLedger | None = None,
    budget: RunBudget | None = None,
    reserved: tuple[str, ...] = (),
    unfit: tuple[str, ...] = (),
    esperado: float | None = None,
    limites: dict[str, EndpointLimits] | None = None,
) -> QuorumCapacity:
    tabela = limites or {}
    return estimate_quorum_capacity(
        inv,
        ledger or QuotaLedger(),
        budget or RunBudget(max_calls=100),
        reserved=reserved,
        unfit=unfit,
        expected_calls_per_closure=esperado,
        limits_for=lambda p: tabela.get(p.key, SEM_LIMITE),
    )


# Um painel válido: MIN_VALID_VOTES revisores cobrindo MIN_PROVIDERS provedores e
# MIN_FAMILIES famílias, mais um endpoint sobrando para o proponente.
PAINEL_COMPLETO = (
    perfil("groq", "a", "llama"),
    perfil("nvidia", "b", "qwen"),
    perfil("groq", "c", "gemma"),
    perfil("ollama", "d", "minimax"),
)


class TestCapacidade:
    def test_um_provedor_so_nao_forma_painel(self) -> None:
        inv = inventario(
            perfil("groq", "a", "llama"),
            perfil("groq", "b", "qwen"),
            perfil("groq", "c", "gemma"),
            perfil("groq", "d", "minimax"),
        )
        resultado = capacidade(inv)
        assert resultado.complete_panels == 0
        assert resultado.limiting_factor is LimitingFactor.PROVIDER
        assert resultado.providers_available < MIN_PROVIDERS

    def test_familia_unica_com_dois_provedores_forma_painel(self) -> None:
        """Família não é silo: dois provedores adequados fecham o painel."""
        familias = [f"f{indice}" for indice in range(max(MIN_FAMILIES - 1, 1))]
        inv = inventario(
            *[
                perfil("groq" if indice % 2 == 0 else "nvidia", f"e{indice}", familias[0])
                for indice in range(MIN_VALID_VOTES + 1)
            ]
        )
        resultado = capacidade(inv)
        assert resultado.complete_panels == 1
        assert resultado.limiting_factor is LimitingFactor.NONE

    def test_diversidade_suficiente_mas_sem_cota_nao_forma_painel(self) -> None:
        ledger = QuotaLedger()
        for p in PAINEL_COMPLETO:
            ledger.record_call(endpoint=p.key, provider=p.provider)
        estourado = {
            p.key: EndpointLimits(requests_per_minute=1, source="teste")
            for p in PAINEL_COMPLETO
        }
        resultado = capacidade(inventario(*PAINEL_COMPLETO), ledger=ledger, limites=estourado)
        assert resultado.complete_panels == 0
        assert resultado.limiting_factor is LimitingFactor.QUOTA
        assert "cota" in resultado.detail

    def test_painel_completo_disponivel_conta_um(self) -> None:
        resultado = capacidade(inventario(*PAINEL_COMPLETO))
        assert resultado.complete_panels == 1
        assert resultado.limiting_factor is LimitingFactor.NONE
        assert resultado.reviewer_slots == len(PAINEL_COMPLETO)

    def test_endpoint_inviavel_nao_infla_capacidade(self) -> None:
        """O endpoint está verde no inventário e morto na telemetria."""
        completo = capacidade(inventario(*PAINEL_COMPLETO))
        assert completo.complete_panels == 1
        sem_um = capacidade(inventario(*PAINEL_COMPLETO), unfit=(PAINEL_COMPLETO[1].key,))
        assert sem_um.complete_panels == 0

    def test_reserva_reduz_a_capacidade_vista_pela_proxima(self) -> None:
        livre = capacidade(inventario(*PAINEL_COMPLETO))
        preso = capacidade(inventario(*PAINEL_COMPLETO), reserved=(PAINEL_COMPLETO[0].key,))
        assert livre.complete_panels == 1
        assert preso.complete_panels == 0

    def test_orcamento_de_chamadas_limita_antes_da_diversidade(self) -> None:
        muitos = inventario(
            *PAINEL_COMPLETO,
            perfil("nvidia", "e", "llama"),
            perfil("ollama", "f", "qwen"),
            perfil("groq", "g", "gemma"),
            perfil("nvidia", "h", "minimax"),
        )
        curto = capacidade(muitos, budget=RunBudget(max_calls=CHAMADAS_MINIMAS_POR_PAINEL))
        assert curto.complete_panels == 1
        assert capacidade(muitos).complete_panels == 2

    def test_custo_esperado_vem_da_medicao_e_nunca_abaixo_do_painel_minimo(self) -> None:
        medido = capacidade(inventario(*PAINEL_COMPLETO), esperado=9.6)
        assert medido.calls_expected_per_closure == pytest.approx(9.6)
        otimista = capacidade(inventario(*PAINEL_COMPLETO), esperado=1.0)
        assert otimista.calls_expected_per_closure == CHAMADAS_MINIMAS_POR_PAINEL

    def test_serializa_para_json(self) -> None:
        """A-10: o ramo de saída precisa ser exercido, não só construído."""
        carga = capacidade(inventario(*PAINEL_COMPLETO)).to_dict()
        assert json.loads(json.dumps(carga))["limiting_factor"] == "none"


class TestAdmissao:
    def test_duas_tarefas_disputando_um_painel_so_admitem_uma(self) -> None:
        controlador = AdmissionController()
        inv = inventario(*PAINEL_COMPLETO)

        primeira = controlador.admit(
            "aut-1",
            capacidade(inv, reserved=tuple(controlador.reserved_keys)),
            holds=[p.key for p in PAINEL_COMPLETO],
        )
        segunda = controlador.admit(
            "aut-2", capacidade(inv, reserved=tuple(controlador.reserved_keys))
        )

        assert primeira.admitted is True
        assert segunda.admitted is False
        assert segunda.next_eligible_at is not None
        assert segunda.reason.startswith("quorum_capacity:")

    def test_liberar_devolve_a_capacidade(self) -> None:
        controlador = AdmissionController()
        inv = inventario(*PAINEL_COMPLETO)
        controlador.admit("aut-1", capacidade(inv), holds=[p.key for p in PAINEL_COMPLETO])
        assert controlador.release("aut-1") is True
        depois = capacidade(inv, reserved=tuple(controlador.reserved_keys))
        assert controlador.admit("aut-2", depois).admitted is True

    def test_liberar_o_que_nao_existe_nao_levanta(self) -> None:
        assert AdmissionController().release("nunca-admitida") is False

    def test_readmitir_a_mesma_tarefa_e_idempotente(self) -> None:
        controlador = AdmissionController()
        inv = inventario(*PAINEL_COMPLETO)
        controlador.admit("aut-1", capacidade(inv), holds=[PAINEL_COMPLETO[0].key])
        antes = controlador.open_reservations
        de_novo = controlador.admit("aut-1", capacidade(inv, reserved=("groq/a",)))
        assert de_novo.admitted is True
        assert controlador.open_reservations == antes

    def test_reinicio_nao_herda_reserva(self) -> None:
        """A reserva coordena tarefas de uma execução; ela não pode sobreviver ao processo."""
        controlador = AdmissionController()
        controlador.admit("aut-1", capacidade(inventario(*PAINEL_COMPLETO)), holds=["groq/a"])
        assert controlador.reserved_keys
        controlador.clear()
        assert controlador.reserved_keys == set()

    def test_recusa_carrega_o_fator_limitante(self) -> None:
        sem_diversidade = capacidade(
            inventario(perfil("groq", "a", "llama"), perfil("groq", "b", "llama"))
        )
        decisao = AdmissionController().admit("aut-1", sem_diversidade)
        assert decisao.admitted is False
        assert decisao.limiting_factor is not LimitingFactor.NONE
        assert decisao.limiting_factor.value in decisao.reason


@dataclass
class _ChamadaContada:
    chamadas: int = 0


class TestIntegracaoComOWorker:
    """O executor real, com o gancho de admissão que o worker consulta."""

    def _executor(self, inv: Inventory, hints: CapacityHints | None = None):
        from vault.autonomy.worker import OrchestratedTaskExecutor

        return OrchestratedTaskExecutor(
            inventory=inv,
            adapters={},
            ledger=QuotaLedger(),
            process_budget=RunBudget(max_calls=100),
            quorum_store=None,  # type: ignore[arg-type]
            work_store=None,  # type: ignore[arg-type]
            reader=None,  # type: ignore[arg-type]
            capacity_hints=(lambda: hints) if hints else None,
        )

    def _tarefa(self, kind: str = "corpus_review"):
        from vault.autonomy.models import AutonomousTask, TaskBudget, TaskKind, TaskOrigin

        return AutonomousTask(
            id="aut-teste-0001",
            origin=TaskOrigin.WEAK_CLAIM,
            objective="reavalie",
            priority=50,
            domain="Física",
            kind=TaskKind(kind),
            required_roles=["verificador-factual"],
            budget=TaskBudget(max_calls=5),
            corpus_entity="Física/Nota.md",
            source_fingerprint="f" * 64,
        )

    def test_sem_painel_possivel_a_tarefa_e_adiada_com_causa(self) -> None:
        executor = self._executor(inventario(perfil("groq", "a", "llama")))
        motivo = executor.defer_reason(self._tarefa())
        assert motivo is not None
        assert motivo.startswith("quorum_capacity:")
        assert executor.admission.open_reservations == 0

    def test_com_painel_possivel_a_tarefa_entra_e_fica_reservada(self) -> None:
        executor = self._executor(inventario(*PAINEL_COMPLETO))
        assert executor.defer_reason(self._tarefa()) is None
        assert executor.admission.open_reservations == 1

    def test_a_segunda_tarefa_espera_a_primeira_liberar(self) -> None:
        executor = self._executor(inventario(*PAINEL_COMPLETO))
        assert executor.defer_reason(self._tarefa()) is None
        segunda = self._tarefa()
        segunda = segunda.model_copy(update={"id": "aut-outra-0001"})
        assert executor.defer_reason(segunda) is not None
        executor.admission.release("aut-teste-0001")
        assert executor.defer_reason(segunda) is None

    def test_can_start_nao_reserva(self) -> None:
        """Reservar durante a seleção prometeria capacidade a quem nem será reivindicada."""
        executor = self._executor(inventario(*PAINEL_COMPLETO))
        assert executor.can_start(self._tarefa()) is True
        assert executor.admission.open_reservations == 0

    def test_diagnostico_nao_passa_pela_capacidade_de_painel(self) -> None:
        """Uma chamada só; não há painel para caber."""
        executor = self._executor(inventario(perfil("groq", "a", "llama")))
        assert executor.defer_reason(self._tarefa("endpoint_diagnosis")) is None

    def test_orcamento_da_tarefa_nao_encolhe_com_o_contador_compartilhado(self) -> None:
        executor = self._executor(inventario(*PAINEL_COMPLETO))
        executor.ledger.run_calls = 40
        orcamento = executor._task_budget(self._tarefa())
        assert orcamento.max_calls == 100
        assert orcamento.allows(executor.ledger)
