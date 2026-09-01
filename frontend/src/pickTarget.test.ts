import { describe, expect, it } from 'vitest';

import { escolherAlvoDoClique } from './pickTarget';

describe('escolherAlvoDoClique', () => {
  it('o painel vivo no anel da nota fica com o clique', () => {
    expect(
      escolherAlvoDoClique(
        { entityId: 'Física/Bases Neurais da Consciência' },
        { entityId: 'op/quorum/abc/panel' },
      ),
    ).toEqual({ entityId: 'op/quorum/abc/panel', runtime: true });
  });

  it('sem painel vivo, a nota continua selecionável', () => {
    expect(escolherAlvoDoClique({ entityId: 'Índice' }, null)).toEqual({
      entityId: 'Índice',
      runtime: false,
    });
  });

  it('vazio não inventa alvo', () => {
    expect(escolherAlvoDoClique(null, null)).toBeNull();
  });
});
