import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  advanceRuntime,
  parseRuntimeEvent,
  parseRuntimeHeartbeat,
  parseRuntimeSnapshot,
  watchRuntime,
} from './runtime';

function event(revision: number, overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: `runtime-${String(revision).padStart(20, '0')}`,
    revision,
    timestamp: `2026-08-04T0${Math.min(revision, 9)}:00:00+00:00`,
    type: 'task_created',
    actor: 'orquestrador',
    provider: 'groq',
    endpoint: 'qwen/qwen3',
    task: 'task-001',
    entity: 'Física/Entropia',
    before: { status: 'pending' },
    after: { status: 'running' },
    metadata: { attempt: 1 },
    ...overrides,
  };
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('fronteira do runtime', () => {
  it('retém só escalares permitidos e descarta mapas livres', () => {
    const parsed = parseRuntimeEvent(event(1));
    expect(parsed).toEqual({
      id: 'runtime-00000000000000000001',
      revision: 1,
      timestamp: '2026-08-04T01:00:00+00:00',
      type: 'task_created',
      actor: 'orquestrador',
      provider: 'groq',
      endpoint: 'qwen/qwen3',
      task: 'task-001',
      entity: 'Física/Entropia',
    });
    expect(parsed).not.toHaveProperty('before');
    expect(parsed).not.toHaveProperty('after');
    expect(parsed).not.toHaveProperty('metadata');
  });

  it('aceita somente o resumo estruturado necessário ao painel de quórum', () => {
    const parsed = parseRuntimeEvent(
      event(1, {
        type: 'vote_received',
        metadata: {
          panel_id: 'panel-1',
          role: 'verificador-factual',
          family: 'qwen',
          decision: 'approve',
          action: 'promote',
          confidence: 0.82,
          schema_valid: true,
          valid_votes: 3,
          provider_count: 2,
          family_count: 3,
          tally: { approve: 3, reject: 0, revise: 0, abstain: 0 },
          blocking_issues: ['não deve atravessar'],
        },
      }),
    );

    expect(parsed).toMatchObject({
      panelId: 'panel-1',
      role: 'verificador-factual',
      family: 'qwen',
      decision: 'approve',
      action: 'promote',
      confidence: 0.82,
      schemaValid: true,
      validVotes: 3,
      providerCount: 2,
      familyCount: 3,
      tally: { approve: 3, reject: 0, revise: 0, abstain: 0 },
    });
    expect(parsed).not.toHaveProperty('blocking_issues');
    expect(parsed).not.toHaveProperty('metadata');
  });

  it('recusa identidade divergente e texto de raciocínio nos campos visuais', () => {
    expect(parseRuntimeEvent(event(2, { id: 'runtime-00000000000000000001' }))).toBeNull();
    expect(parseRuntimeEvent(event(1, { task: '<think>privado</think>' }))).toBeNull();
    expect(parseRuntimeEvent(event(1, { type: 'evento-inventado' }))).toBeNull();
  });

  it('aceita somente prazo de chamada positivo e limitado', () => {
    expect(
      parseRuntimeEvent(event(1, { metadata: { deadline_seconds: 240 } }))
        ?.deadlineSeconds,
    ).toBe(240);
    expect(parseRuntimeEvent(event(1, { metadata: { deadline_seconds: 0 } }))).toBeNull();
    expect(parseRuntimeEvent(event(1, { metadata: { deadline_seconds: 601 } }))).toBeNull();
  });

  it('ordena, deduplica e avança a revisão sem misturá-la ao corpus', () => {
    const snapshot = parseRuntimeSnapshot({
      runtimeRevision: 2,
      events: [event(2), event(1), event(2, { actor: 'último' }), { inválido: true }],
      operational: { nodes: ['ignorado'], edges: ['ignorado'] },
    });
    expect(snapshot?.events.map((item) => item.revision)).toEqual([1, 2]);
    expect(snapshot?.events[1]?.actor).toBe('último');

    const next = advanceRuntime(snapshot!, parseRuntimeEvent(event(3))!);
    expect(next.runtimeRevision).toBe(3);
    expect(next.events.map((item) => item.revision)).toEqual([1, 2, 3]);
    expect(advanceRuntime(next, parseRuntimeEvent(event(2))!)).toBe(next);
  });

  it('aceita heartbeat somente com revisão inteira não negativa', () => {
    expect(parseRuntimeHeartbeat({ runtimeRevision: 0 })).toBe(0);
    expect(parseRuntimeHeartbeat({ runtimeRevision: 42 })).toBe(42);
    expect(parseRuntimeHeartbeat({ runtimeRevision: -1 })).toBeNull();
    expect(parseRuntimeHeartbeat({ runtimeRevision: 1.5 })).toBeNull();
    expect(parseRuntimeHeartbeat({ runtimeRevision: '2' })).toBeNull();
  });
});

describe('SSE operacional', () => {
  it('entrega snapshot e evento pelos nomes reais do backend', () => {
    const listeners = new Map<string, (event: Event) => void>();
    const constructed = vi.fn();
    class EventSourceFake {
      constructor(url: string) {
        constructed(url);
      }
      addEventListener(kind: string, listener: EventListener): void {
        listeners.set(kind, listener);
      }
      close(): void {}
    }
    vi.stubGlobal('EventSource', EventSourceFake);
    const onSnapshot = vi.fn();
    const onEvent = vi.fn();
    watchRuntime(onSnapshot, onEvent, vi.fn());
    expect(constructed).toHaveBeenCalledWith('/runtime/events');

    listeners.get('runtime_snapshot')?.(
      new MessageEvent('runtime_snapshot', {
        data: JSON.stringify({ runtimeRevision: 1, events: [event(1)] }),
      }),
    );
    listeners.get('task_assigned')?.(
      new MessageEvent('task_assigned', {
        data: JSON.stringify(event(2, { type: 'task_assigned' })),
      }),
    );

    expect(onSnapshot).toHaveBeenCalledWith(
      expect.objectContaining({ runtimeRevision: 1 }),
    );
    expect(onEvent).toHaveBeenCalledWith(
      expect.objectContaining({ revision: 2, type: 'task_assigned' }),
    );
  });

  it('preserva a reconexão nativa e torna visível o erro inicial', () => {
    const listeners = new Map<string, (event: Event) => void>();
    const close = vi.fn();
    class EventSourceFake {
      addEventListener(kind: string, listener: EventListener): void {
        listeners.set(kind, listener);
      }
      close(): void {
        close();
      }
    }
    vi.stubGlobal('EventSource', EventSourceFake);
    const onError = vi.fn();
    watchRuntime(vi.fn(), vi.fn(), onError);
    listeners.get('error')?.(new Event('error'));
    expect(close).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledWith(
      'fluxo operacional interrompido; aguardando reconexão.',
    );
  });

  it('declara inatividade e recupera somente com o próximo sinal válido', async () => {
    vi.useFakeTimers();
    const instances: EventSourceFake[] = [];
    class EventSourceFake {
      readonly listeners = new Map<string, Set<EventListener>>();
      readonly close = vi.fn();

      constructor() {
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
    const statuses: string[] = [];
    const onError = vi.fn();
    const close = watchRuntime(vi.fn(), vi.fn(), onError, {
      inactivityTimeoutMs: 50,
      onConnectionStatus: (status) => statuses.push(status),
    });
    const source = instances[0]!;

    source.emit('open', new Event('open'));
    source.emit(
      'runtime_snapshot',
      new MessageEvent('runtime_snapshot', {
        data: JSON.stringify({ runtimeRevision: 1, events: [event(1)] }),
      }),
    );
    expect(statuses).toEqual(['connecting', 'online']);

    await vi.advanceTimersByTimeAsync(50);
    expect(statuses.at(-1)).toBe('timeout');

    source.emit(
      'runtime_heartbeat',
      new MessageEvent('runtime_heartbeat', {
        data: JSON.stringify({ runtimeRevision: 'inválida' }),
      }),
    );
    expect(statuses.at(-1)).toBe('timeout');
    expect(onError).toHaveBeenCalledWith(
      'heartbeat operacional inválido ou fora do cursor; ignorado.',
    );

    source.emit(
      'runtime_heartbeat',
      new MessageEvent('runtime_heartbeat', {
        data: JSON.stringify({ runtimeRevision: 0 }),
      }),
    );
    expect(statuses.at(-1)).toBe('timeout');

    source.emit(
      'runtime_heartbeat',
      new MessageEvent('runtime_heartbeat', {
        data: JSON.stringify({ runtimeRevision: 1 }),
      }),
    );
    expect(statuses.at(-1)).toBe('online');

    await vi.advanceTimersByTimeAsync(49);
    expect(statuses.at(-1)).toBe('online');
    source.emit(
      'task_assigned',
      new MessageEvent('task_assigned', {
        data: JSON.stringify(event(2, { type: 'task_assigned' })),
      }),
    );
    await vi.advanceTimersByTimeAsync(49);
    expect(statuses.at(-1)).toBe('online');
    await vi.advanceTimersByTimeAsync(1);
    expect(statuses.at(-1)).toBe('timeout');

    close();
    expect(source.close).toHaveBeenCalledOnce();
  });

  it('aceita heartbeat de abertura antes do snapshot para não declarar timeout', async () => {
    vi.useFakeTimers();
    const instances: EventSourceFake[] = [];
    class EventSourceFake {
      readonly listeners = new Map<string, Set<EventListener>>();
      readonly close = vi.fn();

      constructor() {
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
    const statuses: string[] = [];
    const onError = vi.fn();
    const onSnapshot = vi.fn();
    const close = watchRuntime(onSnapshot, vi.fn(), onError, {
      inactivityTimeoutMs: 50,
      onConnectionStatus: (status) => statuses.push(status),
    });
    const source = instances[0]!;

    source.emit('open', new Event('open'));
    source.emit(
      'runtime_heartbeat',
      new MessageEvent('runtime_heartbeat', {
        data: JSON.stringify({ runtimeRevision: 0 }),
      }),
    );
    expect(onError).not.toHaveBeenCalled();
    expect(statuses.at(-1)).toBe('online');

    await vi.advanceTimersByTimeAsync(49);
    expect(statuses.at(-1)).toBe('online');
    await vi.advanceTimersByTimeAsync(1);
    expect(statuses.at(-1)).toBe('timeout');

    source.emit(
      'runtime_heartbeat',
      new MessageEvent('runtime_heartbeat', {
        data: JSON.stringify({ runtimeRevision: 0 }),
      }),
    );
    expect(statuses.at(-1)).toBe('online');
    expect(onSnapshot).not.toHaveBeenCalled();

    close();
  });
});
