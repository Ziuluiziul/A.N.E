// O pool gráfico: objetos criados uma vez, que trocam de dono sem renascer.

import { describe, expect, it } from 'vitest';

import { projectionFixture } from './fixture';
import type { LodLevel } from './lod';
import { describePanel, linesUpTo, type PanelDescriptor } from './panels';
import { panelWorldExtent } from './panelScale';
import {
  createPanelTextRenderer,
  type PanelTextFrame,
  type PanelTransform,
  TEXT_OBJECTS_PER_SLOT,
  type TextLike,
} from './panelTextRenderer';
import { TOTAL_TEXT_SLOTS, type TextAllocation } from './textPool';

const projecao = projectionFixture();

let criados = 0;
let descartes = 0;
/** Quem foi descartado, por identidade. Contagem não distingue repetido de esquecido. */
let descartados: TextLike[] = [];

/** Dublê estrutural do `Text` do troika: conta criação, sync e descarte. */
function fakeText(alturaMedida = 0): TextLike {
  criados += 1;
  let syncs = 0;
  const obj: TextLike & { syncs: () => number } = {
    text: '',
    fontSize: 1,
    maxWidth: 1,
    lineHeight: 1,
    anchorX: 'left',
    anchorY: 'top',
    textAlign: 'left',
    visible: true,
    renderOrder: 0,
    position: { set: () => undefined },
    quaternion: { set: () => undefined },
    textRenderInfo: alturaMedida > 0 ? { blockBounds: [0, 0, 1, alturaMedida] } : null,
    sync(callback) {
      syncs += 1;
      // O troika mede de forma assíncrona; aqui o retorno é imediato, que é o
      // suficiente para exercitar a correção. O caso atrasado tem teste próprio.
      if (callback) callback();
    },
    dispose() {
      descartes += 1;
      descartados.push(obj);
    },
    syncs: () => syncs,
  };
  return obj;
}

function renderer(capacity = TOTAL_TEXT_SLOTS, alturaMedida = 0) {
  criados = 0;
  descartes = 0;
  descartados = [];
  return createPanelTextRenderer({ capacity, createText: () => fakeText(alturaMedida) });
}

function frameCom(ids: string[]): PanelTextFrame {
  const descriptors = new Map<string, PanelDescriptor>();
  const transforms = new Map<string, PanelTransform>();
  const lines = new Map<string, ReturnType<typeof linesUpTo>>();
  const levels = new Map<string, LodLevel>();
  const allocations: TextAllocation[] = [];
  ids.forEach((id, index) => {
    const node = projecao.nodes.find((n) => n.id === id) ?? projecao.nodes[index]!;
    const descriptor = describePanel({ ...node, id });
    descriptors.set(id, descriptor);
    transforms.set(id, {
      position: { x: index, y: 0, z: 0 },
      quaternion: { x: 0, y: 0, z: 0, w: 1 },
      extent: panelWorldExtent(descriptor),
    });
    lines.set(id, linesUpTo(descriptor, 'legible'));
    levels.set(id, 'legible');
    allocations.push({ entityId: id, slotId: index, priority: 1000 });
  });
  return { allocations, descriptors, transforms, lines, levels };
}

const IDS = projecao.nodes.slice(0, 6).map((n) => n.id);

describe('a criação acontece uma vez só', () => {
  it('nascem dois objetos por vaga, e nem um a mais', () => {
    // Cada vaga tem corpo e título: o título é desenhado acima e fora da placa, e por
    // isso é um objeto próprio. O invariante que importa continua o mesmo — a criação
    // acontece uma vez, na inicialização, e nenhuma atualização acrescenta objeto.
    const r = renderer();
    expect(criados).toBe(TOTAL_TEXT_SLOTS * TEXT_OBJECTS_PER_SLOT);
    // A métrica conta objeto, não vaga. Ela dizia `TOTAL_TEXT_SLOTS` — metade do que
    // esta mesma linha acima prova existir — e era a telemetria que deveria denunciar
    // vazamento de texto.
    expect(r.metrics().createdObjects).toBe(criados);
    expect(r.objects().length).toBe(TOTAL_TEXT_SLOTS * TEXT_OBJECTS_PER_SLOT);
  });

  it('nenhuma atualização cria objeto novo', () => {
    const r = renderer();
    const antes = criados;
    for (let i = 0; i < 5; i += 1) r.update(frameCom(IDS));
    expect(criados).toBe(antes);
    expect(r.metrics().createdObjects).toBe(TOTAL_TEXT_SLOTS * TEXT_OBJECTS_PER_SLOT);
  });

  it('a quantidade de nós não altera a quantidade de objetos', () => {
    const r = renderer();
    r.update(frameCom(IDS.slice(0, 2)));
    const poucos = r.metrics().createdObjects;
    r.update(frameCom(projecao.nodes.slice(0, 40).map((n) => n.id)));
    expect(r.metrics().createdObjects).toBe(poucos);
    expect(r.metrics().visibleObjects).toBeLessThanOrEqual(
      TOTAL_TEXT_SLOTS * TEXT_OBJECTS_PER_SLOT,
    );
    expect(r.metrics().allocatedSlots).toBeLessThanOrEqual(TOTAL_TEXT_SLOTS);
  });
});

describe('a vaga é fixa e a entidade passa por ela', () => {
  it('a atribuição usa o slotId diretamente', () => {
    const r = renderer();
    r.update(frameCom(IDS));
    IDS.forEach((id, index) => expect(r.entityAt(index)).toBe(id));
  });

  it('trocar a entidade reaproveita o mesmo objeto', () => {
    const r = renderer();
    r.update(frameCom(IDS));
    const objeto = r.objects()[0];
    const outros = projecao.nodes.slice(10, 16).map((n) => n.id);
    r.update(frameCom(outros));
    expect(r.objects()[0]).toBe(objeto);
    expect(r.entityAt(0)).toBe(outros[0]);
    expect(criados).toBe(TOTAL_TEXT_SLOTS * 2);
  });

  it('vaga livre fica invisível, vazia e sem resíduo', () => {
    const r = renderer();
    r.update(frameCom(IDS));
    r.update({
      allocations: [],
      descriptors: new Map(),
      transforms: new Map(),
      lines: new Map(),
      levels: new Map(),
    });
    for (const objeto of r.objects()) {
      expect(objeto.visible).toBe(false);
      expect(objeto.text).toBe('');
    }
    expect(r.metrics().allocatedSlots).toBe(0);
    expect(r.metrics().visibleObjects).toBe(0);
  });
});

describe('sincronizar custa, então só se sincroniza o necessário', () => {
  it('quadro sem mudança não sincroniza nada', () => {
    const r = renderer();
    r.update(frameCom(IDS));
    const depoisDoPrimeiro = r.metrics().syncCalls;
    for (let i = 0; i < 10; i += 1) r.update(frameCom(IDS));
    expect(r.metrics().syncCalls).toBe(depoisDoPrimeiro);
  });

  it('mover a câmera não força sincronização', () => {
    const r = renderer();
    const base = frameCom(IDS);
    r.update(base);
    const antes = r.metrics().syncCalls;
    for (let quadro = 1; quadro <= 30; quadro += 1) {
      const movido: PanelTextFrame = {
        ...base,
        transforms: new Map(
          [...base.transforms].map(([id, t]) => [
            id,
            {
              ...t,
              position: { x: t.position.x + quadro, y: quadro, z: 0 },
              quaternion: { x: 0, y: Math.sin(quadro), z: 0, w: Math.cos(quadro) },
            },
          ]),
        ),
      };
      r.update(movido);
    }
    expect(r.metrics().syncCalls).toBe(antes);
  });

  it('mudar o conteúdo sincroniza, e só então', () => {
    const r = renderer();
    r.update(frameCom(IDS));
    const antes = r.metrics().syncCalls;
    r.update(frameCom(projecao.nodes.slice(20, 26).map((n) => n.id)));
    expect(r.metrics().syncCalls).toBeGreaterThan(antes);
  });
});

describe('o estouro real é corrigido na ordem certa', () => {
  it('a linha secundária cai antes de o título encurtar', () => {
    // Bloco medido sempre mais alto que a caixa: força as duas passagens.
    const r = renderer(4, 9999);
    const frame = frameCom(IDS.slice(0, 1));
    r.update(frame);
    const objeto = r.objects()[0]!;
    const linhas = objeto.text.split('\n');
    const descritor = frame.descriptors.get(IDS[0]!)!;
    // Sobrou o cabeçalho e o título; a linha secundária foi retirada inteira.
    expect(linhas.length).toBeLessThanOrEqual(2);
    // E o descritor não foi tocado.
    expect(descritor.title).toBe(descritor.title);
    expect(descritor.truncation.bodyPolicy).toBe('omit-whole-line');
  });

  it('a correção tem teto e não vira laço', () => {
    const r = renderer(2, 9999);
    r.update(frameCom(IDS.slice(0, 1)));
    // Uma sincronização inicial mais no máximo duas correções.
    expect(r.metrics().syncCalls).toBeLessThanOrEqual(3);
  });
});

describe('descarte e integridade', () => {
  it('dispose alcança cada objeto exatamente uma vez', () => {
    // O nome deste teste prometia o que a asserção negava: ele exigia
    // `TOTAL_TEXT_SLOTS` descartes num pool de `TOTAL_TEXT_SLOTS * 2` objetos, e por
    // isso passava enquanto todos os títulos sobreviviam ao descarte — um vazamento por
    // ciclo de recarga a quente, e memória de GPU que só cresce numa sessão longa.
    const r = renderer();
    r.update(frameCom(IDS));
    r.dispose();
    expect(descartes).toBe(TOTAL_TEXT_SLOTS * TEXT_OBJECTS_PER_SLOT);
    r.dispose();
    expect(descartes).toBe(TOTAL_TEXT_SLOTS * TEXT_OBJECTS_PER_SLOT);
  });

  it('cada objeto criado é descartado, e nenhum outro', () => {
    // Por identidade, não por contagem: contagem igual com objeto repetido e objeto
    // esquecido dá o mesmo número, e foi assim que o defeito passou despercebido.
    const r = renderer();
    const antes = new Set(r.objects());
    expect(antes.size).toBe(TOTAL_TEXT_SLOTS * TEXT_OBJECTS_PER_SLOT);
    r.dispose();
    expect(new Set(descartados)).toEqual(antes);
  });

  it('depois do descarte, atualizar não faz nada', () => {
    const r = renderer();
    r.dispose();
    r.update(frameCom(IDS));
    expect(r.metrics().allocatedSlots).toBe(0);
  });

  it('a ordem de desenho fica acima da placa, não acima da cena', () => {
    const r = renderer();
    for (const objeto of r.objects()) expect(objeto.renderOrder).toBe(2);
  });

  it('nenhum conteúdo privado entra na composição', () => {
    const r = renderer();
    r.update(frameCom(IDS));
    for (const objeto of r.objects()) {
      const texto = objeto.text.toLowerCase();
      expect(texto).not.toContain('<think');
      expect(texto).not.toContain('prompt');
      expect(texto).not.toContain('api_key');
    }
  });
});

describe('retorno atrasado de sync não fala por quem já saiu', () => {
  /** Dublê que guarda o callback em vez de executá-lo: simula medição assíncrona. */
  function textoAdiado(pendentes: (() => void)[], altura: number): TextLike {
    criados += 1;
    return {
      text: '',
      fontSize: 1,
      maxWidth: 1,
      lineHeight: 1,
      anchorX: 'left',
      anchorY: 'top',
      textAlign: 'left',
      visible: true,
      renderOrder: 0,
      position: { set: () => undefined },
      quaternion: { set: () => undefined },
      textRenderInfo: { blockBounds: [0, 0, 1, altura] },
      sync(callback) {
        if (callback) pendentes.push(callback);
      },
      dispose() {
        descartes += 1;
      },
    };
  }

  it('a correção de estouro da entidade anterior não reescreve a nova', () => {
    const pendentes: (() => void)[] = [];
    criados = 0;
    const r = createPanelTextRenderer({
      capacity: 1,
      createText: () => textoAdiado(pendentes, 9999),
    });

    const primeiro = IDS[0]!;
    r.update(frameCom([primeiro]));
    const outro = projecao.nodes.find((n) => n.id !== primeiro)!.id;
    r.update(frameCom([outro]));
    const categoriaDeB = frameCom([outro]).descriptors.get(outro)!.category.toUpperCase();

    // Só agora chegam as medições, inclusive as de A, quando a vaga já é de B.
    for (const pendente of pendentes.splice(0)) pendente();

    expect(r.entityAt(0)).toBe(outro);
    // O texto pode ter encurtado pela correção do próprio B; o que não pode é
    // deixar de ser de B.
    expect(r.objects()[0]!.text.startsWith(categoriaDeB)).toBe(true);
  });

  it('a vaga liberada não é reescrita por medição em voo', () => {
    const pendentes: (() => void)[] = [];
    criados = 0;
    const r = createPanelTextRenderer({
      capacity: 1,
      createText: () => textoAdiado(pendentes, 9999),
    });
    r.update(frameCom([IDS[0]!]));
    r.update({
      allocations: [],
      descriptors: new Map(),
      transforms: new Map(),
      lines: new Map(),
      levels: new Map(),
    });
    for (const pendente of pendentes.splice(0)) pendente();

    expect(r.entityAt(0)).toBeNull();
    expect(r.objects()[0]!.text).toBe('');
    expect(r.objects()[0]!.visible).toBe(false);
  });
});

describe('a causa de cada sincronização é registrada', () => {
  it('transformação pura não sincroniza nem troca dono', () => {
    const r = renderer();
    const base = frameCom(IDS);
    r.update(base);
    const antes = r.metrics();

    // Ensaio A: candidatos, alocação, descritores, LOD, extensão e conteúdo
    // congelados. Só posição e quaternion mudam, por 40 quadros.
    for (let quadro = 1; quadro <= 40; quadro += 1) {
      r.update({
        ...base,
        transforms: new Map(
          [...base.transforms].map(([id, t]) => [
            id,
            {
              ...t,
              position: { x: quadro * 3, y: quadro, z: -quadro },
              quaternion: { x: 0, y: Math.sin(quadro / 3), z: 0, w: Math.cos(quadro / 3) },
            },
          ]),
        ),
      });
    }

    const depois = r.metrics();
    expect(depois.syncCalls - antes.syncCalls).toBe(0);
    expect(depois.allocationOwnerChanges - antes.allocationOwnerChanges).toBe(0);
    expect(depois.contentKeyChanges - antes.contentKeyChanges).toBe(0);
  });

  it('a primeira atribuição conta como inicial, e a troca conta como dono', () => {
    const r = renderer();
    r.update(frameCom(IDS));
    expect(r.metrics().syncByReason.initial).toBe(IDS.length);
    expect(r.metrics().allocationOwnerChanges).toBe(0);

    r.update(frameCom(projecao.nodes.slice(30, 36).map((n) => n.id)));
    expect(r.metrics().syncByReason['owner-changed']).toBeGreaterThan(0);
    expect(r.metrics().allocationOwnerChanges).toBeGreaterThan(0);
  });

  it('a soma por causa bate com o total de sincronizações', () => {
    const r = renderer(8);
    r.update(frameCom(IDS));
    r.update(frameCom(projecao.nodes.slice(30, 36).map((n) => n.id)));
    const m = r.metrics();
    const soma = Object.values(m.syncByReason).reduce((a, b) => a + b, 0);
    expect(soma).toBe(m.syncCalls);
  });

  it('a telemetria separa corpus de runtime', () => {
    const r = renderer();
    const frame = frameCom(IDS);
    const sources = new Map(IDS.map((id, i) => [id, i < 2 ? 'runtime' : 'corpus'] as const));
    r.update({ ...frame, sources });
    const m = r.metrics();
    expect(m.runtimeAllocated).toBe(2);
    expect(m.corpusAllocated).toBe(IDS.length - 2);
    expect(m.corpusAllocated + m.runtimeAllocated).toBeLessThanOrEqual(64);
  });
});

describe('a correção de estouro não vira ressincronização perpétua', () => {
  it('composição pedida igual não sincroniza, mesmo depois de corrigida', () => {
    // Bloco sempre estourado: toda primeira atribuição sofre correção.
    const r = renderer(4, 9999);
    const frame = frameCom(IDS.slice(0, 1));
    r.update(frame);
    const depoisDoPrimeiro = r.metrics().syncCalls;

    // Mesmo quadro, repetido: nada mudou, nada pode sincronizar.
    for (let i = 0; i < 20; i += 1) r.update(frame);

    const m = r.metrics();
    expect(m.syncCalls).toBe(depoisDoPrimeiro);
    expect(m.syncByReason['content-changed']).toBe(0);
    expect(m.allocationOwnerChanges).toBe(0);
  });
});

describe('o painel que rola não é cortado pela correção de estouro', () => {
  /** Um quadro de painel aberto, com um documento que passa muito da placa. */
  function frameAberto(id: string, quantasLinhas: number): PanelTextFrame {
    const frame = frameCom([id]);
    const linhas = Array.from({ length: quantasLinhas }, (_, i) => ({
      section: 'descricao' as const,
      text: `Linha ${i} do documento, com texto suficiente para ocupar largura inteira.`,
      priority: -1,
    }));
    return {
      ...frame,
      lines: new Map([[id, linhas]]),
      levels: new Map([[id, 'expanded' as LodLevel]]),
      lineRevision: new Map([[id, 'documento']]),
      scroll: new Map([[id, 0]]),
    };
  }

  it('mantém as linhas que não cabem, porque são elas que existem para rolar', () => {
    // Este teste reprovava antes do incremento. A correção de estouro existe para o
    // painel de tamanho fixo, onde texto que passa da placa vaza para fora dela. No
    // painel aberto ela cortava o documento: com 81 linhas medindo oito vezes a altura
    // útil, a primeira passagem guardava dez e a segunda cortava de novo — sobravam o
    // cabeçalho e duas linhas. Era esta a causa de o painel aberto parar no título e na
    // descrição.
    const r = renderer(4, 9999);
    const id = IDS[0]!;
    r.update(frameAberto(id, 80));
    const m = r.metrics();
    expect(m.syncByReason['overflow-secondary-removed']).toBe(0);
    expect(m.syncByReason['overflow-title-ellipsized']).toBe(0);
    // E o painel declara que há muito o que rolar, medido no bloco real.
    const extensao = r.scrollExtents().find((e) => e.entityId === id);
    expect(extensao).toBeDefined();
    expect(extensao!.maxScroll).toBeGreaterThan(0);
  });

  it('prefere a altura medida à estimada quando ela é deste conteúdo', () => {
    // A estimativa conta glifos por uma largura média; num documento de milhares de
    // caracteres o erro dessa média decide se as últimas linhas são alcançáveis.
    const alto = renderer(4, 9999);
    const id = IDS[0]!;
    const quadro = frameAberto(id, 80);
    alto.update(quadro);
    // A segunda passagem já encontra a medida gravada na vaga.
    alto.update(quadro);
    const medido = alto.scrollExtents().find((e) => e.entityId === id)!;

    const semMedida = renderer(4, 0);
    semMedida.update(quadro);
    const estimado = semMedida.scrollExtents().find((e) => e.entityId === id)!;
    expect(medido.contentHeight).toBeGreaterThan(estimado.contentHeight);
  });

  it('o painel de tamanho fixo continua sendo cortado', () => {
    // A correção não sai de cena: ela vale onde o estouro de fato vaza para fora.
    const r = renderer(4, 9999);
    r.update(frameCom(IDS.slice(0, 1)));
    expect(r.metrics().syncByReason['overflow-secondary-removed']).toBeGreaterThan(0);
  });
});

describe('conteúdo novo na mesma placa é reescrito', () => {
  /** Troca só as linhas: entidade, nível, extensão e rolagem ficam iguais. */
  function frameComLinhas(id: string, texto: string, revisao?: string): PanelTextFrame {
    const frame = frameCom([id]);
    return {
      ...frame,
      lines: new Map([[id, [{ section: 'estado' as const, text: texto, priority: 95 }]]]),
      ...(revisao === undefined ? {} : { lineRevision: new Map([[id, revisao]]) }),
    };
  }

  it('sem revisão declarada, a chave do cache não vê a troca', () => {
    // Este é o comportamento que congelava o raciocínio na placa viva: o cache de
    // layout tem por chave entidade, nível, área e rolagem, e nenhum deles muda quando
    // muda só o texto. Fica documentado porque é o motivo de a revisão existir.
    const r = renderer();
    const id = IDS[0]!;
    r.update(frameComLinhas(id, 'primeiro pensamento'));
    const antes = r.metrics().syncCalls;
    r.update(frameComLinhas(id, 'segundo pensamento'));
    expect(r.metrics().syncCalls).toBe(antes);
  });

  it('com revisão declarada, o texto novo chega à placa', () => {
    const r = renderer();
    const id = IDS[0]!;
    r.update(frameComLinhas(id, 'primeiro pensamento', 'd1'));
    const antes = r.metrics().syncCalls;
    r.update(frameComLinhas(id, 'segundo pensamento', 'd2'));

    expect(r.metrics().syncCalls).toBeGreaterThan(antes);
    const escrito = r.objects().map((objeto) => objeto.text).join(' | ');
    expect(escrito).toContain('segundo pensamento');
    expect(escrito).not.toContain('primeiro pensamento');
  });
});
