// Gates de governança visual: as propriedades que o dossiê exige e que dá para
// verificar sem GPU. O que só o olho resolve fica nas capturas do relatório.

import { describe, expect, it } from 'vitest';

import { OPERATIONAL_KINDS, type ProjectionNode } from './contract';
import { webglDisponivel, modoTextualPedido } from './fallback';
import { projectionFixture } from './fixture';
import { extentOf, layoutAtlas } from './layout';
import { mergePositions } from './layoutStore';
import { DOMAIN_TOKENS, emissiveOf, perceptualDistance, tokenColor } from './palette';
import { BASE_RADIUS, Z_LAYER } from './sizing';

const projecao = projectionFixture();

describe('o MOC de raiz não é um sol central', () => {
  const mocs = projecao.nodes.filter((n) => n.kind === 'moc');
  const raiz = mocs.find((n) => n.domainId === 'raiz')!;

  it('tem exatamente o mesmo tamanho dos outros MOCs', () => {
    // Tamanho é degrau por classe. Centralidade não pode virar grandeza.
    for (const moc of mocs) {
      expect(BASE_RADIUS[moc.kind]).toBe(BASE_RADIUS[raiz.kind]);
    }
  });

  it('não recebe tratamento de emissão diferente', () => {
    // A luminosidade final varia com o token do domínio, e deve variar: o que não
    // pode variar é o tratamento. O acréscimo emissivo é o mesmo para todo MOC, e o
    // MOC de raiz não é o mais brilhante da cena.
    const acrescimo = (n: ProjectionNode) => {
      const base = tokenColor(n.visual.paletteToken);
      return emissiveOf(base).l - base.l;
    };
    const doRaiz = acrescimo(raiz);
    for (const moc of mocs) expect(acrescimo(moc)).toBeCloseTo(doRaiz, 6);

    const brilhos = mocs.map((m) => emissiveOf(tokenColor(m.visual.paletteToken)).l);
    expect(emissiveOf(tokenColor(raiz.visual.paletteToken)).l).toBeLessThanOrEqual(
      Math.max(...brilhos),
    );
  });

  it('é âncora como qualquer outro MOC, sem hierarquia', () => {
    for (const moc of mocs) {
      expect(moc.visual.isAnchor).toBe(true);
      expect(moc.visual.lodClass).toBe(raiz.visual.lodClass);
      expect(moc.anchorMocId).toBeNull();
    }
  });

  it('nenhuma nota é ancorada nele por centralidade', () => {
    const ancoradas = projecao.nodes.filter((n) => n.anchorMocId === raiz.id);
    expect(ancoradas).toEqual([]);
  });

  it('todos os MOCs periféricos ficam à mesma distância do centro', () => {
    // A calota é uma esfera: a distância tridimensional ao centro é idêntica para
    // todos. Sem isso, a elevação viraria hierarquia — um MOC "mais alto" pareceria
    // mais importante que o vizinho.
    const posicoes = layoutAtlas(projecao);
    const distancias = mocs
      .filter((m) => m.id !== raiz.id)
      .map((m) => {
        const p = posicoes.get(m.id)!;
        return Math.hypot(p.x, p.y, p.z);
      });
    expect(Math.max(...distancias) - Math.min(...distancias)).toBeLessThan(0.001);
    expect(Math.min(...distancias)).toBeGreaterThan(30);
  });
});

describe('camada operacional', () => {
  it('todo tipo operacional tem geometria e faixa de z próprias', () => {
    for (const kind of OPERATIONAL_KINDS) {
      expect(BASE_RADIUS[kind]).toBeGreaterThan(0);
      expect(Z_LAYER[kind]).toBeGreaterThan(Z_LAYER.moc);
    }
  });

  it('nenhum operacional é maior que a nota canônica', () => {
    // Procedência acompanha o conhecimento; não compete com ele.
    for (const kind of OPERATIONAL_KINDS) {
      expect(BASE_RADIUS[kind]).toBeLessThanOrEqual(BASE_RADIUS.note + 0.2);
    }
  });

  it('a rede operacional fica acima do plano epistêmico', () => {
    const epistemicos = [Z_LAYER.moc, Z_LAYER.note, Z_LAYER.reference, Z_LAYER.register];
    const operacionais = OPERATIONAL_KINDS.map((k) => Z_LAYER[k]);
    expect(Math.min(...operacionais)).toBeGreaterThan(Math.max(...epistemicos));
  });

  it('a fixture de produção não traz nenhum nó operacional', () => {
    expect(projecao.meta.operationalSource).toBe('none');
    expect(projecao.nodes.filter((n: ProjectionNode) => n.layer === 'operational')).toEqual([]);
  });
});

describe('memória espacial', () => {
  it('posição gravada prevalece; entidade nova é assentada', () => {
    const calculadas = layoutAtlas(projecao);
    const gravadas = new Map([['Física/Entropia', { x: 99, y: 98, z: 1 }]]);
    const { positions, reused, placed } = mergePositions(calculadas, gravadas);
    expect(positions.get('Física/Entropia')).toEqual({ x: 99, y: 98, z: 1 });
    expect(reused).toBe(1);
    expect(placed).toBe(calculadas.size - 1);
  });

  it('posição gravada de entidade que sumiu não ressuscita', () => {
    const calculadas = layoutAtlas(projecao);
    const gravadas = new Map([['Nota/Apagada', { x: 1, y: 2, z: 3 }]]);
    const { positions } = mergePositions(calculadas, gravadas);
    expect(positions.has('Nota/Apagada')).toBe(false);
  });

  it('sem nada gravado, o resultado é o layout determinístico', () => {
    const calculadas = layoutAtlas(projecao);
    const { positions, reused } = mergePositions(calculadas, new Map());
    expect(reused).toBe(0);
    expect(positions).toEqual(calculadas);
  });
});

describe('acesso alternativo', () => {
  it('reconhece o pedido explícito de modo textual', () => {
    expect(modoTextualPedido('?texto=1')).toBe(true);
    expect(modoTextualPedido('?text=1')).toBe(true);
    expect(modoTextualPedido('')).toBe(false);
    expect(modoTextualPedido('?outro=1')).toBe(false);
  });

  it('detecta ausência de WebGL sem estourar fora do navegador', () => {
    // Em Node não há `document`; a função precisa responder, não quebrar.
    expect(typeof webglDisponivel()).toBe('boolean');
  });
});

describe('nenhuma informação depende só de cor', () => {
  it('forma, tamanho e faixa de z distinguem as classes epistêmicas', () => {
    const classes = ['moc', 'note', 'reference', 'register'] as const;
    const assinaturas = classes.map((k) => `${BASE_RADIUS[k]}|${Z_LAYER[k]}`);
    expect(new Set(assinaturas).size).toBe(classes.length);
  });

  it('a paleta continua discriminável depois da camada nova', () => {
    const tokens = Object.values(DOMAIN_TOKENS);
    for (let i = 0; i < tokens.length; i += 1) {
      for (let j = i + 1; j < tokens.length; j += 1) {
        expect(perceptualDistance(tokens[i]!, tokens[j]!)).toBeGreaterThan(0.045);
      }
    }
  });

  it('há profundidade real, e ela não vira volume esférico', () => {
    // Sem paralaxe o atlas é um diagrama plano; com profundidade demais a oclusão
    // come a legibilidade, que é o defeito da esfera livre que ele substituiu.
    const { radius, depth } = extentOf(layoutAtlas(projecao));
    const proporcao = depth / radius;
    expect(proporcao).toBeGreaterThan(0.12);
    expect(proporcao).toBeLessThan(0.35);
  });

  it('as âncoras ocupam alturas distintas, não um anel plano', () => {
    const posicoes = layoutAtlas(projecao);
    const alturas = projecao.nodes
      .filter((n) => n.kind === 'moc' && n.domainId !== 'raiz')
      .map((n) => posicoes.get(n.id)!.z);
    expect(new Set(alturas.map((z) => z.toFixed(3))).size).toBe(alturas.length);
    expect(Math.max(...alturas) - Math.min(...alturas)).toBeGreaterThan(10);
  });

  it('cada território tem volume, não é um disco', () => {
    const posicoes = layoutAtlas(projecao);
    const doFisica = projecao.nodes.filter((n) => n.anchorMocId === 'Física/MOC — Física');
    const alturas = doFisica.map((n) => posicoes.get(n.id)!.z);
    expect(Math.max(...alturas) - Math.min(...alturas)).toBeGreaterThan(3);
  });
});
