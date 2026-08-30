import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  ControlPollingTimeoutError,
  controlPollingMode,
  createControlPolling,
  createSerialTaskQueue,
} from './controlPolling';

function deferred<T>(): {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason: unknown) => void;
} {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

async function settle(): Promise<void> {
  // A fila encadeia `then`, `catch` e `finally`; drenar todos aqui evita fazer cada
  // teste conhecer quantas microtarefas uma implementação correta usa internamente.
  for (let index = 0; index < 12; index += 1) await Promise.resolve();
}

afterEach(() => {
  vi.useRealTimers();
});

describe('cadência do snapshot de controle', () => {
  it('mantém leitura lenta para o indicador e pausa só com o documento oculto', () => {
    expect(controlPollingMode(false, false, true)).toBe('collapsed');
    expect(controlPollingMode(true, false, false)).toBe('paused');
    expect(controlPollingMode(true, true, true)).toBe('collapsed');
    expect(controlPollingMode(true, false, true)).toBe('open');
  });

  it('não lê oculto e faz uma leitura imediata ao abrir', async () => {
    vi.useFakeTimers();
    const request = vi.fn().mockResolvedValue('agora');
    const onValue = vi.fn();
    const polling = createControlPolling({ request, onValue, onError: vi.fn() });

    await vi.advanceTimersByTimeAsync(60_000);
    expect(request).not.toHaveBeenCalled();
    polling.setMode('open');
    await settle();
    expect(request).toHaveBeenCalledOnce();
    expect(onValue).toHaveBeenCalledWith('agora');
  });

  it('usa a cadência lenta recolhido e atualiza imediatamente ao expandir', async () => {
    vi.useFakeTimers();
    const request = vi.fn().mockResolvedValue('snapshot');
    const polling = createControlPolling({
      request,
      onValue: vi.fn(),
      onError: vi.fn(),
      openIntervalMs: 25,
      collapsedIntervalMs: 200,
    });

    polling.setMode('collapsed');
    await settle();
    await vi.advanceTimersByTimeAsync(199);
    expect(request).toHaveBeenCalledOnce();
    polling.setMode('open');
    await settle();
    expect(request).toHaveBeenCalledTimes(2);
  });

  it('mantém single-flight e condensa refreshes concorrentes', async () => {
    vi.useFakeTimers();
    const first = deferred<string>();
    const second = deferred<string>();
    const request = vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    const onValue = vi.fn();
    const polling = createControlPolling({ request, onValue, onError: vi.fn() });

    polling.setMode('open');
    polling.refresh();
    polling.refresh();
    await settle();
    expect(request).toHaveBeenCalledOnce();

    first.resolve('primeiro');
    await settle();
    expect(request).toHaveBeenCalledTimes(2);
    second.resolve('segundo');
    await settle();
    expect(onValue.mock.calls.map(([value]) => value)).toEqual(['primeiro', 'segundo']);
  });

  it('aborta no prazo e consegue tentar novamente', async () => {
    vi.useFakeTimers();
    const signals: AbortSignal[] = [];
    const request = vi.fn((signal: AbortSignal) => {
      signals.push(signal);
      return new Promise<string>(() => undefined);
    });
    const onError = vi.fn();
    const polling = createControlPolling({
      request,
      onValue: vi.fn(),
      onError,
      openIntervalMs: 25,
      timeoutMs: 50,
    });

    polling.setMode('open');
    await vi.advanceTimersByTimeAsync(50);
    expect(signals[0]?.aborted).toBe(true);
    expect(onError.mock.calls[0]?.[0]).toBeInstanceOf(ControlPollingTimeoutError);
    await vi.advanceTimersByTimeAsync(25);
    expect(request).toHaveBeenCalledTimes(2);
  });

  it('ignora a resposta antiga depois de pausa e reabertura', async () => {
    const old = deferred<string>();
    const request = vi.fn().mockReturnValueOnce(old.promise).mockResolvedValueOnce('novo');
    const onValue = vi.fn();
    const polling = createControlPolling({ request, onValue, onError: vi.fn() });

    polling.setMode('open');
    polling.setMode('paused');
    await settle();
    old.resolve('velho');
    polling.setMode('open');
    await settle();

    expect(request).toHaveBeenCalledTimes(2);
    expect(onValue).toHaveBeenCalledTimes(1);
    expect(onValue).toHaveBeenCalledWith('novo');
  });

  it('hold invalida o GET anterior e só retoma depois da última escrita', async () => {
    const old = deferred<string>();
    const request = vi.fn().mockReturnValueOnce(old.promise).mockResolvedValueOnce('reconciliado');
    const onValue = vi.fn();
    const polling = createControlPolling({ request, onValue, onError: vi.fn() });
    polling.setMode('open');

    const releaseFirst = polling.hold();
    const releaseSecond = polling.hold();
    old.resolve('anterior à escrita');
    releaseFirst();
    await settle();
    expect(request).toHaveBeenCalledOnce();
    releaseSecond();
    await settle();

    expect(request).toHaveBeenCalledTimes(2);
    expect(onValue).toHaveBeenCalledTimes(1);
    expect(onValue).toHaveBeenCalledWith('reconciliado');
  });

  it('dispose cancela e não deixa callback tardio', async () => {
    vi.useFakeTimers();
    const late = deferred<string>();
    const signalSeen: AbortSignal[] = [];
    const onValue = vi.fn();
    const onError = vi.fn();
    const polling = createControlPolling({
      request: (signal) => {
        signalSeen.push(signal);
        return late.promise;
      },
      onValue,
      onError,
    });
    polling.setMode('open');
    polling.dispose();
    late.resolve('tarde');
    await settle();
    await vi.runAllTimersAsync();

    expect(signalSeen[0]?.aborted).toBe(true);
    expect(onValue).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe('fila de ações de controle', () => {
  it('preserva a ordem e mantém o polling suspenso até esvaziar', async () => {
    const first = deferred<void>();
    const order: string[] = [];
    const busy: boolean[] = [];
    const queue = createSerialTaskQueue((value) => busy.push(value));

    queue.enqueue(async () => {
      order.push('primeira-início');
      await first.promise;
      order.push('primeira-fim');
    });
    queue.enqueue(async () => {
      order.push('segunda');
    });
    await settle();
    expect(order).toEqual(['primeira-início']);
    expect(busy).toEqual([true]);

    first.resolve();
    await settle();
    await settle();
    expect(order).toEqual(['primeira-início', 'primeira-fim', 'segunda']);
    expect(busy).toEqual([true, false]);
  });
});
