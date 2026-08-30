// O que 3.5-B precisa prender: o layout volumétrico não reintroduz sobreposição, o
// ordinal da execução sobrevive a qualquer bagunça temporal, e a inspeção da cena é
// dado, não objeto.

import { describe, expect, it } from 'vitest';

import { composeLayout } from './composeLayout';
import type { Projection, ProjectionEdge, ProjectionNode } from './contract';
import { edge, node, projectionFixture } from './fixture';
import { layoutAtlas } from './layout';
import { atribuirSlots, groupQuorumSystems, layoutOperational } from './operationalLayout';
import {
  POSE_FIXA,
  dispersaoEspacial,
  idsEpistemicos,
  metricasDeTela,
  poseAutoenquadrada,
  projetarCaixas,
  separacaoAngular,
} from './screenMetrics';

function execucao(panelId: string, criadaEm: string | null): {
  nodes: ProjectionNode[];
  edges: ProjectionEdge[];
} {
  const base = {
    layer: 'operational' as const,
    path: null,
    canonicalState: 'temporary' as const,
    domainId: 'operacional/quorum',
    domainLabel: 'quórum',
    createdAt: criadaEm,
  };
  const painel = node(`op/quorum/${panelId}/panel`, {
    ...base,
    kind: 'quorum-panel',
    operational: { panelId },
  });
  const nodes: ProjectionNode[] = [painel];
  const edges: ProjectionEdge[] = [];
  for (let i = 0; i < 3; i += 1) {
    const membro = `op/quorum/${panelId}/member/0${i}`;
    const voto = `op/quorum/${panelId}/vote/0${i}`;
    nodes.push(
      node(membro, { ...base, kind: 'quorum-member', operational: { panelId } }),
      node(voto, { ...base, kind: 'quorum-vote', operational: { panelId } }),
    );
    edges.push(
      edge(painel.id, membro, 'operational', 'operational'),
      edge(membro, voto, 'operational', 'operational'),
    );
  }
  return { nodes, edges };
}

function comExecucoes(datas: [string, string | null][]): Projection {
  const p = projectionFixture();
  const nodes = [...p.nodes];
  const edges = [...p.edges];
  for (const [id, data] of datas) {
    const e = execucao(id, data);
    nodes.push(...e.nodes);
    edges.push(...e.edges);
  }
  return { ...p, nodes, edges };
}

const DIA = (d: number): string => `2026-07-${String(d).padStart(2, '0')}T00:00:00+00:00`;

describe('o ordinal da execução sobrevive à bagunça temporal', () => {
  // Ordenar por data só é estável para inserção cronologicamente posterior. Cada caso
  // abaixo é uma forma de quebrar isso, e todas reprovariam com a ordenação por data.
  const base = comExecucoes([
    ['a', DIA(10)],
    ['b', DIA(20)],
    ['c', DIA(30)],
  ]);
  const assentar = (p: Projection, slots?: ReadonlyMap<string, number>) =>
    layoutOperational(p, slots ?? new Map());
  const inicial = assentar(base);

  const casos: [string, Projection][] = [
    ['inserção retroativa', comExecucoes([['a', DIA(10)], ['b', DIA(20)], ['c', DIA(30)], ['z', DIA(1)]])],
    ['timestamps iguais', comExecucoes([['a', DIA(10)], ['b', DIA(10)], ['c', DIA(30)]])],
    ['correção de data', comExecucoes([['a', DIA(28)], ['b', DIA(20)], ['c', DIA(30)]])],
    ['relógio fora de ordem', comExecucoes([['a', DIA(10)], ['b', DIA(20)], ['c', DIA(5)]])],
    ['data ausente', comExecucoes([['a', null], ['b', DIA(20)], ['c', DIA(30)]])],
    ['reimportação completa', comExecucoes([['c', DIA(30)], ['b', DIA(20)], ['a', DIA(10)]])],
  ];

  it.each(casos)('%s não move execução já assentada', (_nome, projecao) => {
    const depois = assentar(projecao, inicial.slots);
    for (const [id, p] of inicial.positions) {
      const nova = depois.positions.get(id);
      if (!nova) continue; // execução que saiu da projeção não é deslocamento
      expect(nova).toEqual(p);
    }
  });

  it('sem ordinal gravado o assentamento continua determinístico', () => {
    const a = assentar(base).positions;
    const b = assentar({ ...base, nodes: [...base.nodes].reverse() }).positions;
    for (const [id, p] of a) expect(b.get(id)).toEqual(p);
  });

  it('ordinal já atribuído nunca é reatribuído, e o novo pega o menor livre', () => {
    const { systems } = groupQuorumSystems(base);
    const slots = atribuirSlots(systems, new Map([['b', 0]]));
    expect(slots.get('b')).toBe(0);
    expect(new Set(slots.values()).size).toBe(slots.size);
    expect(Math.max(...slots.values())).toBe(systems.length - 1);
  });
});

describe('layout volumétrico do corpus', () => {
  const projection = projectionFixture([
    'Física/Nota A', 'Física/Nota B', 'Física/Nota C', 'Física/Nota D',
    'Física/Nota E', 'Física/Nota F', 'Física/Nota G', 'Física/Nota H',
  ]);
  const ids = idsEpistemicos(projection);
  const composto = composeLayout(projection);

  it('nenhuma entidade fica totalmente ocluída, nos dois protocolos', () => {
    const auto = poseAutoenquadrada(composto.extent.corpus.radius, composto.extent.corpus.depth);
    for (const pose of [POSE_FIXA, auto]) {
      const m = metricasDeTela(projetarCaixas(projection, composto.positions, ids, pose));
      expect(m.totalmenteOcluidas).toBe(0);
    }
  });

  it('a âncora não invade a placa de nenhum membro', () => {
    // O primeiro membro nascia no centro do território, a 1,6 unidades do próprio MOC,
    // porque `clusterize` deixa os MOCs de fora e eles nunca entravam na colisão.
    for (const moc of projection.nodes.filter((n) => n.kind === 'moc')) {
      const pm = composto.positions.get(moc.id);
      if (!pm) continue;
      for (const membro of projection.nodes) {
        if (membro.anchorMocId !== moc.id) continue;
        const p = composto.positions.get(membro.id)!;
        expect(Math.hypot(p.x - pm.x, p.y - pm.y, p.z - pm.z)).toBeGreaterThan(9);
      }
    }
  });

  it('a profundidade carrega estrutura, não só volume', () => {
    const d = dispersaoEspacial(composto.positions, ids);
    // O atlas auditado tinha 2,3% da variância em profundidade e lia como lâmina.
    expect(d.razaoSigma3Sigma1).toBeGreaterThan(0.24);
    expect(d.varianciaZ).toBeGreaterThan(0);
  });

  it('a separação angular entre territórios não regride', () => {
    const a = separacaoAngular(projection, composto.positions, POSE_FIXA);
    expect(a.mediana_graus).toBeGreaterThan(0);
    expect(a.minima_graus).toBeGreaterThan(0);
  });

  it('é determinístico e independente da ordem de entrada', () => {
    const embaralhada: Projection = {
      ...projection,
      nodes: [...projection.nodes].reverse(),
      edges: [...projection.edges].reverse(),
    };
    const b = composeLayout(embaralhada).positions;
    for (const [id, p] of composto.positions) expect(b.get(id)).toEqual(p);
  });

  it('uma nota nova reacomoda o próprio domínio e mais nada', () => {
    const maior = composeLayout(projectionFixture([
      'Física/Nota A', 'Física/Nota B', 'Física/Nota C', 'Física/Nota D',
      'Física/Nota E', 'Física/Nota F', 'Física/Nota G', 'Física/Nota H',
      'Física/Nota I',
    ])).positions;
    for (const no of projection.nodes) {
      if (no.layer !== 'epistemic' || no.domainId === 'fisica') continue;
      const antes = composto.positions.get(no.id);
      const depois = maior.get(no.id);
      if (!antes || !depois) continue;
      expect(Math.hypot(antes.x - depois.x, antes.y - depois.y, antes.z - depois.z)).toBeLessThan(
        1e-9,
      );
    }
  });

  it('o cache reaberto devolve exatamente as posições gravadas', () => {
    const gravadas = new Map(composto.positions);
    const reaberto = layoutAtlas(projection, {}, gravadas);
    for (const [id, p] of reaberto) {
      const g = gravadas.get(id);
      if (g) expect(p).toEqual(g);
    }
  });
});
