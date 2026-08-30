import { edge, node, projectionFixture } from './fixture';
import type { Projection, ProjectionEdge, ProjectionNode } from './contract';

/** Uma execução completa: painel, três avaliadores, um voto cada, uma decisão. */
export function execucao(panelId: string, criadaEm: string): {
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
  // A topologia que o backend produz desde 3.5-F: o avaliador é uma identidade canônica
  // da nuvem de modelos, o painel se liga a ela, e o voto — que declara provedor e
  // endpoint — pende do painel. Nenhuma placa de avaliador dentro da execução.
  for (let i = 0; i < 3; i += 1) {
    const provider = `prov${i}`;
    const endpoint = `modelo-${i}`;
    const votoId = `op/quorum/${panelId}/vote/0${i}`;
    nodes.push(
      node(votoId, {
        ...base,
        kind: 'quorum-vote',
        operational: { panelId, provider, endpoint },
      }),
    );
    edges.push(
      edge(painel.id, `op/model/${provider}/${endpoint}`, 'operational', 'operational', {
        matchedBy: 'quorum-model',
      }),
      edge(painel.id, votoId, 'operational', 'operational'),
    );
  }
  const decisaoId = `op/quorum/${panelId}/decision`;
  nodes.push(node(decisaoId, { ...base, kind: 'quorum-decision', operational: { panelId } }));
  edges.push(edge(`op/quorum/${panelId}/vote/00`, decisaoId, 'operational', 'operational'));
  return { nodes, edges };
}

/** Várias execuções de quórum, sem modelo nem provedor — a topologia nua da nuvem viva. */
export function comExecucoes(quantidade: number, inicio = 1): Projection {
  const projection = projectionFixture();
  const nodes = [...projection.nodes];
  const edges = [...projection.edges];
  for (let i = 0; i < quantidade; i += 1) {
    const indice = inicio + i;
    const dia = String(indice).padStart(2, '0');
    const { nodes: n, edges: e } = execucao(
      `exec${String(indice).padStart(4, '0')}`,
      `2026-07-${dia.length > 2 ? '01' : dia}T0${indice % 10}:00:00+00:00`,
    );
    nodes.push(...n);
    edges.push(...e);
  }
  return { ...projection, nodes, edges };
}

/** Liga cada execução a uma entidade do corpus, como faz a aresta `quorum-entity`. */
export function comAssunto(
  projection: Projection,
  paresPorPainel: Record<string, string>,
): Projection {
  const edges = [...projection.edges];
  for (const [panelId, alvo] of Object.entries(paresPorPainel)) {
    edges.push(
      edge(`op/quorum/${panelId}/panel`, alvo, 'operational', 'operational', {
        matchedBy: 'quorum-entity',
      }),
    );
  }
  return { ...projection, edges };
}
