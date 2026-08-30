// O corpo do nó virou placa: este arquivo prende o que não pode regredir.
//
// Roda sem GPU. `InstancedMesh` e `PlaneGeometry` existem em memória sem contexto
// WebGL, então dá para conferir contagem de malhas, matrizes e a tradução de
// identidade sem abrir janela.

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import * as THREE from 'three';
import { describe, expect, it } from 'vitest';

import type { ProjectionNode } from './contract';
import { node, projectionFixture } from './fixture';
import { layoutAtlas } from './layout';
import { createPanelBodies } from './panelBodies';
import { describePanel } from './panels';
import { panelWorldExtent } from './panelScale';

const projecao = projectionFixture();
const posicoes = layoutAtlas(projecao);

function corpos() {
  return createPanelBodies(projecao.nodes, posicoes);
}

function escalaDe(mesh: THREE.InstancedMesh, index: number): THREE.Vector3 {
  const matriz = new THREE.Matrix4();
  mesh.getMatrixAt(index, matriz);
  const escala = new THREE.Vector3();
  matriz.decompose(new THREE.Vector3(), new THREE.Quaternion(), escala);
  return escala;
}

function posicaoDe(corpo: ReturnType<typeof corpos>, id: string): THREE.Vector3 {
  const matriz = new THREE.Matrix4();
  for (const mesh of corpo.meshes) {
    for (let index = 0; index < mesh.count; index += 1) {
      if (corpo.entityFor(mesh, index) !== id) continue;
      mesh.getMatrixAt(index, matriz);
      const position = new THREE.Vector3();
      matriz.decompose(position, new THREE.Quaternion(), new THREE.Vector3());
      return position;
    }
  }
  throw new Error(`entidade sem instância: ${id}`);
}

describe('todo nó vira instância de painel', () => {
  it('a soma das instâncias cobre a projeção inteira', () => {
    const corpo = corpos();
    const total = corpo.meshes.reduce((soma, mesh) => soma + mesh.count, 0);
    expect(total).toBe(projecao.nodes.length);
    for (const node of projecao.nodes) {
      expect(corpo.extentFor(node.id)).not.toBeNull();
    }
  });

  it('move a instância e a placa expandida sem reconstruir a identidade', () => {
    const corpo = corpos();
    const id = projecao.nodes[0]!.id;
    const mesh = corpo.meshes.find((candidate) =>
      Array.from({ length: candidate.count }, (_, index) => corpo.entityFor(candidate, index))
        .includes(id),
    )!;
    mesh.computeBoundingSphere();
    expect(mesh.boundingSphere).not.toBeNull();
    const destino = new THREE.Vector3(91, -42, 17);
    corpo.moveTo(id, destino);
    expect(mesh.boundingSphere).toBeNull();
    expect(corpo.positionFor(id)?.toArray()).toEqual(destino.toArray());
    expect(posicaoDe(corpo, id).toArray()).toEqual(destino.toArray());

    corpo.setExpanded(id, true);
    const frente = corpo.expandedTarget()!;
    corpo.moveTo(id, { x: 12, y: 23, z: 34 });
    expect(frente.position.toArray()).toEqual([12, 23, 34]);
    expect(corpo.entityFor(frente, undefined)).toBe(id);
  });
});

describe('nenhuma primitiva sobrou como corpo', () => {
  it('toda malha é placa plana, e nenhuma é esfera, cilindro ou toro', () => {
    // O invariante da ADR-002 é que o painel **é** o nó: nenhum corpo volumétrico ao
    // lado da placa. A silhueta por tipo, que entrou depois, continua sendo placa —
    // muda o contorno, não a dimensionalidade. Daí aceitar `ShapeGeometry` e continuar
    // recusando primitiva de volume.
    for (const mesh of corpos().meshes) {
      expect(['PlaneGeometry', 'ShapeGeometry']).toContain(mesh.geometry.type);
      expect(mesh.geometry.type).not.toMatch(/Sphere|Cylinder|Torus|Capsule|Octahedron|Box/);
      const posicao = mesh.geometry.getAttribute('position');
      for (let i = 0; i < posicao.count; i += 1) expect(posicao.getZ(i)).toBe(0);
    }
  });

  it('não existe mesh individual por entidade', () => {
    const corpo = corpos();
    expect(corpo.meshes.length).toBeLessThan(projecao.nodes.length);
    for (const mesh of corpo.meshes) {
      expect(mesh).toBeInstanceOf(THREE.InstancedMesh);
    }
  });

  it('o número de chamadas de desenho não cresce com o número de nós', () => {
    const pequeno = createPanelBodies(projecao.nodes.slice(0, 3), posicoes);
    const inteiro = corpos();
    // Malhas são agrupadas por material; dobrar os nós não dobra as malhas.
    expect(inteiro.meshes.length).toBeLessThanOrEqual(pequeno.meshes.length + 2);
    expect(inteiro.meshes.length).toBeLessThanOrEqual(10);
  });
});

describe('a matriz carrega a extensão do descritor', () => {
  it('escala de cada instância bate com panelExtent', () => {
    const corpo = corpos();
    for (const node of projecao.nodes) {
      const esperado = panelWorldExtent(describePanel(node));
      const medida = corpo.extentFor(node.id)!;
      expect(medida.width).toBeCloseTo(esperado.width, 10);
      expect(medida.height).toBeCloseTo(esperado.height, 10);
    }
  });

  it('a escala escrita no buffer é a mesma que o descritor pediu', () => {
    const corpo = corpos();
    const mesh = corpo.meshes[0]!;
    const escala = escalaDe(mesh, 0);
    expect(escala.x).toBeGreaterThan(0);
    expect(escala.y).toBeGreaterThan(0);
    expect(escala.z).toBeCloseTo(1, 6);
  });
});

describe('proporção diferente, mesma área', () => {
  function comKind(node: ProjectionNode, patch: Partial<ProjectionNode>): ProjectionNode {
    return { ...node, ...patch };
  }
  const base = projecao.nodes.find((n) => n.kind === 'moc')!;
  const nota = projecao.nodes.find((n) => n.kind === 'note')!;

  it('MOC e ponte do mesmo degrau ocupam a mesma área', () => {
    const ponte = comKind(base, {
      id: 'Pontes/Ponte — Teste',
      domainId: 'pontes',
      domainLabel: 'pontes',
    });
    const corpo = createPanelBodies([base, ponte], posicoes);
    const a = corpo.extentFor(base.id)!;
    const b = corpo.extentFor(ponte.id)!;
    expect(a.width * a.height).toBeCloseTo(b.width * b.height, 10);
    expect(b.width).toBeGreaterThan(a.width);
  });

  it('mesmo degrau, mesma área — a proporção muda a forma, não o espaço', () => {
    // O par nota/quórum deixou de servir aqui: em 3.5-E o quórum subiu de degrau,
    // porque desde que a deliberação chega à cena ele carrega tarefa, proposta,
    // avaliação e apuração, e não cabia no tamanho de uma nota. O invariante é o
    // mesmo e continua sendo o que importa: quem compartilha degrau compartilha área.
    const moc = comKind(nota, { id: 'MOC — Teste', kind: 'moc' });
    const quorum = comKind(nota, {
      id: 'runtime/quorum-1',
      kind: 'quorum-decision',
      layer: 'operational',
    });
    const corpo = createPanelBodies([moc, quorum], posicoes);
    const a = corpo.extentFor(moc.id)!;
    const b = corpo.extentFor(quorum.id)!;
    expect(a.width * a.height).toBeCloseTo(b.width * b.height, 10);
    // E a proporção continua distinguindo uma silhueta da outra. O quórum era retrato,
    // e deitou em 3.5-F porque o corpo é dimensionado pela largura: retrato dava fonte
    // 0,41 contra 0,68 do MOC, e a nuvem operacional lia como sussurro. O que o teste
    // prende é a área compartilhada e a distinção — não qual dos dois é mais alto.
    expect(a.width / a.height).not.toBeCloseTo(b.width / b.height, 3);
    expect(a.width).toBeGreaterThan(a.height);
  });

  it('degrau maior ocupa mais área que degrau menor', () => {
    const quorum = comKind(nota, {
      id: 'runtime/quorum-2',
      kind: 'quorum-decision',
      layer: 'operational',
    });
    const corpo = createPanelBodies([nota, quorum], posicoes);
    const daNota = corpo.extentFor(nota.id)!;
    const doQuorum = corpo.extentFor(quorum.id)!;
    expect(doQuorum.width * doQuorum.height).toBeGreaterThan(daNota.width * daNota.height);
  });

  it('a raiz não recebe escala nem tratamento especial', () => {
    const corpo = corpos();
    const mocs = projecao.nodes.filter((n) => n.kind === 'moc');
    const raiz = mocs.find((m) => m.domainId === 'raiz') ?? mocs[0]!;
    const daRaiz = corpo.extentFor(raiz.id)!;
    for (const moc of mocs) {
      const medida = corpo.extentFor(moc.id)!;
      expect(medida.width).toBeCloseTo(daRaiz.width, 10);
      expect(medida.height).toBeCloseTo(daRaiz.height, 10);
    }
  });
});

describe('cor continua vindo do domínio', () => {
  it('cada instância recebe cor, e o buffer tem uma por nó', () => {
    for (const mesh of corpos().meshes) {
      expect(mesh.instanceColor).not.toBeNull();
      expect(mesh.instanceColor!.count).toBe(mesh.count);
    }
  });

  it('dois nós do mesmo domínio recebem a mesma cor, tipos diferentes ou não', () => {
    const doDominio = projecao.nodes.filter(
      (n) => n.visual.paletteToken === projecao.nodes[0]!.visual.paletteToken,
    );
    const corpo = createPanelBodies(doDominio, posicoes);
    const cores = new Set<string>();
    for (const mesh of corpo.meshes) {
      for (let i = 0; i < mesh.count; i += 1) {
        const cor = new THREE.Color();
        mesh.getColorAt(i, cor);
        cores.add(cor.getHexString());
      }
    }
    expect(cores.size).toBe(1);
  });
});

describe('a identidade é o entityId, nunca o instanceId', () => {
  it('instanceId resolve para o entityId correto', () => {
    const corpo = corpos();
    for (const mesh of corpo.meshes) {
      for (let i = 0; i < mesh.count; i += 1) {
        const id = corpo.entityFor(mesh, i);
        expect(id).not.toBeNull();
        expect(corpo.extentFor(id!)).not.toBeNull();
      }
    }
  });

  it('índice inválido não resolve para entidade alguma', () => {
    const corpo = corpos();
    const mesh = corpo.meshes[0]!;
    for (const invalido of [-1, 1.5, mesh.count + 10, Number.NaN]) {
      expect(corpo.entityFor(mesh, invalido)).toBeNull();
    }
    expect(corpo.entityFor(mesh, undefined)).toBeNull();
    expect(corpo.entityFor(new THREE.Object3D(), 0)).toBeNull();
  });

  it('reconstruir com a projeção reordenada preserva a seleção por entityId', () => {
    const corpo = corpos();
    const alvo = projecao.nodes[2]!;
    corpo.setElevated(alvo.id, true);
    const antes = corpo.entityFor(corpo.meshes[0]!, 0);

    const invertida = [...projecao.nodes].reverse();
    corpo.rebuild(invertida, posicoes);

    // O buffer mudou de ordem; a entidade elevada continua sendo a mesma.
    const depois = corpo.entityFor(corpo.meshes[0]!, 0);
    expect(depois).not.toBe(antes);
    expect(corpo.extentFor(alvo.id)).not.toBeNull();
    expect(corpo.descriptorFor(alvo.id)!.entityId).toBe(alvo.id);
  });
});

describe('seleção e visibilidade seguem funcionando', () => {
  it('elevar muda a matriz e não muda a escala', () => {
    const corpo = corpos();
    const alvo = projecao.nodes[0]!;
    const mesh = corpo.meshes.find((m) => corpo.entityFor(m, 0) !== null)!;
    const antes = escalaDe(mesh, 0);
    corpo.setElevated(corpo.entityFor(mesh, 0)!, true);
    const depois = escalaDe(mesh, 0);
    expect(depois.x).toBeCloseTo(antes.x, 10);
    expect(depois.y).toBeCloseTo(antes.y, 10);
    expect(corpo.extentFor(alvo.id)).not.toBeNull();
  });

  it('ocultar encolhe sem tirar a instância do buffer', () => {
    const corpo = corpos();
    const total = corpo.meshes.reduce((soma, m) => soma + m.count, 0);
    const alvo = corpo.entityFor(corpo.meshes[0]!, 0)!;
    corpo.setVisible(alvo, false);
    expect(corpo.meshes.reduce((soma, m) => soma + m.count, 0)).toBe(total);
    expect(escalaDe(corpo.meshes[0]!, 0).x).toBeLessThan(0.01);
  });

  it('orientar aplica a mesma rotação a todas as placas', () => {
    const corpo = corpos();
    const q = new THREE.Quaternion().setFromEuler(new THREE.Euler(0.3, 0.5, 0));
    corpo.orient(q);
    const mesh = corpo.meshes[0]!;
    const matriz = new THREE.Matrix4();
    const rotacao = new THREE.Quaternion();
    mesh.getMatrixAt(0, matriz);
    matriz.decompose(new THREE.Vector3(), rotacao, new THREE.Vector3());
    // 1e-4 rad é 0,006°: abaixo de qualquer diferença perceptível, e acima do
    // ruído de decompor matriz com escala mundial.
    expect(rotacao.angleTo(q)).toBeLessThan(1e-4);
  });
});

describe('expandir é a mesma placa maior, nunca um segundo objeto', () => {
  it('não nasce malha nem instância ao expandir', () => {
    const corpo = corpos();
    const alvo = projecao.nodes[0]!.id;
    const malhas = corpo.meshes.length;
    const instancias = corpo.meshes.reduce((soma, m) => soma + m.count, 0);
    corpo.setExpanded(alvo, true);
    expect(corpo.meshes.length).toBe(malhas);
    expect(corpo.meshes.reduce((soma, m) => soma + m.count, 0)).toBe(instancias);
    expect(corpo.isExpanded(alvo)).toBe(true);
  });

  it('a extensão efetiva cresce e a matriz acompanha', () => {
    const corpo = corpos();
    const alvo = projecao.nodes[0]!.id;
    const compacto = corpo.extentFor(alvo)!;
    corpo.setExpanded(alvo, true);
    const expandido = corpo.extentFor(alvo)!;
    expect(expandido.width).toBeGreaterThan(compacto.width);
    // A proporção comunica função e não pode mudar ao expandir.
    expect(expandido.width / expandido.height).toBeCloseTo(compacto.width / compacto.height, 10);

    // Quem desenha o expandido é a placa da frente; a instância apaga no mesmo
    // movimento, para que nunca existam dois desenhos da mesma entidade.
    const frente = corpo
      .pickTargets()
      .find((alvoDeClique) => alvoDeClique.name === 'panels:front');
    expect(frente).toBeDefined();
    expect(frente!.visible).toBe(true);
    expect(frente!.scale.x).toBeCloseTo(expandido.width, 6);
    expect(frente!.scale.y).toBeCloseTo(expandido.height, 6);

    const mesh = corpo.meshes.find((m) => corpo.entityFor(m, 0) === alvo);
    if (mesh) expect(escalaDe(mesh, 0).x).toBeLessThan(0.01);
  });

  it('a placa da frente é o mesmo nó, e resolve para o mesmo entityId', () => {
    const corpo = corpos();
    const alvo = projecao.nodes[0]!.id;
    expect(corpo.pickTargets().some((item) => item.name === 'panels:front')).toBe(false);
    corpo.setExpanded(alvo, true);
    const frente = corpo.pickTargets().find((item) => item.name === 'panels:front')!;
    expect(corpo.entityFor(frente, undefined)).toBe(alvo);
    // Recolher devolve o desenho à instância e tira a placa da frente do caminho.
    corpo.setExpanded(alvo, false);
    expect(corpo.pickTargets().some((item) => item.name === 'panels:front')).toBe(false);
  });

  it('nunca há dois desenhos da mesma entidade ao mesmo tempo', () => {
    const corpo = corpos();
    const alvo = projecao.nodes[0]!.id;
    const desenhos = (): number => {
      const naFrente = corpo
        .pickTargets()
        .filter((item) => item.name === 'panels:front' && item.visible).length;
      const mesh = corpo.meshes.find((m) => corpo.entityFor(m, 0) === alvo);
      const naInstancia = mesh && escalaDe(mesh, 0).x > 0.01 ? 1 : 0;
      return naFrente + naInstancia;
    };
    expect(desenhos()).toBe(1);
    corpo.setExpanded(alvo, true);
    expect(desenhos()).toBe(1);
    corpo.setExpanded(alvo, false);
    expect(desenhos()).toBe(1);
  });

  it('recolher devolve exatamente a extensão do descritor', () => {
    const corpo = corpos();
    const alvo = projecao.nodes[0]!.id;
    const esperado = panelWorldExtent(describePanel(projecao.nodes[0]!));
    corpo.setExpanded(alvo, true);
    corpo.setExpanded(alvo, false);
    const medida = corpo.extentFor(alvo)!;
    expect(medida.width).toBeCloseTo(esperado.width, 10);
    expect(medida.height).toBeCloseTo(esperado.height, 10);
  });

  it('a margem de clique não cresce junto com a placa', () => {
    const corpo = corpos();
    const alvo = projecao.nodes[0]!.id;
    const folga = (id: string): number =>
      corpo.pickExtentFor(id)!.width - corpo.extentFor(id)!.width;
    const antes = folga(alvo);
    corpo.setExpanded(alvo, true);
    expect(folga(alvo)).toBeCloseTo(antes, 10);
  });
});

describe('a ênfase derruba contraste sem inventar cor', () => {
  function corDe(corpo: ReturnType<typeof corpos>, id: string): THREE.Color {
    for (const mesh of corpo.meshes) {
      for (let i = 0; i < mesh.count; i += 1) {
        if (corpo.entityFor(mesh, i) !== id) continue;
        const cor = new THREE.Color();
        mesh.getColorAt(i, cor);
        return cor;
      }
    }
    throw new Error(`entidade sem instância: ${id}`);
  }

  it('apagar aproxima do fundo e realçar afasta dele', () => {
    const corpo = corpos();
    const alvo = projecao.nodes[0]!.id;
    const normal = corDe(corpo, alvo).getHexString();
    corpo.setEmphasis(alvo, 'dimmed');
    const apagado = corDe(corpo, alvo);
    corpo.setEmphasis(alvo, 'highlighted');
    const realcado = corDe(corpo, alvo);
    expect(apagado.getHexString()).not.toBe(normal);
    expect(realcado.getHexString()).not.toBe(normal);
    // Luminância, não matiz: o domínio continua sendo dito pela mesma cor.
    expect(apagado.r + apagado.g + apagado.b).toBeLessThan(realcado.r + realcado.g + realcado.b);
  });

  it('alternar ênfase não faz a cor de domínio derivar', () => {
    const corpo = corpos();
    const alvo = projecao.nodes[0]!.id;
    const original = corDe(corpo, alvo).getHexString();
    for (const enfase of ['dimmed', 'highlighted', 'normal', 'dimmed', 'normal'] as const) {
      corpo.setEmphasis(alvo, enfase);
    }
    expect(corDe(corpo, alvo).getHexString()).toBe(original);
  });
});

describe('nada privado atravessa para o corpo', () => {
  it('o descritor exposto pelo corpo é o mesmo do módulo puro', () => {
    const corpo = corpos();
    for (const node of projecao.nodes.slice(0, 5)) {
      const serializado = JSON.stringify(corpo.descriptorFor(node.id));
      expect(serializado).toBe(JSON.stringify(describePanel(node)));
      expect(serializado.toLowerCase()).not.toContain('<think');
      expect(serializado.toLowerCase()).not.toContain('prompt');
    }
  });
});

describe('a camada de runtime obedece à mesma gramática', () => {
  it('runtimeLayer não importa mais a fábrica de primitivas', () => {
    const fonte = readFileSync(join(__dirname, 'runtimeLayer.ts'), 'utf-8');
    expect(fonte).not.toContain('buildKindGeometries');
    expect(fonte).toContain('createPanelBodies');
  });

  it('nenhum módulo de cena cria primitiva como corpo de entidade', () => {
    for (const arquivo of ['atlas.ts', 'runtimeLayer.ts', 'panelBodies.ts']) {
      const fonte = readFileSync(join(__dirname, arquivo), 'utf-8');
      expect(fonte).not.toMatch(/new THREE\.(Sphere|Cylinder|Torus|Capsule|Octahedron)Geometry/);
    }
  });

  it('a malha global fica fora do recorte por frustum', () => {
    for (const mesh of corpos().meshes) {
      expect(mesh.frustumCulled).toBe(false);
    }
  });
});

describe('a identidade da malha decide a quem o clique pertence', () => {
  it('uma malha de outra instância não é reconhecida, mesmo com o nome igual', () => {
    // Corpus e camada viva usam a mesma fábrica, e por isso as duas produzem uma malha
    // chamada `panels:temporary:operational`. Enquanto a busca comparava só o nome, o
    // corpus devolvia o nó que tivesse o mesmo índice de instância — clicar num evento
    // ao vivo selecionava um painel de quórum.
    const operacional = (id: string): ProjectionNode =>
      node(id, {
        kind: 'quorum-vote',
        layer: 'operational',
        path: null,
        canonicalState: 'temporary',
        domainId: 'operacional/quorum',
        domainLabel: 'quórum',
        operational: { panelId: 'p1' },
      });

    const doCorpus = [operacional('corpus/a'), operacional('corpus/b')];
    const daCamadaViva = [operacional('vivo/a'), operacional('vivo/b')];
    const posicoes = (ns: ProjectionNode[]) =>
      new Map(ns.map((n, i) => [n.id, { x: i * 10, y: 0, z: 0 }]));

    const corpus = createPanelBodies(doCorpus, posicoes(doCorpus));
    const vivo = createPanelBodies(daCamadaViva, posicoes(daCamadaViva));

    const malhaDoVivo = vivo.pickTargets()[0]!;
    const malhaDoCorpus = corpus.pickTargets()[0]!;
    expect(malhaDoVivo.name).toBe(malhaDoCorpus.name);

    // Cada um só reconhece a própria malha.
    expect(corpus.entityFor(malhaDoVivo, 0)).toBeNull();
    expect(vivo.entityFor(malhaDoCorpus, 0)).toBeNull();
    expect(corpus.entityFor(malhaDoCorpus, 0)).toBe('corpus/a');
    expect(vivo.entityFor(malhaDoVivo, 0)).toBe('vivo/a');

    corpus.dispose();
    vivo.dispose();
  });
});
