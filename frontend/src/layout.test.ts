import { describe, expect, it } from 'vitest';

import { projectionFixture } from './fixture';
import { extentOf, hash32, layoutAtlas, ringRadius } from './layout';
import { mergePositions } from './layoutStore';
import { describePanel } from './panels';
import { panelSweepRadius, panelWorldExtent } from './panelScale';
import { Z_LAYER } from './sizing';

const projecao = projectionFixture();

function distancia(a: { x: number; y: number }, b: { x: number; y: number }): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function distancia3(
  a: { x: number; y: number; z: number },
  b: { x: number; y: number; z: number },
): number {
  return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
}

const raioVarrido = (node: (typeof projecao.nodes)[number]): number =>
  panelSweepRadius(describePanel(node));

describe('layoutAtlas', () => {
  it('posiciona toda entidade da projeção', () => {
    const posicoes = layoutAtlas(projecao);
    expect(posicoes.size).toBe(projecao.nodes.length);
    for (const node of projecao.nodes) {
      const p = posicoes.get(node.id)!;
      expect(Number.isFinite(p.x) && Number.isFinite(p.y) && Number.isFinite(p.z)).toBe(true);
    }
  });

  it('é determinístico: mesma projeção, mesmas posições', () => {
    const a = layoutAtlas(projecao);
    const b = layoutAtlas(projecao);
    for (const [id, posicao] of a) expect(posicao).toEqual(b.get(id));
  });

  it('a calota ocupa de 15% a 25% do raio estrutural', () => {
    // A faixa do dossiê, medida contra o raio das âncoras — que é quantizado e por
    // isso estável. Medir contra a extensão total faria a profundidade mudar a cada
    // nota nova, movendo todos os MOCs.
    const posicoes = layoutAtlas(projecao);
    const perifericos = projecao.nodes.filter(
      (n) => n.kind === 'moc' && n.domainId !== 'raiz',
    );
    const raio = Math.hypot(...['x', 'y', 'z'].map((eixo) => {
      const p = posicoes.get(perifericos[0]!.id)! as unknown as Record<string, number>;
      return p[eixo]!;
    }));
    const alturas = perifericos.map((m) => Math.abs(posicoes.get(m.id)!.z));
    const proporcao = Math.max(...alturas) / raio;
    expect(proporcao).toBeGreaterThan(0.15);
    expect(proporcao).toBeLessThan(0.25);
  });

  it('a profundidade total nunca vira volume esférico', () => {
    const { radius, depth } = extentOf(layoutAtlas(projecao));
    expect(depth / radius).toBeLessThan(0.35);
  });

  it('coloca o MOC de raiz no centro e os de domínio numa calota ao redor', () => {
    const posicoes = layoutAtlas(projecao);
    const raiz = posicoes.get('Índice')!;
    expect(Math.hypot(raiz.x, raiz.y)).toBeLessThan(1e-9);
    expect(raiz.z).toBeCloseTo(Z_LAYER.moc, 6);

    const perifericos = projecao.nodes.filter(
      (node) => node.kind === 'moc' && node.domainId !== 'raiz',
    );
    const alturas: number[] = [];
    for (const moc of perifericos) {
      const p = posicoes.get(moc.id)!;
      expect(Math.hypot(p.x, p.y)).toBeGreaterThan(30);
      alturas.push(p.z);
    }
    // Alturas distintas: é calota, não anel plano.
    expect(new Set(alturas.map((z) => z.toFixed(4))).size).toBe(alturas.length);
  });

  it('aproxima cada nota da própria âncora mais que de outra qualquer', () => {
    const posicoes = layoutAtlas(projecao);
    const ancorada = projecao.nodes.filter((node) => node.anchorMocId !== null);
    expect(ancorada.length).toBeGreaterThan(0);
    for (const node of ancorada) {
      const p = posicoes.get(node.id)!;
      const daPropria = distancia(p, posicoes.get(node.anchorMocId!)!);
      const outras = projecao.nodes
        .filter((outro) => outro.kind === 'moc' && outro.id !== node.anchorMocId)
        .map((outro) => distancia(p, posicoes.get(outro.id)!));
      expect(daPropria).toBeLessThan(Math.min(...outras));
    }
  });

  it('não sobrepõe entidades do mesmo território', () => {
    const posicoes = layoutAtlas(projecao);
    const porAncora = new Map<string, typeof projecao.nodes>();
    for (const node of projecao.nodes) {
      if (!node.anchorMocId) continue;
      porAncora.set(node.anchorMocId, [...(porAncora.get(node.anchorMocId) ?? []), node]);
    }
    for (const membros of porAncora.values()) {
      for (let i = 0; i < membros.length; i += 1) {
        for (let j = i + 1; j < membros.length; j += 1) {
          const a = membros[i]!;
          const b = membros[j]!;
          // Medido na placa, e não mais em `footprint()`, que derivava do raio das
          // esferas que a ADR-002 tirou de cena: para uma nota ele valia 2,0 unidades
          // contra 14,4 de diagonal de placa, e prendia uma folga sete vezes menor que a
          // real — passava sem poder reprovar nada.
          const minima = raioVarrido(a) + raioVarrido(b);
          expect(distancia3(posicoes.get(a.id)!, posicoes.get(b.id)!)).toBeGreaterThanOrEqual(
            minima,
          );
        }
      }
    }
  });
});

describe('estabilidade do mapa mental', () => {
  it('nota nova não desloca nenhum MOC', () => {
    const antes = layoutAtlas(projecao);
    const depois = layoutAtlas(projectionFixture(['Física/Nova']));
    for (const moc of projecao.nodes.filter((node) => node.kind === 'moc')) {
      expect(depois.get(moc.id)).toEqual(antes.get(moc.id));
    }
  });

  // A promessa era deslocamento **zero** em território vizinho, e ela deixou de ser
  // verdadeira quando a separação global entrou: uma nota nova que cai em cima de uma
  // placa de outro domínio empurra essa placa, porque deixá-la coberta é pior. O que
  // continua valendo — e é o que sustenta o mapa mental — é a ordem de grandeza: o
  // vizinho cede o quanto a sobreposição exige, e não recomeça em outro lugar.
  it('nota nova mexe no vizinho no máximo o que a sobreposição exigir', () => {
    const antes = layoutAtlas(projecao);
    const depois = layoutAtlas(projectionFixture(['Física/Nova']));
    const forasteiros = ['Dados/Shannon', 'Metodologia/Política', 'Computação/Sem âncora'];
    // Uma placa de nota tem 11,5 de largura nesta escala; o teto é ela inteira.
    for (const id of forasteiros) {
      const a = antes.get(id)!;
      const b = depois.get(id)!;
      expect(Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z)).toBeLessThan(12);
    }
  });

  it('nenhuma placa cobre outra, em qualquer território', () => {
    const posicoes = layoutAtlas(projecao);
    const raio = (node: (typeof projecao.nodes)[number]): number => {
      const e = panelWorldExtent(describePanel(node));
      return Math.hypot(e.width, e.height) / 2;
    };
    for (let i = 0; i < projecao.nodes.length; i += 1) {
      for (let j = i + 1; j < projecao.nodes.length; j += 1) {
        const a = projecao.nodes[i]!;
        const b = projecao.nodes[j]!;
        const pa = posicoes.get(a.id)!;
        const pb = posicoes.get(b.id)!;
        const separacao = Math.hypot(pa.x - pb.x, pa.y - pb.y, pa.z - pb.z);
        expect(separacao).toBeGreaterThanOrEqual(raio(a) + raio(b));
      }
    }
  });

  it('posições anteriores prevalecem sobre o recálculo', () => {
    const antes = layoutAtlas(projecao);
    const fixado = { x: 1, y: 2, z: 3 };
    antes.set('Física/Entropia', fixado);
    const depois = layoutAtlas(projectionFixture(['Física/Nova']), {}, antes);
    expect(depois.get('Física/Entropia')).toEqual(fixado);
    expect(depois.has('Física/Nova')).toBe(true);
  });

  it('preserva todas as posições ao atravessar um degrau do raio', () => {
    // A fixture base tem 11 nós. Com 20 extras fica imediatamente antes do degrau
    // de 32; a nota seguinte força outro raio calculado, mas não pode mover o mapa
    // que já foi persistido.
    const extras = Array.from({ length: 20 }, (_, index) => `Física/Extra ${index}`);
    const antesProjection = projectionFixture(extras);
    const depoisProjection = projectionFixture([...extras, 'Física/Nova no degrau']);
    expect(antesProjection.nodes.length).toBe(31);
    expect(depoisProjection.nodes.length).toBe(32);
    expect(ringRadius(antesProjection.nodes.length, 64)).not.toBe(
      ringRadius(depoisProjection.nodes.length, 64),
    );

    const antes = layoutAtlas(antesProjection);
    const { positions: depois } = mergePositions(layoutAtlas(depoisProjection), antes);
    for (const node of antesProjection.nodes) {
      expect(depois.get(node.id)).toEqual(antes.get(node.id));
    }

    const nova = depois.get('Física/Nova no degrau')!;
    const ancora = antes.get('Física/MOC — Física')!;
    const daAncora = Math.hypot(nova.x - ancora.x, nova.y - ancora.y, nova.z - ancora.z);
    const deOutras = antesProjection.nodes
      .filter((node) => node.kind === 'moc' && node.id !== 'Física/MOC — Física')
      .map((node) => {
        const p = antes.get(node.id)!;
        return Math.hypot(nova.x - p.x, nova.y - p.y, nova.z - p.z);
      });
    expect(daAncora).toBeLessThan(Math.min(...deOutras));
  });

  it('remove do resultado uma entidade ausente sem deslocar as restantes', () => {
    const comTemporaria = projectionFixture(['Física/Temporária']);
    const antes = layoutAtlas(comTemporaria);
    const semTemporaria = projectionFixture();

    const { positions: depois } = mergePositions(layoutAtlas(semTemporaria), antes);

    expect(depois.has('Física/Temporária')).toBe(false);
    for (const node of semTemporaria.nodes) {
      expect(depois.get(node.id)).toEqual(antes.get(node.id));
    }
  });

  it('o anel só cresce por degrau, não a cada nota', () => {
    const base = 64;
    expect(ringRadius(80, base)).toBe(ringRadius(81, base));
    expect(ringRadius(95, base)).toBeLessThan(ringRadius(96, base));
  });
});

describe('hash32', () => {
  it('é estável e fica em [0, 1)', () => {
    const valor = hash32('Física/Entropia', 7);
    expect(hash32('Física/Entropia', 7)).toBe(valor);
    expect(valor).toBeGreaterThanOrEqual(0);
    expect(valor).toBeLessThan(1);
  });

  it('separa entradas próximas', () => {
    expect(hash32('Nota A')).not.toBe(hash32('Nota B'));
  });
});
