// Camada tridimensional do event log operacional.
//
// Ela é deliberadamente separada da projeção canônica: atualizar o relógio do
// runtime substitui apenas este grupo, sem recalcular posições do corpus, mover a
// câmera ou alegar que atividade operacional virou conhecimento.

import * as THREE from 'three';

import {
  OPERATIONAL_KINDS,
  type CanonicalState,
  type OperationalKind,
  type OperationalMetadata,
  type Projection,
  type ProjectionEdge,
  type ProjectionNode,
} from './contract';
import { trimEdge } from './edgePath';
import { buildRelationLines } from './edges';
import { createFlowMaterial, flowAttributes, type FlowMaterial } from './runtimeFlow';
import { hash32, layoutAtlas, type LayoutMap, type Vec3 } from './layout';
import { createPanelBodies, type PanelBodies } from './panelBodies';
import { providerToken } from './palette';
import { panelSweepRadii } from './panelScale';
import type { PanelDescriptor } from './panels';
import type { CognitionFrame } from './cognition';
import {
  diffWorkers,
  workerNodeId,
  type RuntimeWorker,
} from './workerEntities';
import {
  advanceMotion,
  motionStartPositions,
  preserveAnchorTargets,
} from './semanticMotion';
import {
  cognitiveStates,
  describeCognitiveState,
  observableCognitiveWork,
  withCognition,
  type CognitiveStatus,
} from './cognitiveState';
import {
  runtimeEventLabel,
  type RuntimeEventType,
  type RuntimeSnapshot,
} from './runtime';
import {
  MORPH_AMPLITUDE_FRACTION,
  aplicarMorfologia,
  direcaoPara,
  sinaisOperacionais,
} from './operationalMotion';

const KIND_BY_EVENT: Record<RuntimeEventType, OperationalKind> = {
  task_created: 'activity',
  task_assigned: 'activity',
  call_started: 'activity',
  call_completed: 'activity',
  temporary_created: 'temporary-file',
  temporary_discarded: 'temporary-file',
  evidence_recorded: 'evidence',
  proposal_created: 'proposal',
  quorum_started: 'quorum-panel',
  // Pedir voto é **ação**, não avaliador. Enquanto era `quorum-member`, o painel de um
  // pedido de voto tinha a mesma forma e o mesmo tipo de um modelo do registro, e a
  // hierarquia da nuvem viva não tinha como distinguir os dois.
  vote_requested: 'activity',
  vote_received: 'quorum-vote',
  quorum_decided: 'quorum-decision',
  promotion_started: 'activity',
  promotion_completed: 'activity',
  commit_created: 'commit',
  corpus_changed: 'commit',
};

const STATE_BY_KIND: Record<OperationalKind, CanonicalState> = {
  agent: 'temporary',
  activity: 'temporary',
  evidence: 'temporary',
  proposal: 'proposed',
  commit: 'canonical',
  rejection: 'rejected',
  'temporary-file': 'temporary',
  'quorum-panel': 'temporary',
  'quorum-member': 'temporary',
  'quorum-vote': 'temporary',
  'quorum-decision': 'temporary',
};

const PALETTE_BY_KIND: Record<OperationalKind, string> = {
  agent: 'D06',
  activity: 'D06',
  evidence: 'D05',
  proposal: 'D09',
  commit: 'D04',
  rejection: 'D01',
  'temporary-file': 'D03',
  'quorum-panel': 'D08',
  'quorum-member': 'D06',
  'quorum-vote': 'D06',
  'quorum-decision': 'D04',
};

function visualNode(
  id: string,
  kind: OperationalKind,
  title: string,
  shortLabel: string,
  timestamp: string,
  operational: OperationalMetadata,
  /**
   * A cor, quando ela não vem do tipo do nó.
   *
   * Provedor e modelo são os dois nós que **têm dono**, e a cor deles é a da marca —
   * é ela que faz reconhecer de longe quem está atendendo, sem ler a placa. O resto da
   * camada viva continua colorido pelo que é, não por quem serviu.
   */
  paletteToken?: string,
  isAnchor = false,
): ProjectionNode {
  return {
    id,
    title,
    shortLabel,
    path: null,
    kind,
    layer: 'operational',
    canonicalState: STATE_BY_KIND[kind],
    epistemicStatus: 'not-specified',
    domainId: 'operacional/live',
    domainLabel: 'operação ao vivo',
    anchorMocId: null,
    mocIds: [],
    claimCount: 0,
    incomingDegree: 0,
    outgoingDegree: 0,
    degreeByRelation: {},
    createdAt: timestamp,
    updatedAt: timestamp,
    verifiedAt: null,
    visual: {
      paletteToken: paletteToken ?? PALETTE_BY_KIND[kind],
      lodClass: 1,
      labelPriority: 1,
      isAnchor,
    },
    operational,
  };
}

/**
 * Quem executou um evento, como identidade estável da nuvem viva.
 *
 * A âncora era o **ator** — `autonomous-worker` para quase tudo —, então 167 eventos
 * pendiam de dois ou três nós e a nuvem não dizia qual modelo estava trabalhando. Onde o
 * evento declara provedor e endpoint, a âncora passa a ser o modelo, e acima dele o
 * provedor: a mesma hierarquia de três níveis que o corpus tem em MOC → nota e que a
 * nuvem de modelos tem em provedor → modelo. Sem provedor declarado — tarefa criada pelo
 * worker, arquivo temporário — o ator continua sendo a âncora, porque é o que existe.
 */
function providerId(provider: string): string {
  return `runtime:provider:${provider}`;
}

function modelId(provider: string, endpoint: string): string {
  return `runtime:model:${provider}/${endpoint}`;
}

function eventNodeId(eventId: string): string {
  return `runtime:event:${eventId}`;
}

/**
 * Estado vivo derivado de aberturas e fechamentos reais da trilha.
 *
 * Recência não entra na conta. Os seis últimos eventos podem ter terminado há horas;
 * iluminá-los continuamente faria o Atlas afirmar trabalho onde existe apenas história.
 * Um modelo só está ativo enquanto `openCognitiveWork` conserva ao menos uma abertura
 * correlacionada sem fechamento. Um painel só está ativo entre a abertura e o fechamento
 * do seu ciclo de quórum ou promoção.
 */
export interface RuntimeActivity {
  activeNodeIds: ReadonlySet<string>;
  activePanelIds: ReadonlySet<string>;
}

function cognitiveFingerprint(states: ReadonlyMap<string, CognitiveStatus>): string {
  return JSON.stringify(
    [...states]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, status]) => [
        key,
        status.state,
        status.revision,
        status.narration,
        status.result,
      ]),
  );
}

const PANEL_OPEN_EVENTS: ReadonlySet<RuntimeEventType> = new Set([
  'quorum_started',
  'promotion_started',
]);
const PANEL_PROGRESS_EVENTS: ReadonlySet<RuntimeEventType> = new Set([
  'vote_requested',
  'vote_received',
]);
const PANEL_CLOSE_EVENTS: ReadonlySet<RuntimeEventType> = new Set([
  'quorum_decided',
  'promotion_completed',
]);

function activityFrom(snapshot: RuntimeSnapshot, now = Date.now()): RuntimeActivity {
  const activeNodeIds = new Set<string>();
  for (const work of observableCognitiveWork(snapshot, now)) {
    if (work.kind !== 'call') continue;
    activeNodeIds.add(modelId(work.provider, work.endpoint));
    activeNodeIds.add(eventNodeId(work.eventId));
  }

  // A abertura permanece sendo a evidência visual do ciclo inteiro e desaparece quando
  // a decisão o fecha. `vote_*` sem abertura visível recupera somente o `panelId` de um
  // snapshot cuja janela já descartou `quorum_started`.
  const aberturaPorPainel = new Map<
    string,
    { nodeId: string | null; task: string | null }
  >();
  for (const event of [...snapshot.events].sort((a, b) => a.revision - b.revision)) {
    if (
      event.task &&
      (event.type === 'task_assigned' ||
        (event.type === 'evidence_recorded' && !event.provider))
    ) {
      for (const [panelId, abertura] of aberturaPorPainel) {
        if (abertura.task === event.task) aberturaPorPainel.delete(panelId);
      }
    }
    const panelId = event.panelId;
    if (panelId === undefined) continue;
    if (PANEL_CLOSE_EVENTS.has(event.type)) {
      aberturaPorPainel.delete(panelId);
    } else if (PANEL_OPEN_EVENTS.has(event.type)) {
      aberturaPorPainel.set(panelId, {
        nodeId: eventNodeId(event.id),
        task: event.task ?? null,
      });
    } else if (PANEL_PROGRESS_EVENTS.has(event.type) && !aberturaPorPainel.has(panelId)) {
      // Uma janela truncada pode começar já no meio dos votos. Isso prova que o painel
      // ainda está aberto, mas não autoriza fingir que um voto já recebido continua em
      // execução; sem a abertura visível, só o painel persistido recebe o pulso.
      aberturaPorPainel.set(panelId, { nodeId: null, task: event.task ?? null });
    }
  }
  for (const { nodeId } of aberturaPorPainel.values()) {
    if (nodeId !== null) activeNodeIds.add(nodeId);
  }

  return {
    activeNodeIds,
    activePanelIds: new Set(aberturaPorPainel.keys()),
  };
}

export function runtimeActivity(snapshot: RuntimeSnapshot, now = Date.now()): RuntimeActivity {
  return activityFrom(snapshot, now);
}

function actorId(actor: string): string {
  const digest = Math.floor(hash32(actor, 20260804) * 0xffffffff)
    .toString(16)
    .padStart(8, '0');
  return `runtime:actor:${digest}`;
}

function operationalEdge(source: string, target: string): ProjectionEdge {
  return {
    source,
    target,
    kind: 'operational',
    layer: 'operational',
    relations: ['operational'],
    primaryRelation: 'operational',
    weight: 1,
    matchedBy: 'runtime-event',
  };
}

/** Projeção visual interna derivada só dos escalares validados em `runtime.ts`. */
export function projectRuntime(
  snapshot: RuntimeSnapshot,
  now?: number,
  frames: readonly CognitionFrame[] = [],
): Projection {
  // O estado temporal de cada modelo, lido da trilha antes de qualquer nó ser criado: é
  // ele que o painel do modelo passa a dizer, no lugar de repetir provedor e endpoint.
  // O canal cognitivo entra por cima, e só sobre quem a trilha já diz estar trabalhando:
  // ele descreve o agora, e não tem autoridade para afirmar estado depois que a chamada
  // fechou. Sem quadro nenhum, a leitura é exatamente a de antes.
  const estados = withCognition(cognitiveStates(snapshot, now), frames);
  const nodes: ProjectionNode[] = [];
  const edges: ProjectionEdge[] = [];
  const actors = new Map<string, string>();
  const lastByTask = new Map<string, string>();
  const lastByEntity = new Map<string, string>();
  const edgeKeys = new Set<string>();

  const connect = (source: string, target: string): void => {
    const key = `${source}\u0000${target}`;
    if (edgeKeys.has(key)) return;
    edgeKeys.add(key);
    edges.push(operationalEdge(source, target));
  };

  const providers = new Map<string, string>();
  const modelos = new Map<string, string>();

  for (const event of [...snapshot.events].sort((a, b) => a.revision - b.revision)) {
    const id = eventNodeId(event.id);
    // A entidade que o evento toca, dele ou **da tarefa dele**. Só o `task_created`
    // costuma declará-la, e ele quase sempre caiu fora da janela de 160 eventos: nos 160
    // mais recentes da trilha real, nenhum evento a declarava, e a camada viva não tinha
    // uma única linha para o corpus. Herdar da tarefa é o que a própria trilha afirma.
    const entidade = event.entity ?? (event.task ? snapshot.entityByTask.get(event.task) : undefined);
    // A âncora do evento: o modelo que o produziu, quando ele se declara; o ator, quando
    // não há modelo. É isto que dá à nuvem viva a hierarquia que ela não tinha.
    if (event.provider && event.endpoint) {
      let idProvedor = providers.get(event.provider);
      if (!idProvedor) {
        idProvedor = providerId(event.provider);
        providers.set(event.provider, idProvedor);
        nodes.push(
          visualNode(
            idProvedor,
            'agent',
            `Provedor — ${event.provider}`,
            event.provider,
            event.timestamp,
            { provider: event.provider },
            providerToken(event.provider) ?? undefined,
            true,
          ),
        );
      }
      const chaveDoModelo = `${event.provider}/${event.endpoint}`;
      let idModelo = modelos.get(chaveDoModelo);
      if (!idModelo) {
        idModelo = modelId(event.provider, event.endpoint);
        modelos.set(chaveDoModelo, idModelo);
        const estado = estados.get(chaveDoModelo);
        nodes.push(
          visualNode(
            idModelo,
            'quorum-member',
            `${event.provider} · ${event.endpoint}`,
            event.endpoint,
            event.timestamp,
            {
              provider: event.provider,
              endpoint: event.endpoint,
              // A frase do estado entra como narração porque é o que ela é: o que se sabe
              // estar acontecendo, dito em linguagem natural e vindo da própria trilha.
              //
              // Menos o repouso. "Sem trabalho aberto vigente" numa nuvem de modelos
              // parados é uma linha em cada placa para não dizer nada — a densidade que
              // a composição acabou de equalizar. A placa fala quando há o que falar.
              ...(estado && estado.state !== 'latent'
                ? { narration: describeCognitiveState(estado) }
                : {}),
            },
            providerToken(event.provider) ?? undefined,
          ),
        );
        connect(idModelo, idProvedor);
      }
      connect(idModelo, id);
    } else if (event.actor) {
      let idActor = actors.get(event.actor);
      if (!idActor) {
        idActor = actorId(event.actor);
        actors.set(event.actor, idActor);
        nodes.push(
          visualNode(
            idActor,
            'agent',
            event.actor,
            event.actor,
            event.timestamp,
            { actor: event.actor },
            undefined,
            true,
          ),
        );
      }
      connect(idActor, id);
    }

    const kind = KIND_BY_EVENT[event.type];
    // O assunto preferido é a entidade: um título com o nome da nota diz do que o evento
    // trata; um com o identificador da tarefa repete um hash.
    const subject = entidade ?? event.task ?? event.provider;
    const label = runtimeEventLabel(event.type);
    const panelId =
      event.panelId ??
      (event.type.startsWith('quorum_') || event.type.startsWith('vote_')
        ? (event.task ?? event.entity ?? event.id)
        : undefined);
    const operational: OperationalMetadata = {
      eventId: event.id,
      runtimeRevision: event.revision,
      eventType: event.type,
      ...(event.actor ? { actor: event.actor } : {}),
      ...(event.provider ? { provider: event.provider } : {}),
      ...(event.endpoint ? { endpoint: event.endpoint } : {}),
      ...(event.family ? { family: event.family } : {}),
      ...(event.role ? { role: event.role } : {}),
      ...(event.task ? { task: event.task } : {}),
      ...(entidade ? { entity: entidade } : {}),
      ...(event.narration ? { narration: event.narration } : {}),
      ...(panelId ? { panelId } : {}),
      ...(event.decision ? { decision: event.decision } : {}),
      ...(event.action ? { action: event.action } : {}),
      ...(event.confidence === undefined ? {} : { confidence: event.confidence }),
      ...(event.schemaValid === undefined ? {} : { schemaValid: event.schemaValid }),
      ...(event.validVotes === undefined ? {} : { validVotes: event.validVotes }),
      ...(event.providerCount === undefined ? {} : { providerCount: event.providerCount }),
      ...(event.familyCount === undefined ? {} : { familyCount: event.familyCount }),
      ...(event.tally ? { tally: event.tally } : {}),
    };
    nodes.push(
      visualNode(
        id,
        kind,
        subject ? `${label}: ${subject}` : label,
        label,
        event.timestamp,
        operational,
      ),
    );

    const predecessors = new Set<string>();
    if (event.task && lastByTask.has(event.task)) predecessors.add(lastByTask.get(event.task)!);
    if (entidade && lastByEntity.has(entidade)) {
      predecessors.add(lastByEntity.get(entidade)!);
    }
    for (const predecessor of predecessors) connect(predecessor, id);
    if (event.task) lastByTask.set(event.task, id);
    if (entidade) lastByEntity.set(entidade, id);
  }

  const ids = new Map(nodes.map((node) => [node.id, node]));
  for (const edge of edges) {
    ids.get(edge.source)!.outgoingDegree += 1;
    ids.get(edge.target)!.incomingDegree += 1;
  }

  return {
    meta: {
      contractVersion: '1.0.0',
      generatedAt: new Date(0).toISOString(),
      source: 'corpus',
      operationalSource: 'mixed',
      operationalKinds: [...OPERATIONAL_KINDS],
      corpusFingerprint: '0'.repeat(64),
      computedFields: ['runtime event trail'],
      relationFamilies: ['operational'],
      domains: [],
      counts: {
        notes: 0,
        operationalNodes: nodes.length,
        canonicalEdges: 0,
        aggregatedEdges: 0,
        wikilinks: 0,
        claims: 0,
        mocs: 0,
      },
      diagnostics: { broken: [], undeclared: [], collisions: {} },
    },
    nodes,
    edges,
  };
}

export interface RuntimeTether {
  from: Vec3;
  to: Vec3;
  runtimeNodeId: string;
  entityId: string;
}

export interface RuntimePlacement {
  positions: LayoutMap;
  tethers: RuntimeTether[];
}

export interface RuntimeActivitySegment {
  from: Vec3;
  to: Vec3;
  source: string;
  target: string;
  kind: 'edge' | 'tether';
}

/**
 * Segmentos que podem afirmar atividade sem confundir procedência histórica com fluxo.
 *
 * Uma aresta interna acende somente quando as duas pontas estão ativas. A única exceção
 * de fronteira é a haste do modelo vivo ao mesmo modelo no catálogo canônico: são duas
 * representações da mesma identidade ativa. Hastes de evento para assunto continuam
 * como procedência histórica e não fingem que a nota também está executando.
 */
export function activeRuntimeSegments(
  edges: readonly ProjectionEdge[],
  positions: LayoutMap,
  tethers: readonly RuntimeTether[],
  activeNodeIds: ReadonlySet<string>,
): RuntimeActivitySegment[] {
  const segments: RuntimeActivitySegment[] = [];
  for (const edge of edges) {
    if (!activeNodeIds.has(edge.source) || !activeNodeIds.has(edge.target)) continue;
    const from = positions.get(edge.source);
    const to = positions.get(edge.target);
    if (!from || !to) continue;
    segments.push({ from, to, source: edge.source, target: edge.target, kind: 'edge' });
  }
  for (const tether of tethers) {
    if (!activeNodeIds.has(tether.runtimeNodeId)) continue;
    const prefix = 'runtime:model:';
    if (
      !tether.runtimeNodeId.startsWith(prefix) ||
      tether.entityId !== `op/model/${tether.runtimeNodeId.slice(prefix.length)}`
    ) {
      continue;
    }
    segments.push({
      from: tether.from,
      // A ponta viva sai do mapa quando ele a conhece: a haste foi calculada com a
      // placa assentada, e a placa escolhida sobe. Sem isto ela continua amarrada à
      // cota antiga, e a linha termina onde o painel não está mais.
      to: positions.get(tether.runtimeNodeId) ?? tether.to,
      source: tether.runtimeNodeId,
      target: tether.entityId,
      kind: 'tether',
    });
  }
  return segments;
}

/**
 * Assenta a trilha com **o mesmo algoritmo do corpus**, sem alterar coordenada canônica.
 *
 * Já foi um esferoide oblato, e depois anéis no plano da tela — e anel, visto de lado, é
 * uma linha: com a câmera livre a nuvem inteira colapsava. O corpus não tem esse problema
 * porque não usa anel; usa calota com faixa de profundidade e relaxamento em três eixos.
 * É essa disposição que se quer aqui, então o que se reusa é a própria função.
 *
 * A hierarquia continua sendo provedor → modelo → evento: o provedor é âncora, e o
 * `anchorIdOf` lê de quem cada nó pende **pelo prefixo do identificador**, que este
 * módulo cunha e portanto é contrato. Pelo `kind` seria ambíguo — `vote_requested` já foi
 * projetado como `quorum-member`, o mesmo tipo do nó de modelo.
 *
 * A haste até a entidade do corpus continua sendo a única coisa que atravessa a
 * fronteira: o evento mora junto de quem o produziu, e aponta para o que ele anotou.
 */
/** O quanto uma disposição se afasta da própria origem. */
function raioDaNuvem(positions: LayoutMap, origem: Vec3): number {
  let raio = 0;
  for (const p of positions.values()) {
    raio = Math.max(raio, Math.hypot(p.x - origem.x, p.y - origem.y, p.z - origem.z));
  }
  return raio;
}

export function placeRuntime(
  projection: Projection,
  basePositions: LayoutMap,
  origem: Vec3 = { x: 0, y: 0, z: 0 },
  alvosDeHaste: LayoutMap = basePositions,
  /**
   * O raio que a nuvem tem para caber, porque alguém o reservou para ela.
   *
   * O anel das âncoras sai daqui, e o resultado era só um chute: medida na trilha real, a
   * nuvem chegava a 195 unidades dentro de uma reserva de 138 e encostava na borda de
   * dentro do quórum. A camada viva nasce em frame próprio, depois da composição, e por
   * isso não entrava em conferência nenhuma — era a única população da cena fora do
   * sistema de colisão.
   *
   * Agora ela se ajusta: mede o que ocupou e, se passou, reassenta com o anel encolhido
   * na mesma proporção. Duas tentativas, não um laço — o conteúdo tem um piso, porque a
   * separação de placas não deixa duas se cobrirem, e insistir abaixo dele só gastaria
   * passadas. Transbordar continua sendo melhor que amontoar; o que muda é que agora só
   * transborda quem não cabe mesmo.
   */
  raioReservado = 110,
): RuntimePlacement {
  const ancoraDoNo = new Map<string, string>();
  for (const edge of projection.edges) {
    // `modelo → provedor` e `âncora → evento`, ambas emitidas por `projectRuntime`.
    if (edge.source.startsWith('runtime:model:') && edge.target.startsWith('runtime:provider:')) {
      ancoraDoNo.set(edge.source, edge.target);
    } else if (
      (edge.source.startsWith('runtime:model:') || edge.source.startsWith('runtime:actor:')) &&
      edge.target.startsWith('runtime:event:')
    ) {
      ancoraDoNo.set(edge.target, edge.source);
    }
  }

  const assentar = (anel: number): LayoutMap =>
    layoutAtlas(projection, {
      include: 'all',
      // Âncora é o topo da hierarquia: provedor, e ator para quem não declara modelo.
      isAnchor: (node) => node.visual.isAnchor,
      // O evento pende do modelo, e o modelo do provedor. Como `layoutAtlas` agrupa num
      // nível só, o evento de um modelo é remetido ao provedor dele — o modelo continua
      // sendo um satélite do mesmo grupo, e os dois ficam vizinhos.
      anchorIdOf: (node) => {
        const direta = ancoraDoNo.get(node.id);
        if (direta === undefined) return null;
        return direta.startsWith('runtime:model:')
          ? (ancoraDoNo.get(direta) ?? direta)
          : direta;
      },
      isRoot: () => false,
      anchorRing: anel,
      seed: 20260808,
    });

  // Duas tentativas: assenta com o anel proporcional à reserva e, se o conteúdo
  // transbordou, encolhe o anel na mesma proporção do excesso e reassenta. A segunda
  // passagem não força nada — a separação de placas continua valendo, e o que não couber
  // continua saindo. O que ela desfaz é a folga que não era necessária.
  const NO_CENTRO = { x: 0, y: 0, z: 0 };
  let local = assentar(raioReservado * FRACAO_DO_ANEL);
  const excedente = raioDaNuvem(local, NO_CENTRO) / raioReservado;
  if (excedente > 1) {
    const encolhida = assentar((raioReservado * FRACAO_DO_ANEL) / excedente);
    // Só vale se de fato encolheu: com o anel menor os territórios se aproximam, e a
    // separação de placas pode empurrar de volta o que o anel economizou.
    if (raioDaNuvem(encolhida, NO_CENTRO) < raioDaNuvem(local, NO_CENTRO)) local = encolhida;
  }

  const positions: LayoutMap = new Map();
  for (const [id, p] of local) {
    positions.set(id, { x: p.x + origem.x, y: p.y + origem.y, z: p.z + origem.z });
  }

  // As hastes: o que a camada viva toca fora dela.
  //
  // Havia só uma origem — a entidade do corpus que o evento anota — e ela secou. Medido
  // na trilha real, nenhum dos 160 eventos visíveis declara entidade, e as tarefas
  // recentes são de revisão de proposta e de divergência entre modelos: elas não tratam
  // de nota nenhuma. Não há vínculo a desenhar ali, e inventar um seria mentir.
  //
  // O que **existe** em quase todo evento é o modelo que o executou, e ele tem identidade
  // canônica na nuvem de modelos. Ligar o modelo local ao canônico é o vínculo que a
  // trilha de fato afirma, e é ele que tira a camada viva do isolamento.
  const tethers: RuntimePlacement['tethers'] = [];
  const amarrar = (node: ProjectionNode, alvo: string, mapa: LayoutMap): void => {
    const base = mapa.get(alvo);
    const placed = positions.get(node.id);
    if (!base || !placed) return;
    tethers.push({ from: base, to: placed, runtimeNodeId: node.id, entityId: alvo });
  };
  for (const node of projection.nodes) {
    const entityId = node.operational?.entity;
    if (entityId) amarrar(node, entityId, basePositions);
    // Uma haste por **modelo**, e não por evento: os eventos já pendem do modelo dentro
    // da nuvem, e repetir a ligação em cada um encheria a cena de linhas paralelas
    // dizendo a mesma coisa.
    if (!node.id.startsWith('runtime:model:')) continue;
    const provider = node.operational?.provider;
    const endpoint = node.operational?.endpoint;
    if (provider === undefined || endpoint === undefined) continue;
    amarrar(node, `op/model/${provider}/${endpoint}`, alvosDeHaste);
  }
  return { positions, tethers };
}

/**
 * Quanto do raio reservado vira anel das âncoras.
 *
 * O resto é território: cada provedor abre a própria vizinhança de modelos e eventos em
 * volta da âncora, e essa vizinhança precisa caber entre o anel e a borda da reserva. A
 * fração vem do que a nuvem já media — anel de 78 dentro de uma reserva da ordem do raio
 * do corpus — e mantém a mesma proporção quando a reserva muda de tamanho.
 */
const FRACAO_DO_ANEL = 0.62;


export interface RuntimeSelection {
  runtimeNodeId: string;
  linkedEntityId: string | null;
  description: string;
}

/**
 * Um painel vivo, pronto para entrar no mesmo orçamento de texto do corpus.
 *
 * A camada operacional não tem pool próprio: ela concorre pelas mesmas 64 vagas, com
 * o piso que `textPool.ts` reserva. Expor o painel em vez de desenhá-lo aqui é o que
 * torna isso possível — e o que impede a operação de virar um segundo alfabeto.
 */
export interface RuntimePanel {
  entityId: string;
  descriptor: PanelDescriptor;
  position: THREE.Vector3;
  extent: { width: number; height: number };
}

export interface RuntimeLayer {
  group: THREE.Group;
  update: (snapshot: RuntimeSnapshot) => void;
  /**
   * O raciocínio que os modelos estão emitindo agora, por `provedor/endpoint`.
   *
   * Separado de `update` porque a origem é outra: a trilha operacional não carrega texto
   * de modelo, e este canal não carrega evento. Quadro de um modelo que a trilha não diz
   * estar trabalhando é ignorado — a cena não afirma atividade que a trilha não sustenta.
   */
  updateCognition: (frames: readonly CognitionFrame[]) => void;
  /**
   * Sincroniza o roster de trabalhadores por identidade, sem reconstruir a trilha.
   *
   * `undefined` e `[]` não são a mesma coisa, e confundi-los é o defeito que este
   * contrato existe para impedir. `undefined` é "nenhum snapshot novo, preserve o que
   * está"; `[]` é "o runtime afirma que não há nenhum". Sem a distinção, um polling que
   * falhasse apagaria os sete da cena.
   *
   * Id novo cria, id existente atualiza no lugar, id ausente remove, id que volta
   * recria — sempre na âncora canônica. Atualizar metadado **não** toca em nenhuma das
   * três poses.
   */
  syncWorkers: (workers?: readonly RuntimeWorker[]) => void;
  /** Os trabalhadores que esta camada possui agora, para medição e paridade. */
  workerPoses: () => { id: string; anchor: Vec3; target: Vec3; current: Vec3 }[];
  /** Muda só o destino de um trabalhador. Âncora e pose corrente não se alteram aqui. */
  retargetWorker: (id: string, target: Vec3) => void;
  /** Reavalia prazos de atividade sem reconstruir painéis ou apagar a seleção. */
  refreshActivity: (now?: number) => void;
  /**
   * Assenta a última mudança topológica no tempo do quadro.
   *
   * Devolve `true` enquanto alguma placa realmente mudou, para títulos e enquadramento
   * poderem acompanhar sem medir a camada inteira em repouso.
   */
  advance: (deltaSeconds: number, reducedMotion?: boolean) => boolean;
  /** Orienta as placas vivas para a câmera. Elas são painéis, e painel se lê de frente. */
  updateView: (camera: THREE.PerspectiveCamera) => void;
  panels: () => RuntimePanel[];
  pickables: () => THREE.Object3D[];
  /** Só a placa do evento expandido. Ver `PanelBodies.expandedTarget`. */
  expandedTarget: () => THREE.Object3D | null;
  selectionFor: (object: THREE.Object3D, instanceId: number | undefined) => RuntimeSelection | null;
  /** O mesmo dado da seleção, a partir do id já resolvido. */
  panelSelection: (runtimeNodeId: string) => RuntimeSelection | null;
  /** Onde a placa está desenhada, para quem precisa projetá-la em pixels. */
  renderPositionFor: (runtimeNodeId: string) => THREE.Vector3 | null;
  /**
   * Os segmentos das arestas que tocam um nó vivo, já em coordenadas de mundo.
   *
   * A camada viva tem projeção e posições próprias, então o foco do atlas — que lê a
   * projeção do corpus — não tinha como iluminar nada aqui: clicar num evento acendia o
   * painel e deixava as ligações apagadas. Devolver os segmentos deixa o desenho onde ele
   * já está, com a mesma fita e o mesmo degradê.
   */
  neighbourhood: (runtimeNodeId: string) => { from: Vec3; to: Vec3 }[];
  /**
   * Apaga a camada viva enquanto há foco no corpus, preservando o que se liga a ele.
   *
   * Sem isto, selecionar uma nota deixaria a operação em contraste cheio ao redor: a
   * vizinhança do nó ativo perderia a disputa por atenção para eventos que não têm
   * relação nenhuma com o que se está lendo.
   */
  setDimmed: (dimmed: boolean, relatedEntityId: string | null) => void;
  dispose: () => void;
  /**
   * Acende o que está acontecendo **agora**, na intensidade que o quadro pede.
   *
   * Substitui a antiga `activeIds`, que devolvia os seis eventos mais recentes e não era
   * consumida por ninguém: a nuvem viva era a única população da cena sem pulso, e "há cognição
   * acontecendo aqui" — que é o que a visão de conjunto precisa dizer — não era dito.
   *
   * O que acende não é recência, é **estado**: um modelo com chamada aberta continua
   * trabalhando enquanto ela não voltar, ainda que dez eventos de outros tenham entrado no
   * meio. Recência acenderia quem já terminou e apagaria quem ainda trabalha.
   */
  pulse: (intensity: number, seconds?: number, motion?: boolean) => void;
  /** Autoriza ou suprime toda afirmação de atividade sem apagar a geometria histórica. */
  setActivityEnabled: (enabled: boolean) => void;
  /** O estado temporal de cada modelo da trilha, por `provedor/endpoint`. */
  cognitive: () => ReadonlyMap<string, CognitiveStatus>;
  /** Nós cujo trabalho continua aberto depois da última revisão recebida. */
  activeIds: () => ReadonlySet<string>;
  /** Painéis persistidos que ainda estão dentro de um ciclo de quórum ou promoção. */
  activePanelIds: () => ReadonlySet<string>;
  /**
   * Expande o evento escolhido, e recolhe o anterior.
   *
   * Sem isto a seleção mudava só o nível do texto: o painel passava a compor o
   * conteúdo inteiro e continuava do tamanho de antes, e tudo ficava recortado. Quem
   * cresce é a placa; o texto acompanha.
   */
  setSelected: (runtimeNodeId: string | null) => void;
}

/**
 * Onde a nuvem viva mora, no mundo composto: **no miolo**.
 *
 * Ela já morou em dois lugares errados. Primeiro na origem, em cima do corpus, e as
 * rosetas de evento caíam entre as notas. Depois "no que sobrava" — a direção oposta à
 * soma das nuvens já assentadas —, que era uma regra defensável e cega: ela media centros
 * alheios para descobrir onde não incomodar, e o resultado era a nuvem do que está
 * acontecendo agora encostada na borda da cena, longe de tudo que comenta.
 *
 * Agora o lugar é declarado pela composição, e é o centro: o conhecimento desceu para
 * debaixo do quórum e deixou o miolo, com o tamanho que ele ocupava. Quem chega vê
 * primeiro o que está acontecendo, e o acervo fica onde a deliberação o julga.
 *
 * A haste até a entidade anotada continua ligando as duas, e é ela que atravessa a
 * fronteira.
 */

export function createRuntimeLayer(
  basePositions: LayoutMap,
  alvosDeHaste: LayoutMap = basePositions,
  /** O miolo que a composição reserva: onde a nuvem viva mora e que raio ela cabe. */
  miolo: { origin: Vec3; radius: number } = { origin: { x: 0, y: 0, z: 0 }, radius: 110 },
  /** Raio varrido das placas que as hastes miram, para elas pararem na borda. */
  raiosDeHaste: ReadonlyMap<string, number> = new Map(),
  /**
   * A âncora dos trabalhadores, **injetada** — nunca o raio cru.
   *
   * Se esta camada recebesse raio, ângulo ou regra de distribuição, ela passaria a possuir
   * um pedaço do layout, e a separação que a ADR-005 fixou voltaria a se misturar. O que
   * ela recebe é uma pergunta: dadas estas identidades, onde elas se assentam. Quem
   * responde é a fonte geométrica canônica, do outro lado da injeção.
   */
  workerAnchors: (ids: readonly string[]) => LayoutMap = () => new Map(),
): RuntimeLayer {
  const group = new THREE.Group();
  group.name = 'runtime-live-layer';
  let bodies: PanelBodies | null = null;
  let nodeById = new Map<string, ProjectionNode>();
  /** Arestas e posições da projeção viva, para o foco poder iluminá-las. */
  let arestasVivas: ProjectionEdge[] = [];
  let posicoesVivas: LayoutMap = new Map();
  /** Alvos da política de layout; as posições acima são o quadro atualmente desenhado. */
  let alvosVivos: LayoutMap = new Map();
  let ancorasVivas = new Set<string>();
  let hastesVivas: RuntimeTether[] = [];
  let ultimoSnapshot: RuntimeSnapshot | null = null;

  /**
   * A pose exibida é âncora + deslocamento técnico (M5 da ADR-003).
   *
   * O mapa de entrada — `alvosVivos` — nunca é mutado: ele é a memória espacial
   * da política de layout. Aqui se deriva, a cada chamada, o alvo que o motor de
   * movimento deve perseguir. Chamar por quadro mantém a órbita de espera girando
   * entre eventos, e com movimento reduzido devolve o mapa de entrada intacto —
   * acessibilidade vence a gramática.
   */
  const alvosComMorfologia = (): LayoutMap => {
    if (!ultimoSnapshot || ultimoSnapshot.events.length === 0) return alvosVivos;
    const sinais = sinaisOperacionais(ultimoSnapshot, Date.now());
    return aplicarMorfologia(
      alvosVivos,
      sinais,
      (provider, ancora) =>
        direcaoPara(alvosDeHaste.get(`op/provider/${provider}`), ancora),
      (entityId, ancora) => direcaoPara(alvosDeHaste.get(entityId), ancora),
      miolo.radius * MORPH_AMPLITUDE_FRACTION,
    );
  };
  /**
   * O tecido dos trabalhadores, com ciclo de vida separado do da trilha.
   *
   * Três poses e três autoridades, como a ADR-005 fixou: a âncora vem do layout, por
   * `workerAnchors` injetada; o alvo é da política morfogênica; a corrente é do motor de
   * movimento. Nenhuma das três é escrita por quem não a possui.
   */
  const grupoDosTrabalhadores = new THREE.Group();
  grupoDosTrabalhadores.name = 'runtime-workers';
  group.add(grupoDosTrabalhadores);
  const trabalhadores = new Map<string, RuntimeWorker>();
  let corposDosTrabalhadores: PanelBodies | null = null;
  const ancoraDoTrabalhador: LayoutMap = new Map();
  const alvoDoTrabalhador: LayoutMap = new Map();
  const poseDoTrabalhador: LayoutMap = new Map();

  let ownedGeometries: THREE.BufferGeometry[] = [];
  /** Relações de repouso são substituídas enquanto a topologia se assenta. */
  let connectionObjects: THREE.Object3D[] = [];
  let connectionGeometries: THREE.BufferGeometry[] = [];
  let connectionMaterials: THREE.Material[] = [];
  /** Linha direta e barata exibida só enquanto as placas estão se assentando. */
  let settlingLines: THREE.LineSegments | null = null;
  let settlingGeometry: THREE.BufferGeometry | null = null;
  let settlingMaterial: THREE.LineBasicMaterial | null = null;
  let settling = false;
  let raiosVivos: ReadonlyMap<string, number> = new Map();
  /** Estado temporal por modelo e atividade que continua aberta na última revisão. */
  let estados: ReadonlyMap<string, CognitiveStatus> = new Map();
  let assinaturaCognitiva = '';
  /**
   * O último raciocínio por modelo, vindo do canal efêmero.
   *
   * Não é limpo por `clear()`: a trilha pode ser reconstruída do zero enquanto a mesma
   * chamada segue aberta, e apagar o pensamento junto faria a cena esquecer o que o
   * modelo ainda está dizendo. Quem o expira é o próprio canal, ao mandar o `final`.
   */
  let quadrosCognitivos: readonly CognitionFrame[] = [];
  let atividade: RuntimeActivity = { activeNodeIds: new Set(), activePanelIds: new Set() };
  /** O que está aceso, para apagar só quem saiu do fluxo. */
  let pulsando = new Set<string>();
  /** Material do caminho ativo, cuja opacidade acompanha o mesmo pulso dos painéis. */
  let materialDaAtividade: THREE.Material | null = null;
  /** O mesmo material, com o relógio do fluxo. Ver `runtimeFlow.ts`. */
  let fluxoDaAtividade: FlowMaterial | null = null;
  let linhasDaAtividade: THREE.LineSegments | null = null;
  let atividadeHabilitada = true;
  let camadaAtenuada = false;
  let entidadeRelacionada: string | null = null;
  /** O evento escolhido, cuja placa cresce para caber a leitura. */
  let selecionado: string | null = null;
  let ownedMaterials: THREE.Material[] = [];

  /**
   * Escreve posição, distância e progresso do fluxo numa geometria de segmentos.
   *
   * Os três atributos são reescritos juntos, sempre: um comprimento novo com a
   * distância antiga poria o pulso correndo fora do fio.
   */
  const escreverFluxo = (
    geometry: THREE.BufferGeometry,
    segmentos: readonly RuntimeActivitySegment[],
  ): void => {
    const buffers = flowAttributes(segmentos);
    const escreverAtributo = (
      name: string,
      values: Float32Array,
      itemSize: number,
    ): void => {
      const current = geometry.getAttribute(name) as THREE.BufferAttribute | undefined;
      if (current?.array instanceof Float32Array && current.array.length === values.length) {
        current.array.set(values);
        current.needsUpdate = true;
      } else geometry.setAttribute(name, new THREE.BufferAttribute(values, itemSize));
    };
    escreverAtributo('position', buffers.position, 3);
    escreverAtributo('aFlow', buffers.flow, 1);
    escreverAtributo('aProgresso', buffers.progress, 1);
  };

  const limparConexoes = (): void => {
    for (const object of connectionObjects) group.remove(object);
    for (const geometry of connectionGeometries) geometry.dispose();
    for (const material of connectionMaterials) material.dispose();
    connectionObjects = [];
    connectionGeometries = [];
    connectionMaterials = [];
  };

  const limparConexoesDeAssentamento = (): void => {
    if (settlingLines) group.remove(settlingLines);
    settlingGeometry?.dispose();
    settlingMaterial?.dispose();
    settlingLines = null;
    settlingGeometry = null;
    settlingMaterial = null;
    settling = false;
  };

  /** Posições desenhadas de toda a camada, incluindo a elevação de seleção. */
  const posicoesDesenhadas = (): LayoutMap => {
    const desenhadas: LayoutMap = new Map();
    for (const id of nodeById.keys()) {
      const position = bodies?.renderPositionFor(id);
      const fallback = posicoesVivas.get(id);
      const point = position ?? fallback;
      if (point) desenhadas.set(id, { x: point.x, y: point.y, z: point.z });
    }
    return desenhadas;
  };

  /** Reconstrói o roteamento completo depois que a topologia chega ao repouso. */
  const reconstruirConexoes = (): void => {
    limparConexoes();
    if (settlingLines) settlingLines.visible = false;
    settling = false;
    if (!bodies) return;
    const desenhadas = posicoesDesenhadas();
    for (const build of buildRelationLines(arestasVivas, desenhadas, raiosVivos)) {
      group.add(build.lines);
      connectionObjects.push(build.lines);
      connectionGeometries.push(build.lines.geometry);
      connectionMaterials.push(...materialsOf(build.lines.material));
      if (build.markers) {
        group.add(build.markers);
        connectionObjects.push(build.markers);
        connectionGeometries.push(build.markers.geometry);
        connectionMaterials.push(...materialsOf(build.markers.material));
      }
    }

    const points = hastesVivas.flatMap(({ from, to, runtimeNodeId, entityId }) => {
      const current = desenhadas.get(runtimeNodeId) ?? to;
      const trimmed = trimEdge(
        from,
        current,
        raiosDeHaste.get(entityId) ?? 0,
        raiosVivos.get(runtimeNodeId) ?? 0,
      );
      if (!trimmed) return [];
      return [
        trimmed.a.x,
        trimmed.a.y,
        trimmed.a.z,
        trimmed.b.x,
        trimmed.b.y,
        trimmed.b.z,
      ];
    });
    if (points.length === 0) return;
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(points, 3));
    const material = new THREE.LineBasicMaterial({
      color: 0x7898c4,
      transparent: true,
      opacity: 0.24,
      depthWrite: false,
    });
    const tethers = new THREE.LineSegments(geometry, material);
    tethers.name = 'runtime-entity-tethers';
    tethers.renderOrder = 2;
    group.add(tethers);
    connectionObjects.push(tethers);
    connectionGeometries.push(geometry);
    connectionMaterials.push(material);
  };

  /**
   * Atualiza uma malha linear durante o movimento, sem refazer desvio de obstáculos.
   *
   * O roteamento curvo custa dezenas de milissegundos no snapshot vivo. Durante a
   * transição, a informação necessária é aderência das pontas; a rota canônica volta
   * uma única vez no repouso. Assim nenhum elo fica para trás e o quadro continua leve.
   */
  const atualizarConexoesDeAssentamento = (): void => {
    const desenhadas = posicoesDesenhadas();
    const points: number[] = [];
    const vistos = new Set<string>();
    for (const edge of arestasVivas) {
      if (edge.kind === 'aggregated' || !edge.primaryRelation) continue;
      const pair = edge.source < edge.target
        ? `${edge.source}\0${edge.target}`
        : `${edge.target}\0${edge.source}`;
      if (vistos.has(pair)) continue;
      vistos.add(pair);
      const from = desenhadas.get(edge.source);
      const to = desenhadas.get(edge.target);
      if (!from || !to) continue;
      const trimmed = trimEdge(
        from,
        to,
        raiosVivos.get(edge.source) ?? 0,
        raiosVivos.get(edge.target) ?? 0,
      );
      if (trimmed) {
        points.push(
          trimmed.a.x, trimmed.a.y, trimmed.a.z,
          trimmed.b.x, trimmed.b.y, trimmed.b.z,
        );
      }
    }
    for (const { from, to, runtimeNodeId, entityId } of hastesVivas) {
      const current = desenhadas.get(runtimeNodeId) ?? to;
      const trimmed = trimEdge(
        from,
        current,
        raiosDeHaste.get(entityId) ?? 0,
        raiosVivos.get(runtimeNodeId) ?? 0,
      );
      if (trimmed) {
        points.push(
          trimmed.a.x, trimmed.a.y, trimmed.a.z,
          trimmed.b.x, trimmed.b.y, trimmed.b.z,
        );
      }
    }

    if (!settlingGeometry || !settlingMaterial || !settlingLines) {
      settlingGeometry = new THREE.BufferGeometry();
      settlingMaterial = new THREE.LineBasicMaterial({
        color: 0x7898c4,
        transparent: true,
        opacity: 0.16,
        depthWrite: false,
      });
      settlingLines = new THREE.LineSegments(settlingGeometry, settlingMaterial);
      settlingLines.name = 'runtime-settling-links';
      settlingLines.renderOrder = 2;
      settlingLines.frustumCulled = false;
      settlingGeometry.setAttribute(
        'position',
        new THREE.Float32BufferAttribute(
          new Float32Array(Math.max((arestasVivas.length + hastesVivas.length) * 6, 6)),
          3,
        ),
      );
      group.add(settlingLines);
    }
    const position = settlingGeometry.getAttribute('position') as THREE.BufferAttribute;
    (position.array as Float32Array).set(points);
    position.needsUpdate = true;
    settlingGeometry.setDrawRange(0, points.length / 3);
    settlingLines.visible = points.length > 0;
    for (const object of connectionObjects) object.visible = false;
    settling = true;
  };

  /**
   * Reconstrói os corpos dos trabalhadores. Só quando a composição de ids muda.
   *
   * Atualizar metadado de um trabalhador existente não passa por aqui: reconstruir sete
   * placas a cada polling do controle seria pagar geometria por um texto que talvez nem
   * tenha mudado.
   */
  const redesenharTrabalhadores = (): void => {
    corposDosTrabalhadores?.dispose();
    corposDosTrabalhadores = null;
    grupoDosTrabalhadores.clear();
  };

  const clear = (): void => {
    limparConexoes();
    limparConexoesDeAssentamento();
    bodies?.dispose();
    bodies = null;
    for (const geometry of ownedGeometries) geometry.dispose();
    for (const material of ownedMaterials) material.dispose();
    ownedGeometries = [];
    ownedMaterials = [];
    nodeById = new Map();
    arestasVivas = [];
    posicoesVivas = new Map();
    alvosVivos = new Map();
    ancorasVivas = new Set();
    hastesVivas = [];
    ultimoSnapshot = null;
    estados = new Map();
    assinaturaCognitiva = '';
    atividade = { activeNodeIds: new Set(), activePanelIds: new Set() };
    pulsando = new Set();
    materialDaAtividade = null;
    fluxoDaAtividade = null;
    linhasDaAtividade = null;
    raiosVivos = new Map();
    selecionado = null;
    // `group.clear()` derrubaria junto o tecido dos trabalhadores, que tem ciclo de vida
    // próprio: a trilha ficar vazia significa "nenhum evento", nunca "nenhum
    // trabalhador". É a distinção que a ADR-005 fixou entre as duas atualizações.
    for (const filho of [...group.children]) {
      if (filho !== grupoDosTrabalhadores) group.remove(filho);
    }
  };

  /**
   * A posição em que a placa está **desenhada**, e não a que o layout assentou.
   *
   * A placa escolhida sobe para sair de trás das vizinhas. Quem ligasse a linha à cota
   * do layout a deixava presa no lugar de onde o painel saiu — a ligação apontando para
   * o vazio. É a mesma armadilha que `panels()` já documenta para o texto e a câmera.
   */
  const posicaoDesenhada = (id: string): Vec3 | undefined => {
    const desenhada = bodies?.renderPositionFor(id);
    if (desenhada) return { x: desenhada.x, y: desenhada.y, z: desenhada.z };
    return posicoesVivas.get(id);
  };

  /** Os vizinhos diretos de um nó vivo, em qualquer sentido da aresta. */
  const vizinhosDe = (runtimeNodeId: string): Set<string> => {
    const vizinhos = new Set<string>();
    for (const edge of arestasVivas) {
      if (edge.source === runtimeNodeId) vizinhos.add(edge.target);
      else if (edge.target === runtimeNodeId) vizinhos.add(edge.source);
    }
    return vizinhos;
  };

  const aplicarEnfase = (): void => {
    const atual = bodies;
    if (!atual) return;
    // A seleção viva manda na própria camada, com a mesma gramática do corpus: o
    // escolhido acende, os vizinhos diretos acompanham, o resto atenua. Sem isto, quem
    // abria um painel vivo não via nenhuma das ligações dele responderem — o painel
    // crescia sozinho no meio de uma nuvem inteira em contraste cheio.
    const vizinhos = selecionado === null ? null : vizinhosDe(selecionado);
    for (const [id, node] of nodeById) {
      const ligado =
        entidadeRelacionada !== null && node.operational?.entity === entidadeRelacionada;
      const ativo = atividadeHabilitada && atividade.activeNodeIds.has(id);
      if (selecionado !== null) {
        const acompanha = id === selecionado || vizinhos?.has(id) === true;
        atual.setEmphasis(id, acompanha ? 'highlighted' : 'dimmed');
        continue;
      }
      atual.setEmphasis(
        id,
        camadaAtenuada && !ligado ? 'dimmed' : ativo ? 'highlighted' : 'normal',
      );
    }
  };

  const atualizarLinhasDaAtividade = (): void => {
    if (!linhasDaAtividade) return;
    const segmentos = activeRuntimeSegments(
      arestasVivas,
      posicoesDesenhadas(),
      hastesVivas,
      atividade.activeNodeIds,
    );
    if (segmentos.length === 0) {
      linhasDaAtividade.visible = false;
      return;
    }
    escreverFluxo(linhasDaAtividade.geometry, segmentos);
    linhasDaAtividade.geometry.computeBoundingSphere();
    linhasDaAtividade.visible = atividadeHabilitada;
  };

  const recalcularAtividade = (now = Date.now()): void => {
    if (!ultimoSnapshot) return;
    const proximosEstados = withCognition(
      cognitiveStates(ultimoSnapshot, now),
      quadrosCognitivos,
    );
    const proximaAssinatura = cognitiveFingerprint(proximosEstados);
    if (proximaAssinatura !== assinaturaCognitiva) {
      const projection = projectRuntime(ultimoSnapshot, now, quadrosCognitivos);
      nodeById = new Map(projection.nodes.map((node) => [node.id, node]));
      raiosVivos = panelSweepRadii(projection.nodes);
      bodies?.rebuild(projection.nodes, posicoesVivas);
      estados = proximosEstados;
      assinaturaCognitiva = proximaAssinatura;
    }
    const calculada = activityFrom(ultimoSnapshot, now);
    atividade = {
      activeNodeIds: new Set(
        [...calculada.activeNodeIds].filter((runtimeNodeId) => nodeById.has(runtimeNodeId)),
      ),
      activePanelIds: calculada.activePanelIds,
    };

    const acesos = atividadeHabilitada ? atividade.activeNodeIds : new Set<string>();
    if (bodies) {
      for (const id of pulsando) if (!acesos.has(id)) bodies.setActivity(id, 0);
    }
    pulsando = new Set([...pulsando].filter((id) => acesos.has(id)));
    aplicarEnfase();

    atualizarLinhasDaAtividade();
  };

  return {
    group,
    update(snapshot) {
      // A identidade visual atravessa o snapshot. O log muda; uma placa que continua
      // representando a mesma entidade não teleporta por causa disso.
      const anteriores: LayoutMap = new Map(
        [...posicoesVivas].map(([id, point]) => [id, { ...point }]),
      );
      clear();
      ultimoSnapshot = snapshot;
      if (snapshot.events.length === 0) return;
      const agora = Date.now();
      const projection = projectRuntime(snapshot, agora, quadrosCognitivos);
      nodeById = new Map(projection.nodes.map((node) => [node.id, node]));
      raiosVivos = panelSweepRadii(projection.nodes);
      estados = withCognition(cognitiveStates(snapshot, agora), quadrosCognitivos);
      assinaturaCognitiva = cognitiveFingerprint(estados);
      const calculada = activityFrom(snapshot, agora);
      atividade = {
        activeNodeIds: new Set(
          [...calculada.activeNodeIds].filter((runtimeNodeId) => nodeById.has(runtimeNodeId)),
        ),
        activePanelIds: calculada.activePanelIds,
      };
      // Uma passagem só. Eram duas — a primeira media o tamanho da nuvem para a segunda
      // saber o quanto se afastar do corpus —, e medir deixou de ser preciso no dia em que
      // o lugar passou a ser declarado pela composição em vez de deduzido do que sobrava.
      const placement = placeRuntime(
        projection,
        basePositions,
        miolo.origin,
        alvosDeHaste,
        miolo.radius,
      );

      // O painel operacional também é o nó: mesma gramática do corpus, mesma
      // fábrica de placas. O runtime tem malha própria porque se reconstrói a cada
      // instantâneo, não porque desenha outro alfabeto.
      arestasVivas = projection.edges;
      alvosVivos = preserveAnchorTargets(
        projection.nodes,
        projection.edges,
        placement.positions,
        anteriores,
      );
      ancorasVivas = new Set(
        projection.nodes.filter((node) => node.visual.isAnchor).map((node) => node.id),
      );
      // O primeiro snapshot é história já assentada, não atividade acontecendo agora.
      // Animá-lo desde as âncoras faria o Atlas encenar centenas de eventos antigos no
      // carregamento e ainda enquadraria a nuvem recolhida antes de ela se abrir. Só uma
      // revisão posterior ganha continuidade temporal a partir do quadro anterior.
      posicoesVivas =
        anteriores.size === 0
          ? new Map(
              [...alvosVivos].map(([id, point]) => [id, { ...point }]),
            )
          : motionStartPositions(
              projection.nodes,
              projection.edges,
              alvosVivos,
              anteriores,
            );
      hastesVivas = placement.tethers;
      bodies = createPanelBodies(projection.nodes, posicoesVivas);
      group.add(bodies.group);
      reconstruirConexoes();

      const segmentosAtivos = activeRuntimeSegments(
        projection.edges,
        posicoesDesenhadas(),
        placement.tethers,
        atividade.activeNodeIds,
      );
      if (segmentosAtivos.length > 0) {
        const geometry = new THREE.BufferGeometry();
        escreverFluxo(geometry, segmentosAtivos);
        // Este é o fio que **deve** se destacar: ele só existe enquanto há trabalho
        // aberto, e some quando acaba. O que ele diz agora não é só "há trabalho": o
        // pulso corre na direção em que a informação vai, e é isso que responde
        // "quem está alimentando quem" numa cena com dezenas de execuções abertas.
        fluxoDaAtividade = createFlowMaterial();
        materialDaAtividade = fluxoDaAtividade.material;
        const linhasAtivas = new THREE.LineSegments(geometry, materialDaAtividade);
        linhasAtivas.name = 'runtime-active-links';
        linhasAtivas.renderOrder = 6;
        linhasAtivas.visible = atividadeHabilitada;
        linhasDaAtividade = linhasAtivas;
        group.add(linhasAtivas);
        ownedGeometries.push(geometry);
        ownedMaterials.push(materialDaAtividade);
      }
    },
    syncWorkers(workers) {
      const passo = diffWorkers(trabalhadores, workers);
      if (workers === undefined) return;
      for (const id of passo.removed) {
        trabalhadores.delete(id);
        ancoraDoTrabalhador.delete(id);
        alvoDoTrabalhador.delete(id);
        poseDoTrabalhador.delete(id);
      }
      // Atualização no lugar: o estado muda, as três poses não. Só `retargetWorker`
      // mexe no alvo, e só `advance` mexe na pose corrente.
      for (const worker of passo.updated) trabalhadores.set(worker.id, worker);
      for (const worker of passo.created) trabalhadores.set(worker.id, worker);

      // A âncora é recalculada a partir das identidades vivas, e não herdada: é isso que
      // faz um trabalhador que volta reaparecer no lugar certo em vez de onde ele estava
      // quando saiu. `workerAnchorPoses` ordena por id, então a ordem de chegada do
      // snapshot não vira geometria.
      const ancoras = workerAnchors(
        [...trabalhadores.values()].map((worker) => workerNodeId(worker.role)),
      );
      for (const [id, ponto] of ancoras) {
        ancoraDoTrabalhador.set(id, { ...ponto });
        if (!poseDoTrabalhador.has(id)) {
          // Estado inicial obrigatório: as três iguais, e portanto zero movimento
          // visível no instante em que o dono muda.
          alvoDoTrabalhador.set(id, { ...ponto });
          poseDoTrabalhador.set(id, { ...ponto });
        }
      }
      if (passo.membershipChanged) redesenharTrabalhadores();
    },

    workerPoses() {
      return [...trabalhadores.values()]
        .map((worker) => workerNodeId(worker.role))
        .sort((a, b) => a.localeCompare(b))
        .flatMap((id) => {
          const anchor = ancoraDoTrabalhador.get(id);
          const target = alvoDoTrabalhador.get(id);
          const current = poseDoTrabalhador.get(id);
          return anchor && target && current
            ? [{ id, anchor: { ...anchor }, target: { ...target }, current: { ...current } }]
            : [];
        });
    },

    retargetWorker(id, target) {
      if (!alvoDoTrabalhador.has(id)) return;
      alvoDoTrabalhador.set(id, { ...target });
    },

    updateCognition(frames) {
      quadrosCognitivos = frames;
      recalcularAtividade();
    },
    refreshActivity(now = Date.now()) {
      recalcularAtividade(now);
    },
    advance(deltaSeconds, reducedMotion = false) {
      // O tecido dos trabalhadores anda pelo mesmo motor e por conta própria: ele não
      // depende da trilha ter eventos, e nenhuma âncora entra no conjunto ancorado
      // porque aqui a âncora é o ponto de partida, não uma posição imóvel. Enquanto
      // ninguém chamar `retargetWorker`, alvo e pose corrente são iguais e isto não
      // move nada — que é o estado inicial obrigatório da migração.
      const passoDoTecido = advanceMotion(
        poseDoTrabalhador,
        alvoDoTrabalhador,
        new Set<string>(),
        deltaSeconds,
        reducedMotion,
      );
      if (passoDoTecido.moved) {
        for (const [id, ponto] of poseDoTrabalhador) corposDosTrabalhadores?.moveTo(id, ponto);
      }

      const step = advanceMotion(
        posicoesVivas,
        reducedMotion ? alvosVivos : alvosComMorfologia(),
        ancorasVivas,
        deltaSeconds,
        reducedMotion,
      );
      if (!step.moved) return passoDoTecido.moved;
      for (const [id, point] of posicoesVivas) bodies?.moveTo(id, point);

      if (reducedMotion || step.settled) {
        reconstruirConexoes();
      } else atualizarConexoesDeAssentamento();
      atualizarLinhasDaAtividade();
      return true;
    },
    updateView(camera) {
      bodies?.orient(camera.quaternion);
    },
    panels() {
      const atual = bodies;
      if (!atual) return [];
      const lista: RuntimePanel[] = [];
      for (const entityId of atual.entityIds()) {
        const descriptor = atual.descriptorFor(entityId);
        // A posição **desenhada**, e não a assentada. É a mesma armadilha que o corpus
        // já documenta em `renderPositionFor`: o painel escolhido sobe 1,4 para sair de
        // trás dos vizinhos, e quem usasse a cota do layout — texto, halo, câmera —
        // ficaria para trás. A placa, opaca e escrevendo profundidade, passava a esconder
        // justamente o que ela existe para mostrar, e o painel vivo aparecia vazio ao ser
        // selecionado.
        const position = atual.renderPositionFor(entityId);
        const extent = atual.extentFor(entityId);
        if (!descriptor || !position || !extent) continue;
        lista.push({ entityId, descriptor, position, extent });
      }
      return lista;
    },
    pickables() {
      // A placa da frente entra junto: sem ela, o evento expandido — que desenha por
      // cima de tudo — era o único painel da cena que não se podia apontar.
      return bodies?.pickTargets() ?? [];
    },
    expandedTarget() {
      return bodies?.expandedTarget() ?? null;
    },
    selectionFor(object, instanceId) {
      const runtimeNodeId = bodies?.entityFor(object, instanceId);
      return runtimeNodeId ? this.panelSelection(runtimeNodeId) : null;
    },
    neighbourhood(runtimeNodeId) {
      const saida: { from: Vec3; to: Vec3 }[] = [];
      const vistas = new Set<string>();
      const segmentosVistos = new Set<string>();
      for (const edge of arestasVivas) {
        if (edge.source !== runtimeNodeId && edge.target !== runtimeNodeId) continue;
        // Uma aresta por par, em qualquer sentido. O par (A,B) e o par (B,A) desenham a
        // mesma reta, e duas retas coincidentes com a mesma cor não somam informação —
        // somam brilho, que é como a fita aparecia mais grossa em alguns vínculos.
        const par = edge.source < edge.target
          ? `${edge.source}\0${edge.target}`
          : `${edge.target}\0${edge.source}`;
        if (vistas.has(par)) continue;
        vistas.add(par);
        const de = posicaoDesenhada(edge.source);
        const para = posicaoDesenhada(edge.target);
        if (!de || !para) continue;
        // Durante o nascimento autônomo, dois filhos podem partir da mesma âncora. As
        // relações continuam distintas no registro, mas desenhar a mesma reta duas
        // vezes somaria brilho até elas se separarem — aparência de peso sem semântica.
        const segmento = `${de.x},${de.y},${de.z}|${para.x},${para.y},${para.z}`;
        const inverso = `${para.x},${para.y},${para.z}|${de.x},${de.y},${de.z}`;
        if (segmentosVistos.has(segmento) || segmentosVistos.has(inverso)) continue;
        segmentosVistos.add(segmento);
        saida.push({ from: de, to: para });
      }
      return saida;
    },
    renderPositionFor(runtimeNodeId) {
      return bodies?.renderPositionFor(runtimeNodeId) ?? null;
    },
    panelSelection(runtimeNodeId) {
      const node = nodeById.get(runtimeNodeId);
      if (!node) return null;
      const endpoint =
        node.operational?.provider && node.operational.endpoint
          ? ` Endpoint ${node.operational.provider}, ${node.operational.endpoint}.`
          : '';
      return {
        runtimeNodeId,
        linkedEntityId:
          node.operational?.entity && basePositions.has(node.operational.entity)
            ? node.operational.entity
            : null,
        description: `${node.title}.${endpoint}`,
      };
    },
    setDimmed(dimmed, relatedEntityId) {
      camadaAtenuada = dimmed;
      entidadeRelacionada = relatedEntityId;
      // O realce afirma trabalho aberto, não mera posição na cauda do log. Assim um
      // fechamento volta ao repouso imediatamente, enquanto uma chamada longa não
      // desaparece só porque outros eventos chegaram depois dela.
      aplicarEnfase();
    },
    pulse(intensity, seconds = 0, motion = true) {
      const atual = bodies;
      if (!atual) return;
      const acesos = atividadeHabilitada
        ? new Set(atividade.activeNodeIds)
        : new Set<string>();
      for (const id of acesos) atual.setActivity(id, intensity);
      // Quem saiu do fluxo apaga uma vez só, e não a cada quadro.
      for (const id of pulsando) if (!acesos.has(id)) atual.setActivity(id, 0);
      pulsando = acesos;
      if (linhasDaAtividade) linhasDaAtividade.visible = atividadeHabilitada;
      if (fluxoDaAtividade && atividadeHabilitada) {
        // O brilho de repouso do fio continua respirando junto com as placas; o que o
        // relógio acrescenta é o pulso que **anda**. São duas coisas: uma diz "há
        // trabalho aqui", a outra diz "para onde ele está indo".
        const limitada = Math.max(0, Math.min(1, intensity));
        fluxoDaAtividade.advance(seconds, 0.18 + limitada * 0.42, motion);
      }
    },
    setActivityEnabled(enabled) {
      atividadeHabilitada = enabled;
      if (linhasDaAtividade) linhasDaAtividade.visible = enabled;
      aplicarEnfase();
      if (!enabled) {
        if (bodies) {
          for (const id of pulsando) bodies.setActivity(id, 0);
        }
        pulsando = new Set();
      }
    },
    cognitive() {
      return estados;
    },
    activeIds() {
      return atividadeHabilitada ? new Set(atividade.activeNodeIds) : new Set();
    },
    activePanelIds() {
      return atividadeHabilitada ? new Set(atividade.activePanelIds) : new Set();
    },
    setSelected(runtimeNodeId: string | null) {
      const atual = bodies;
      if (!atual) return;
      if (selecionado !== null && selecionado !== runtimeNodeId) {
        atual.setExpanded(selecionado, false);
        atual.setElevated(selecionado, false);
      }
      selecionado = runtimeNodeId;
      if (selecionado !== null && nodeById.has(selecionado)) {
        atual.setExpanded(selecionado, true);
        atual.setElevated(selecionado, true);
      }
      // Escolher move a placa e muda quem acende. As linhas de atividade saem das
      // posições desenhadas, então elas precisam ser refeitas aqui — do contrário a
      // ligação fica apontando para a cota de onde a placa acabou de subir.
      recalcularAtividade();
      if (settling) atualizarConexoesDeAssentamento();
      else reconstruirConexoes();
      aplicarEnfase();
    },
    dispose() {
      clear();
    },
  };
}

function materialsOf(material: THREE.Material | THREE.Material[]): THREE.Material[] {
  return Array.isArray(material) ? material : [material];
}
