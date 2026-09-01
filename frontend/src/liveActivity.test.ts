import { describe, expect, it } from 'vitest';

import {
  describeLiveActivity,
  OPEN_ACTIVITY_EVIDENCE_MS,
  RECENT_ACTIVITY_MS,
  type LiveActivitySource,
} from './liveActivity';
import type { RuntimeEvent, RuntimeSnapshot } from './runtime';

function event(
  revision: number,
  type: RuntimeEvent['type'],
  extra: Partial<RuntimeEvent> = {},
): RuntimeEvent {
  return {
    id: `runtime-${String(revision).padStart(20, '0')}`,
    revision,
    timestamp: '2026-08-11T22:00:00.000Z',
    type,
    ...extra,
  };
}

function snapshot(...events: RuntimeEvent[]): RuntimeSnapshot {
  return {
    runtimeRevision: events.at(-1)?.revision ?? 0,
    events,
    entityByTask: new Map(),
  };
}

const operation = {
  auto: true,
  queued: 34,
  running: 0,
  budget: '6 chamadas por execução',
};

function source(overrides: Partial<LiveActivitySource> = {}): LiveActivitySource {
  return {
    operation,
    controlFreshness: 'fresh',
    runtimeConnection: 'online',
    runtimeSnapshotReady: true,
    ...overrides,
  };
}

describe('resumo visível da atividade', () => {
  it('diz qual modelo está trabalhando e aponta para seu painel', () => {
    const view = describeLiveActivity(
      snapshot(
        event(1, 'call_started', {
          provider: 'openrouter',
          endpoint: 'nvidia/nemotron:free',
          narration: 'Consultando o modelo como proponente.',
        }),
      ),
      source({ operation: { ...operation, running: 1 } }),
      Date.parse('2026-08-11T22:00:05.000Z'),
    );

    expect(view.phase).toBe('active');
    expect(view.headline).toBe('1 modelo trabalhando');
    expect(view.detail).toContain('openrouter · nvidia/nemotron:free');
    expect(view.targetId).toBe('runtime:model:openrouter/nvidia/nemotron:free');
  });

  it('prefere a narração do evento ao rótulo do tipo', () => {
    const view = describeLiveActivity(
      snapshot(
        event(1, 'quorum_decided', {
          narration:
            'Quórum decidiu reject. Nenhum wikilink foi declarado com as relações do vocabulário permitido.',
        }),
      ),
      source(),
      Date.parse('2026-08-11T22:01:00.000Z'),
    );
    expect(view.detail).toContain('Nenhum wikilink foi declarado');
    expect(view.detail).not.toContain('Quórum decidido ·');
  });

  it('não chama histórico de trabalho atual', () => {
    const view = describeLiveActivity(
      snapshot(
        event(1, 'call_started', { provider: 'groq', endpoint: 'qwen' }),
        event(2, 'call_completed', { provider: 'groq', endpoint: 'qwen' }),
      ),
      source(),
      Date.parse('2026-08-11T22:01:00.000Z'),
    );

    expect(view.phase).toBe('idle');
    expect(view.headline).toBe('Em espera · 34 tarefas na fila');
    expect(view.detail).toContain('Último evento: Chamada concluída');
    expect(view.meta).toContain('último');
    expect(view.targetId).toBe('runtime:event:runtime-00000000000000000002');
  });

  it('traz ciclo, próxima execução e falhas no meta do cartão', () => {
    const view = describeLiveActivity(
      snapshot(event(1, 'call_completed', { provider: 'groq', endpoint: 'qwen' })),
      source({
        operation: {
          ...operation,
          lastCycle: 'há 2 min',
          nextRun: 'em 40 s',
          failures: ['groq recusou a cota'],
        },
      }),
      Date.parse('2026-08-11T22:01:00.000Z'),
    );
    expect(view.meta).toContain('ciclo há 2 min');
    expect(view.meta).toContain('próxima em 40 s');
    expect(view.meta).toContain('1 falha recente');
  });

  it('não despeja ISO do last_cycle no rodapé do cartão', () => {
    const view = describeLiveActivity(
      snapshot(event(1, 'call_completed', { provider: 'groq', endpoint: 'qwen' })),
      source({
        operation: {
          ...operation,
          lastCycle: '2026-09-01T04:47:19+00:00',
        },
      }),
      Date.parse('2026-08-11T22:01:00.000Z'),
    );
    expect(view.meta).not.toContain('2026-09-01T');
    expect(view.meta).toMatch(/ciclo \d{2}:\d{2}:\d{2}/);
  });

  it('mantém a chegada acesa por uma janela finita', () => {
    const start = Date.parse('2026-08-11T22:00:00.000Z');
    const view = describeLiveActivity(
      snapshot(event(1, 'evidence_recorded', { task: 'aut-123' })),
      source(),
      start + RECENT_ACTIVITY_MS - 1,
    );
    expect(view.phase).toBe('recent');
    expect(view.expiresAt).toBe(start + RECENT_ACTIVITY_MS);
  });

  it('mostra pausa explícita sem apagar o último evento', () => {
    const view = describeLiveActivity(
      snapshot(event(1, 'task_created', { task: 'aut-123' })),
      source({ operation: { ...operation, auto: false } }),
      Date.parse('2026-08-11T22:01:00.000Z'),
    );
    expect(view.phase).toBe('paused');
    expect(view.headline).toBe('Automação pausada');
    expect(view.detail).toContain('Tarefa criada');
  });

  it('declara ausência antes do primeiro evento', () => {
    const view = describeLiveActivity(
      snapshot(),
      source({
        operation: null,
        controlFreshness: 'loading',
        runtimeConnection: 'connecting',
        runtimeSnapshotReady: false,
      }),
      0,
    );
    expect(view.phase).toBe('empty');
    expect(view.headline).toContain('Conectando');
    expect(view.targetId).toBeNull();
  });

  it('não trata EventSource aberto como snapshot recebido', () => {
    const view = describeLiveActivity(
      snapshot(event(1, 'call_started', { provider: 'groq', endpoint: 'qwen' })),
      source({ runtimeSnapshotReady: false }),
      Date.parse('2026-08-11T22:00:01.000Z'),
    );
    expect(view.phase).toBe('unavailable');
    expect(view.headline).toContain('snapshot');
  });

  it.each(['reconnecting', 'timeout'] as const)(
    'preserva a revisão sem afirmar trabalho durante %s',
    (runtimeConnection) => {
      const view = describeLiveActivity(
        snapshot(event(1, 'call_started', { provider: 'groq', endpoint: 'qwen' })),
        source({ runtimeConnection, runtimeSnapshotReady: false }),
        Date.parse('2026-08-11T22:00:01.000Z'),
      );
      expect(view.phase).toBe('unavailable');
      expect(view.detail).toContain('Última revisão preservada');
      expect(view.targetId).toBe('runtime:event:runtime-00000000000000000001');
    },
  );

  it('não promove running antigo quando o controle está stale', () => {
    const view = describeLiveActivity(
      snapshot(event(1, 'evidence_recorded', { task: 'aut-123' })),
      source({
        operation: { ...operation, running: 1 },
        controlFreshness: 'stale',
      }),
      Date.parse('2026-08-11T22:00:01.000Z'),
    );
    expect(view.phase).toBe('unavailable');
    expect(view.headline).toBe('Controle desatualizado');
    expect(view.meta).not.toContain('fila 34');
  });

  it('mantém chamada recém-aberta observável mesmo sem usar running stale', () => {
    const view = describeLiveActivity(
      snapshot(event(1, 'call_started', { provider: 'groq', endpoint: 'qwen' })),
      source({ controlFreshness: 'stale' }),
      Date.parse('2026-08-11T22:00:01.000Z'),
    );
    expect(view.phase).toBe('active');
    expect(view.headline).toBe('1 modelo trabalhando');
    expect(view.meta).toContain('controle desatualizado');
  });

  it('expira abertura órfã e execução sem evento recente', () => {
    const expiredAt = Date.parse('2026-08-11T22:00:00.000Z') + OPEN_ACTIVITY_EVIDENCE_MS;
    const orphan = describeLiveActivity(
      snapshot(event(1, 'call_started', { provider: 'groq', endpoint: 'qwen' })),
      source({ operation: { ...operation, running: 1 } }),
      expiredAt,
    );
    expect(orphan.phase).toBe('unavailable');
    expect(orphan.headline).toContain('sem desfecho');

    const queueOnly = describeLiveActivity(
      snapshot(event(1, 'task_assigned', { task: 'aut-123' })),
      source({ operation: { ...operation, running: 1 } }),
      expiredAt,
    );
    expect(queueOnly.phase).toBe('unavailable');
    expect(queueOnly.headline).toContain('sem sinal recente');
  });

  it('mostra trabalho drenando antes de dizer que a automação está pausada', () => {
    const view = describeLiveActivity(
      snapshot(event(1, 'task_assigned', { task: 'aut-123' })),
      source({ operation: { ...operation, auto: false, running: 1 } }),
      Date.parse('2026-08-11T22:00:01.000Z'),
    );
    expect(view.phase).toBe('active');
    expect(view.headline).toBe('1 execução em curso');
    expect(view.targetId).toBeNull();
  });
});

describe('o raciocínio ao vivo no cartão', () => {
  const chamada = snapshot(
    event(1, 'call_started', {
      provider: 'openrouter',
      endpoint: 'nvidia/nemotron:free',
      narration: 'Consultando o modelo como proponente.',
    }),
  );
  const agora = Date.parse('2026-08-11T22:00:05.000Z');

  it('troca a narração do sistema pelo que o modelo está dizendo', () => {
    const view = describeLiveActivity(
      chamada,
      source({
        operation: { ...operation, running: 1 },
        thoughts: new Map([['openrouter/nvidia/nemotron:free', 'preciso conferir o DOI']]),
      }),
      agora,
    );

    expect(view.headline).toBe('Pensando');
    expect(view.detail).toContain('preciso conferir o DOI');
    // A frase do orquestrador descreve o sistema; havendo texto do provedor, é ele que
    // interessa. Repetir as duas diria a mesma coisa duas vezes.
    expect(view.detail).not.toContain('Consultando o modelo');
  });

  it('volta à narração do sistema quando o pensamento é de outro modelo', () => {
    const view = describeLiveActivity(
      chamada,
      source({
        operation: { ...operation, running: 1 },
        thoughts: new Map([['groq/qwen3', 'pensamento de outra chamada']]),
      }),
      agora,
    );

    expect(view.headline).toBe('1 modelo trabalhando');
    expect(view.detail).toContain('Consultando o modelo');
  });

  it('não fica pensando quando o canal cognitivo não trouxe nada', () => {
    const view = describeLiveActivity(
      chamada,
      source({ operation: { ...operation, running: 1 }, thoughts: new Map() }),
      agora,
    );
    expect(view.headline).toBe('1 modelo trabalhando');
    expect(view.layout ?? 'single').toBe('single');
  });

  it('divide o cartão quando vários modelos pensam juntos', () => {
    const view = describeLiveActivity(
      snapshot(
        event(1, 'call_started', {
          provider: 'groq',
          endpoint: 'qwen',
          role: 'proponente',
          narration: 'Consultando groq/qwen como proponente.',
        }),
        event(2, 'vote_requested', {
          provider: 'nous',
          endpoint: 'longcat',
          role: 'verificador-factual',
          narration: 'Pedido de voto a nous/longcat.',
        }),
        event(3, 'vote_requested', {
          provider: 'nvidia',
          endpoint: 'glm',
          role: 'revisor-estrutural',
          narration: 'Pedido de voto a nvidia/glm.',
        }),
      ),
      source({
        operation: { ...operation, running: 1 },
        thoughts: new Map([
          ['groq/qwen', 'o DOI precisa resolver'],
          ['nous/longcat', 'a aresta não está tipada'],
        ]),
      }),
      agora,
    );

    expect(view.layout).toBe('split');
    expect(view.headline).toBe('3 modelos pensando');
    expect(view.streams).toHaveLength(3);
    expect(view.streams?.map((stream) => stream.role)).toEqual([
      'proponente',
      'verificador-factual',
      'revisor-estrutural',
    ]);
    expect(view.streams?.[0]?.text).toContain('o DOI precisa resolver');
    expect(view.streams?.[1]?.text).toContain('a aresta não está tipada');
    expect(view.streams?.[2]?.thinking).toBe(false);
    expect(view.detail).toContain('groq · qwen');
    expect(view.detail).toContain('nous · longcat');
  });

  it('volta a um cartão só quando o painel desfaz', () => {
    const view = describeLiveActivity(
      snapshot(
        event(1, 'call_started', { provider: 'groq', endpoint: 'qwen' }),
        event(2, 'call_completed', { provider: 'groq', endpoint: 'qwen' }),
      ),
      source(),
      Date.parse('2026-08-11T22:01:00.000Z'),
    );
    expect(view.layout ?? 'single').toBe('single');
    expect(view.streams ?? []).toEqual([]);
    expect(view.headline).toContain('Em espera');
  });
});
