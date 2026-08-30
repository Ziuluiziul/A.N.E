import { describe, expect, it } from 'vitest';

import type { LayoutMap, Vec3 } from './layout';
import {
  ESPERA_SATURACAO_S,
  aplicarMorfologia,
  direcaoPara,
  morphOffset,
  sinaisOperacionais,
  type SinalOperacional,
} from './operationalMotion';
import type { RuntimeSnapshot } from './runtime';

const AGORA = Date.parse('2026-08-16T18:00:00Z');

function evento(parcial: Record<string, unknown>): RuntimeSnapshot['events'][number] {
  return {
    id: `e-${Math.random().toString(36).slice(2, 8)}`,
    revision: 1,
    timestamp: '2026-08-16T17:59:00Z',
    type: 'evidence_recorded',
    ...parcial,
  } as RuntimeSnapshot['events'][number];
}

function snapshot(eventos: RuntimeSnapshot['events']): RuntimeSnapshot {
  return {
    runtimeRevision: 1,
    events: eventos,
    entityByTask: new Map<string, string>(),
  };
}

function sinal(parcial: Partial<SinalOperacional>): SinalOperacional {
  return { estado: 'parado', idadeS: 0, ...parcial };
}

describe('sinaisOperacionais', () => {
  it('chamada aberta marca ativo com o provedor que executa', () => {
    const chamada = evento({
      id: 'aberta',
      type: 'call_started',
      task: 't1',
      provider: 'groq',
      timestamp: '2026-08-16T17:58:30Z',
    });
    const outra = evento({ id: 'outra', task: 't1', type: 'evidence_recorded' });

    const sinais = sinaisOperacionais(snapshot([chamada, outra]), AGORA);

    expect(sinais.get('outra')?.estado).toBe('ativo');
    expect(sinais.get('outra')?.provedor).toBe('groq');
  });

  it('chamada fechada devolve o painel ao repouso', () => {
    const eventos = [
      evento({ id: 'aberta', type: 'call_started', task: 't1', provider: 'groq' }),
      evento({ id: 'fechada', type: 'call_completed', task: 't1' }),
      evento({ id: 'apos', task: 't1', type: 'evidence_recorded' }),
    ];

    const sinais = sinaisOperacionais(snapshot(eventos), AGORA);

    expect(sinais.get('apos')?.estado).toBe('parado');
  });

  it('painel decidido propaga o veredito aos eventos do painel', () => {
    const eventos = [
      evento({ id: 'voto', panelId: 'p1', type: 'vote_received' }),
      evento({
        id: 'decisao',
        panelId: 'p1',
        type: 'quorum_decided',
        action: 'escalate',
        entity: 'Física/Nota',
      }),
    ];

    const sinais = sinaisOperacionais(snapshot(eventos), AGORA);

    expect(sinais.get('voto')?.estado).toBe('decidido');
    expect(sinais.get('voto')?.desfecho).toBe('escalate');
    expect(sinais.get('voto')?.entidade).toBe('Física/Nota');
  });

  it('veredito revise volta a esperar, não inventa desfecho', () => {
    const eventos = [
      evento({ id: 'voto', panelId: 'p1', type: 'vote_received' }),
      evento({ id: 'decisao', panelId: 'p1', type: 'quorum_decided', action: 'revise' }),
    ];

    const sinais = sinaisOperacionais(snapshot(eventos), AGORA);

    expect(sinais.get('voto')?.estado).toBe('esperando');
    expect(sinais.get('voto')?.desfecho).toBeUndefined();
  });

  it('tarefa criada sem chamada espera, com a idade do evento', () => {
    const eventos = [
      evento({
        id: 'criada',
        type: 'task_assigned',
        task: 't1',
        timestamp: '2026-08-16T17:30:00Z',
      }),
    ];

    const sinais = sinaisOperacionais(snapshot(eventos), AGORA);

    expect(sinais.get('criada')?.estado).toBe('esperando');
    expect(sinais.get('criada')?.idadeS).toBe(30 * 60);
  });
});

describe('morphOffset', () => {
  const amplitude = 100;
  const norte = { x: 0, y: 1, z: 0 };

  it('ativo inclina na direção do provedor, 40% da amplitude', () => {
    const offset = morphOffset(sinal({ estado: 'ativo' }), norte, null, amplitude);
    expect(offset.y).toBeCloseTo(40);
  });

  it('ativo sem direção de provedor não inventa movimento', () => {
    const offset = morphOffset(sinal({ estado: 'ativo' }), null, null, amplitude);
    expect(offset).toEqual({ x: 0, y: 0, z: 0 });
  });

  it('esperando cresce com o tempo e satura no teto', () => {
    const curto = morphOffset(sinal({ estado: 'esperando', idadeS: 0 }), null, null, amplitude);
    const medio = morphOffset(
      sinal({ estado: 'esperando', idadeS: ESPERA_SATURACAO_S / 2 }),
      null,
      null,
      amplitude,
    );
    const longo = morphOffset(
      sinal({ estado: 'esperando', idadeS: ESPERA_SATURACAO_S * 4 }),
      null,
      null,
      amplitude,
    );
    expect(Math.hypot(curto.x, curto.y)).toBeCloseTo(0);
    expect(Math.hypot(medio.x, medio.y)).toBeGreaterThan(0);
    expect(Math.hypot(longo.x, longo.y)).toBeLessThanOrEqual(amplitude * 0.25 + 1e-6);
  });

  it('decidido converge sobre a entidade e o desfecho move o eixo vertical', () => {
    const promover = morphOffset(
      sinal({ estado: 'decidido', desfecho: 'promote' }),
      null,
      norte,
      amplitude,
    );
    const rejeitar = morphOffset(
      sinal({ estado: 'decidido', desfecho: 'reject' }),
      null,
      norte,
      amplitude,
    );
    expect(promover.y).toBeCloseTo(55 + 30);
    expect(rejeitar.y).toBeCloseTo(55 - 30);
  });

  it('parado é âncora: deslocamento zero', () => {
    expect(morphOffset(sinal({ estado: 'parado' }), norte, norte, amplitude)).toEqual({
      x: 0,
      y: 0,
      z: 0,
    });
  });
});

describe('aplicarMorfologia', () => {
  it('desloca só os nós com sinal e nunca muta o mapa de entrada', () => {
    const ancora: Vec3 = { x: 10, y: 0, z: 0 };
    const alvos: LayoutMap = new Map([
      ['runtime:event:e1', ancora],
      ['runtime:event:e2', { x: -10, y: 0, z: 0 }],
    ]);
    const sinais = new Map([
      ['e1', sinal({ estado: 'ativo', provedor: 'groq' })],
      ['e2', sinal({ estado: 'parado' })],
    ]);

    const resultado = aplicarMorfologia(
      alvos,
      sinais,
      () => ({ x: 1, y: 0, z: 0 }),
      () => null,
      100,
    );

    expect(resultado.get('runtime:event:e1')).toEqual({ x: 50, y: 0, z: 0 });
    expect(resultado.get('runtime:event:e2')).toEqual({ x: -10, y: 0, z: 0 });
    expect(alvos.get('runtime:event:e1')).toEqual(ancora);
  });

  it('ignora evento sem nó correspondente', () => {
    const alvos: LayoutMap = new Map();
    const sinais = new Map([['fantasma', sinal({ estado: 'ativo' })]]);

    const resultado = aplicarMorfologia(alvos, sinais, () => null, () => null, 100);

    expect(resultado.size).toBe(0);
  });
});

describe('direcaoPara', () => {
  it('devolve o vetor unitário da âncora ao alvo', () => {
    const direcao = direcaoPara({ x: 5, y: 0, z: 0 }, { x: 0, y: 0, z: 0 });
    expect(direcao).toEqual({ x: 1, y: 0, z: 0 });
  });

  it('alvo ausente ou coincidente não tem direção', () => {
    expect(direcaoPara(undefined, { x: 0, y: 0, z: 0 })).toBeNull();
    expect(direcaoPara({ x: 0, y: 0, z: 0 }, { x: 0, y: 0, z: 0 })).toBeNull();
  });
});
