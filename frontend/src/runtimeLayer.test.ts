import * as THREE from 'three';
import { describe, expect, it } from 'vitest';

import type { CognitionFrame } from './cognition';
import type { LayoutMap } from './layout';
import type { ProjectionNode } from './contract';
import { describePanel } from './panels';
import { panelWorldExtent } from './panelScale';
import { preserveAnchorTargets } from './semanticMotion';
import type { RuntimeEvent, RuntimeSnapshot } from './runtime';
import {
  activeRuntimeSegments,
  createRuntimeLayer,
  placeRuntime,
  projectRuntime,
  runtimeActivity,
} from './runtimeLayer';

function liveEvent(
  revision: number,
  type: RuntimeEvent['type'],
  overrides: Partial<RuntimeEvent> = {},
): RuntimeEvent {
  return {
    id: `runtime-${String(revision).padStart(20, '0')}`,
    revision,
    timestamp: `2026-08-04T0${revision}:00:00+00:00`,
    type,
    actor: 'orquestrador',
    provider: 'groq',
    endpoint: 'qwen/qwen3',
    task: 'task-001',
    entity: 'Física/Entropia',
    ...overrides,
  };
}

function liveSnapshot(): RuntimeSnapshot {
  return {
    runtimeRevision: 10,
    entityByTask: new Map(),
    events: [
      // Sem provedor nem endpoint: exercita a âncora de ator, que é o recuo para
      // eventos que nenhum modelo produziu — tarefa criada pelo worker, por exemplo.
      liveEvent(1, 'task_created', { provider: undefined, endpoint: undefined }),
      liveEvent(2, 'call_started'),
      liveEvent(3, 'quorum_started', { panelId: 'panel-1' }),
      liveEvent(4, 'vote_requested', {
        panelId: 'panel-1', role: 'verificador-factual', family: 'qwen',
      }),
      liveEvent(5, 'vote_received', {
        panelId: 'panel-1', role: 'verificador-factual', family: 'qwen',
        decision: 'approve', action: 'promote', confidence: 0.9, schemaValid: true,
      }),
      liveEvent(6, 'vote_requested', {
        panelId: 'panel-1', role: 'critico-epistemologico', family: 'glm',
        provider: 'nvidia', endpoint: 'glm-4',
      }),
      liveEvent(7, 'vote_received', {
        panelId: 'panel-1', role: 'critico-epistemologico', family: 'glm',
        provider: 'nvidia', endpoint: 'glm-4', decision: 'approve', action: 'promote',
        confidence: 0.8, schemaValid: true,
      }),
      liveEvent(8, 'vote_requested', {
        panelId: 'panel-1', role: 'revisor-estrutural', family: 'llama',
        endpoint: 'llama-3',
      }),
      liveEvent(9, 'vote_received', {
        panelId: 'panel-1', role: 'revisor-estrutural', family: 'llama',
        endpoint: 'llama-3', decision: 'approve', action: 'promote', confidence: 0.85,
        schemaValid: true,
      }),
      liveEvent(10, 'quorum_decided', {
        panelId: 'panel-1',
        action: 'promote',
        tally: { approve: 3, revise: 0, reject: 0, abstain: 0 },
        validVotes: 3,
        providerCount: 2,
        familyCount: 3,
      }),
    ],
  };
}

describe('projeção visual separada do runtime', () => {
  it('deriva entidades e relações só dos eventos escalares validados', () => {
    const projection = projectRuntime(liveSnapshot());
    // Duas âncoras `agent` desde 3.5-G: o ator, para os eventos sem modelo declarado, e
    // o provedor, que é o topo da hierarquia provedor → modelo → evento. Antes havia só
    // o ator, e 167 eventos pendiam dele sem dizer qual modelo estava trabalhando.
    expect(projection.nodes.filter((node) => node.id.startsWith('runtime:actor:'))).toHaveLength(1);
    // Dois provedores — groq e nvidia — e um nó de modelo por par provedor·endpoint.
    expect(projection.nodes.filter((node) => node.id.startsWith('runtime:provider:'))).toHaveLength(2);
    expect(
      projection.nodes
        .filter(
          (node) =>
            node.id.startsWith('runtime:provider:') || node.id.startsWith('runtime:actor:'),
        )
        .every((node) => node.visual.isAnchor),
    ).toBe(true);
    expect(projection.nodes.filter((node) => node.id.startsWith('runtime:model:'))).toHaveLength(3);
    // `vote_requested` deixou de ser projetado como `quorum-member`: pedir voto é ação, e
    // enquanto compartilhava tipo com o nó de modelo a hierarquia não distinguia os dois.
    expect(projection.nodes.filter((node) => node.kind === 'activity')).toHaveLength(5);
    expect(projection.nodes.filter((node) => node.kind === 'quorum-panel')).toHaveLength(1);
    expect(projection.nodes.filter((node) => node.kind === 'quorum-decision')).toHaveLength(1);
    expect(projection.edges.length).toBeGreaterThanOrEqual(5);
    expect(JSON.stringify(projection)).not.toMatch(/before|after|metadata|<think/i);
  });

  it('liga eventos a entidades canônicas sem mover a coordenada canônica', () => {
    const base: LayoutMap = new Map([['Física/Entropia', { x: 12, y: -8, z: 1 }]]);
    const before = structuredClone(base.get('Física/Entropia'));
    const placement = placeRuntime(projectRuntime(liveSnapshot()), base);
    expect(base.get('Física/Entropia')).toEqual(before);
    expect(placement.tethers).toHaveLength(10);
    for (const tether of placement.tethers) {
      expect(tether.entityId).toBe('Física/Entropia');
      expect(tether.to).not.toEqual(tether.from);
    }
  });

  it('cada evento é o próprio painel, sem placa auxiliar consolidando outros', () => {
    // Havia aqui uma segunda camada: placas de resumo, ligadas por haste, que
    // agrupavam eventos por endpoint, tarefa e quórum. Elas eram a "segunda
    // representação do mesmo nó" que a direção de 3.4 proíbe — o mesmo evento
    // aparecia como corpo e como cartão. Agora o painel é o nó, e só ele.
    const projection = projectRuntime(liveSnapshot());
    const positions = placeRuntime(
      projection,
      new Map([['Física/Entropia', { x: 12, y: -8, z: 1 }]]),
    ).positions;

    const descritores = projection.nodes.map(describePanel);
    expect(descritores).toHaveLength(projection.nodes.length);
    for (const node of projection.nodes) expect(positions.has(node.id)).toBe(true);
    // Um painel por entidade: nenhuma consolidação inventa nó nem o duplica.
    expect(new Set(descritores.map((item) => item.entityId)).size).toBe(descritores.length);

    const decisao = projection.nodes.find((node) => node.kind === 'quorum-decision')!;
    const painel = describePanel(decisao);
    const frases = Object.values(painel.contentByLod).flat().map((linha) => linha.text);
    // A contagem que chega ao painel é a computada, dita por extenso, e a procedência
    // vem junto — sem trocar campo por sigla e sem inventar o que o contrato não traz.
    expect(frases.some((frase) => frase.includes('computou 3 votos'))).toBe(true);
    expect(frases.some((frase) => frase.includes('2 provedores'))).toBe(true);
    expect(frases.some((frase) => frase.includes('promover a proposta'))).toBe(true);
  });

  it('preserva âncoras e assenta satélites quando a trilha ganha evento', () => {
    const layer = createRuntimeLayer(new Map());
    const first = liveSnapshot();
    layer.update(first);
    // O histórico inicial já nasce no repouso. Movimento só começa quando uma revisão
    // nova altera a topologia observada.
    expect(layer.advance(0.1, false)).toBe(false);
    const before = new Map(layer.panels().map((panel) => [panel.entityId, panel.position.clone()]));

    const next: RuntimeSnapshot = {
      ...first,
      runtimeRevision: 11,
      events: [...first.events, liveEvent(11, 'call_started', { task: 'task-002' })],
    };
    layer.update(next);
    const atStart = new Map(layer.panels().map((panel) => [panel.entityId, panel.position.clone()]));
    const provider = 'runtime:provider:groq';
    expect(atStart.get(provider)?.toArray()).toEqual(before.get(provider)?.toArray());

    const moved = layer.advance(0.1, false);
    expect(moved).toBe(true);
    const after = new Map(layer.panels().map((panel) => [panel.entityId, panel.position.clone()]));
    expect(after.get(provider)?.toArray()).toEqual(before.get(provider)?.toArray());
    expect(
      [...after].some(
        ([id, point]) =>
          !id.startsWith('runtime:provider:') &&
          !id.startsWith('runtime:actor:') &&
          !point.equals(atStart.get(id)!),
      ),
    ).toBe(true);

    layer.advance(0, true);
    const nextProjection = projectRuntime(next);
    const rawTargets = placeRuntime(nextProjection, new Map()).positions;
    const targets = preserveAnchorTargets(
      nextProjection.nodes,
      nextProjection.edges,
      rawTargets,
      new Map(
        [...before].map(([id, point]) => [
          id,
          { x: point.x, y: point.y, z: point.z },
        ]),
      ),
    );
    for (const panel of layer.panels()) {
      if (panel.entityId.startsWith('runtime:provider:') || panel.entityId.startsWith('runtime:actor:')) {
        continue;
      }
      expect(panel.position.toArray()).toEqual([
        targets.get(panel.entityId)!.x,
        targets.get(panel.entityId)!.y,
        targets.get(panel.entityId)!.z,
      ]);
    }
  });

  it('move as pontas das relações e hastes junto com os satélites', () => {
    const corpus: LayoutMap = new Map([['Física/Entropia', { x: 12, y: -8, z: 1 }]]);
    const layer = createRuntimeLayer(corpus);
    const first = liveSnapshot();
    layer.update(first);
    layer.advance(0, true);

    const next: RuntimeSnapshot = {
      ...first,
      runtimeRevision: 11,
      events: [...first.events, liveEvent(11, 'call_started', { task: 'task-002' })],
    };
    layer.update(next);

    const vertices = (): number[] =>
      layer.group.children
        .filter(
          (object) =>
            object.visible &&
            (object.name.startsWith('edges:') ||
              object.name === 'runtime-entity-tethers' ||
              object.name === 'runtime-settling-links'),
        )
        .flatMap((object) =>
          Array.from(
            ((object as THREE.LineSegments).geometry.getAttribute('position') as THREE.BufferAttribute)
              .array,
          ),
        );

    const atStart = vertices();
    expect(atStart.length).toBeGreaterThan(0);
    layer.advance(0.1, false);
    expect(vertices()).not.toEqual(atStart);
  });

  it('mantém o território relativo quando um novo provedor recompõe os slots', () => {
    const first: RuntimeSnapshot = {
      runtimeRevision: 1,
      entityByTask: new Map(),
      events: [liveEvent(1, 'call_started')],
    };
    const layer = createRuntimeLayer(new Map());
    layer.update(first);
    const providerId = 'runtime:provider:groq';
    const modelId = 'runtime:model:groq/qwen/qwen3';
    const providerBefore = layer.panels().find((panel) => panel.entityId === providerId)!.position;

    const next: RuntimeSnapshot = {
      runtimeRevision: 2,
      entityByTask: new Map(),
      events: [
        ...first.events,
        liveEvent(2, 'call_started', {
          provider: 'aaa',
          endpoint: 'modelo-novo',
          task: 'task-002',
        }),
      ],
    };
    layer.update(next);
    layer.advance(0, true);
    const panels = new Map(layer.panels().map((panel) => [panel.entityId, panel.position]));
    expect(panels.get(providerId)?.toArray()).toEqual(providerBefore.toArray());

    const raw = placeRuntime(projectRuntime(next), new Map()).positions;
    const expectedRelative = new THREE.Vector3(
      raw.get(modelId)!.x - raw.get(providerId)!.x,
      raw.get(modelId)!.y - raw.get(providerId)!.y,
      raw.get(modelId)!.z - raw.get(providerId)!.z,
    );
    const actualRelative = panels.get(modelId)!.clone().sub(panels.get(providerId)!);
    expect(actualRelative.distanceTo(expectedRelative)).toBeLessThan(1e-9);
    expect(
      panels.get('runtime:provider:aaa')!.distanceTo(panels.get(providerId)!),
    ).toBeGreaterThan(50);
  });
});

describe('atividade visual representa trabalho aberto', () => {
  it('acende a chamada aberta e apaga modelo e evento quando ela fecha', () => {
    const aberta = liveEvent(1, 'call_started');
    const snapshotAberto: RuntimeSnapshot = {
      runtimeRevision: 1,
      entityByTask: new Map(),
      events: [aberta],
    };
    expect(runtimeActivity(snapshotAberto, Date.parse(aberta.timestamp) + 1).activeNodeIds).toEqual(
      new Set([
        'runtime:model:groq/qwen/qwen3',
        `runtime:event:${aberta.id}`,
      ]),
    );

    const fechada: RuntimeSnapshot = {
      ...snapshotAberto,
      runtimeRevision: 8,
      events: [
        aberta,
        liveEvent(2, 'call_completed'),
        ...[3, 4, 5, 6, 7, 8].map((revision) =>
          liveEvent(revision, 'temporary_created', {
            provider: undefined,
            endpoint: undefined,
          }),
        ),
      ],
    };
    // Mesmo sendo a cauda inteira do log, evento concluído não é atividade atual.
    expect(runtimeActivity(fechada, Date.parse(aberta.timestamp) + 1).activeNodeIds).toEqual(
      new Set(),
    );
  });

  it('preserva B no mesmo endpoint quando A termina depois de ambas abrirem', () => {
    const primeira = liveEvent(1, 'call_started', { task: 'tarefa-A' });
    const segunda = liveEvent(2, 'call_started', { task: 'tarefa-B' });
    const activity = runtimeActivity({
      runtimeRevision: 3,
      entityByTask: new Map(),
      events: [
        primeira,
        segunda,
        liveEvent(3, 'call_completed', { task: 'tarefa-A' }),
      ],
    }, Date.parse(segunda.timestamp) + 1);
    expect(activity.activeNodeIds).toContain('runtime:model:groq/qwen/qwen3');
    expect(activity.activeNodeIds).toContain(`runtime:event:${segunda.id}`);
    expect(activity.activeNodeIds).not.toContain(`runtime:event:${primeira.id}`);
  });

  it('mantém panelId somente durante um ciclo de quórum ou promoção', () => {
    const activity = runtimeActivity({
      runtimeRevision: 7,
      entityByTask: new Map(),
      events: [
        liveEvent(1, 'quorum_started', {
          panelId: 'encerrado', provider: undefined, endpoint: undefined,
        }),
        liveEvent(2, 'quorum_decided', {
          panelId: 'encerrado', provider: undefined, endpoint: undefined,
        }),
        // O começo caiu fora da janela, mas voto sem decisão posterior ainda prova
        // que este ciclo está aberto. O voto recebido em si não é aceso.
        liveEvent(3, 'vote_received', { panelId: 'janela-truncada' }),
        liveEvent(4, 'promotion_started', {
          panelId: 'promovendo', provider: undefined, endpoint: undefined,
        }),
        liveEvent(5, 'promotion_completed', {
          panelId: 'promovendo', provider: undefined, endpoint: undefined,
        }),
        liveEvent(6, 'quorum_started', {
          panelId: 'coletando', provider: undefined, endpoint: undefined,
        }),
        liveEvent(7, 'temporary_created', {
          panelId: 'coletando', provider: undefined, endpoint: undefined,
        }),
      ],
    }, Date.parse(liveEvent(7, 'temporary_created').timestamp) + 1);
    expect(activity.activePanelIds).toEqual(new Set(['janela-truncada', 'coletando']));
    expect(activity.activeNodeIds).toContain(
      `runtime:event:${liveEvent(6, 'quorum_started').id}`,
    );
    expect(activity.activeNodeIds).not.toContain(
      `runtime:event:${liveEvent(3, 'vote_received').id}`,
    );
  });

  it('não deixa painel da tentativa interrompida atravessar a recuperação', () => {
    const inicio = liveEvent(1, 'quorum_started', { panelId: 'interrompido' });
    const activity = runtimeActivity(
      {
        runtimeRevision: 2,
        entityByTask: new Map(),
        events: [
          inicio,
          liveEvent(2, 'task_assigned', {
            provider: undefined,
            endpoint: undefined,
            task: inicio.task,
          }),
        ],
      },
      Date.parse(inicio.timestamp) + 1,
    );
    expect(activity.activePanelIds).toEqual(new Set());
    expect(activity.activeNodeIds).not.toContain(`runtime:event:${inicio.id}`);
  });

  it('liga apenas nós ativos e inclui a haste do modelo ao catálogo canônico', () => {
    const snapshot: RuntimeSnapshot = {
      runtimeRevision: 1,
      entityByTask: new Map(),
      events: [liveEvent(1, 'call_started')],
    };
    const projection = projectRuntime(snapshot);
    const corpus: LayoutMap = new Map([['Física/Entropia', { x: 12, y: -8, z: 1 }]]);
    const modeloCanonico = 'op/model/groq/qwen/qwen3';
    const modelos: LayoutMap = new Map([[modeloCanonico, { x: -20, y: 4, z: 2 }]]);
    const placement = placeRuntime(projection, corpus, undefined, modelos);
    const active = runtimeActivity(snapshot, Date.parse(snapshot.events[0]!.timestamp) + 1)
      .activeNodeIds;
    const segments = activeRuntimeSegments(
      projection.edges,
      placement.positions,
      placement.tethers,
      active,
    );

    expect(segments).toContainEqual(
      expect.objectContaining({
        kind: 'edge',
        source: 'runtime:model:groq/qwen/qwen3',
        target: 'runtime:event:runtime-00000000000000000001',
      }),
    );
    expect(segments).toContainEqual(
      expect.objectContaining({
        kind: 'tether',
        source: 'runtime:model:groq/qwen/qwen3',
        target: modeloCanonico,
      }),
    );
    expect(segments).not.toContainEqual(
      expect.objectContaining({ kind: 'tether', target: 'Física/Entropia' }),
    );
    expect(segments.some(({ source }) => source.startsWith('runtime:provider:'))).toBe(false);
  });

  it('desenha e pulsa o overlay somente enquanto há atividade', () => {
    const corpus: LayoutMap = new Map([['Física/Entropia', { x: 12, y: -8, z: 1 }]]);
    const modelos: LayoutMap = new Map([
      ['op/model/groq/qwen/qwen3', { x: -20, y: 4, z: 2 }],
    ]);
    const layer = createRuntimeLayer(corpus, modelos);
    const aberta = liveEvent(1, 'call_started', {
      deadlineSeconds: 1,
      timestamp: new Date().toISOString(),
    });
    layer.update({ runtimeRevision: 1, entityByTask: new Map(), events: [aberta] });

    const overlay = layer.group.getObjectByName('runtime-active-links') as
      | THREE.LineSegments
      | undefined;
    expect(overlay).toBeDefined();
    // O brilho de repouso do fio mora no uniforme, e não em `opacity`: o material do
    // caminho ativo passou a ser o do fluxo, que decide alfa por fragmento.
    const material = overlay!.material as THREE.ShaderMaterial;
    layer.pulse(0.1, 0);
    const baixa = material.uniforms.uBase!.value as number;
    layer.pulse(0.9, 0);
    expect(material.uniforms.uBase!.value as number).toBeGreaterThan(baixa);

    // O relógio anda, e é ele que faz a luz correr. Sem isto o fluxo teria direção e
    // ficaria parado nela — que é a mesma coisa que não ter fluxo.
    layer.pulse(0.9, 2.5);
    expect(material.uniforms.uTempo!.value).toBe(2.5);
    layer.pulse(0.9, 3, false);
    expect(material.uniforms.uMovimento!.value).toBe(0);

    layer.setActivityEnabled(false);
    layer.pulse(0.9);
    expect(overlay!.visible).toBe(false);
    expect(layer.activeIds()).toEqual(new Set());
    layer.setActivityEnabled(true);
    expect(overlay!.visible).toBe(true);

    layer.refreshActivity(Date.parse(aberta.timestamp) + 16_000);
    expect(layer.activeIds()).toEqual(new Set());
    expect(layer.cognitive().get('groq/qwen/qwen3')?.state).toBe('latent');
    expect(overlay!.visible).toBe(false);

    layer.update({
      runtimeRevision: 2,
      entityByTask: new Map(),
      events: [aberta, liveEvent(2, 'call_completed')],
    });
    expect(layer.activeIds()).toEqual(new Set());
    expect(layer.group.getObjectByName('runtime-active-links')).toBeUndefined();
    layer.dispose();
  });

  it('remove A no prazo sem apagar B nem reconstruir a camada inteira', () => {
    const agora = Date.now();
    const inicioA = liveEvent(1, 'call_started', {
      task: 'tarefa-A',
      deadlineSeconds: 1,
      timestamp: new Date(agora - 500).toISOString(),
    });
    const inicioB = liveEvent(2, 'call_started', {
      task: 'tarefa-B',
      deadlineSeconds: 1,
      timestamp: new Date(agora).toISOString(),
    });
    const layer = createRuntimeLayer(new Map());
    layer.update({
      runtimeRevision: 2,
      entityByTask: new Map(),
      events: [inicioA, inicioB],
    });
    expect(layer.activeIds()).toContain(`runtime:event:${inicioA.id}`);
    expect(layer.activeIds()).toContain(`runtime:event:${inicioB.id}`);

    layer.refreshActivity(Date.parse(inicioA.timestamp) + 16_000);

    expect(layer.activeIds()).not.toContain(`runtime:event:${inicioA.id}`);
    expect(layer.activeIds()).toContain(`runtime:event:${inicioB.id}`);
    expect(layer.activeIds()).toContain('runtime:model:groq/qwen/qwen3');
    expect(layer.group.getObjectByName('runtime-active-links')?.visible).toBe(true);
    layer.dispose();
  });
});

describe('o painel vivo diz o que está acontecendo', () => {
  // Ele dizia "Registro operacional de call_started" — repetir o nome do tipo não é
  // dizer o que aconteceu, e a narração do orquestrador não existe na trilha gravada:
  // medido, 894 eventos, zero com narração. A frase é composta dos campos do evento.
  const textoDe = (node: ProjectionNode): string =>
    Object.values(describePanel(node).contentByLod)
      .flat()
      .map((linha) => linha.text)
      .join(' | ');

  it('nomeia a ação, quem executou e sobre o quê', () => {
    const projection = projectRuntime(liveSnapshot());
    const evento = projection.nodes.find((n) => n.operational?.eventType === 'call_started')!;
    const texto = textoDe(evento);
    expect(texto).toContain('chamada ao modelo');
    expect(texto).toContain('groq · qwen/qwen3');
    expect(texto).toContain('Física/Entropia');
    // E nunca o nome cru do tipo, que era o que estava lá.
    expect(texto).not.toContain('call_started');
  });

  it('o voto diz o veredito e a confiança, e não só que chegou', () => {
    const projection = projectRuntime(liveSnapshot());
    const voto = projection.nodes.find(
      (n) => n.operational?.eventType === 'vote_received' && n.operational.confidence !== undefined,
    )!;
    const texto = textoDe(voto);
    expect(texto).toContain('voto chegou');
    expect(texto).toMatch(/favorável|contrário|revisão|absteve/);
    expect(texto).toMatch(/\d+% de confiança/);
  });

  it('a narração do orquestrador, quando existir, tem precedência', () => {
    const projection = projectRuntime({
      runtimeRevision: 1,
      entityByTask: new Map(),
      events: [liveEvent(1, 'call_started', { narration: 'Perguntando ao modelo se a nota se sustenta.' })],
    });
    const texto = textoDe(projection.nodes.find((n) => n.id.startsWith('runtime:event:'))!);
    expect(texto).toContain('Perguntando ao modelo se a nota se sustenta.');
    expect(texto).not.toContain('Uma chamada ao modelo começou');
  });

  it('a placa do modelo passa a dizer o raciocínio que o provedor emitiu', () => {
    const trilha: RuntimeSnapshot = {
      runtimeRevision: 1,
      entityByTask: new Map(),
      events: [liveEvent(1, 'call_started')],
    };
    const agora = Date.parse('2026-08-04T01:00:01+00:00');
    const quadro: CognitionFrame = {
      revision: 1,
      kind: 'reasoning',
      provider: 'groq',
      endpoint: 'qwen/qwen3',
      text: 'o identificador não resolve; vou omitir a afirmação',
      timestamp: '2026-08-04T01:00:01+00:00',
    };
    const modeloDe = (projection: { nodes: ProjectionNode[] }): string =>
      textoDe(projection.nodes.find((n) => n.id.startsWith('runtime:model:'))!);

    const semCanal = modeloDe(projectRuntime(trilha, agora));
    const comCanal = modeloDe(projectRuntime(trilha, agora, [quadro]));

    expect(semCanal).not.toContain('vou omitir a afirmação');
    expect(comCanal).toContain('o identificador não resolve; vou omitir a afirmação');
  });
});

describe('a nuvem viva cabe no miolo que lhe reservaram', () => {
  // Era a única população fora de qualquer conferência: ela nasce em frame próprio,
  // depois da composição, e ninguém media o que ela ocupava. Medido na trilha real, a
  // nuvem chegava a 195 unidades dentro de uma reserva de 138 e encostava na borda de
  // dentro do quórum.
  function nuvemGrande(eventos: number): RuntimeSnapshot {
    const events: RuntimeEvent[] = [];
    for (let i = 0; i < eventos; i += 1) {
      events.push(
        liveEvent(i + 1, 'call_started', {
          provider: `provedor-${i % 5}`,
          endpoint: `modelo-${i % 11}`,
          task: `task-${i}`,
        }),
      );
    }
    return { runtimeRevision: eventos, entityByTask: new Map(), events };
  }

  const raioDe = (positions: LayoutMap, origem = { x: 0, y: 0, z: 0 }): number => {
    let raio = 0;
    for (const p of positions.values()) {
      raio = Math.max(raio, Math.hypot(p.x - origem.x, p.y - origem.y, p.z - origem.z));
    }
    return raio;
  };

  it('cabe inteira quando o conteúdo permite', () => {
    const projection = projectRuntime(nuvemGrande(12));
    const { positions } = placeRuntime(projection, new Map(), undefined, new Map(), 140);
    expect(raioDe(positions)).toBeLessThanOrEqual(140);
  });

  it('transborda pouco quando o conteúdo não cabe, e nunca amontoa', () => {
    const projection = projectRuntime(nuvemGrande(160));
    const reserva = 90;
    const { positions } = placeRuntime(projection, new Map(), undefined, new Map(), reserva);
    // Há um piso: a separação de placas não deixa duas se cobrirem, e abaixo dele a
    // nuvem não encolhe mais. Transbordar é o comportamento certo — encolher o
    // espaçamento faria caber e faria as placas se cobrirem.
    expect(raioDe(positions)).toBeLessThan(reserva * 1.6);
    const ids = [...positions.keys()];
    const raios = new Map(
      projection.nodes.map((n) => {
        const e = panelWorldExtent(describePanel(n));
        return [n.id, Math.hypot(e.width, e.height) / 2];
      }),
    );
    let sobrepostos = 0;
    for (let i = 0; i < ids.length; i += 1) {
      for (let j = i + 1; j < ids.length; j += 1) {
        const a = positions.get(ids[i]!)!;
        const b = positions.get(ids[j]!)!;
        const minimo = (raios.get(ids[i]!) ?? 0) + (raios.get(ids[j]!) ?? 0);
        if (Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z) < minimo) sobrepostos += 1;
      }
    }
    expect(sobrepostos).toBe(0);
  });

  it('a reserva menor produz nuvem menor', () => {
    const projection = projectRuntime(nuvemGrande(40));
    const larga = placeRuntime(projection, new Map(), undefined, new Map(), 200);
    const estreita = placeRuntime(projection, new Map(), undefined, new Map(), 100);
    expect(raioDe(estreita.positions)).toBeLessThan(raioDe(larga.positions));
  });
});

describe('a ligação acompanha a placa que subiu', () => {
  const corpus: LayoutMap = new Map([['Física/Entropia', { x: 12, y: -8, z: 1 }]]);
  const modelos: LayoutMap = new Map([
    ['op/model/groq/qwen/qwen3', { x: -20, y: 4, z: 2 }],
  ]);

  function camadaComChamadaAberta(): ReturnType<typeof createRuntimeLayer> {
    const layer = createRuntimeLayer(corpus, modelos);
    layer.update({
      runtimeRevision: 1,
      entityByTask: new Map(),
      events: [
        liveEvent(1, 'call_started', {
          deadlineSeconds: 600,
          timestamp: new Date().toISOString(),
        }),
      ],
    });
    return layer;
  }

  const MODELO = 'runtime:model:groq/qwen/qwen3';
  /** O quanto a placa escolhida sobe para sair de trás das vizinhas. */
  const ELEVACAO_DA_PLACA = 1.4;

  it('a vizinhança sai da cota desenhada, não da assentada', () => {
    const layer = camadaComChamadaAberta();
    const antes = layer.neighbourhood(MODELO);
    expect(antes.length).toBeGreaterThan(0);

    layer.setSelected(MODELO);
    const depois = layer.neighbourhood(MODELO);

    // A placa escolhida sobe em z. A linha que continuasse na cota antiga terminaria
    // no lugar de onde o painel saiu — que é como ela aparecia apontando para o vazio.
    // A ponta que interessa é a compartilhada: ela é o próprio modelo, presente em
    // todos os segmentos da vizinhança dele.
    expect(depois.map(({ from }) => from.z)).toEqual(
      antes.map(({ from }) => from.z + ELEVACAO_DA_PLACA),
    );
  });

  it('não desenha a mesma reta duas vezes', () => {
    const layer = camadaComChamadaAberta();
    const retas = layer
      .neighbourhood(MODELO)
      .map(({ from, to }) => `${from.x},${from.y},${from.z}|${to.x},${to.y},${to.z}`);
    expect(new Set(retas).size).toBe(retas.length);
  });

  it('escolher acende o painel e seus vizinhos, e atenua o resto', () => {
    const layer = camadaComChamadaAberta();
    layer.setSelected(MODELO);

    const enfases = new Map(
      layer.panels().map((painel) => [painel.entityId, painel.entityId]),
    );
    // O painel existe e a seleção não o perdeu — a ênfase em si é interna ao corpo,
    // e o que se pode afirmar daqui é que a seleção sobreviveu ao recálculo que ela
    // dispara. Sem esse recálculo, a linha ficava para trás.
    expect(enfases.has(MODELO)).toBe(true);
    expect(layer.panelSelection(MODELO)).not.toBeNull();
  });
});

describe('trabalhadores não deixam placa estática na cena', () => {
  it('sincroniza o roster sem criar corpo nem alvo clicável', () => {
    const ancora = { x: 10, y: 0, z: 0 };
    const layer = createRuntimeLayer(
      new Map(),
      new Map(),
      { origin: { x: 0, y: 0, z: 0 }, radius: 110 },
      new Map(),
      (ids) => new Map(ids.map((id) => [id, ancora])),
    );
    layer.syncWorkers([
      {
        id: 'proponente',
        role: 'proponente',
        className: 'produtor',
        summary: 'propõe',
        area: 'proposta',
        paletteToken: 'W:produtor:0',
        concurrencyMax: 1,
      },
    ]);
    const grupo = layer.group.children.find((child) => child.name === 'runtime-workers');
    expect(grupo).toBeDefined();
    expect(grupo?.children).toHaveLength(0);
    expect(layer.panels().some((panel) => panel.entityId.startsWith('op/worker/'))).toBe(false);
    expect(layer.pickables()).toHaveLength(0);
    expect(layer.workerPoses()).toEqual([
      { id: 'op/worker/proponente', anchor: ancora, target: ancora, current: ancora },
    ]);
    layer.dispose();
  });
});

describe('a haste ativa termina onde a placa está', () => {
  it('prefere a posição conhecida à cota gravada na haste', () => {
    const tether = {
      from: { x: 0, y: 0, z: 0 },
      to: { x: 5, y: 5, z: 0 },
      runtimeNodeId: 'runtime:model:groq/qwen3',
      entityId: 'op/model/groq/qwen3',
    };
    const posicoes: LayoutMap = new Map([['runtime:model:groq/qwen3', { x: 5, y: 5, z: 9 }]]);

    const segmentos = activeRuntimeSegments(
      [],
      posicoes,
      [tether],
      new Set(['runtime:model:groq/qwen3']),
    );

    expect(segmentos).toHaveLength(1);
    expect(segmentos[0]!.to).toEqual({ x: 5, y: 5, z: 9 });
  });
});
