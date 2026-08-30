import { describe, expect, it } from 'vitest';

import { normalizar, searchIndex, searchMatches } from './searchPalette';
import type { Projection } from './contract';

function projecaoComNodes(nodes: Projection['nodes']): Projection {
  return {
    meta: {
      contractVersion: 1,
      source: 'test',
      corpusFingerprint: 'f',
      counts: { notes: nodes.length, mocs: 0, wikilinks: 0, claims: 0 },
      domains: [],
    },
    nodes,
    edges: [],
  } as unknown as Projection;
}

describe('normalizar', () => {
  it('remove acento e caixa sem tocar no resto', () => {
    expect(normalizar('Álgebra Linear')).toBe('algebra linear');
    expect(normalizar('ESTATÍSTICA')).toBe('estatistica');
  });
});

describe('searchIndex', () => {
  it('indexa somente a camada epistêmica', () => {
    const projection = projecaoComNodes([
      {
        id: 'nota',
        title: 'Memória',
        domainLabel: 'Cognição',
        kind: 'nota',
        layer: 'epistemic',
      },
      {
        id: 'painel',
        title: 'Execução 7',
        domainLabel: 'Operação',
        kind: 'operational',
        layer: 'operational',
      },
    ] as unknown as Projection['nodes']);

    const index = searchIndex(projection);

    expect(index).toHaveLength(1);
    expect(index[0]?.id).toBe('nota');
  });

  it('a chave junta título, identidade e domínio normalizados', () => {
    const projection = projecaoComNodes([
      {
        id: 'MOC — Estatística e Inferência',
        title: 'Estatística',
        domainLabel: 'Estatística',
        kind: 'moc',
        layer: 'epistemic',
      },
    ] as unknown as Projection['nodes']);

    const [entrada] = searchIndex(projection);
    expect(entrada?.chave).toContain('estatistica e inferencia');
    expect(entrada?.chave).toContain('estatistica');
  });
});

describe('searchMatches', () => {
  const index = [
    { id: 'a', title: 'Memória', domainLabel: 'Cognição', kind: 'nota', chave: 'memoria a cognicao' },
    { id: 'b', title: 'Memória de Trabalho', domainLabel: 'Cognição', kind: 'nota', chave: 'memoria de trabalho beta cognicao' },
    { id: 'c', title: 'Probabilidade', domainLabel: 'Estatística', kind: 'moc', chave: 'probabilidade c estatistica' },
  ];

  it('casa sem acento e sem caixa', () => {
    expect(searchMatches(index, 'MEMÓRIA').map((e) => e.id)).toEqual(['a', 'b']);
    expect(searchMatches(index, 'estatistica').map((e) => e.id)).toEqual(['c']);
  });

  it('devolve vazio para consulta em branco', () => {
    expect(searchMatches(index, '   ')).toEqual([]);
  });

  it('respeita o limite', () => {
    expect(searchMatches(index, 'memoria', 1).map((e) => e.id)).toEqual(['a']);
  });

  it('casa pela identidade, não só pelo título', () => {
    expect(searchMatches(index, 'beta').map((e) => e.id)).toEqual(['b']);
  });
});
