import { describe, expect, it } from 'vitest';

import { isEditableTarget, selectionKeyboardAction } from './keyboardTarget';

/** Alvo estrutural: o predicado não depende de DOM real, e o teste também não. */
function alvo(tagName: string, contentEditable = false): EventTarget {
  return { tagName, isContentEditable: contentEditable } as unknown as EventTarget;
}

describe('a tecla digitada num campo pertence ao campo', () => {
  it('reconhece os três elementos que aceitam digitação', () => {
    for (const etiqueta of ['INPUT', 'TEXTAREA', 'SELECT']) {
      expect(isEditableTarget(alvo(etiqueta))).toBe(true);
    }
  });

  it('reconhece contentEditable em qualquer elemento', () => {
    expect(isEditableTarget(alvo('DIV', true))).toBe(true);
    expect(isEditableTarget(alvo('DIV'))).toBe(false);
  });

  it('a etiqueta em minúsculas continua valendo', () => {
    // `tagName` vem maiúsculo em HTML e minúsculo em XHTML/SVG. Comparar sem
    // normalizar deixaria o atalho engolir a tecla exatamente no caso raro.
    expect(isEditableTarget(alvo('input'))).toBe(true);
  });

  it('a cena continua recebendo o que não é campo', () => {
    expect(isEditableTarget(alvo('CANVAS'))).toBe(false);
    expect(isEditableTarget(alvo('BUTTON'))).toBe(false);
    expect(isEditableTarget(null)).toBe(false);
  });

  it('alvo sem tagName não quebra o predicado', () => {
    // `window` e `document` são alvos válidos de evento e não têm `tagName`.
    expect(isEditableTarget({} as EventTarget)).toBe(false);
  });
});

describe('Enter e Escape obedecem à seleção visível', () => {
  it('Escape recolhe tanto o corpus quanto a camada viva', () => {
    expect(selectionKeyboardAction('Escape', true, false)).toBe('clear-selection');
    expect(selectionKeyboardAction('Escape', false, true)).toBe('clear-selection');
    expect(selectionKeyboardAction('Escape', true, true)).toBe('clear-selection');
  });

  it('Escape sem seleção não abre menu nenhum', () => {
    expect(selectionKeyboardAction('Escape', false, false)).toBeNull();
  });

  it('Enter recentra a seleção no domínio certo', () => {
    expect(selectionKeyboardAction('Enter', true, false)).toBe('focus-corpus');
    expect(selectionKeyboardAction('Enter', false, true)).toBe('focus-runtime');
    expect(selectionKeyboardAction('Enter', true, true)).toBe('focus-runtime');
  });

  it('não inventa ação sem seleção nem para outra tecla', () => {
    expect(selectionKeyboardAction('Enter', false, false)).toBeNull();
    expect(selectionKeyboardAction('g', true, true)).toBeNull();
  });
});
