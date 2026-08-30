// A arbitragem da roda, prendida nas duas condições que ela precisa exigir juntas.
//
// Os dois primeiros casos reprovavam antes deste incremento: a regra anterior olhava só
// para "existe painel selecionado com rolagem", e por isso consumia a roda com o ponteiro
// em qualquer canto da tela e a retinha até o fim do conteúdo.

import { describe, expect, it } from 'vitest';

import { wheelOwner, type WheelArbitration } from './wheelTarget';

/** Um painel aberto no meio de um documento longo, com o ponteiro sobre ele. */
const NO_MEIO: WheelArbitration = {
  deltaY: 100,
  scrollOffset: 50,
  maxScroll: 200,
  pointerOverPanel: true,
};

describe('de quem é a roda', () => {
  it('é da câmera quando o ponteiro não está sobre a placa aberta', () => {
    // O painel continua aberto, continua tendo o que rolar, e mesmo assim não retém a
    // roda: quem gira longe dele está falando com o mundo.
    expect(wheelOwner({ ...NO_MEIO, pointerOverPanel: false })).toBe('camera');
  });

  // As seis bordas, numa tabela só: três posições no conteúdo × duas direções de giro.
  // Juntas elas são a regra inteira, e separá-las em casos soltos escondia justamente o
  // par que faltava — a regra antiga só soltava a roda quando não havia mais nada a
  // revelar em **direção nenhuma**, e por isso cada ponta prendia um sentido a mais.
  it.each([
    ['topo', 'para baixo', 'panel', 0, 100],
    ['topo', 'para cima', 'camera', 0, -100],
    ['meio', 'para baixo', 'panel', 50, 100],
    ['meio', 'para cima', 'panel', 50, -100],
    ['fundo', 'para baixo', 'camera', 200, 100],
    ['fundo', 'para cima', 'panel', 200, -100],
  ] as const)('no %s, girando %s, a roda é do %s', (_onde, _sentido, dono, scrollOffset, deltaY) => {
    expect(wheelOwner({ ...NO_MEIO, scrollOffset, deltaY })).toBe(dono);
  });

  it('é da câmera quando o conteúdo cabe inteiro na placa', () => {
    expect(wheelOwner({ ...NO_MEIO, scrollOffset: 0, maxScroll: 0 })).toBe('camera');
  });

  it('não inventa movimento a partir de giro nulo', () => {
    expect(wheelOwner({ ...NO_MEIO, deltaY: 0 })).toBe('camera');
  });

  it('não guarda estado entre eventos', () => {
    // Nenhuma carência, nenhum limiar acumulado: a mesma entrada dá a mesma saída, e
    // alternar entre painel e câmera não custa evento nenhum de transição.
    const sequencia: WheelArbitration[] = [
      { ...NO_MEIO, pointerOverPanel: true },
      { ...NO_MEIO, pointerOverPanel: false },
      { ...NO_MEIO, pointerOverPanel: true },
    ];
    expect(sequencia.map(wheelOwner)).toEqual(['panel', 'camera', 'panel']);
  });
});
