// Layout ancorado, volumétrico e estável. Substitui a esfera force-directed da prova.
//
// A esfera livre era ruim por três motivos: oclusão sem remédio, nenhum ponto de
// referência para reencontrar uma nota, e o mapa inteiro se reorganizando quando uma
// única nota mudava. O atlas troca isso por âncoras.
//
// `x/y` carregam a topologia: azimute igualmente espaçado para os MOCs, e cada nota
// orbitando a própria âncora. `z` dá volume — as âncoras se assentam numa calota, e
// os territórios são nuvens achatadas, não discos — dentro da faixa de 15% a 25% da
// extensão horizontal que o dossiê especifica.
//
// A profundidade é limitada, e não por timidez: `z` separa camadas, foco e
// sobreposições, mas não mede nada. Profundidade maior que essa faixa custa
// legibilidade e oclusão sem devolver informação, e foi por isso que a esfera livre
// da prova saiu.
//
// Tudo é determinístico a partir da semente: um mapa que muda de forma a cada
// recarga não é navegável, e um teste não conseguiria prendê-lo.

import type { Projection, ProjectionEdge, ProjectionNode } from './contract';
import { describePanel } from './panels';
import { panelSweepRadius, panelWorldExtent } from './panelScale';
import { Z_LAYER } from './sizing';

export interface Vec3 {
  x: number;
  y: number;
  z: number;
}

export interface LayoutOptions {
  /** Raio da calota onde os MOCs de domínio se assentam. */
  anchorRing?: number;
  /** Metade da espessura da faixa de profundidade. */
  zBand?: number;
  /** Amplitude da calota, como fração do raio das âncoras. */
  crownDepth?: number;
  seed?: number;
  relaxIterations?: number;
  /**
   * Que camada assentar. `epistemic` é o padrão, e o padrão é a proteção.
   *
   * Enquanto esta função assentava a projeção inteira, os nós de quórum contavam para
   * `ringRadius` e acumular 32 painéis empurrava o anel de 87 para 148 unidades,
   * movendo **todos os MOCs** — dado que não é do corpus reorganizando o mapa que o
   * usuário memorizou. Quem precisa assentar operação usa um frame próprio
   * (`operationalLayout.ts`); `all` existe para a camada de eventos ao vivo, que é uma
   * projeção inteiramente operacional e se assenta sozinha, longe deste anel.
   */
  include?: 'epistemic' | 'all';
  /**
   * Quem é âncora, e de quem cada nó pende.
   *
   * Era fixo em `kind === 'moc'` e `anchorMocId`, e isso prendia este algoritmo ao
   * corpus. As outras nuvens ficaram sem ele e foram construídas em anéis no plano da
   * tela — que colapsam numa linha assim que a câmera sai da visada canônica. Como é
   * justamente a disposição do corpus que se quer nelas, o que precisa mudar é só quem
   * responde "isto é âncora" e "isto pende daquilo".
   */
  isAnchor?: (node: ProjectionNode) => boolean;
  anchorIdOf?: (node: ProjectionNode) => string | null;
  /** Âncora que fica no miolo, em vez de na calota. Por padrão, o MOC de raiz. */
  isRoot?: (node: ProjectionNode) => boolean;
}

const DEFAULTS = {
  /**
   * Raio da calota das âncoras.
   *
   * Era 64, de quando a placa media 3,2. Com ela em 5,0 o corpus virou a nuvem mais
   * densa da cena: medido, 56% da área projetada era placa, contra 18% do quórum — o
   * conhecimento lia como um bloco compacto e a deliberação como um campo vazio. Em 92
   * os dois ficam em 31%, que é a mesma densidade, e o corpus continua mais junto em
   * raio absoluto, como convém a quem tem 84 nós contra 216. Em 104 abre mais ar entre
   * territórios sem afrouxar o quórum.
   */
  anchorRing: 104,
  // Meia-espessura da faixa de profundidade. O dossiê pede `z` entre 15% e 25% da
  // extensão horizontal; a primeira entrega ficou em 5,7%, que é raso demais para
  // haver paralaxe real. Este valor põe o atlas dentro da faixa especificada.
  zBand: 54,
  seed: 20260802,
  relaxIterations: 90,
  /**
   * Amplitude da calota, como fração do raio das âncoras.
   *
   * As âncoras não ficam num anel plano: elas se assentam numa calota, com azimute
   * igualmente espaçado e elevação variando por índice, o que dá volume à estrutura
   * sem soltá-la.
   *
   * A amplitude é fração do raio — que é quantizado — e não da extensão total. Medir
   * contra a extensão pareceria mais fiel ao dossiê, mas a extensão depende do maior
   * território, então uma nota nova mudaria a profundidade de todos os MOCs. Amarrar
   * à escala estrutural mantém a faixa e preserva a estabilidade.
   */
  crownDepth: 0.22,
  include: 'epistemic',
  isAnchor: (node: ProjectionNode) => node.kind === 'moc',
  anchorIdOf: (node: ProjectionNode) => node.anchorMocId,
  isRoot: (node: ProjectionNode) => node.domainId === 'raiz',
} as const;

const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

/**
 * Folga entre placas, como fração da soma dos raios.
 *
 * Acima de 1 porque encostar não basta: duas placas tangentes ainda competem pela
 * leitura, e o texto de uma começa onde a borda da outra termina.
 */
const FOLGA_ENTRE_PLACAS = 1.78;

/** Passo inicial da espiral do território, em raios médios de placa. */
const PASSO_POR_RAIO = 1.78;

/**
 * Folga mínima entre duas placas **quaisquer**, como fração da soma dos raios.
 *
 * Menor que `FOLGA_ENTRE_PLACAS` de propósito. Dentro de um território a folga é de
 * leitura: as placas vizinhas são lidas em conjunto e precisam de ar entre elas. Entre
 * territórios diferentes o que se exige é só que não se cubram — pedir a mesma folga
 * afastaria domínios inteiros por uma exigência que ninguém formulou.
 */
const FOLGA_MINIMA_GLOBAL = 1.06;

/**
 * Quanto da distância ao centro vira altura.
 *
 * Era 0,45, e a auditoria mostrou por que isso não bastava: só 2,3% da variância da
 * cena estava em profundidade, e o atlas lia como lâmina. Aqui `z` passa a separar o
 * que o plano não consegue — dois nós no mesmo azimute deixam de se sobrepor porque
 * estão em alturas diferentes, não porque foram afastados no plano.
 *
 * Subiu de 1,18 para 1,42 quando a espiral passou a somar em quadratura. A altura é
 * proporcional ao raio do território, então apertar o plano encolhia junto a
 * profundidade: `volumetric.test.ts` acusou σ3/σ1 em 0,224 contra o mínimo de 0,24, que
 * é o atlas voltando a ler como lâmina. A intenção era apertar o plano, não achatar a
 * cena — este valor devolve a razão sem desfazer o aperto, e foi calibrado contra o
 * teste, não escolhido à mão.
 */
const COMPRESSAO_VERTICAL = 1.42;

export type LayoutMap = Map<string, Vec3>;

/** Hash estável de string. Mesma nota, mesma posição, em qualquer máquina. */
export function hash32(text: string, seed = 0): number {
  let h = 2166136261 ^ seed;
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) / 4294967296;
}

interface Cluster {
  key: string;
  anchorId: string | null;
  members: ProjectionNode[];
}

/**
 * Agrupa por âncora. Nota sem âncora cai no agrupamento do próprio domínio, e não
 * numa âncora escolhida a esmo — o backend já se recusou a desempatar, e o layout
 * não desfaz essa recusa.
 */
function clusterize(
  nodes: ProjectionNode[],
  isAnchor: (node: ProjectionNode) => boolean,
  anchorIdOf: (node: ProjectionNode) => string | null,
): Cluster[] {
  const porChave = new Map<string, Cluster>();
  for (const node of nodes) {
    if (isAnchor(node)) continue;
    const anchorId = anchorIdOf(node);
    const key = anchorId ?? `domínio:${node.domainId}`;
    const cluster = porChave.get(key) ?? { key, anchorId, members: [] };
    cluster.members.push(node);
    porChave.set(key, cluster);
  }
  return [...porChave.values()].sort((a, b) => a.key.localeCompare(b.key));
}

/** Degrau de crescimento do anel. Ver `ringRadius`. */
const BUCKET_SIZE = 32;

/**
 * Raio do anel, quantizado pelo tamanho do corpus.
 *
 * O anel precisa crescer quando o corpus cresce, senão territórios vizinhos se
 * tocam. Mas fazê-lo variar continuamente moveria todos os MOCs a cada nota nova, e
 * a métrica de estabilidade do dossiê pede deslocamento zero de MOC fora de mudança
 * estrutural. O degrau resolve a tensão: dentro do mesmo balde de 32 entidades o
 * anel não muda, e a passagem de balde é rara e observável.
 */
export function ringRadius(nodeCount: number, base: number): number {
  return base * (1 + 0.12 * Math.floor(nodeCount / BUCKET_SIZE));
}

/**
 * A ordem dos domínios no anel, tirada das arestas que os ligam.
 *
 * Era `localeCompare` do id — alfabética. Medido sobre o corpus real, isso punha
 * 279 das 607 arestas cruzando o anel com mediana 158 contra 56 das internas: quase
 * metade das ligações pagava a travessia porque um domínio começa com "C" e o outro
 * com "M". Alfabética é ordem sem conteúdo, e a Política é explícita em que a pasta é
 * só localização — o que estrutura é a relação declarada.
 *
 * O encadeamento é guloso: começa no par mais ligado e acrescenta sempre o domínio de
 * maior afinidade com a ponta atual. Não é a seriação ótima, e não precisa ser — a
 * diferença que importa é entre "vizinho porque se ligam" e "vizinho porque a inicial
 * calhou". Empate desempata por id, para a ordem continuar determinística e a memória
 * espacial continuar valendo entre execuções.
 */
export function affinityOrder(
  mocs: ProjectionNode[],
  edges: readonly ProjectionEdge[],
  domainOf: ReadonlyMap<string, string | undefined>,
): ProjectionNode[] {
  if (mocs.length < 3) return [...mocs].sort((a, b) => a.id.localeCompare(b.id));

  const afinidade = new Map<string, number>();
  const par = (a: string, b: string) => (a < b ? `${a} ${b}` : `${b} ${a}`);
  for (const aresta of edges) {
    const origem = domainOf.get(aresta.source);
    const destino = domainOf.get(aresta.target);
    if (!origem || !destino || origem === destino) continue;
    const chave = par(origem, destino);
    afinidade.set(chave, (afinidade.get(chave) ?? 0) + 1);
  }

  const restantes = [...mocs].sort((a, b) => a.id.localeCompare(b.id));
  const dominioDoMoc = new Map(restantes.map((moc) => [moc.id, domainOf.get(moc.id) ?? moc.id]));
  const peso = (a: ProjectionNode, b: ProjectionNode): number =>
    afinidade.get(par(dominioDoMoc.get(a.id)!, dominioDoMoc.get(b.id)!)) ?? 0;

  let inicio = restantes[0]!;
  let melhor = -1;
  for (const a of restantes) {
    const soma = restantes.reduce((total, b) => (a === b ? total : total + peso(a, b)), 0);
    if (soma > melhor) {
      melhor = soma;
      inicio = a;
    }
  }

  const ordem: ProjectionNode[] = [inicio];
  const pendentes = restantes.filter((moc) => moc !== inicio);
  while (pendentes.length > 0) {
    const ponta = ordem[ordem.length - 1]!;
    let escolhido = 0;
    for (let indice = 1; indice < pendentes.length; indice += 1) {
      const atual = peso(ponta, pendentes[indice]!);
      const vigente = peso(ponta, pendentes[escolhido]!);
      if (atual > vigente) escolhido = indice;
    }
    ordem.push(...pendentes.splice(escolhido, 1));
  }
  return ordem;
}

/**
 * Assenta os MOCs. O de raiz no centro; os de domínio, em fatias angulares iguais.
 *
 * As fatias são iguais — nunca proporcionais à quantidade de notas. Proporcional seria
 * mais bonito e faria cada MOC mudar de lugar toda vez que uma nota entrasse em qualquer
 * domínio, que é exatamente o que destrói o mapa mental de quem já sabe onde as coisas
 * ficam. O que decide a **ordem** delas é a afinidade acima, e não o alfabeto.
 */
function placeAnchors(
  mocs: ProjectionNode[],
  totalNodes: number,
  options: Required<LayoutOptions>,
  ordemDosDominios?: ProjectionNode[],
): LayoutMap {
  const posicoes: LayoutMap = new Map();

  const raiz = mocs.filter((moc) => options.isRoot(moc));
  const perifericos = (ordemDosDominios ?? mocs).filter((moc) => !options.isRoot(moc));

  raiz.forEach((moc, indice) => {
    // Mais de um MOC de raiz é improvável; se houver, ficam juntos no miolo.
    const angulo = GOLDEN_ANGLE * indice;
    const raio = indice === 0 ? 0 : 8;
    posicoes.set(moc.id, {
      x: Math.cos(angulo) * raio,
      y: Math.sin(angulo) * raio,
      z: Z_LAYER.moc,
    });
  });

  const raio = ringRadius(totalNodes, options.anchorRing);
  perifericos.forEach((moc, indice) => {
    const azimute = (2 * Math.PI * indice) / perifericos.length;
    // Elevação pelo ângulo áureo: espalha bem, é função só do índice — nada de
    // depender da quantidade de notas — e evita que dois MOCs vizinhos no anel
    // caiam na mesma altura, que é o que faria a coroa parecer um anel plano.
    const altura = raio * options.crownDepth * Math.sin(indice * GOLDEN_ANGLE);
    // Raio horizontal corrigido para que a distância tridimensional ao centro seja a
    // mesma para todas as âncoras. Sem isso a elevação viraria hierarquia: um MOC
    // "mais alto" pareceria mais importante que o vizinho.
    const horizontal = Math.sqrt(Math.max(raio * raio - altura * altura, 1));
    posicoes.set(moc.id, {
      x: Math.cos(azimute) * horizontal,
      y: Math.sin(azimute) * horizontal,
      z: altura,
    });
  });

  return posicoes;
}

/**
 * Espalha os membros num volume achatado ao redor da âncora, não num disco.
 *
 * A distribuição é a de Fibonacci sobre a esfera — direções bem separadas, sem
 * agrupamento nos polos — com o raio crescendo pela raiz do índice, de modo que as
 * notas de maior grau, que vêm primeiro, fiquem perto da âncora. A componente
 * vertical é comprimida: o território tem volume de verdade, mas continua mais largo
 * que alto, porque profundidade excessiva custa legibilidade sem devolver informação.
 */
function placeMembers(
  cluster: Cluster,
  centro: Vec3,
  posicoes: LayoutMap,
  options: Required<LayoutOptions>,
  ancora: ProjectionNode | undefined,
): void {
  const ordenados = [...cluster.members].sort(
    (a, b) => b.visual.labelPriority - a.visual.labelPriority || a.id.localeCompare(b.id),
  );
  // O passo sai da própria placa, não de uma constante: a distribuição inicial já
  // nasce na escala em que o relaxamento vai trabalhar, e ele converge sem arrastar
  // ninguém para longe da âncora.
  const passo =
    ordenados.reduce((soma, node) => soma + raioDaPlaca(node), 0) /
      Math.max(ordenados.length, 1) *
    PASSO_POR_RAIO;
  const total = Math.max(ordenados.length, 1);
  const giro = hash32(cluster.key, options.seed) * Math.PI * 2;
  const raioInicial = ancora ? raioDaPlaca(ancora) * FOLGA_ENTRE_PLACAS : 0;

  ordenados.forEach((node, indice) => {
    const cosPolar = 1 - (2 * (indice + 0.5)) / total;
    const senoPolar = Math.sqrt(Math.max(1 - cosPolar * cosPolar, 0));
    const azimute = GOLDEN_ANGLE * indice + giro;
    // A espiral começa fora da placa da âncora, e não no centro dela: nascer em cima
    // do MOC e depender do relaxamento para sair é pagar iterações por um erro de
    // origem.
    //
    // **Em quadratura, e não somado.** O afastamento mínimo era acrescentado a *toda*
    // camada — `raioInicial + passo·√i` —, o que translada a espiral inteira para fora e
    // deixa de valer como distância mínima para virar distância acrescentada. O efeito
    // medido é território esparso com buraco no miolo: computação punha 9 notas num raio
    // de 67, mais largo que as 17 de física. Somar em quadratura preserva exatamente a
    // mesma folga da primeira camada — a mais interna continua fora da placa da âncora —
    // e devolve o crescimento por raiz, que é o que mantém densidade constante.
    const raio = Math.sqrt(raioInicial * raioInicial + passo * passo * (indice + 0.6));

    posicoes.set(node.id, {
      x: centro.x + Math.cos(azimute) * senoPolar * raio,
      y: centro.y + Math.sin(azimute) * senoPolar * raio,
      // A componente vertical deixa de ser um resíduo de 0,45 e passa a carregar
      // estrutura: quem está no polo do território fica de fato acima ou abaixo dele.
      z: clampZ(centro.z + Z_LAYER[node.kind] + cosPolar * raio * COMPRESSAO_VERTICAL, options.zBand),
    });
  });
}

function clampZ(value: number, band: number): number {
  return Math.min(Math.max(value, -band), band);
}

/**
 * O espaço que a placa de fato ocupa, medido nela e não numa esfera que não existe mais.
 *
 * `footprint()` derivava de `BASE_RADIUS`, o raio dos corpos primitivos que a ADR-002
 * tirou de cena. Para uma nota ele vale 2,0 unidades — e a placa que a nota desenha tem
 * 9,2 de diagonal. O relaxamento separava por menos de um quarto do que os painéis
 * precisam, e por isso a sobreposição existia **por construção**: nenhuma quantidade de
 * iterações resolve uma distância mínima quatro vezes pequena demais.
 *
 * A meia-diagonal é a medida certa porque a placa é orientada à câmera: ela gira, e o
 * que precisa caber é o círculo que ela varre ao girar.
 */
function raioDaPlaca(node: ProjectionNode): number {
  return panelSweepRadius(describePanel(node));
}

/**
 * Relaxamento local, em três dimensões: só empurra membros do mesmo agrupamento.
 *
 * Restringir ao agrupamento é o que preserva o mapa mental. Uma nota nova em Física
 * reacomoda Física e mais nada — nenhum MOC se move, e nenhum domínio vizinho sente.
 * O empurrão é espacial: separar só no plano deixaria pares sobrepostos em projeção
 * assim que o território ganhou volume.
 */
function relaxCluster(
  cluster: Cluster,
  posicoes: LayoutMap,
  centro: Vec3,
  iteracoes: number,
  ancora: ProjectionNode | undefined,
): void {
  const membros = cluster.members;
  const raio = new Map(membros.map((node) => [node.id, raioDaPlaca(node)]));
  // A âncora entra na colisão como obstáculo **imóvel**.
  //
  // Ela não é membro do agrupamento — `clusterize` deixa os MOCs de fora — e por isso
  // nunca participava do empurra. O efeito era o pior tipo de sobreposição: o primeiro
  // membro nascia no centro do território, a 1,6 unidades do próprio MOC, e a placa da
  // âncora cobria a dele por inteiro. Imóvel porque o azimute dos MOCs é a identidade
  // do domínio: empurrar a âncora para abrir espaço trocaria uma oclusão por uma
  // desorientação.
  const raioDaAncora = ancora ? raioDaPlaca(ancora) : 0;
  for (let passo = 0; passo < iteracoes; passo += 1) {
    let mexeu = false;
    for (let i = 0; i < membros.length; i += 1) {
      const a = membros[i]!;
      const pa = posicoes.get(a.id)!;
      for (let j = i + 1; j < membros.length; j += 1) {
        const b = membros[j]!;
        const pb = posicoes.get(b.id)!;
        // Soma dos raios, com folga: duas placas encostadas ainda disputam leitura.
        const minima = (raio.get(a.id)! + raio.get(b.id)!) * FOLGA_ENTRE_PLACAS;
        let dx = pa.x - pb.x;
        let dy = pa.y - pb.y;
        let dz = pa.z - pb.z;
        let distancia = Math.hypot(dx, dy, dz);
        if (distancia >= minima) continue;
        if (distancia < 1e-6) {
          dx = Math.cos(i + j);
          dy = Math.sin(i + j);
          dz = Math.cos(i - j) * 0.5;
          distancia = Math.hypot(dx, dy, dz);
        }
        const empurrao = (minima - distancia) / 2;
        pa.x += (dx / distancia) * empurrao;
        pa.y += (dy / distancia) * empurrao;
        pa.z += (dz / distancia) * empurrao;
        pb.x -= (dx / distancia) * empurrao;
        pb.y -= (dy / distancia) * empurrao;
        pb.z -= (dz / distancia) * empurrao;
        mexeu = true;
      }
      // Afastamento da âncora: ela empurra, e não é empurrada.
      if (raioDaAncora > 0) {
        const minima = (raio.get(a.id)! + raioDaAncora) * FOLGA_ENTRE_PLACAS;
        let dx = pa.x - centro.x;
        let dy = pa.y - centro.y;
        let dz = pa.z - centro.z;
        let distancia = Math.hypot(dx, dy, dz);
        if (distancia < minima) {
          if (distancia < 1e-6) {
            dx = Math.cos(i);
            dy = Math.sin(i);
            dz = 0.35;
            distancia = Math.hypot(dx, dy, dz);
          }
          const empurrao = minima - distancia;
          pa.x += (dx / distancia) * empurrao;
          pa.y += (dy / distancia) * empurrao;
          pa.z += (dz / distancia) * empurrao;
          mexeu = true;
        }
      }
      // Coesão fraca com a âncora, para o agrupamento não se dissolver com o empurra.
      pa.x += (centro.x - pa.x) * 0.004;
      pa.y += (centro.y - pa.y) * 0.004;
      pa.z += (centro.z - pa.z) * 0.004;
    }
    if (!mexeu) break;
  }
}

/**
 * Posições do atlas inteiro.
 *
 * `previous` preserva o que já estava colocado: identidades conhecidas mantêm a
 * posição e só as novas são assentadas. É o que faz uma nota nova aparecer sem
 * redesenhar o mapa que o usuário já memorizou.
 */
export function layoutAtlas(
  projection: Projection,
  options: LayoutOptions = {},
  previous?: LayoutMap,
): LayoutMap {
  const config = { ...DEFAULTS, ...options };
  const assentados =
    config.include === 'all'
      ? projection.nodes
      : projection.nodes.filter((node) => node.layer === 'epistemic');
  const mocs = assentados.filter((node) => config.isAnchor(node));
  const clusters = clusterize(assentados, config.isAnchor, config.anchorIdOf);

  // A contagem que dimensiona o anel é a dos nós assentados, nunca a da projeção
  // inteira: é essa distinção que faz a camada viva não deslocar o corpus.
  const ordemDosDominios = affinityOrder(
    mocs,
    projection.edges,
    new Map(assentados.map((node) => [node.id, node.domainId])),
  );
  const posicoes = placeAnchors(mocs, assentados.length, config, ordemDosDominios);

  for (const cluster of clusters) {
    const centro = cluster.anchorId
      ? (posicoes.get(cluster.anchorId) ?? { x: 0, y: 0, z: 0 })
      : domainFallbackCenter(cluster, mocs, posicoes, config, assentados.length);
    const ancora = cluster.anchorId
      ? mocs.find((moc) => moc.id === cluster.anchorId)
      : undefined;
    placeMembers(cluster, centro, posicoes, config, ancora);
    relaxCluster(cluster, posicoes, centro, config.relaxIterations, ancora);
  }

  // A ordem é: separar o que se cobre no espaço, desalinhar o que se cobre na visada,
  // e separar de novo. O desalinhamento anda perpendicular à visada e pode encostar
  // duas placas que estavam soltas; a segunda passagem é curta porque o que sobrou é
  // pouco, e ela devolve o piso sem desfazer o desalinhamento — que trabalha em
  // cobertura total, e não em distância.
  separarPlacas(assentados, posicoes, config.isAnchor, config.relaxIterations);
  desalinharOclusoes(assentados, posicoes);
  separarPlacas(assentados, posicoes, config.isAnchor, config.relaxIterations);

  if (previous) {
    for (const [id, anterior] of previous) {
      if (posicoes.has(id)) posicoes.set(id, { ...anterior });
    }
  }
  return posicoes;
}

/**
 * Separação entre placas de **territórios diferentes**, que o relaxamento não alcança.
 *
 * O relaxamento é local ao agrupamento, e é isso que preserva o mapa mental: uma nota
 * nova em Física reacomoda Física e mais nada. O preço era que duas placas de domínios
 * vizinhos podiam cair uma sobre a outra e nenhuma passagem as separava — medido no
 * corpus real, 11 pares se cobriam, quase todos entre territórios diferentes.
 *
 * Esta passagem é o piso que faltava, e ela é deliberadamente **rasa**: só age onde há
 * sobreposição de fato, com a folga mínima em vez da folga de leitura, e o empurrão
 * morre assim que os dois se soltam. Uma nota nova continua não movendo o vizinho —
 * exceto quando ela cai exatamente em cima dele, que é o único caso em que ficar parado
 * seria pior.
 *
 * Âncora não se move: o azimute dela é a identidade do domínio, e empurrar um MOC para
 * abrir espaço trocaria uma oclusão por uma desorientação.
 */
function separarPlacas(
  nodes: ProjectionNode[],
  posicoes: LayoutMap,
  isAnchor: (node: ProjectionNode) => boolean,
  iteracoes: number,
): void {
  const assentados = nodes.filter((node) => posicoes.has(node.id));
  const raio = new Map(assentados.map((node) => [node.id, raioDaPlaca(node)]));
  const movel = new Map(assentados.map((node) => [node.id, !isAnchor(node)]));
  for (let passo = 0; passo < iteracoes; passo += 1) {
    let mexeu = false;
    for (let i = 0; i < assentados.length; i += 1) {
      const a = assentados[i]!;
      const pa = posicoes.get(a.id)!;
      for (let j = i + 1; j < assentados.length; j += 1) {
        const b = assentados[j]!;
        const movelA = movel.get(a.id)!;
        const movelB = movel.get(b.id)!;
        if (!movelA && !movelB) continue;
        const pb = posicoes.get(b.id)!;
        const minima = (raio.get(a.id)! + raio.get(b.id)!) * FOLGA_MINIMA_GLOBAL;
        let dx = pa.x - pb.x;
        let dy = pa.y - pb.y;
        let dz = pa.z - pb.z;
        let distancia = Math.hypot(dx, dy, dz);
        if (distancia >= minima) continue;
        if (distancia < 1e-6) {
          dx = Math.cos(i + j);
          dy = Math.sin(i + j);
          dz = Math.cos(i - j) * 0.5;
          distancia = Math.hypot(dx, dy, dz);
        }
        // Quem pode se mexer divide o empurrão; sozinho, carrega-o inteiro.
        const total = minima - distancia;
        const parteA = movelA ? (movelB ? total / 2 : total) : 0;
        const parteB = movelB ? (movelA ? total / 2 : total) : 0;
        pa.x += (dx / distancia) * parteA;
        pa.y += (dy / distancia) * parteA;
        pa.z += (dz / distancia) * parteA;
        pb.x -= (dx / distancia) * parteB;
        pb.y -= (dy / distancia) * parteB;
        pb.z -= (dz / distancia) * parteB;
        mexeu = true;
      }
    }
    if (!mexeu) break;
  }
}

/**
 * A direção canônica de visada, a mesma que `cameraPoseForExtent` usa.
 *
 * Duplicada aqui como constante em vez de importada de `depth.ts` para não criar um
 * ciclo entre layout e câmera. Se as duas divergirem, a passagem abaixo deixa de
 * cumprir o que promete — por isso `depth.test.ts` prende a igualdade.
 */
export const DIRECAO_CANONICA: Vec3 = (() => {
  const v = { x: 0.34, y: -0.69, z: 0.64 };
  const n = Math.hypot(v.x, v.y, v.z);
  return { x: v.x / n, y: v.y / n, z: v.z / n };
})();

/**
 * Desfaz oclusão total ao longo da linha de visada canônica.
 *
 * O relaxamento por agrupamento não alcança este caso, e nenhuma quantidade dele
 * alcançaria: as duas oclusões que sobravam estavam a 32,7 e 66,6 unidades de
 * distância, em agrupamentos diferentes. Elas não são proximidade — são **alinhamento**.
 * Uma placa grande e próxima cobre por inteiro uma placa menor e distante que por acaso
 * caiu atrás dela.
 *
 * Isto é uma propriedade do ponto de vista, não do layout, e a honestidade sobre o
 * alcance importa: a passagem garante zero oclusão total **na direção canônica**, que é
 * a que o produto abre. Orbitando, o usuário encontra outros alinhamentos — nenhum
 * layout de placas orientadas à câmera pode evitá-los em todas as direções.
 *
 * O empurrão é perpendicular à visada e mínimo: o que se corrige é a coincidência
 * lateral, e a profundidade — que carrega a estrutura — fica intacta. MOCs não se
 * movem, porque o azimute deles é a identidade do domínio.
 */
function desalinharOclusoes(
  nodes: ProjectionNode[],
  posicoes: LayoutMap,
  iteracoes = 40,
): void {
  const moveis = nodes
    .filter((node) => node.kind !== 'moc' && posicoes.has(node.id))
    .sort((a, b) => a.id.localeCompare(b.id));
  const todos = nodes
    .filter((node) => posicoes.has(node.id))
    .sort((a, b) => a.id.localeCompare(b.id));
  if (moveis.length === 0) return;

  // Meia-largura e meia-altura, não o raio circunscrito: a métrica mede contenção de
  // **caixa**, e um círculo em volta da placa erra os dois lados — sobra nos cantos e
  // falta nas bordas. Testar com a mesma forma que se mede é o que faz esta passagem
  // realmente zerar a oclusão em vez de quase zerar.
  const meia = new Map(
    todos.map((node) => {
      const e = panelWorldExtent(describePanel(node));
      return [node.id, { w: e.width / 2, h: e.height / 2 }];
    }),
  );

  const direita = normalizar(cruzar({ x: 0, y: 0, z: 1 }, DIRECAO_CANONICA));
  const acima = normalizar(cruzar(DIRECAO_CANONICA, direita));
  const extensao = extentOf(posicoes);
  const distancia = Math.max(extensao.radius * 3.0, 60);
  const camera = {
    x: DIRECAO_CANONICA.x * distancia,
    y: DIRECAO_CANONICA.y * distancia,
    z: DIRECAO_CANONICA.z * distancia,
  };

  /** Posição no plano da tela, em ângulo, e profundidade ao longo da visada. */
  const visto = (id: string): { u: number; v: number; d: number } => {
    const p = posicoes.get(id)!;
    const rx = p.x - camera.x;
    const ry = p.y - camera.y;
    const rz = p.z - camera.z;
    const d = Math.max(
      -(rx * DIRECAO_CANONICA.x + ry * DIRECAO_CANONICA.y + rz * DIRECAO_CANONICA.z),
      1,
    );
    return {
      u: (rx * direita.x + ry * direita.y + rz * direita.z) / d,
      v: (rx * acima.x + ry * acima.y + rz * acima.z) / d,
      d,
    };
  };

  for (let passo = 0; passo < iteracoes; passo += 1) {
    let mexeu = false;
    for (const alvo of moveis) {
      const a = visto(alvo.id);
      const ma = meia.get(alvo.id)!;
      for (const frente of todos) {
        if (frente.id === alvo.id) continue;
        const b = visto(frente.id);
        if (b.d >= a.d) continue; // não está na frente
        const mb = meia.get(frente.id)!;
        // Sobra angular da placa da frente sobre a de trás, em cada eixo.
        const sobraU = (mb.w / b.d - ma.w / a.d) * FOLGA_DE_VISADA;
        const sobraV = (mb.h / b.d - ma.h / a.d) * FOLGA_DE_VISADA;
        if (sobraU <= 0 || sobraV <= 0) continue; // não cobre nem alinhada
        const du = a.u - b.u;
        const dv = a.v - b.v;
        if (Math.abs(du) >= sobraU || Math.abs(dv) >= sobraV) continue;

        // Sai pelo eixo mais barato: o que exige menos deslocamento para desalinhar.
        const custoU = sobraU - Math.abs(du);
        const custoV = sobraV - Math.abs(dv);
        const p = posicoes.get(alvo.id)!;
        const eixo = custoU <= custoV ? direita : acima;
        const sinal = (custoU <= custoV ? du : dv) >= 0 ? 1 : -1;
        const passoMundo = (custoU <= custoV ? custoU : custoV) * a.d * sinal;
        p.x += eixo.x * passoMundo;
        p.y += eixo.y * passoMundo;
        p.z += eixo.z * passoMundo;
        mexeu = true;
        break;
      }
    }
    if (!mexeu) break;
  }
}

/**
 * Folga angular exigida além da diferença de tamanhos aparentes.
 *
 * Generosa de propósito. Esta passagem trabalha com uma câmera aproximada — a direção
 * canônica, a uma distância derivada da extensão — enquanto a medição acontece em duas
 * poses ligeiramente diferentes: a fixa do protocolo causal e a que o
 * autoenquadramento produz. Uma folga justa zerava a oclusão numa e deixava passar uma
 * na outra. A margem cobre as duas sem custar quase nada: ela só age onde já havia
 * cobertura total.
 */
const FOLGA_DE_VISADA = 2.5;

function cruzar(a: Vec3, b: Vec3): Vec3 {
  return { x: a.y * b.z - a.z * b.y, y: a.z * b.x - a.x * b.z, z: a.x * b.y - a.y * b.x };
}
function normalizar(v: Vec3): Vec3 {
  const n = Math.hypot(v.x, v.y, v.z) || 1;
  return { x: v.x / n, y: v.y / n, z: v.z / n };
}

/** Centro de um agrupamento sem âncora: o baricentro dos MOCs do domínio. */
function domainFallbackCenter(
  cluster: Cluster,
  mocs: ProjectionNode[],
  posicoes: LayoutMap,
  options: Required<LayoutOptions>,
  totalNodes: number,
): Vec3 {
  const domainId = cluster.key.replace('domínio:', '');
  const doDominio = mocs.filter((moc) => moc.domainId === domainId);
  if (doDominio.length === 0) {
    const angulo = hash32(cluster.key, options.seed) * Math.PI * 2;
    return {
      x: Math.cos(angulo) * ringRadius(totalNodes, options.anchorRing) * 1.35,
      y: Math.sin(angulo) * ringRadius(totalNodes, options.anchorRing) * 1.35,
      z: 0,
    };
  }
  const soma = doDominio.reduce(
    (acc, moc) => {
      const p = posicoes.get(moc.id)!;
      return { x: acc.x + p.x, y: acc.y + p.y };
    },
    { x: 0, y: 0 },
  );
  return { x: soma.x / doDominio.length, y: soma.y / doDominio.length, z: 0 };
}

/**
 * Extensão do atlas, para a câmera enquadrar sem adivinhar.
 *
 * `only` restringe a medida a um conjunto de identidades. É o que permite enquadrar a
 * camada ativa em vez da projeção inteira: com as duas camadas na mesma cena, medir
 * tudo faria a visão de corpus recuar para caber um observatório que ninguém pediu
 * para ver.
 */
export function extentOf(
  posicoes: LayoutMap,
  only?: ReadonlySet<string>,
): { radius: number; depth: number } {
  let radius = 1;
  let depth = 1;
  for (const [id, p] of posicoes) {
    if (only && !only.has(id)) continue;
    radius = Math.max(radius, Math.hypot(p.x, p.y));
    depth = Math.max(depth, Math.abs(p.z));
  }
  return { radius, depth };
}
