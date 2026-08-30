import { describe, expect, it } from 'vitest';

import type { ProjectionEdge, ProjectionNode } from './contract';
import { edge as projectionEdge } from './fixture';
import type { LayoutMap } from './layout';
import { advanceMotion, motionStartPositions, preserveAnchorTargets } from './semanticMotion';

function node(id: string, anchor = false): ProjectionNode {
  return {
    id,
    title: id,
    shortLabel: id,
    path: null,
    kind: anchor ? 'agent' : 'activity',
    layer: 'operational',
    canonicalState: 'temporary',
    epistemicStatus: 'not-specified',
    domainId: 'operacional/live',
    domainLabel: 'operação ao vivo',
    anchorMocId: null,
    mocIds: [],
    claimCount: 0,
    incomingDegree: 0,
    outgoingDegree: 0,
    degreeByRelation: {},
    createdAt: null,
    updatedAt: null,
    verifiedAt: null,
    visual: { paletteToken: 'D06', lodClass: 1, labelPriority: 1, isAnchor: anchor },
    operational: {},
  };
}

function edge(source: string, target: string): ProjectionEdge {
  return { ...projectionEdge(source, target, 'operational'), kind: 'operational', layer: 'operational' };
}

describe('o assentamento semântico', () => {
  it('translada os alvos dependentes junto com a âncora preservada', () => {
    const nodes = [node('provedor', true), node('modelo'), node('evento')];
    const edges = [edge('modelo', 'provedor'), edge('modelo', 'evento')];
    const targets: LayoutMap = new Map([
      ['provedor', { x: 100, y: 20, z: 0 }],
      ['modelo', { x: 112, y: 20, z: 0 }],
      ['evento', { x: 118, y: 20, z: 0 }],
    ]);
    const previous: LayoutMap = new Map([['provedor', { x: 4, y: -3, z: 1 }]]);

    const rebased = preserveAnchorTargets(nodes, edges, targets, previous);

    expect(rebased.get('provedor')).toEqual({ x: 4, y: -3, z: 1 });
    expect(rebased.get('modelo')).toEqual({ x: 16, y: -3, z: 1 });
    expect(rebased.get('evento')).toEqual({ x: 22, y: -3, z: 1 });
  });

  it('dá à âncora nova o slot livre em vez de colidir com a preservada', () => {
    const nodes = [
      node('groq', true),
      node('modelo-groq'),
      node('anthropic', true),
      node('modelo-anthropic'),
    ];
    const edges = [edge('modelo-groq', 'groq'), edge('modelo-anthropic', 'anthropic')];
    const targets: LayoutMap = new Map([
      ['groq', { x: -68, y: 0, z: 0 }],
      ['modelo-groq', { x: -58, y: 0, z: 0 }],
      ['anthropic', { x: 68, y: 0, z: 0 }],
      ['modelo-anthropic', { x: 78, y: 0, z: 0 }],
    ]);
    const previous: LayoutMap = new Map([
      ['groq', { x: 68, y: 0, z: 0 }],
      ['modelo-groq', { x: 78, y: 0, z: 0 }],
    ]);

    const rebased = preserveAnchorTargets(nodes, edges, targets, previous);

    expect(rebased.get('groq')).toEqual({ x: 68, y: 0, z: 0 });
    expect(rebased.get('anthropic')).toEqual({ x: -68, y: 0, z: 0 });
    expect(rebased.get('modelo-anthropic')).toEqual({ x: -58, y: 0, z: 0 });
  });

  it('conserva âncora, reaproveita satélite e nasce evento no vizinho causal', () => {
    const nodes = [node('provedor', true), node('modelo'), node('evento')];
    const edges = [edge('modelo', 'provedor'), edge('modelo', 'evento')];
    const targets: LayoutMap = new Map([
      ['provedor', { x: 30, y: 0, z: 0 }],
      ['modelo', { x: 40, y: 0, z: 0 }],
      ['evento', { x: 50, y: 0, z: 0 }],
    ]);
    const previous: LayoutMap = new Map([
      ['provedor', { x: 10, y: 0, z: 0 }],
      ['modelo', { x: 18, y: 0, z: 0 }],
    ]);

    const start = motionStartPositions(nodes, edges, targets, previous);

    expect(start.get('provedor')).toEqual({ x: 10, y: 0, z: 0 });
    expect(start.get('modelo')).toEqual({ x: 18, y: 0, z: 0 });
    expect(start.get('evento')).toEqual({ x: 18, y: 0, z: 0 });
  });

  it('move somente satélites e termina exatamente no alvo', () => {
    const current: LayoutMap = new Map([
      ['ancora', { x: 2, y: 0, z: 0 }],
      ['satelite', { x: 0, y: 0, z: 0 }],
    ]);
    const targets: LayoutMap = new Map([
      ['ancora', { x: 99, y: 0, z: 0 }],
      ['satelite', { x: 10, y: 0, z: 0 }],
    ]);

    const first = advanceMotion(current, targets, new Set(['ancora']), 0.1);
    expect(first.moved).toBe(true);
    expect(first.settled).toBe(false);
    expect(current.get('ancora')?.x).toBe(2);
    expect(current.get('satelite')!.x).toBeGreaterThan(0);
    expect(current.get('satelite')!.x).toBeLessThan(10);

    const last = advanceMotion(current, targets, new Set(['ancora']), 1, true);
    expect(last).toEqual({ moved: true, settled: true });
    expect(current.get('satelite')).toEqual({ x: 10, y: 0, z: 0 });
  });
});
