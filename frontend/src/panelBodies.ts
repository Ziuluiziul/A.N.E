// O corpo do nó: uma placa instanciada, e nenhuma primitiva.
//
// Segundo incremento da ADR-002. A entidade deixa de ser esfera, cilindro ou toro e
// passa a ser a própria placa, dimensionada por `panelExtent()` a partir do descritor
// puro de `panels.ts`. Não há corpo atrás da placa e não há haste.
//
// **Agrupamento por material, nunca por nó.** Um `InstancedMesh` por combinação de
// estado canônico e camada — no máximo dez, na prática duas ou três — sobre uma única
// geometria de quad. É o que mantém a promessa de poucas chamadas de desenho e, ao
// mesmo tempo, preserva o invariante de que proposta não ganha falsa solidez: a
// transparência continua morando no material, que continua sendo por estado.
//
// **`instanceId` é efêmero.** Ele vale para o buffer da GPU e para mais nada. A
// autoridade é `entityId`: reconstruir os buffers, reordenar a projeção ou trocar o
// agrupamento não pode mover a seleção de uma entidade para outra.
//
// **Expandir é a mesma placa maior.** O estado expandido não abre modal nem popover:
// ele multiplica a extensão do painel que já existe. Um só desenho por entidade, a
// qualquer instante — o critério central da direção de 3.4.
//
// O nó expandido troca de **caminho de desenho**, não de identidade: ele passa da
// malha instanciada para uma placa dedicada, com `renderOrder` próprio e sem teste de
// profundidade, e a instância correspondente é ocultada no mesmo movimento. É a única
// forma de conceder direito de passagem a um nó dentro de uma malha instanciada, que
// só sabe ordenar por malha inteira. Enquanto isso vale, o nó continua único: a placa
// da frente desenha um, e apenas um, e é a mesma entidade que a instância deixou de
// desenhar.

import * as THREE from 'three';

import type { ProjectionNode } from './contract';
import { bodyMaterial } from './geometry';
import type { LayoutMap } from './layout';
import { NEUTRALS, oklchToHex, tokenColor } from './palette';
import { describePanel, type PanelDescriptor } from './panels';
import { panelShapeGeometry, shapeOf, type PanelShape } from './panelShapes';
import { panelPickExtent, panelWorldExtent } from './panelScale';

/** Quad unitário compartilhado por todas as placas. A escala vem da matriz. */

/** Elevação de seleção: destaca sem mudar tamanho nem cor. */
const ELEVACAO = 1.4;

/**
 * Quanto a placa cresce ao expandir.
 *
 * Área, não lado: 2,2 de fator linear é quase cinco vezes a superfície, que é o que o
 * conteúdo estruturado completo pede sem que o painel deixe de caber no afastamento
 * que o layout reserva entre vizinhos (`panelSweepRadius`).
 */
const EXPANSAO = 2.2;

/** Fora de vista sem sair do buffer: a instância continua existindo e no lugar. */
const OCULTA = 0.0001;

/**
 * Ordem de desenho da placa: acima do ambiente, abaixo do texto.
 *
 * Vai na malha, não no grupo. `renderOrder` de um `Group` não desce para os filhos —
 * o three.js ordena cada objeto pelo valor dele próprio —, então ajustá-lo no grupo
 * era não ajustar nada.
 */
const ORDEM_DA_PLACA = 1;

/**
 * A placa da frente: uma malha só, emprestada ao nó expandido enquanto ele durar.
 *
 * `InstancedMesh` não concede `renderOrder` a uma instância, e sem isso o painel
 * expandido continuava sendo cortado por qualquer vizinho que estivesse alguns metros
 * mais perto da câmera — lia-se meia frase e o resto sumia atrás de uma placa vazia.
 *
 * Enquanto esta malha desenha um nó, **a instância dele fica oculta**. Em nenhum
 * instante existem dois desenhos da mesma entidade: o que existe é a mesma placa,
 * desenhada por outro caminho, com direito de passar por cima.
 */
const ORDEM_DA_PLACA_EXPANDIDA = 3;
/**
 * Preenchimento do painel selecionado.
 *
 * Era 0,88 — quase sólido, calibrado quando a placa era pequena e o texto disputava o
 * espaço com o que passasse atrás. Com a placa em 5,0 a superfície de leitura é grande o
 * bastante para ceder um pouco: em 0,74 o painel escolhido continua sendo fundo para o
 * texto e volta a pertencer à cena, em vez de tapá-la.
 *
 * Há um piso, e ele não é de gosto: abaixo de ~0,6 o que passa atrás começa a competir
 * com o glifo, e a placa da frente deixa de fazer a única coisa que ela existe para
 * fazer — ser superfície de leitura.
 */
const OPACIDADE_EXPANDIDA = 0.74;

/**
 * Ênfase perceptiva. **Não** é canal de informação: nada além de foco depende dela.
 *
 * `dimmed` mistura a cor da instância com o fundo. Isso derruba contraste sem mexer
 * em matiz, então o domínio continua sendo dito pela mesma cor de sempre — só mais
 * perto do fundo. `highlighted` sobe luminância pelo caminho inverso.
 */
export type PanelEmphasis = 'normal' | 'highlighted' | 'dimmed';

/** Fração da cor que vai para o fundo quando o nó não pertence à vizinhança ativa. */
const MISTURA_APAGADO = 0.74;
/** Fração de branco somada no realce. Discreta de propósito: é prévia, não seleção. */
const MISTURA_REALCE = 0.22;
/**
 * Fração de branco no auge do pulso de atividade.
 *
 * Maior que o realce porque diz outra coisa: realce é "isto é vizinho do que você
 * olha", atividade é "isto está acontecendo agora". Continua abaixo de meio para a cor
 * do domínio sobreviver ao pulso — o painel acende, não troca de identidade.
 */
const MISTURA_ATIVIDADE = 0.42;

const BRANCO = new THREE.Color(0xffffff);

interface Slot {
  descriptor: PanelDescriptor;
  materialKey: string;
  /** A silhueta desta entidade, para a placa da frente assumi-la ao expandir. */
  shape: PanelShape;
  index: number;
  position: THREE.Vector3;
  /** Extensão compacta, vinda do descritor. A expansão multiplica; não substitui. */
  width: number;
  height: number;
  visible: boolean;
  elevated: boolean;
  expanded: boolean;
  emphasis: PanelEmphasis;
  /** Intensidade do pulso de atividade, de 0 a 1. Zero em tudo que não está vivo. */
  activity: number;
  baseColor: THREE.Color;
}

export interface PanelBodies {
  group: THREE.Group;
  /** As malhas do corpo. Uma por material, nunca uma por entidade. */
  meshes: THREE.InstancedMesh[];
  /** Tudo que o raio de seleção deve considerar, incluindo a placa da frente. */
  pickTargets(): THREE.Object3D[];
  /**
   * Só a placa do nó expandido, para quem precisa perguntar "o ponteiro está **nela**?".
   *
   * A pergunta não se responde com o primeiro acerto do raio: a placa expandida ignora
   * profundidade e desenha por cima de tudo, mas o raio continua ordenando por distância,
   * e um vizinho mais próximo é atingido antes dela. Quem apontasse para o meio do painel
   * aberto receberia o nome do painel que ele está cobrindo.
   */
  expandedTarget(): THREE.Object3D | null;
  /** `instanceId` → `entityId`. A tradução só existe nesta direção por acaso do buffer. */
  entityFor(mesh: THREE.Object3D, instanceId: number | undefined): string | null;
  /** A extensão **efetiva**: já com a expansão aplicada, se houver. */
  extentFor(entityId: string): { width: number; height: number } | null;
  /** A área de clique: a placa mais margem uniforme, nunca proporcional. */
  pickExtentFor(entityId: string): { width: number; height: number } | null;
  /** A posição assentada pelo layout, sem elevação de seleção. */
  positionFor(entityId: string): THREE.Vector3 | null;
  /**
   * Move a placa para uma posição já decidida pelo layout sem reconstruir a malha.
   *
   * Esta porta não decide movimento: ela só escreve o quadro atual do assentamento
   * autônomo. Âncora, alvo e causalidade continuam pertencendo ao layout.
   */
  moveTo(entityId: string, position: THREE.Vector3Like): void;
  /**
   * A posição em que a placa é **desenhada**, elevação de seleção incluída.
   *
   * Texto e halo precisam desta, e não da anterior. Enquanto o texto usava a posição
   * do layout, o painel selecionado subia 1,4 e o texto ficava para trás: a própria
   * placa, opaca e escrevendo profundidade, passava a esconder o que ela existe para
   * mostrar. O painel expandido aparecia vazio — e só na cena, nunca no teste.
   */
  renderPositionFor(entityId: string): THREE.Vector3 | null;
  descriptorFor(entityId: string): PanelDescriptor | null;
  /** As entidades que este corpo desenha, em ordem estável. */
  entityIds(): string[];
  setVisible(entityId: string, visible: boolean): void;
  setElevated(entityId: string, elevated: boolean): void;
  /** Expande ou recolhe a própria placa. Não cria objeto nem troca de material. */
  setExpanded(entityId: string, expanded: boolean): void;
  isExpanded(entityId: string): boolean;
  setEmphasis(entityId: string, emphasis: PanelEmphasis): void;
  /**
   * Acende um painel porque **está acontecendo agora**.
   *
   * A intensidade é contínua para o pulso poder ser suave: alternar entre aceso e
   * apagado piscaria, e piscar lê como defeito de renderização, não como sinal de vida.
   */
  setActivity(entityId: string, intensity: number): void;
  /** Orienta todas as placas para a leitura, sem rotação individual arbitrária. */
  orient(quaternion: THREE.Quaternion): void;
  /** Reconstrói os buffers preservando a identidade de cada entidade. */
  rebuild(nodes: ProjectionNode[], positions: LayoutMap): void;
  dispose(): void;
}

/**
 * A chave da malha instanciada.
 *
 * A forma entra na chave junto com o material: instâncias de uma `InstancedMesh`
 * compartilham a geometria, então painéis de silhuetas diferentes precisam de malhas
 * diferentes. São cinco formas e poucos materiais, e o produto continua sendo um punhado
 * de malhas — não uma por painel.
 */
function materialKeyOf(node: ProjectionNode): string {
  return `${node.canonicalState}:${node.layer}:${shapeOf(node.kind)}`;
}

export function createPanelBodies(
  nodes: ProjectionNode[],
  positions: LayoutMap,
): PanelBodies {
  const group = new THREE.Group();
  group.name = 'panel-bodies';

  let slots = new Map<string, Slot>();
  let meshes: THREE.InstancedMesh[] = [];
  let porChave = new Map<string, THREE.InstancedMesh>();
  const dummy = new THREE.Object3D();
  const cor = new THREE.Color();
  const fundo = new THREE.Color(oklchToHex(NEUTRALS.backgroundDeep));
  let orientacao = new THREE.Quaternion();

  // `depthTest: false` é o que dá o direito de passagem. Ele vale para uma placa só,
  // a do nó que o usuário escolheu ler; qualquer outra continua sujeita à
  // profundidade, como deve ser.
  const materialDaFrente = new THREE.MeshBasicMaterial({
    transparent: true,
    opacity: OPACIDADE_EXPANDIDA,
    depthTest: false,
    depthWrite: false,
    side: THREE.DoubleSide,
  });
  // A placa da frente assume a silhueta do painel que ela representa: com uma forma
  // fixa, expandir um voto triangular o transformaria num retângulo, e a silhueta
  // deixaria de identificar justamente quando se está olhando para ela.
  const frente = new THREE.Mesh(panelShapeGeometry('retangulo'), materialDaFrente);
  frente.name = 'panels:front';
  frente.renderOrder = ORDEM_DA_PLACA_EXPANDIDA;
  frente.frustumCulled = false;
  frente.visible = false;
  group.add(frente);
  let expandidoId: string | null = null;

  function limpar(): void {
    for (const mesh of meshes) {
      group.remove(mesh);
      const material = mesh.material;
      if (Array.isArray(material)) for (const m of material) m.dispose();
      else material.dispose();
      mesh.dispose();
    }
    meshes = [];
    porChave = new Map();
  }

  function extensaoEfetiva(slot: Slot): { width: number; height: number } {
    const fator = slot.expanded ? EXPANSAO : 1;
    return { width: slot.width * fator, height: slot.height * fator };
  }

  function escrever(slot: Slot): void {
    const mesh = porChave.get(slot.materialKey);
    if (!mesh) return;
    dummy.position.copy(slot.position);
    if (slot.elevated) dummy.position.z += ELEVACAO;
    dummy.quaternion.copy(orientacao);
    const medida = extensaoEfetiva(slot);
    // Expandido, quem desenha é a placa da frente. Manter a instância acesa faria
    // dois desenhos da mesma entidade — a coisa que esta arquitetura existe para
    // não ter.
    const fator = slot.visible && !slot.expanded ? 1 : OCULTA;
    dummy.scale.set(medida.width * fator, medida.height * fator, 1);
    dummy.updateMatrix();
    mesh.setMatrixAt(slot.index, dummy.matrix);
    mesh.instanceMatrix.needsUpdate = true;
    // `InstancedMesh.raycast` guarda a esfera depois do primeiro hit-test. A matriz
    // muda durante o assentamento, portanto o cache antigo pode nem alcançar a posição
    // nova e tornar uma placa visível impossível de clicar.
    mesh.boundingSphere = null;
    mesh.boundingBox = null;
  }

  /** A placa da frente segue o slot expandido: mesma posição, extensão e cor. */
  function escreverFrente(): void {
    const slot = expandidoId === null ? undefined : slots.get(expandidoId);
    if (!slot || !slot.visible) {
      frente.visible = false;
      return;
    }
    const forma = panelShapeGeometry(slot.shape);
    if (frente.geometry !== forma) frente.geometry = forma;
    const medida = extensaoEfetiva(slot);
    frente.position.copy(slot.position);
    if (slot.elevated) frente.position.z += ELEVACAO;
    frente.quaternion.copy(orientacao);
    frente.scale.set(medida.width, medida.height, 1);
    // Cor de domínio, com a mesma ênfase que a instância teria. A placa muda de
    // caminho de desenho; ela não muda de identidade.
    materialDaFrente.color.copy(slot.baseColor);
    if (slot.emphasis === 'highlighted') materialDaFrente.color.lerp(BRANCO, MISTURA_REALCE);
    frente.visible = true;
  }

  /**
   * Escreve a cor da instância a partir da cor de domínio e da ênfase.
   *
   * `baseColor` nunca é sobrescrita: ela é a autoridade do token, e a ênfase é sempre
   * recalculada a partir dela. Sem isso, alternar seleção acumularia misturas e a cor
   * do domínio derivaria a cada clique.
   */
  function colorir(slot: Slot): void {
    const mesh = porChave.get(slot.materialKey);
    if (!mesh) return;
    cor.copy(slot.baseColor);
    if (slot.emphasis === 'dimmed') cor.lerp(fundo, MISTURA_APAGADO);
    else if (slot.emphasis === 'highlighted') cor.lerp(BRANCO, MISTURA_REALCE);
    // Atividade entra **depois** da ênfase e por cima dela: uma execução acontecendo
    // agora precisa ser vista mesmo quando está fora da vizinhança do que se olha.
    if (slot.activity > 0) cor.lerp(BRANCO, MISTURA_ATIVIDADE * slot.activity);
    mesh.setColorAt(slot.index, cor);
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  }

  function construir(entrada: ProjectionNode[], layout: LayoutMap): void {
    limpar();
    const anteriores = slots;
    slots = new Map();

    const porMaterial = new Map<string, ProjectionNode[]>();
    for (const node of entrada) {
      const chave = materialKeyOf(node);
      porMaterial.set(chave, [...(porMaterial.get(chave) ?? []), node]);
    }

    for (const [chave, doGrupo] of porMaterial) {
      if (doGrupo.length === 0) continue;
      const [estado, camada, forma] = chave.split(':') as [
        string,
        'epistemic' | 'operational',
        PanelShape,
      ];
      const mesh = new THREE.InstancedMesh(
        panelShapeGeometry(forma),
        bodyMaterial(estado, camada),
        doGrupo.length,
      );
      mesh.name = `panels:${chave}`;
      mesh.renderOrder = ORDEM_DA_PLACA;
      // A esfera envolvente de uma malha instanciada é calculada uma vez e não
      // acompanha matriz reescrita. Com placas que mudam de escala e de orientação a
      // cada quadro, deixá-la governar o recorte fazia a cena inteira desaparecer.
      mesh.frustumCulled = false;
      mesh.instanceColor = new THREE.InstancedBufferAttribute(
        new Float32Array(doGrupo.length * 3),
        3,
      );
      porChave.set(chave, mesh);
      meshes.push(mesh);
      group.add(mesh);

      doGrupo.forEach((node, index) => {
        const descriptor = describePanel(node);
        // Autoridade única de escala: corpo, clique, foco e texto saem daqui.
        const { width, height } = panelWorldExtent(descriptor);
        const p = layout.get(node.id) ?? { x: 0, y: 0, z: 0 };
        const anterior = anteriores.get(node.id);
        const slot: Slot = {
          descriptor,
          materialKey: chave,
          shape: shapeOf(node.kind),
          index,
          position: new THREE.Vector3(p.x, p.y, p.z),
          width,
          height,
          // Estado interativo sobrevive à reconstrução: ele pertence à entidade.
          visible: anterior?.visible ?? true,
          elevated: anterior?.elevated ?? false,
          expanded: anterior?.expanded ?? false,
          emphasis: anterior?.emphasis ?? 'normal',
          activity: anterior?.activity ?? 0,
          // Cor vem do token de domínio e de mais nada — nem do tipo de painel, nem
          // da proporção, nem do estado.
          baseColor: new THREE.Color(oklchToHex(tokenColor(descriptor.paletteToken))),
        };
        slots.set(node.id, slot);
        colorir(slot);
        escrever(slot);
      });
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    }
  }

  construir(nodes, positions);

  return {
    group,
    get meshes() {
      return meshes;
    },
    pickTargets() {
      return frente.visible ? [...meshes, frente] : [...meshes];
    },
    expandedTarget() {
      return frente.visible ? frente : null;
    },
    entityFor(mesh, instanceId) {
      // A placa da frente não tem instância: ela desenha um nó por vez, e é o
      // `expandidoId` que diz qual.
      if (mesh === frente) return expandidoId;
      if (instanceId === undefined || !Number.isInteger(instanceId) || instanceId < 0) {
        return null;
      }
      const chave = mesh.name.replace('panels:', '');
      // A malha tem de ser **desta** instância, e não apenas ter o mesmo nome.
      //
      // Corpus e camada viva usam a mesma fábrica de placas, então as duas produzem
      // uma malha chamada `panels:temporary:operational`. Comparar só pelo nome fazia
      // o corpus reconhecer a malha da camada viva e devolver o nó de quórum que por
      // acaso tinha o mesmo índice de instância: clicar num evento ao vivo selecionava
      // um painel de quórum. A identidade do objeto é o que desfaz a coincidência.
      if (porChave.get(chave) !== mesh) return null;
      for (const [entityId, slot] of slots) {
        if (slot.materialKey === chave && slot.index === instanceId) return entityId;
      }
      return null;
    },
    extentFor(entityId) {
      const slot = slots.get(entityId);
      return slot ? extensaoEfetiva(slot) : null;
    },
    pickExtentFor(entityId) {
      const slot = slots.get(entityId);
      if (!slot) return null;
      const margem = panelPickExtent(slot.descriptor);
      const medida = extensaoEfetiva(slot);
      // A margem de captura é a mesma sempre; o que cresce ao expandir é a placa.
      return {
        width: medida.width + (margem.width - slot.width),
        height: medida.height + (margem.height - slot.height),
      };
    },
    positionFor(entityId) {
      return slots.get(entityId)?.position.clone() ?? null;
    },
    moveTo(entityId, position) {
      const slot = slots.get(entityId);
      if (!slot || slot.position.equals(position)) return;
      slot.position.set(position.x, position.y, position.z);
      escrever(slot);
      if (expandidoId === entityId) escreverFrente();
    },
    renderPositionFor(entityId) {
      const slot = slots.get(entityId);
      if (!slot) return null;
      const posicao = slot.position.clone();
      if (slot.elevated) posicao.z += ELEVACAO;
      return posicao;
    },
    descriptorFor(entityId) {
      return slots.get(entityId)?.descriptor ?? null;
    },
    entityIds() {
      return [...slots.keys()];
    },
    setVisible(entityId, visible) {
      const slot = slots.get(entityId);
      if (!slot || slot.visible === visible) return;
      slot.visible = visible;
      escrever(slot);
      if (expandidoId === entityId) escreverFrente();
    },
    setElevated(entityId, elevated) {
      const slot = slots.get(entityId);
      if (!slot || slot.elevated === elevated) return;
      slot.elevated = elevated;
      escrever(slot);
      if (expandidoId === entityId) escreverFrente();
    },
    setExpanded(entityId, expanded) {
      const slot = slots.get(entityId);
      if (!slot || slot.expanded === expanded) return;
      slot.expanded = expanded;
      if (expanded) expandidoId = entityId;
      else if (expandidoId === entityId) expandidoId = null;
      escrever(slot);
      escreverFrente();
    },
    isExpanded(entityId) {
      return slots.get(entityId)?.expanded ?? false;
    },
    setEmphasis(entityId, emphasis) {
      const slot = slots.get(entityId);
      if (!slot || slot.emphasis === emphasis) return;
      slot.emphasis = emphasis;
      colorir(slot);
      if (expandidoId === entityId) escreverFrente();
    },
    setActivity(entityId, intensity) {
      const slot = slots.get(entityId);
      if (!slot) return;
      const valor = Math.min(Math.max(intensity, 0), 1);
      // Sem o corte, um pulso contínuo reescreveria a cor de instância a cada quadro
      // para cada painel vivo, e o buffer inteiro subiria para a GPU sem necessidade.
      if (Math.abs(slot.activity - valor) < 0.01) return;
      slot.activity = valor;
      colorir(slot);
      if (expandidoId === entityId) escreverFrente();
    },
    orient(quaternion) {
      // Uma orientação para todas: a placa acompanha a câmera sem girar por conta
      // própria, então nenhuma aparece de perfil e nada treme entre quadros.
      if (orientacao.equals(quaternion)) return;
      orientacao = quaternion.clone();
      for (const slot of slots.values()) escrever(slot);
      escreverFrente();
    },
    rebuild(entrada, layout) {
      construir(entrada, layout);
      // `construir` limpa o grupo das malhas; a placa da frente é dona de si mesma.
      if (!group.children.includes(frente)) group.add(frente);
      escreverFrente();
    },
    dispose() {
      limpar();
      group.remove(frente);
      materialDaFrente.dispose();
      expandidoId = null;
      slots = new Map();
    },
  };
}
