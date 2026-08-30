import { describe, expect, it } from 'vitest';

import { emphasisFor, focusOf, type EmphasisState } from './emphasis';

const VAZIO: EmphasisState = {
  selected: null,
  hovered: null,
  linkedEntity: null,
  neighbours: undefined,
};

function estado(parcial: Partial<EmphasisState>): EmphasisState {
  return { ...VAZIO, ...parcial };
}

describe('sem nada escolhido, ninguém se destaca', () => {
  it('cena em repouso é toda normal', () => {
    expect(emphasisFor('a', VAZIO)).toBe('normal');
  });

  it('o sobrevoo destaca sem apagar o resto', () => {
    const s = estado({ hovered: 'a' });
    expect(emphasisFor('a', s)).toBe('highlighted');
    // Apagar a cena inteira por passar o mouse seria ruído, não resposta.
    expect(emphasisFor('b', s)).toBe('normal');
  });
});

describe('a seleção do corpus manda', () => {
  const s = estado({ selected: 'a', neighbours: new Set(['b']) });

  it('a selecionada acende, a vizinha acompanha, o resto apaga', () => {
    expect(emphasisFor('a', s)).toBe('highlighted');
    expect(emphasisFor('b', s)).toBe('highlighted');
    expect(emphasisFor('c', s)).toBe('dimmed');
  });

  it('o sobrevoo não rouba o destaque de quem está selecionado', () => {
    const comHover = estado({ ...s, hovered: 'c' });
    expect(emphasisFor('c', comHover)).toBe('dimmed');
  });
});

describe('o vínculo vivo acende quando o corpus não escolheu', () => {
  it('a outra ponta da haste acende e o resto apaga', () => {
    const s = estado({ linkedEntity: 'x' });
    expect(emphasisFor('x', s)).toBe('highlighted');
    expect(emphasisFor('y', s)).toBe('dimmed');
  });

  it('o sobrevoo não sobrepõe o vínculo', () => {
    // Este é o defeito que a fonte única resolve: mover o mouse apagava o vínculo,
    // porque a outra função varria a cena depois e não sabia dele.
    const s = estado({ linkedEntity: 'x', hovered: 'y' });
    expect(emphasisFor('x', s)).toBe('highlighted');
    expect(emphasisFor('y', s)).toBe('dimmed');
  });
});

describe('a precedência é fixa, e não depende da ordem das chamadas', () => {
  it('com as duas ativas, quem acende é a seleção do corpus', () => {
    const s = estado({ selected: 'a', linkedEntity: 'x' });
    expect(focusOf(s)).toBe('a');
    expect(emphasisFor('a', s)).toBe('highlighted');
    expect(emphasisFor('x', s)).toBe('dimmed');
  });

  it('a vizinhança acompanha a seleção, nunca o vínculo', () => {
    // A vizinhança de uma nota apontada por um evento não é o que o evento diz.
    const s = estado({ linkedEntity: 'x', neighbours: new Set(['v']) });
    expect(emphasisFor('v', s)).toBe('dimmed');
  });

  it('a mesma entrada dá a mesma saída, chamada quantas vezes for', () => {
    const s = estado({ selected: 'a', hovered: 'b', linkedEntity: 'x' });
    const primeira = ['a', 'b', 'x', 'z'].map((id) => emphasisFor(id, s));
    const segunda = ['a', 'b', 'x', 'z'].map((id) => emphasisFor(id, s));
    expect(segunda).toEqual(primeira);
  });
});
