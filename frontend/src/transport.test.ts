import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  BackendTimeoutError,
  SHARED_WORKER_HANDSHAKE_CAP_MS,
  backendFetch,
  backendUrl,
  openBackendEvents,
  resetBackendEventTransport,
} from './transport';
import {
  BACKEND_PROXY,
  BACKEND_PROXY_PREFIXES,
  validateProxyTarget,
} from '../vite.config';

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  resetBackendEventTransport();
});

describe('transporte HTTP same-origin', () => {
  it('aceita paths locais e recusa URLs que poderiam trocar de origem', () => {
    expect(backendUrl('/api/control/snapshot?fresh=1')).toBe('/api/control/snapshot?fresh=1');
    expect(() => backendUrl('http://example.test/api')).toThrow(TypeError);
    expect(() => backendUrl('//example.test/api')).toThrow(TypeError);
    expect(() => backendUrl('/api\\example')).toThrow(TypeError);
    expect(() => backendUrl('/api#fragment')).toThrow(TypeError);
  });

  it('mantém o proxy de desenvolvimento nos mesmos prefixos do contrato', () => {
    expect(Object.keys(BACKEND_PROXY)).toEqual([...BACKEND_PROXY_PREFIXES]);
    const configured = validateProxyTarget(
      process.env.VAULT_VITE_PROXY_TARGET ?? 'http://127.0.0.1:8000',
    );
    expect(BACKEND_PROXY['/api']).toEqual({ target: configured });
    expect(SHARED_WORKER_HANDSHAKE_CAP_MS).toBeLessThan(8_000);
    expect(validateProxyTarget('https://backend.example.test/')).toBe(
      'https://backend.example.test',
    );
    expect(() => validateProxyTarget('https://user@backend.example.test')).toThrow(TypeError);
    expect(() => validateProxyTarget('file:///tmp/backend')).toThrow(TypeError);
  });

  it('preserva init e sempre limpa o timer após uma resposta', async () => {
    vi.useFakeTimers();
    const response = new Response('{}');
    const fetchMock = vi.fn().mockResolvedValue(response);
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      backendFetch('/api/test', { method: 'POST', body: '{}' }, 250),
    ).resolves.toBe(response);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/test',
      expect.objectContaining({ method: 'POST', body: '{}', signal: expect.any(AbortSignal) }),
    );
    expect(vi.getTimerCount()).toBe(0);
  });

  it('aborta uma chamada pendurada e distingue timeout', async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init.signal?.addEventListener('abort', () => reject(init.signal?.reason));
        }),
      ),
    );

    const request = backendFetch('/corpus/projection', {}, 100);
    const assertion = expect(request).rejects.toBeInstanceOf(BackendTimeoutError);
    await vi.advanceTimersByTimeAsync(100);
    await assertion;
    expect(vi.getTimerCount()).toBe(0);
  });

  it('propaga o cancelamento externo sem convertê-lo em timeout', async () => {
    const external = new AbortController();
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init.signal?.addEventListener('abort', () => reject(init.signal?.reason));
        }),
      ),
    );
    const reason = new DOMException('fim do ciclo', 'AbortError');
    const request = backendFetch('/runtime/events', { signal: external.signal }, 1_000);
    const assertion = expect(request).rejects.toBe(reason);

    external.abort(reason);

    await assertion;
  });
});

describe('transporte SSE', () => {
  it('usa o worker compartilhado e retransmite eventos sem abrir EventSource na aba', () => {
    const ports: PortFake[] = [];
    const eventSource = vi.fn();
    class PortFake {
      readonly sent: unknown[] = [];
      readonly start = vi.fn();
      readonly close = vi.fn();
      onmessage: ((event: MessageEvent) => void) | null = null;

      postMessage(message: unknown): void {
        this.sent.push(message);
      }
      emit(data: unknown): void {
        this.onmessage?.(new MessageEvent('message', { data }));
      }
    }
    class SharedWorkerFake {
      readonly port = new PortFake();
      onerror: ((event: Event) => void) | null = null;

      constructor() {
        ports.push(this.port);
      }
    }
    vi.stubGlobal('SharedWorker', SharedWorkerFake);
    vi.stubGlobal('EventSource', eventSource);
    const statuses: string[] = [];
    const events = openBackendEvents('/runtime/events', {
      onStatus: (status) => statuses.push(status),
    });
    const delivered = vi.fn();
    events.source.addEventListener('runtime_snapshot', delivered);

    expect(eventSource).not.toHaveBeenCalled();
    expect(ports[0]?.start).toHaveBeenCalledOnce();
    expect(ports[0]?.sent).toContainEqual(
      expect.objectContaining({ type: 'attach', path: '/runtime/events' }),
    );
    expect(ports[0]?.sent).toContainEqual({ type: 'listen', kind: 'runtime_snapshot' });

    ports[0]?.emit({ type: 'ready' });
    ports[0]?.emit({ type: 'status', status: 'online' });
    ports[0]?.emit({ type: 'event', kind: 'runtime_snapshot', data: '{"ok":true}' });
    expect(statuses).toEqual(['connecting', 'online']);
    expect(delivered).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'runtime_snapshot', data: '{"ok":true}' }),
    );

    events.close();
    expect(ports[0]?.sent).toContainEqual({ type: 'detach' });
    expect(ports[0]?.close).toHaveBeenCalledOnce();
  });

  it('cai para EventSource se o módulo do worker falhar depois do construtor', () => {
    const workers: SharedWorkerFake[] = [];
    const instances: EventSourceFake[] = [];
    class PortFake {
      readonly sent: unknown[] = [];
      readonly start = vi.fn();
      readonly close = vi.fn();
      onmessage: ((event: MessageEvent) => void) | null = null;

      postMessage(message: unknown): void {
        this.sent.push(message);
      }
    }
    class SharedWorkerFake {
      readonly port = new PortFake();
      onerror: ((event: Event) => void) | null = null;

      constructor() {
        workers.push(this);
      }
    }
    class EventSourceFake extends EventTarget {
      readonly close = vi.fn();

      constructor(readonly url: string) {
        super();
        instances.push(this);
      }
    }
    vi.stubGlobal('SharedWorker', SharedWorkerFake);
    vi.stubGlobal('EventSource', EventSourceFake);
    const statuses: string[] = [];
    const events = openBackendEvents('/runtime/events', {
      onStatus: (status) => statuses.push(status),
    });
    const delivered = vi.fn();
    events.source.addEventListener('runtime_snapshot', delivered);

    workers[0]?.onerror?.(new Event('error'));
    expect(instances).toHaveLength(1);
    expect(instances[0]?.url).toBe('/runtime/events');
    expect(workers[0]?.port.sent).toContainEqual({ type: 'detach' });
    expect(workers[0]?.port.close).toHaveBeenCalledOnce();

    instances[0]?.dispatchEvent(new Event('open'));
    instances[0]?.dispatchEvent(
      new MessageEvent('runtime_snapshot', { data: '{"runtimeRevision":0}' }),
    );
    expect(statuses).toEqual(['connecting', 'online']);
    expect(delivered).toHaveBeenCalledOnce();

    events.close();
    expect(instances[0]?.close).toHaveBeenCalledOnce();
  });

  it('não fica preso se o worker não confirmar que carregou', async () => {
    vi.useFakeTimers();
    const instances: EventSourceFake[] = [];
    class PortFake {
      readonly start = vi.fn();
      readonly close = vi.fn();
      onmessage: ((event: MessageEvent) => void) | null = null;
      postMessage(): void {}
    }
    class SharedWorkerFake {
      readonly port = new PortFake();
      onerror: ((event: Event) => void) | null = null;
    }
    class EventSourceFake extends EventTarget {
      readonly close = vi.fn();

      constructor(readonly url: string) {
        super();
        instances.push(this);
      }
    }
    vi.stubGlobal('SharedWorker', SharedWorkerFake);
    vi.stubGlobal('EventSource', EventSourceFake);
    const events = openBackendEvents('/runtime/events', {
      connectTimeoutMs: 50,
      retryBaseMs: 10,
    });
    events.source.addEventListener('runtime_snapshot', vi.fn());

    expect(instances).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(50);
    expect(instances).toHaveLength(1);
    expect(instances[0]?.url).toBe('/runtime/events');

    instances[0]?.dispatchEvent(new Event('open'));
    events.close();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('cai para EventSource se o worker disser online e não mandar snapshot', async () => {
    vi.useFakeTimers();
    const ports: PortFake[] = [];
    const instances: EventSourceFake[] = [];
    class PortFake {
      readonly sent: unknown[] = [];
      readonly start = vi.fn();
      readonly close = vi.fn();
      onmessage: ((event: MessageEvent) => void) | null = null;

      postMessage(message: unknown): void {
        this.sent.push(message);
      }
      emit(data: unknown): void {
        this.onmessage?.(new MessageEvent('message', { data }));
      }
    }
    class SharedWorkerFake {
      readonly port = new PortFake();
      onerror: ((event: Event) => void) | null = null;

      constructor() {
        ports.push(this.port);
      }
    }
    class EventSourceFake extends EventTarget {
      readonly close = vi.fn();

      constructor(readonly url: string) {
        super();
        instances.push(this);
      }
    }
    vi.stubGlobal('SharedWorker', SharedWorkerFake);
    vi.stubGlobal('EventSource', EventSourceFake);
    const delivered = vi.fn();
    const events = openBackendEvents('/runtime/events', {
      connectTimeoutMs: 50,
      retryBaseMs: 10,
    });
    events.source.addEventListener('runtime_snapshot', delivered);

    ports[0]?.emit({ type: 'ready' });
    ports[0]?.emit({ type: 'status', status: 'online' });
    expect(instances).toHaveLength(0);

    await vi.advanceTimersByTimeAsync(50);
    expect(instances).toHaveLength(1);
    expect(instances[0]?.url).toBe('/runtime/events');

    instances[0]?.dispatchEvent(new Event('open'));
    instances[0]?.dispatchEvent(
      new MessageEvent('runtime_snapshot', { data: '{"runtimeRevision":3}' }),
    );
    expect(delivered).toHaveBeenCalledOnce();
    events.close();
  });

  it('não tenta de novo o worker depois que um canal já caiu para EventSource', () => {
    const constructed = vi.fn();
    const workers: SharedWorkerFake[] = [];
    class PortFake {
      readonly start = vi.fn();
      readonly close = vi.fn();
      onmessage: ((event: MessageEvent) => void) | null = null;
      postMessage(): void {}
    }
    class SharedWorkerFake {
      readonly port = new PortFake();
      onerror: ((event: Event) => void) | null = null;

      constructor() {
        constructed();
        workers.push(this);
      }
    }
    class EventSourceFake extends EventTarget {
      readonly close = vi.fn();
    }
    vi.stubGlobal('SharedWorker', SharedWorkerFake);
    vi.stubGlobal('EventSource', EventSourceFake);

    const first = openBackendEvents('/runtime/events');
    first.source.addEventListener('runtime_snapshot', vi.fn());
    expect(constructed).toHaveBeenCalledOnce();
    workers[0]?.onerror?.(new Event('error'));

    const second = openBackendEvents('/runtime/cognition');
    second.source.addEventListener('cognition_snapshot', vi.fn());
    expect(constructed).toHaveBeenCalledOnce();

    first.close();
    second.close();
  });

  it('respeita ?sse=local e nem instancia o worker', () => {
    const constructed = vi.fn();
    class SharedWorkerFake {
      constructor() {
        constructed();
      }
    }
    class EventSourceFake extends EventTarget {
      readonly close = vi.fn();
    }
    vi.stubGlobal('location', { search: '?sse=local' });
    vi.stubGlobal('SharedWorker', SharedWorkerFake);
    vi.stubGlobal('EventSource', EventSourceFake);

    const events = openBackendEvents('/runtime/events');
    events.source.addEventListener('runtime_snapshot', vi.fn());
    expect(constructed).not.toHaveBeenCalled();
    events.close();
  });

  it('recria conexão terminal, preserva listeners e mede um prazo contínuo', async () => {
    vi.useFakeTimers();
    const constructor = vi.fn();
    const instances: EventSourceFake[] = [];
    class EventSourceFake {
      readonly listeners = new Map<string, Set<EventListener>>();
      readonly close = vi.fn();

      constructor(url: string) {
        constructor(url);
        instances.push(this);
      }
      addEventListener(kind: string, listener: EventListener): void {
        const bucket = this.listeners.get(kind) ?? new Set<EventListener>();
        bucket.add(listener);
        this.listeners.set(kind, bucket);
      }
      removeEventListener(kind: string, listener: EventListener): void {
        this.listeners.get(kind)?.delete(listener);
      }
      emit(kind: string, event: Event): void {
        for (const listener of [...(this.listeners.get(kind) ?? [])]) listener(event);
      }
    }
    vi.stubGlobal('EventSource', EventSourceFake);
    const controller = new AbortController();
    const statuses: string[] = [];
    const events = openBackendEvents('/runtime/events', {
      signal: controller.signal,
      connectTimeoutMs: 50,
      retryBaseMs: 10,
      onStatus: (status) => statuses.push(status),
    });
    const delivered = vi.fn();
    events.source.addEventListener('runtime_snapshot', delivered);

    expect(constructor).toHaveBeenCalledWith('/runtime/events');
    expect(statuses).toEqual(['connecting']);
    await vi.advanceTimersByTimeAsync(20);
    instances[0]!.emit('error', new Event('error'));
    expect(statuses.at(-1)).toBe('reconnecting');
    await Promise.resolve();
    expect(instances[0]!.close).toHaveBeenCalledOnce();

    await vi.advanceTimersByTimeAsync(10);
    expect(instances).toHaveLength(2);
    instances[1]!.emit('runtime_snapshot', new MessageEvent('runtime_snapshot', { data: '{}' }));
    expect(delivered).toHaveBeenCalledOnce();
    await vi.advanceTimersByTimeAsync(10);
    instances[1]!.emit('error', new Event('error'));
    await Promise.resolve();
    await vi.advanceTimersByTimeAsync(10);
    expect(statuses.at(-1)).toBe('timeout');
    expect(instances).toHaveLength(2);

    await vi.advanceTimersByTimeAsync(10);
    expect(instances).toHaveLength(3);
    instances[2]!.emit('open', new Event('open'));
    expect(statuses.at(-1)).toBe('online');
    expect(vi.getTimerCount()).toBe(0);

    instances[2]!.emit(
      'error',
      new MessageEvent('error', {
        data: JSON.stringify({ fingerprint: 'a'.repeat(64), revision: 2, detail: 'aviso' }),
      }),
    );
    expect(statuses.at(-1)).toBe('online');
    expect(vi.getTimerCount()).toBe(0);
    expect(instances[2]!.close).not.toHaveBeenCalled();

    controller.abort();
    expect(instances[2]!.close).toHaveBeenCalledOnce();
  });
});
