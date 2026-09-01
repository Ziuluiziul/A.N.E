// Atalho e legenda são a mesma afirmação. Este teste é o que impede que divirjam.

import { describe, expect, it } from 'vitest';

import { CONTROLS, SCENE_LEGEND } from './controls3d';

describe('a legenda da cena', () => {
  it('menciona todo atalho que o teclado de fato executa', () => {
    const teclas = SCENE_LEGEND.map((item) => item.keys.toLowerCase());
    for (const controle of CONTROLS) {
      expect(teclas).toContain(controle.shortcut.toLowerCase());
    }
  });

  it('não repete gesto nem deixa ação vazia', () => {
    const teclas = SCENE_LEGEND.map((item) => item.keys.toLowerCase());
    expect(new Set(teclas).size).toBe(teclas.length);
    for (const { action } of SCENE_LEGEND) expect(action.trim().length).toBeGreaterThan(0);
  });

  it('descreve o gesto do mouse, que é como se chega a um painel', () => {
    // A pergunta de quem lê a faixa é "o que eu faço para chegar lá", e a resposta
    // principal não passa pelo teclado. Um clique escolhe; o duplo traz a câmera — e a
    // legenda precisa dizer os dois, porque essa distinção não é adivinhável.
    const teclas = SCENE_LEGEND.map((item) => item.keys);
    expect(teclas).toContain('clique');
    const duplo = SCENE_LEGEND.find((item) => item.keys.includes('duplo clique'));
    expect(duplo?.action).toMatch(/aproxim/);
    // Zoom é gesto de mouse e não aparece em `CONTROLS`; sem ele a faixa deixaria de
    // fora o movimento que mais se usa.
    expect(teclas.some((item) => item.includes('scroll'))).toBe(true);
    expect(teclas.some((item) => item.includes('pinça'))).toBe(true);
  });

  it('Escape fecha a legenda, não só a escolha', () => {
    const escape = SCENE_LEGEND.find((item) => item.keys === 'Esc');
    expect(escape?.action).toMatch(/legenda/);
    expect(escape?.action).toMatch(/escolha/);
  });

  it('menciona a busca, que o teclado de fato abre', () => {
    const teclas = SCENE_LEGEND.map((item) => item.keys);
    expect(teclas.some((item) => item.includes('Ctrl+K'))).toBe(true);
    expect(teclas.some((item) => item.includes('/'))).toBe(true);
  });
});
