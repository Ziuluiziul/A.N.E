// A nuvem de modelos: quem faz o trabalho, mapeado como o corpus mapeia o que se sabe.
//
// Antes daqui, "modelos" eram 114 placas — os mesmos 7 modelos redesenhados a cada
// execução de quórum. Isso não é um mapa, é uma repetição: a cena respondia "houve 38
// execuções" quando a pergunta era "quem avaliou, e quanto". O registro canônico do
// backend reduziu aquilo a 4 provedores e 7 modelos, e este módulo dá a eles a mesma
// gramática espacial que o corpus usa para MOC e nota: **âncora com satélites**.
//
// O provedor é a âncora, e os modelos dele orbitam em volta, no plano da tela. O
// paralelo é literal e proposital — quem já sabe ler um domínio do corpus sabe ler um
// provedor sem aprender nada novo.
//
// **Uma família por provedor, e cada família na própria direção.**
//
// Provedores e modelos já foram duas nuvens em lugares diferentes do mundo, e o preço
// estava em todas as capturas: cada uma das 193 arestas provedor→modelo atravessava o
// vão entre as duas, todas pelo mesmo volume, e o que se via era uma parede de fios com
// dois pontos de fuga. A causa não era a quantidade de arestas — era a colinearidade.
// Separar as nuvens **por altura** punha origem e destino no mesmo eixo, e aí não há
// espessura de linha nem opacidade que desfaça o feixe.
//
// Agora o modelo mora junto do provedor que o reúne. Cada família se assenta num setor
// próprio da casca, e o provedor fica na face interna da sua — perto do miolo, onde a
// constelação de infraestrutura se lê como constelação, e não afogado no meio de
// dezenas de filhos. As mesmas 193 relações continuam existindo; o que muda é que elas
// passaram a ser curtas, locais e a apontar para direções diferentes.

import type { Projection, ProjectionNode } from './contract';
import { layoutAtlas, type LayoutMap, type Vec3 } from './layout';
import { paraMundoNaBase } from './screenBasis';
import { panelWorldExtentOf } from './panelScale';


/**
 * Os dois domínios da frente de modelos.
 *
 * O provedor saiu da nuvem de modelos e ganhou a sua quando o acervo passou de 30 para
 * 193 modelos: como âncora **dentro** da nuvem que ele organiza, ele sumia no meio dos
 * filhos — quatro painéis contra centenas. Separado, o provedor volta a ser o mapa, e a
 * ligação entre as duas nuvens continua dizendo quem reúne quem.
 */
export const MODEL_DOMAIN = 'operacional/modelos';
export const PROVIDER_DOMAIN = 'operacional/provedores';
/**
 * Os trabalhadores, que são vizinhos da nuvem de modelos sem pertencerem a ela.
 *
 * Um papel não é um modelo: ele é resolvido para um a cada leitura do catálogo, e essa
 * resolução muda. Por isso ele não entra em nenhuma família de provedor — ficaria
 * afirmando um vínculo do tamanho de uma sessão. Fica na borda da região, em anel
 * próprio, e é lá que a configuração dele mora.
 */
export const WORKER_DOMAIN = 'operacional/trabalhadores';
/**
 * Histórico de quórum injetado na projeção. Não pertence à cena principal: a
 * `runtimeLayer` é a autoridade da operação (ADR-005). Com milhares de painéis
 * persistidos, desenhá-los como placas e arestas estoura o buffer de vértices.
 */
export const QUORUM_DOMAIN = 'operacional/quorum';

/**
 * Raio da calota dos provedores.
 *
 * Menor que o do corpus porque a nuvem é menor: quatro provedores com sete a dezoito
 * modelos cada não precisam do mesmo território que quinze domínios com sessenta e cinco
 * notas. O relaxamento de `layoutAtlas` cuida do resto.
 */
const ANEL_DOS_PROVEDORES = 52;

/** Espaçamento entre placas, para quem ainda dispõe satélites em volta de uma âncora. */
const FOLGA_ENTRE_PLACAS = 0.55;

/** Raio que acomoda `quantos` painéis de largura `largura` numa volta completa. */
export function raioParaCaber(quantos: number, largura: number, minimo: number): number {
  if (quantos <= 1) return minimo;
  const separacao = largura * (1 + FOLGA_ENTRE_PLACAS);
  return Math.max(minimo, separacao / (2 * Math.sin(Math.PI / quantos)));
}

export interface ModelPlacement {
  /** Provedores **e** modelos, no frame da região de computação. */
  positions: LayoutMap;
  /** Raio e profundidade da nuvem inteira, no frame dela. */
  extent: { radius: number; depth: number };
  /** Extensão só dos provedores, para quem precisa medir a constelação sozinha. */
  providerExtent: { radius: number; depth: number };
  providers: string[];
  /** Os trabalhadores, no anel da borda. Vazio quando a projeção não os traz. */
  workers: string[];
  /**
   * O raio da casca das famílias — a entrada de âncora dos trabalhadores.
   *
   * Sai daqui porque quem os possui é a `runtimeLayer`, e ela precisa da **mesma**
   * grandeza que este layout usaria. Devolver a extensão medida no lugar dela daria um
   * número parecido e errado, e a paridade da migração acusaria diferença sem haver
   * mudança de política.
   */
  shellRadius: number;
}

export function isModelNode(node: ProjectionNode): boolean {
  return node.domainId === MODEL_DOMAIN;
}

export function isProviderNode(node: ProjectionNode): boolean {
  return node.domainId === PROVIDER_DOMAIN;
}

export function isWorkerNode(node: ProjectionNode): boolean {
  return node.domainId === WORKER_DOMAIN;
}

/**
 * A qual provedor um modelo pertence. Ele declara isso nos metadados, e é só dali.
 *
 * Modelo sem provedor declarado ganha família própria, e não é distribuído numa
 * qualquer: pertencer é afirmação, e inventá-la faria o mapa dizer que um endpoint é de
 * quem não o serve.
 */
const SEM_PROVEDOR = 'op/provider/';

function familiaDe(node: ProjectionNode): string {
  const provider = node.operational?.provider;
  return provider === undefined ? SEM_PROVEDOR : `op/provider/${provider}`;
}

/**
 * Assenta provedores e modelos com **o mesmo algoritmo do corpus**, família por família.
 *
 * A disposição de cada família é a do corpus, e pelo mesmo motivo de sempre: já foi um
 * anel de anéis no plano da tela, e visto de lado um anel é uma linha — com a câmera
 * livre, a nuvem inteira colapsava. O que se reusa é a própria função: `layoutAtlas`
 * deixou de presumir que âncora é MOC, e aqui o provedor ocupa esse papel.
 *
 * O que mudou foi o **nível** em que ela é chamada. Antes era uma chamada só, com as
 * quatro âncoras juntas numa calota, e os provedores eram depois arrancados para uma
 * nuvem distante: as 193 arestas provedor→modelo ficavam todas colineares e formavam a
 * parede de fios. Agora cada família é assentada no frame dela, e o conjunto de famílias
 * se reparte pela casca — cada uma no seu setor, apontando para fora. As relações são as
 * mesmas; elas passaram a cruzar o espaço em direções diferentes.
 */
/**
 * A âncora de cada trabalhador, a partir da identidade — e não de um nó já assentado.
 *
 * É a `anchorPose` da ADR-005, extraída para que a `runtimeLayer` possa **possuir** a
 * entidade em vez de espelhar uma posição pronta. A diferença não é de estilo: receber a
 * posição já calculada transfere o objeto sem transferir a autoridade, e a duplicação
 * sobrevive sob outro nome.
 *
 * Depende de três coisas e de mais nada — a ordem das identidades, a quantidade delas, e
 * o raio da casca dos modelos. Nenhuma delas é a projeção: quem chama decide de onde tira
 * os ids, e é isso que permite a mesma âncora ser calculada pelo dono novo e pelo antigo
 * durante a migração, para a paridade poder ser medida entre os dois.
 *
 * `raioDaCasca` zero significa região de modelos vazia: o anel se sustenta sozinho, com o
 * raio que as próprias placas exigem.
 */
export function workerAnchorPoses(
  ids: readonly string[],
  raioDaCasca: number,
): LayoutMap {
  const positions: LayoutMap = new Map();
  if (ids.length === 0) return positions;
  const largura = panelWorldExtentOf('worker').width;
  const raio = Math.max(
    raioDaCasca * FOLGA_DO_ANEL_DE_TRABALHO,
    raioParaCaber(ids.length, largura, largura),
  );
  [...ids].sort((a, b) => a.localeCompare(b)).forEach((id, indice) => {
    const angulo = (2 * Math.PI * indice) / ids.length;
    positions.set(
      id,
      paraMundoNaBase({ x: 0, y: 0, z: 0 }, Math.cos(angulo) * raio, Math.sin(angulo) * raio, 0),
    );
  });
  return positions;
}

export function layoutModels(projection: Projection): ModelPlacement {
  // O trabalhador entra na região, mas não nas famílias: ele é assentado depois, no
  // anel da borda.
  const daRegiao = projection.nodes.filter((node) => isModelNode(node) || isProviderNode(node));
  if (daRegiao.length === 0) {
    // Sem modelo nem provedor não há casca — mas pode haver trabalhador, e ele não
    // depende de nenhum dos dois para existir. O anel é assentado sozinho, com o raio
    // que as próprias placas exigem.
    const soltos = projection.nodes.filter(isWorkerNode).sort(sortById);
    const largura = panelWorldExtentOf('worker').width;
    const raio = raioParaCaber(soltos.length, largura, largura);
    // Também aqui os trabalhadores não são materializados: quem os possui é a
    // `runtimeLayer`. O que sobrevive é a extensão que eles reservam, para a região
    // continuar medindo o mesmo território de antes.
    const positions: LayoutMap = new Map();
    return {
      positions,
      extent: { radius: soltos.length > 0 ? raio + largura : 1, depth: 1 },
      providerExtent: { radius: 1, depth: 1 },
      providers: [],
      workers: soltos.map((node) => node.id),
      shellRadius: 0,
    };
  }
  const provedores = daRegiao
    .filter(isProviderNode)
    .map((node) => node.id)
    .sort();

  // As famílias, na ordem estável do identificador do provedor: é ela que decide o setor
  // de cada uma, e um setor que mudasse de dono entre recargas destruiria o mapa mental
  // pela mesma razão que o azimute de um MOC não muda.
  const membros = new Map<string, ProjectionNode[]>();
  for (const id of provedores) membros.set(id, []);
  for (const node of daRegiao) {
    if (isProviderNode(node)) continue;
    const chave = familiaDe(node);
    const lista = membros.get(chave);
    if (lista) lista.push(node);
    else membros.set(chave, [node]);
  }
  const chaves = [...membros.keys()].sort();

  // Cada família no frame dela, com o provedor na origem. O relaxamento e a faixa de
  // profundidade são os do corpus, e é isso que dá volume a cada família em vez de
  // deixá-la um disco.
  const porFamilia = new Map<string, { locais: LayoutMap; raio: number }>();
  for (const chave of chaves) {
    const doGrupo = membros.get(chave)!;
    const ancora = daRegiao.find((node) => node.id === chave);
    const subProjecao: Projection = {
      ...projection,
      nodes: ancora ? [ancora, ...doGrupo] : doGrupo,
    };
    const locais = layoutAtlas(subProjecao, {
      include: 'all',
      isAnchor: isProviderNode,
      anchorIdOf: () => chave,
      // O provedor da família é a raiz **dela**: ele fica no miolo do próprio frame, e
      // quem reparte os setores é a casca de famílias, um nível acima.
      isRoot: () => true,
      anchorRing: ANEL_DOS_PROVEDORES,
      seed: 20260808,
    });
    let raio = 1;
    for (const [id, p] of locais) {
      if (id === chave) continue;
      raio = Math.max(raio, Math.hypot(p.x, p.y, p.z));
    }
    porFamilia.set(chave, { locais, raio: raio + panelWorldExtentOf('endpoint').width });
  }

  // O recuo do provedor: ele sai do miolo da própria família e vai para a face interna
  // dela. Dentro da família ele era quatro placas num mar de cento e noventa, e o mapa
  // desaparecia no território que ele mapeia; na face interna, os quatro voltam a formar
  // uma constelação legível sem que nenhuma aresta precise atravessar a cena para chegar
  // aos filhos.
  const meiaPlacaDoProvedor = Math.hypot(
    panelWorldExtentOf('provider').width,
    panelWorldExtentOf('provider').height,
  ) / 2;
  const recuo = (raioDaFamilia: number): number =>
    raioDaFamilia + meiaPlacaDoProvedor * (1 + FOLGA_ENTRE_PLACAS);

  const direcoes = direcoesDaCasca(chaves.length);
  const maiorRaio = Math.max(...chaves.map((chave) => porFamilia.get(chave)!.raio));
  const maiorRecuo = Math.max(...chaves.map((chave) => recuo(porFamilia.get(chave)!.raio)));
  // O raio da casca sai da separação exigida entre duas famílias vizinhas — bordas sem
  // se tocar — e nunca de um número escolhido à mão. O piso é o maior recuo: com ele, o
  // provedor mais afastado da própria família cai no miolo da região, e não do lado de
  // fora dela.
  //
  // E é **quantizado**, pelo mesmo motivo que o anel das âncoras do corpus é: sem degrau,
  // um endpoint novo na maior família mudaria o raio da casca e deslocaria os outros três
  // provedores, que não têm nada com isso.
  const raioDaCasca = emDegraus(
    Math.max(maiorRecuo, (maiorRaio * 2 * (1 + FOLGA_ENTRE_FAMILIAS)) / menorSeparacao(direcoes)),
  );

  const positions: LayoutMap = new Map();
  chaves.forEach((chave, indice) => {
    const { locais, raio } = porFamilia.get(chave)!;
    const direcao = direcoes[indice]!;
    const centro = paraMundoNaBase(
      { x: 0, y: 0, z: 0 },
      direcao.x * raioDaCasca,
      direcao.y * raioDaCasca,
      direcao.z * raioDaCasca,
    );
    for (const [id, p] of locais) {
      if (id === chave) continue;
      positions.set(id, { x: p.x + centro.x, y: p.y + centro.y, z: p.z + centro.z });
    }
    if (!locais.has(chave)) return;
    // O provedor, na face interna: o centro da família menos o recuo, na mesma direção.
    const passo = raioDaCasca - recuo(raio);
    positions.set(
      chave,
      paraMundoNaBase(
        { x: 0, y: 0, z: 0 },
        direcao.x * passo,
        direcao.y * passo,
        direcao.z * passo,
      ),
    );
  });

  // **O anel dos trabalhadores**, na borda externa da região.
  //
  // Fora da casca, e não em mais um setor dela: um setor a mais reparte as direções de
  // novo e move os quatro provedores, que não têm nada com isto — e continuidade
  // espacial é invariante, não cortesia. Aqui nenhuma posição existente muda; o que
  // muda é que a região passa a ter uma borda ocupada.
  //
  // Em anel no plano da visada canônica, e não em calota: são sete placas, e sete numa
  // casca esférica ficam tão espalhadas que deixam de se ler como um grupo.
  // **Os trabalhadores não são materializados aqui — ADR-005.**
  //
  // Quem os possui é a `runtimeLayer`, e este layout passou a ser só a fonte da âncora
  // deles, por `workerAnchorPoses`. Assentá-los também aqui criaria a segunda instância
  // visual que a ADR existe para eliminar: os sete apareceriam duas vezes, e dois
  // subsistemas poderiam reposicionar a mesma entidade.
  //
  // O descarte é por **semântica**, e nunca por quantidade ou posição: enquanto o backend
  // seguir enviando os nós legados, eles são carga ignorada, e um oitavo trabalhador
  // futuro não ressuscita por acidente. O que os identifica é o domínio, que é o mesmo
  // discriminador que `isWorkerNode` já aplica.
  const trabalhadores = projection.nodes.filter(isWorkerNode).sort(sortById);

  const medir = (quais: (id: string) => boolean): { radius: number; depth: number } => {
    let radius = 1;
    let depth = 1;
    for (const [id, p] of positions) {
      if (!quais(id)) continue;
      radius = Math.max(radius, Math.hypot(p.x, p.y));
      depth = Math.max(depth, Math.abs(p.z));
    }
    return { radius, depth };
  };
  const daConstelacao = new Set(provedores);
  const idsTrabalhadores = trabalhadores.map((node) => node.id);
  return {
    positions,
    extent: medir(() => true),
    providerExtent: medir((id) => daConstelacao.has(id)),
    providers: provedores,
    workers: idsTrabalhadores,
    shellRadius: raioDaCasca,
  };
}

function sortById(a: ProjectionNode, b: ProjectionNode): number {
  return a.id.localeCompare(b.id);
}

/**
 * Quanto o anel dos trabalhadores se afasta da casca de modelos.
 *
 * Encostar não basta, pelo mesmo motivo de sempre: um anel tangente à casca lê como
 * parte dela, e o que se quer dizer é que trabalhador não é modelo.
 */
const FOLGA_DO_ANEL_DE_TRABALHO = 1.22;

/**
 * Folga entre duas famílias vizinhas, como fração do diâmetro da maior.
 *
 * Encostar não basta pelo mesmo motivo que vale entre duas placas: famílias tangentes
 * ainda se leem como uma só, e o que se quer aqui é justamente que se leiam como quatro.
 */
const FOLGA_ENTRE_FAMILIAS = 0.16;

/** Degrau do raio da casca, em larguras de placa. Ver o uso, e `ringRadius` no corpus. */
const DEGRAU_DA_CASCA = 6;

function emDegraus(raio: number): number {
  const degrau = panelWorldExtentOf('endpoint').width * DEGRAU_DA_CASCA;
  return Math.ceil(raio / degrau) * degrau;
}

/** As direções dos setores: Fibonacci na esfera, na base da tela. */
function direcoesDaCasca(total: number): Vec3[] {
  if (total <= 1) return [{ x: 0, y: 1, z: 0 }];
  return Array.from({ length: total }, (_, indice) => {
    const altura = 1 - (2 * indice) / (total - 1);
    const anel = Math.sqrt(Math.max(1 - altura * altura, 0));
    const azimute = ANGULO_AUREO * indice;
    return { x: Math.cos(azimute) * anel, y: Math.sin(azimute) * anel, z: altura };
  });
}

/** A menor distância entre duas direções da casca. Zero direções ou uma só: sem escala. */
function menorSeparacao(direcoes: Vec3[]): number {
  let minima = Number.POSITIVE_INFINITY;
  for (let i = 0; i < direcoes.length; i += 1) {
    for (let j = i + 1; j < direcoes.length; j += 1) {
      const a = direcoes[i]!;
      const b = direcoes[j]!;
      minima = Math.min(minima, Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z));
    }
  }
  return Number.isFinite(minima) && minima > 1e-9 ? minima : Number.POSITIVE_INFINITY;
}

const ANGULO_AUREO = Math.PI * (3 - Math.sqrt(5));
