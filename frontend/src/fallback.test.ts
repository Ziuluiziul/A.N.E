import { describe, expect, it, vi } from 'vitest';

import {
  atalhoDoModoTextual,
  carregarCorpoTextual,
  corpoTextualVisivel,
  referenciaDocumental,
} from './fallback';
import { node } from './fixture';

describe('referenciaDocumental', () => {
  it('usa o path da nota epistêmica', () => {
    const nota = node('Cognição/Memória', { kind: 'note', layer: 'epistemic' });
    expect(referenciaDocumental(nota)).toBe(nota.path);
  });

  it('recusa painel operacional: não há arquivo', () => {
    const painel = node('op/panel/abc', {
      kind: 'quorum-panel',
      layer: 'operational',
      path: null,
    });
    expect(referenciaDocumental(painel)).toBeNull();
  });

  it('recusa path vazio', () => {
    const oca = node('x', { kind: 'note', layer: 'epistemic', path: '' });
    expect(referenciaDocumental(oca)).toBeNull();
  });
});

describe('carregarCorpoTextual', () => {
  it('busca o markdown sob demanda e não inventa corpo operacional', async () => {
    const nota = node('Cognição/Memória', { kind: 'note', layer: 'epistemic' });
    const load = vi.fn(async (referencia: string) => `corpo de ${referencia}`);
    await expect(carregarCorpoTextual(nota, load)).resolves.toBe(`corpo de ${nota.path}`);
    expect(load).toHaveBeenCalledOnce();
    expect(load).toHaveBeenCalledWith(nota.path);

    const painel = node('op/panel/abc', {
      kind: 'quorum-panel',
      layer: 'operational',
      path: null,
    });
    await expect(carregarCorpoTextual(painel, load)).resolves.toBeNull();
    expect(load).toHaveBeenCalledOnce();
  });
});

describe('corpo textual visível', () => {
  it('resolve a marcação em vez de mostrar o Markdown cru', () => {
    const visivel = corpoTextualVisivel(
      '# Título da nota\n\n## Finalidade\n\nUm **organismo** e um [[wikilink]].\n',
      'Título da nota',
    );
    expect(visivel).not.toContain('# ');
    expect(visivel).not.toContain('**');
    expect(visivel).not.toContain('[[');
    expect(visivel).toMatch(/FINALIDADE/i);
    expect(visivel).toContain('organismo');
    expect(visivel).toContain('wikilink');
  });
});

describe('atalhos do modo textual', () => {
  const campo = { tagName: 'INPUT', isContentEditable: false } as unknown as EventTarget;

  it('barra e Ctrl+K abrem a busca fora de um campo', () => {
    expect(atalhoDoModoTextual('/', null)).toBe('focus-search');
    expect(atalhoDoModoTextual('k', null, true)).toBe('focus-search');
    expect(atalhoDoModoTextual('/', campo)).toBeNull();
  });

  it('Escape limpa a busca mesmo com o campo focado', () => {
    expect(atalhoDoModoTextual('Escape', campo)).toBe('clear-search');
    expect(atalhoDoModoTextual('Escape', null)).toBe('clear-search');
  });
});
