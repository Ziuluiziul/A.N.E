// Projeção sintética para os testes. Não é importada por nenhum código de cena, e
// por isso não entra no bundle — mas fica em `src/` para o TypeScript checá-la com o
// mesmo rigor do resto.
//
// Ela imita a forma do corpus real: um MOC de raiz, MOCs de domínio, notas ancoradas
// e um domínio com dois MOCs, que é o caso em que a ancoragem se recusa a desempatar.

import {
  OPERATIONAL_KINDS,
  type EntityKind,
  type Projection,
  type ProjectionEdge,
  type ProjectionNode,
  type RelationFamily,
} from './contract';

let contador = 0;

export function node(
  id: string,
  overrides: Partial<ProjectionNode> = {},
): ProjectionNode {
  contador += 1;
  const kind: EntityKind = overrides.kind ?? 'note';
  const domainId = overrides.domainId ?? 'fisica';
  return {
    id,
    title: overrides.title ?? id,
    shortLabel: overrides.shortLabel ?? id.split('/').at(-1)!,
    path: `${id}.md`,
    kind,
    layer: overrides.layer ?? 'epistemic',
    canonicalState: 'canonical',
    epistemicStatus: 'established',
    domainId,
    domainLabel: overrides.domainLabel ?? domainId,
    anchorMocId: overrides.anchorMocId ?? null,
    mocIds: overrides.mocIds ?? [],
    claimCount: overrides.claimCount ?? 3,
    incomingDegree: overrides.incomingDegree ?? 1,
    outgoingDegree: overrides.outgoingDegree ?? 1,
    degreeByRelation: overrides.degreeByRelation ?? { prerequisite: 1 },
    createdAt: null,
    updatedAt: null,
    verifiedAt: null,
    visual: overrides.visual ?? {
      paletteToken: `D0${(contador % 9) + 1}`,
      lodClass: kind === 'moc' ? 0 : 2,
      labelPriority: overrides.claimCount ?? 3,
      isAnchor: kind === 'moc',
    },
    ...overrides,
  };
}

export function edge(
  source: string,
  target: string,
  relation: RelationFamily = 'prerequisite',
  kind: ProjectionEdge['kind'] = 'canonical',
  overrides: Partial<ProjectionEdge> = {},
): ProjectionEdge {
  return {
    source,
    target,
    kind,
    layer: kind === 'operational' ? 'operational' : 'epistemic',
    relations: [relation],
    primaryRelation: relation,
    weight: 1,
    matchedBy: kind === 'aggregated' ? 'computed' : 'id',
    ...overrides,
  };
}

export function projectionFixture(extraNotes: string[] = []): Projection {
  const nodes: ProjectionNode[] = [
    node('Índice', { kind: 'moc', domainId: 'raiz', domainLabel: 'raiz' }),
    node('Física/MOC — Física', { kind: 'moc', domainId: 'fisica', domainLabel: 'Física' }),
    node('Dados/MOC — Dados', { kind: 'moc', domainId: 'dados', domainLabel: 'Dados' }),
    // Domínio com dois MOCs: quem nenhum reivindica fica sem âncora, de propósito.
    node('Computação/MOC — Computação', {
      kind: 'moc',
      domainId: 'computacao',
      domainLabel: 'Computação',
    }),
    node('Computação/MOC — Python', {
      kind: 'moc',
      domainId: 'computacao',
      domainLabel: 'Computação',
    }),
    node('Física/Entropia', { anchorMocId: 'Física/MOC — Física', claimCount: 8 }),
    node('Física/Calor', { anchorMocId: 'Física/MOC — Física', claimCount: 5 }),
    node('Física/Referências', {
      kind: 'reference',
      anchorMocId: 'Física/MOC — Física',
      claimCount: 0,
    }),
    node('Dados/Shannon', {
      domainId: 'dados',
      domainLabel: 'Dados',
      anchorMocId: 'Dados/MOC — Dados',
      claimCount: 4,
    }),
    node('Computação/Sem âncora', {
      domainId: 'computacao',
      domainLabel: 'Computação',
      anchorMocId: null,
    }),
    node('Metodologia/Política', {
      kind: 'register',
      domainId: 'metodologia',
      domainLabel: 'Metodologia',
      anchorMocId: null,
    }),
  ];

  for (const extra of extraNotes) {
    nodes.push(node(extra, { anchorMocId: 'Física/MOC — Física' }));
  }

  const edges: ProjectionEdge[] = [
    edge('Física/MOC — Física', 'Física/Entropia', 'navigation'),
    edge('Física/MOC — Física', 'Física/Calor', 'navigation'),
    edge('Física/Calor', 'Física/Entropia', 'prerequisite'),
    edge('Física/Entropia', 'Dados/Shannon', 'extends'),
    edge('Física/Referências', 'Física/Entropia', 'evidence'),
    edge('Dados/MOC — Dados', 'Dados/Shannon', 'navigation'),
    edge('Física/MOC — Física', 'Dados/MOC — Dados', 'extends', 'aggregated'),
  ];

  return {
    meta: {
      contractVersion: '1.0.0',
      generatedAt: '2026-08-02T00:00:00+00:00',
      source: 'corpus',
      operationalSource: 'none',
      operationalKinds: [...OPERATIONAL_KINDS],
      corpusFingerprint: 'f'.repeat(64),
      computedFields: ['domainId', 'anchorMocId', 'visual.paletteToken'],
      relationFamilies: [
        'navigation',
        'prerequisite',
        'extends',
        'contrasts',
        'evidence',
        'operational',
        'historical',
      ],
      domains: [
        { id: 'raiz', label: 'raiz', paletteToken: 'D01', mocIds: ['Índice'] },
        { id: 'fisica', label: 'Física', paletteToken: 'D02', mocIds: ['Física/MOC — Física'] },
        { id: 'dados', label: 'Dados', paletteToken: 'D03', mocIds: ['Dados/MOC — Dados'] },
        {
          id: 'computacao',
          label: 'Computação',
          paletteToken: 'D04',
          mocIds: ['Computação/MOC — Computação', 'Computação/MOC — Python'],
        },
        { id: 'metodologia', label: 'Metodologia', paletteToken: 'D05', mocIds: [] },
      ],
      counts: {
        notes: nodes.filter((n) => n.layer === 'epistemic').length,
        operationalNodes: nodes.filter((n) => n.layer === 'operational').length,
        canonicalEdges: edges.filter((e) => e.kind === 'canonical').length,
        aggregatedEdges: edges.filter((e) => e.kind === 'aggregated').length,
        wikilinks: edges
          .filter((item) => item.kind === 'canonical')
          .reduce((sum, item) => sum + item.weight, 0),
        claims: nodes.reduce((soma, n) => soma + n.claimCount, 0),
        mocs: nodes.filter((n) => n.kind === 'moc').length,
      },
      diagnostics: { broken: [], undeclared: [], collisions: {} },
    },
    nodes,
    edges,
  };
}
