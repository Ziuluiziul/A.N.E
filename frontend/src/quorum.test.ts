import { describe, expect, it } from 'vitest';

import {
  ContractError,
  QUORUM_ACTIONS,
  assertConsistent,
  type Projection,
  type QuorumAction,
} from './contract';
import { composeLayout } from './composeLayout';
import { buildRelationLines } from './edges';
import { edge, node, projectionFixture } from './fixture';

import { describePanel } from './panels';

function quorumFixture(action: QuorumAction = 'promote'): Projection {
  const projection = projectionFixture();
  const panel = node('op/quorum/panel-001/panel', {
    kind: 'quorum-panel',
    layer: 'operational',
    path: null,
    canonicalState: 'temporary',
    domainId: 'operacional/quorum',
    domainLabel: 'quórum',
    operational: { panelId: 'panel-001' },
  });
  // O avaliador é identidade canônica da nuvem de modelos, e não uma placa dentro da
  // execução: eram 114 delas para 7 modelos antes de 3.5-F.
  const member = node('op/model/groq/qwen/qwen3', {
    kind: 'quorum-member',
    layer: 'operational',
    path: null,
    canonicalState: 'temporary',
    domainId: 'operacional/modelos',
    domainLabel: 'modelos',
    operational: {
      provider: 'groq',
      endpoint: 'qwen/qwen3',
      executionCount: 1,
    },
  });
  const vote = node('op/quorum/panel-001/vote/01', {
    kind: 'quorum-vote',
    layer: 'operational',
    path: null,
    canonicalState: 'temporary',
    domainId: 'operacional/quorum',
    domainLabel: 'quórum',
    operational: {
      panelId: 'panel-001',
      provider: 'groq',
      endpoint: 'qwen/qwen3',
      family: 'qwen',
      decision: 'approve',
      confidence: 0.86,
      reasoningBlockDetected: true,
      reasoningBlockRemoved: true,
    },
  });
  const decision = node('op/quorum/panel-001/decision', {
    kind: 'quorum-decision',
    layer: 'operational',
    path: null,
    canonicalState: 'temporary',
    domainId: 'operacional/quorum',
    domainLabel: 'quórum',
    operational: {
      panelId: 'panel-001',
      action,
      tally: { approve: 1, reject: 0, revise: 0, abstain: 0 },
    },
  });
  projection.nodes.push(panel, member, vote, decision);
  projection.edges.push(
    edge(panel.id, member.id, 'operational', 'operational', { matchedBy: 'quorum-model' }),
    edge(panel.id, vote.id, 'operational', 'operational'),
    edge(vote.id, decision.id, 'operational', 'operational'),
  );
  projection.meta.operationalSource = 'quorum';
  projection.meta.counts.operationalNodes = 4;
  return projection;
}

describe('contrato operacional do quórum', () => {
  it('mantém compatibilidade com a projeção v1.0 sem metadado operacional', () => {
    const antiga = projectionFixture();
    antiga.meta.contractVersion = '1.0.0';
    expect(() => assertConsistent(antiga)).not.toThrow();
  });

  it.each(QUORUM_ACTIONS)('aceita a ação fechada %s', (action) => {
    expect(() => assertConsistent(quorumFixture(action))).not.toThrow();
  });

  it('recusa JSON arbitrário no metadado que deveria ser lista branca', () => {
    const projection = quorumFixture();
    const vote = projection.nodes.find((item) => item.kind === 'quorum-vote')!;
    (vote.operational as Record<string, unknown>).raw_response = '<think>privado</think>';
    expect(() => assertConsistent(projection)).toThrow(ContractError);
  });

  it('recusa tag de raciocínio mesmo escondida num campo estrutural', () => {
    const projection = quorumFixture();
    const member = projection.nodes.find((item) => item.kind === 'quorum-member')!;
    member.operational!.provider = '<think>não é provedor</think>';
    expect(() => assertConsistent(projection)).toThrow(/provider operacional inválido/);
  });

  it('não contém resposta livre nem bloco de raciocínio na forma válida', () => {
    const serialized = JSON.stringify(quorumFixture()).toLowerCase();
    expect(serialized).not.toContain('raw_response');
    expect(serialized).not.toContain('final_response');
    expect(serialized).not.toContain('<think');
  });
});

describe('gramática visual do painel', () => {
  it('os quatro papéis viram painel deliberativo, distinguidos por texto', () => {
    // Até a ADR-002 cada papel tinha uma primitiva própria — aro, hexágono vazado,
    // losango, selo. A forma dizia a ontologia, e o texto era acessório. Agora os
    // três são o mesmo tipo de painel, e quem os separa é o que está escrito. O
    // avaliador saiu da conta em 3.5-F: ele deixou de ser papel da execução e virou
    // identidade da nuvem de modelos, com painel de modelo e não de deliberação.
    const projection = quorumFixture();
    const papeis = projection.nodes.filter(
      (item) => item.kind.startsWith('quorum-') && item.domainId === 'operacional/quorum',
    );
    expect(papeis).toHaveLength(3);

    const descritores = papeis.map(describePanel);
    for (const descritor of descritores) {
      expect(descritor.panelType).toBe('quorum');
      expect(descritor.variant).toBe('deliberativa');
      // Categoria por extenso no cabeçalho: nada aqui depende de cor nem de silhueta.
      expect(descritor.category).toBe('Deliberação');
      expect(descritor.header.startsWith('Deliberação')).toBe(true);
    }
    expect(new Set(descritores.map((item) => item.title)).size).toBe(3);
  });

  it('assenta os papéis da execução e desenha suas arestas operacionais', () => {
    const projection = quorumFixture();
    // Desde 3.5-A quem assenta a camada viva é o observatório, não o atlas: `layoutAtlas`
    // recusa nó operacional de propósito, para que acumular execuções não mexa no anel
    // de âncoras do corpus. A composição é que devolve os dois frames no mesmo mundo.
    const composto = composeLayout(projection);
    const positions = composto.positions;
    for (const node of projection.nodes.filter((item) => item.kind.startsWith('quorum-'))) {
      expect(positions.has(node.id), node.id).toBe(true);
    }
    // O avaliador é assentado, mas na nuvem de modelos — não dentro da execução.
    expect(composto.ids.modelos.has('op/model/groq/qwen/qwen3')).toBe(true);
    expect(composto.ids.operacional.has('op/model/groq/qwen/qwen3')).toBe(false);
    const operational = buildRelationLines(projection.edges, positions).find(
      (build) => build.family === 'operational',
    );
    expect(operational).toBeDefined();
    expect(operational!.lines.geometry.getAttribute('position').count).toBeGreaterThan(0);
    operational!.lines.geometry.dispose();
    const lineMaterials = Array.isArray(operational!.lines.material)
      ? operational!.lines.material
      : [operational!.lines.material];
    for (const material of lineMaterials) material.dispose();
    operational!.markers?.geometry.dispose();
    const markerMaterial = operational!.markers?.material;
    if (markerMaterial) {
      const markerMaterials = Array.isArray(markerMaterial) ? markerMaterial : [markerMaterial];
      for (const material of markerMaterials) material.dispose();
    }
  });
});
