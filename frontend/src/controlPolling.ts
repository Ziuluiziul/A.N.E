/**
 * Cadencia a leitura do painel de controle sem deixar trabalho órfão.
 *
 * O escalonador não conhece URL, `fetch` nem DOM. Ele recebe uma leitura cancelável,
 * mantém no máximo uma tentativa lógica em voo e só arma o próximo intervalo depois
 * que a tentativa corrente termina. Ocultar o documento invalida a geração corrente:
 * mesmo uma implementação que ignore `AbortSignal` não consegue publicar tarde. O dock
 * oculto apenas reduz a cadência, porque o indicador persistente também lê o snapshot.
 */

export type ControlPollingMode = 'open' | 'collapsed' | 'paused';

export interface ControlPollingOptions<T> {
  request: (signal: AbortSignal) => Promise<T>;
  onValue: (value: T) => void;
  onError: (error: unknown) => void;
  openIntervalMs?: number;
  collapsedIntervalMs?: number;
  timeoutMs?: number;
}

export interface ControlPolling {
  readonly mode: ControlPollingMode;
  setMode(mode: ControlPollingMode): void;
  /** Pede uma leitura imediata; chamadas durante um voo se condensam em uma só. */
  refresh(): void;
  /**
   * Suspende enquanto uma operação exclusiva usa o mesmo snapshot.
   *
   * O retorno libera exatamente uma suspensão. Suspensões aninhadas só retomam a
   * leitura quando a última termina.
   */
  hold(): () => void;
  dispose(): void;
}

export class ControlPollingTimeoutError extends Error {
  constructor(timeoutMs: number) {
    super(`snapshot de controle não respondeu em ${timeoutMs} ms`);
    this.name = 'ControlPollingTimeoutError';
  }
}

const DEFAULT_OPEN_INTERVAL_MS = 2_500;
const DEFAULT_COLLAPSED_INTERVAL_MS = 20_000;
const DEFAULT_TIMEOUT_MS = 8_000;

function positiveDuration(value: number, name: string): number {
  if (!Number.isFinite(value) || value <= 0) {
    throw new TypeError(`${name} precisa ser positivo e finito`);
  }
  return value;
}

function abortError(message: string): DOMException {
  return new DOMException(message, 'AbortError');
}

/**
 * A leitura lenta continua quando o dock está oculto: o indicador de atividade é uma
 * segunda superfície real e precisa de fila/running para não confundir espera com
 * trabalho. Documento oculto continua pausando tudo; dock aberto apenas acelera.
 */
export function controlPollingMode(
  dockVisible: boolean,
  dockCollapsed: boolean,
  documentVisible: boolean,
): ControlPollingMode {
  if (!documentVisible) return 'paused';
  return !dockVisible || dockCollapsed ? 'collapsed' : 'open';
}

export function createControlPolling<T>({
  request,
  onValue,
  onError,
  openIntervalMs = DEFAULT_OPEN_INTERVAL_MS,
  collapsedIntervalMs = DEFAULT_COLLAPSED_INTERVAL_MS,
  timeoutMs = DEFAULT_TIMEOUT_MS,
}: ControlPollingOptions<T>): ControlPolling {
  const intervalOpen = positiveDuration(openIntervalMs, 'openIntervalMs');
  const intervalCollapsed = positiveDuration(collapsedIntervalMs, 'collapsedIntervalMs');
  const deadline = positiveDuration(timeoutMs, 'timeoutMs');

  let mode: ControlPollingMode = 'paused';
  let holds = 0;
  let disposed = false;
  let generation = 0;
  let refreshQueued = false;
  let scheduled: ReturnType<typeof setTimeout> | undefined;
  let active:
    | {
        token: number;
        cancel: (reason: unknown) => void;
      }
    | undefined;

  const enabled = (): boolean => !disposed && holds === 0 && mode !== 'paused';

  const clearScheduled = (): void => {
    if (scheduled !== undefined) globalThis.clearTimeout(scheduled);
    scheduled = undefined;
  };

  const interval = (): number =>
    mode === 'collapsed' ? intervalCollapsed : intervalOpen;

  const schedule = (): void => {
    if (!enabled() || active !== undefined || scheduled !== undefined) return;
    scheduled = globalThis.setTimeout(() => {
      scheduled = undefined;
      start();
    }, interval());
  };

  const invalidate = (reason: unknown): void => {
    generation += 1;
    refreshQueued = false;
    clearScheduled();
    active?.cancel(reason);
  };

  function start(): void {
    if (!enabled()) return;
    clearScheduled();
    if (active !== undefined) {
      refreshQueued = true;
      return;
    }
    refreshQueued = false;

    const token = ++generation;
    const controller = new AbortController();
    let rejectCancellation: (reason: unknown) => void = () => undefined;
    let cancelled = false;
    const cancellation = new Promise<never>((_resolve, reject) => {
      rejectCancellation = reject;
    });
    let deadlineTimer: ReturnType<typeof setTimeout> | undefined;
    const timeout = new Promise<never>((_resolve, reject) => {
      deadlineTimer = globalThis.setTimeout(() => {
        const error = new ControlPollingTimeoutError(deadline);
        controller.abort(error);
        reject(error);
      }, deadline);
    });

    let operation: Promise<T>;
    try {
      operation = Promise.resolve(request(controller.signal));
    } catch (error) {
      operation = Promise.reject(error);
    }

    active = {
      token,
      cancel(reason) {
        if (cancelled) return;
        cancelled = true;
        controller.abort(reason);
        rejectCancellation(reason);
      },
    };

    void Promise.race([operation, timeout, cancellation])
      .then(
        (value) => {
          if (enabled() && token === generation) onValue(value);
        },
        (error: unknown) => {
          if (enabled() && token === generation) onError(error);
        },
      )
      .finally(() => {
        if (deadlineTimer !== undefined) globalThis.clearTimeout(deadlineTimer);
        if (active?.token === token) active = undefined;
        if (!enabled()) return;
        if (refreshQueued) {
          refreshQueued = false;
          start();
        } else {
          schedule();
        }
      });
  }

  const handle: ControlPolling = {
    get mode() {
      return mode;
    },
    setMode(next) {
      if (disposed || next === mode) return;
      const previous = mode;
      const wasEnabled = enabled();
      mode = next;
      if (!enabled()) {
        invalidate(abortError('polling de controle pausado'));
        return;
      }
      if (!wasEnabled) {
        start();
        return;
      }
      if (previous === 'collapsed' && next === 'open') {
        // Ao expandir, o leitor voltou. Não o obrigue a esperar o restante da cadência
        // lenta por um snapshot que pode ter vinte segundos.
        clearScheduled();
        start();
        return;
      }
      // Só a cadência mudou. A leitura corrente continua válida; o próximo prazo passa
      // a contar do estado novo.
      clearScheduled();
      schedule();
    },
    refresh() {
      if (!enabled()) return;
      clearScheduled();
      start();
    },
    hold() {
      if (disposed) return () => undefined;
      holds += 1;
      if (holds === 1) invalidate(abortError('polling suspenso por operação de controle'));
      let released = false;
      return () => {
        if (released) return;
        released = true;
        holds = Math.max(holds - 1, 0);
        if (enabled()) start();
      };
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      invalidate(abortError('polling de controle encerrado'));
    },
  };
  return handle;
}

export interface SerialTaskQueue {
  enqueue(task: () => Promise<void>): void;
  dispose(): void;
}

/**
 * Serializa ações que devolvem o mesmo snapshot.
 *
 * `onBusyChange(true)` acontece antes de a primeira ação poder começar, de modo que o
 * chamador consiga invalidar um GET antigo. Falha de uma ação não impede a seguinte;
 * cada ação continua responsável por apresentar o próprio erro.
 */
export function createSerialTaskQueue(
  onBusyChange: (busy: boolean) => void,
): SerialTaskQueue {
  let tail = Promise.resolve();
  let pending = 0;
  let disposed = false;

  return {
    enqueue(task) {
      if (disposed) return;
      pending += 1;
      if (pending === 1) onBusyChange(true);
      tail = tail
        .then(async () => {
          if (!disposed) await task();
        })
        .catch(() => undefined)
        .finally(() => {
          pending -= 1;
          if (pending === 0) onBusyChange(false);
        });
    },
    dispose() {
      disposed = true;
    },
  };
}
