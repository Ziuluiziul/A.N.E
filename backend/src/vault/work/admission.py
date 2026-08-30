"""M2 da ADR-003: decidir se dá para fechar **antes** de gastar a primeira inferência.

A precedência de hoje é invertida. O orquestrador chama o proponente, recebe a proposta,
e só então planeja os revisores distintos — quando descobre que o painel não se monta, a
chamada do proponente já foi gasta. Foi assim que 65% dos painéis escalonaram: não porque
três revisores formados discordaram, mas porque o painel nunca chegou a existir.

Aqui a ordem se inverte:

    tarefa candidata → capacidade → reserva → proponente → revisores → decisão

**Reserva é de painel, não de endpoint.** Encontrar três endpoints e devolvê-los ao
escalonador não resolve nada: dez tarefas concorrentes leriam `capacity=1` ao mesmo tempo
e todas entrariam. A reserva desconta do mesmo horizonte que responde às outras.

**Adiamento não é tentativa.** Quem não foi admitido não chamou modelo nenhum, e marcar
isso como tentativa fracassada mancharia o histórico de um endpoint que sequer foi
consultado — o mesmo cuidado que `WorkResult` já toma com `skipped`.

**A reserva não sobrevive ao processo, e é de propósito.** Ela existe para coordenar
tarefas concorrentes dentro de uma execução; o consumo real de cota é do `QuotaLedger`,
que é persistido. Reserva persistida vazaria: um worker morto no meio de um painel
deixaria endpoints reservados para sempre, e a capacidade encolheria a cada queda.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from vault.work.capacity import LimitingFactor, QuorumCapacity

# Quanto uma tarefa adiada espera antes de voltar a perguntar. Curto o bastante para a
# fila reagir quando a janela abre, longo o bastante para não transformar espera em
# giro ocupado — o worker roda com `--interval 2`.
ESPERA_PADRAO_S = 90


@dataclass(frozen=True, slots=True)
class Admission:
    """A resposta do controlador: entra, ou espera com motivo e hora."""

    admitted: bool
    reason: str
    limiting_factor: LimitingFactor
    next_eligible_at: str | None = None
    reserved: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "admitted": self.admitted,
            "reason": self.reason,
            "limiting_factor": self.limiting_factor.value,
            "next_eligible_at": self.next_eligible_at,
            "reserved": list(self.reserved),
        }


def _futuro(segundos: int) -> str:
    return (datetime.now(UTC) + timedelta(seconds=segundos)).isoformat(timespec="seconds")


@dataclass
class AdmissionController:
    """Guarda quantos painéis já foram prometidos e a quem.

    O estado é um mapa de tarefa para os endpoints que ela segura. Ele é pequeno de
    propósito: o controlador decide **se** o trabalho nasce, e quem escolhe o endpoint
    concreto de cada papel continua sendo o orquestrador, que é quem conhece o papel.
    """

    espera_s: int = ESPERA_PADRAO_S
    _reservas: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def reserved_keys(self) -> set[str]:
        """Todos os endpoints prometidos e ainda não liberados."""
        return {chave for reserva in self._reservas.values() for chave in reserva}

    @property
    def open_reservations(self) -> int:
        return len(self._reservas)

    def admit(
        self,
        task_id: str,
        capacity: QuorumCapacity,
        *,
        holds: Iterable[str] = (),
    ) -> Admission:
        """Decide sobre uma tarefa, descontando o que já foi prometido.

        `capacity` precisa ter sido estimada **com** `reserved=self.reserved_keys`, ou o
        desconto acontece duas vezes. Reservar de novo a mesma tarefa é idempotente: uma
        retomada não pode consumir capacidade que ela já segurava.
        """
        if task_id in self._reservas:
            return Admission(
                admitted=True,
                reason="reserva já existente para esta tarefa",
                limiting_factor=LimitingFactor.NONE,
                reserved=self._reservas[task_id],
            )
        if capacity.complete_panels < 1:
            return Admission(
                admitted=False,
                reason=f"quorum_capacity:{capacity.limiting_factor.value}"
                + (f" — {capacity.detail}" if capacity.detail else ""),
                limiting_factor=capacity.limiting_factor,
                next_eligible_at=_futuro(self.espera_s),
            )
        reserva = tuple(dict.fromkeys(holds))
        self._reservas[task_id] = reserva
        return Admission(
            admitted=True,
            reason=f"{capacity.complete_panels} painel(is) completo(s) na capacidade atual",
            limiting_factor=LimitingFactor.NONE,
            reserved=reserva,
        )

    def release(self, task_id: str) -> bool:
        """Devolve a capacidade de uma tarefa que terminou — por sucesso ou por falha.

        Liberar o que não existe não é erro: o caminho de falha do worker chama isto sem
        saber se chegou a admitir, e um erro aqui esconderia o erro de lá.
        """
        return self._reservas.pop(task_id, None) is not None

    def clear(self) -> None:
        """Esquece tudo. Usado na retomada, quando nenhuma promessa antiga vale."""
        self._reservas.clear()
