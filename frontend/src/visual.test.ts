// Paleta, LOD, arestas e contrato — a parte da apresentação que dá para verificar
// sem GPU. O que exige WebGL fica para a verificação no navegador, registrada no
// relatório do ciclo.

import { describe, expect, it } from 'vitest';

import { ContractError, assertConsistent, assertSupported } from './contract';
import { dashPath } from './edgePath';
import { EDGE_STYLES } from './edges';
import { projectionFixture } from './fixture';
import { bodyMaterial } from './geometry';
import { LOD_ORDER, levelFor, levelWithHysteresis, projectedPixels, showsLabel } from './lod';
import {
  DOMAIN_TOKENS,
  NEUTRALS,
  emissiveOf,
  hexString,
  linkColorOf,
  mixOklch,
  oklchToHex,
  perceptualDistance,
} from './palette';
import { BASE_RADIUS, Z_LAYER } from './sizing';

describe('paleta OKLCH', () => {
  it('converte para sRGB de forma determinística e dentro da faixa', () => {
    for (const token of Object.values(DOMAIN_TOKENS)) {
      const hex = oklchToHex(token);
      expect(hex).toBe(oklchToHex(token));
      expect(hex).toBeGreaterThanOrEqual(0);
      expect(hex).toBeLessThanOrEqual(0xffffff);
    }
  });

  it('reproduz os neutros do dossiê', () => {
    // Fundo carvão azulado #0B1016, e não preto puro.
    expect(hexString(NEUTRALS.backgroundDeep)).toBe('#0b1016');
    expect(hexString(NEUTRALS.textPrimary)).toBe('#edf2f9');
  });

  it('nenhum par de domínios fica perceptivelmente junto', () => {
    const tokens = Object.entries(DOMAIN_TOKENS);
    for (let i = 0; i < tokens.length; i += 1) {
      for (let j = i + 1; j < tokens.length; j += 1) {
        const [nomeA, a] = tokens[i]!;
        const [nomeB, b] = tokens[j]!;
        expect(perceptualDistance(a, b), `${nomeA} vs ${nomeB}`).toBeGreaterThan(0.045);
      }
    }
  });

  it('mantém luminosidade próxima entre domínios', () => {
    // Croma e matiz distinguem; luminosidade não, senão um domínio pareceria
    // "mais importante" que outro.
    const luminosidades = Object.values(DOMAIN_TOKENS).map((token) => token.l);
    expect(Math.max(...luminosidades) - Math.min(...luminosidades)).toBeLessThan(0.09);
  });

  it('a cor do link é mais saturada que a do corpo, e mais que a emissiva', () => {
    // O link é fino: pouco croma nele desaparece contra o fundo, e o degradê chegava
    // esbranquiçado, sem dizer quais dois domínios estava ligando.
    for (const base of Object.values(DOMAIN_TOKENS)) {
      const link = linkColorOf(base);
      expect(link.c).toBeGreaterThan(base.c);
      expect(link.c).toBeGreaterThan(emissiveOf(base).c);
      expect(link.l).toBeGreaterThan(base.l);
      expect(link.h).toBe(base.h);
      // Nem tão claro que vire branco: aí a matiz se perderia de outro jeito.
      expect(link.l).toBeLessThanOrEqual(0.92);
    }
  });

  it('a emissiva não é branco somado por cima', () => {
    const base = DOMAIN_TOKENS.D01!;
    const brilho = emissiveOf(base);
    expect(brilho.h).toBe(base.h);
    expect(brilho.l).toBeGreaterThan(base.l);
    expect(brilho.c).toBeGreaterThan(0);
  });
});

describe('mistura de cor do degradê', () => {
  it('o miolo não empalidece: mantém croma comparável ao das pontas', () => {
    // Em sRGB o meio de duas matizes distantes cai para perto do cinza, e era isso que
    // apagava o degradê do link exatamente onde ele precisa ser lido.
    const a = DOMAIN_TOKENS.D01!;
    const b = DOMAIN_TOKENS.D05!;
    const meio = mixOklch(a, b, 0.5);
    expect(meio.c).toBeGreaterThan(Math.min(a.c, b.c) * 0.9);
  });

  it('gira pelo arco curto, e não pelo lado longo', () => {
    const meio = mixOklch({ l: 0.7, c: 0.1, h: 350 }, { l: 0.7, c: 0.1, h: 10 }, 0.5);
    expect(((meio.h % 360) + 360) % 360).toBeCloseTo(0, 6);
  });

  it('as pontas são exatamente as cores dadas', () => {
    const a = DOMAIN_TOKENS.D01!;
    const b = DOMAIN_TOKENS.D03!;
    expect(mixOklch(a, b, 0)).toEqual(a);
    expect(oklchToHex(mixOklch(a, b, 1))).toBe(oklchToHex(b));
  });

  it('a fração é limitada, então nenhuma extrapolação escapa', () => {
    const a = DOMAIN_TOKENS.D01!;
    const b = DOMAIN_TOKENS.D03!;
    expect(mixOklch(a, b, 2)).toEqual(mixOklch(a, b, 1));
    expect(mixOklch(a, b, -1)).toEqual(mixOklch(a, b, 0));
  });
});

describe('tamanho por classe', () => {
  it('usa degraus discretos e o MOC não é o maior por muito', () => {
    // As quatro classes epistêmicas têm raios distintos entre si. Entre operacionais
    // é aceitável repetir: ali quem distingue é a forma, e o tamanho só diz que
    // procedência não compete com conhecimento pela atenção.
    const epistemicos = [
      BASE_RADIUS.moc,
      BASE_RADIUS.note,
      BASE_RADIUS.reference,
      BASE_RADIUS.register,
    ];
    expect(new Set(epistemicos).size).toBe(epistemicos.length);
    expect(BASE_RADIUS.moc / BASE_RADIUS.note).toBeLessThan(3);
    // Nenhum valor é contínuo: são degraus escolhidos, não uma função de métrica.
    expect(new Set(Object.values(BASE_RADIUS)).size).toBeLessThan(
      Object.keys(BASE_RADIUS).length,
    );
  });

  it('separa camadas em z sem inverter a hierarquia', () => {
    expect(Z_LAYER.moc).toBeGreaterThan(Z_LAYER.register);
    expect(Z_LAYER.note).toBe(0);
  });
});

describe('materiais com volume', () => {
  it('distingue provisório de canônico pela solidez, e nenhum deles é gaiola', () => {
    // Em 3.5-D o painel canônico deixou de ser opaco e o provisório deixou de ser
    // wireframe. A distinção continua existindo — e agora ela sobrevive em escala de
    // cinza sem que nada seja desenhado em volta do painel.
    const canonical = bodyMaterial('canonical', 'epistemic');
    const proposed = bodyMaterial('proposed', 'operational');
    const temporary = bodyMaterial('temporary', 'operational');
    expect(canonical.opacity).toBeGreaterThan(proposed.opacity);
    expect(canonical.opacity).toBeLessThan(1);
    expect(proposed.emissiveIntensity).toBeGreaterThan(canonical.emissiveIntensity);
    for (const material of [canonical, proposed, temporary]) {
      expect(material.wireframe).toBe(false);
      expect(material.transparent).toBe(true);
      expect(material.depthWrite).toBe(false);
      material.dispose();
    }
  });
});

describe('LOD', () => {
  it('mede tamanho projetado em pixels, não distância no mundo', () => {
    const perto = projectedPixels(1, 10, 45, 800);
    const longe = projectedPixels(1, 100, 45, 800);
    expect(perto).toBeGreaterThan(longe);
    // Mesma distância, janela maior: mais pixels.
    expect(projectedPixels(1, 50, 45, 1600)).toBeCloseTo(projectedPixels(1, 50, 45, 800) * 2, 6);
  });

  it('classifica pelos limiares do dossiê', () => {
    expect(levelFor(2)).toBe('distant');
    expect(levelFor(6)).toBe('structural');
    expect(levelFor(15)).toBe('identifiable');
    expect(levelFor(40)).toBe('legible');
    expect(levelFor(120)).toBe('expanded');
  });

  it('só mostra rótulo a partir de identificável', () => {
    expect(showsLabel('distant')).toBe(false);
    expect(showsLabel('structural')).toBe(false);
    expect(showsLabel('identifiable')).toBe(true);
  });

  it('a histerese impede cintilação na fronteira', () => {
    // 28 px é o limiar de "legível". Cair para 24 não deve rebaixar de imediato.
    expect(levelWithHysteresis(24, 'legible')).toBe('legible');
    // Cair bem abaixo rebaixa.
    expect(levelWithHysteresis(15, 'legible')).toBe('identifiable');
    // Subir é imediato, sem folga.
    expect(levelWithHysteresis(90, 'identifiable')).toBe('expanded');
  });

  it('sem nível anterior, usa a classificação crua', () => {
    for (const pixels of [1, 6, 15, 40, 120]) {
      expect(LOD_ORDER).toContain(levelWithHysteresis(pixels, undefined));
      expect(levelWithHysteresis(pixels, undefined)).toBe(levelFor(pixels));
    }
  });
});

describe('tipagem das arestas', () => {
  it('cada família tem assinatura visual própria sem usar cor', () => {
    // As setas de ponta saíram em 3.5-E, então a assinatura passa a ser só padrão e
    // duplicação. O invariante é o mesmo e continua sendo o que importa: distinguir
    // relação sem gastar matiz, que é do domínio.
    const assinaturas = Object.values(EDGE_STYLES).map(
      (style) => `${style.pattern.join('/')}|${style.doubled ? 'dupla' : 'simples'}`,
    );
    expect(new Set(assinaturas).size).toBe(assinaturas.length);
  });

  it('padrão vazio produz um segmento contínuo', () => {
    const pontos = dashPath([{ x: 0, y: 0, z: 0 }, { x: 10, y: 0, z: 0 }], []);
    expect(pontos).toEqual([0, 0, 0, 10, 0, 0]);
  });

  it('tracejado produz vários segmentos dentro do comprimento', () => {
    const pontos = dashPath([{ x: 0, y: 0, z: 0 }, { x: 10, y: 0, z: 0 }], [1, 1]);
    expect(pontos.length / 6).toBeGreaterThan(3);
    for (let i = 0; i < pontos.length; i += 3) {
      expect(pontos[i]!).toBeGreaterThanOrEqual(0);
      expect(pontos[i]!).toBeLessThanOrEqual(10.0001);
    }
  });

  it('traço-ponto alterna dois comprimentos de traço', () => {
    const [, , , x1] = dashPath(
      [{ x: 0, y: 0, z: 0 }, { x: 20, y: 0, z: 0 }],
      [1.6, 0.7, 0.25, 0.7],
    );
    expect(x1).toBeCloseTo(1.6, 6);
  });

  it('segmento degenerado não gera geometria', () => {
    expect(dashPath([{ x: 1, y: 1, z: 1 }, { x: 1, y: 1, z: 1 }], [])).toEqual([]);
  });

  it('comprimento não finito não gera geometria', () => {
    expect(
      dashPath([{ x: 0, y: 0, z: 0 }, { x: Number.POSITIVE_INFINITY, y: 0, z: 0 }], [1, 1]),
    ).toEqual([]);
  });

  it('caminho enorme não estoura o buffer de vértices', () => {
    const pontos = dashPath([{ x: 0, y: 0, z: 0 }, { x: 1e9, y: 0, z: 0 }], [0.9, 1.1]);
    expect(pontos.length).toBeGreaterThan(0);
    expect(pontos.length % 6).toBe(0);
    expect(pontos.length / 6).toBeLessThanOrEqual(2048);
  });

  // A curva é amostrada em pedaços, e o padrão precisa correr por cima deles como se
  // fosse um caminho só: reiniciar a fase a cada amostra transformaria traço-ponto num
  // pontilhado uniforme, e a assinatura da família deixaria de distinguir.
  it('a fase do padrão atravessa os pedaços da polilinha', () => {
    const inteiro = dashPath([{ x: 0, y: 0, z: 0 }, { x: 12, y: 0, z: 0 }], [2, 1]);
    const partido = dashPath(
      [{ x: 0, y: 0, z: 0 }, { x: 5, y: 0, z: 0 }, { x: 12, y: 0, z: 0 }],
      [2, 1],
    );
    // O corte em x=5 cai dentro de um traço, e parte esse traço em dois pares de
    // vértices; o que não pode mudar é onde o padrão liga e desliga.
    const ligados = (v: number[]): number[] =>
      v.filter((_, i) => i % 3 === 0).map((x) => Number(x.toFixed(6)));
    expect(ligados(partido)).toContain(3);
    expect(ligados(inteiro)).toContain(3);
    expect(Math.max(...ligados(partido))).toBeCloseTo(Math.max(...ligados(inteiro)), 6);
  });
});

describe('contrato', () => {
  it('aceita a major suportada', () => {
    expect(() => assertSupported(projectionFixture().meta)).not.toThrow();
  });

  it('recusa uma major que esta cena não sabe desenhar', () => {
    const meta = { ...projectionFixture().meta, contractVersion: '2.0.0' };
    expect(() => assertSupported(meta)).toThrow(ContractError);
  });

  it('recusa aresta que aponta para fora do conjunto de nós', () => {
    const projecao = projectionFixture();
    projecao.edges.push({
      source: 'Física/Entropia',
      target: 'Nota/Que não existe',
      kind: 'canonical',
      layer: 'epistemic',
      relations: ['prerequisite'],
      primaryRelation: 'prerequisite',
      weight: 1,
      matchedBy: 'id',
    });
    expect(() => assertConsistent(projecao)).toThrow(/fora do conjunto de nós/);
  });

  it('a projeção sintética é internamente consistente', () => {
    expect(() => assertConsistent(projectionFixture())).not.toThrow();
  });

});
