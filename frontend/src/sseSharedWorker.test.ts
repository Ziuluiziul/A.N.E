import { afterEach, describe, expect, it, vi } from 'vitest';

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  Reflect.deleteProperty(globalThis, 'onconnect');
  vi.resetModules();
});

class PortFake {
  readonly sent: unknown[] = [];
  readonly start = vi.fn();
  readonly close = vi.fn();
  onmessage: ((event: MessageEvent) => void) | null = null;

  postMessage(message: unknown): void {
    this.sent.push(message);
  }

  receive(data: unknown): void {
    this.onmessage?.(new MessageEvent('message', { data }));
  }
}

describe('dono SSE compartilhado', () => {
  it('repassa snapshot e cauda à aba tardia sem abrir outra conexão', async () => {
    vi.useFakeTimers();
    const instances: EventSourceFake[] = [];
    class EventSourceFake extends EventTarget {
      readonly close = vi.fn();

      constructor(readonly url: string) {
        super();
        instances.push(this);
      }

      emit(kind: string, data?: string, lastEventId = ''): void {
        this.dispatchEvent(
          data === undefined
            ? new Event(kind)
            : new MessageEvent(kind, { data, lastEventId }),
        );
      }
    }
    const closeWorker = vi.fn();
    vi.stubGlobal('EventSource', EventSourceFake);
    vi.stubGlobal('close', closeWorker);
    await import('./sseSharedWorker');
    const connect = (globalThis as unknown as {
      onconnect: (event: MessageEvent & { ports: MessagePort[] }) => void;
    }).onconnect;

    const first = new PortFake();
    connect({ ports: [first as unknown as MessagePort] } as MessageEvent & {
      ports: MessagePort[];
    });
    first.receive({
      type: 'attach',
      path: '/runtime/events',
      connectTimeoutMs: 8_000,
      retryBaseMs: 1_000,
    });
    first.receive({ type: 'listen', kind: 'runtime_snapshot' });
    first.receive({ type: 'listen', kind: 'task_assigned' });
    expect(instances).toHaveLength(1);

    instances[0]?.emit('open');
    instances[0]?.emit('runtime_snapshot', '{"runtimeRevision":1}', 'runtime-1');
    await vi.advanceTimersByTimeAsync(0);
    instances[0]?.emit('task_assigned', '{"revision":2}', 'runtime-2');

    const second = new PortFake();
    connect({ ports: [second as unknown as MessagePort] } as MessageEvent & {
      ports: MessagePort[];
    });
    second.receive({
      type: 'attach',
      path: '/runtime/events',
      connectTimeoutMs: 8_000,
      retryBaseMs: 1_000,
    });
    second.receive({ type: 'listen', kind: 'runtime_snapshot' });
    second.receive({ type: 'listen', kind: 'task_assigned' });
    await vi.advanceTimersByTimeAsync(0);

    expect(instances).toHaveLength(1);
    expect(second.sent).toEqual([
      { type: 'ready' },
      { type: 'status', status: 'online' },
      {
        type: 'event',
        kind: 'runtime_snapshot',
        data: '{"runtimeRevision":1}',
        lastEventId: 'runtime-1',
      },
      {
        type: 'event',
        kind: 'task_assigned',
        data: '{"revision":2}',
        lastEventId: 'runtime-2',
      },
    ]);

    // A segunda porta herdou um socket já online. Entrar não pode armar um prazo que
    // só um novo `open` limparia, porque esse `open` não vai acontecer.
    await vi.advanceTimersByTimeAsync(8_001);
    expect(second.sent).not.toContainEqual({ type: 'status', status: 'timeout' });

    second.receive({ type: 'detach' });
    expect(instances[0]?.close).not.toHaveBeenCalled();
    expect(closeWorker).not.toHaveBeenCalled();

    first.receive({ type: 'detach' });
    expect(instances[0]?.close).toHaveBeenCalledOnce();
    expect(closeWorker).toHaveBeenCalledOnce();
  });

  it('coalesce current antigo quando changed já representa o corpus mais novo', async () => {
    vi.useFakeTimers();
    const instances: EventSourceFake[] = [];
    class EventSourceFake extends EventTarget {
      readonly close = vi.fn();

      constructor(readonly url: string) {
        super();
        instances.push(this);
      }

      emit(kind: string, data: string): void {
        this.dispatchEvent(new MessageEvent(kind, { data }));
      }
    }
    vi.stubGlobal('EventSource', EventSourceFake);
    vi.stubGlobal('close', vi.fn());
    await import('./sseSharedWorker');
    const connect = (globalThis as unknown as {
      onconnect: (event: MessageEvent & { ports: MessagePort[] }) => void;
    }).onconnect;
    const attach = (port: PortFake): void => {
      connect({ ports: [port as unknown as MessagePort] } as MessageEvent & {
        ports: MessagePort[];
      });
      port.receive({
        type: 'attach',
        path: '/corpus/events',
        connectTimeoutMs: 8_000,
        retryBaseMs: 1_000,
      });
      port.receive({ type: 'listen', kind: 'current' });
      port.receive({ type: 'listen', kind: 'changed' });
    };

    const first = new PortFake();
    attach(first);
    instances[0]?.dispatchEvent(new Event('open'));
    const current = JSON.stringify({ fingerprint: 'a'.repeat(64), revision: 1, detail: null });
    const changed = JSON.stringify({ fingerprint: 'b'.repeat(64), revision: 2, detail: null });
    instances[0]?.emit('current', current);
    await vi.advanceTimersByTimeAsync(0);
    instances[0]?.emit('changed', changed);

    const late = new PortFake();
    attach(late);
    await vi.advanceTimersByTimeAsync(0);

    expect(instances).toHaveLength(1);
    expect(late.sent).toContainEqual({
      type: 'event',
      kind: 'current',
      data: changed,
    });
    expect(late.sent).not.toContainEqual({
      type: 'event',
      kind: 'current',
      data: current,
    });
  });

  it('trata error de revisão nova como estado compactado do corpus', async () => {
    vi.useFakeTimers();
    const instances: EventSourceFake[] = [];
    class EventSourceFake extends EventTarget {
      readonly close = vi.fn();

      constructor(readonly url: string) {
        super();
        instances.push(this);
      }

      emit(kind: string, data: string): void {
        this.dispatchEvent(new MessageEvent(kind, { data }));
      }
    }
    vi.stubGlobal('EventSource', EventSourceFake);
    vi.stubGlobal('close', vi.fn());
    await import('./sseSharedWorker');
    const connect = (globalThis as unknown as {
      onconnect: (event: MessageEvent & { ports: MessagePort[] }) => void;
    }).onconnect;
    const attach = (port: PortFake): void => {
      connect({ ports: [port as unknown as MessagePort] } as MessageEvent & {
        ports: MessagePort[];
      });
      port.receive({
        type: 'attach',
        path: '/corpus/events',
        connectTimeoutMs: 8_000,
        retryBaseMs: 1_000,
      });
      port.receive({ type: 'listen', kind: 'current' });
      port.receive({ type: 'listen', kind: 'error' });
    };

    const first = new PortFake();
    attach(first);
    instances[0]?.dispatchEvent(new Event('open'));
    const oldCurrent = JSON.stringify({
      fingerprint: 'a'.repeat(64),
      revision: 1,
      detail: null,
    });
    const compacted = JSON.stringify({
      fingerprint: 'b'.repeat(64),
      revision: 2,
      detail: 'memória espacial não reconciliada',
    });
    instances[0]?.emit('current', oldCurrent);
    await vi.advanceTimersByTimeAsync(0);
    instances[0]?.emit('error', compacted);

    const late = new PortFake();
    attach(late);
    await vi.advanceTimersByTimeAsync(0);

    expect(late.sent).toContainEqual({ type: 'event', kind: 'current', data: compacted });
    expect(late.sent).toContainEqual({ type: 'event', kind: 'error', data: compacted });
    expect(late.sent).not.toContainEqual({
      type: 'event',
      kind: 'current',
      data: oldCurrent,
    });
  });

  it('invalida o replay do corpus quando o transporte cai', async () => {
    vi.useFakeTimers();
    const instances: EventSourceFake[] = [];
    class EventSourceFake extends EventTarget {
      readonly close = vi.fn();

      constructor(readonly url: string) {
        super();
        instances.push(this);
      }

      emit(kind: string, data?: string): void {
        this.dispatchEvent(
          data === undefined ? new Event(kind) : new MessageEvent(kind, { data }),
        );
      }
    }
    vi.stubGlobal('EventSource', EventSourceFake);
    vi.stubGlobal('close', vi.fn());
    await import('./sseSharedWorker');
    const connect = (globalThis as unknown as {
      onconnect: (event: MessageEvent & { ports: MessagePort[] }) => void;
    }).onconnect;
    const attach = (port: PortFake): void => {
      connect({ ports: [port as unknown as MessagePort] } as MessageEvent & {
        ports: MessagePort[];
      });
      port.receive({
        type: 'attach',
        path: '/corpus/events',
        connectTimeoutMs: 8_000,
        retryBaseMs: 1_000,
      });
      port.receive({ type: 'listen', kind: 'current' });
    };

    const first = new PortFake();
    attach(first);
    instances[0]?.emit('open');
    const current = JSON.stringify({
      fingerprint: 'a'.repeat(64),
      revision: 1,
      detail: null,
    });
    instances[0]?.emit('current', current);
    await vi.advanceTimersByTimeAsync(0);
    instances[0]?.emit('error');
    await Promise.resolve();

    const late = new PortFake();
    attach(late);
    await vi.advanceTimersByTimeAsync(0);
    expect(late.sent).not.toContainEqual({ type: 'event', kind: 'current', data: current });

    await vi.advanceTimersByTimeAsync(1_000);
    instances[1]?.emit('open');
    const recovered = JSON.stringify({
      fingerprint: 'b'.repeat(64),
      revision: 2,
      detail: null,
    });
    instances[1]?.emit('current', recovered);
    expect(late.sent).toContainEqual({ type: 'event', kind: 'current', data: recovered });
  });

  it('mede timeout também ao renovar uma cauda que atingiu o limite', async () => {
    vi.useFakeTimers();
    const instances: EventSourceFake[] = [];
    class EventSourceFake extends EventTarget {
      readonly close = vi.fn();

      constructor(readonly url: string) {
        super();
        instances.push(this);
      }

      emit(kind: string, data: string): void {
        this.dispatchEvent(new MessageEvent(kind, { data }));
      }
    }
    vi.stubGlobal('EventSource', EventSourceFake);
    vi.stubGlobal('close', vi.fn());
    await import('./sseSharedWorker');
    const connect = (globalThis as unknown as {
      onconnect: (event: MessageEvent & { ports: MessagePort[] }) => void;
    }).onconnect;
    const port = new PortFake();
    connect({ ports: [port as unknown as MessagePort] } as MessageEvent & {
      ports: MessagePort[];
    });
    port.receive({
      type: 'attach',
      path: '/runtime/events',
      connectTimeoutMs: 50,
      retryBaseMs: 10,
    });
    port.receive({ type: 'listen', kind: 'runtime_snapshot' });
    port.receive({ type: 'listen', kind: 'task_assigned' });
    instances[0]?.dispatchEvent(new Event('open'));
    instances[0]?.emit('runtime_snapshot', '{"runtimeRevision":0}');
    await vi.advanceTimersByTimeAsync(0);

    for (let revision = 1; revision <= 1_024; revision += 1) {
      instances[0]?.emit('task_assigned', JSON.stringify({ revision }));
    }
    await Promise.resolve();

    expect(instances).toHaveLength(2);
    expect(instances[0]?.close).toHaveBeenCalledOnce();
    expect(port.sent).toContainEqual({ type: 'status', status: 'reconnecting' });
    await vi.advanceTimersByTimeAsync(50);
    expect(port.sent).toContainEqual({ type: 'status', status: 'timeout' });
  });

  it('não deixa uma segunda porta sobrescrever a política do worker', async () => {
    vi.useFakeTimers();
    const instances: EventSourceFake[] = [];
    class EventSourceFake extends EventTarget {
      readonly close = vi.fn();

      constructor(readonly url: string) {
        super();
        instances.push(this);
      }
    }
    vi.stubGlobal('EventSource', EventSourceFake);
    vi.stubGlobal('close', vi.fn());
    await import('./sseSharedWorker');
    const connect = (globalThis as unknown as {
      onconnect: (event: MessageEvent & { ports: MessagePort[] }) => void;
    }).onconnect;
    const first = new PortFake();
    connect({ ports: [first as unknown as MessagePort] } as MessageEvent & {
      ports: MessagePort[];
    });
    first.receive({
      type: 'attach',
      path: '/runtime/events',
      connectTimeoutMs: 50,
      retryBaseMs: 10,
    });
    first.receive({ type: 'listen', kind: 'runtime_snapshot' });

    const conflicting = new PortFake();
    connect({ ports: [conflicting as unknown as MessagePort] } as MessageEvent & {
      ports: MessagePort[];
    });
    conflicting.receive({
      type: 'attach',
      path: '/runtime/events',
      connectTimeoutMs: 5_000,
      retryBaseMs: 2_000,
    });

    await vi.advanceTimersByTimeAsync(50);
    expect(first.sent).toContainEqual({ type: 'status', status: 'timeout' });
    expect(conflicting.sent).not.toContainEqual({ type: 'status', status: 'connecting' });
  });
});
