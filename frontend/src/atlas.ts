// O Atlas Neural-Epistêmico: montagem da cena, navegação e seleção.
//
// Quatro decisões estruturais que o resto do arquivo obedece.
//
// **O painel é o nó, e é o único alvo de interação.** Não há corpo geométrico, não há
// placa auxiliar, não há página de leitura ao lado e não há modal: cada entidade é
// uma placa 2D instanciada, dimensionada pelo descritor puro de `panels.ts`, e o
// clique acontece sobre a superfície preenchida dela. Casca territorial, equador e
// plano de referência são ambiente e não respondem ao raio de seleção — quem responde
// é o conteúdo.
//
// **Expandir é a mesma placa maior.** Selecionar não abre uma segunda representação:
// multiplica a escala da instância que já existe e sobe o nível de LOD para
// `expanded`, de modo que o mesmo objeto passe a mostrar o conteúdo completo. Fechar
// devolve a placa ao tamanho compacto. Nunca existem dois desenhos do mesmo nó.
//
// **Progressão de exploração.** A visão global mostra as populações que compõem o
// Atlas; foco, distância e seleção decidem quanto de cada entidade e relação se lê.
// Nenhum filtro de camada fica escondido numa API sem controle correspondente.
//
// **Movimento só quando significa algo.** Não há respiração, órbita nem partícula.
// O que se move é consequência de uma ação: a câmera que o usuário arrasta e a
// expansão do nó que ele selecionou.

import * as THREE from 'three';
import { LineMaterial } from 'three/examples/jsm/lines/LineMaterial.js';
import { LineSegments2 } from 'three/examples/jsm/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/examples/jsm/lines/LineSegmentsGeometry.js';
import { Text } from 'troika-three-text';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

import {
  loadNoteDocument,
  type EntityKind,
  type Projection,
  type ProjectionNode,
  type RelationFamily,
} from './contract';
import { selectThoughts, type CognitionFrame } from './cognition';
import { withLiveThought } from './cognitiveState';
import { createCloudTitles, type CloudKey, type CloudTitle } from './cloudTitles';
import { escolherAlvoDoClique } from './pickTarget';
import { CONTROLS } from './controls3d';
import { panelShapeGeometry, textAreaOf, type PanelShape } from './panelShapes';
import { buildRelationRegistry } from './relationRegistry';
import type { RuntimeWorker } from './workerEntities';
import { cameraPoseForExtent, createDepthEnvironment } from './depth';
import {
  EDGE_STYLES,
  SPINE_OPACITY,
  buildRelationLines,
} from './edges';
import { dashPath, edgePath, type EdgeObstacle } from './edgePath';
import { panelSweepRadii } from './panelScale';
import { emphasisFor, type EmphasisState } from './emphasis';
import { HALO_OPACITY, panelHaloMaterial } from './geometry';
import { initialRuntimeFramingAction } from './initialFraming';
import { isEditableTarget, selectionKeyboardAction } from './keyboardTarget';
import { documentLines } from './noteDocument';
import { wheelOwner } from './wheelTarget';
import { extentOf, type LayoutMap, type Vec3 } from './layout';
import {
  LOD_THRESHOLDS,
  levelWithHysteresis,
  projectedPixels,
  showsBody,
  type LodLevel,
} from './lod';
import {
  NEUTRALS,
  inkOn,
  linkColorOf,
  mixOklch,
  oklchToHex,
  tokenColor,
  type Oklch,
} from './palette';
import type { RuntimeSnapshot } from './runtime';
import { createPanelBodies } from './panelBodies';
import {
  createPanelTextRenderer,
  type PanelTransform,
  type PanelTextMetrics,
  type TextLike,
} from './panelTextRenderer';
import {
  MODEL_DOMAIN,
  PROVIDER_DOMAIN,
  WORKER_DOMAIN,
  describePanel,
  linesUpTo,
  type PanelDescriptor,
  type PanelLine,
} from './panels';
import {
  MIN_CORPUS_SLOTS,
  MIN_RUNTIME_SLOTS,
  TOTAL_TEXT_SLOTS,
  createTextPool,
  type TextCandidate,
} from './textPool';
import { createRuntimeLayer } from './runtimeLayer';
import { BASE_RADIUS } from './sizing';
import {
  LIMITE_DE_APROXIMACAO_MINIMO,
  distanciaMinimaDaOrbita,
} from './cameraLimits';

/**
 * Ordem de desenho. Halo atrás, arestas do foco junto das placas, texto por cima.
 *
 * `InstancedMesh` não tem `renderOrder` por instância: ele é por malha, e a malha
 * agrupa dezenas de nós. O que destaca o nó expandido entre os seus pares é a
 * expansão e a elevação em `z` que a seleção já aplica — não um privilégio de
 * ordenação que a instanciação não permite conceder a um só.
 */
const ORDEM_HALO = 0;
const ORDEM_ARESTAS_FOCAIS = 1;

/**
 * A hierarquia de relações, em três regimes, com a calibração da direção de 3.4.
 *
 * O defeito que ela desfaz: todas as arestas tinham peso visual parecido, então a
 * cena respondia "há muitas relações" antes que alguém tivesse escolhido o que
 * investigar. Agora a distância e a seleção decidem o que merece linha.
 *
 * - **global** — só o filamento agregado entre MOCs. Nenhuma ponta, nenhum padrão:
 *   a essa distância eles não se distinguem e viram ruído.
 * - **intermediária** — a espinha estrutural do MOC, lisa e discreta.
 * - **foco** — primeiro grau com a assinatura da família; segundo grau quase
 *   invisível; todo o resto recolhido.
 */
const RELACOES_INATIVAS = 0.04;
/**
 * A fita do primeiro grau, mais discreta e mais fina.
 *
 * Ela era o objeto mais forte da cena depois do texto: opacidade 0,85 e 3,4 pixels de
 * largura sobre uma placa que agora ocupa 34% mais território. O realce continua sendo o
 * canal que responde ao clique — o que muda é o quanto ele precisa gritar para ser visto,
 * que é menos do que precisava quando a placa era pequena e a linha ia de centro a centro.
 */
const RELACOES_DIRETAS = 0.6;

/**
 * A espessura do link em foco, em pixels — e não em unidades de mundo.
 *
 * `linewidth` de `LineBasicMaterial` é ignorado por praticamente todo driver, então
 * "engrossar" ali não desenharia nada: é preciso uma fita, que é o que `LineSegments2`
 * constrói no vértice a partir da resolução da tela. Em pixels a ênfase é a mesma de
 * perto e de longe, que é o que se quer de um destaque — ele responde à seleção, não
 * à distância.
 */
const ESPESSURA_EM_REPOUSO = 1;
const ESPESSURA_EM_FOCO = 2.2;
/** Segundos até a ênfase chegar ao fim. Curto o bastante para parecer resposta. */
const TEMPO_DA_ENFASE = 0.22;
/** Luminosidade OKLCH somada no meio do degradê, onde a mistura naturalmente cede. */
const BRILHO_DO_MEIO = 0.07;
/** Fração do raio do layout abaixo da qual a câmera deixa de estar "na visão global". */
const BANDA_GLOBAL = 0.9;

/**
 * Quantos pares um território desenha ao ser aproximado.
 *
 * Orçamento por primitiva, não por aresta: o que custa leitura é a quantidade de linhas
 * na tela, e não quantas relações cada uma representa.
 */
const MAX_PRIMITIVAS_DE_DOMINIO = 48;

/** Fração da distância ao alvo percorrida por segundo com uma tecla de movimento. */
const VELOCIDADE_DE_VOO = 1.6;

/** Ciclos por segundo da respiração do halo. Lento o bastante para não chamar. */
const PULSO_DO_HALO = 1.5;
/** Quanto a opacidade do halo varia em torno do valor de repouso. */
const AMPLITUDE_DO_HALO = 0.08;


/** Unidades de mundo roladas por unidade de `deltaY` da roda. */
const PASSO_DE_ROLAGEM = 0.012;

/** Quanto o refino em espaço de tela pode afastar além do que a conta de mundo pediu. */
const TETO_DO_REFINO = 1.35;

type RegimeDeRelacoes = 'global' | 'intermediaria' | 'foco';

/**
 * Fração da altura da janela que o painel deve ocupar quando a câmera se aproxima.
 *
 * A aproximação não é um zoom fixo: ela resolve a distância a partir do tamanho
 * projetado desejado, que é a mesma grandeza em que o LOD é medido. Assim um painel
 * de ponte e um de tarefa terminam igualmente legíveis, apesar de extensões distintas.
 */
const ALVO_DE_LEITURA = 0.34;

/**
 * A mesma fração, para o painel em que se **digita**.
 *
 * Ler e preencher não pedem o mesmo tamanho. Em 0,34 a área de leitura de um painel de
 * provedor sai com 194 × 109 pixels numa janela de 720 — medido, não estimado —, e um
 * campo de credencial com três botões nesse espaço nasce ilegível.
 *
 * O valor sai da face mais alta, e não da mais curta: a do trabalhador mede 242 pixels
 * de conteúdo contra 200 de caixa em 0,62, e a diferença aparecia como barra de rolagem
 * dentro do hexágono. Calibrar pela face curta deixaria a outra rolando; calibrar pela
 * alta custa alguns pixels à curta e mais nada.
 *
 * Só vale para o painel que carrega uma face; nenhum outro nó muda de comportamento.
 */
const ALVO_DE_DIGITACAO = 0.72;

/** Um objeto desenhado, descrito por valor. Ver `AtlasHandle.inspect`. */
export interface SceneObjectInfo {
  name: string;
  type: string;
  /** Visível de verdade: a cadeia inteira até a raiz está visível. */
  visible: boolean;
  instances: number | null;
  /** Caixa em coordenadas de mundo, para saber sobre qual camada o objeto cai. */
  worldBox: { min: [number, number, number]; max: [number, number, number] } | null;
}

/** O que a cena informa quando a escolha muda. */
export interface AtlasSelection {
  /** O nó escolhido, ou `null` quando a escolha foi solta. */
  id: string | null;
  /** Veio da camada viva? Corpus e runtime têm identidade separada. */
  runtime: boolean;
  /** Onde o nó estava na tela, em pixels, no instante da escolha. */
  screen: { x: number; y: number } | null;
}

/**
 * A área de leitura de um painel, projetada em pixels de CSS.
 *
 * É a **mesma** caixa que o texto do painel ocuparia — `textAreaOf` sobre a extensão
 * efetiva —, e não a caixa da placa: quem desenha uma face fora da cena precisa cair
 * dentro da silhueta, não sobre os cantos que o hexágono não tem.
 */
export interface PanelFaceRect {
  left: number;
  top: number;
  width: number;
  height: number;
  /**
   * Que tinta se lê sobre esta placa.
   *
   * Vem da luminosidade do token de domínio, e não de uma escolha fixa: a mesma tinta
   * clara que se lê sobre o azul-ardósia do openrouter some sobre o verde-claro do
   * nvidia. Quem desenha a face precisa disto porque escreve **sobre** a placa.
   */
  ink: 'clara' | 'escura';
}

export interface AtlasHandle {
  /**
   * Inventário do que a cena está realmente desenhando, como dado.
   *
   * Existe porque a aba de auditoria não compõe quadros: sem isto, provar que uma
   * camada está isolada — e não apenas parecendo isolada numa captura — dependeria de
   * adivinhar qual objeto ainda desenha.
   *
   * Devolve uma **cópia**, e não a raiz da cena. Entregar o objeto Three permitiria
   * mutação acidental de fora e transformaria uma ferramenta de diagnóstico em
   * acoplamento: qualquer chamador poderia mexer na cena por um caminho que o resto do
   * módulo não conhece.
   */
  inspect: () => SceneObjectInfo[];
  /**
   * Pose da câmera, por valor.
   *
   * Existe pelo mesmo motivo de `inspect`: sem ela, provar que `WASD` moveu a câmera —
   * e que o limite de aproximação impede a penetração — dependeria de inferir a
   * posição pelo que apareceu na tela.
   */
  cameraPose: () => { position: [number, number, number]; target: [number, number, number]; distance: number; minDistance: number; fov: number };
  dispose: () => void;
  select: (id: string | null) => void;
  toggle: (controlId: string) => void;
  /** Recentra a câmera numa entidade, preservando a direção de visada. */
  focusOn: (id: string) => void;
  /** Abre e recentra um modelo/evento da camada viva pelo identificador já validado. */
  focusRuntime: (id: string) => void;
  /** Suprime ou libera pulsos/links conforme o canal prova frescor operacional. */
  setRuntimeActivityEnabled: (enabled: boolean) => void;
  /** Recalcula apenas a vigência temporal da camada, preservando cena e seleção. */
  refreshRuntimeActivity: (now?: number) => void;
  /**
   * Substitui somente a camada operacional viva.
   *
   * A primeira atualização com geometria completa o enquadramento de startup se a
   * câmera ainda estiver intacta. Toda atualização posterior preserva a pose.
   */
  updateRuntime: (snapshot: RuntimeSnapshot) => void;
  /**
   * Reescreve as posições da cena principal a partir de uma simulação viva.
   *
   * Move as placas **e** refaz as ligações no mesmo passo. Elas guardam vértice, não
   * referência: separar as duas coisas deixa o fio pendurado onde a placa estava.
   *
   * Sem clique e sem arrasto por desenho. A posição continua saindo da relação
   * declarada; arrastar afirmaria um lugar que nenhuma aresta sustenta.
   */
  setPositions: (positions: LayoutMap) => void;
  /**
   * O roster de trabalhadores, direto para quem os possui — ADR-005.
   *
   * Passa reto para a camada viva: o atlas não guarda cópia nem decide nada sobre eles.
   * `undefined` preserva; `[]` remove. Ver `RuntimeLayer.syncWorkers`.
   */
  syncWorkers: (workers?: readonly RuntimeWorker[]) => void;
  /** As três poses de cada trabalhador, para a paridade da migração ser medida. */
  workerPoses: () => { id: string; anchor: Vec3; target: Vec3; current: Vec3 }[];
  /**
   * Substitui o raciocínio ao vivo, sem tocar na trilha nem na geometria.
   *
   * A placa do modelo é reconstruída só quando a leitura muda de fato — a assinatura
   * cognitiva é quem decide —, e por isso um fluxo de pensamento não vira um fluxo de
   * reconstrução da nuvem.
   */
  updateCognition: (frames: readonly CognitionFrame[]) => void;
  /** Enquadra o que está de fato ocupado, com margem, na área visível da janela. */
  fitToGraph: () => void;
  /** A legenda da cena, em texto. Quem a exibe é o dock, não mais uma placa 3D. */
  legendText: () => string;
  /**
   * A escolha mudou: qual nó, de qual camada, e onde ele está na tela.
   *
   * O ponto é o do instante da escolha e não acompanha a câmera de propósito. Quem o
   * consome ancora um formulário, e formulário que foge do cursor enquanto se digita
   * é pior que formulário parado ao lado do nó que o abriu.
   */
  onSelectionChange: (listener: (selection: AtlasSelection) => void) => void;
  /**
   * Declara que a face de um painel é desenhada fora da cena, e por isso o texto
   * dele não deve ser alocado aqui.
   *
   * É a mesma troca de **caminho de desenho** que a placa da frente faz ao expandir:
   * a entidade continua única, e continua sendo desenhada uma vez só. O que muda é
   * quem desenha a superfície — o DOM, quando ela precisa de campo e botão, que a
   * cena não tem como oferecer com foco, máscara e leitor de tela.
   */
  setPanelFace: (entityId: string | null) => void;
  /**
   * O que um painel afirma, em frases, no nível de leitura aberto.
   *
   * Quem desenha a face precisa **dizer o mesmo** que a placa dizia: trocar a leitura
   * do painel por um formulário sem contexto tiraria da cena a informação que o nó
   * carrega — e ela não está em nenhum outro lugar da tela.
   */
  panelLines: (entityId: string) => string[];
  /**
   * Onde a face declarada cai na tela **agora**, ou `null` se ela não está visível.
   *
   * Diferente de `AtlasSelection.screen`, este ponto acompanha a câmera: ele não
   * ancora um formulário ao lado do nó, ele **é** a superfície do nó. Um painel que
   * saísse de baixo da própria face desmentiria a única coisa que ela afirma.
   */
  panelFaceRect: () => PanelFaceRect | null;
  /** Telemetria local do orçamento de texto. Não atravessa para a projeção. */
  textMetrics: () => PanelTextMetrics & { lodChanges: number };
  readonly state: {
    selected: string | null;
    hovered: string | null;
    reducedMotion: boolean;
    view: 'global' | 'focus';
  };
  /**
   * Desenha um quadro fora do laço e devolve o que a GPU fez.
   *
   * Existe para a verificação: uma aba sem composição não recebe
   * `requestAnimationFrame`, então sem isto não haveria como conferir chamadas de
   * desenho nem exercer o picking, que depende das matrizes atualizadas no render.
   */
  renderOnce: () => { drawCalls: number; triangles: number; objects: number };
  /**
   * Avança um quadro com um passo de tempo declarado, e desenha.
   *
   * O laço normal é `requestAnimationFrame`, que uma aba sem composição não chama — e
   * sem isto o deslocamento por `WASD` seria inverificável de fora justamente no
   * ambiente em que a verificação acontece. Não substitui o laço: ele continua rodando
   * quando a aba compõe.
   */
  advance: (deltaSeconds: number) => void;
  /**
   * Renderiza numa resolução dada e devolve o PNG.
   *
   * A leitura do buffer acontece no mesmo turno de JavaScript do render, porque sem
   * composição da aba o conteúdo não sobrevive ao quadro seguinte.
   */
  captureAt: (width: number, height: number) => string;
}

interface NodeSlot {
  node: ProjectionNode;
  kind: EntityKind;
  position: THREE.Vector3;
  /** Nível medido pela distância. A expansão o sobrepõe sem apagá-lo. */
  level: LodLevel | undefined;
}

export function createAtlas(
  container: HTMLElement,
  projection: Projection,
  positions: LayoutMap,
  announce: (message: string) => void,
  /** O miolo que a composição reserva à nuvem viva. Ver `ComposedLayout.core`. */
  miolo: { origin: Vec3; radius: number } = { origin: { x: 0, y: 0, z: 0 }, radius: 110 },
  /** Onde o corpus mora no mundo composto. Ver `ComposedLayout.origin.corpus`. */
  origemDoCorpus: Vec3 = { x: 0, y: 0, z: 0 },
  /**
   * A âncora dos trabalhadores, para a camada viva que os possui.
   *
   * Atravessa esta função sem ser consultada: o atlas não sabe onde um trabalhador se
   * assenta, e não deve saber. Ele só liga quem pergunta a quem responde.
   */
  workerAnchors: (ids: readonly string[]) => LayoutMap = () => new Map(),
): AtlasHandle {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(oklchToHex(NEUTRALS.backgroundDeep));

  // As duas camadas são frames independentes: cada uma se enquadra e se mede sozinha.
  // Enquanto a medida era da projeção inteira, o observatório operacional — a 200
  // unidades da origem — empurrava `extentOf` de 92 para 247 e afastava a câmera 2,7x,
  // encolhendo o corpus para caber um anexo que ninguém tinha pedido para ver.
  const idsPorCamada: Record<'corpus' | 'operacional', ReadonlySet<string>> = {
    corpus: new Set(
      projection.nodes.filter((node) => node.layer === 'epistemic').map((node) => node.id),
    ),
    operacional: new Set(
      projection.nodes
        .filter(
          (node) =>
            node.layer === 'operational' && node.domainId !== WORKER_DOMAIN,
        )
        .map((node) => node.id),
    ),
  };
  // A interface não oferece mais filtros de camada: corpus, observatório e fluxo vivo
  // compõem uma única cena. Manter a lista combinada explícita evita preservar ramos
  // mortos que sugeririam uma capacidade ainda selecionável.
  const idsDaProjecao = new Set([
    ...idsPorCamada.corpus,
    ...idsPorCamada.operacional,
  ]);

  /** O quadro atualmente desenhado, para não reescrever instância que não mudou. */
  const desenhadas: LayoutMap = new Map(positions);

  // A pose-base mede o corpus; o enquadramento final inclui a cena composta.
  // Medida **em torno da origem do corpus**, e não da origem do mundo. Desde que a
  // composição virou coluna, o corpus mora abaixo do miolo: medir do mundo somava a
  // altura da coluna ao raio dele, e a pose de abertura, o teto de afastamento e a
  // escala da névoa saíam todos de um número cujo nome dizia "raio do corpus" e cujo
  // valor era "altura da coluna" — 347 no lugar de 127.
  const noFrameDoCorpus: LayoutMap = new Map();
  for (const id of idsPorCamada.corpus) {
    const p = positions.get(id);
    if (p) {
      noFrameDoCorpus.set(id, {
        x: p.x - origemDoCorpus.x,
        y: p.y - origemDoCorpus.y,
        z: p.z - origemDoCorpus.z,
      });
    }
  }
  const { radius, depth } = extentOf(noFrameDoCorpus);
  const posicoesDaCena: LayoutMap = new Map(
    [...positions].filter(([id]) => idsPorCamada.corpus.has(id) || idsPorCamada.operacional.has(id)),
  );
  /** Alcance do mundo composto, para a névoa saber até onde precisa enxergar. */
  const alcanceDoMundo = Math.max(radius, extentOf(posicoesDaCena).radius, 1);
  const aspect = Math.max(container.clientWidth / Math.max(container.clientHeight, 1), 0.25);
  const pose = cameraPoseForExtent(radius, depth, aspect);
  // A densidade exponencial preserva contraste perto da câmera e dissolve o
  // horizonte gradualmente; a escala vem da extensão real do layout.
  scene.fog = new THREE.FogExp2(
    oklchToHex(NEUTRALS.backgroundDeep),
    1 / Math.max(alcanceDoMundo * 5.4, 240),
  );

  const camera = new THREE.PerspectiveCamera(
    pose.fov,
    aspect,
    pose.near,
    pose.far,
  );
  // `z` é a vertical do atlas: o plano do conhecimento é `x/y`.
  camera.up.set(0, 0, 1);
  camera.position.set(pose.position.x, pose.position.y, pose.position.z);
  camera.lookAt(pose.target.x, pose.target.y, pose.target.z);

  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.toneMappingExposure = 1.06;
  container.appendChild(renderer.domElement);

  const orbit = new OrbitControls(camera, renderer.domElement);
  orbit.enableDamping = true;
  orbit.dampingFactor = 0.09;
  orbit.minDistance = LIMITE_DE_APROXIMACAO_MINIMO;
  orbit.maxDistance = Math.max(radius * 5.4, pose.distance * 1.65);
  // **Rotação livre.** Os limites polares existiam para impedir que a câmera passasse
  // por cima do atlas e o visse de topo, onde um mapa em anel vira um disco ilegível.
  // O preço era não poder olhar de baixo nem contornar o mundo, e agora que há três
  // nuvens em posições distintas isso deixou de ser detalhe: metade das aproximações
  // possíveis estava barrada. A folga nos polos evita apenas a singularidade do
  // `up` vertical, onde a órbita daria um giro brusco sobre si mesma.
  orbit.minPolarAngle = 0.02;
  orbit.maxPolarAngle = Math.PI - 0.02;
  orbit.target.set(pose.target.x, pose.target.y, pose.target.z);

  // Hemisfério separa faces voltadas ao céu e ao chão. Duas luzes direcionais
  // assimétricas devolvem arestas e silhueta sem fazer matiz medir importância.
  scene.add(
    new THREE.HemisphereLight(
      0xc7d7ed,
      oklchToHex(NEUTRALS.backgroundSecondary),
      1.08,
    ),
  );
  const luzPrincipal = new THREE.DirectionalLight(0xf5f8ff, 1.12);
  luzPrincipal.position.set(radius * 0.72, -radius * 0.48, Math.max(radius, depth * 2));
  scene.add(luzPrincipal);
  const luzRecorte = new THREE.DirectionalLight(0x7898c4, 0.48);
  luzRecorte.position.set(-radius * 0.85, radius * 0.62, Math.max(depth, 12));
  scene.add(luzRecorte);

  // O campo envolve a cena inteira e corre ao longo da coluna epistêmica: a mesma
  // direção da tela em que o conhecimento desce e o quórum sobe.
  const ambiente = createDepthEnvironment();
  scene.add(ambiente.group);

  // --- placas instanciadas -------------------------------------------------

  /**
   * O que esta cena materializa — ADR-005, primeira transferência de propriedade.
   *
   * Os trabalhadores saem daqui: quem os possui é a `runtimeLayer`. O observatório
   * de quórum volta a entrar — o backend já corta o histórico no teto recente.
   */
  const nosDaCena = projection.nodes.filter((node) => node.domainId !== WORKER_DOMAIN);
  const corpos = createPanelBodies(nosDaCena, positions);
  scene.add(corpos.group);
  const slots = new Map<string, NodeSlot>();
  let pensamentosVivos = new Map<string, string>();
  for (const node of nosDaCena) {
    const p = positions.get(node.id) ?? { x: 0, y: 0, z: 0 };
    slots.set(node.id, {
      node,
      kind: node.kind,
      position: new THREE.Vector3(p.x, p.y, p.z),
      level: undefined,
    });
  }

  // Vizinhança de primeiro grau, calculada uma vez. Selecionar precisa responder
  // "quem se liga a isto" sem varrer 511 arestas a cada quadro.
  const vizinhos = new Map<string, Set<string>>();
  for (const edge of projection.edges) {
    if (edge.kind === 'aggregated') continue;
    for (const [de, para] of [
      [edge.source, edge.target],
      [edge.target, edge.source],
    ]) {
      const conjunto = vizinhos.get(de!) ?? new Set<string>();
      conjunto.add(para!);
      vizinhos.set(de!, conjunto);
    }
  }

  // --- texto: uma instância, 64 objetos, anexados uma vez -------------------

  const vagasDeTexto = createTextPool(TOTAL_TEXT_SLOTS, MIN_CORPUS_SLOTS, MIN_RUNTIME_SLOTS);
  const textoDosPaineis = createPanelTextRenderer({
    capacity: TOTAL_TEXT_SLOTS,
    createText: () => new Text() as unknown as TextLike,
  });
  const grupoDeTexto = new THREE.Group();
  grupoDeTexto.name = 'panel-text';
  for (const objeto of textoDosPaineis.objects()) {
    grupoDeTexto.add(objeto as unknown as THREE.Object3D);
  }
  scene.add(grupoDeTexto);

  // O raio varrido de cada placa, uma vez só: ele decide onde a linha começa, onde ela
  // termina e o que ela contorna. Sem isto a aresta ia de centro a centro e as duas
  // pontas ficavam enterradas dentro das placas que ela liga.
  const raiosDasPlacas = panelSweepRadii(projection.nodes);
  const obstaculosDeAresta: EdgeObstacle[] = [];
  for (const [id, radius] of raiosDasPlacas) {
    const position = positions.get(id);
    if (position) obstaculosDeAresta.push({ id, position, radius });
  }

  // A camada de eventos ao vivo recebe **só as posições do corpus**.
  //
  // Ela amarra cada evento à entidade que ele toca, e dimensiona o próprio anel pela
  // extensão que recebe. Entregando o mundo composto, esse anel passava a medir 529
  // unidades — a distância até o observatório — e os eventos se espalhavam por cima do
  // atlas inteiro. Ela anota o corpus; é a extensão do corpus que a governa.
  const posicoesDoCorpus: LayoutMap = new Map(
    [...positions].filter(([id]) => idsPorCamada.corpus.has(id)),
  );
  // As hastes da camada viva miram no corpus **e** na nuvem de modelos: o evento anota
  // uma nota quando tem uma, e o modelo que o executou tem identidade canônica lá.
  //
  // E ela recebe os centros das outras nuvens operacionais, para se assentar no que
  // sobra. O lado dela era fixo — o oposto de onde o observatório ficava **antes** —, e
  // quando a composição mudou o raciocínio foi parar sobre a região de computação: a
  // nuvem que deve ter território próprio virava um arquipélago encostado no vizinho.
  const runtimeLayer = createRuntimeLayer(
    posicoesDoCorpus,
    positions,
    miolo,
    raiosDasPlacas,
    workerAnchors,
  );
  // `EventSource.open` ainda não é um snapshot. A camada só poderá afirmar atividade
  // quando o coordenador da página liberar explicitamente o gate de frescor.
  runtimeLayer.setActivityEnabled(false);
  scene.add(runtimeLayer.group);
  /** Histerese de LOD da camada viva, por entidade. Zerada a cada instantâneo. */
  const nivelRuntime = new Map<string, LodLevel>();


  // --- arestas -------------------------------------------------------------

  // Dois grupos de arestas, separados por **camada** e não por família.
  //
  // A distinção custou um defeito para aparecer: `operational` é ao mesmo tempo o nome
  // de uma camada da cena e o de uma família de relação que o corpus declara em
  // wikilink. Agrupar pelo nome da família fazia as arestas epistêmicas marcadas
  // `relation:operational` acompanharem o observatório, e elas reapareciam sobre o
  // corpus escondido. Camada é propriedade da aresta; família é vocabulário editorial.
  // O registro semântico: 555 relações dirigidas, intactas. Tudo que a cena desenha
  // deriva daqui, e de qualquer primitiva se volta a ele.
  const registroDeRelacoes = buildRelationRegistry(projection.edges);

  const idsDaCena = new Set(nosDaCena.map((node) => node.id));
  const arestaNaCena = (edge: { source: string; target: string }): boolean =>
    idsDaCena.has(edge.source) && idsDaCena.has(edge.target);
  const arestasEpistemicas = projection.edges.filter(
    (edge) => edge.layer === 'epistemic' && arestaNaCena(edge),
  );
  const arestasOperacionais = projection.edges.filter(
    (edge) => edge.layer === 'operational' && arestaNaCena(edge),
  );
  const grupoFamilias = new THREE.Group();
  grupoFamilias.name = 'relation-families';
  grupoFamilias.visible = true;
  scene.add(grupoFamilias);
  const grupoOperacional = new THREE.Group();
  grupoOperacional.name = 'relation-families:operational';
  scene.add(grupoOperacional);

  /**
   * Reconstrói as linhas por família a partir das posições correntes.
   *
   * Elas guardam vértice, e não referência ao nó: mover a placa sem refazer a linha
   * deixa o fio pendurado onde a placa estava. Foi exatamente o que a primeira tentativa
   * do modo solto ao vivo produziu — os corpos andaram, o leque ficou.
   *
   * A reconstrução descarta as geometrias anteriores. Sem isso, mil quadros de
   * assentamento vazam mil buffers na GPU.
   */
  const reconstruirFamilias = (fonte: LayoutMap): void => {
    for (const grupo of [grupoFamilias, grupoOperacional]) {
      for (const filho of [...grupo.children]) {
        grupo.remove(filho);
        const malha = filho as THREE.Mesh;
        malha.geometry?.dispose();
      }
    }
    for (const build of buildRelationLines(arestasEpistemicas, fonte, raiosDasPlacas)) {
      grupoFamilias.add(build.lines);
      if (build.markers) grupoFamilias.add(build.markers);
    }
    for (const build of buildRelationLines(arestasOperacionais, fonte, raiosDasPlacas)) {
      grupoOperacional.add(build.lines);
      if (build.markers) grupoOperacional.add(build.markers);
    }
  };
  reconstruirFamilias(positions);

  // Os filamentos agregados saem de cena.
  //
  // Eles existiam para a visão global mostrar a ponte entre territórios sem as dezenas
  // de arestas que a compõem. Com todas as relações desenhadas por padrão, o tubo passa
  // a dizer de novo o que as linhas já dizem — e um tubo por cima de um feixe é a
  // duplicação visual que 3.5-C existiu para desfazer. A agregação continua no dado, e
  // continua sendo o que a seleção recupera.

  // A espinha deixou de ser fixa e passou a ser **contextual**.
  //
  // Ela desenhava 223 relações nota→nota — 40% do corpus — sempre que a câmera entrava
  // na banda intermediária, e a visão global herdava esse emaranhado sem que ninguém o
  // tivesse pedido. Agora a visão global mostra só as pontes agregadas, e a espinha
  // aparece restrita ao território mais próximo do alvo da câmera: quem se aproxima de
  // um domínio recebe as relações **daquele** domínio, e não as de todos.
  const espinha = new THREE.LineSegments(
    new THREE.BufferGeometry(),
    new THREE.LineBasicMaterial({
      color: oklchToHex(NEUTRALS.edgeInactive),
      transparent: true,
      opacity: SPINE_OPACITY,
      depthWrite: false,
    }),
  );
  espinha.name = 'edges:spine';
  espinha.renderOrder = 0;
  espinha.visible = false;
  espinha.raycast = () => undefined;
  scene.add(espinha);

  /** Centroide de cada território, para saber de qual o usuário se aproximou. */
  const centroDoDominio = new Map<string, THREE.Vector3>();
  {
    const soma = new Map<string, { p: THREE.Vector3; n: number }>();
    for (const node of projection.nodes) {
      if (node.layer !== 'epistemic') continue;
      const p = positions.get(node.id);
      if (!p) continue;
      const atual = soma.get(node.domainId) ?? { p: new THREE.Vector3(), n: 0 };
      atual.p.add(new THREE.Vector3(p.x, p.y, p.z));
      atual.n += 1;
      soma.set(node.domainId, atual);
    }
    for (const [dominio, { p, n }] of soma) {
      centroDoDominio.set(dominio, p.divideScalar(Math.max(n, 1)));
    }
  }
  const dominioDoNo = new Map(projection.nodes.map((node) => [node.id, node.domainId]));

  /** O território mais próximo do alvo da câmera. */
  function dominioEmFoco(): string | null {
    let melhor: string | null = null;
    let menor = Infinity;
    for (const [dominio, centro] of centroDoDominio) {
      const d = centro.distanceTo(orbit.target);
      if (d < menor) {
        menor = d;
        melhor = dominio;
      }
    }
    return melhor;
  }

  let dominioDaEspinha: string | null = null;

  /**
   * Reescreve a espinha com as relações internas de um território.
   *
   * O orçamento é por primitiva e não por aresta: `MAX_PRIMITIVAS_DE_DOMINIO` limita
   * quantos pares o território desenha, e a ordenação por grau põe primeiro os que
   * explicam a estrutura. Cortar pelo fim de uma lista ordenada é declaradamente uma
   * escolha editorial, e é melhor que a alternativa anterior, que era não cortar.
   */
  function escreverEspinhaDoDominio(dominio: string | null): void {
    if (dominio === dominioDaEspinha) return;
    dominioDaEspinha = dominio;
    if (!dominio) {
      escrever(espinha, []);
      return;
    }
    const pares = registroDeRelacoes.pairs
      .filter(
        (par) =>
          par.aggregation === 'canonical' &&
          !par.selfLink &&
          dominioDoNo.get(par.a) === dominio &&
          dominioDoNo.get(par.b) === dominio,
      )
      .sort((x, y) => y.relationCount - x.relationCount || x.key.localeCompare(y.key))
      .slice(0, MAX_PRIMITIVAS_DE_DOMINIO);
    const vertices: number[] = [];
    for (const par of pares) {
      const a = positions.get(par.a);
      const b = positions.get(par.b);
      if (!a || !b) continue;
      // A espinha desenha as mesmas relações que as famílias desenham, e por isso
      // percorre o mesmo caminho: reta aqui e curva ali fariam a mesma relação parecer
      // duas, uma em cima da outra, quando o regime intermediário liga as duas camadas.
      const caminho = caminhoDaAresta(par.a, par.b, a, b);
      if (caminho) vertices.push(...dashPath(caminho, []));
    }
    escrever(espinha, vertices);
  }

  function linhasDeFoco(nome: string, opacidade: number): THREE.LineSegments {
    const linhas = new THREE.LineSegments(
      new THREE.BufferGeometry(),
      new THREE.LineBasicMaterial({
        // A cor vem do vértice: o link entre o painel escolhido e cada vizinho é um
        // degradê entre as duas cores de domínio. Uma linha de cor única diria que a
        // relação pertence a alguém; o degradê diz que ela liga dois lados, e mostra
        // **quais** dois — que é a pergunta de quem acabou de selecionar algo.
        vertexColors: true,
        transparent: true,
        opacity: opacidade,
        depthWrite: false,
      }),
    );
    linhas.name = nome;
    linhas.renderOrder = ORDEM_ARESTAS_FOCAIS;
    linhas.visible = false;
    linhas.raycast = () => undefined;
    scene.add(linhas);
    return linhas;
  }

  /**
   * O primeiro grau é uma **fita**, não uma linha.
   *
   * Uma linha de um pixel não tem como ganhar destaque: `linewidth` é ignorado pelo
   * driver, e sem espessura o único recurso restante seria cor — que já é do domínio.
   * A fita é construída no vértice a partir da resolução da tela, então ela engrossa de
   * verdade, e a espessura vira o canal que responde à seleção.
   */
  const materialFocal = new LineMaterial({
    vertexColors: true,
    transparent: true,
    opacity: RELACOES_DIRETAS,
    depthWrite: false,
    linewidth: ESPESSURA_EM_REPOUSO,
    // Mistura normal. A aditiva parecia a escolha óbvia para "mais luminoso", e medida
    // na cena as duas ficaram quase empatadas — dos pixels claros que a seleção acende,
    // 48% saem neutros com a normal contra 53% com a aditiva. A diferença é pequena, e
    // desempata a favor da normal porque a aditiva satura para branco justamente onde
    // vários links se sobrepõem, que é onde há mais relação para ler. A luz aqui vem da
    // cor — clara e saturada por `linkColorOf` —, não da soma.
  });
  materialFocal.resolution.set(container.clientWidth, container.clientHeight);
  const focais = new LineSegments2(new LineSegmentsGeometry(), materialFocal);
  focais.name = 'edges:focus';
  focais.renderOrder = ORDEM_ARESTAS_FOCAIS;
  focais.visible = false;
  focais.raycast = () => undefined;
  // A fita é construída a partir de segmentos, e o volume de cálculo do frustum não
  // acompanha a espessura: sem isto o link some ao encostar na borda da tela.
  focais.frustumCulled = false;
  scene.add(focais);

  /**
   * A ênfase é uma **transição**, não um degrau.
   *
   * Trocar a espessura de uma vez faz o link piscar, e piscar lê como defeito. Crescer
   * em pouco mais de dois décimos lê como resposta ao clique — o olho acompanha o link
   * engrossando e sabe, sem legenda, qual painel puxou aquilo.
   */
  let espessuraAtual = ESPESSURA_EM_REPOUSO;
  let espessuraAlvo = ESPESSURA_EM_REPOUSO;
  function engrossarFoco(delta: number): void {
    if (espessuraAtual === espessuraAlvo) return;
    // Sem movimento, a preferência do sistema manda: chega no destino sem animar.
    const passo = mutable.reducedMotion ? 1 : Math.min(delta / TEMPO_DA_ENFASE, 1);
    espessuraAtual += (espessuraAlvo - espessuraAtual) * passo;
    if (Math.abs(espessuraAlvo - espessuraAtual) < 0.01) espessuraAtual = espessuraAlvo;
    materialFocal.linewidth = espessuraAtual;
  }

  // Segundo grau continua linha fina: ele responde "há mais além disto" e não deve
  // disputar leitura com o que foi perguntado.
  const segundoGrau = linhasDeFoco('edges:second-degree', RELACOES_INATIVAS);

  // --- halo de seleção ------------------------------------------------------

  // O halo é a única coisa que sobrou do envoltório: uma placa discreta atrás do
  // painel selecionado, sem clique e sem raycast. Ele marca; não é lido.
  // O halo assume a silhueta do painel que ele marca.
  //
  // Com forma fixa, ele aparecia como um retângulo atrás de um losango ou de um
  // hexágono — a placa velha que parecia ter sobrado, e que na verdade nunca tinha
  // deixado de ser retângulo. Marcar uma forma com outra forma é apontar para o lugar
  // errado.
  const halo = new THREE.Mesh(
    panelShapeGeometry('retangulo'),
    panelHaloMaterial(oklchToHex(NEUTRALS.focus)),
  );
  halo.name = 'panel-halo';
  halo.visible = false;
  halo.renderOrder = ORDEM_HALO;
  halo.raycast = () => undefined;
  scene.add(halo);

  scene.add(camera);

  // --- estado ---------------------------------------------------------------

  /**
   * Quem escutar a escolha recebe o nó e a posição dele na tela.
   *
   * É por aqui que a configuração de um provedor chega ao painel dele: o Atlas não
   * conhece formulário nem credencial, e quem os conhece não conhece a projeção. O
   * ponto vai junto porque projetar mundo em pixel exige a câmera, que mora aqui.
   */
  let aoEscolher: ((escolha: AtlasSelection) => void) | null = null;

  function pontoNaTela(id: string): { x: number; y: number } | null {
    const doCorpus = corpos.renderPositionFor(id);
    const doRuntime = doCorpus ? null : runtimeLayer.renderPositionFor(id);
    const onde = doCorpus ?? doRuntime;
    if (!onde) return null;
    const projetada = onde.clone().project(camera);
    if (projetada.z > 1) return null;
    const largura = renderer.domElement.clientWidth || 1;
    const altura = renderer.domElement.clientHeight || 1;
    return {
      x: ((projetada.x + 1) / 2) * largura,
      y: ((1 - projetada.y) / 2) * altura,
    };
  }

  function anunciarEscolha(id: string | null, runtime: boolean): void {
    aoEscolher?.({ id, runtime, screen: id === null ? null : pontoNaTela(id) });
  }

  /** O painel cuja face é desenhada fora da cena. No máximo um, e quase sempre nenhum. */
  let painelComFace: string | null = null;

  /**
   * A geometria de leitura de um painel: onde ele está, quanto ele mede, que forma tem.
   *
   * Corpus e camada viva guardam isso em módulos diferentes, e quem projeta não deve
   * precisar saber de qual dos dois o nó veio.
   */
  function geometriaDoPainel(id: string): {
    onde: THREE.Vector3;
    extent: { width: number; height: number };
    shape: PanelShape;
    token: string;
  } | null {
    const doCorpus = corpos.renderPositionFor(id);
    if (doCorpus) {
      const extent = corpos.extentFor(id);
      const descriptor = corpos.descriptorFor(id);
      if (!extent || !descriptor) return null;
      return {
        onde: doCorpus,
        extent,
        shape: descriptor.shape,
        token: descriptor.paletteToken,
      };
    }
    const vivo = runtimeLayer.panels().find((painel) => painel.entityId === id);
    if (!vivo) return null;
    const onde = runtimeLayer.renderPositionFor(id);
    if (!onde) return null;
    return {
      onde,
      extent: vivo.extent,
      shape: vivo.descriptor.shape,
      token: vivo.descriptor.paletteToken,
    };
  }

  function faceDoPainel(): PanelFaceRect | null {
    const id = painelComFace;
    if (id === null) return null;
    const geometria = geometriaDoPainel(id);
    if (!geometria) return null;
    const area = textAreaOf(geometria.shape, geometria.extent);
    // O centro da área de leitura sobe pelo `offsetY` da silhueta, na direção que a
    // placa chama de "para cima" — e, como toda placa olha para a câmera, essa direção
    // é a vertical da própria câmera. Sem isto a face cairia no centro geométrico, que
    // nas formas assimétricas não é onde o texto mora.
    const centro = geometria.onde
      .clone()
      .addScaledVector(camera.up.clone().normalize(), area.offsetY);
    const projetada = centro.clone().project(camera);
    // Atrás da câmera não há face: continuar projetando devolveria um retângulo
    // espelhado no lado errado da tela, sobre um painel que ninguém está vendo.
    if (projetada.z > 1) return null;
    const larguraViewport = renderer.domElement.clientWidth || 1;
    const alturaViewport = renderer.domElement.clientHeight || 1;
    const distancia = camera.position.distanceTo(centro);
    const largura = projectedPixels(area.width / 2, distancia, camera.fov, alturaViewport);
    const altura = projectedPixels(area.height / 2, distancia, camera.fov, alturaViewport);
    const x = ((projetada.x + 1) / 2) * larguraViewport;
    const y = ((1 - projetada.y) / 2) * alturaViewport;
    return {
      left: x - largura / 2,
      top: y - altura / 2,
      width: largura,
      height: altura,
      ink: inkOn(tokenColor(geometria.token)),
    };
  }
  /**
   * Deslocamento de leitura do painel selecionado.
   *
   * Um mapa e não um escalar porque a rolagem pertence ao painel: voltar a um nó já
   * lido devolve a posição em que ele foi deixado, e trocar de nó não herda a rolagem
   * do anterior.
   */
  const rolagemPorEntidade = new Map<string, number>();
  const rolagemMaxima = new Map<string, number>();

  /**
   * O documento de cada nota já buscada, em linhas.
   *
   * A projeção leva `summary` — a abertura do corpo, cortada — e os claims. Um painel
   * aberto mostrava, com isso, frases **sobre** a nota e a primeira frase **dela**, e
   * depois espaço vazio: o resto do documento não existia no navegador. Buscar sob
   * demanda é o que permite mostrá-lo inteiro sem inchar a projeção, que é servida em
   * bloco a cada abertura para que um único painel — o aberto — use um corpo de cada vez.
   *
   * O mapa é cache e é permanente na sessão: reabrir uma nota já lida não repete a
   * viagem, e o documento de uma nota não muda enquanto a projeção não muda.
   */
  const documentoPorEntidade = new Map<string, PanelLine[]>();
  /** A busca em curso. Trocar de painel cancela a anterior: ninguém lê duas de uma vez. */
  let buscaDeDocumento: AbortController | null = null;

  function buscarDocumento(id: string): void {
    if (documentoPorEntidade.has(id)) return;
    const node = slots.get(id)?.node;
    // Só o corpus tem documento: um painel de quórum não é arquivo nenhum, e pedir um
    // para ele seria inventar um 404 por quadro.
    if (!node || node.layer !== 'epistemic' || node.path === null) return;
    buscaDeDocumento?.abort();
    const controlador = new AbortController();
    buscaDeDocumento = controlador;
    void loadNoteDocument(node.path, controlador.signal)
      .then((corpo) => {
        documentoPorEntidade.set(id, documentLines(corpo, { title: node.title }));
      })
      .catch((erro: unknown) => {
        if (controlador.signal.aborted) return;
        // Falhar aqui não corrompe nada: o painel continua com as frases derivadas do
        // descritor. O que não pode é falhar em silêncio, e por isso o anúncio existe.
        announce(`Documento de ${node.title} indisponível: ${String(erro)}`);
      });
  }

  const mutable = {
    selected: null as string | null,
    hovered: null as string | null,
    reducedMotion: false,
    view: 'global' as 'global' | 'focus',
    /**
     * O evento ao vivo escolhido, que lê como painel expandido.
     *
     * Fica no estado observável, e não numa variável privada, porque "o que está
     * selecionado" é pergunta que a interface e a auditoria fazem — e um seletor que
     * ninguém consegue consultar é um seletor que ninguém consegue conferir.
     */
    runtimeSelected: null as string | null,
    /**
     * A entidade do corpus na outra ponta da haste do evento vivo selecionado.
     *
     * Entrada de `aplicarEnfase`, e não um segundo escritor de ênfase. Antes existia uma
     * função própria que varria todos os slots por conta própria: quem rodasse por
     * último vencia, e um `hover` ou um quadro SSE apagava o vínculo aceso enquanto a
     * seleção viva continuava ativa. Estado derivado tem um dono só.
     */
    runtimeLinkedEntity: null as string | null,
  };
  let initialRuntimeFramingResolved = false;
  let viewTouchedByUser = false;

  /** Depois do primeiro gesto, nenhum evento assíncrono ganha autoridade sobre a câmera. */
  function markViewTouched(): void {
    viewTouchedByUser = true;
  }

  /**
   * O nível efetivo do painel.
   *
   * Selecionar não muda a distância: muda o que o painel mostra. Forçar `expanded`
   * aqui — em vez de mexer no nível medido — preserva a histerese e faz o painel
   * voltar sozinho ao nível certo quando a seleção sai.
   */
  function nivelDe(slot: NodeSlot): LodLevel | undefined {
    if (mutable.selected === slot.node.id) return 'expanded';
    return slot.level;
  }

  /**
   * Ênfase de toda a cena, derivada de tudo que a determina. Uma passada, sem alocar.
   *
   * **Esta é a única função que escreve ênfase.** Havia duas, e a segunda acendia a
   * outra ponta da haste do evento vivo varrendo os mesmos slots por conta própria.
   * Quem rodasse por último vencia: mover o mouse ou receber um quadro SSE apagava o
   * vínculo aceso enquanto a seleção viva continuava ativa, e o inverso também
   * acontecia. Estado visual derivado de várias entradas precisa de uma função que
   * conheça todas elas, não de uma função por entrada.
   */
  function aplicarEnfase(): void {
    const ativo = mutable.selected;
    const estado: EmphasisState = {
      selected: ativo,
      hovered: mutable.hovered,
      linkedEntity: mutable.runtimeLinkedEntity,
      neighbours: ativo ? vizinhos.get(ativo) : undefined,
    };
    for (const id of slots.keys()) corpos.setEmphasis(id, emphasisFor(id, estado));
    // A operação acompanha o foco do corpus: sem isso a camada viva continuaria em
    // contraste cheio e competiria com o nó que se está lendo.
    runtimeLayer.setDimmed(ativo !== null, ativo);
  }

  function select(id: string | null): void {
    const anterior = mutable.selected;
    if (anterior && anterior !== id) {
      corpos.setExpanded(anterior, false);
      atualizarCorpo(anterior, false);
    }
    mutable.selected = id;

    if (!id) {
      halo.visible = false;
      focais.visible = false;
      segundoGrau.visible = false;
      // Soltar a seleção devolve a fita à espessura de repouso, para o próximo clique
      // começar do mesmo lugar em vez de herdar a ênfase do anterior.
      espessuraAlvo = ESPESSURA_EM_REPOUSO;
      mutable.view = 'global';
      ajustarLimiteDeAproximacao(null);
      if (mutable.runtimeSelected !== null) {
        mutable.runtimeSelected = null;
        // O vínculo cai junto: ele é derivado da seleção viva, e sobreviver a ela
        // deixaria uma entidade acesa sem nada apontando para ela.
        mutable.runtimeLinkedEntity = null;
        runtimeLayer.setSelected(null);
      }
      aplicarEnfase();
      atualizarRegimeDeRelacoes();
      anunciarEscolha(null, false);
      announce('Nenhuma entidade selecionada. Visão global.');
      return;
    }

    const slot = slots.get(id);
    if (!slot) {
      mutable.selected = anterior;
      return;
    }
    // Um painel visto pela primeira vez começa no topo; um já lido volta onde parou.
    if (!rolagemPorEntidade.has(id)) rolagemPorEntidade.set(id, 0);
    buscarDocumento(id);

    // A ordem importa: expandir antes de medir, porque o halo e a aproximação usam a
    // extensão efetiva, que só existe depois da expansão.
    corpos.setExpanded(id, true);
    atualizarCorpo(id, true);
    mutable.view = 'focus';
    ajustarLimiteDeAproximacao(id);
    aplicarEnfase();

    desenharVizinhanca(id);
    atualizarRegimeDeRelacoes();
    anunciarEscolha(id, false);
    const incidentes = (vizinhos.get(id) ?? new Set<string>()).size;

    // **A câmera não anda no clique.** Ela andava quando o painel ainda não estava em
    // distância de leitura, o que fazia o mesmo gesto ter dois efeitos conforme de onde
    // se clicava: perto, escolher; longe, escolher e viajar. Quem usa não tem como
    // prever qual dos dois vai acontecer, e a resposta muda de nuvem para nuvem porque a
    // distância de leitura depende do tamanho da placa. Um clique escolhe; o duplo traz.

    announce(
      `${slot.node.title}, expandido no lugar. Domínio ${slot.node.domainLabel}. ` +
        `${slot.node.claimCount} claims. ${incidentes} vizinhos diretos. ` +
        'Esc, clique no vazio ou segundo clique para recolher.',
    );
  }

  /**
   * Distância mínima da órbita, derivada do que está no alvo.
   *
   * Era a constante 12, e a auditoria mostrou o que isso custava: com `fov` de 38° a
   * janela mostra 14,7 × 8,3 unidades a essa distância, e um MOC expandido mede
   * 28,2 × 15,8 — quase o dobro em cada eixo. Rolar a roda até o fim enchia a tela de
   * texto recortado. O limite agora é o tamanho do alvo: aproximar-se para de funcionar
   * exatamente onde o painel deixaria de caber.
   */
  function ajustarLimiteDeAproximacao(id: string | null): void {
    if (!id) {
      orbit.minDistance = LIMITE_DE_APROXIMACAO_MINIMO;
      return;
    }
    const medida = corpos.extentFor(id);
    const slot = slots.get(id);
    const alcance = medida
      ? Math.max(medida.width, medida.height)
      : slot
        ? BASE_RADIUS[slot.kind] * 2
        : 0;
    orbit.minDistance = distanciaMinimaDaOrbita({
      alcance,
      fovDeg: camera.fov,
      width: renderer.domElement.clientWidth || container.clientWidth || 1280,
      height: renderer.domElement.clientHeight || container.clientHeight || 720,
    });
  }

  /**
   * A base da câmera: direita e cima da tela, em coordenadas de mundo.
   *
   * `direita = cima × paraTrás`, nesta ordem. A ordem inversa devolve o vetor com o
   * sinal trocado, e o efeito é silencioso: a compensação do dock empurrava a cena
   * para debaixo do próprio painel em vez de para fora dele.
   */
  function baseDaCamera(alvo: THREE.Vector3): {
    paraTras: THREE.Vector3;
    direita: THREE.Vector3;
    acima: THREE.Vector3;
  } {
    const paraTras = new THREE.Vector3().subVectors(camera.position, alvo).normalize();
    const direita = new THREE.Vector3().crossVectors(camera.up, paraTras).normalize();
    const acima = new THREE.Vector3().crossVectors(paraTras, direita).normalize();
    return { paraTras, direita, acima };
  }

  /** Distância em que uma placa de dado alcance ocupa a fatia de leitura da janela. */
  function distanciaDeLeitura(alcance: number, fatia = ALVO_DE_LEITURA): number {
    // Uma janela ainda sem layout mede zero, e zero aqui colapsava a aproximação
    // até a distância mínima da órbita: um painel selecionado antes do primeiro
    // `resize` engolia a tela inteira. Preferir o contêiner, e depois um valor de
    // referência, é dizer "não sei a janela" em vez de dizer "a janela tem 1 pixel".
    const altura = renderer.domElement.clientHeight || container.clientHeight || 720;
    const focal = altura / (2 * Math.tan((camera.fov * Math.PI) / 360));
    const limiarExpandido =
      LOD_THRESHOLDS.find((item) => item.level === 'expanded')?.minPixels ?? 80;
    const alvo = Math.max(altura * fatia, limiarExpandido);
    return Math.max((alcance * focal) / alvo, orbit.minDistance);
  }

  /**
   * Recentra sem girar. A direção de visada é preservada de propósito: mudar o
   * ângulo junto com o alvo desorienta, e o dossiê pede estabilidade de câmera —
   * nenhuma mudança de perspectiva que o usuário não tenha pedido.
   */
  function aproximarDe(slot: NodeSlot): void {
    const direcao = new THREE.Vector3().subVectors(camera.position, orbit.target).normalize();
    const medida = corpos.extentFor(slot.node.id);
    const alcance = medida ? Math.max(medida.width, medida.height) : BASE_RADIUS[slot.kind] * 2;
    // Painel com face é painel em que se digita, e por isso ele chega mais perto.
    const distancia = distanciaDeLeitura(
      alcance,
      painelComFace === slot.node.id ? ALVO_DE_DIGITACAO : ALVO_DE_LEITURA,
    );
    orbit.target.copy(slot.position);
    camera.position.copy(orbit.target).addScaledVector(direcao, distancia);
    camera.updateMatrixWorld();
  }

  /**
   * Enquadra o que está realmente ocupado, medido nos eixos da tela.
   *
   * Duas coisas faziam a visão global sair com metade da janela vazia. A distância
   * vinha da extensão dos **centros**, sem contar a extensão das placas; e a caixa
   * usada era alinhada aos eixos do mundo, que numa visada oblíqua é bem maior do que
   * a área que a cena de fato cobre — enquadrar a caixa é enquadrar o vazio em volta
   * dela.
   *
   * Aqui cada painel é projetado nos eixos da própria câmera, com a meia-extensão
   * dele somada como margem de tela. O que se enquadra passa a ser a ocupação, e a
   * faixa coberta pelo dock sai da largura antes da conta.
   */
  const MARGEM_DE_ENQUADRAMENTO = 0.1;

  function fitToGraph(): void {
    // Os títulos têm tamanho aparente limitado. Medir antes de aplicar essa escala
    // enquadraria o corpo bruto do mundo e depois o título poderia crescer para fora do
    // quadro no primeiro render.
    nomesDasNuvens.orient(camera.quaternion);
    nomesDasNuvens.updateView(
      camera,
      renderer.domElement.clientHeight || container.clientHeight || 720,
    );
    const ocupacao: {
      posicao: THREE.Vector3;
      meiaLargura: number;
      meiaAltura: number;
    }[] = [];
    const origem = new THREE.Vector3();
    const ativos = idsDaProjecao;
    for (const slot of slots.values()) {
      if (!ativos.has(slot.node.id)) continue;
      const medida = corpos.extentFor(slot.node.id);
      if (!medida) continue;
      ocupacao.push({
        posicao: slot.position.clone(),
        meiaLargura: medida.width / 2,
        meiaAltura: medida.height / 2,
      });
      origem.add(slot.position);
    }
    // A camada viva também é cena, e ficava de fora da conta: desde que ela ganhou lugar
    // próprio, longe do corpus, isso deixou de ser detalhe — ela aparecia cortada na
    // borda e o nome dela nem entrava no quadro.
    // Os nomes das nuvens entram na conta: eles se assentam na borda de cada uma, e
    // ficavam fora do quadro justamente nas nuvens em que servem mais.
    for (const nome of nomesDasNuvens.bounds()) {
      ocupacao.push({
        posicao: nome.position.clone(),
        meiaLargura: nome.halfWidth,
        meiaAltura: nome.halfHeight,
      });
      origem.add(nome.position);
    }
    for (const painel of runtimeLayer.panels()) {
      ocupacao.push({
        posicao: painel.position.clone(),
        meiaLargura: painel.extent.width / 2,
        meiaAltura: painel.extent.height / 2,
      });
      origem.add(painel.position);
    }
    if (ocupacao.length === 0) return;
    origem.divideScalar(ocupacao.length);

    const { paraTras, direita, acima } = baseDaCamera(orbit.target);
    const larguraJanela = renderer.domElement.clientWidth || container.clientWidth || 1280;
    const alturaJanela = renderer.domElement.clientHeight || container.clientHeight || 720;
    const vertical = (camera.fov * Math.PI) / 180;
    const tanV = Math.tan(vertical / 2);
    const tanH = tanV * (larguraJanela / alturaJanela);
    const relativo = new THREE.Vector3();

    // Passagem um: onde a ocupação começa e termina, em cada eixo da tela.
    let latMin = Number.POSITIVE_INFINITY;
    let latMax = Number.NEGATIVE_INFINITY;
    let vertMin = Number.POSITIVE_INFINITY;
    let vertMax = Number.NEGATIVE_INFINITY;
    for (const painel of ocupacao) {
      relativo.copy(painel.posicao).sub(origem);
      const lateral = relativo.dot(direita);
      const altura = relativo.dot(acima);
      latMin = Math.min(latMin, lateral - painel.meiaLargura);
      latMax = Math.max(latMax, lateral + painel.meiaLargura);
      vertMin = Math.min(vertMin, altura - painel.meiaAltura);
      vertMax = Math.max(vertMax, altura + painel.meiaAltura);
    }

    // O centro do enquadramento é o meio da ocupação, não a média das posições: um
    // território mais povoado puxaria a média e deixaria o outro lado cortado.
    const centro = origem
      .clone()
      .addScaledVector(direita, (latMin + latMax) / 2)
      .addScaledVector(acima, (vertMin + vertMax) / 2);

    // Passagem dois: a distância que faz caber o painel mais exigente. Quem está mais
    // perto da câmera exige mais afastamento, e por isso a profundidade entra na conta.
    let distancia = orbit.minDistance;
    for (const painel of ocupacao) {
      relativo.copy(painel.posicao).sub(centro);
      const profundidade = relativo.dot(paraTras);
      distancia = Math.max(
        distancia,
        (Math.abs(relativo.dot(direita)) + painel.meiaLargura) / tanH + profundidade,
        (Math.abs(relativo.dot(acima)) + painel.meiaAltura) / tanV + profundidade,
      );
    }

    orbit.target.copy(centro);
    camera.position.copy(orbit.target).addScaledVector(paraTras, distancia);
    // O plano distante acompanha o enquadramento.
    //
    // Ele vinha da pose inicial, calculada com o raio do **corpus** — 109 unidades —
    // enquanto o mundo composto tem quase mil. Recuar a câmera para caber as quatro
    // nuvens levava o observatório para além do plano, e a cena inteira desaparecia: um
    // quadro vazio que parecia defeito de enquadramento e era de recorte.
    let maisLonge = distancia;
    for (const painel of ocupacao) {
      maisLonge = Math.max(
        maisLonge,
        camera.position.distanceTo(painel.posicao) +
          Math.max(painel.meiaLargura, painel.meiaAltura),
      );
    }
    if (camera.far < maisLonge * 1.15) {
      camera.far = maisLonge * 1.15;
      camera.updateProjectionMatrix();
    }
    camera.updateMatrixWorld();

    // A distância que a passagem dois calculou é o teto do refino.
    //
    // O refino em NDC é iterativo e pode divergir: um ponto que projeta atrás da câmera
    // entra no cálculo com sinal invertido, o preenchimento estimado dispara, a câmera
    // recua, e recuar põe mais pontos em posição ruim. Medido, com o conteúdo mais
    // distante a 416 unidades ele chegou a pedir 4196 — e a cena inteira desapareceu num
    // quadro vazio. A passagem dois trabalha em unidades de mundo e não tem esse modo de
    // falha; ela serve de teto, e o refino continua livre para **aproximar**.
    const tetoDoRefino = distancia * TETO_DO_REFINO;

    // Passagem três: refino no espaço de tela.
    //
    // As duas primeiras trabalham em unidades de mundo, e o mundo não é o que se vê:
    // a perspectiva divide pela profundidade, então numa visada oblíqua o meio da
    // ocupação em coordenadas de mundo não cai no meio da imagem. O lado próximo
    // projeta maior e puxa o conjunto para baixo — era por isso que a cena ficava
    // enquadrada e ainda assim descentrada. Aqui a conta é feita onde o defeito
    // aparece: em NDC, já na área efetivamente desenhada pelo canvas.
    for (let passagem = 0; passagem < 2; passagem += 1) {
      let xMin = Number.POSITIVE_INFINITY;
      let xMax = Number.NEGATIVE_INFINITY;
      let yMin = Number.POSITIVE_INFINITY;
      let yMax = Number.NEGATIVE_INFINITY;
      let visiveis = 0;
      for (const painel of ocupacao) {
        relativo.copy(painel.posicao).project(camera);
        if (!Number.isFinite(relativo.x) || relativo.z >= 1) continue;
        visiveis += 1;
        xMin = Math.min(xMin, relativo.x);
        xMax = Math.max(xMax, relativo.x);
        yMin = Math.min(yMin, relativo.y);
        yMax = Math.max(yMax, relativo.y);
      }
      if (visiveis === 0) break;

      // NDC 1 vale esta distância em unidades de mundo, no plano do alvo.
      const meiaLarguraMundo = tanV * (larguraJanela / alturaJanela) * distancia;
      const meiaAlturaMundo = tanV * distancia;
      orbit.target
        .addScaledVector(direita, ((xMin + xMax) / 2) * meiaLarguraMundo)
        .addScaledVector(acima, ((yMin + yMax) / 2) * meiaAlturaMundo);

      const preenchimento = Math.max(
        (xMax - xMin) / 2,
        (yMax - yMin) / 2,
        0.05,
      );
      distancia = Math.min(
        tetoDoRefino,
        Math.max(distancia * preenchimento * (1 + MARGEM_DE_ENQUADRAMENTO), orbit.minDistance),
      );
      camera.position.copy(orbit.target).addScaledVector(paraTras, distancia);
      camera.updateMatrixWorld();
    }

    orbit.maxDistance = Math.max(orbit.maxDistance, distancia * 1.6);
    orbit.update();
  }

  function focusOn(id: string): void {
    const slot = slots.get(id);
    if (!slot) return;
    if (mutable.selected !== id) select(id);
    aproximarDe(slot);
  }

  function atualizarCorpo(id: string, selecionado: boolean): void {
    const slot = slots.get(id);
    if (!slot) return;
    corpos.setElevated(id, selecionado);
    // MOCs e operação sustentam a leitura global. Só conteúdo epistêmico sem tamanho
    // projetado suficiente sai do raster; a posição continua estável.
    const visivel =
      selecionado ||
      slot.kind === 'moc' ||
      slot.node.layer === 'operational' ||
      slot.level === undefined ||
      showsBody(slot.level);
    corpos.setVisible(id, visivel);
  }

  function escrever(linhas: THREE.LineSegments, vertices: number[], cores?: number[]): void {
    linhas.geometry.dispose();
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    // Sem cor declarada, o branco deixa a opacidade do material decidir sozinha — é o
    // que o segundo grau quer, já que ele responde "há mais além disto" e não "isto
    // liga aquilo com aquele outro".
    const canal = cores ?? new Array<number>((vertices.length / 3) * 3).fill(1);
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(canal, 3));
    linhas.geometry = geometry;
    linhas.visible = vertices.length > 0;
  }

  /** Escreve a fita do primeiro grau, que guarda posições e cores por segmento. */
  function escreverFita(vertices: number[], cores: number[]): void {
    focais.geometry.dispose();
    const geometry = new LineSegmentsGeometry();
    const cabem = vertices.length >= 6 && vertices.length % 6 === 0;
    if (cabem) {
      geometry.setPositions(vertices);
      if (cores.length === vertices.length) geometry.setColors(cores);
    }
    focais.geometry = geometry;
    focais.visible = cabem;
  }

  /**
   * A cor de domínio de uma entidade, para o degradê do link saber de onde partir.
   *
   * É a versão de **link** do token: mais clara e mais saturada que a do corpo. A cor de
   * superfície, pensada para área grande, chegava apagada quando esticada num fio de
   * poucos pixels — e um degradê esbranquiçado não diz quais dois domínios ele liga.
   */
  const corDaEntidade = new Map<string, Oklch>();
  for (const node of projection.nodes) {
    corDaEntidade.set(node.id, linkColorOf(tokenColor(node.visual.paletteToken)));
  }
  const corNeutra = NEUTRALS.focus;
  /** Reaproveitada a cada vértice do degradê: são milhares por seleção. */
  const corDoDegrade = new THREE.Color();

  /**
   * As duas camadas de vizinhança do nó ativo.
   *
   * O primeiro grau carrega a assinatura da família — contínua, tracejada, traço-ponto
   * —, porque é o único conjunto em que essa distinção pode ser lida. O segundo grau
   * entra liso e quase invisível: ele responde "há mais para além disto" sem disputar
   * a leitura com o que foi perguntado.
   */
  /**
   * O caminho de uma aresta do corpus, com a mesma regra que a linha de repouso usa.
   *
   * A vizinhança é reescrita a cada seleção, então ela recalcula o desvio em vez de
   * guardá-lo: guardar exigiria manter um caminho por par vivo enquanto o layout pode
   * mudar por baixo, e o custo aqui é de dezenas de arestas, não de mil.
   */
  function caminhoDaAresta(
    origem: string,
    destino: string,
    a: Vec3,
    b: Vec3,
  ): Vec3[] | null {
    return edgePath(
      a,
      b,
      raiosDasPlacas.get(origem) ?? 0,
      raiosDasPlacas.get(destino) ?? 0,
      obstaculosDeAresta,
      new Set([origem, destino]),
    );
  }

  function desenharVizinhanca(id: string): void {
    const primeiroGrau = vizinhos.get(id) ?? new Set<string>();
    const diretas: number[] = [];
    const coresDiretas: number[] = [];
    const indiretas: number[] = [];

    for (const edge of projection.edges) {
      if (edge.kind === 'aggregated') continue;
      const a = positions.get(edge.source);
      const b = positions.get(edge.target);
      if (!a || !b) continue;

      if (edge.source === id || edge.target === id) {
        const style = edge.primaryRelation ? EDGE_STYLES[edge.primaryRelation] : null;
        const antes = diretas.length;
        // O realce percorre o **mesmo** caminho que a linha de repouso: aparado nas
        // duas placas e desviado do que houver no meio. Traçá-lo reto faria selecionar
        // mudar por onde a relação passa, e o degradê apareceria cruzando placas que a
        // linha apagada contornava.
        const caminho = caminhoDaAresta(edge.source, edge.target, a, b);
        if (caminho) diretas.push(...dashPath(caminho, style?.pattern ?? []));
        // Um degradê por segmento, interpolado pela posição do traço ao longo do par.
        // Com padrão tracejado a linha vira vários segmentos, e colorir cada um pelo
        // ponto onde ele está é o que faz o degradê atravessar a lacuna sem saltar.
        const daOrigem = corDaEntidade.get(edge.source) ?? corNeutra;
        const doDestino = corDaEntidade.get(edge.target) ?? corNeutra;
        const comprimento = Math.hypot(b.x - a.x, b.y - a.y, b.z - a.z) || 1;
        for (let v = antes; v < diretas.length; v += 3) {
          const t = Math.min(
            Math.max(
              Math.hypot(diretas[v]! - a.x, diretas[v + 1]! - a.y, diretas[v + 2]! - a.z) /
                comprimento,
              0,
            ),
            1,
          );
          // A mistura acontece em OKLCH, não em RGB: o miolo do degradê mantém croma
          // em vez de desbotar, e um leve ganho de luminosidade no meio do caminho
          // acende o trecho sem estourá-lo para branco.
          const misturada = mixOklch(daOrigem, doDestino, t);
          const cor = corDoDegrade.setHex(
            oklchToHex({
              ...misturada,
              l: Math.min(misturada.l + BRILHO_DO_MEIO * Math.sin(Math.PI * t), 0.98),
            }),
            THREE.SRGBColorSpace,
          );
          coresDiretas.push(cor.r, cor.g, cor.b);
        }
        continue;
      }
      // Segundo grau: uma ponta na vizinhança direta, a outra fora dela.
      const naVizinhanca = [edge.source, edge.target].filter((ponta) =>
        primeiroGrau.has(ponta),
      ).length;
      if (naVizinhanca === 1) {
        const caminho = caminhoDaAresta(edge.source, edge.target, a, b);
        if (caminho) indiretas.push(...dashPath(caminho, []));
      }
    }

    escreverFita(diretas, coresDiretas);
    escrever(segundoGrau, indiretas);
    // Selecionar é o que pede a ênfase; o crescimento em si é do laço.
    espessuraAlvo = diretas.length > 0 ? ESPESSURA_EM_FOCO : ESPESSURA_EM_REPOUSO;
  }

  /**
   * O foco na camada viva.
   *
   * A vizinhança do corpus é lida da projeção do corpus, e a camada viva tem projeção e
   * posições próprias — então clicar num evento acendia o painel e deixava as ligações
   * dele apagadas. Aqui os segmentos vêm da própria camada e entram na **mesma** fita,
   * com o mesmo degradê e a mesma ênfase que engrossa: o realce é um só na cena, e não um
   * por população.
   */
  function desenharVizinhancaViva(runtimeNodeId: string | null): void {
    if (runtimeNodeId === null) {
      escreverFita([], []);
      espessuraAlvo = ESPESSURA_EM_REPOUSO;
      return;
    }
    const vertices: number[] = [];
    const cores: number[] = [];
    const cor = corDoDegrade.setHex(oklchToHex(corNeutra), THREE.SRGBColorSpace);
    for (const { from, to } of runtimeLayer.neighbourhood(runtimeNodeId)) {
      vertices.push(from.x, from.y, from.z, to.x, to.y, to.z);
      cores.push(cor.r, cor.g, cor.b, cor.r, cor.g, cor.b);
    }
    escreverFita(vertices, cores);
    escrever(segundoGrau, []);
    espessuraAlvo = vertices.length > 0 ? ESPESSURA_EM_FOCO : ESPESSURA_EM_REPOUSO;
  }

  let regimeAtual: RegimeDeRelacoes | null = null;

  /**
   * Aplica o regime de relações. Só escreve quando o regime muda de verdade.
   *
   * Chamada a cada quadro porque a banda depende da distância da câmera, que muda
   * enquanto o usuário navega. Comparar antes de escrever é o que impede a órbita de
   * reescrever material sessenta vezes por segundo sem que nada tenha mudado.
   */
  function atualizarRegimeDeRelacoes(): void {
    const distancia = camera.position.distanceTo(orbit.target);
    // Selecionar um MOC **é** focar o domínio: o MOC é a âncora do território, e a
    // pergunta de quem o escolhe é "como este território se organiza", não "o que este
    // nó toca". Sem esta regra o estado de domínio era quase inalcançável — a
    // aproximação a uma âncora para a câmera a ~120 unidades, fora da banda de 94.
    const selecionadoEhMoc =
      mutable.selected !== null && slots.get(mutable.selected)?.kind === 'moc';
    const regime: RegimeDeRelacoes = selecionadoEhMoc
      ? 'intermediaria'
      : mutable.selected
        ? 'foco'
        : distancia > radius * BANDA_GLOBAL
          ? 'global'
          : 'intermediaria';
    if (regime === regimeAtual) return;
    regimeAtual = regime;

    // Visão global: só as pontes agregadas. Nenhuma relação nota→nota bruta aparece
    // fora de seleção ou de aproximação a um território.
    // Com um MOC escolhido, o território é o dele; sem seleção, o mais próximo do alvo.
    const dominioAtivo =
      regime !== 'intermediaria'
        ? null
        : selecionadoEhMoc
          ? (dominioDoNo.get(mutable.selected!) ?? null)
          : dominioEmFoco();
    escreverEspinhaDoDominio(dominioAtivo);
    espinha.visible = regime === 'intermediaria';
    (espinha.material as THREE.LineBasicMaterial).opacity = SPINE_OPACITY;
  }

  // --- interação ------------------------------------------------------------

  const raycaster = new THREE.Raycaster();
  const ponteiro = new THREE.Vector2();
  let pressionado: { x: number; y: number } | null = null;
  /** Última posição do cursor em NDC, resolvida no quadro e não no evento. */
  let sobrevoo: { x: number; y: number } | null = null;
  let sobrevooPendente = false;

  function paraNDC(clientX: number, clientY: number): { x: number; y: number } {
    const rect = renderer.domElement.getBoundingClientRect();
    return {
      x: ((clientX - rect.left) / rect.width) * 2 - 1,
      y: -((clientY - rect.top) / rect.height) * 2 + 1,
    };
  }

  /**
   * A entidade sob o cursor, seja ela do corpus ou da camada viva.
   *
   * Se o raio acerta as duas placas no mesmo anel, o painel vivo fica com o
   * clique: a nota, maior, cobria os dois painéis do observatório.
   */
  function alvoEm(ndc: { x: number; y: number }): {
    entityId: string;
    runtime: boolean;
  } | null {
    ponteiro.set(ndc.x, ndc.y);
    raycaster.setFromCamera(ponteiro, camera);
    const acertoOperacional = raycaster.intersectObjects(runtimeLayer.pickables(), false)[0];
    const acertoCorpus = raycaster.intersectObjects(corpos.pickTargets(), false)[0];
    const operacional = acertoOperacional
      ? runtimeLayer.selectionFor(acertoOperacional.object, acertoOperacional.instanceId)
      : null;
    const corpus = acertoCorpus
      ? corpos.entityFor(acertoCorpus.object, acertoCorpus.instanceId)
      : null;
    return escolherAlvoDoClique(
      corpus === null ? null : { entityId: corpus },
      operacional === null ? null : { entityId: operacional.runtimeNodeId },
    );
  }

  function onPointerDown(event: PointerEvent): void {
    markViewTouched();
    pressionado = { x: event.clientX, y: event.clientY };
  }

  function onPointerMove(event: PointerEvent): void {
    sobrevoo = paraNDC(event.clientX, event.clientY);
    sobrevooPendente = true;
  }

  function onPointerUp(event: PointerEvent): void {
    if (!pressionado) return;
    const arrastou = Math.hypot(event.clientX - pressionado.x, event.clientY - pressionado.y) > 4;
    pressionado = null;
    if (arrastou) return; // Arrastar é rotação; só clique parado seleciona.

    const ndc = paraNDC(event.clientX, event.clientY);
    const alvo = alvoEm(ndc);
    if (!alvo) {
      select(null); // Clique no vazio recolhe.
      return;
    }
    if (alvo.runtime) {
      abrirOperacional(alvo.entityId);
      return;
    }
    // Segundo clique no mesmo painel recolhe, como Esc e como o clique no vazio.
    select(alvo.entityId === mutable.selected ? null : alvo.entityId);
  }

  /**
   * Um painel da camada viva ligado a uma entidade do corpus.
   *
   * Ele não vira seleção do corpus por conta própria: quando declara vínculo, leva
   * ao nó ligado; quando não declara, apenas se anuncia. Atividade operacional não
   * se promove a conhecimento por ter sido clicada.
   */
  /**
   * Clicar num nó da camada viva seleciona **aquele nó**.
   *
   * Antes o clique pulava para `linkedEntityId` — a entidade do corpus que o evento
   * anota. A intenção era levar do evento ao conhecimento, mas o efeito era outro:
   * quem clicava num modelo ou numa tarefa via a seleção aparecer em outro painel, sem
   * nada explicando o salto. O vínculo continua existindo e continua sendo dito em voz
   * alta; ele deixou de sequestrar o clique.
   */
  /**
   * Abre um painel da camada viva, com **a mesma gramática do corpus**.
   *
   * Ela não era a mesma em duas coisas, e as duas apareciam ao clicar. O duplo clique
   * chamava esta função outra vez, e como ela alterna, a sequência clique-clique-duplo
   * selecionava, desmarcava e selecionava de novo — no corpus, duplo clique é
   * *recentrar*, nunca alternar. E a câmera vinha sempre, mesmo quando o painel já
   * estava em tamanho de leitura, tirando o usuário do lugar sem lhe dar nada.
   *
   * `recentrar` é o que separa os dois gestos: o clique escolhe, o duplo clique traz.
   */
  function abrirOperacional(runtimeNodeId: string, recentrar = false): void {
    const alvo = runtimeLayer.panelSelection(runtimeNodeId);
    if (!alvo) return;
    // Clicar num evento ao vivo **seleciona aquele evento**.
    //
    // Tirar o antigo salto para a entidade ligada corrigiu o clique que caía em outro
    // painel, mas deixou o clique sem efeito nenhum: o painel não abria e a narração
    // não aparecia. Selecionar aqui é o que faz o evento crescer para o nível de
    // leitura, exatamente como um nó do corpus.
    // O valor anterior é lido **antes** de limpar a seleção do corpus, que também zera
    // esta — sem isso o segundo clique no mesmo painel voltaria a abri-lo.
    const jaEstava = mutable.runtimeSelected === runtimeNodeId;
    select(null);
    // Recentrar nunca desmarca: o duplo clique traz a câmera para o que já está escolhido.
    mutable.runtimeSelected = jaEstava && !recentrar ? null : runtimeNodeId;
    runtimeLayer.setSelected(mutable.runtimeSelected);
    nivelRuntime.clear();
    // Mesma regra do corpus: o clique escolhe e o duplo traz a câmera. Aqui ela era
    // ainda mais imprevisível — `nivelRuntime.clear()` acima apaga o nível que a
    // condição consultava, então a leitura dava sempre "ilegível" e a câmera vinha em
    // todo clique. Duas nuvens, dois comportamentos, e nenhum deles pedido.
    if (recentrar) aproximarDoRuntime(mutable.runtimeSelected);
    else ajustarLimiteDoRuntime(mutable.runtimeSelected);
    desenharVizinhancaViva(mutable.runtimeSelected);
    anunciarEscolha(mutable.runtimeSelected, true);
    mutable.runtimeLinkedEntity = mutable.runtimeSelected ? alvo.linkedEntityId : null;
    aplicarEnfase();
    announce(
      alvo.linkedEntityId
        ? `${alvo.description} Ligado a ${alvo.linkedEntityId}.`
        : alvo.description,
    );
  }

  /**
   * Reconcilia a seleção viva depois de um quadro novo.
   *
   * `runtimeLayer.update` recria os objetos e zera a seleção **da camada**, mas o id
   * escolhido morava aqui em cima e sobrevivia ao quadro. O resultado era uma seleção
   * lógica sem contraparte visual: a placa perdia expansão e elevação, e `Enter` e
   * `Esc` continuavam agindo sobre ela como se estivesse destacada.
   *
   * A janela viva guarda os últimos eventos, então um evento selecionado pode
   * simplesmente sair dela. Quando sai, a seleção morre junto — inclusive o vínculo com
   * o corpus, que sem isso ficaria aceso apontando para um evento que não está mais em
   * cena.
   */
  function reconciliarSelecaoViva(): void {
    const escolhido = mutable.runtimeSelected;
    if (escolhido === null) return;
    const alvo = runtimeLayer.panelSelection(escolhido);
    if (alvo === null) {
      mutable.runtimeSelected = null;
      mutable.runtimeLinkedEntity = null;
      return;
    }
    runtimeLayer.setSelected(escolhido);
    mutable.runtimeLinkedEntity = alvo.linkedEntityId;
  }

  function setReducedMotion(reduced: boolean, report = true): void {
    mutable.reducedMotion = reduced;
    orbit.enableDamping = !reduced;
    if (report) {
      announce(reduced ? 'Movimento reduzido ativado.' : 'Movimento reduzido desativado.');
    }
  }

  /**
   * O que sobrou dos atalhos: voltar à visão global.
   *
   * `C` e `F` existiam para ligar camadas e relações. Com tudo em cena por padrão eles
   * passaram a alternar entre "como está" e "faltando coisa", que não é uma escolha que
   * valha uma tecla. `L` levava à legenda, que mora no painel de configuração, e `M`
   * reduzia movimento — o navegador já declara essa preferência, e respeitá-la sem
   * perguntar é melhor que oferecer um botão para repeti-la.
   */
  function toggle(controlId: string): void {
    if (controlId !== 'global') return;
    markViewTouched();
    select(null);
    fitToGraph();
    announce('Visão global restaurada, enquadrada no que está ocupado.');
  }

  /**
   * Deslocamento contínuo por `WASD`.
   *
   * Câmera e alvo andam juntos, o que preserva a direção de visada: `W` aproxima do que
   * se está olhando em vez de girar em torno dele. A órbita continua respondendo ao
   * mouse, e as duas coisas não brigam porque uma move o par inteiro e a outra move só
   * a câmera em torno do alvo.
   *
   * A velocidade é proporcional à distância do alvo. Um passo fixo seria rápido demais
   * dentro de um território e lento demais atravessando o atlas, e o usuário passaria a
   * gerenciar a própria velocidade — que é exatamente o tipo de complexidade que esta
   * navegação existe para não pedir.
   */
  const teclasDeMovimento = new Set<string>();
  /**
   * `W`/`S` frente e trás, `A`/`D` de lado.
   *
   * Passaram por vertical num ciclo intermediário, e não era isso: atravessar o espaço
   * é o que o teclado precisa fazer, e a roda do mouse resolve a aproximação fina de um
   * painel — as duas coisas se parecem só quando não se está indo a lugar nenhum.
   */
  const MOVIMENTO: Record<string, [number, number]> = {
    w: [0, 1],
    s: [0, -1],
    a: [-1, 0],
    d: [1, 0],
  };

  function aplicarMovimento(delta: number): void {
    if (teclasDeMovimento.size === 0) return;
    let frente = 0;
    let lado = 0;
    for (const tecla of teclasDeMovimento) {
      const eixo = MOVIMENTO[tecla];
      if (!eixo) continue;
      lado += eixo[0];
      frente += eixo[1];
    }
    if (frente === 0 && lado === 0) return;

    const paraAlvo = new THREE.Vector3().subVectors(orbit.target, camera.position);
    const distancia = paraAlvo.length() || 1;
    paraAlvo.normalize();
    const direita = new THREE.Vector3().crossVectors(paraAlvo, camera.up).normalize();

    const passo = Math.min(distancia, orbit.maxDistance) * VELOCIDADE_DE_VOO * delta;
    const deslocamento = new THREE.Vector3()
      .addScaledVector(paraAlvo, frente)
      .addScaledVector(direita, lado);
    if (deslocamento.lengthSq() === 0) return;
    deslocamento.normalize().multiplyScalar(passo);

    // Câmera e alvo andam **juntos**: a distância entre eles não muda, e por isso voar
    // nunca colapsa a órbita nem atravessa o que está sendo olhado. Aproximar de um
    // objeto é a roda do mouse; `WASD` é atravessar o espaço.
    camera.position.add(deslocamento);
    orbit.target.add(deslocamento);
    camera.updateMatrixWorld();
  }

  function onKeyDown(event: KeyboardEvent): void {
    // Antes de qualquer outra coisa: o que é digitado num campo pertence ao campo.
    // Sem isto, `WASD` e os atalhos de controle chamavam `preventDefault()` sobre a
    // tecla digitada no dock, e uma chave de API com `w`, `a`, `s` ou `d` não podia
    // sequer ser escrita.
    if (isEditableTarget(event.target)) return;
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    const tecla = event.key.toLowerCase();
    if (tecla in MOVIMENTO) {
      event.preventDefault();
      markViewTouched();
      teclasDeMovimento.add(tecla);
      return;
    }
    const control = CONTROLS.find((item) => item.shortcut === tecla);
    if (control) {
      event.preventDefault();
      markViewTouched();
      toggle(control.id);
      return;
    }
    const selectionAction = selectionKeyboardAction(
      event.key,
      mutable.selected !== null,
      mutable.runtimeSelected !== null,
    );
    if (selectionAction === 'clear-selection') {
      markViewTouched();
      select(null);
      return;
    }
    if (selectionAction === 'focus-runtime' && mutable.runtimeSelected) {
      markViewTouched();
      abrirOperacional(mutable.runtimeSelected, true);
      return;
    }
    if (selectionAction === 'focus-corpus' && mutable.selected) {
      markViewTouched();
      focusOn(mutable.selected);
    }
  }

  function onKeyUp(event: KeyboardEvent): void {
    // Este **não** filtra por campo, de propósito: soltar uma tecla sempre a solta.
    // Uma tecla pressionada na cena e solta depois de o foco cair num campo ficaria
    // presa no conjunto, e a câmera andaria sozinha até o próximo `blur`.
    teclasDeMovimento.delete(event.key.toLowerCase());
  }

  function onBlur(): void {
    // Sem isto uma tecla pressionada durante a troca de janela ficaria presa, e a
    // câmera continuaria andando sozinha depois de voltar.
    teclasDeMovimento.clear();
  }

  function onDoubleClick(event: MouseEvent): void {
    const alvo = alvoEm(paraNDC(event.clientX, event.clientY));
    if (!alvo) return;
    if (alvo.runtime) abrirOperacional(alvo.entityId, true);
    else focusOn(alvo.entityId);
  }

  renderer.domElement.addEventListener('pointerdown', onPointerDown);
  renderer.domElement.addEventListener('pointermove', onPointerMove);
  renderer.domElement.addEventListener('pointerup', onPointerUp);
  renderer.domElement.addEventListener('dblclick', onDoubleClick);
  // Captura, para chegar antes do controle de órbita registrado no mesmo elemento.
  renderer.domElement.addEventListener('wheel', onWheel, { capture: true, passive: false });
  orbit.addEventListener('start', markViewTouched);
  window.addEventListener('keydown', onKeyDown);
  window.addEventListener('keyup', onKeyUp);
  window.addEventListener('blur', onBlur);

  const prefereMenosMovimento = window.matchMedia('(prefers-reduced-motion: reduce)');
  const onMotionPreference = (event: MediaQueryListEvent): void => {
    setReducedMotion(event.matches);
  };
  prefereMenosMovimento.addEventListener('change', onMotionPreference);
  if (prefereMenosMovimento.matches) setReducedMotion(true, false);

  function onResize(): void {
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
    // A fita calcula a espessura em pixels a partir daqui: sem atualizar, redimensionar
    // a janela mudaria a grossura dos links sem que ninguém tivesse selecionado nada.
    materialFocal.resolution.set(container.clientWidth, container.clientHeight);
  }
  window.addEventListener('resize', onResize);

  // --- LOD e laço ------------------------------------------------------------

  const ordenadosPorPrioridade = [...slots.values()].sort(
    (a, b) =>
      a.node.visual.lodClass - b.node.visual.lodClass ||
      b.node.visual.labelPriority - a.node.visual.labelPriority,
  );

  /**
   * A identidade do descritor, virada número estável.
   *
   * O cache de layout do texto tem por chave entidade, nível, área útil e rolagem — e
   * nenhum desses campos muda quando muda **o conteúdo**. Na placa viva é exatamente o
   * que acontece: o raciocínio do modelo troca de frase na mesma placa, no mesmo nível
   * e no mesmo tamanho, e a leitura ficava congelada na primeira frase que chegou.
   *
   * O descritor de um painel vivo é criado uma vez por reconstrução da camada e
   * preservado entre elas, então a identidade dele é a revisão que faltava — sem
   * pagar hash de conteúdo por quadro, que foi o custo que este cache existe para
   * evitar. O corpus não precisa: os descritores dele só mudam quando a projeção
   * inteira é recarregada.
   */
  const revisaoDoDescritor = new WeakMap<PanelDescriptor, string>();
  let descritoresVistos = 0;
  function revisaoDe(descriptor: PanelDescriptor): string {
    const conhecida = revisaoDoDescritor.get(descriptor);
    if (conhecida !== undefined) return conhecida;
    descritoresVistos += 1;
    const nova = `d${descritoresVistos}`;
    revisaoDoDescritor.set(descriptor, nova);
    return nova;
  }

  /**
   * Monta o único quadro de texto: corpus e runtime disputam o mesmo teto.
   *
   * A ordem é fixa — candidatos das duas origens, uma alocação, um `update`. O
   * renderizador materializa a decisão; ele não consulta projeção, não descobre LOD
   * e não deriva conteúdo do nó.
   */
  function atualizarTextoDosPaineis(alturaViewport: number): void {
    const candidatos: TextCandidate[] = [];
    const descritores = new Map<string, PanelDescriptor>();
    const transformacoes = new Map<string, PanelTransform>();
    const linhas = new Map<string, ReturnType<typeof linesUpTo>>();
    const versaoDasLinhas = new Map<string, string>();
    const niveis = new Map<string, LodLevel>();
    const larguraViewport = renderer.domElement.clientWidth || 1;
    const quaternion = {
      x: camera.quaternion.x,
      y: camera.quaternion.y,
      z: camera.quaternion.z,
      w: camera.quaternion.w,
    };

    const inscrever = (
      entityId: string,
      descriptor: PanelDescriptor,
      posicao: THREE.Vector3,
      extent: { width: number; height: number },
      nivel: LodLevel,
      origem: 'corpus' | 'runtime',
    ): void => {
      // Painel com face desenhada fora da cena não recebe texto aqui: a superfície é
      // uma só, e alocar vaga para uma leitura que a face cobre tiraria essa vaga de
      // um painel que a tela de fato mostra.
      if (entityId === painelComFace) return;
      const distancia = camera.position.distanceTo(posicao);
      const selecionado = mutable.selected === entityId;
      // Fora do enquadramento não há o que ler: gastar vaga com um painel que a
      // tela não mostra é tirá-la de outro que ela mostra. O selecionado passa de
      // qualquer forma — a leitura dele é o motivo de a câmera estar onde está.
      projetado.copy(posicao).project(camera);
      const enquadrado =
        Math.abs(projetado.x) <= 1.25 && Math.abs(projetado.y) <= 1.25 && projetado.z < 1;
      if (!enquadrado && !selecionado) return;

      candidatos.push({
        entityId,
        lod: nivel,
        selected: selecionado,
        hovered: mutable.hovered === entityId,
        projectedSize: projectedPixels(
          Math.max(extent.width, extent.height) / 2,
          distancia,
          camera.fov,
          alturaViewport,
        ),
        distance: distancia,
        source: origem,
        // A caixa que o painel ocupa na tela, em pixels. É com ela que o pool recusa
        // rótulo novo que cairia por cima de um já priorizado.
        screen: {
          x: ((projetado.x + 1) / 2) * larguraViewport,
          y: ((1 - projetado.y) / 2) * alturaViewport,
          width: projectedPixels(extent.width / 2, distancia, camera.fov, alturaViewport),
          height: projectedPixels(extent.height / 2, distancia, camera.fov, alturaViewport),
        },
      });
      niveis.set(entityId, nivel);
      descritores.set(entityId, descriptor);
      // Mesma posição e mesmo quaternion das placas: nada é decomposto de novo, e a
      // extensão é a **efetiva**, para o texto acompanhar a placa que expandiu.
      transformacoes.set(entityId, {
        position: { x: posicao.x, y: posicao.y, z: posicao.z },
        quaternion,
        extent,
      });
      // **Aberto, o painel mostra o documento; em qualquer outro degrau, o descritor.**
      //
      // Não é acréscimo, é substituição, e por uma razão de leitura: as frases derivadas
      // já dizem o que a nota é — status, contagem de afirmações, abertura do corpo — e
      // todas elas reaparecem, ditas melhor, dentro do próprio documento. Somadas, o
      // painel abria repetindo a mesma abertura duas vezes, uma resumida e outra íntegra.
      //
      // O cabeçalho não é afetado: ele vem de `descriptor.category`, e não das linhas.
      const documento = nivel === 'expanded' ? documentoPorEntidade.get(entityId) : undefined;
      if (documento === undefined) {
        linhas.set(entityId, linesUpTo(descriptor, nivel));
        if (origem === 'runtime') versaoDasLinhas.set(entityId, revisaoDe(descriptor));
      } else {
        linhas.set(entityId, documento);
        versaoDasLinhas.set(entityId, 'documento');
      }
    };

    for (const slot of slots.values()) {
      const medida = corpos.extentFor(slot.node.id);
      // A posição desenhada, não a assentada: o painel selecionado sobe, e o texto
      // que ficasse na cota do layout desapareceria atrás da própria placa.
      const onde = corpos.renderPositionFor(slot.node.id);
      const nivel = nivelDe(slot);
      if (!medida || !onde || nivel === undefined) continue;
      const nodeVivo = withLiveThought(slot.node, pensamentosVivos);
      const descriptor =
        nodeVivo === slot.node
          ? corpos.descriptorFor(slot.node.id)
          : describePanel(nodeVivo);
      if (!descriptor) continue;
      inscrever(slot.node.id, descriptor, onde, medida, nivel, 'corpus');
      if (nodeVivo !== slot.node && nodeVivo.operational?.narration) {
        versaoDasLinhas.set(slot.node.id, nodeVivo.operational.narration);
      }
    }

    for (const painel of runtimeLayer.panels()) {
      const distancia = camera.position.distanceTo(painel.position);
      const pixels = projectedPixels(
        Math.max(painel.extent.width, painel.extent.height) / 2,
        distancia,
        camera.fov,
        alturaViewport,
      );
      // Escolhido lê inteiro, como no corpus: a distância decide o resto.
      const nivel =
        mutable.runtimeSelected === painel.entityId
          ? 'expanded'
          : levelWithHysteresis(pixels, nivelRuntime.get(painel.entityId));
      nivelRuntime.set(painel.entityId, nivel);
      inscrever(painel.entityId, painel.descriptor, painel.position, painel.extent, nivel, 'runtime');
    }

    textoDosPaineis.update({
      scroll: rolagemPorEntidade,
      allocations: vagasDeTexto.allocate(candidatos),
      sources: new Map(candidatos.map((c) => [c.entityId, c.source])),
      descriptors: descritores,
      transforms: transformacoes,
      lines: linhas,
      lineRevision: versaoDasLinhas,
      levels: niveis,
      // Quem está na frente é o escolhido de **qualquer** camada. Com só o corpus aqui,
      // o texto de um painel vivo selecionado continuava com teste de profundidade
      // ligado, e a própria placa expandida — opaca e escrevendo profundidade — ganhava
      // dele: a leitura saía lavada, escondida atrás do que deveria mostrá-la.
      front: mutable.selected ?? mutable.runtimeSelected,
    });
  }

  let mudancasDeLod = 0;

  /** Resolve o sobrevoo uma vez por quadro, e só quando o cursor de fato andou. */
  function atualizarSobrevoo(): void {
    if (!sobrevooPendente || !sobrevoo) return;
    sobrevooPendente = false;
    const alvo = alvoEm(sobrevoo);
    const novo = alvo && !alvo.runtime ? alvo.entityId : null;
    if (novo === mutable.hovered) return;
    mutable.hovered = novo;
    aplicarEnfase();
  }

  function atualizarLod(): void {
    // A placa acompanha a câmera antes de qualquer medida de LOD: o tamanho
    // projetado de um quad visto de perfil não descreve o que se lê.
    corpos.orient(camera.quaternion);
    // O nome da nuvem é billboard como o painel: ele nomeia um volume, e girar com a
    // câmera é o que o mantém legível de qualquer aproximação.
    nomesDasNuvens.orient(camera.quaternion);
    runtimeLayer.updateView(camera);
    const altura = renderer.domElement.clientHeight || 1;
    // O tamanho aparente do nome e a disputa entre nomes dependem da câmera **e** da
    // altura da janela, e por isso vêm depois dela.
    nomesDasNuvens.updateView(camera, altura);

    for (const slot of ordenadosPorPrioridade) {
      const distanciaCamera = camera.position.distanceTo(slot.position);
      const medida = corpos.extentFor(slot.node.id);
      const raio = medida
        ? Math.max(medida.width, medida.height) / 2
        : BASE_RADIUS[slot.kind];
      const pixels = projectedPixels(raio, distanciaCamera, camera.fov, altura);
      const level = levelWithHysteresis(pixels, slot.level);
      if (level !== slot.level) {
        mudancasDeLod += 1;
        slot.level = level;
        atualizarCorpo(slot.node.id, mutable.selected === slot.node.id);
      }
    }

    atualizarSobrevoo();
    atualizarRegimeDeRelacoes();
    atualizarTextoDosPaineis(altura);
    // O limite de rolagem só é conhecido depois de compor o texto: ele depende da
    // altura do bloco, que depende da largura útil, que depende da extensão da placa.
    for (const extensao of textoDosPaineis.scrollExtents()) {
      rolagemMaxima.set(extensao.entityId, extensao.maxScroll);
    }
    posicionarHalo();
  }

  /**
   * A roda: do painel aberto quando o ponteiro está **nele**, da câmera em todo o resto.
   *
   * Havia uma condição só — existir painel selecionado com rolagem — e ela era ampla
   * demais em dois sentidos. Primeiro, o ponteiro não contava: bastava ter algo aberto
   * para a roda deixar de aproximar, em qualquer canto da tela. Segundo, a devolução era
   * tardia: como o consumo só cessava no fim do conteúdo, sair de um documento longo
   * exigia rolá-lo inteiro antes de o mundo voltar a responder. Era essa a sensação de
   * "primeiro termino de rolar o painel, e só depois volto a dar zoom".
   *
   * A regra passa a ser a que se descreve numa linha: **ponteiro sobre a placa aberta e
   * ainda há o que revelar naquela direção** — a roda é do painel; senão, é da câmera, no
   * mesmo evento. Não há tempo de espera, nem carência, nem estado residual entre as
   * duas: cada evento decide sozinho, e por isso a devolução é imediata em qualquer
   * ponto do documento.
   */
  function onWheel(event: WheelEvent): void {
    markViewTouched();
    // Um painel aberto por vez, em qualquer das duas camadas.
    const aberto = mutable.selected ?? mutable.runtimeSelected;
    if (!aberto) return;
    const limite = rolagemMaxima.get(aberto) ?? 0;
    const atual = rolagemPorEntidade.get(aberto) ?? 0;
    const dono = wheelOwner({
      deltaY: event.deltaY,
      scrollOffset: atual,
      maxScroll: limite,
      // O raio vai só contra a placa aberta. Perguntar pelo primeiro acerto da cena
      // devolveria o vizinho mais próximo: a placa expandida ignora profundidade e
      // desenha por cima, mas o raio continua ordenando por distância, e quem apontasse
      // para o meio do painel aberto receberia o nome do painel que ele está cobrindo.
      //
      // O raio só é lançado quando o resto da regra já autorizou — é a parte cara da
      // decisão, e as outras respondem sozinhas na maioria dos eventos.
      pointerOverPanel: limite > 0 && event.deltaY !== 0 && ponteiroSobreOPainelAberto(event),
    });
    if (dono === 'camera') return;
    const passo = event.deltaY * PASSO_DE_ROLAGEM;
    rolagemPorEntidade.set(aberto, Math.min(Math.max(atual + passo, 0), limite));
    event.preventDefault();
    event.stopImmediatePropagation();
  }

  function ponteiroSobreOPainelAberto(event: WheelEvent): boolean {
    const placa = mutable.selected ? corpos.expandedTarget() : runtimeLayer.expandedTarget();
    if (!placa) return false;
    const ndc = paraNDC(event.clientX, event.clientY);
    ponteiro.set(ndc.x, ndc.y);
    raycaster.setFromCamera(ponteiro, camera);
    return raycaster.intersectObject(placa, false).length > 0;
  }

  const recuo = new THREE.Vector3();
  const projetado = new THREE.Vector3();

  /** O halo acompanha a placa que marca: mesma extensão efetiva, mesma orientação. */
  /**
   * Enquadra um painel da camada viva, e ajusta o limite de aproximação a ele.
   *
   * Reaproveita a mesma conta de `aproximarDe`, porque a pergunta é a mesma: a que
   * distância esta placa ocupa a fatia de leitura da janela.
   */
  /**
   * O piso de aproximação de um painel vivo, sem mover a câmera.
   *
   * O corpus separa as duas coisas — `ajustarLimiteDeAproximacao` diz até onde a roda
   * pode chegar, e `aproximarDe` é que leva a câmera. Aqui elas vinham juntas, então
   * escolher um painel já legível ainda assim reposicionava a câmera.
   */
  function ajustarLimiteDoRuntime(runtimeNodeId: string | null): void {
    if (!runtimeNodeId) {
      ajustarLimiteDeAproximacao(null);
      return;
    }
    const painel = runtimeLayer.panels().find((item) => item.entityId === runtimeNodeId);
    if (!painel) return;
    const distancia = distanciaDeLeitura(Math.max(painel.extent.width, painel.extent.height));
    orbit.minDistance = Math.max(LIMITE_DE_APROXIMACAO_MINIMO, distancia / 2.4);
  }

  function aproximarDoRuntime(runtimeNodeId: string | null): void {
    if (!runtimeNodeId) {
      ajustarLimiteDeAproximacao(null);
      return;
    }
    const painel = runtimeLayer.panels().find((item) => item.entityId === runtimeNodeId);
    if (!painel) return;
    // `extent` já vem **efetiva** de `extentFor`, que aplica a expansão. Multiplicar por
    // ela outra vez parava a câmera a mais que o dobro da distância de leitura, e era por
    // isso que o painel vivo continuava ilegível depois de selecionado.
    const alcance = Math.max(painel.extent.width, painel.extent.height);
    const distancia = distanciaDeLeitura(alcance);
    const direcao = new THREE.Vector3().subVectors(camera.position, orbit.target).normalize();
    if (direcao.lengthSq() < 1e-9) direcao.set(0, -1, 0);
    orbit.target.copy(painel.position);
    camera.position.copy(orbit.target).addScaledVector(direcao, distancia);
    camera.updateMatrixWorld();
    orbit.minDistance = Math.max(LIMITE_DE_APROXIMACAO_MINIMO, distancia / 2.4);
  }

  function posicionarHalo(): void {
    const id = mutable.selected;
    if (!id) {
      // Sem nó do corpus escolhido, o halo ainda pode pertencer a um evento ao vivo.
      const vivo = mutable.runtimeSelected;
      const painel = vivo
        ? runtimeLayer.panels().find((item) => item.entityId === vivo)
        : undefined;
      if (!painel) {
        halo.visible = false;
        return;
      }
      const silhuetaViva = panelShapeGeometry(painel.descriptor.shape);
      if (halo.geometry !== silhuetaViva) halo.geometry = silhuetaViva;
      halo.position
        .copy(painel.position)
        .addScaledVector(recuo.subVectors(painel.position, camera.position).normalize(), 0.12);
      halo.quaternion.copy(camera.quaternion);
      // A extensão já vem **efetiva** de `extentFor`, que aplica a expansão. O fator
      // repetido aqui fazia o halo do painel vivo sair 2,2 vezes maior que a placa — o
      // retângulo pálido e desproporcional atrás dela.
      halo.scale.set(painel.extent.width * 1.06, painel.extent.height * 1.06, 1);
      const materialVivo = halo.material as THREE.MeshBasicMaterial;
      materialVivo.opacity = mutable.reducedMotion
        ? HALO_OPACITY
        : HALO_OPACITY + Math.sin(relogioDoHalo * PULSO_DO_HALO) * AMPLITUDE_DO_HALO;
      halo.visible = true;
      return;
    }
    const medida = corpos.extentFor(id);
    const onde = corpos.renderPositionFor(id);
    const descritor = corpos.descriptorFor(id);
    if (!medida || !onde || !descritor) {
      halo.visible = false;
      return;
    }
    const silhueta = panelShapeGeometry(descritor.shape);
    if (halo.geometry !== silhueta) halo.geometry = silhueta;
    // Um passo para trás ao longo da visada. Coplanares, halo e placa disputariam o
    // mesmo valor de profundidade e a borda cintilaria conforme a câmera anda.
    halo.position
      .copy(onde)
      .addScaledVector(recuo.subVectors(onde, camera.position).normalize(), 0.12);
    halo.quaternion.copy(camera.quaternion);
    halo.scale.set(medida.width * 1.06, medida.height * 1.06, 1);
    // Uma respiração lenta, e não um pisca-pisca: o painel escolhido fica **vivo** sem
    // disputar a leitura do que está escrito nele. Sob movimento reduzido a luz fica
    // parada no valor médio, porque quem pediu menos movimento não pediu menos marca.
    const material = halo.material as THREE.MeshBasicMaterial;
    material.opacity = mutable.reducedMotion
      ? HALO_OPACITY
      : HALO_OPACITY + Math.sin(relogioDoHalo * PULSO_DO_HALO) * AMPLITUDE_DO_HALO;
    halo.visible = true;
  }

  let frame = 0;
  let instanteAnterior = 0;
  /** Tempo acumulado em segundos, só para a respiração do halo. */
  /**
   * As execuções que o fluxo ao vivo diz estarem acontecendo **agora**.
   *
   * O observatório guarda execuções concluídas, e nada nele distinguia uma que acabou
   * ontem de uma rodando neste instante. A camada viva recompõe o ciclo de cada painel:
   * ele só respira entre a abertura e o fechamento do quórum ou da promoção.
   */
  const paineisVivos = new Set<string>();
  const nosDaExecucao = new Map<string, string[]>();
  for (const node of projection.nodes) {
    const panelId = node.operational?.panelId;
    if (panelId === undefined) continue;
    const lista = nosDaExecucao.get(panelId);
    if (lista) lista.push(node.id);
    else nosDaExecucao.set(panelId, [node.id]);
  }
  let atividadeAplicada = new Set<string>();
  let atividadeConfiavel = false;

  function registrarAtividade(): void {
    paineisVivos.clear();
    if (!atividadeConfiavel) return;
    for (const panelId of runtimeLayer.activePanelIds()) paineisVivos.add(panelId);
  }

  /**
   * O pulso em si, um valor por quadro.
   *
   * Contínuo, e não alternado: piscar lê como defeito de renderização, e o que se quer
   * dizer é "isto respira". Sem movimento, a preferência do sistema manda e o painel
   * fica aceso num valor fixo — a informação sobrevive, a animação não.
   */
  function pulsarAtividade(): void {
    const vivos = new Set<string>();
    for (const panelId of paineisVivos) {
      for (const id of nosDaExecucao.get(panelId) ?? []) vivos.add(id);
    }
    const intensidade = mutable.reducedMotion
      ? 0.7
      : 0.45 + 0.55 * (0.5 + 0.5 * Math.sin(relogioDoHalo * 2.4));
    for (const id of vivos) corpos.setActivity(id, intensidade);
    // Quem saiu do fluxo apaga uma vez só, e não a cada quadro.
    for (const id of atividadeAplicada) if (!vivos.has(id)) corpos.setActivity(id, 0);
    atividadeAplicada = vivos;
    // A nuvem viva pulsa pelo mesmo relógio, e por conta própria decide o que nela está
    // acontecendo: ela é a única que sabe qual modelo tem chamada aberta. O relógio vai
    // junto porque o fluxo das arestas **anda**: ele diz para onde a informação vai, e
    // direção sem deslocamento não é direção.
    runtimeLayer.pulse(intensidade, relogioDoHalo, !mutable.reducedMotion);
  }

  let relogioDoHalo = 0;
  function animate(agora = 0): void {
    frame = requestAnimationFrame(animate);
    // Delta em segundos, limitado: uma aba que volta do segundo plano entrega um salto
    // de vários segundos, e sem o teto a câmera atravessaria o atlas de uma vez.
    const delta = instanteAnterior === 0 ? 0 : Math.min((agora - instanteAnterior) / 1000, 0.05);
    instanteAnterior = agora;
    relogioDoHalo += delta;
    pulsarAtividade();
    engrossarFoco(delta);
    aplicarMovimento(delta);
    if (runtimeLayer.advance(delta, mutable.reducedMotion)) {
      recolocarNomes();
      if (mutable.runtimeSelected !== null) desenharVizinhancaViva(mutable.runtimeSelected);
    }
    orbit.update();
    atualizarLod();
    renderer.render(scene, camera);
  }
  /**
   * Os nomes das nuvens.
   *
   * As quatro populações moram em lugares distintos do mundo e nada dizia qual era qual:
   * a única forma de descobrir era aproximar até ler um painel, o que obriga a perder a
   * visão de conjunto para obter a informação que orienta a visão de conjunto.
   */
  const nomesDasNuvens = createCloudTitles();
  scene.add(nomesDasNuvens.group);

  function recolocarNomes(): void {
    const grupos: Record<CloudKey, THREE.Vector3[]> = {
      corpus: [],
      operacional: [],
      modelos: [],
      provedores: [],
      trabalhadores: [],
      vivo: [],
    };
    for (const slot of slots.values()) {
      const chave: CloudKey =
        slot.node.layer === 'epistemic'
          ? 'corpus'
          : slot.node.domainId === MODEL_DOMAIN || slot.node.domainId === PROVIDER_DOMAIN
            ? 'modelos'
            : slot.node.domainId === WORKER_DOMAIN
                ? 'trabalhadores'
                : 'operacional';
      grupos[chave].push(slot.position);
    }
    for (const painel of runtimeLayer.panels()) grupos.vivo.push(painel.position);

    const nuvens: CloudTitle[] = [];
    const chaves: CloudKey[] = [
      'corpus',
      'operacional',
      'modelos',
      'trabalhadores',
      'vivo',
    ];
    for (const chave of chaves) {
      const pontos = grupos[chave] ?? [];
      if (pontos.length === 0) continue;
      // **Centro perceptivo, não centro de massa.**
      //
      // A média é puxada por quem está longe: a deliberação é duas populações — a casca
      // das execuções e o anel das que se ancoraram no corpus, do outro lado da cena —, e
      // o centro de massa das duas cai no vazio entre elas. A mediana por eixo fica onde a
      // nuvem de fato está, que é onde quem olha procura o nome dela.
      const mediana = (eixo: 'x' | 'y' | 'z'): number => {
        const valores = pontos.map((ponto) => ponto[eixo]).sort((a, b) => a - b);
        return valores[Math.floor(valores.length / 2)] ?? 0;
      };
      const centro = new THREE.Vector3(mediana('x'), mediana('y'), mediana('z'));
      // Raio pelo **percentil**, e não pelo máximo.
      //
      // A deliberação é duas populações: a casca das execuções, junta, e o anel das que
      // se ancoraram no corpus, do outro lado da cena. O máximo media a distância entre
      // as duas — 456 unidades — e o nome saía com o corpo e a altura de uma nuvem que
      // não existe. O percentil descreve onde a nuvem de fato está.
      const distancias = pontos.map((ponto) => ponto.distanceTo(centro)).sort((a, b) => a - b);
      const raio = Math.max(distancias[Math.floor(distancias.length * 0.75)] ?? 1, 1);
      nuvens.push({ key: chave, center: centro, radius: raio });
    }
    nomesDasNuvens.place(nuvens);
  }
  recolocarNomes();

  // Todas as populações pertencem à composição inicial; distância, LOD e seleção
  // controlam a leitura sem manter um seletor de camada invisível ao usuário.
  animate();

  const caixaDeInspecao = new THREE.Box3();

  return {
    cameraPose() {
      return {
        position: [camera.position.x, camera.position.y, camera.position.z],
        target: [orbit.target.x, orbit.target.y, orbit.target.z],
        distance: camera.position.distanceTo(orbit.target),
        minDistance: orbit.minDistance,
        fov: camera.fov,
      };
    },
    inspect() {
      const saida: SceneObjectInfo[] = [];
      scene.traverse((objeto) => {
        const malha = objeto as THREE.Mesh & { count?: number };
        if (!malha.geometry) return;
        let visivel = objeto.visible;
        for (let pai = objeto.parent; pai && visivel; pai = pai.parent) visivel = pai.visible;
        let caixa: SceneObjectInfo['worldBox'] = null;
        try {
          caixaDeInspecao.setFromObject(objeto);
          if (!caixaDeInspecao.isEmpty()) {
            caixa = {
              min: [caixaDeInspecao.min.x, caixaDeInspecao.min.y, caixaDeInspecao.min.z],
              max: [caixaDeInspecao.max.x, caixaDeInspecao.max.y, caixaDeInspecao.max.z],
            };
          }
        } catch {
          caixa = null;
        }
        saida.push({
          name: objeto.name || objeto.type,
          type: objeto.type,
          visible: visivel,
          instances: typeof malha.count === 'number' ? malha.count : null,
          worldBox: caixa,
        });
      });
      return saida;
    },
    state: mutable,
    select,
    toggle,
    focusOn,
    focusRuntime(id) {
      markViewTouched();
      abrirOperacional(id, true);
    },
    setRuntimeActivityEnabled(enabled) {
      atividadeConfiavel = enabled;
      runtimeLayer.setActivityEnabled(enabled);
      registrarAtividade();
    },
    refreshRuntimeActivity(now = Date.now()) {
      runtimeLayer.refreshActivity(now);
      registrarAtividade();
    },
    legendText: () => construirLegenda(projection),
    onSelectionChange(listener) {
      aoEscolher = listener;
    },
    setPanelFace(entityId) {
      if (painelComFace === entityId) return;
      painelComFace = entityId;
      // O texto do painel sai do quadro no mesmo instante em que a face entra. Sem
      // isto os dois desenhariam a mesma superfície, e a placa mostraria a leitura
      // antiga por baixo dos campos.
      atualizarLod();
    },
    panelFaceRect: faceDoPainel,
    panelLines(entityId) {
      const slot = slots.get(entityId);
      const descriptor = slot
        ? describePanel(withLiveThought(slot.node, pensamentosVivos))
        : (corpos.descriptorFor(entityId) ??
          runtimeLayer.panels().find((painel) => painel.entityId === entityId)?.descriptor ??
          null);
      if (!descriptor) return [];
      // O documento buscado tem precedência sobre as frases derivadas, pela mesma razão
      // que tem na placa: as duas dizem a mesma coisa, e a íntegra diz melhor.
      const documento = documentoPorEntidade.get(entityId);
      const linhas = documento ?? linesUpTo(descriptor, 'expanded');
      // Categoria e rótulo curto saem: quem desenha a face já os põe no cabeçalho, e
      // repeti-los no corpo gastava duas linhas para dizer duas vezes a mesma coisa —
      // numa superfície que mede duzentos pixels de altura, é o que faz o resto
      // transbordar.
      // A categoria sai: quem desenha a face já a tem no descritor, e repeti-la no
      // corpo gasta uma linha para dizer o que o cabeçalho diz — numa superfície que
      // mede duzentos pixels de altura, é o que faz o resto transbordar.
      return linhas
        .map((linha) => linha.text)
        .filter((texto) => texto !== descriptor.category);
    },
    fitToGraph,
    updateCognition(frames) {
      pensamentosVivos = selectThoughts(frames);
      runtimeLayer.updateCognition(frames);
      registrarAtividade();
      // O texto da placa é inscrito aqui dentro, e só aqui. Sem esta chamada a camada
      // reconstruía os corpos com a frase nova e a leitura continuava a antiga: numa
      // cena parada, nada mais convoca o LOD, e o raciocínio ficava congelado no
      // primeiro quadro que chegou. Medido em captura — o teste passava dos dois jeitos.
      atualizarLod();
    },
    syncWorkers(workers) {
      runtimeLayer.syncWorkers(workers);
    },

    workerPoses() {
      return runtimeLayer.workerPoses();
    },

    setPositions(novas) {
      let mexeu = false;
      for (const [id, ponto] of novas) {
        const atual = desenhadas.get(id);
        if (atual && atual.x === ponto.x && atual.y === ponto.y && atual.z === ponto.z) continue;
        desenhadas.set(id, { ...ponto });
        corpos.moveTo(id, ponto);
        mexeu = true;
      }
      if (!mexeu) return;
      reconstruirFamilias(desenhadas);
      if (mutable.selected !== null) desenharVizinhanca(mutable.selected);
      recolocarNomes();
    },

    updateRuntime(snapshot) {
      runtimeLayer.update(snapshot);
      nivelRuntime.clear();
      // A nuvem viva muda de tamanho a cada evento, e o nome dela precisa acompanhar.
      recolocarNomes();
      registrarAtividade();
      reconciliarSelecaoViva();
      desenharVizinhancaViva(mutable.runtimeSelected);
      aplicarEnfase();
      const framing = initialRuntimeFramingAction({
        resolved: initialRuntimeFramingResolved,
        hasRuntimePanels: runtimeLayer.panels().length > 0,
        runtimeVisible: true,
        userInteracted: viewTouchedByUser,
        hasSelection: mutable.selected !== null || mutable.runtimeSelected !== null,
      });
      if (framing !== 'wait') initialRuntimeFramingResolved = true;
      if (framing === 'fit') fitToGraph();
      atualizarLod();
    },
    textMetrics() {
      // Telemetria local do frontend. Não vai para a projeção nem para o corpus.
      //
      // As três populações são contadas separadamente: enquanto o fluxo ao vivo era
      // somado ao corpus, a carga visual real da cena não aparecia em número nenhum.
      return {
        ...textoDosPaineis.metrics(),
        lodChanges: mudancasDeLod,
        corpusNodes: idsPorCamada.corpus.size,
        observatoryNodes: idsPorCamada.operacional.size,
        liveNodes: runtimeLayer.panels().length,
      };
    },
    captureAt(width, height) {
      const anterior = renderer.getSize(new THREE.Vector2());
      const proporcaoAnterior = camera.aspect;
      renderer.setPixelRatio(1);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      atualizarLod();
      renderer.render(scene, camera);
      const png = renderer.domElement.toDataURL('image/png');
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setSize(anterior.x, anterior.y, false);
      camera.aspect = proporcaoAnterior;
      camera.updateProjectionMatrix();
      return png;
    },
    advance(deltaSeconds) {
      const passo = Math.max(0, Math.min(deltaSeconds, 0.05));
      relogioDoHalo += passo;
      // O mesmo trabalho por quadro do laço normal, incluindo a ênfase, o pulso e o
      // ambiente: uma aba que não compõe é justamente onde a cena é medida, e um passo
      // que pula a transição mediria um estado que a tela nunca mostra.
      pulsarAtividade();
      engrossarFoco(passo);
      aplicarMovimento(passo);
      if (runtimeLayer.advance(passo, mutable.reducedMotion)) {
        recolocarNomes();
        if (mutable.runtimeSelected !== null) desenharVizinhancaViva(mutable.runtimeSelected);
      }
      orbit.update();
      atualizarLod();
      renderer.render(scene, camera);
    },
    renderOnce() {
      atualizarLod();
      renderer.info.reset();
      renderer.render(scene, camera);
      return {
        drawCalls: renderer.info.render.calls,
        triangles: renderer.info.render.triangles,
        objects: scene.children.length,
      };
    },
    dispose() {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', onResize);
      // `keyup` e `blur` ficavam para trás: três listeners registrados no `window` e um
      // só removido. Cada recriação da cena deixava dois órfãos segurando o closure
      // inteiro do atlas anterior — a mesma família de vazamento que F-15 tinha no
      // texto, e que só aparece em quem recria a cena, como o harness de captura.
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keyup', onKeyUp);
      window.removeEventListener('blur', onBlur);
      prefereMenosMovimento.removeEventListener('change', onMotionPreference);
      renderer.domElement.removeEventListener('pointerdown', onPointerDown);
      renderer.domElement.removeEventListener('pointermove', onPointerMove);
      renderer.domElement.removeEventListener('pointerup', onPointerUp);
      renderer.domElement.removeEventListener('dblclick', onDoubleClick);
      renderer.domElement.removeEventListener('wheel', onWheel, { capture: true });
      orbit.removeEventListener('start', markViewTouched);
      orbit.dispose();
      runtimeLayer.dispose();
      ambiente.dispose();
      corpos.dispose();
      textoDosPaineis.dispose();
      nomesDasNuvens.dispose();
      // As famílias são reconstruídas a cada movimento, então o que existe agora é o
      // que está nos grupos — guardar a lista da construção inicial vazaria tudo que
      // veio depois dela.
      for (const grupo of [grupoFamilias, grupoOperacional]) {
        for (const filho of grupo.children) {
          const malha = filho as THREE.Mesh;
          malha.geometry?.dispose();
          if (malha.material) disposeMaterial(malha.material);
        }
      }
      for (const linhas of [focais, segundoGrau]) {
        linhas.geometry.dispose();
        disposeMaterial(linhas.material);
      }
      espinha.geometry.dispose();
      disposeMaterial(espinha.material);
      halo.geometry.dispose();
      disposeMaterial(halo.material);
      scene.clear();
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}

function disposeMaterial(material: THREE.Material | THREE.Material[]): void {
  for (const item of Array.isArray(material) ? material : [material]) item.dispose();
}

/**
 * A legenda em texto. Ela descreve a gramática que a cena tem agora.
 *
 * A versão anterior ainda nomeava esfera, prisma e toro — corpos que a ADR-002 tirou
 * de cena. Uma legenda que descreve o desenho antigo é pior que legenda nenhuma:
 * ela ensina a procurar o que não está lá.
 */
function construirLegenda(projection: Projection): string {
  const linhas: string[] = [
    'PAINÉIS',
    'MOC: largo 16:9, cabeçalho do domínio',
    'nota: compacto 4:3',
    'ponte: horizontal 21:9, dois domínios no cabeçalho',
    'quórum: vertical 3:4',
    'tarefa: quadrado · endpoint: pequeno 3:2',
    '',
    'clique expande o próprio painel; Esc recolhe',
    '',
  ];
  linhas.push('RELAÇÕES');
  for (const familia of projection.meta.relationFamilies) {
    const style = EDGE_STYLES[familia as RelationFamily];
    const padrao = style.pattern.length === 0 ? 'contínua' : 'tracejada';
    linhas.push(`${style.label}: ${style.doubled ? 'dupla' : padrao}`);
  }
  linhas.push('');
  linhas.push('DOMÍNIOS');
  for (const domain of projection.meta.domains) linhas.push(domain.label);
  return linhas.join('\n');
}
