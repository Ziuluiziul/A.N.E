import { describe, expect, it } from 'vitest';

import { composeLayout } from './composeLayout';
import { ALCANCE_DO_SISTEMA, groupQuorumSystems } from './operationalLayout';
import { comExecucoes } from './quorumScenario';
import { MODEL_DOMAIN, PROVIDER_DOMAIN } from './modelsLayout';
import { node, edge } from './fixture';
import type { Projection } from './contract';

/** Cenário com execuções de quórum E os modelos que as avaliam (com provedores). */
function cenario(quantas: number): Projection {
  const projection = comExecucoes(quantas);
  const modelos = new Set<string>();
  for (const e of projection.edges) {
    if (e.matchedBy === 'quorum-model') modelos.add(e.target);
  }
  const provedores = new Set<string>();
  for (const m of modelos) {
    const provider = m.split('/')[2]!;
    provedores.add(provider);
    projection.nodes.push(
      node(m, {
        kind: 'quorum-member',
        layer: 'operational',
        path: null,
        canonicalState: 'canonical',
        domainId: MODEL_DOMAIN,
        domainLabel: 'modelos',
        operational: { provider },
      }),
    );
    projection.edges.push(
      edge(`op/provider/${provider}`, m, 'operational', 'operational', {
        matchedBy: 'model-provider',
      }),
    );
  }
  for (const pr of provedores) {
    projection.nodes.push(
      node(`op/provider/${pr}`, {
        kind: 'agent',
        layer: 'operational',
        path: null,
        canonicalState: 'canonical',
        domainId: PROVIDER_DOMAIN,
        domainLabel: 'provedores',
        operational: {},
      }),
    );
  }
  return projection;
}

describe('nuvem viva assentada por forças', () => {
  it('mantém modelo e provedor na mesma nuvem', () => {
    const projection = cenario(80);
    const { positions, origin } = composeLayout(projection);
    const modeloProvedor: number[] = [];
    for (const e of projection.edges) {
      if (e.matchedBy !== 'model-provider') continue;
      const a = positions.get(e.source)!;
      const b = positions.get(e.target)!;
      modeloProvedor.push(Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z));
    }
    expect(modeloProvedor.length).toBeGreaterThan(0);
    expect(Math.max(...modeloProvedor)).toBeLessThan(80);
    expect(origin.modelos).toEqual(origin.provedores);
  });

  it('mantém os sistemas locais separados (sem sobreposição)', () => {
    const projection = cenario(100);
    const { positions } = composeLayout(projection);
    const paineis = projection.nodes
      .filter((no) => no.kind === 'quorum-panel')
      .map((no) => positions.get(no.id)!);
    let pares = 0;
    let muitoPerto = 0;
    for (let i = 0; i < paineis.length; i += 1) {
      for (let j = i + 1; j < paineis.length; j += 1) {
        const d = Math.hypot(
          paineis[i]!.x - paineis[j]!.x,
          paineis[i]!.y - paineis[j]!.y,
          paineis[i]!.z - paineis[j]!.z,
        );
        pares += 1;
        if (d < ALCANCE_DO_SISTEMA * 0.5) muitoPerto += 1;
      }
    }
    expect(pares).toBeGreaterThan(1000);
    expect(muitoPerto).toBe(0);
  });

  it('preserva a leitura do sistema local: decisão acima do painel', () => {
    // As execuções mantêm o leque que já as dispunha; o sistema local anda rígido, então a
    // decisão continua acima do painel na mesma direção de antes.
    const projection = cenario(40);
    const { positions } = composeLayout(projection);
    const { systems } = groupQuorumSystems(projection);
    let conferidos = 0;
    for (const sistema of systems) {
      if (sistema.panelNodeId === null || sistema.decisionIds.length === 0) continue;
      const painel = positions.get(sistema.panelNodeId)!;
      const decisao = positions.get(sistema.decisionIds[0]!)!;
      expect(decisao.y).toBeGreaterThan(painel.y);
      conferidos += 1;
    }
    expect(conferidos).toBeGreaterThan(20);
  });
});
