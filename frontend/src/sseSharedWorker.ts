/**
 * Dono compartilhado de um canal SSE.
 *
 * Cada instância é nomeada pelo path em `transport.ts`, portanto reúne as abas que
 * observam o mesmo canal e nunca mistura corpus, runtime e cognição. O worker contém
 * apenas transporte: validação e semântica dos payloads continuam nos consumidores.
 */

export {};

type ConnectionStatus = 'connecting' | 'online' | 'reconnecting' | 'timeout';

type Inbound =
  | {
      type: 'attach';
      path: string;
      connectTimeoutMs: number;
      retryBaseMs: number;
    }
  | { type: 'listen'; kind: string }
  | { type: 'detach' };

type Outbound =
  | { type: 'ready' }
  | { type: 'status'; status: ConnectionStatus }
  | { type: 'event'; kind: string; data?: string; lastEventId?: string };

type EventMessage = Extract<Outbound, { type: 'event' }>;

interface PortState {
  kinds: Set<string>;
  ready: boolean;
  replayTimer: ReturnType<typeof setTimeout> | undefined;
}

interface WorkerScope {
  onconnect: ((event: MessageEvent & { ports: MessagePort[] }) => void) | null;
  close(): void;
}

const scope = globalThis as unknown as WorkerScope;
const ports = new Map<MessagePort, PortState>();
const eventKinds = new Set<string>();
const eventListeners = new Map<string, (event: Event) => void>();
let replay: EventMessage[] = [];
let path: string | null = null;
let source: EventSource | null = null;
let status: ConnectionStatus = 'connecting';
let connectTimeoutMs = 8_000;
let retryBaseMs = 1_000;
let timedOut = false;
let failedAttempts = 0;
let timeoutTimer: ReturnType<typeof setTimeout> | undefined;
let retryTimer: ReturnType<typeof setTimeout> | undefined;

function validPath(value: string): boolean {
  return (
    value.startsWith('/') &&
    !value.startsWith('//') &&
    !value.includes('\\') &&
    !value.includes('#') &&
    ![...value].some((character) => {
      const code = character.charCodeAt(0);
      return code <= 31 || code === 127;
    })
  );
}

function send(port: MessagePort, message: Outbound): void {
  try {
    port.postMessage(message);
  } catch {
    const state = ports.get(port);
    if (state?.replayTimer !== undefined) globalThis.clearTimeout(state.replayTimer);
    ports.delete(port);
  }
}

function broadcast(message: Outbound): void {
  for (const [port, state] of [...ports]) {
    if (message.type === 'event' && (!state.ready || !state.kinds.has(message.kind))) continue;
    send(port, message);
  }
}

function setStatus(next: ConnectionStatus): void {
  if (next === status) return;
  status = next;
  broadcast({ type: 'status', status });
}

function clearTimeoutTimer(): void {
  if (timeoutTimer !== undefined) globalThis.clearTimeout(timeoutTimer);
  timeoutTimer = undefined;
}

function clearRetryTimer(): void {
  if (retryTimer !== undefined) globalThis.clearTimeout(retryTimer);
  retryTimer = undefined;
}

function armTimeout(): void {
  if (timeoutTimer !== undefined || timedOut) return;
  timeoutTimer = globalThis.setTimeout(() => {
    timeoutTimer = undefined;
    timedOut = true;
    setStatus('timeout');
  }, connectTimeoutMs);
}

function eventMessage(kind: string, event: MessageEvent<string>): EventMessage {
  return {
    type: 'event',
    kind,
    data: event.data,
    ...(event.lastEventId === '' ? {} : { lastEventId: event.lastEventId }),
  };
}

function corpusVersion(message: EventMessage): { fingerprint: string | null; revision: number } | null {
  if (message.data === undefined) return null;
  try {
    const value = JSON.parse(message.data) as unknown;
    if (value === null || typeof value !== 'object') return null;
    const fingerprint = (value as { fingerprint?: unknown }).fingerprint;
    const revision = (value as { revision?: unknown }).revision;
    if (
      (typeof fingerprint !== 'string' && fingerprint !== null) ||
      (typeof fingerprint === 'string' && !/^[0-9a-f]{64}$/.test(fingerprint)) ||
      typeof revision !== 'number' ||
      !Number.isInteger(revision) ||
      revision < 0
    ) {
      return null;
    }
    return { fingerprint, revision };
  } catch {
    return null;
  }
}

/**
 * Guarda o suficiente para uma aba tardia reconstruir o mesmo estado.
 *
 * Os três endpoints iniciam por `current` ou snapshot integral. Receber outro desses
 * envelopes substitui toda a história anterior; eventos nomeados depois dele formam
 * a cauda que a nova aba também precisa consumir. O limite é defensivo: se uma sessão
 * excepcionalmente longa o alcançar, a conexão é reaberta para obter snapshot novo,
 * em vez de manter memória ilimitada ou entregar uma cauda truncada como se completa.
 */
function remember(message: EventMessage): void {
  if (path === '/corpus/events') {
    if (message.kind === 'current' || message.kind === 'changed') {
      // `changed(B)` torna `current(A)` história. Repetir ambos a uma aba que já
      // carregou B faria A pedir reload antes de B chegar, e o mesmo worker vivo
      // repetiria o ciclo na página seguinte. Para quem entra agora B é o `current`
      // que uma conexão física nova enviaria — inclusive para trocar um snapshot
      // estático pelo backend vivo. Mantemos só esse estado e, quando existir, o
      // diagnóstico vigente daquela mesma revisão.
      replay = [{ ...message, kind: 'current' }];
    } else if (message.kind === 'error') {
      // A fila limitada do watcher pode compactar `changed(B)` e conservar apenas
      // `error(B)`. Nesse caso o fingerprint/revision do erro também é o estado mais
      // novo: uma aba tardia precisa primeiro enxergá-lo como `current(B)` e depois
      // receber o diagnóstico. Payload inválido não recebe semântica inventada.
      const incoming = corpusVersion(message);
      const remembered = replay[0] === undefined ? null : corpusVersion(replay[0]);
      if (
        incoming !== null &&
        incoming.fingerprint !== null &&
        (remembered === null || incoming.revision > remembered.revision)
      ) {
        replay = [{ ...message, kind: 'current' }, message];
      } else {
        replay = replay.filter((item) => item.kind !== 'error' && item.kind !== 'recovered');
        replay.push(message);
      }
    } else {
      replay = replay.filter((item) => item.kind !== 'error' && item.kind !== 'recovered');
      replay.push(message);
    }
    return;
  }
  if (['current', 'runtime_snapshot', 'cognition_snapshot'].includes(message.kind)) {
    replay = [message];
  } else {
    replay.push(message);
  }
  if (replay.length <= 1_024 || source === null) return;
  const stale = source;
  replay = [];
  source = null;
  setStatus('reconnecting');
  armTimeout();
  globalThis.queueMicrotask(() => {
    detachSource(stale);
    stale.close();
    connect();
  });
}

function forward(kind: string, event: Event): void {
  if (event instanceof MessageEvent && typeof event.data === 'string') {
    const message = eventMessage(kind, event);
    remember(message);
    broadcast(message);
  } else {
    // Erro nativo é estado de transporte daquele instante. Repeti-lo a uma aba que
    // acabou de entrar faria parecer que ela observou uma queda histórica.
    broadcast({ type: 'event', kind });
  }
}

function listen(kind: string): void {
  if (kind === 'open' || eventKinds.has(kind)) return;
  eventKinds.add(kind);
  if (kind === 'error') return;
  const listener = (event: Event): void => forward(kind, event);
  eventListeners.set(kind, listener);
  source?.addEventListener(kind, listener);
}

function detachSource(current: EventSource): void {
  current.removeEventListener('open', handleOpen);
  current.removeEventListener('error', handleError);
  for (const [kind, listener] of eventListeners) current.removeEventListener(kind, listener);
}

function handleOpen(event: Event): void {
  const current = event.currentTarget;
  if (!(current instanceof EventSource) || current !== source) return;
  clearTimeoutTimer();
  clearRetryTimer();
  timedOut = false;
  failedAttempts = 0;
  setStatus('online');
}

function scheduleRetry(): void {
  if (ports.size === 0 || retryTimer !== undefined) return;
  const delay = Math.min(retryBaseMs * 2 ** Math.min(failedAttempts, 5), 30_000);
  failedAttempts += 1;
  retryTimer = globalThis.setTimeout(() => {
    retryTimer = undefined;
    connect();
  }, delay);
}

function handleError(event: Event): void {
  const current = event.currentTarget;
  if (!(current instanceof EventSource) || current !== source) return;
  // `/corpus/events` usa `event: error` com dados para diagnóstico. Ele é mensagem do
  // contrato, não queda do socket, e precisa chegar intacto ao watcher.
  if (event instanceof MessageEvent && typeof event.data === 'string' && event.data !== '') {
    forward('error', event);
    return;
  }
  forward('error', event);
  // O replay deixa de provar estado vivo quando a conexão física cai. Uma aba que
  // entrar durante a indisponibilidade pode ter carregado o snapshot estático; usar
  // o cache antigo como recuperação provocaria reload em ciclo. A reconexão repõe
  // `current`/snapshot antes de publicar sua cauda.
  replay = [];
  setStatus(timedOut ? 'timeout' : 'reconnecting');
  armTimeout();
  globalThis.queueMicrotask(() => {
    if (source !== current) return;
    source = null;
    detachSource(current);
    current.close();
    scheduleRetry();
  });
}

function connect(): void {
  if (ports.size === 0 || path === null || source !== null) return;
  try {
    const current = new EventSource(path);
    source = current;
    current.addEventListener('open', handleOpen);
    current.addEventListener('error', handleError);
    for (const [kind, listener] of eventListeners) current.addEventListener(kind, listener);
  } catch {
    setStatus(timedOut ? 'timeout' : 'reconnecting');
    armTimeout();
    scheduleRetry();
  }
}

function shutdown(): void {
  clearTimeoutTimer();
  clearRetryTimer();
  if (source !== null) {
    detachSource(source);
    source.close();
    source = null;
  }
  scope.close();
}

function receive(port: MessagePort, message: Inbound): void {
  if (message.type === 'listen') {
    const state = ports.get(port);
    if (!state) return;
    state.kinds.add(message.kind);
    listen(message.kind);
    // O primeiro evento de cada endpoint é o snapshot. Conectar no `attach`, antes
    // deste listener existir, deixava o servidor responder rápido demais e a aba
    // ficava online sem jamais receber estado. O consumidor registra snapshot/current
    // primeiro; só então há autorização para abrir o socket.
    connect();
    if (!state.ready) {
      if (state.replayTimer !== undefined) globalThis.clearTimeout(state.replayTimer);
      // `openBackendEvents` registra vários tipos em sequência. Um turno de espera
      // reúne essa lista e só então repete snapshot + cauda na ordem original.
      state.replayTimer = globalThis.setTimeout(() => {
        state.replayTimer = undefined;
        for (const item of replay) {
          if (state.kinds.has(item.kind)) send(port, item);
        }
        state.ready = true;
      }, 0);
    } else {
      // Listener acrescentado depois da inicialização recebe o histórico apenas do
      // novo tipo; os tipos já ativos não são duplicados.
      for (const item of replay) {
        if (item.kind === message.kind) send(port, item);
      }
    }
    return;
  }
  if (message.type === 'detach') {
    const state = ports.get(port);
    if (state?.replayTimer !== undefined) globalThis.clearTimeout(state.replayTimer);
    ports.delete(port);
    port.close();
    if (ports.size === 0) shutdown();
    return;
  }
  if (!validPath(message.path)) return;
  if (
    !Number.isFinite(message.connectTimeoutMs) ||
    message.connectTimeoutMs <= 0 ||
    !Number.isFinite(message.retryBaseMs) ||
    message.retryBaseMs <= 0
  ) {
    return;
  }
  if (path !== null) {
    // O nome criado por `transport.ts` inclui estes dois valores. Esta verificação
    // torna o primeiro contrato imutável mesmo diante de uma mensagem defeituosa,
    // em vez de deixar uma aba reprogramar os timers de todas as demais.
    if (
      path !== message.path ||
      connectTimeoutMs !== message.connectTimeoutMs ||
      retryBaseMs !== message.retryBaseMs
    ) {
      return;
    }
  } else {
    path = message.path;
    connectTimeoutMs = message.connectTimeoutMs;
    retryBaseMs = message.retryBaseMs;
  }
  send(port, { type: 'status', status });
  // Uma porta tardia herda a conexão já aberta. Rearmar o prazo aqui criava um
  // timeout inevitável oito segundos depois: não haverá outro `open` para limpá-lo.
  if (status !== 'online') armTimeout();
}

scope.onconnect = (event): void => {
  const port = event.ports[0];
  if (!port) return;
  ports.set(port, { kinds: new Set(), ready: false, replayTimer: undefined });
  port.onmessage = (message: MessageEvent<Inbound>): void => {
    if (message.data && typeof message.data === 'object') receive(port, message.data);
  };
  port.start();
  send(port, { type: 'ready' });
};
