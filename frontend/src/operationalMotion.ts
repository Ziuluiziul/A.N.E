// Morfologia operacional: painéis deixam de ser fixos, e o movimento tem base
// técnica — não estética.
//
// A fórmula é a do M5 da ADR-003: displayPose = anchorPose + morphOffset, com o
// deslocamento derivado **do estado operacional**, nunca de uma função de
// aparência. Cada estado tem um significado que a posição codifica:
//
//   ativo     — há chamada aberta: o painel inclina-se na direção da placa do
//               provedor que a executa. A cena mostra o locus da execução.
//   esperando — tarefa criada sem chamada: o painel entra numa órbita lenta cuja
//               distância cresce com o tempo parado. Distância = espera.
//   decidido  — painel com veredito: converge sobre a entidade do corpus que
//               julgou, e o desfecho desloca no eixo vertical — promote sobe,
//               reject desce, escalate afasta. Direção = veredito, sem depender
//               de cor.
//   parado    — sem sinal: offset zero, o painel volta à âncora persistida.
//
// O piso duro permanece: o motor continua exigindo diversidade mínima para
// decidir, e a âncora persistida não muda — o que muda é a pose exibida.

import type { LayoutMap, Vec3 } from './layout';
import type { RuntimeEvent, RuntimeEventType, RuntimeSnapshot } from './runtime';

/** Abertura e fecho de chamada; só o par define execução acontecendo agora. */
const ABRE_CHAMADA: ReadonlySet<RuntimeEventType> = new Set(['call_started']);
const FECHA_CHAMADA: ReadonlySet<RuntimeEventType> = new Set(['call_completed']);
const FECHA_PAINEL: ReadonlySet<RuntimeEventType> = new Set(['quorum_decided']);

/** Quanto do raio reservado a morfologia pode usar. O resto é assentamento. */
export const MORPH_AMPLITUDE_FRACTION = 0.22;

/** A espera satura: esperar duas horas ou dez não muda mais a distância. */
export const ESPERA_SATURACAO_S = 2 * 3600;

/** Seis graus por minuto: órbita visível sem virar carrossel. */
export const ORBITA_RAD_POR_S = (Math.PI / 180) * 0.1;

export type EstadoOperacional = 'ativo' | 'esperando' | 'decidido' | 'parado';

export type Desfecho = 'promote' | 'reject' | 'escalate';

export interface SinalOperacional {
  estado: EstadoOperacional;
  desfecho?: Desfecho;
  /** Segundos desde o evento que sustenta o sinal. */
  idadeS: number;
  /** O provedor que executa a chamada aberta, quando há. */
  provedor?: string;
  /** A entidade do corpus que o painel julga, quando há. */
  entidade?: string;
}

const ZERO: Vec3 = { x: 0, y: 0, z: 0 };

function idadeDoEvento(evento: RuntimeEvent, agora: number): number {
  const quando = Date.parse(evento.timestamp);
  if (!Number.isFinite(quando)) return 0;
  return Math.max(0, (agora - quando) / 1000);
}

/**
 * Sinais por id de evento, derivados só da trilha. O que a trilha não afirma,
 * o sinal não afirma: sem chamada aberta não há `ativo`, sem veredito não há
 * `decidido` — e o painel volta para a âncora.
 */
export function sinaisOperacionais(
  snapshot: RuntimeSnapshot,
  agora: number,
): Map<string, SinalOperacional> {
  const sinais = new Map<string, SinalOperacional>();
  const chamadaAbertaPorTask = new Map<string, RuntimeEvent>();
  const decisaoPorPainel = new Map<string, RuntimeEvent>();

  for (const evento of snapshot.events) {
    if (evento.task && ABRE_CHAMADA.has(evento.type)) chamadaAbertaPorTask.set(evento.task, evento);
    if (evento.task && FECHA_CHAMADA.has(evento.type)) chamadaAbertaPorTask.delete(evento.task);
    if (evento.panelId && FECHA_PAINEL.has(evento.type)) decisaoPorPainel.set(evento.panelId, evento);
  }

  for (const evento of snapshot.events) {
    const aberta = evento.task ? chamadaAbertaPorTask.get(evento.task) : undefined;
    const entidade =
      evento.entity ?? (evento.task ? snapshot.entityByTask.get(evento.task) : undefined);
    const idade = idadeDoEvento(evento, agora);

    if (aberta) {
      sinais.set(evento.id, {
        estado: 'ativo',
        idadeS: idade,
        provedor: aberta.provider,
        entidade,
      });
      continue;
    }

    const decisao = evento.panelId ? decisaoPorPainel.get(evento.panelId) : undefined;
    if (decisao) {
      const desfecho: Desfecho | undefined =
        decisao.action === 'promote'
          ? 'promote'
          : decisao.action === 'reject'
            ? 'reject'
            : decisao.action === 'escalate'
              ? 'escalate'
              : undefined;
      sinais.set(evento.id, {
        // `revise` não fecha: o painel volta ao trabalho, e esperar é o estado
        // honesto — não há veredito para exibir.
        estado: desfecho === undefined ? 'esperando' : 'decidido',
        desfecho,
        idadeS: idade,
        // A entidade julgada vem do veredito do painel, que a declara; os
        // votos do mesmo painel a herdam — julgaram o mesmo objeto.
        entidade: entidade ?? decisao.entity,
      });
      continue;
    }

    const aguardando =
      evento.type === 'task_created' ||
      evento.type === 'task_assigned' ||
      evento.type === 'proposal_created' ||
      evento.type === 'quorum_started';
    sinais.set(evento.id, {
      estado: aguardando ? 'esperando' : 'parado',
      idadeS: idade,
      entidade,
    });
  }
  return sinais;
}

function escala(direcao: Vec3 | null, fator: number): Vec3 {
  if (!direcao) return { ...ZERO };
  return { x: direcao.x * fator, y: direcao.y * fator, z: direcao.z * fator };
}

/**
 * O deslocamento de um painel, em unidades de mundo, para a amplitude dada.
 *
 * Puro e determinístico: mesmos sinais, mesma pose. Não há ruído, não há
 * relaxamento "para ficar bonito" — cada termo corresponde a um fato da trilha.
 */
export function morphOffset(
  sinal: SinalOperacional,
  dirProvedor: Vec3 | null,
  dirEntidade: Vec3 | null,
  amplitude: number,
): Vec3 {
  switch (sinal.estado) {
    case 'ativo':
      return escala(dirProvedor, amplitude * 0.4);
    case 'decidido': {
      const base = escala(dirEntidade, amplitude * 0.55);
      if (sinal.desfecho === 'promote') return { ...base, y: base.y + amplitude * 0.3 };
      if (sinal.desfecho === 'reject') return { ...base, y: base.y - amplitude * 0.3 };
      if (sinal.desfecho === 'escalate') {
        const radial = dirEntidade ?? { x: 1, y: 0, z: 0 };
        return {
          x: base.x + radial.x * amplitude * 0.3,
          y: base.y,
          z: base.z + radial.z * amplitude * 0.3,
        };
      }
      return base;
    }
    case 'esperando': {
      const teto = amplitude * 0.25;
      const fracao = Math.min(1, sinal.idadeS / ESPERA_SATURACAO_S);
      const distancia = teto * fracao;
      const angulo = sinal.idadeS * ORBITA_RAD_POR_S;
      return { x: Math.cos(angulo) * distancia, y: Math.sin(angulo) * distancia * 0.4, z: 0 };
    }
    default:
      return { ...ZERO };
  }
}

/**
 * Aplica a morfologia sobre os alvos do layout: a âncora não muda, a pose
 * exibida sim. Devolve um mapa novo — `alvos` nunca é mutado.
 */
export function aplicarMorfologia(
  alvos: LayoutMap,
  sinais: ReadonlyMap<string, SinalOperacional>,
  direcaoProvedor: (provider: string, ancora: Vec3) => Vec3 | null,
  direcaoEntidade: (entityId: string, ancora: Vec3) => Vec3 | null,
  amplitude: number,
): LayoutMap {
  const resultado = new Map(alvos);
  for (const [eventId, sinal] of sinais) {
    const nodeId = `runtime:event:${eventId}`;
    const ancora = alvos.get(nodeId);
    if (!ancora) continue;
    const offset = morphOffset(
      sinal,
      sinal.provedor ? direcaoProvedor(sinal.provedor, ancora) : null,
      sinal.entidade ? direcaoEntidade(sinal.entidade, ancora) : null,
      amplitude,
    );
    if (offset.x === 0 && offset.y === 0 && offset.z === 0) continue;
    resultado.set(nodeId, {
      x: ancora.x + offset.x,
      y: ancora.y + offset.y,
      z: ancora.z + offset.z,
    });
  }
  return resultado;
}

/** Vetor unitário da âncora ao alvo, ou `null` quando o alvo não tem lugar. */
export function direcaoPara(alvo: Vec3 | undefined, ancora: Vec3): Vec3 | null {
  if (!alvo) return null;
  const dx = alvo.x - ancora.x;
  const dy = alvo.y - ancora.y;
  const dz = alvo.z - ancora.z;
  const norma = Math.hypot(dx, dy, dz);
  if (norma < 1e-6) return null;
  return { x: dx / norma, y: dy / norma, z: dz / norma };
}
