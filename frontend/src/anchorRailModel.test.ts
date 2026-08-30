import { describe, expect, it } from 'vitest';

import { ANCHOR_SIDE, anchorName, anchorTargets } from './anchorRailModel';
import type { Projection, ProjectionNode } from './contract';
import { projectionFixture } from './fixture';
import { PROVIDER_DOMAIN, WORKER_DOMAIN } from './modelsLayout';

function operationalAnchor(id: string, domainId: string, title: string): ProjectionNode {
  const base = projectionFixture().nodes[0]!;
  return {
    ...base,
    id,
    title,
    shortLabel: title,
    kind: 'agent',
    layer: 'operational',
    domainId,
    domainLabel: domainId,
    visual: { ...base.visual, isAnchor: true },
    operational: {},
  };
}

describe('o rail das âncoras', () => {
  it('lista somente a política isAnchor e agrupa na ordem da cena', () => {
    const fixture = projectionFixture();
    const free = { ...fixture.nodes.find((node) => !node.visual.isAnchor)! };
    free.id = 'solto';
    const projection: Projection = {
      ...fixture,
      nodes: [
        free,
        operationalAnchor('op/provider/teste', PROVIDER_DOMAIN, 'Teste Provider'),
        operationalAnchor('op/worker/teste', WORKER_DOMAIN, 'Teste Worker'),
        ...fixture.nodes,
      ],
    };

    const targets = anchorTargets(projection);
    expect(targets.some((target) => target.id === 'solto')).toBe(false);
    expect(targets.find((target) => target.id === 'op/provider/teste')?.group).toBe('providers');
    // Trabalhador saiu da régua: sete papéis de configuração não são destino de câmera.
    // Ele continua na cena e continua selecionável — o que sai é o atalho.
    expect(targets.find((target) => target.id === 'op/worker/teste')).toBeUndefined();
    const groupOrder = [...new Set(targets.map((target) => target.group))];
    expect(groupOrder).toEqual(['providers', 'knowledge']);
    expect(targets.every((target) => target.label !== '' && target.name !== '')).toBe(true);
  });

  it('mostra o nome do sistema, e não uma reescrita dele', () => {
    expect(anchorName({ shortLabel: 'MOC — Física Teórica', title: 'MOC — Física Teórica' })).toBe(
      'MOC — Física Teórica',
    );
    expect(anchorName({ shortLabel: 'critico-epistemologico', title: 'Trabalhador — critico-epistemologico' })).toBe(
      'critico-epistemologico',
    );
  });

  it('cai no título quando o rótulo curto vem vazio, para o botão nunca ficar mudo', () => {
    expect(anchorName({ shortLabel: '   ', title: 'Índice do Vault' })).toBe('Índice do Vault');
  });

  it('mantém o título inteiro no alvo, que é o que vira tooltip e nome acessível', () => {
    const targets = anchorTargets({
      ...projectionFixture(),
      nodes: [operationalAnchor('op/provider/teste', PROVIDER_DOMAIN, 'Provedor — teste')],
    });
    expect(targets[0]?.label).toBe('Provedor — teste');
  });

  it('conhecimento e provedores compartilham a régua direita', () => {
    expect(ANCHOR_SIDE.knowledge).toBe('direita');
    expect(ANCHOR_SIDE.providers).toBe('direita');
  });
});
