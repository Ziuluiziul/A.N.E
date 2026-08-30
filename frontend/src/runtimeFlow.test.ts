// A direção do fluxo é afirmação, não enfeite: ela diz para onde a informação vai.
// Errá-la é pior que não ter fluxo nenhum — um fio que corre para o lado errado
// ensina o contrário do que a trilha registrou.

import { describe, expect, it } from 'vitest';

import { flowAttributes, flowDirection } from './runtimeFlow';
import type { RuntimeActivitySegment } from './runtimeLayer';

function segmento(patch: Partial<RuntimeActivitySegment> = {}): RuntimeActivitySegment {
  return {
    from: { x: 0, y: 0, z: 0 },
    to: { x: 3, y: 4, z: 0 },
    source: 'runtime:model:groq/qwen3',
    target: 'runtime:event:abc',
    kind: 'edge',
    ...patch,
  };
}

describe('a luz corre para onde a informação vai', () => {
  it('do modelo para o evento que ele produziu', () => {
    expect(flowDirection(segmento())).toBe('forward');
  });

  it('de um evento para o que o sucede na trilha', () => {
    expect(
      flowDirection(
        segmento({ source: 'runtime:event:abc', target: 'runtime:event:def' }),
      ),
    ).toBe('forward');
  });

  it('do provedor para o modelo, e não o contrário', () => {
    // A aresta é gravada como `modelo → provedor` porque é vínculo. Quem atende é o
    // provedor; quem trabalha é o modelo.
    expect(
      flowDirection(
        segmento({
          source: 'runtime:model:groq/qwen3',
          target: 'runtime:provider:groq',
        }),
      ),
    ).toBe('reverse');
  });

  it('a haste corre para a representação viva, que é a que executa', () => {
    expect(
      flowDirection(
        segmento({
          kind: 'tether',
          source: 'runtime:model:groq/qwen3',
          target: 'op/model/groq/qwen3',
        }),
      ),
    ).toBe('reverse');
  });
});

describe('a direção é assada no atributo', () => {
  it('a origem do fluxo recebe zero, e o destino, o comprimento em mundo', () => {
    const { position, flow, progress } = flowAttributes([segmento()]);
    expect([...position]).toEqual([0, 0, 0, 3, 4, 0]);
    // 3-4-5: o comprimento é do mundo, não normalizado.
    expect([...flow]).toEqual([0, 5]);
    expect([...progress]).toEqual([0, 1]);
  });

  it('invertido, o zero troca de ponta sem mover a geometria', () => {
    const invertido = segmento({
      source: 'runtime:model:groq/qwen3',
      target: 'runtime:provider:groq',
    });
    const { position, flow, progress } = flowAttributes([invertido]);
    expect([...position]).toEqual([0, 0, 0, 3, 4, 0]);
    expect([...flow]).toEqual([5, 0]);
    expect([...progress]).toEqual([1, 0]);
  });

  it('a velocidade é do mundo: dois segmentos de comprimentos diferentes não são normalizados', () => {
    const curto = segmento({ to: { x: 1, y: 0, z: 0 } });
    const longo = segmento({ to: { x: 40, y: 0, z: 0 } });
    const { flow } = flowAttributes([curto, longo]);
    expect(flow[1]).toBe(1);
    expect(flow[3]).toBe(40);
  });

  it('sem segmento nenhum, os buffers nascem vazios em vez de indefinidos', () => {
    const vazio = flowAttributes([]);
    expect(vazio.position).toHaveLength(0);
    expect(vazio.flow).toHaveLength(0);
    expect(vazio.progress).toHaveLength(0);
  });
});
