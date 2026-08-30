// O que a aparagem e o desvio prometem, preso em teste.
//
// Os números que justificaram este módulo — 235 travessias caindo para 40 — vieram de
// uma medição feita à mão sobre a projeção viva e descartada depois. Aqui ficam as
// garantias que não dependem de backend nenhum: elas são sobre geometria, e geometria se
// mede num teste.

import { describe, expect, it } from 'vitest';

import { composeLayout } from './composeLayout';
import { edge, node, projectionFixture } from './fixture';
import { dashPath, edgePath, trimEdge, type EdgeObstacle } from './edgePath';
import type { Projection, ProjectionEdge, ProjectionNode } from './contract';
import { describePanel } from './panels';
import { panelSweepRadius } from './panelScale';
import { buildRelationRegistry } from './relationRegistry';

const A = { x: 0, y: 0, z: 0 };
const B = { x: 100, y: 0, z: 0 };

function comprimento(pontos: { x: number; y: number; z: number }[]): number {
  let total = 0;
  for (let i = 0; i + 1 < pontos.length; i += 1) {
    const p = pontos[i]!;
    const q = pontos[i + 1]!;
    total += Math.hypot(q.x - p.x, q.y - p.y, q.z - p.z);
  }
  return total;
}

/** Distância mínima de um ponto à polilinha. */
function distanciaAte(
  pontos: { x: number; y: number; z: number }[],
  alvo: { x: number; y: number; z: number },
): number {
  let menor = Number.POSITIVE_INFINITY;
  for (let i = 0; i + 1 < pontos.length; i += 1) {
    const p = pontos[i]!;
    const q = pontos[i + 1]!;
    const dx = q.x - p.x;
    const dy = q.y - p.y;
    const dz = q.z - p.z;
    const quadrado = dx * dx + dy * dy + dz * dz;
    const t =
      quadrado < 1e-9
        ? 0
        : Math.max(
            0,
            Math.min(
              1,
              ((alvo.x - p.x) * dx + (alvo.y - p.y) * dy + (alvo.z - p.z) * dz) / quadrado,
            ),
          );
    menor = Math.min(
      menor,
      Math.hypot(p.x + dx * t - alvo.x, p.y + dy * t - alvo.y, p.z + dz * t - alvo.z),
    );
  }
  return menor;
}

describe('a ponta da linha', () => {
  it('para encostada na placa, e nunca no centro dela', () => {
    const aparada = trimEdge(A, B, 10, 6)!;
    expect(aparada).not.toBeNull();
    // Dentro do círculo varrido — a linha pode entrar por baixo da própria placa,
    // porque a placa a esconde — e longe do centro, que é onde ela ficaria enterrada.
    expect(aparada.a.x).toBeLessThan(10);
    expect(aparada.a.x).toBeGreaterThan(10 * 0.5);
    expect(100 - aparada.b.x).toBeLessThan(6);
    expect(100 - aparada.b.x).toBeGreaterThan(6 * 0.5);
  });

  it('recusa o traço que não sobraria entre duas placas encostadas', () => {
    // Duas placas praticamente coladas produziriam um toco de poucos pixels, que não lê
    // como ligação e ainda soma uma primitiva.
    expect(trimEdge(A, { x: 12, y: 0, z: 0 }, 10, 6)).toBeNull();
    expect(trimEdge(A, A, 1, 1)).toBeNull();
  });
});

describe('o desvio', () => {
  const obstaculo: EdgeObstacle = { id: 'meio', position: { x: 50, y: 0, z: 0 }, radius: 8 };

  it('contorna a placa que estaria no caminho', () => {
    const reto = edgePath(A, B, 2, 2, [], new Set())!;
    expect(distanciaAte(reto, obstaculo.position)).toBeLessThan(obstaculo.radius);

    const desviado = edgePath(A, B, 2, 2, [obstaculo], new Set())!;
    expect(desviado.length).toBeGreaterThan(2);
    expect(distanciaAte(desviado, obstaculo.position)).toBeGreaterThanOrEqual(
      obstaculo.radius,
    );
  });

  it('não desvia do que ele próprio liga', () => {
    // Os dois extremos são placas, e evitá-las seria fugir do próprio destino.
    const caminho = edgePath(A, B, 2, 2, [obstaculo], new Set(['meio']))!;
    expect(caminho).toHaveLength(2);
  });

  it('paga em comprimento, e pouco', () => {
    const reto = edgePath(A, B, 2, 2, [], new Set())!;
    const desviado = edgePath(A, B, 2, 2, [obstaculo], new Set())!;
    expect(comprimento(desviado)).toBeGreaterThan(comprimento(reto));
    expect(comprimento(desviado)).toBeLessThan(comprimento(reto) * 1.3);
  });

  it('devolve dois pontos quando a reta já está livre, para a geometria ficar barata', () => {
    const longe: EdgeObstacle = { id: 'longe', position: { x: 50, y: 90, z: 0 }, radius: 8 };
    expect(edgePath(A, B, 2, 2, [longe], new Set())).toHaveLength(2);
  });
});

describe('o padrão corre pelo caminho inteiro', () => {
  it('não reinicia a fase a cada pedaço da curva', () => {
    const curva = edgePath(
      A,
      B,
      2,
      2,
      [{ id: 'meio', position: { x: 50, y: 0, z: 0 }, radius: 8 }],
      new Set(),
    )!;
    const vertices = dashPath(curva, [4, 2]);
    let desenhado = 0;
    for (let i = 0; i < vertices.length; i += 6) {
      desenhado += Math.hypot(
        vertices[i + 3]! - vertices[i]!,
        vertices[i + 4]! - vertices[i + 1]!,
        vertices[i + 5]! - vertices[i + 2]!,
      );
    }
    // A prova é a **proporção desenhada**, não a contagem de traços: um traço partido na
    // fronteira de duas amostras vira dois pares de vértices sem mudar o que se vê. Com
    // a fase contínua, o padrão 4/2 pinta dois terços do caminho. Reiniciada por pedaço,
    // cada amostra recomeçaria desenhando e a proporção subiria — é essa a diferença.
    // A faixa, e não a igualdade: o caminho não é múltiplo do período, então a última
    // repetição termina cortada. Reiniciada por pedaço, a proporção iria a ~0,73.
    const proporcao = desenhado / comprimento(curva);
    expect(proporcao).toBeGreaterThan(0.64);
    expect(proporcao).toBeLessThan(0.7);
  });
});

/** Uma projeção com execuções, para medir o caminho sobre uma cena composta. */
function comExecucoes(quantas: number): Projection {
  const projection = projectionFixture();
  const nodes: ProjectionNode[] = [...projection.nodes];
  const edges: ProjectionEdge[] = [...projection.edges];
  for (let i = 0; i < quantas; i += 1) {
    const painel = `op/quorum/exec${i}/panel`;
    nodes.push(
      node(painel, {
        kind: 'quorum-panel',
        layer: 'operational',
        domainId: 'operacional',
        operational: { panelId: `exec${i}` },
      }),
    );
    const decisao = `op/quorum/exec${i}/decision`;
    nodes.push(
      node(decisao, {
        kind: 'quorum-decision',
        layer: 'operational',
        domainId: 'operacional',
        operational: { panelId: `exec${i}` },
      }),
    );
    edges.push(edge(painel, decisao, 'operational'));
  }
  return { ...projection, nodes, edges };
}

describe('na cena composta', () => {
  it('quase nenhuma linha atravessa uma placa que ela não liga', () => {
    const projection = comExecucoes(20);
    const composto = composeLayout(projection);
    const raio = new Map(
      projection.nodes.map((n) => [n.id, panelSweepRadius(describePanel(n))]),
    );
    const obstaculos: EdgeObstacle[] = [];
    for (const [id, r] of raio) {
      const p = composto.positions.get(id);
      if (p) obstaculos.push({ id, position: p, radius: r });
    }
    const registro = buildRelationRegistry(
      projection.edges.filter((e) => e.kind !== 'aggregated' && e.primaryRelation),
    );

    let desenhadas = 0;
    let atravessam = 0;
    for (const par of registro.pairs) {
      if (par.selfLink || !par.dominantFamily) continue;
      const a = composto.positions.get(par.a);
      const b = composto.positions.get(par.b);
      if (!a || !b) continue;
      const caminho = edgePath(
        a,
        b,
        raio.get(par.a) ?? 0,
        raio.get(par.b) ?? 0,
        obstaculos,
        new Set([par.a, par.b]),
      );
      if (!caminho) continue;
      desenhadas += 1;
      const cruza = obstaculos.some(
        (o) =>
          o.id !== par.a && o.id !== par.b && distanciaAte(caminho, o.position) < o.radius,
      );
      if (cruza) atravessam += 1;
    }

    expect(desenhadas).toBeGreaterThan(0);
    // O desvio é aproximado por construção — um ponto de controle não resolve dois
    // obstáculos em lados opostos —, então o teto é um teto, não um zero. O que ele
    // impede é a regressão silenciosa: medido na projeção viva, 993 pares desenhados
    // com 40 travessias, ou 4%.
    expect(atravessam / desenhadas).toBeLessThan(0.1);
  });
});
