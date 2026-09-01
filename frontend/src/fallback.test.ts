import { describe, expect, it, vi } from 'vitest';

import { carregarCorpoTextual, referenciaDocumental } from './fallback';
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
