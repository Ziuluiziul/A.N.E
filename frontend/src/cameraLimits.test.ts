import { describe, expect, it } from 'vitest';

import {
  FOLGA_DE_APROXIMACAO,
  LIMITE_DE_APROXIMACAO_MINIMO,
  alvoCabeNaJanela,
  distanciaMinimaDaOrbita,
} from './cameraLimits';

describe('distância mínima da órbita', () => {
  it('um MOC expandido cabe na janela no limite, e 12 não bastava', () => {
    // Números da auditoria F-01: MOC 4,00 × 2,25 × escala 3,2 × expansão 2,2.
    const alcance = Math.max(4.0 * 3.2 * 2.2, 2.25 * 3.2 * 2.2);
    const janela = { width: 1600, height: 900, fovDeg: 38 };
    const limite = distanciaMinimaDaOrbita({ alcance, ...janela });

    expect(alcance).toBeCloseTo(28.16, 2);
    expect(limite).toBeGreaterThan(LIMITE_DE_APROXIMACAO_MINIMO);
    expect(
      alvoCabeNaJanela({ alcance, distancia: LIMITE_DE_APROXIMACAO_MINIMO, ...janela }),
    ).toBe(false);
    expect(alvoCabeNaJanela({ alcance, distancia: limite, ...janela })).toBe(true);
    expect(alvoCabeNaJanela({ alcance, distancia: limite / FOLGA_DE_APROXIMACAO, ...janela })).toBe(
      true,
    );
  });

  it('a lente atual de 55° também recusa o piso 12 para o mesmo alvo', () => {
    const alcance = 28.16;
    const janela = { width: 1440, height: 1000, fovDeg: 55 };
    const limite = distanciaMinimaDaOrbita({ alcance, ...janela });
    expect(limite).toBeGreaterThan(LIMITE_DE_APROXIMACAO_MINIMO);
    expect(alvoCabeNaJanela({ alcance, distancia: limite, ...janela })).toBe(true);
  });

  it('alvo minúsculo não desce abaixo do piso', () => {
    expect(
      distanciaMinimaDaOrbita({
        alcance: 0.4,
        fovDeg: 55,
        width: 1280,
        height: 720,
      }),
    ).toBe(LIMITE_DE_APROXIMACAO_MINIMO);
  });

  it('janela ou alcance inválidos não colapsam a câmera', () => {
    expect(
      distanciaMinimaDaOrbita({ alcance: 0, fovDeg: 55, width: 1280, height: 720 }),
    ).toBe(LIMITE_DE_APROXIMACAO_MINIMO);
    expect(
      distanciaMinimaDaOrbita({ alcance: 20, fovDeg: 0, width: 1280, height: 720 }),
    ).toBe(LIMITE_DE_APROXIMACAO_MINIMO);
  });
});
