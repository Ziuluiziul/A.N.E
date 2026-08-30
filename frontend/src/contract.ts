// Espelho tipado de `vault.projection`. Mudança incompatível sobe a major do
// contrato, e a cena recusa uma major que não conhece em vez de renderizar campos
// que não entende — falhar visível é melhor que desenhar um atlas errado.

import {
  PayloadError,
  payloadArray,
  payloadBoolean,
  payloadEnum,
  payloadNullableString,
  payloadNumber,
  payloadRecord,
  payloadString,
  payloadStringArray,
  payloadText,
  payloadUnique,
} from './payload';
import {
  backendFetch,
  openBackendEvents,
  type BackendConnectionStatus,
} from './transport';

export const SUPPORTED_CONTRACT_MAJOR = 1;

export type EpistemicKind = 'note' | 'moc' | 'reference' | 'register';

/** Camada operacional: procedência, nunca conhecimento. */
export type OperationalKind =
  | 'agent'
  | 'activity'
  | 'evidence'
  | 'proposal'
  | 'commit'
  | 'rejection'
  | 'temporary-file'
  | 'quorum-panel'
  | 'quorum-member'
  | 'quorum-vote'
  | 'quorum-decision';

export type EntityKind = EpistemicKind | OperationalKind;

export type Layer = 'epistemic' | 'operational';

export const OPERATIONAL_KINDS: OperationalKind[] = [
  'agent',
  'activity',
  'evidence',
  'proposal',
  'commit',
  'rejection',
  'temporary-file',
  'quorum-panel',
  'quorum-member',
  'quorum-vote',
  'quorum-decision',
];

export type CanonicalState = 'canonical' | 'proposed' | 'temporary' | 'rejected' | 'archived';

export type QuorumVoteDecision = 'approve' | 'reject' | 'revise' | 'abstain';
export type QuorumAction = 'promote' | 'revise' | 'reject' | 'escalate';

export const QUORUM_VOTE_DECISIONS: QuorumVoteDecision[] = [
  'approve',
  'reject',
  'revise',
  'abstain',
];
export const QUORUM_ACTIONS: QuorumAction[] = ['promote', 'revise', 'reject', 'escalate'];

/**
 * Resumo operacional permitido no navegador.
 *
 * É uma lista branca deliberadamente pequena: respostas de modelo, justificativas
 * livres e qualquer bloco de raciocínio não fazem parte do contrato do Atlas.
 */
export interface OperationalMetadata {
  panelId?: string;
  decision?: QuorumVoteDecision;
  action?: QuorumAction;
  confidence?: number;
  tally?: Partial<Record<QuorumVoteDecision, number>>;
  endpoint?: string;
  provider?: string;
  family?: string;
  role?: string;
  schemaValid?: boolean;
  validVotes?: number;
  providerCount?: number;
  familyCount?: number;
  /** Registro de modelos: quantos modelos um provedor tem, e quanto cada um trabalhou. */
  modelCount?: number;
  executionCount?: number;
  /** Quantos modelos de um provedor responderam na sonda mais recente. */
  availableCount?: number;
  /** Estado observado do endpoint: `ok`, `reachable`, `unavailable`, … */
  endpointStatus?: string;
  /** Identidade estática de um papel do trabalho. O estado vivo é do painel de controle. */
  workerClass?: string;
  summary?: string;
  area?: string;
  concurrencyMax?: number;
  /** Campos escalares da trilha operacional viva; mapas livres não entram aqui. */
  eventId?: string;
  runtimeRevision?: number;
  eventType?: string;
  actor?: string;
  task?: string;
  entity?: string;
  reasoningBlockDetected?: boolean;
  reasoningBlockRemoved?: boolean;
  /**
   * A deliberação em linguagem natural.
   *
   * São frases já sanitizadas pelo backend: `_resumo` corta na fronteira de frase e
   * recusa qualquer texto com bloco de raciocínio ou forma de segredo. O requisito é
   * processo observável — o que o avaliador examinou, o que o incomodou, o que o
   * quórum decidiu e por quê —, nunca cadeia privada de pensamento.
   */
  assessment?: string;
  blockingIssue?: string;
  reason?: string;
  synthesis?: string;
  candidate?: string;
  /**
   * O que está sendo feito **agora**, dito em linguagem natural.
   *
   * Vem da trilha ao vivo, e é o que permite acompanhar um worker antes da resposta
   * final. O backend recusa bloco de raciocínio e forma de segredo antes de emitir.
   */
  narration?: string;
}

export type RelationFamily =
  | 'navigation'
  | 'prerequisite'
  | 'extends'
  | 'contrasts'
  | 'evidence'
  | 'operational'
  | 'historical';

export interface NodeVisual {
  paletteToken: string;
  lodClass: number;
  labelPriority: number;
  isAnchor: boolean;
}

export type ClaimStatus =
  | 'established'
  | 'supported'
  | 'model-dependent'
  | 'hypothesis'
  | 'speculative'
  | 'open'
  | 'refuted'
  | 'operational'
  | 'out-of-scope'
  | 'quarantine';

export type EpistemicStatus =
  | 'established'
  | 'supported'
  | 'model-dependent'
  | 'hypothesis'
  | 'speculative'
  | 'mixed'
  | 'operational'
  | 'quarantine'
  | 'not-specified';

/** Um claim como o corpus o declara: afirmação, status fechado e evidência. */
export interface ProjectionClaim {
  id: string;
  statement: string;
  status: ClaimStatus;
  evidence: string | null;
}

export interface ProjectionNode {
  id: string;
  title: string;
  shortLabel: string;
  path: string | null;
  kind: EntityKind;
  layer: Layer;
  canonicalState: CanonicalState;
  epistemicStatus: EpistemicStatus;
  domainId: string;
  domainLabel: string;
  anchorMocId: string | null;
  mocIds: string[];
  claimCount: number;
  /**
   * O conteúdo da nota, e não apenas o que se sabe sobre ela.
   *
   * A projeção levava só metadado, e um painel aberto mostrava frases **sobre** a nota
   * e nenhuma linha **dela**. `summary` é a abertura do corpo; `claims` são a unidade
   * epistêmica — o que a nota afirma, com que status e sobre que evidência.
   */
  summary?: string | null;
  claims?: ProjectionClaim[];
  incomingDegree: number;
  outgoingDegree: number;
  degreeByRelation: Record<string, number>;
  createdAt: string | null;
  updatedAt: string | null;
  verifiedAt: string | null;
  visual: NodeVisual;
  operational?: OperationalMetadata;
}

export interface ProjectionEdge {
  source: string;
  target: string;
  kind: 'canonical' | 'aggregated' | 'operational';
  layer: Layer;
  relations: RelationFamily[];
  primaryRelation: RelationFamily | null;
  weight: number;
  matchedBy: string;
  /** Proveniência direcional presente nas arestas agregadas desde o contrato 1.1. */
  weightByDirection?: { forward: number; backward: number };
  relationsByDirection?: {
    forward: RelationFamily[];
    backward: RelationFamily[];
  };
  reciprocal?: boolean;
}

export interface DomainMeta {
  id: string;
  label: string;
  paletteToken: string;
  mocIds: string[];
}

export interface ProjectionMeta {
  contractVersion: string;
  generatedAt: string;
  source: 'corpus' | 'demo';
  operationalSource: 'none' | 'demo' | 'quorum' | 'mixed';
  operationalKinds: OperationalKind[];
  corpusFingerprint: string;
  computedFields: string[];
  relationFamilies: RelationFamily[];
  domains: DomainMeta[];
  counts: {
    notes: number;
    operationalNodes: number;
    canonicalEdges: number;
    aggregatedEdges: number;
    wikilinks: number;
    claims: number;
    mocs: number;
  };
  diagnostics: {
    broken: unknown[];
    undeclared: unknown[];
    collisions: Record<string, unknown>;
  };
}

export interface Projection {
  meta: ProjectionMeta;
  nodes: ProjectionNode[];
  edges: ProjectionEdge[];
}

export class ContractError extends Error {}

const EPISTEMIC_KINDS = ['note', 'moc', 'reference', 'register'] as const;
const ENTITY_KINDS = [...EPISTEMIC_KINDS, ...OPERATIONAL_KINDS] as const;
const LAYERS = ['epistemic', 'operational'] as const;
const CANONICAL_STATES = [
  'canonical',
  'proposed',
  'temporary',
  'rejected',
  'archived',
] as const;
const RELATION_FAMILIES = [
  'navigation',
  'prerequisite',
  'extends',
  'contrasts',
  'evidence',
  'operational',
  'historical',
] as const;
const EDGE_KINDS = ['canonical', 'aggregated', 'operational'] as const;
const CLAIM_STATUSES = [
  'established',
  'supported',
  'model-dependent',
  'hypothesis',
  'speculative',
  'open',
  'refuted',
  'operational',
  'out-of-scope',
  'quarantine',
] as const;
const EPISTEMIC_STATUSES = [
  'established',
  'supported',
  'model-dependent',
  'hypothesis',
  'speculative',
  'mixed',
  'operational',
  'quarantine',
  'not-specified',
] as const;

function payloadDate(value: unknown, path: string): string {
  const text = payloadString(value, path);
  if (!Number.isFinite(Date.parse(text))) throw new PayloadError(path, 'esperada data válida');
  return text;
}

function payloadNullableDate(value: unknown, path: string): string | null {
  return value === null ? null : payloadDate(value, path);
}

function payloadEnumArray<T extends string>(
  value: unknown,
  path: string,
  allowed: readonly T[],
): T[] {
  const result = payloadArray(value, path).map((item, index) =>
    payloadEnum(item, `${path}[${index}]`, allowed),
  );
  payloadUnique(result, path);
  return result;
}

function payloadCountMap(value: unknown, path: string): Record<string, number> {
  const source = payloadRecord(value, path);
  const result: Record<string, number> = {};
  for (const [key, item] of Object.entries(source)) {
    payloadEnum(key, `${path}.${key}`, RELATION_FAMILIES);
    result[key] = payloadNumber(item, `${path}.${key}`, { integer: true, min: 0 });
  }
  return result;
}

function optional<T>(
  source: Record<string, unknown>,
  key: string,
  path: string,
  parse: (value: unknown, fieldPath: string) => T,
): T | undefined {
  return source[key] === undefined ? undefined : parse(source[key], `${path}.${key}`);
}

function parseOperational(value: unknown, path: string): OperationalMetadata {
  const source = payloadRecord(value, path);
  const unknown = Object.keys(source).filter((key) => !OPERATIONAL_METADATA_KEYS.has(key));
  if (unknown.length > 0) {
    throw new PayloadError(`${path}.${unknown[0]}`, 'campo operacional fora da lista branca');
  }

  const panelId = optional(source, 'panelId', path, payloadString);
  const endpoint = optional(source, 'endpoint', path, payloadString);
  const provider = optional(source, 'provider', path, payloadString);
  const family = optional(source, 'family', path, payloadString);
  const role = optional(source, 'role', path, payloadString);
  const endpointStatus = optional(source, 'endpointStatus', path, payloadString);
  const workerClass = optional(source, 'workerClass', path, payloadString);
  const summary = optional(source, 'summary', path, payloadString);
  const area = optional(source, 'area', path, payloadString);
  const eventId = optional(source, 'eventId', path, payloadString);
  const eventType = optional(source, 'eventType', path, payloadString);
  const actor = optional(source, 'actor', path, payloadString);
  const task = optional(source, 'task', path, payloadString);
  const entity = optional(source, 'entity', path, payloadString);
  const assessment = optional(source, 'assessment', path, payloadString);
  const blockingIssue = optional(source, 'blockingIssue', path, payloadString);
  const reason = optional(source, 'reason', path, payloadString);
  const synthesis = optional(source, 'synthesis', path, payloadString);
  const candidate = optional(source, 'candidate', path, payloadString);
  const narration = optional(source, 'narration', path, payloadString);
  const decision = optional(source, 'decision', path, (item, itemPath) =>
    payloadEnum(item, itemPath, QUORUM_VOTE_DECISIONS),
  );
  const action = optional(source, 'action', path, (item, itemPath) =>
    payloadEnum(item, itemPath, QUORUM_ACTIONS),
  );
  const confidence = optional(source, 'confidence', path, (item, itemPath) =>
    payloadNumber(item, itemPath, { min: 0, max: 1 }),
  );
  const schemaValid = optional(source, 'schemaValid', path, payloadBoolean);
  const reasoningBlockDetected = optional(
    source,
    'reasoningBlockDetected',
    path,
    payloadBoolean,
  );
  const reasoningBlockRemoved = optional(
    source,
    'reasoningBlockRemoved',
    path,
    payloadBoolean,
  );
  const integer = (item: unknown, itemPath: string): number =>
    payloadNumber(item, itemPath, { integer: true, min: 0 });
  const validVotes = optional(source, 'validVotes', path, integer);
  const providerCount = optional(source, 'providerCount', path, integer);
  const familyCount = optional(source, 'familyCount', path, integer);
  const modelCount = optional(source, 'modelCount', path, integer);
  const concurrencyMax = optional(source, 'concurrencyMax', path, integer);
  const executionCount = optional(source, 'executionCount', path, integer);
  const availableCount = optional(source, 'availableCount', path, integer);
  const runtimeRevision = optional(source, 'runtimeRevision', path, integer);
  const tally = optional(source, 'tally', path, (item, itemPath) => {
    const counts = payloadRecord(item, itemPath);
    const parsed: Partial<Record<QuorumVoteDecision, number>> = {};
    for (const [key, count] of Object.entries(counts)) {
      const vote = payloadEnum(key, `${itemPath}.${key}`, QUORUM_VOTE_DECISIONS);
      parsed[vote] = payloadNumber(count, `${itemPath}.${key}`, {
        integer: true,
        min: 0,
      });
    }
    return parsed;
  });

  return {
    ...(panelId === undefined ? {} : { panelId }),
    ...(endpoint === undefined ? {} : { endpoint }),
    ...(provider === undefined ? {} : { provider }),
    ...(family === undefined ? {} : { family }),
    ...(role === undefined ? {} : { role }),
    ...(endpointStatus === undefined ? {} : { endpointStatus }),
    ...(workerClass === undefined ? {} : { workerClass }),
    ...(summary === undefined ? {} : { summary }),
    ...(area === undefined ? {} : { area }),
    ...(concurrencyMax === undefined ? {} : { concurrencyMax }),
    ...(eventId === undefined ? {} : { eventId }),
    ...(eventType === undefined ? {} : { eventType }),
    ...(actor === undefined ? {} : { actor }),
    ...(task === undefined ? {} : { task }),
    ...(entity === undefined ? {} : { entity }),
    ...(assessment === undefined ? {} : { assessment }),
    ...(blockingIssue === undefined ? {} : { blockingIssue }),
    ...(reason === undefined ? {} : { reason }),
    ...(synthesis === undefined ? {} : { synthesis }),
    ...(candidate === undefined ? {} : { candidate }),
    ...(narration === undefined ? {} : { narration }),
    ...(decision === undefined ? {} : { decision }),
    ...(action === undefined ? {} : { action }),
    ...(confidence === undefined ? {} : { confidence }),
    ...(schemaValid === undefined ? {} : { schemaValid }),
    ...(reasoningBlockDetected === undefined ? {} : { reasoningBlockDetected }),
    ...(reasoningBlockRemoved === undefined ? {} : { reasoningBlockRemoved }),
    ...(validVotes === undefined ? {} : { validVotes }),
    ...(providerCount === undefined ? {} : { providerCount }),
    ...(familyCount === undefined ? {} : { familyCount }),
    ...(modelCount === undefined ? {} : { modelCount }),
    ...(executionCount === undefined ? {} : { executionCount }),
    ...(availableCount === undefined ? {} : { availableCount }),
    ...(runtimeRevision === undefined ? {} : { runtimeRevision }),
    ...(tally === undefined ? {} : { tally }),
  };
}

function parseClaim(value: unknown, path: string): ProjectionClaim {
  const source = payloadRecord(value, path);
  return {
    id: payloadString(source.id, `${path}.id`),
    statement: payloadString(source.statement, `${path}.statement`),
    status: payloadEnum(source.status, `${path}.status`, CLAIM_STATUSES),
    evidence: payloadNullableString(source.evidence, `${path}.evidence`),
  };
}

function parseNode(value: unknown, path: string): ProjectionNode {
  const source = payloadRecord(value, path);
  const kind = payloadEnum(source.kind, `${path}.kind`, ENTITY_KINDS);
  const layer = payloadEnum(source.layer, `${path}.layer`, LAYERS);
  const epistemic = EPISTEMIC_KINDS.includes(kind as EpistemicKind);
  if ((epistemic && layer !== 'epistemic') || (!epistemic && layer !== 'operational')) {
    throw new PayloadError(`${path}.layer`, `incompatível com kind=${kind}`);
  }
  const visual = payloadRecord(source.visual, `${path}.visual`);
  const claims =
    source.claims === undefined
      ? undefined
      : payloadArray(source.claims, `${path}.claims`).map((claim, index) =>
          parseClaim(claim, `${path}.claims[${index}]`),
        );
  const claimCount = payloadNumber(source.claimCount, `${path}.claimCount`, {
    integer: true,
    min: 0,
  });
  if (claims !== undefined && claims.length !== claimCount) {
    throw new PayloadError(`${path}.claimCount`, `declarado ${claimCount}, recebido ${claims.length}`);
  }
  const summary = optional(source, 'summary', path, payloadNullableString);
  const operational = optional(source, 'operational', path, parseOperational);
  return {
    id: payloadString(source.id, `${path}.id`),
    title: payloadString(source.title, `${path}.title`),
    shortLabel: payloadString(source.shortLabel, `${path}.shortLabel`),
    path: payloadNullableString(source.path, `${path}.path`),
    kind,
    layer,
    canonicalState: payloadEnum(
      source.canonicalState,
      `${path}.canonicalState`,
      CANONICAL_STATES,
    ),
    epistemicStatus: payloadEnum(
      source.epistemicStatus,
      `${path}.epistemicStatus`,
      EPISTEMIC_STATUSES,
    ),
    domainId: payloadString(source.domainId, `${path}.domainId`),
    domainLabel: payloadString(source.domainLabel, `${path}.domainLabel`),
    anchorMocId: payloadNullableString(source.anchorMocId, `${path}.anchorMocId`),
    mocIds: payloadStringArray(source.mocIds, `${path}.mocIds`),
    claimCount,
    ...(summary === undefined ? {} : { summary }),
    ...(claims === undefined ? {} : { claims }),
    incomingDegree: payloadNumber(source.incomingDegree, `${path}.incomingDegree`, {
      integer: true,
      min: 0,
    }),
    outgoingDegree: payloadNumber(source.outgoingDegree, `${path}.outgoingDegree`, {
      integer: true,
      min: 0,
    }),
    degreeByRelation: payloadCountMap(source.degreeByRelation, `${path}.degreeByRelation`),
    createdAt: payloadNullableDate(source.createdAt, `${path}.createdAt`),
    updatedAt: payloadNullableDate(source.updatedAt, `${path}.updatedAt`),
    verifiedAt: payloadNullableDate(source.verifiedAt, `${path}.verifiedAt`),
    visual: {
      paletteToken: payloadString(visual.paletteToken, `${path}.visual.paletteToken`),
      lodClass: payloadNumber(visual.lodClass, `${path}.visual.lodClass`, {
        integer: true,
        min: 0,
      }),
      labelPriority: payloadNumber(visual.labelPriority, `${path}.visual.labelPriority`, {
        integer: true,
        min: 0,
      }),
      isAnchor: payloadBoolean(visual.isAnchor, `${path}.visual.isAnchor`),
    },
    ...(operational === undefined ? {} : { operational }),
  };
}

function parseDirectionWeights(
  value: unknown,
  path: string,
): { forward: number; backward: number } {
  const source = payloadRecord(value, path);
  return {
    forward: payloadNumber(source.forward, `${path}.forward`, { integer: true, min: 0 }),
    backward: payloadNumber(source.backward, `${path}.backward`, { integer: true, min: 0 }),
  };
}

function parseDirectionRelations(
  value: unknown,
  path: string,
): { forward: RelationFamily[]; backward: RelationFamily[] } {
  const source = payloadRecord(value, path);
  return {
    forward: payloadEnumArray(source.forward, `${path}.forward`, RELATION_FAMILIES),
    backward: payloadEnumArray(source.backward, `${path}.backward`, RELATION_FAMILIES),
  };
}

function parseEdge(value: unknown, path: string): ProjectionEdge {
  const source = payloadRecord(value, path);
  const kind = payloadEnum(source.kind, `${path}.kind`, EDGE_KINDS);
  const layer = payloadEnum(source.layer, `${path}.layer`, LAYERS);
  const expectedLayer = kind === 'operational' ? 'operational' : 'epistemic';
  if (layer !== expectedLayer) {
    throw new PayloadError(`${path}.layer`, `incompatível com kind=${kind}`);
  }
  const relations = payloadEnumArray(source.relations, `${path}.relations`, RELATION_FAMILIES);
  const primaryRelation =
    source.primaryRelation === null
      ? null
      : payloadEnum(source.primaryRelation, `${path}.primaryRelation`, RELATION_FAMILIES);
  if (primaryRelation !== null && !relations.includes(primaryRelation)) {
    throw new PayloadError(`${path}.primaryRelation`, 'não aparece em relations');
  }
  const weightByDirection = optional(
    source,
    'weightByDirection',
    path,
    parseDirectionWeights,
  );
  const relationsByDirection = optional(
    source,
    'relationsByDirection',
    path,
    parseDirectionRelations,
  );
  const reciprocal = optional(source, 'reciprocal', path, payloadBoolean);
  return {
    source: payloadString(source.source, `${path}.source`),
    target: payloadString(source.target, `${path}.target`),
    kind,
    layer,
    relations,
    primaryRelation,
    weight: payloadNumber(source.weight, `${path}.weight`, { integer: true, min: 1 }),
    matchedBy: payloadString(source.matchedBy, `${path}.matchedBy`),
    ...(weightByDirection === undefined ? {} : { weightByDirection }),
    ...(relationsByDirection === undefined ? {} : { relationsByDirection }),
    ...(reciprocal === undefined ? {} : { reciprocal }),
  };
}

function parseMeta(value: unknown, path: string): ProjectionMeta {
  const source = payloadRecord(value, path);
  const domains = payloadArray(source.domains, `${path}.domains`).map((item, index) => {
    const domainPath = `${path}.domains[${index}]`;
    const domain = payloadRecord(item, domainPath);
    return {
      id: payloadString(domain.id, `${domainPath}.id`),
      label: payloadString(domain.label, `${domainPath}.label`),
      paletteToken: payloadString(domain.paletteToken, `${domainPath}.paletteToken`),
      mocIds: payloadStringArray(domain.mocIds, `${domainPath}.mocIds`),
    };
  });
  payloadUnique(
    domains.map((domain) => domain.id),
    `${path}.domains`,
  );
  const counts = payloadRecord(source.counts, `${path}.counts`);
  const nonnegativeInteger = (key: string): number =>
    payloadNumber(counts[key], `${path}.counts.${key}`, { integer: true, min: 0 });
  const diagnostics = payloadRecord(source.diagnostics, `${path}.diagnostics`);
  return {
    contractVersion: payloadString(source.contractVersion, `${path}.contractVersion`),
    generatedAt: payloadDate(source.generatedAt, `${path}.generatedAt`),
    source: payloadEnum(source.source, `${path}.source`, ['corpus', 'demo']),
    operationalSource: payloadEnum(source.operationalSource, `${path}.operationalSource`, [
      'none',
      'demo',
      'quorum',
      'mixed',
    ]),
    operationalKinds: payloadEnumArray(
      source.operationalKinds,
      `${path}.operationalKinds`,
      OPERATIONAL_KINDS,
    ),
    corpusFingerprint: (() => {
      const fingerprint = payloadString(source.corpusFingerprint, `${path}.corpusFingerprint`);
      if (!FINGERPRINT.test(fingerprint)) {
        throw new PayloadError(`${path}.corpusFingerprint`, 'esperado SHA-256 minúsculo');
      }
      return fingerprint;
    })(),
    computedFields: (() => {
      const fields = payloadStringArray(source.computedFields, `${path}.computedFields`);
      payloadUnique(fields, `${path}.computedFields`);
      return fields;
    })(),
    relationFamilies: payloadEnumArray(
      source.relationFamilies,
      `${path}.relationFamilies`,
      RELATION_FAMILIES,
    ),
    domains,
    counts: {
      notes: nonnegativeInteger('notes'),
      operationalNodes: nonnegativeInteger('operationalNodes'),
      canonicalEdges: nonnegativeInteger('canonicalEdges'),
      aggregatedEdges: nonnegativeInteger('aggregatedEdges'),
      wikilinks: nonnegativeInteger('wikilinks'),
      claims: nonnegativeInteger('claims'),
      mocs: nonnegativeInteger('mocs'),
    },
    diagnostics: {
      broken: [...payloadArray(diagnostics.broken, `${path}.diagnostics.broken`)],
      undeclared: [...payloadArray(diagnostics.undeclared, `${path}.diagnostics.undeclared`)],
      collisions: {
        ...payloadRecord(diagnostics.collisions, `${path}.diagnostics.collisions`),
      },
    },
  };
}

function assertDeclaredCount(path: string, declared: number, actual: number): void {
  if (declared !== actual) {
    throw new PayloadError(path, `declarado ${declared}, calculado ${actual}`);
  }
}

/** Constrói uma projeção nova a partir de JSON desconhecido antes de expô-la à cena. */
export function parseProjection(value: unknown): Projection {
  try {
    const source = payloadRecord(value, '$');
    const meta = parseMeta(source.meta, '$.meta');
    assertSupported(meta);
    const nodes = payloadArray(source.nodes, '$.nodes').map((item, index) =>
      parseNode(item, `$.nodes[${index}]`),
    );
    const edges = payloadArray(source.edges, '$.edges').map((item, index) =>
      parseEdge(item, `$.edges[${index}]`),
    );
    payloadUnique(
      nodes.map((node) => node.id),
      '$.nodes',
    );
    payloadUnique(
      nodes.flatMap((node) => node.claims?.map((claim) => claim.id) ?? []),
      '$.nodes[*].claims',
    );
    const projection = { meta, nodes, edges };
    assertConsistent(projection);

    assertDeclaredCount(
      '$.meta.counts.notes',
      meta.counts.notes,
      nodes.filter((node) => node.layer === 'epistemic').length,
    );
    assertDeclaredCount(
      '$.meta.counts.operationalNodes',
      meta.counts.operationalNodes,
      nodes.filter((node) => node.layer === 'operational').length,
    );
    assertDeclaredCount(
      '$.meta.counts.canonicalEdges',
      meta.counts.canonicalEdges,
      edges.filter((edge) => edge.kind === 'canonical').length,
    );
    assertDeclaredCount(
      '$.meta.counts.aggregatedEdges',
      meta.counts.aggregatedEdges,
      edges.filter((edge) => edge.kind === 'aggregated').length,
    );
    assertDeclaredCount(
      '$.meta.counts.wikilinks',
      meta.counts.wikilinks,
      edges
        .filter((edge) => edge.kind === 'canonical')
        .reduce((sum, edge) => sum + edge.weight, 0),
    );
    assertDeclaredCount(
      '$.meta.counts.claims',
      meta.counts.claims,
      nodes.reduce((sum, node) => sum + node.claimCount, 0),
    );
    assertDeclaredCount(
      '$.meta.counts.mocs',
      meta.counts.mocs,
      nodes.filter((node) => node.kind === 'moc').length,
    );
    return projection;
  } catch (error) {
    if (error instanceof ContractError) throw error;
    if (error instanceof PayloadError) throw new ContractError(error.message);
    throw error;
  }
}

/** Rejeita uma projeção cuja major não é a que esta cena sabe desenhar. */
export function assertSupported(meta: ProjectionMeta): void {
  const major = Number.parseInt(meta.contractVersion.split('.')[0] ?? '', 10);
  if (!Number.isFinite(major)) {
    throw new ContractError(`contractVersion ilegível: ${meta.contractVersion}`);
  }
  if (major !== SUPPORTED_CONTRACT_MAJOR) {
    throw new ContractError(
      `contrato v${meta.contractVersion} incompatível com esta cena ` +
        `(esperado v${SUPPORTED_CONTRACT_MAJOR}.x). Atualize o frontend.`,
    );
  }
}

/**
 * Verificação estrutural mínima antes de desenhar.
 *
 * Uma aresta apontando para um nó inexistente não é um detalhe estético: ela vira
 * uma linha para as coordenadas de origem, e o atlas passa a mostrar uma relação
 * que o corpus não tem.
 */
export function assertConsistent(projection: Projection): void {
  const ids = new Set(projection.nodes.map((node) => node.id));
  const soltas = projection.edges.filter(
    (edge) => !ids.has(edge.source) || !ids.has(edge.target),
  );
  if (soltas.length > 0) {
    const exemplo = soltas[0]!;
    throw new ContractError(
      `${soltas.length} aresta(s) apontam para fora do conjunto de nós, ` +
        `por exemplo ${exemplo.source} → ${exemplo.target}`,
    );
  }
  for (const node of projection.nodes) assertOperationalMetadata(node);
}

const OPERATIONAL_METADATA_KEYS = new Set([
  'panelId',
  'decision',
  'action',
  'confidence',
  'tally',
  'endpoint',
  'provider',
  'family',
  'role',
  'schemaValid',
  'validVotes',
  'providerCount',
  'familyCount',
  // Registro de modelos: contagens derivadas das arestas já emitidas pelo backend, e
  // nunca de texto produzido por modelo.
  'modelCount',
  'executionCount',
  'availableCount',
  'endpointStatus',
  // O papel do trabalho, como identidade: classe, resumo, área e teto de simultâneas.
  // Nada aqui é estado de execução — esse vem do painel de controle, que responde agora.
  'workerClass',
  'summary',
  'area',
  'concurrencyMax',
  'eventId',
  'runtimeRevision',
  'eventType',
  'actor',
  'task',
  'entity',
  'reasoningBlockDetected',
  'reasoningBlockRemoved',
  // A deliberação em linguagem natural. Todos passam pelo sanitizador do backend, que
  // recusa bloco de raciocínio e qualquer coisa com forma de segredo — o requisito é
  // processo observável, não cadeia privada de pensamento.
  'assessment',
  'blockingIssue',
  'reason',
  'synthesis',
  'candidate',
  'narration',
]);
const FORBIDDEN_OPERATIONAL_TEXT = /<\s*\/?\s*think\b|raw_response/i;

function assertOperationalMetadata(node: ProjectionNode): void {
  if (!node.operational) {
    if (node.kind.startsWith('quorum-')) {
      throw new ContractError(`${node.id}: entidade de quórum sem metadado operacional`);
    }
    return;
  }
  if (node.layer !== 'operational') {
    throw new ContractError(`${node.id}: metadado operacional numa entidade epistêmica`);
  }
  const metadata = node.operational as Record<string, unknown>;
  const unknown = Object.keys(metadata).filter((key) => !OPERATIONAL_METADATA_KEYS.has(key));
  if (unknown.length > 0) {
    throw new ContractError(`${node.id}: metadado operacional fora da lista branca: ${unknown[0]}`);
  }
  for (const key of [
    'panelId',
    'endpoint',
    'provider',
    'family',
    'role',
    'eventId',
    'eventType',
    'actor',
    'task',
    'entity',
    'endpointStatus',
    'workerClass',
    'summary',
    'area',
    'assessment',
    'blockingIssue',
    'reason',
    'synthesis',
    'candidate',
    'narration',
  ] as const) {
    const value = metadata[key];
    if (
      value !== undefined &&
      (typeof value !== 'string' || value.length === 0 || FORBIDDEN_OPERATIONAL_TEXT.test(value))
    ) {
      throw new ContractError(`${node.id}: ${key} operacional inválido`);
    }
  }
  if (
    metadata.runtimeRevision !== undefined &&
    (typeof metadata.runtimeRevision !== 'number' ||
      !Number.isSafeInteger(metadata.runtimeRevision) ||
      metadata.runtimeRevision < 0)
  ) {
    throw new ContractError(`${node.id}: revisão operacional inválida`);
  }
  if (
    metadata.decision !== undefined &&
    !QUORUM_VOTE_DECISIONS.includes(metadata.decision as QuorumVoteDecision)
  ) {
    throw new ContractError(`${node.id}: voto operacional inválido`);
  }
  if (metadata.action !== undefined && !QUORUM_ACTIONS.includes(metadata.action as QuorumAction)) {
    throw new ContractError(`${node.id}: ação operacional inválida`);
  }
  if (
    metadata.confidence !== undefined &&
    (typeof metadata.confidence !== 'number' ||
      !Number.isFinite(metadata.confidence) ||
      metadata.confidence < 0 ||
      metadata.confidence > 1)
  ) {
    throw new ContractError(`${node.id}: confiança operacional fora de 0..1`);
  }
  for (const key of ['reasoningBlockDetected', 'reasoningBlockRemoved'] as const) {
    if (metadata[key] !== undefined && typeof metadata[key] !== 'boolean') {
      throw new ContractError(`${node.id}: ${key} precisa ser booleano`);
    }
  }
  if (metadata.schemaValid !== undefined && typeof metadata.schemaValid !== 'boolean') {
    throw new ContractError(`${node.id}: schemaValid precisa ser booleano`);
  }
  for (const key of [
    'validVotes',
    'providerCount',
    'familyCount',
    'modelCount',
    'executionCount',
    'availableCount',
  ] as const) {
    const value = metadata[key];
    if (
      value !== undefined &&
      (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0)
    ) {
      throw new ContractError(`${node.id}: ${key} operacional inválido`);
    }
  }
  if (metadata.tally !== undefined) {
    if (typeof metadata.tally !== 'object' || metadata.tally === null) {
      throw new ContractError(`${node.id}: contagem operacional inválida`);
    }
    for (const [decision, count] of Object.entries(metadata.tally)) {
      if (
        !QUORUM_VOTE_DECISIONS.includes(decision as QuorumVoteDecision) ||
        typeof count !== 'number' ||
        !Number.isInteger(count) ||
        count < 0
      ) {
        throw new ContractError(`${node.id}: contagem operacional inválida`);
      }
    }
  }
  const required: Partial<Record<OperationalKind, string[]>> = {
    'quorum-panel': ['panelId'],
    // O membro deixou de ser uma placa por execução e virou o modelo canônico do
    // registro: ele não pertence a um painel, então `panelId` sai da exigência. Quem
    // participou de qual execução continua dito pela aresta, que é onde isso é verdade.
    'quorum-member': ['provider', 'endpoint'],
    'quorum-vote': [
      'panelId',
      'provider',
      'endpoint',
      'family',
      'decision',
      'confidence',
    ],
    'quorum-decision': ['panelId', 'action', 'tally'],
  };
  for (const key of required[node.kind as OperationalKind] ?? []) {
    if (metadata[key] === undefined) {
      throw new ContractError(`${node.id}: ${node.kind} sem ${key}`);
    }
  }
}

export interface LoadedProjection {
  projection: Projection;
  origin: string;
}

const STATIC_SOURCE = '/projection.json';
export const BACKEND_SOURCE = '/corpus/projection';
const BACKEND_EVENTS = '/corpus/events';
const FINGERPRINT = /^[0-9a-f]{64}$/;

interface CorpusEventPayload {
  fingerprint: string | null;
  revision: number;
  detail: string | null;
}

/** Só uma impressão SHA-256 diferente pode invalidar a cena já carregada. */
export function shouldReloadProjection(current: string, candidate: unknown): candidate is string {
  return typeof candidate === 'string' && FINGERPRINT.test(candidate) && candidate !== current;
}

export function isBackendProjectionOrigin(origin: string): boolean {
  return origin === BACKEND_SOURCE;
}

/** Um `current` válido prova que o backend tem uma projeção pronta para servir. */
export function shouldReplaceStaticProjection(
  origin: string,
  currentFingerprint: unknown,
): boolean {
  return (
    !isBackendProjectionOrigin(origin) &&
    typeof currentFingerprint === 'string' &&
    FINGERPRINT.test(currentFingerprint)
  );
}

export function parseCorpusEventPayload(value: unknown): CorpusEventPayload {
  const source = payloadRecord(value, '$');
  const fingerprint =
    source.fingerprint === null
      ? null
      : payloadString(source.fingerprint, '$.fingerprint');
  if (fingerprint !== null && !FINGERPRINT.test(fingerprint)) {
    throw new PayloadError('$.fingerprint', 'esperado SHA-256 minúsculo ou null');
  }
  const detail = source.detail === null ? null : payloadText(source.detail, '$.detail');
  return {
    fingerprint,
    revision: payloadNumber(source.revision, '$.revision', { integer: true, min: 0 }),
    detail,
  };
}

/**
 * Observa a projeção viva, inclusive enquanto o arquivo estático sustenta a cena.
 * A abertura do transporte não basta para declarar recuperação: `onCurrent` só é
 * chamado depois de validar o envelope e o fingerprint enviados pelo backend.
 */
export function watchProjection(
  currentFingerprint: string,
  onChange: (fingerprint: string) => void,
  onError: (detail: string) => void,
  options: {
    signal?: AbortSignal;
    onConnectionStatus?: (status: BackendConnectionStatus) => void;
    onCurrent?: (fingerprint: string) => void;
  } = {},
): () => void {
  if (typeof EventSource === 'undefined') return () => undefined;

  const events = openBackendEvents(BACKEND_EVENTS, {
    signal: options.signal,
    onStatus: options.onConnectionStatus,
  });
  const source = events.source;
  let reloadRequested = false;
  const parseEvent = (
    event: Event,
    kind: 'current' | 'changed' | 'error' | 'recovered',
  ): CorpusEventPayload | null => {
    // O `error` nativo do EventSource não traz `data`: ele indica transporte e deixa
    // a reconexão automática trabalhar. Mensagem com `data`, por outro lado, é parte
    // do contrato do watcher e precisa ser validada.
    if (!(event instanceof MessageEvent) || typeof event.data !== 'string') return null;
    try {
      const payload = parseCorpusEventPayload(JSON.parse(event.data) as unknown);
      if ((kind === 'current' || kind === 'changed') && payload.fingerprint === null) {
        throw new PayloadError('$.fingerprint', `obrigatório em evento ${kind}`);
      }
      return payload;
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      onError(`evento ${kind} inválido (${detail}); projeção atual preservada.`);
      return null;
    }
  };
  const handleFingerprint = (event: Event): void => {
    const kind = event.type === 'changed' ? 'changed' : 'current';
    const candidate = parseEvent(event, kind)?.fingerprint;
    if (kind === 'current' && candidate !== null && candidate !== undefined) {
      options.onCurrent?.(candidate);
    }
    if (!reloadRequested && shouldReloadProjection(currentFingerprint, candidate)) {
      reloadRequested = true;
      onChange(candidate);
    }
  };
  const handleError = (event: Event): void => {
    // A fila do servidor é limitada. Mesmo que um erro posterior compacte um
    // `changed`, seu fingerprint ainda carrega a revisão viva e exige recarga.
    const payload = parseEvent(event, 'error');
    const candidate = payload?.fingerprint;
    if (!reloadRequested && shouldReloadProjection(currentFingerprint, candidate)) {
      reloadRequested = true;
      onChange(candidate);
    }
    const detail = payload?.detail;
    // Eventos nativos de desconexão também se chamam ``error``. Sem payload do
    // watcher eles não alegam que o corpus está inválido; o EventSource reconecta.
    if (typeof detail === 'string' && detail.length > 0) onError(detail);
  };
  const handleRecovery = (event: Event): void => {
    const detail = parseEvent(event, 'recovered')?.detail;
    if (typeof detail === 'string' && detail.length > 0) onError(detail);
  };

  source.addEventListener('current', handleFingerprint);
  source.addEventListener('changed', handleFingerprint);
  source.addEventListener('error', handleError);
  source.addEventListener('recovered', handleRecovery);
  return events.close;
}

/**
 * Carrega a projeção, preferindo o backend ao arquivo gerado.
 *
 * As duas origens são o mesmo corpus real; nenhuma delas é demonstração, e não há
 * caminho de código que caia para dados de exemplo quando o corpus falha. Qual
 * origem respondeu fica registrado e é exibido, porque um arquivo gerado ontem e um
 * backend de agora podem discordar, e o usuário precisa saber qual está vendo.
 */
export async function loadProjection(signal?: AbortSignal): Promise<LoadedProjection> {
  const falhas: string[] = [];
  for (const origin of [BACKEND_SOURCE, STATIC_SOURCE]) {
    try {
      const init: RequestInit = {
        ...(origin === BACKEND_SOURCE ? { cache: 'no-store' as const } : {}),
        ...(signal === undefined ? {} : { signal }),
      };
      const response = await backendFetch(origin, init);
      if (!response.ok) {
        falhas.push(`${origin}: HTTP ${response.status}`);
        continue;
      }
      const projection = parseProjection(await response.json());
      return { projection, origin };
    } catch (error) {
      if (signal?.aborted) throw (signal.reason ?? error);
      if (error instanceof ContractError) throw error;
      falhas.push(`${origin}: ${String(error)}`);
    }
  }
  throw new ContractError(
    `nenhuma origem de projeção respondeu.\n${falhas.join('\n')}\n` +
      'Rode `make corpus-graph` ou suba o backend com `make backend`.',
  );
}

/**
 * O corpo canônico de uma nota, buscado **sob demanda**.
 *
 * A projeção não o leva de propósito: ela é servida inteira a cada abertura, e embutir os
 * 84 corpos nela multiplicaria o que trafega para que um único painel — o que estiver
 * aberto — use um deles. Aqui se busca um por vez, que é quantos se leem por vez.
 *
 * A identidade de uma nota tem barras (`Cognição/Memória`), e cada segmento é escapado
 * separadamente: `encodeURIComponent` sobre o todo escaparia também as barras, e o
 * caminho deixaria de casar com a rota.
 */
export async function loadNoteDocument(
  reference: string,
  signal?: AbortSignal,
): Promise<string> {
  const caminho = reference
    .split('/')
    .filter((parte) => parte !== '')
    .map(encodeURIComponent)
    .join('/');
  if (caminho === '') throw new ContractError('referência de nota vazia');
  const response = await backendFetch(`/corpus/documents/${caminho}`, {
    ...(signal === undefined ? {} : { signal }),
  });
  if (!response.ok) {
    throw new ContractError(`documento de ${reference}: HTTP ${response.status}`);
  }
  const corpo = payloadRecord(await response.json(), '$');
  return payloadText(corpo.body, '$.body');
}
