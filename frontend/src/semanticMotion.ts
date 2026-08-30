// Movimento autônomo que continua sendo layout, e não decoração.
//
// A posição-alvo vem das mesmas políticas que assentam a projeção. Este módulo não
// inventa órbita, ruído nem deriva: ele só dá continuidade temporal quando a topologia
// muda. Âncoras chegam imediatamente ao alvo; satélites existentes partem de onde já
// estavam; satélites novos nascem no vizinho causal mais próximo e se assentam.

import type { ProjectionEdge, ProjectionNode } from './contract';
import type { LayoutMap, Vec3 } from './layout';

/** Tempo perceptivo do assentamento. Curto o bastante para a cena não ficar atrasada. */
const TEMPO_DE_ASSENTAMENTO = 0.42;
/** Abaixo deste deslocamento não há movimento visível nem motivo para reescrever GPU. */
const LIMIAR_DE_REPOUSO = 0.035;

function copiar(ponto: Vec3): Vec3 {
  return { x: ponto.x, y: ponto.y, z: ponto.z };
}

function vizinhanca(edges: readonly ProjectionEdge[]): Map<string, string[]> {
  const mapa = new Map<string, string[]>();
  for (const edge of edges) {
    mapa.set(edge.source, [...(mapa.get(edge.source) ?? []), edge.target]);
    mapa.set(edge.target, [...(mapa.get(edge.target) ?? []), edge.source]);
  }
  return mapa;
}

/**
 * Preserva a referência espacial de cada âncora sem descolar seus satélites.
 *
 * `layoutAtlas` recompõe o conjunto inteiro quando a topologia muda. Se uma âncora já
 * existente trocar de slot nessa recomposição, congelar apenas a âncora deixaria todos
 * os alvos dependentes orbitando a posição fantasma que ela teria ocupado. A BFS
 * multiorigem atribui cada nó à âncora topologicamente mais próxima e translada o grupo
 * inteiro pela diferença entre alvo novo e posição já desenhada.
 */
export function preserveAnchorTargets(
  nodes: readonly ProjectionNode[],
  edges: readonly ProjectionEdge[],
  targets: LayoutMap,
  previous: LayoutMap,
): LayoutMap {
  const neighbours = vizinhanca(edges);
  const anchors = nodes.filter((node) => node.visual.isAnchor && targets.has(node.id));
  const owner = new Map<string, string>();
  const queue: string[] = [];
  for (const anchor of anchors) {
    owner.set(anchor.id, anchor.id);
    queue.push(anchor.id);
  }
  for (let cursor = 0; cursor < queue.length; cursor += 1) {
    const id = queue[cursor]!;
    const anchorId = owner.get(id)!;
    for (const neighbour of neighbours.get(id) ?? []) {
      if (owner.has(neighbour)) continue;
      owner.set(neighbour, anchorId);
      queue.push(neighbour);
    }
  }

  const existing = anchors.filter((anchor) => previous.has(anchor.id));
  // No primeiro quadro não existe memória espacial a preservar; manter o resultado do
  // layout evita permutar âncoras novas só para reconstruir a mesma composição.
  if (existing.length === 0) {
    return new Map([...targets].map(([id, point]) => [id, copiar(point)]));
  }

  const desiredByAnchor = new Map<string, Vec3>();
  const occupied: Vec3[] = [];
  for (const anchor of existing) {
    const old = copiar(previous.get(anchor.id)!);
    desiredByAnchor.set(anchor.id, old);
    occupied.push(old);
  }

  // Inserir uma âncora pode reordenar todos os slots crus. O slot cru da nova costuma
  // ser justamente o lugar que uma âncora antiga preservou; usá-lo causaria colisão.
  // Entre os slots que a nova composição oferece, ela recebe o mais distante dos já
  // ocupados. O território ligado a ela recebe o mesmo delta logo abaixo.
  const candidates = anchors.map((anchor) => ({
    anchorId: anchor.id,
    point: copiar(targets.get(anchor.id)!),
  }));
  const usedCandidates = new Set<number>();
  const news = anchors
    .filter((anchor) => !previous.has(anchor.id))
    .sort((left, right) => left.id.localeCompare(right.id));
  for (const anchor of news) {
    const own = candidates.findIndex((candidate) => candidate.anchorId === anchor.id);
    let best = own >= 0 && !usedCandidates.has(own)
      ? own
      : candidates.findIndex((_, index) => !usedCandidates.has(index));
    let bestDistance = -1;
    for (let index = 0; index < candidates.length; index += 1) {
      if (usedCandidates.has(index)) continue;
      const candidate = candidates[index]!.point;
      const distance = Math.min(
        ...occupied.map((point) =>
          Math.hypot(candidate.x - point.x, candidate.y - point.y, candidate.z - point.z),
        ),
      );
      if (distance > bestDistance) {
        best = index;
        bestDistance = distance;
      }
    }
    if (best < 0) continue;
    usedCandidates.add(best);
    const chosen = copiar(candidates[best]!.point);
    desiredByAnchor.set(anchor.id, chosen);
    occupied.push(chosen);
  }

  const deltaByAnchor = new Map<string, Vec3>();
  for (const anchor of anchors) {
    const target = targets.get(anchor.id)!;
    const desired = desiredByAnchor.get(anchor.id) ?? target;
    deltaByAnchor.set(anchor.id, {
      x: desired.x - target.x,
      y: desired.y - target.y,
      z: desired.z - target.z,
    });
  }

  const result: LayoutMap = new Map();
  for (const [id, target] of targets) {
    const delta = deltaByAnchor.get(owner.get(id) ?? '');
    result.set(id, {
      x: target.x + (delta?.x ?? 0),
      y: target.y + (delta?.y ?? 0),
      z: target.z + (delta?.z ?? 0),
    });
  }
  return result;
}

/**
 * A origem visual de uma projeção nova.
 *
 * A busca é não dirigida porque a direção da aresta é semântica, não espacial:
 * `modelo → provedor` e `modelo → evento` apontam em sentidos diferentes da mesma
 * hierarquia. O primeiro nó já desenhado vence; depois, a âncora-alvo mais próxima.
 */
export function motionStartPositions(
  nodes: readonly ProjectionNode[],
  edges: readonly ProjectionEdge[],
  targets: LayoutMap,
  previous: LayoutMap,
): LayoutMap {
  const anchors = new Set(nodes.filter((node) => node.visual.isAnchor).map((node) => node.id));
  const neighbours = vizinhanca(edges);
  const result: LayoutMap = new Map();

  for (const node of nodes) {
    const target = targets.get(node.id);
    if (!target) continue;
    if (anchors.has(node.id)) {
      // Uma âncora existente não muda de lugar porque chegaram novos satélites. A
      // coordenada anterior é a referência espacial; o alvo só inaugura âncora nova.
      result.set(node.id, copiar(previous.get(node.id) ?? target));
      continue;
    }
    const old = previous.get(node.id);
    if (old) {
      result.set(node.id, copiar(old));
      continue;
    }

    const visited = new Set([node.id]);
    let frontier = [node.id];
    let origin: Vec3 | undefined;
    while (frontier.length > 0 && !origin) {
      const next: string[] = [];
      for (const id of frontier) {
        for (const neighbour of neighbours.get(id) ?? []) {
          if (visited.has(neighbour)) continue;
          visited.add(neighbour);
          origin = previous.get(neighbour);
          if (!origin && anchors.has(neighbour)) origin = targets.get(neighbour);
          if (origin) break;
          next.push(neighbour);
        }
        if (origin) break;
      }
      frontier = next;
    }
    result.set(node.id, copiar(origin ?? target));
  }
  return result;
}

export interface MotionStep {
  moved: boolean;
  settled: boolean;
}

/**
 * Avança posições em direção aos alvos e devolve se houve trabalho visual.
 *
 * A exponencial torna o resultado independente da taxa de quadros. Movimento reduzido
 * não desliga a semântica: aplica o estado final imediatamente, sem transição.
 */
export function advanceMotion(
  current: LayoutMap,
  targets: LayoutMap,
  anchoredIds: ReadonlySet<string>,
  deltaSeconds: number,
  reducedMotion = false,
): MotionStep {
  const alpha = reducedMotion
    ? 1
    : 1 - Math.exp(-Math.max(deltaSeconds, 0) / TEMPO_DE_ASSENTAMENTO);
  let moved = false;
  let settled = true;

  for (const [id, target] of targets) {
    const point = current.get(id);
    if (!point) {
      current.set(id, copiar(target));
      moved = true;
      continue;
    }
    // A posição corrente é a autoridade das âncoras existentes. O layout pode mudar
    // ao receber novos nós, mas a referência espacial não acompanha essa recomposição.
    if (anchoredIds.has(id)) continue;
    const dx = target.x - point.x;
    const dy = target.y - point.y;
    const dz = target.z - point.z;
    const distance = Math.hypot(dx, dy, dz);
    if (distance <= LIMIAR_DE_REPOUSO || reducedMotion) {
      if (distance > 0) {
        point.x = target.x;
        point.y = target.y;
        point.z = target.z;
        moved = true;
      }
      continue;
    }
    settled = false;
    if (alpha === 0) continue;
    point.x += dx * alpha;
    point.y += dy * alpha;
    point.z += dz * alpha;
    moved = true;
  }
  return { moved, settled };
}
