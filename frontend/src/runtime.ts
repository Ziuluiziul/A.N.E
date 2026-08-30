// Contrato estrito da camada operacional viva.
//
// O endpoint envia também `before`, `after`, `metadata` e uma projeção auxiliar.
// O Atlas não precisa desses mapas livres: reconstrói a visualização apenas com os
// campos escalares abaixo e descarta o restante na fronteira. Assim a camada viva
// não alarga a lista branca do corpus nem leva texto de modelo para a GPU/DOM.

import { openBackendEvents, type BackendConnectionStatus } from './transport';

export const RUNTIME_EVENT_TYPES = [
  'task_created',
  'task_assigned',
  'call_started',
  'call_completed',
  'temporary_created',
  'temporary_discarded',
  'evidence_recorded',
  'proposal_created',
  'quorum_started',
  'vote_requested',
  'vote_received',
  'quorum_decided',
  'promotion_started',
  'promotion_completed',
  'commit_created',
  'corpus_changed',
] as const;

export type RuntimeEventType = (typeof RUNTIME_EVENT_TYPES)[number];

const EVENT_LABELS: Record<RuntimeEventType, string> = {
  task_created: 'Tarefa criada',
  task_assigned: 'Tarefa atribuída',
  call_started: 'Chamada iniciada',
  call_completed: 'Chamada concluída',
  temporary_created: 'Temporário criado',
  temporary_discarded: 'Temporário descartado',
  evidence_recorded: 'Evidência registrada',
  proposal_created: 'Proposta criada',
  quorum_started: 'Quórum iniciado',
  vote_requested: 'Voto solicitado',
  vote_received: 'Voto recebido',
  quorum_decided: 'Quórum decidido',
  promotion_started: 'Promoção iniciada',
  promotion_completed: 'Promoção concluída',
  commit_created: 'Commit criado',
  corpus_changed: 'Corpus alterado',
};

export function runtimeEventLabel(type: RuntimeEventType): string {
  return EVENT_LABELS[type];
}

export interface RuntimeEvent {
  id: string;
  revision: number;
  timestamp: string;
  type: RuntimeEventType;
  actor?: string;
  provider?: string;
  endpoint?: string;
  task?: string;
  entity?: string;
  /** A frase de acompanhamento do evento, em linguagem natural. */
  narration?: string;
  panelId?: string;
  role?: string;
  family?: string;
  decision?: 'approve' | 'reject' | 'revise' | 'abstain';
  action?: 'promote' | 'revise' | 'reject' | 'escalate';
  confidence?: number;
  schemaValid?: boolean;
  /** Prazo total que o backend impõe à chamada externa. */
  deadlineSeconds?: number;
  validVotes?: number;
  providerCount?: number;
  familyCount?: number;
  tally?: Partial<Record<'approve' | 'reject' | 'revise' | 'abstain', number>>;
}

export interface RuntimeSnapshot {
  runtimeRevision: number;
  events: RuntimeEvent[];
  /**
   * De que entidade do corpus cada tarefa trata, acumulado da trilha **inteira**.
   *
   * A cena guarda os últimos 160 eventos, e só o `task_created` costuma declarar a
   * entidade — nos 160 mais recentes da trilha real, **nenhum** evento a declarava. A
   * camada viva ficava sem nenhuma linha para o corpus, e o vínculo existia: os eventos
   * nomeiam a tarefa, e a tarefa nomeia a entidade, algumas centenas de revisões atrás.
   *
   * O mapa é montado antes do corte e sobrevive a ele. É memória do que a trilha já
   * disse, não dedução: se nenhum evento ligou aquela tarefa a uma entidade, ela não
   * aparece aqui.
   */
  entityByTask: ReadonlyMap<string, string>;
}

const BACKEND_RUNTIME_EVENTS = '/runtime/events';
export const DEFAULT_RUNTIME_INACTIVITY_TIMEOUT_MS = 45_000;
const EVENT_ID = /^runtime-([0-9]{20})$/;
const FORBIDDEN_TEXT =
  /<\s*\/?\s*think\b|raw_?response|final_?response|scratchpad|chain_?of_?thought|reasoning|prompt/i;
const MAX_VISIBLE_EVENTS = 160;

function record(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function optionalText(value: unknown, maxLength: number): string | undefined | null {
  if (value === undefined || value === null) return undefined;
  if (
    typeof value !== 'string' ||
    value.length === 0 ||
    value.length > maxLength ||
    FORBIDDEN_TEXT.test(value)
  ) {
    return null;
  }
  return value;
}

function optionalInteger(value: unknown): number | undefined | null {
  if (value === undefined || value === null) return undefined;
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : null;
}

function optionalDeadlineSeconds(value: unknown): number | undefined | null {
  const seconds = optionalInteger(value);
  if (typeof seconds !== 'number') return seconds;
  return seconds > 0 && seconds <= 600 ? seconds : null;
}

function optionalConfidence(value: unknown): number | undefined | null {
  if (value === undefined || value === null) return undefined;
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1
    ? value
    : null;
}

function optionalBoolean(value: unknown): boolean | undefined | null {
  if (value === undefined || value === null) return undefined;
  return typeof value === 'boolean' ? value : null;
}

const DECISIONS = ['approve', 'reject', 'revise', 'abstain'] as const;
const ACTIONS = ['promote', 'revise', 'reject', 'escalate'] as const;

function optionalEnum<T extends string>(
  value: unknown,
  allowed: readonly T[],
): T | undefined | null {
  if (value === undefined || value === null) return undefined;
  return typeof value === 'string' && allowed.includes(value as T) ? (value as T) : null;
}

function optionalTally(value: unknown): RuntimeEvent['tally'] | undefined | null {
  if (value === undefined || value === null) return undefined;
  const source = record(value);
  if (!source) return null;
  const tally: NonNullable<RuntimeEvent['tally']> = {};
  for (const decision of DECISIONS) {
    const count = source[decision];
    if (count === undefined) continue;
    if (typeof count !== 'number' || !Number.isSafeInteger(count) || count < 0) return null;
    tally[decision] = count;
  }
  return tally;
}

/** Copia só a lista branca escalar e verifica que ID, revisão e tipo concordam. */
export function parseRuntimeEvent(value: unknown): RuntimeEvent | null {
  const payload = record(value);
  if (!payload) return null;
  if (
    typeof payload.revision !== 'number' ||
    !Number.isSafeInteger(payload.revision) ||
    payload.revision < 1 ||
    typeof payload.id !== 'string' ||
    typeof payload.timestamp !== 'string' ||
    payload.timestamp.length < 20 ||
    payload.timestamp.length > 64 ||
    !Number.isFinite(Date.parse(payload.timestamp)) ||
    !RUNTIME_EVENT_TYPES.includes(payload.type as RuntimeEventType)
  ) {
    return null;
  }
  const match = EVENT_ID.exec(payload.id);
  if (!match || Number(match[1]) !== payload.revision) return null;

  const optional = {
    actor: optionalText(payload.actor, 240),
    provider: optionalText(payload.provider, 80),
    endpoint: optionalText(payload.endpoint, 300),
    task: optionalText(payload.task, 160),
    entity: optionalText(payload.entity, 300),
  };
  const metadata = record(payload.metadata) ?? {};
  const structured = {
    panelId: optionalText(metadata.panel_id, 128),
    role: optionalText(metadata.role, 80),
    family: optionalText(metadata.family, 120),
    decision: optionalEnum(metadata.decision, DECISIONS),
    action: optionalEnum(metadata.action, ACTIONS),
    confidence: optionalConfidence(metadata.confidence),
    schemaValid: optionalBoolean(metadata.schema_valid),
    deadlineSeconds: optionalDeadlineSeconds(metadata.deadline_seconds),
    validVotes: optionalInteger(metadata.valid_votes),
    providerCount: optionalInteger(metadata.provider_count),
    familyCount: optionalInteger(metadata.family_count),
    tally: optionalTally(metadata.tally),
    /**
     * A frase de acompanhamento do evento.
     *
     * É o que faz o painel de um worker em execução ter o que dizer antes do artefato
     * final: o que ele está consultando, quanto demorou, como votou e por quê. Passa
     * pelo mesmo tratamento dos outros textos — limite de tamanho e recusa do que não
     * casa —, e o backend já recusou bloco de raciocínio e forma de segredo antes de
     * emitir.
     */
    narration: optionalText(metadata.narration, 240),
  };
  if (
    optional.actor === null ||
    optional.provider === null ||
    optional.endpoint === null ||
    optional.task === null ||
    optional.entity === null ||
    Object.values(structured).some((value) => value === null)
  ) {
    return null;
  }

  return {
    id: payload.id,
    revision: payload.revision,
    timestamp: payload.timestamp,
    type: payload.type as RuntimeEventType,
    ...(optional.actor === undefined ? {} : { actor: optional.actor }),
    ...(optional.provider === undefined ? {} : { provider: optional.provider }),
    ...(optional.endpoint === undefined ? {} : { endpoint: optional.endpoint }),
    ...(optional.task === undefined ? {} : { task: optional.task }),
    ...(optional.entity === undefined ? {} : { entity: optional.entity }),
    ...(typeof structured.narration === 'string' ? { narration: structured.narration } : {}),
    ...(typeof structured.panelId === 'string' ? { panelId: structured.panelId } : {}),
    ...(typeof structured.role === 'string' ? { role: structured.role } : {}),
    ...(typeof structured.family === 'string' ? { family: structured.family } : {}),
    ...(typeof structured.decision === 'string' ? { decision: structured.decision } : {}),
    ...(typeof structured.action === 'string' ? { action: structured.action } : {}),
    ...(typeof structured.confidence === 'number'
      ? { confidence: structured.confidence }
      : {}),
    ...(typeof structured.schemaValid === 'boolean'
      ? { schemaValid: structured.schemaValid }
      : {}),
    ...(typeof structured.deadlineSeconds === 'number'
      ? { deadlineSeconds: structured.deadlineSeconds }
      : {}),
    ...(typeof structured.validVotes === 'number'
      ? { validVotes: structured.validVotes }
      : {}),
    ...(typeof structured.providerCount === 'number'
      ? { providerCount: structured.providerCount }
      : {}),
    ...(typeof structured.familyCount === 'number'
      ? { familyCount: structured.familyCount }
      : {}),
    ...(structured.tally && typeof structured.tally === 'object'
      ? { tally: structured.tally }
      : {}),
  };
}

/** Snapshot inválido degrada para ausência; eventos individuais inválidos são omitidos. */
export function parseRuntimeSnapshot(value: unknown): RuntimeSnapshot | null {
  const payload = record(value);
  if (
    !payload ||
    typeof payload.runtimeRevision !== 'number' ||
    !Number.isSafeInteger(payload.runtimeRevision) ||
    payload.runtimeRevision < 0 ||
    !Array.isArray(payload.events)
  ) {
    return null;
  }
  const byRevision = new Map<number, RuntimeEvent>();
  for (const candidate of payload.events) {
    const event = parseRuntimeEvent(candidate);
    if (event && event.revision <= payload.runtimeRevision) byRevision.set(event.revision, event);
  }
  const ordenados = [...byRevision.values()].sort((a, b) => a.revision - b.revision);
  // O mapa é montado **antes** do corte: é justamente o que o corte descarta.
  const entityByTask = new Map<string, string>();
  for (const event of ordenados) {
    if (event.task && event.entity && !entityByTask.has(event.task)) {
      entityByTask.set(event.task, event.entity);
    }
  }
  const events = ordenados.slice(-MAX_VISIBLE_EVENTS);
  return { runtimeRevision: payload.runtimeRevision, events, entityByTask };
}

/** Acrescenta replay/live de modo monotônico e mantém a camada visual limitada. */
export function advanceRuntime(
  snapshot: RuntimeSnapshot,
  event: RuntimeEvent,
): RuntimeSnapshot {
  if (event.revision <= snapshot.runtimeRevision) return snapshot;
  const entityByTask = new Map(snapshot.entityByTask);
  if (event.task && event.entity && !entityByTask.has(event.task)) {
    entityByTask.set(event.task, event.entity);
  }
  return {
    runtimeRevision: event.revision,
    events: [...snapshot.events, event].slice(-MAX_VISIBLE_EVENTS),
    entityByTask,
  };
}

function payloadOf(event: Event): unknown {
  if (!(event instanceof MessageEvent) || typeof event.data !== 'string') return null;
  try {
    return JSON.parse(event.data) as unknown;
  } catch {
    return null;
  }
}

/** Sinal de vida não avança a trilha; apenas declara o cursor que continua vigente. */
export function parseRuntimeHeartbeat(value: unknown): number | null {
  const payload = record(value);
  if (
    !payload ||
    typeof payload.runtimeRevision !== 'number' ||
    !Number.isSafeInteger(payload.runtimeRevision) ||
    payload.runtimeRevision < 0
  ) {
    return null;
  }
  return payload.runtimeRevision;
}

/**
 * Assina o relógio operacional independente do watcher do corpus.
 *
 * Cada conexão começa com um snapshot integral do backend; por isso a reconexão
 * explícita também recupera quando o proxy respondeu 502 antes de o backend subir.
 * Erros de transporte são reportados sem destruir a última camada válida.
 */
export function watchRuntime(
  onSnapshot: (snapshot: RuntimeSnapshot) => void,
  onEvent: (event: RuntimeEvent) => void,
  onError: (detail: string) => void,
  options: {
    signal?: AbortSignal;
    onConnectionStatus?: (status: BackendConnectionStatus) => void;
    /** Prazo sem snapshot, evento ou heartbeat válido. Configurável para teste. */
    inactivityTimeoutMs?: number;
  } = {},
): () => void {
  if (typeof EventSource === 'undefined') return () => undefined;

  const inactivityTimeoutMs =
    options.inactivityTimeoutMs ?? DEFAULT_RUNTIME_INACTIVITY_TIMEOUT_MS;
  if (!Number.isFinite(inactivityTimeoutMs) || inactivityTimeoutMs <= 0) {
    throw new TypeError('inactivityTimeoutMs precisa ser positivo e finito');
  }

  let closed = false;
  let transportOnline = false;
  let inactivityTimedOut = false;
  let lastRuntimeRevision: number | null = null;
  let inactivityTimer: ReturnType<typeof setTimeout> | undefined;
  const clearInactivityTimer = (): void => {
    if (inactivityTimer !== undefined) globalThis.clearTimeout(inactivityTimer);
    inactivityTimer = undefined;
  };
  const armInactivityTimer = (): void => {
    clearInactivityTimer();
    if (closed || !transportOnline) return;
    inactivityTimer = globalThis.setTimeout(() => {
      inactivityTimer = undefined;
      if (closed || !transportOnline) return;
      inactivityTimedOut = true;
      options.onConnectionStatus?.('timeout');
    }, inactivityTimeoutMs);
  };
  const validSignal = (): void => {
    if (closed) return;
    if (inactivityTimedOut) {
      inactivityTimedOut = false;
      options.onConnectionStatus?.('online');
    }
    armInactivityTimer();
  };
  const transportStatus = (status: BackendConnectionStatus): void => {
    transportOnline = status === 'online';
    if (!transportOnline) {
      inactivityTimedOut = false;
      clearInactivityTimer();
    } else {
      armInactivityTimer();
    }
    options.onConnectionStatus?.(status);
  };

  const events = openBackendEvents(BACKEND_RUNTIME_EVENTS, {
    signal: options.signal,
    onStatus: transportStatus,
  });
  const source = events.source;
  source.addEventListener('runtime_snapshot', (event) => {
    const snapshot = parseRuntimeSnapshot(payloadOf(event));
    if (snapshot) {
      lastRuntimeRevision = snapshot.runtimeRevision;
      validSignal();
      onSnapshot(snapshot);
    }
    else onError('snapshot operacional inválido; camada viva preservada.');
  });
  for (const type of RUNTIME_EVENT_TYPES) {
    source.addEventListener(type, (event) => {
      const runtimeEvent = parseRuntimeEvent(payloadOf(event));
      if (runtimeEvent) {
        lastRuntimeRevision = Math.max(lastRuntimeRevision ?? 0, runtimeEvent.revision);
        validSignal();
        onEvent(runtimeEvent);
      }
      else onError(`evento operacional ${type} inválido; ignorado.`);
    });
  }
  source.addEventListener('runtime_heartbeat', (event) => {
    const revision = parseRuntimeHeartbeat(payloadOf(event));
    if (revision !== null && revision === lastRuntimeRevision) validSignal();
    else onError('heartbeat operacional inválido ou fora do cursor; ignorado.');
  });
  source.addEventListener('error', () => {
    onError('fluxo operacional interrompido; aguardando reconexão.');
  });
  const close = (): void => {
    if (closed) return;
    closed = true;
    clearInactivityTimer();
    options.signal?.removeEventListener('abort', close);
    events.close();
  };
  options.signal?.addEventListener('abort', close, { once: true });
  if (options.signal?.aborted) close();
  return close;
}
