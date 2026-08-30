// Resumo visível da operação em tempo real.
//
// A conexão SSE estar viva não significa que exista trabalho. Este módulo mantém as
// duas afirmações separadas: lê chamadas abertas da trilha para dizer "trabalhando" e
// usa o snapshot de controle apenas para fila/automação. O resultado é texto pronto
// para uma superfície pequena e sempre visível, sem inventar progresso quando o worker
// está apenas acordado e sem orçamento.

import {
  OPEN_COGNITIVE_WORK_EVIDENCE_MS,
  observableCognitiveWork,
  openCognitiveWork,
  type OpenCognitiveWork,
} from './cognitiveState';
import { runtimeEventLabel, type RuntimeEvent, type RuntimeSnapshot } from './runtime';

export const RECENT_ACTIVITY_MS = 10_000;
/**
 * Fallback dos eventos antigos. Chamadas novas carregam seu próprio prazo imposto pelo
 * backend; depois dele e da margem de entrega, abertura sem fechamento vira anomalia.
 */
export const OPEN_ACTIVITY_EVIDENCE_MS = OPEN_COGNITIVE_WORK_EVIDENCE_MS;

export interface OperationActivity {
  auto: boolean;
  queued: number | null;
  running: number | null;
  budget: string | null;
  lastCycle?: string | null;
  nextRun?: string | null;
  failures?: readonly string[];
}

export type LiveActivityPhase =
  | 'empty'
  | 'idle'
  | 'recent'
  | 'active'
  | 'paused'
  | 'unavailable';

export type RuntimeActivityConnection =
  | 'connecting'
  | 'online'
  | 'reconnecting'
  | 'timeout'
  | 'static';

export type ControlActivityFreshness = 'loading' | 'fresh' | 'stale' | 'unavailable';

export interface LiveActivitySource {
  operation: OperationActivity | null;
  controlFreshness: ControlActivityFreshness;
  runtimeConnection: RuntimeActivityConnection;
  /** `EventSource.open` não basta: um snapshot válido desta conexão já chegou? */
  runtimeSnapshotReady: boolean;
  /** Último raciocínio ao vivo por `provedor/endpoint`. Não vem da trilha operacional. */
  thoughts?: ReadonlyMap<string, string>;
}

export interface LiveActivityStream {
  who: string;
  role: string | null;
  text: string;
  thinking: boolean;
  targetId: string;
}

export type LiveActivityLayout = 'single' | 'split';

export interface LiveActivityView {
  phase: LiveActivityPhase;
  headline: string;
  detail: string;
  meta: string;
  targetId: string | null;
  layout?: LiveActivityLayout;
  streams?: readonly LiveActivityStream[];
  /** Momento em que `recent` deve virar `idle`, ou `null` quando não há transição. */
  expiresAt: number | null;
}

function compact(value: string, maxLength = 150): string {
  const singleLine = value.replace(/\s+/g, ' ').trim();
  return singleLine.length <= maxLength
    ? singleLine
    : `${singleLine.slice(0, Math.max(maxLength - 1, 1))}…`;
}

function subjectOf(event: RuntimeEvent): string {
  if (event.provider && event.endpoint) return `${event.provider} · ${event.endpoint}`;
  return event.entity ?? event.task ?? event.actor ?? 'sem entidade declarada';
}

function eventTarget(event: RuntimeEvent): string {
  return `runtime:event:${event.id}`;
}

function modelTarget(provider: string, endpoint: string): string {
  return `runtime:model:${provider}/${endpoint}`;
}

function plural(value: number, singular: string, pluralForm: string): string {
  return `${value} ${value === 1 ? singular : pluralForm}`;
}

function metaOf(snapshot: RuntimeSnapshot, source: LiveActivitySource): string {
  const parts = [`revisão ${snapshot.runtimeRevision}`];
  const latest = snapshot.events.at(-1);
  if (latest) {
    const moment = new Date(latest.timestamp);
    if (Number.isFinite(moment.getTime())) {
      parts.push(
        `último ${moment.toLocaleTimeString('pt-BR', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        })}`,
      );
    }
  }
  if (
    source.controlFreshness === 'fresh' &&
    source.operation?.queued !== null &&
    source.operation?.queued !== undefined
  ) {
    parts.push(`fila ${source.operation.queued}`);
  }
  if (source.controlFreshness === 'fresh' && source.operation?.budget) {
    parts.push(source.operation.budget);
  }
  if (source.controlFreshness === 'fresh' && source.operation?.lastCycle) {
    parts.push(`ciclo ${source.operation.lastCycle}`);
  }
  if (source.controlFreshness === 'fresh' && source.operation?.nextRun) {
    parts.push(`próxima ${source.operation.nextRun}`);
  }
  const falhas = source.operation?.failures;
  if (source.controlFreshness === 'fresh' && falhas && falhas.length > 0) {
    parts.push(falhas.length === 1 ? '1 falha recente' : `${falhas.length} falhas recentes`);
  }
  if (source.controlFreshness === 'stale') {
    parts.push('controle desatualizado');
  } else if (source.controlFreshness === 'unavailable') {
    parts.push('controle indisponível');
  } else if (source.controlFreshness === 'loading') {
    parts.push('carregando operação');
  }
  return parts.join(' · ');
}

const MODEL_WORK = new Set<OpenCognitiveWork['kind']>(['call', 'vote']);
const ROLE_ORDER = [
  'proponente',
  'verificador-factual',
  'critico-epistemologico',
  'revisor-estrutural',
  'arbitro',
];
const MAX_STREAMS = 6;

function roleRank(role: string | null): number {
  if (!role) return ROLE_ORDER.length;
  const index = ROLE_ORDER.indexOf(role);
  return index === -1 ? ROLE_ORDER.length : index;
}

function streamsOf(
  works: readonly OpenCognitiveWork[],
  thoughts: ReadonlyMap<string, string> | undefined,
): LiveActivityStream[] {
  const byModel = new Map<string, OpenCognitiveWork>();
  for (const work of works) {
    if (!MODEL_WORK.has(work.kind)) continue;
    const key = `${work.provider}/${work.endpoint}`;
    const previous = byModel.get(key);
    if (!previous || work.revision > previous.revision) byModel.set(key, work);
  }
  return [...byModel.values()]
    .sort((a, b) => roleRank(a.role) - roleRank(b.role) || b.revision - a.revision)
    .slice(0, MAX_STREAMS)
    .map((work) => {
      const key = `${work.provider}/${work.endpoint}`;
      const thought = thoughts?.get(key)?.trim() ?? '';
      return {
        who: `${work.provider} · ${work.endpoint}`,
        role: work.role,
        text: compact(
          thought || work.narration || 'Aguardando a resposta do provedor.',
          140,
        ),
        thinking: thought.length > 0,
        targetId: modelTarget(work.provider, work.endpoint),
      };
    });
}

function latestDetailOf(snapshot: RuntimeSnapshot): {
  latest: RuntimeEvent | null;
  detail: string;
  targetId: string | null;
} {
  const latest = snapshot.events.at(-1) ?? null;
  const narration = latest?.narration?.trim() ?? '';
  return {
    latest,
    detail: latest
      ? narration
        ? compact(narration)
        : `${runtimeEventLabel(latest.type)} · ${compact(subjectOf(latest))}`
      : 'Nenhum evento operacional recebido ainda.',
    targetId: latest ? eventTarget(latest) : null,
  };
}

function runtimeUnavailable(
  snapshot: RuntimeSnapshot,
  source: LiveActivitySource,
  meta: string,
): LiveActivityView | null {
  const { latest, detail, targetId } = latestDetailOf(snapshot);
  if (source.runtimeConnection === 'online' && source.runtimeSnapshotReady) return null;

  const headline: Record<RuntimeActivityConnection, string> = {
    connecting: 'Conectando à trilha ao vivo',
    online: 'Aguardando o snapshot ao vivo',
    reconnecting: 'Runtime reconectando',
    timeout: 'Runtime sem resposta',
    static: 'Runtime indisponível',
  };
  return {
    phase: source.runtimeConnection === 'connecting' ? 'empty' : 'unavailable',
    headline: headline[source.runtimeConnection],
    detail: latest ? `Última revisão preservada: ${detail}` : detail,
    meta,
    targetId,
    expiresAt: null,
  };
}

/** Deriva a superfície de atividade somente do que runtime e controle declararam. */
export function describeLiveActivity(
  snapshot: RuntimeSnapshot,
  source: LiveActivitySource,
  now = Date.now(),
): LiveActivityView {
  const operation = source.controlFreshness === 'fresh' ? source.operation : null;
  const meta = metaOf(snapshot, source);
  const unavailable = runtimeUnavailable(snapshot, source, meta);
  if (unavailable) return unavailable;

  const openCalls = openCognitiveWork(snapshot).filter((work) => work.kind === 'call');
  const currentWork = observableCognitiveWork(snapshot, now);
  const streams = streamsOf(currentWork, source.thoughts);

  if (streams.length > 0) {
    const evidenceExpiresAt = Math.min(
      ...currentWork
        .filter((work) => MODEL_WORK.has(work.kind))
        .map((work) => work.evidenceExpiresAt),
    );
    const thinking = streams.some((stream) => stream.thinking);
    const split = streams.length > 1;
    const headline = split
      ? thinking
        ? plural(streams.length, 'modelo pensando', 'modelos pensando')
        : plural(streams.length, 'modelo trabalhando', 'modelos trabalhando')
      : thinking
        ? 'Pensando'
        : '1 modelo trabalhando';
    const detail = split
      ? streams
          .map((stream) =>
            stream.role
              ? `${stream.who} (${stream.role}) — ${stream.text}`
              : `${stream.who} — ${stream.text}`,
          )
          .join(' · ')
      : `${streams[0]!.who} — ${streams[0]!.text}`;
    return {
      phase: 'active',
      headline,
      detail,
      meta,
      targetId: streams[0]!.targetId,
      layout: split ? 'split' : 'single',
      streams,
      expiresAt: evidenceExpiresAt,
    };
  }

  if (openCalls.length > 0) {
    const latestOpen = [...openCalls].sort((a, b) => b.revision - a.revision)[0]!;
    return {
      phase: 'unavailable',
      headline: 'Chamada sem desfecho recente',
      detail:
        `${latestOpen.provider} · ${latestOpen.endpoint} abriu trabalho, ` +
        'mas a trilha não confirmou que ele continua em curso.',
      meta,
      targetId: modelTarget(latestOpen.provider, latestOpen.endpoint),
      expiresAt: null,
    };
  }

  const { latest, detail: latestDetail, targetId } = latestDetailOf(snapshot);

  // Uma execução persistida pode sobreviver ao processo que a iniciou. Sem um evento
  // recente, `running=1` é estado da fila, não prova de computação acontecendo agora.
  if ((operation?.running ?? 0) > 0) {
    const evidenceExpiresAt = latest
      ? Date.parse(latest.timestamp) + OPEN_ACTIVITY_EVIDENCE_MS
      : Number.NaN;
    if (!Number.isFinite(evidenceExpiresAt) || now >= evidenceExpiresAt) {
      return {
        phase: 'unavailable',
        headline: 'Execução sem sinal recente',
        detail: latest
          ? `A fila ainda declara trabalho, mas o último evento foi ${latestDetail}.`
          : 'A fila declara trabalho, mas a trilha ainda não registrou nenhum evento.',
        meta,
        targetId,
        expiresAt: null,
      };
    }
    return {
      phase: 'active',
      headline: plural(operation!.running!, 'execução em curso', 'execuções em curso'),
      detail: 'A fila confirma trabalho; aguardando o próximo evento do worker.',
      meta,
      targetId: null,
      expiresAt: evidenceExpiresAt,
    };
  }

  if (operation && !operation.auto) {
    return {
      phase: 'paused',
      headline: 'Automação pausada',
      detail: latest ? `Último evento: ${latestDetail}` : latestDetail,
      meta,
      targetId,
      expiresAt: null,
    };
  }

  if (source.controlFreshness !== 'fresh') {
    return {
      phase: 'unavailable',
      headline:
        source.controlFreshness === 'loading'
          ? 'Carregando o estado operacional'
          : source.controlFreshness === 'stale'
            ? 'Controle desatualizado'
            : 'Controle indisponível',
      detail: latest ? `Trilha ao vivo preservada: ${latestDetail}` : latestDetail,
      meta,
      targetId,
      expiresAt: null,
    };
  }

  if (latest) {
    const completedAt = Date.parse(latest.timestamp);
    const expiresAt = Number.isFinite(completedAt) ? completedAt + RECENT_ACTIVITY_MS : null;
    if (expiresAt !== null && now < expiresAt) {
      return {
        phase: 'recent',
        headline: 'Atividade registrada agora',
        detail: latestDetail,
        meta,
        targetId,
        expiresAt,
      };
    }
  }

  const queued = operation?.queued;
  return {
    phase: snapshot.events.length === 0 ? 'empty' : 'idle',
    headline:
      queued !== null && queued !== undefined && queued > 0
        ? `Em espera · ${plural(queued, 'tarefa na fila', 'tarefas na fila')}`
        : 'Em repouso',
    detail: latest ? `Último evento: ${latestDetail}` : latestDetail,
    meta,
    targetId,
    expiresAt: null,
  };
}
