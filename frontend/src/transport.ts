/**
 * Fronteira única entre o Atlas e o backend.
 *
 * Em produção, todos os caminhos são same-origin e o servidor HTTP decide como
 * encaminhá-los. No desenvolvimento, o Vite aplica o proxy equivalente. Isso evita
 * embutir host/porta em quatro clientes e elimina uma configuração cross-origin que
 * o CORS do backend não prometia aceitar.
 */

export const DEFAULT_FETCH_TIMEOUT_MS = 8_000;
export const MUTATION_FETCH_TIMEOUT_MS = 15_000;
export const PROVIDER_TEST_TIMEOUT_MS = 70_000;
export const EVENT_CONNECT_TIMEOUT_MS = 8_000;
/**
 * Teto do handshake do SharedWorker. O prazo da conexão SSE continua sendo
 * `connectTimeoutMs`; esperar os mesmos 8 s só para descobrir que o script 404 é o
 * que deixava a trilha muda com o backend já respondendo.
 */
export const SHARED_WORKER_HANDSHAKE_CAP_MS = 1_500;

let sharedWorkersBlocked = false;

/** Reabre a preferência pelo worker. Só os testes precisam disto entre casos. */
export function resetBackendEventTransport(): void {
  sharedWorkersBlocked = false;
}

function localEventsRequested(): boolean {
  if (sharedWorkersBlocked) return true;
  const location = globalThis.location;
  if (location === undefined) return false;
  try {
    return new URLSearchParams(location.search).get('sse') === 'local';
  } catch {
    return false;
  }
}

export class BackendTimeoutError extends Error {
  constructor(path: string, timeoutMs: number) {
    super(`backend não respondeu a ${path} em ${timeoutMs} ms`);
    this.name = 'BackendTimeoutError';
  }
}

/** Aceita somente path same-origin absoluto; URL de outra origem nunca entra aqui. */
export function backendUrl(path: string): string {
  const hasControlCharacter = [...path].some((character) => {
    const code = character.charCodeAt(0);
    return code <= 31 || code === 127;
  });
  if (
    !path.startsWith('/') ||
    path.startsWith('//') ||
    path.includes('\\') ||
    path.includes('#') ||
    hasControlCharacter
  ) {
    throw new TypeError(`caminho de backend inválido: ${path}`);
  }
  return path;
}

function abortReason(signal: AbortSignal): unknown {
  return signal.reason ?? new DOMException('operação abortada', 'AbortError');
}

/** `fetch` com timeout e composição explícita do sinal do ciclo da aplicação. */
export async function backendFetch(
  path: string,
  init: RequestInit = {},
  timeoutMs = DEFAULT_FETCH_TIMEOUT_MS,
): Promise<Response> {
  const url = backendUrl(path);
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new TypeError('timeoutMs precisa ser positivo e finito');
  }
  const external = init.signal;
  if (external?.aborted) throw abortReason(external);

  const controller = new AbortController();
  let timedOut = false;
  const onExternalAbort = (): void => controller.abort(abortReason(external!));
  external?.addEventListener('abort', onExternalAbort, { once: true });
  const timer = globalThis.setTimeout(() => {
    timedOut = true;
    controller.abort(new BackendTimeoutError(url, timeoutMs));
  }, timeoutMs);

  try {
    const response = await fetch(url, { ...init, signal: controller.signal });
    if (timedOut) throw new BackendTimeoutError(url, timeoutMs);
    if (external?.aborted) throw abortReason(external);
    return response;
  } catch (error) {
    if (timedOut) throw new BackendTimeoutError(url, timeoutMs);
    if (external?.aborted) throw abortReason(external);
    throw error;
  } finally {
    globalThis.clearTimeout(timer);
    external?.removeEventListener('abort', onExternalAbort);
  }
}

export type BackendConnectionStatus =
  | 'connecting'
  | 'online'
  | 'reconnecting'
  | 'timeout';

export interface BackendEventsOptions {
  signal?: AbortSignal;
  connectTimeoutMs?: number;
  retryBaseMs?: number;
  onStatus?: (status: BackendConnectionStatus) => void;
}

export interface BackendEventStream {
  addEventListener(kind: string, listener: EventListener): void;
  removeEventListener(kind: string, listener: EventListener): void;
}

export interface BackendEvents {
  source: BackendEventStream;
  close(): void;
}

type SharedWorkerInbound =
  | {
      type: 'attach';
      path: string;
      connectTimeoutMs: number;
      retryBaseMs: number;
    }
  | { type: 'listen'; kind: string }
  | { type: 'detach' };

type SharedWorkerOutbound =
  | { type: 'ready' }
  | { type: 'status'; status: BackendConnectionStatus }
  | { type: 'event'; kind: string; data?: string; lastEventId?: string };

/**
 * Compartilha a conexão física entre abas da mesma origem.
 *
 * Três canais SSE por aba saturam o limite HTTP/1.1 do navegador na segunda aba:
 * projeção, runtime e cognição ocupam os seis sockets, e um `fetch` de documento fica
 * na fila até o timeout sem sequer chegar ao backend. Um `SharedWorker` nomeado por
 * path mantém três conexões no total e distribui os eventos às abas. Onde a plataforma
 * não oferece SharedWorker, o transporte local abaixo continua sendo o fallback.
 */
function openSharedBackendEvents(
  url: string,
  {
    signal,
    connectTimeoutMs,
    retryBaseMs,
    onStatus,
  }: Required<Pick<BackendEventsOptions, 'connectTimeoutMs' | 'retryBaseMs' | 'onStatus'>> &
    Pick<BackendEventsOptions, 'signal'>,
): BackendEvents | null {
  if (typeof SharedWorker === 'undefined' || localEventsRequested()) return null;

  let worker: SharedWorker;
  try {
    worker = new SharedWorker(new URL('./sseSharedWorker.ts', import.meta.url), {
      // Políticas diferentes não podem disputar os timers globais de uma mesma
      // instância. No Atlas todos usam os defaults e continuam convergindo nos três
      // workers (um por path); testes ou consumidores especiais recebem outro dono.
      name: `vault-backend-events-v2:${url}:${connectTimeoutMs}:${retryBaseMs}`,
      type: 'module',
    });
  } catch {
    return null;
  }

  let closed = false;
  let sharedActive = true;
  let fallback: BackendEvents | null = null;
  let bootstrapTimer: ReturnType<typeof setTimeout> | undefined;
  let lastStatus: BackendConnectionStatus | null = null;
  const listeners = new Map<string, Set<EventListener>>();
  const notifyStatus = (status: BackendConnectionStatus): void => {
    if (closed || status === lastStatus) return;
    lastStatus = status;
    onStatus(status);
  };
  const clearBootstrapTimer = (): void => {
    if (bootstrapTimer !== undefined) globalThis.clearTimeout(bootstrapTimer);
    bootstrapTimer = undefined;
  };

  let receivedEvent = false;
  let deliveryTimer: ReturnType<typeof setTimeout> | undefined;
  const handshakeMs = Math.min(connectTimeoutMs, SHARED_WORKER_HANDSHAKE_CAP_MS);
  const clearDeliveryTimer = (): void => {
    if (deliveryTimer !== undefined) globalThis.clearTimeout(deliveryTimer);
    deliveryTimer = undefined;
  };
  const armDeliveryWatch = (): void => {
    if (deliveryTimer !== undefined || receivedEvent || fallback !== null || closed) return;
    deliveryTimer = globalThis.setTimeout(() => {
      deliveryTimer = undefined;
      if (!receivedEvent) activateFallback();
    }, connectTimeoutMs);
  };

  /**
   * Um construtor de SharedWorker pode ter sucesso e o módulo falhar depois (CSP,
   * chunk ausente ou recurso não suportado). O stream entregue aos consumidores já
   * existe nesse ponto, então o fallback precisa assumir por baixo dele e reaplicar
   * todos os listeners que foram registrados enquanto o módulo carregava.
   *
   * O mesmo caminho cobre o worker zumbi: `ready` + `online` sem nenhum evento. Ele
   * calava o bootstrap e deixava a aba "conectada" sem snapshot — a trilha viva
   * nascia vazia e o raciocínio não tinha onde pousar.
   */
  function activateFallback(): void {
    if (closed || fallback !== null) return;
    sharedWorkersBlocked = true;
    clearBootstrapTimer();
    clearDeliveryTimer();
    worker.onerror = null;
    if (sharedActive) {
      try {
        worker.port.postMessage({ type: 'detach' } satisfies SharedWorkerInbound);
      } catch {
        // Um port cujo módulo falhou pode já estar fechado; não há recurso a liberar.
      }
      worker.port.onmessage = null;
      worker.port.close();
      sharedActive = false;
    }
    fallback = openLocalBackendEvents(url, {
      signal,
      connectTimeoutMs,
      retryBaseMs,
      onStatus: notifyStatus,
    });
    for (const [kind, bucket] of listeners) {
      for (const listener of bucket) fallback.source.addEventListener(kind, listener);
    }
  }

  const post = (message: SharedWorkerInbound): void => {
    if (closed || !sharedActive) return;
    try {
      worker.port.postMessage(message);
    } catch {
      activateFallback();
    }
  };
  const stream: BackendEventStream = {
    addEventListener(kind, listener) {
      const bucket = listeners.get(kind) ?? new Set<EventListener>();
      const first = bucket.size === 0;
      bucket.add(listener);
      listeners.set(kind, bucket);
      if (fallback !== null) fallback.source.addEventListener(kind, listener);
      else if (first) post({ type: 'listen', kind });
    },
    removeEventListener(kind, listener) {
      const bucket = listeners.get(kind);
      bucket?.delete(listener);
      if (bucket?.size === 0) listeners.delete(kind);
      fallback?.source.removeEventListener(kind, listener);
    },
  };
  worker.port.onmessage = (message: MessageEvent<SharedWorkerOutbound>) => {
    if (closed) return;
    const payload = message.data;
    if (!payload || typeof payload !== 'object') return;
    if (payload.type === 'ready') {
      clearBootstrapTimer();
      return;
    }
    if (payload.type === 'status') {
      notifyStatus(payload.status);
      if (payload.status === 'online') armDeliveryWatch();
      return;
    }
    if (payload.type !== 'event') return;
    receivedEvent = true;
    clearDeliveryTimer();
    const event =
      payload.data === undefined
        ? new Event(payload.kind)
        : new MessageEvent(payload.kind, {
            data: payload.data,
            lastEventId: payload.lastEventId ?? '',
          });
    for (const listener of [...(listeners.get(payload.kind) ?? [])]) listener(event);
  };
  worker.onerror = (event): void => {
    event.preventDefault();
    activateFallback();
  };
  // Sem o handshake, nem `onerror` é garantido por todos os navegadores. O teto
  // curto cobre o 404 do script; o prazo longo da conexão fica para o EventSource.
  bootstrapTimer = globalThis.setTimeout(activateFallback, handshakeMs);
  worker.port.start();
  notifyStatus('connecting');
  post({ type: 'attach', path: url, connectTimeoutMs, retryBaseMs });

  const close = (): void => {
    if (closed) return;
    closed = true;
    clearBootstrapTimer();
    clearDeliveryTimer();
    signal?.removeEventListener('abort', close);
    fallback?.close();
    fallback = null;
    worker.onerror = null;
    if (sharedActive) {
      try {
        worker.port.postMessage({ type: 'detach' } satisfies SharedWorkerInbound);
      } catch {
        // Fechar continua idempotente mesmo se o port já morreu.
      }
      worker.port.onmessage = null;
      worker.port.close();
      sharedActive = false;
    }
    listeners.clear();
  };
  signal?.addEventListener('abort', close, { once: true });
  if (signal?.aborted) close();
  return { source: stream, close };
}

/** EventSource por aba, usado onde SharedWorker não existe ou não conseguiu iniciar. */
function openLocalBackendEvents(
  url: string,
  {
    signal,
    connectTimeoutMs,
    retryBaseMs,
    onStatus,
  }: Required<Pick<BackendEventsOptions, 'connectTimeoutMs' | 'retryBaseMs' | 'onStatus'>> &
    Pick<BackendEventsOptions, 'signal'>,
): BackendEvents {
  let closed = false;
  let timedOut = false;
  let failedAttempts = 0;
  let current: EventSource | null = null;
  let timeoutTimer: ReturnType<typeof setTimeout> | undefined;
  let retryTimer: ReturnType<typeof setTimeout> | undefined;
  const listeners = new Map<string, Set<EventListener>>();

  const stream: BackendEventStream = {
    addEventListener(kind, listener) {
      const bucket = listeners.get(kind) ?? new Set<EventListener>();
      const firstListener = listeners.size === 0 && bucket.size === 0;
      bucket.add(listener);
      listeners.set(kind, bucket);
      current?.addEventListener(kind, listener);
      if (firstListener) connect();
    },
    removeEventListener(kind, listener) {
      const bucket = listeners.get(kind);
      bucket?.delete(listener);
      if (bucket?.size === 0) listeners.delete(kind);
      current?.removeEventListener(kind, listener);
    },
  };

  const detachListeners = (source: EventSource): void => {
    for (const [kind, bucket] of listeners) {
      for (const listener of bucket) source.removeEventListener(kind, listener);
    }
  };

  const clearTimeoutTimer = (): void => {
    if (timeoutTimer !== undefined) globalThis.clearTimeout(timeoutTimer);
    timeoutTimer = undefined;
  };
  const clearRetryTimer = (): void => {
    if (retryTimer !== undefined) globalThis.clearTimeout(retryTimer);
    retryTimer = undefined;
  };
  const armTimeout = (): void => {
    if (timeoutTimer !== undefined || timedOut) return;
    timeoutTimer = globalThis.setTimeout(() => {
      timeoutTimer = undefined;
      if (!closed) {
        timedOut = true;
        onStatus('timeout');
      }
    }, connectTimeoutMs);
  };

  const scheduleRetry = (): void => {
    if (closed || retryTimer !== undefined) return;
    const delay = Math.min(retryBaseMs * 2 ** Math.min(failedAttempts, 5), 30_000);
    failedAttempts += 1;
    retryTimer = globalThis.setTimeout(() => {
      retryTimer = undefined;
      connect();
    }, delay);
  };
  const handleOpen = (source: EventSource): void => {
    if (closed || source !== current) return;
    clearTimeoutTimer();
    clearRetryTimer();
    timedOut = false;
    failedAttempts = 0;
    onStatus('online');
  };
  const handleError = (source: EventSource, event: Event): void => {
    if (closed || source !== current) return;
    // `/corpus/events` usa legitimamente `event: error` para um diagnóstico do
    // watcher. Ele chega como MessageEvent com `data` e não significa desconexão;
    // quem valida o payload é o contrato do corpus. O erro de transporte nativo não
    // carrega dados.
    if (
      event instanceof MessageEvent &&
      typeof event.data === 'string' &&
      event.data.length > 0
    ) {
      return;
    }
    onStatus(timedOut ? 'timeout' : 'reconnecting');
    armTimeout();
    // Deixa os demais listeners deste mesmo evento observarem a interrupção. Fechar
    // e destacar dentro do primeiro listener faria o callback de `watchRuntime`
    // desaparecer no navegador embora passasse em mocks que copiam a lista.
    globalThis.queueMicrotask(() => {
      if (closed || source !== current) return;
      current = null;
      detachListeners(source);
      source.close();
      scheduleRetry();
    });
  };
  function connect(): void {
    if (closed || current !== null) return;
    try {
      const source = new EventSource(url);
      current = source;
      source.addEventListener('open', () => handleOpen(source));
      source.addEventListener('error', (event) => handleError(source, event));
      for (const [kind, bucket] of listeners) {
        for (const listener of bucket) source.addEventListener(kind, listener);
      }
      armTimeout();
    } catch {
      onStatus(timedOut ? 'timeout' : 'reconnecting');
      armTimeout();
      scheduleRetry();
    }
  }
  const close = (): void => {
    if (closed) return;
    closed = true;
    clearTimeoutTimer();
    clearRetryTimer();
    signal?.removeEventListener('abort', close);
    if (current !== null) {
      detachListeners(current);
      current.close();
    }
    current = null;
    listeners.clear();
  };

  signal?.addEventListener('abort', close, { once: true });
  onStatus('connecting');
  if (signal?.aborted) close();
  else if (listeners.size > 0) connect();
  return { source: stream, close };
}

/**
 * Abre um fluxo SSE com reconexão explícita e listeners estáveis.
 *
 * O Chrome encerra definitivamente um EventSource que recebeu 502 — exatamente o que
 * o proxy do Vite devolve enquanto o backend está fora. Por isso um erro de transporte
 * fecha aquela instância e cria outra com backoff. Os endpoints começam cada conexão
 * com `current` (corpus) ou snapshot integral (runtime), então reabrir do zero mantém a
 * continuidade sem fabricar um cursor que a API não aceitou.
 */
export function openBackendEvents(
  path: string,
  {
    signal,
    connectTimeoutMs = EVENT_CONNECT_TIMEOUT_MS,
    retryBaseMs = 1_000,
    onStatus = () => undefined,
  }: BackendEventsOptions = {},
): BackendEvents {
  const url = backendUrl(path);
  if (!Number.isFinite(connectTimeoutMs) || connectTimeoutMs <= 0) {
    throw new TypeError('connectTimeoutMs precisa ser positivo e finito');
  }
  if (!Number.isFinite(retryBaseMs) || retryBaseMs <= 0) {
    throw new TypeError('retryBaseMs precisa ser positivo e finito');
  }
  const shared = openSharedBackendEvents(url, {
    signal,
    connectTimeoutMs,
    retryBaseMs,
    onStatus,
  });
  if (shared !== null) return shared;
  return openLocalBackendEvents(url, {
    signal,
    connectTimeoutMs,
    retryBaseMs,
    onStatus,
  });
}
