// A cor do provedor é a da marca, e ela não pode virar a cor de outra coisa.

import { describe, expect, it } from 'vitest';

import { DOMAIN_TOKENS, PROVIDER_TOKENS, providerToken, tokenColor } from './palette';

/** Distância perceptual aproximada entre dois pontos OKLCH, no plano de croma. */
function distancia(a: { l: number; c: number; h: number }, b: typeof a): number {
  const rad = (graus: number): number => (graus * Math.PI) / 180;
  const ax = a.c * Math.cos(rad(a.h));
  const ay = a.c * Math.sin(rad(a.h));
  const bx = b.c * Math.cos(rad(b.h));
  const by = b.c * Math.sin(rad(b.h));
  return Math.hypot(a.l - b.l, ax - bx, ay - by);
}

describe('a cor do provedor', () => {
  it('resolve pelo nome, sem diferenciar caixa, e nunca inventa marca', () => {
    expect(providerToken('groq')).toBe('P:groq');
    expect(providerToken('NVIDIA')).toBe('P:nvidia');
    expect(providerToken('provedor-que-nao-existe')).toBeNull();
    expect(providerToken(undefined)).toBeNull();
  });

  it('carrega o matiz da marca dentro da luminosidade da cena', () => {
    // Os matizes vêm dos hex oficiais medidos em OKLCH; o que a cena impõe é a faixa
    // de luminosidade, que é o que mantém a placa legível sobre o fundo profundo.
    expect(tokenColor('P:groq').h).toBeCloseTo(32, 0);
    expect(tokenColor('P:google').h).toBeCloseTo(260, 0);
    expect(tokenColor('P:nvidia').h).toBeCloseTo(131, 0);
    for (const token of Object.keys(PROVIDER_TOKENS)) {
      const cor = tokenColor(token);
      expect(cor.l).toBeGreaterThanOrEqual(0.72);
      expect(cor.l).toBeLessThanOrEqual(0.79);
    }
  });

  it('separa a OpenRouter do Google pelo croma, que é o que as marcas afirmam', () => {
    // As duas medem matiz quase igual — 257 e 260. Levar a OpenRouter ao croma da cena
    // as tornaria indistinguíveis, e ainda inventaria uma saturação que o slate dela
    // não tem. A marca de baixo croma continua de baixo croma.
    const openrouter = tokenColor('P:openrouter');
    const google = tokenColor('P:google');
    expect(Math.abs(openrouter.h - google.h)).toBeLessThan(10);
    expect(openrouter.c).toBeLessThan(google.c / 2);
    expect(distancia(openrouter, google)).toBeGreaterThan(0.06);
  });

  it('fica fora da tabela de domínios, que tem gate de distância próprio', () => {
    for (const token of Object.keys(PROVIDER_TOKENS)) {
      expect(token in DOMAIN_TOKENS).toBe(false);
    }
  });

  it('token desconhecido continua caindo no recuo, sem quebrar a cena', () => {
    expect(tokenColor('P:inexistente')).toEqual(tokenColor('token-que-nao-existe'));
  });
});
