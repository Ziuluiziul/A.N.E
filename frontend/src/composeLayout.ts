// A composição dos dois frames. Um lugar só, e de mão única.
//
// O atlas epistêmico e o observatório operacional são calculados sem se conhecerem.
// Aqui eles entram no mesmo mundo, e a única coisa que atravessa a fronteira é o raio
// do corpus — consultado pelo observatório para se afastar dele. Nada volta na direção
// oposta.
//
// A assimetria é o incremento inteiro: é ela que faz mil nós de quórum não moverem um
// MOC sequer, e é ela que permite recompor o mundo sem recalcular o corpus.

import type { Projection } from './contract';
import { extentOf, layoutAtlas, type LayoutMap, type LayoutOptions, type Vec3 } from './layout';
import { layoutModels, workerAnchorPoses } from './modelsLayout';
import { BASE_LOCAL, noPlanoDaTela, paraMundoNaBase } from './screenBasis';
import {
  ALCANCE_DO_SISTEMA,
  SEPARACAO_ENTRE_EXECUCOES,
  layoutOperational,
  type QuorumSystem,
  operationalExtent,
  type OperationalDiagnostics,
  type OperationalSlots,
} from './operationalLayout';
import { layoutLiveCloud } from './liveLayout';
import { panelWorldExtentOf } from './panelScale';

/**
 * Quanto uma execução ancorada fica **fora** da casca do corpus.
 *
 * Menos que isto e o sistema local invade o território epistêmico, cobrindo as notas que
 * ele deveria comentar; muito mais e ele deixa de ler como pertencente àquele setor.
 *
 * Era 34 — um número escolhido à mão, e que envelheceu junto com a placa: quando ela
 * cresceu, cinco votos ancorados passaram a cair **dentro** de placas do corpus, porque
 * 34 unidades já não continham o sistema local. Agora a folga é derivada das duas coisas
 * que ela precisa conter: o alcance do sistema que se ancora, e a meia-diagonal da maior
 * placa do corpus, que é o que a casca epistêmica de fato estende além do centro do nó.
 * Assim ela volta a valer sozinha na próxima vez que a placa mudar de tamanho.
 */
/**
 * Degrau em que a coluna cresce: a diagonal da maior placa do corpus.
 *
 * Um degrau precisa ser grande o bastante para absorver o crescimento comum e pequeno o
 * bastante para a reserva não ficar folgada demais. A diagonal da placa do MOC é a
 * grandeza natural: abaixo dela, a diferença não cabe nem uma placa, e portanto não é
 * diferença que alguém veja.
 */
const DEGRAU_DA_COLUNA = (() => {
  const moc = panelWorldExtentOf('moc');
  return Math.hypot(moc.width, moc.height);
})();

const RAIO_DA_EXECUCAO_ANCORADA = (() => {
  const moc = panelWorldExtentOf('moc');
  return ALCANCE_DO_SISTEMA + Math.hypot(moc.width, moc.height) / 2;
})();

/**
 * Separação mínima entre duas execuções ancoradas.
 *
 * É a **mesma separação** que vale entre execuções vizinhas na grade, e não podia ser um
 * número próprio: quando a geometria do sistema local cresceu, as 30 unidades daqui
 * deixaram de bastar e cinco pares de execuções ancoradas passaram a se cobrir. Nem podia
 * ser o coeficiente da espiral, que é outra grandeza — usá-lo aqui abria o anel 90% mais
 * do que o necessário.
 *
 * O anel seria pior caso que a grade se as colunas subissem todas no mesmo eixo: onde o
 * anel corre nessa direção, duas vizinhas ficariam alinhadas e a decisão de uma
 * alcançaria o voto da outra. Elas não sobem — cada execução ancorada é girada para
 * crescer **para fora** do corpus, e aí o passo da grade basta.
 *
 * O anel podia ser bem menor e ficou: os votos de uma execução ancorada moram dentro do
 * raio do próprio sistema, e os vizinhos tangenciais só precisam de espaço para a
 * **placa**, não para a extensão inteira que a grade exige. Com o passo da grade o anel
 * abria ~4300 unidades no corpus real — o diâmetro do leque, que é o que o observador
 * vê, dominava a cena e espremia o corpus para o centro. O passo caiu para um terço da
 * grade — medido: raio xz ~1900, arestas ancoradas ~1800, anel em y ±2100. O preço é
 * densidade: vizinhos ficam a ~33 unidades e as placas (~50 de diagonal) se enterram até
 * ~35% — o anel lê como faixa contínua, não como fileira de painéis. O passo /4
 * enterrava 90% no setor concentrado e foi descartado; abaixo de /3 o anel deixa de ser
 * legível.
 */
const PASSO_ENTRE_ANCORADAS = SEPARACAO_ENTRE_EXECUCOES / 3;

/** Teto da elevação de uma execução ancorada, em radianos. Cerca de 50°. */
const ELEVACAO_MAXIMA = 0.88;


/**
 * O posto mais alto da cadeia, para a elevação não depender de **quantas** nuvens há.
 *
 * Era `total - 1`, e isso amarrava a altura de cada nuvem ao número de nuvens: juntar
 * provedores e modelos numa região só teria subido o quórum de 25° para 51° sem que
 * ninguém tivesse mexido no quórum. A cadeia epistêmica tem os postos que tem, e é ela
 * que decide a altura.
 */
const POSTO_MAXIMO = 2;

export interface ComposedLayout {
  /** Todas as posições, já no mundo composto. */
  positions: LayoutMap;
  /** Identidades por população, para medição, enquadramento e telemetria. */
  ids: Record<'corpus' | 'operacional' | 'modelos' | 'provedores', ReadonlySet<string>>;
  extent: Record<
    'corpus' | 'operacional' | 'modelos' | 'provedores',
    { radius: number; depth: number }
  >;
  /** Centro de cada população no mundo composto. */
  origin: Record<
    'corpus' | 'operacional' | 'modelos' | 'provedores',
    { x: number; y: number; z: number }
  >;
  diagnostics: OperationalDiagnostics;
  /** Ordinais das execuções, para gravar e devolver na próxima abertura. */
  slots: OperationalSlots;
  /** O miolo reservado à nuvem viva: onde ele está e que raio a composição lhe garante. */
  core: { origin: Vec3; radius: number };
  /**
   * A âncora dos trabalhadores, pronta para quem os possui — ADR-005.
   *
   * A composição já sabe o raio da casca e a origem da região de computação; quem
   * possui a entidade não precisa saber nenhum dos dois. O que atravessa é uma função:
   * dadas estas identidades, onde elas se assentam, já no mundo composto.
   */
  workerAnchors: (ids: readonly string[]) => LayoutMap;
}

/**
 * Um ponto da coluna, medido a partir do miolo. Positivo sobe; negativo desce.
 *
 * "Sobe" é no eixo da tela, e não no `+z` do mundo: as nuvens se assentam no plano da
 * visada canônica, e subir em `z` poria uma atrás da outra em vez de em cima. É o mesmo
 * eixo em que o nome de cada nuvem se assenta acima dela — se os dois divergissem, o
 * rótulo do quórum cairia dentro do corpus.
 */
function naColuna(altura: number): Vec3 {
  return {
    x: BASE_LOCAL.acima.x * altura,
    y: BASE_LOCAL.acima.y * altura,
    z: BASE_LOCAL.acima.z * altura,
  };
}


/**
 * Junta os dois frames.
 *
 * `previous` continua valendo só para o corpus: a memória espacial existe para que uma
 * nota nova não redesenhe o território, e uma execução de quórum não tem território
 * para preservar — ela é determinística a partir da própria ordem temporal, e reaplicar
 * posição gravada só faria uma execução ficar onde uma outra esteve.
 */
export function composeLayout(
  projection: Projection,
  options: LayoutOptions = {},
  previous?: LayoutMap,
  slotsConhecidos?: OperationalSlots,
): ComposedLayout {
  const corpus = layoutAtlas(projection, { ...options, include: 'epistemic' }, previous);
  const extensaoCorpus = extentOf(corpus);

  // A nuvem de modelos sai do observatório: ela não é feita de execuções, e sim de quem
  // as executa. Misturadas, o observatório crescia com 114 placas repetidas dos mesmos
  // 7 modelos, e nenhuma das duas leituras ficava disponível.
  //
  // Provedores e modelos, porém, voltaram a ser **uma região só**. Separá-los em duas
  // nuvens distantes punha as 193 arestas provedor→modelo todas no mesmo eixo, e era daí
  // que vinha a parede de fios: cada modelo mora agora junto do provedor que o reúne, e
  // a constelação de infraestrutura fica no miolo da região. Ver `modelsLayout.ts`.
  const computacao = layoutModels(projection);
  const idsProvedores = new Set(computacao.providers);
  const idsModelos = new Set(
    [...computacao.positions.keys()].filter((id) => !idsProvedores.has(id)),
  );

  const operacional = layoutOperational(projection, slotsConhecidos);
  const extensaoLocal = operationalExtent(operacional);

  // A nuvem viva é só a deliberação. Modelos e provedores ficam na região de
  // computação — uma nuvem só. Puxar o modelo para o centro de massa dos votos
  // partia o catálogo em dois e voltava a parede de fios entre as metades.
  const vivo = layoutLiveCloud(projection, operacional, computacao, slotsConhecidos);

  // As execuções que declaram assunto saem da grade e vão orbitar o corpus, no ângulo do
  // próprio assunto. Elas são calculadas antes de tudo que as consome porque o raio que
  // o conhecimento ocupa — e que decide onde ele se assenta — inclui esse anel.
  const ancoradas = ancorarExecucoes(projection, corpus, operacional, extensaoCorpus.radius);

  // **A coluna epistêmica.** De baixo para cima: conhecimento, raciocínio, quórum.
  //
  // A composição nasceu com o corpus na origem e as outras nuvens orbitando em volta, e a
  // razão era boa: é ele que dá razão a todo o resto. O que a disposição não dizia é que o
  // centro da cena é onde se olha primeiro, e o que se quer ver primeiro é o que está
  // acontecendo agora — não o acervo. Agora o miolo é do raciocínio, o conhecimento desce
  // para debaixo da nuvem que o julga, e a leitura de uma para a outra vira uma direção
  // só: sobe-se do que está escrito para o que está sendo decidido sobre ele.
  //
  // A coluna corre no eixo **da tela**, e não no `+z` do mundo, pelo mesmo motivo que o
  // nome de cada nuvem sobe por ele: as nuvens se assentam no plano da visada canônica, e
  // subir em `z` poria uma atrás da outra em vez de em cima.
  //
  // **A assimetria sobrevive**, e ela é o que mais importa aqui. O conhecimento se assenta
  // por grandezas dele — a reserva do miolo, que é o raio que ele mesmo mede, e o alcance
  // do seu anel de ancoradas. Nada do que a operação faça o move. O quórum é que se
  // afasta o quanto o seu próprio tamanho exigir, e é assim que mil nós de execução
  // continuam não movendo um MOC sequer.
  // A reserva é **quantizado**, e não o raio medido do corpus. Medido, ela mudaria a cada
  // nota nova: o corpus inteiro desceria alguns décimos de unidade, e com ele o quórum e a
  // computação, que se afastam da reserva. Uma nota nova reacomodaria o mundo. No degrau,
  // a coluna só se mexe quando o corpus cresce o bastante para ser notado, e a passagem é
  // rara e observável — a mesma escolha que o anel das âncoras já fazia.
  const miolo = {
    origin: { x: 0, y: 0, z: 0 },
    radius: Math.ceil(extensaoCorpus.radius / DEGRAU_DA_COLUNA) * DEGRAU_DA_COLUNA,
  };
  // O conhecimento ocupa mais que a própria casca: em volta dela corre o anel das
  // execuções ancoradas. A reserva conta com o anel **esteja ele ocupado ou não** — medir
  // o anel de verdade faria ancorar uma execução mover o corpus inteiro, que é exatamente
  // a dependência que esta composição existe para não ter. O raio do anel é derivado da
  // placa, não do dado, e por isso pode entrar na conta sem quebrar a assimetria.
  const raioDoConhecimento = miolo.radius + RAIO_DA_EXECUCAO_ANCORADA;
  const origemDoConhecimento = naColuna(
    -(miolo.radius + raioDoConhecimento + FOLGA_ENTRE_NUVENS_DA_CALOTA),
  );
  // O raio do quórum conta com a extensão da nuvem viva depois de assentada pela força.
  const raioDoQuorum = extensaoLocal.radius;
  // A nuvem viva — só as execuções — mora **acima** do corpus. Modelos e provedores
  // orbitam o miolo na calota, juntos.
  const origem = naColuna(miolo.radius + raioDoQuorum + FOLGA_ENTRE_NUVENS_DA_CALOTA);

  // A computação (provedores) não entra na coluna: instrumenta o corpus sem tocar em
  // conhecimento, e orbita o miolo pela calota — azimute próprio, elevação pelo posto. A
  // varredura recebe a coluna como já assentada, para se afastar dela em vez de descobrir
  // isso depois.
  const origemDaComputacao = orbitarNuvens(
    miolo.radius,
    [{ chave: 'modelos', raio: computacao.extent.radius, posto: POSTO_MAXIMO }],
    [{ centro: origemDoConhecimento, raio: raioDoConhecimento }],
  ).modelos!;

  const positions: LayoutMap = new Map(corpus);
  // A nuvem viva — execuções e os modelos que as avaliam — sai da simulação de forças já
  // no frame dela, e é transladada de uma vez para o topo da coluna. O sistema local de
  // cada execução anda rígido; o que a força moveu foi o centro de cada um. Os provedores
  // ficam na calota, fora daqui.
  const ancorados = new Set<string>();
  for (const sistema of operacional.systems) {
    if (sistema.panelNodeId !== null && ancoradas.has(sistema.panelNodeId)) {
      ancorados.add(sistema.panelNodeId);
    }
  }
  for (const sistema of operacional.systems) {
    if (sistema.panelNodeId === null) continue;
    if (ancorados.has(sistema.panelNodeId)) continue;
    const centroVivo = vivo.execucoes.get(sistema.panelNodeId);
    const centroOper = operacional.positions.get(sistema.panelNodeId);
    if (!centroVivo || !centroOper) continue;
    const ox = centroVivo.x - centroOper.x + origem.x;
    const oy = centroVivo.y - centroOper.y + origem.y;
    const oz = centroVivo.z - centroOper.z + origem.z;
    const nosDoSistema = [
      sistema.panelNodeId,
      ...sistema.decisionIds,
      ...sistema.looseVoteIds,
      ...[...sistema.votesByMember.values()].flat(),
    ];
    for (const id of nosDoSistema) {
      const p = operacional.positions.get(id);
      if (!p) continue;
      positions.set(id, { x: p.x + ox, y: p.y + oy, z: p.z + oz });
    }
  }
  for (const [id, p] of computacao.positions) {
    positions.set(id, {
      x: p.x + origemDaComputacao.x,
      y: p.y + origemDaComputacao.y,
      z: p.z + origemDaComputacao.z,
    });
  }

  // As ancoradas por último: elas já estão em coordenadas de mundo, e sobrescrevem a
  // posição que o observatório lhes daria.
  //
  // Todas as 38 ficavam na grade do observatório, a 366 unidades do corpus, inclusive as
  // 9 que avaliaram uma nota específica. Quem olhava a nota não tinha como saber que ela
  // passou por quórum, e quem olhava o quórum não via sobre o quê. Agora cada uma dessas
  // 9 orbita o corpus **no ângulo do próprio assunto**, fora da casca epistêmica.
  for (const [id, p] of ancoradas) positions.set(id, p);

  const idsCorpus = new Set(corpus.keys());
  // O conhecimento desce em bloco para o lugar que a coluna lhe deu.
  //
  // Rígido, e no fim: âncoras, territórios e as execuções que se ancoraram no assunto
  // andam juntos, então nada do que o corpus organizou muda de forma. O que muda é onde
  // ele mora.
  for (const id of [...idsCorpus, ...ancoradas.keys()]) {
    const p = positions.get(id);
    if (!p) continue;
    positions.set(id, {
      x: p.x + origemDoConhecimento.x,
      y: p.y + origemDoConhecimento.y,
      z: p.z + origemDoConhecimento.z,
    });
  }
  const idsOperacional = new Set(
    [...operacional.positions.keys()].filter(
      (id) => !idsModelos.has(id) && !idsProvedores.has(id),
    ),
  );

  return {
    positions,
    ids: {
      corpus: idsCorpus,
      operacional: idsOperacional,
      modelos: idsModelos,
      provedores: idsProvedores,
    },
    extent: {
      corpus: extensaoCorpus,
      operacional: extensaoLocal,
      modelos: computacao.extent,
      provedores: computacao.providerExtent,
    },
    origin: {
      corpus: origemDoConhecimento,
      operacional: origem,
      modelos: origemDaComputacao,
      provedores: origemDaComputacao,
    },
    // O miolo que o conhecimento desocupou, e que a nuvem viva ocupa: onde ele fica e
    // quanto ele mede. Sem isto, a camada viva teria de adivinhar de que tamanho é o
    // buraco que lhe reservaram, e adivinhou por dois ciclos — ela se assentava "no que
    // sobrava", medindo os centros das outras nuvens.
    core: miolo,
    diagnostics: operacional.diagnostics,
    slots: operacional.slots,
    // A âncora dos trabalhadores já no mundo composto: o anel é calculado no frame da
    // região de computação e transladado pela origem dela, exatamente como as posições
    // de modelo e provedor logo acima. Quem a consome não precisa saber de nenhum dos
    // dois passos — só faz a pergunta.
    workerAnchors: (ids) => {
      const noFrame = workerAnchorPoses(ids, computacao.shellRadius);
      const compostas: LayoutMap = new Map();
      for (const [id, ponto] of noFrame) {
        compostas.set(id, {
          x: ponto.x + origemDaComputacao.x,
          y: ponto.y + origemDaComputacao.y,
          z: ponto.z + origemDaComputacao.z,
        });
      }
      return compostas;
    },
  };
}

/**
 * Reposiciona, em bloco, cada execução que declara assunto no corpus.
 *
 * O deslocamento é **rígido**: o sistema local inteiro — painel, votos e decisão — anda
 * junto, então a geometria que o observatório construiu continua valendo, e a leitura de
 * "painel embaixo, decisão em cima" não muda de lugar para lugar.
 *
 * Todas ficam no mesmo raio, formando um anel em volta do atlas, e o **ângulo** de cada
 * uma é o do seu assunto: a posição já diz de quem a execução fala, sem precisar seguir
 * a aresta com os olhos.
 *
 * Ângulo bruto, porém, colide. Duas execuções sobre a mesma nota caíam exatamente no
 * mesmo ponto, e duas sobre notas vizinhas ficavam a 1,3 unidade uma da outra — medido
 * no corpus real. Por isso os ângulos passam por uma varredura que garante separação
 * mínima: a ordem angular, que é o que carrega o significado, é preservada; o que cede
 * é a precisão do ângulo, que ninguém lê como número.
 */
function ancorarExecucoes(
  projection: Projection,
  corpus: LayoutMap,
  operacional: { positions: LayoutMap; systems: QuorumSystem[] },
  raioDoCorpus: number,
): LayoutMap {
  const assunto = new Map<string, string>();
  for (const edge of projection.edges) {
    if (edge.matchedBy !== 'quorum-entity') continue;
    if (!assunto.has(edge.source)) assunto.set(edge.source, edge.target);
  }
  const movidas: LayoutMap = new Map();
  if (assunto.size === 0) return movidas;

  const projetar = (v: { x: number; y: number; z: number }, eixo: typeof BASE_LOCAL.direita) =>
    v.x * eixo.x + v.y * eixo.y + v.z * eixo.z;

  // Ângulo desejado por execução: o do assunto, no plano da tela.
  const candidatas: { sistema: QuorumSystem; angulo: number; elevacao: number }[] = [];
  for (const sistema of operacional.systems) {
    if (sistema.panelNodeId === null) continue;
    const alvo = assunto.get(sistema.panelNodeId);
    if (alvo === undefined) continue;
    const posicaoDoAlvo = corpus.get(alvo);
    if (!posicaoDoAlvo) continue;
    // Assunto exatamente no centro não tem direção própria: fica onde o observatório o
    // pôs, em vez de receber um ângulo inventado.
    if (Math.hypot(posicaoDoAlvo.x, posicaoDoAlvo.y, posicaoDoAlvo.z) < 1e-6) continue;
    const direcao = noPlanoDaTela(posicaoDoAlvo);
    // A elevação vem da **profundidade do próprio assunto**. Sem ela o anel era um
    // círculo plano, e ele passou a ser a parte chata da cena depois que o observatório
    // virou casca: medido, 4,6% da variância em profundidade nos painéis da grade contra
    // 1,3% quando o anel entrava na conta. Com ela, a execução fica na direção do assunto
    // nos três eixos — que é o que a posição já queria dizer.
    const profundidadeDoAlvo = projetar(posicaoDoAlvo, BASE_LOCAL.profundidade);
    candidatas.push({
      sistema,
      angulo: Math.atan2(projetar(direcao, BASE_LOCAL.acima), projetar(direcao, BASE_LOCAL.direita)),
      // Com teto: o anel precisa caber no paralelo mais apertado que ele contém, e uma
      // única execução perto do polo obrigava o raio inteiro a inflar — medido, 456
      // unidades contra 142 da casca. O teto preserva a leitura (a execução continua do
      // lado do assunto, e acima ou abaixo dele) sem deixar um caso extremo mandar no
      // tamanho da nuvem.
      elevacao: Math.max(
        Math.min(
          Math.atan2(profundidadeDoAlvo, Math.hypot(posicaoDoAlvo.x, posicaoDoAlvo.y, posicaoDoAlvo.z)),
          ELEVACAO_MAXIMA,
        ),
        -ELEVACAO_MAXIMA,
      ),
    });
  }
  if (candidatas.length === 0) return movidas;

  // O raio cresce até o anel caber. Fixo, ele dava a volta: nove execuções com a
  // separação necessária pediam 6,4 radianos num círculo de 6,28, e a última encostava
  // exatamente na primeira — quatro pares coincidentes, painel sobre painel.
  // O raio cresce até o anel caber. Fixo, ele dava a volta: nove execuções com a
  // separação necessária pediam 6,4 radianos num círculo de 6,28, e a última encostava
  // exatamente na primeira. E a conta tem de ser feita no **paralelo mais apertado**: uma
  // execução elevada mora num círculo menor, e catorze delas juntas não cabiam onde
  // catorze no equador caberiam.
  const menorParalelo = Math.max(
    Math.min(...candidatas.map(({ elevacao }) => Math.cos(elevacao))),
    0.2,
  );
  const raio = Math.max(
    raioDoCorpus + RAIO_DA_EXECUCAO_ANCORADA,
    (candidatas.length * PASSO_ENTRE_ANCORADAS) / (2 * Math.PI * menorParalelo),
  );

  // Varredura: em ordem angular, cada uma cede o mínimo para não encostar na anterior.
  //
  // O passo angular necessário depende da **elevação**: a execução mora num paralelo de
  // raio `R·cos(elevação)`, e quanto mais alto o paralelo, menor o arco que um mesmo
  // ângulo percorre. Com um mínimo único, as elevadas encostavam — medido, um par no
  // corpus real e catorze quando os assuntos se concentram num setor.
  const arcoDe = (elevacao: number) => Math.max(raio * Math.cos(elevacao), raio * 0.2);
  candidatas.sort((a, b) => a.angulo - b.angulo || a.sistema.panelId.localeCompare(b.sistema.panelId));
  let minimo = PASSO_ENTRE_ANCORADAS / raio;
  for (let i = 1; i < candidatas.length; i += 1) {
    const anterior = candidatas[i - 1]!;
    const atual = candidatas[i]!;
    const passo =
      PASSO_ENTRE_ANCORADAS / Math.min(arcoDe(anterior.elevacao), arcoDe(atual.elevacao));
    minimo = Math.max(minimo, passo);
    if (atual.angulo - anterior.angulo < passo) atual.angulo = anterior.angulo + passo;
  }
  // A varredura empurra para frente e não olha para trás: onde os assuntos se concentram
  // num setor, o acúmulo passa da volta inteira e a última execução vai parar em cima da
  // primeira. Fechou? Então o setor não comporta o ângulo de cada uma, e a distribuição
  // uniforme é o menos ruim — perde-se precisão angular, não se perde nenhuma execução
  // debaixo de outra.
  const primeira = candidatas[0]!.angulo;
  const ultima = candidatas[candidatas.length - 1]!.angulo;
  if (ultima - primeira > 2 * Math.PI - minimo) {
    candidatas.forEach((candidata, indice) => {
      candidata.angulo = primeira + (2 * Math.PI * indice) / candidatas.length;
    });
  }

  for (const { sistema, angulo, elevacao } of candidatas) {
    const painel = operacional.positions.get(sistema.panelNodeId!);
    if (!painel) continue;
    const noAnel = Math.cos(elevacao) * raio;
    const destino = paraMundoNaBase(
      { x: 0, y: 0, z: 0 },
      Math.cos(angulo) * noAnel,
      Math.sin(angulo) * noAnel,
      Math.sin(elevacao) * raio,
    );
    // A execução é **girada** para crescer na direção radial, e não só transladada.
    //
    // O sistema local sobe sempre no mesmo eixo da tela. Traduzido sem girar, todas as
    // execuções do anel ficavam paralelas: onde o anel corre nessa direção, a decisão de
    // uma alcançava o voto da vizinha, e nas laterais elas apontavam de lado sem relação
    // com o corpus. Girando, o painel fica junto do assunto e o processo se afasta dele —
    // e o anel inteiro lê como pétalas, cada uma apontando para fora.
    const giro = angulo - Math.PI / 2;
    const cos = Math.cos(giro);
    const sen = Math.sin(giro);
    for (const id of [
      sistema.panelNodeId!,
      ...sistema.decisionIds,
      ...sistema.looseVoteIds,
      ...[...sistema.votesByMember.values()].flat(),
    ]) {
      const local = operacional.positions.get(id);
      if (!local) continue;
      const relativo = { x: local.x - painel.x, y: local.y - painel.y, z: local.z - painel.z };
      // O giro acontece no plano da tela; a componente de profundidade é preservada,
      // porque é ela que dá a paralaxe do leque e não tem por que rodar.
      const lateral = projetar(relativo, BASE_LOCAL.direita);
      const alto = projetar(relativo, BASE_LOCAL.acima);
      const fundo = projetar(relativo, BASE_LOCAL.profundidade);
      movidas.set(
        id,
        paraMundoNaBase(destino, lateral * cos - alto * sen, lateral * sen + alto * cos, fundo),
      );
    }
  }
  return movidas;
}

/**
 * Onde cada nuvem operacional se assenta em volta do corpus.
 *
 * É a calota das âncoras do corpus, aplicada um nível acima: o mesmo rigor que decide
 * onde um MOC fica decide onde uma nuvem fica. O corpus ocupa o centro porque é ele que
 * dá razão às outras — deliberação, modelos e provedores existem para servi-lo, e
 * nenhuma delas se sustenta sozinha.
 *
 * **A ordem é epistêmica, não geométrica.** A deliberação vem primeiro porque age sobre
 * o corpus, e as suas arestas terminam dentro dele; os modelos vêm depois porque são
 * quem executa a deliberação; os provedores por último, porque reúnem modelos e não
 * tocam em conhecimento nenhum. Essa ordem se lê na **altura**: subir a calota é
 * percorrer a cadeia que produz o corpus, do que o toca ao que só o instrumenta.
 *
 * A primeira nuvem pode declarar a direção que já calculou por conta própria: o
 * observatório é assentado no lado das entidades que ele referencia, e essa decisão é
 * dele, não desta calota. As demais repartem o que sobra do azimute.
 */
function orbitarNuvens(
  raioDoMiolo: number,
  nuvens: {
    chave: string;
    raio: number;
    direcao?: Vec3;
    azimuteDe?: string;
    /** Posto na cadeia, para a elevação. Fracionário quando se quer ficar entre dois. */
    posto?: number;
    /** Giro extra sobre o azimute que o índice daria, em radianos. */
    giro?: number;
  }[],
  /** Nuvens que já têm lugar — a coluna — e de que a calota precisa se afastar. */
  jaAssentadas: readonly { centro: Vec3; raio: number }[] = [],
): Record<string, Vec3> {
  const saida: Record<string, Vec3> = {};
  const total = Math.max(nuvens.length, 1);
  // Azimute da primeira, quando ela chega com direção própria; senão, um lado fixo.
  const referencia = nuvens[0]?.direcao ? noPlanoDaTela(nuvens[0].direcao) : BASE_LOCAL.direita;
  const azimuteBase = Math.atan2(
    referencia.x * BASE_LOCAL.acima.x +
      referencia.y * BASE_LOCAL.acima.y +
      referencia.z * BASE_LOCAL.acima.z,
    referencia.x * BASE_LOCAL.direita.x +
      referencia.y * BASE_LOCAL.direita.y +
      referencia.z * BASE_LOCAL.direita.z,
  );
  const azimutes = new Map<string, number>();
  nuvens.forEach((nuvem, indice) => {
    // O azimute é do próprio índice, salvo quando a nuvem declara que acompanha outra —
    // e ela declara quando é lá que as ligações dela vão.
    const azimute =
      (nuvem.azimuteDe !== undefined ? azimutes.get(nuvem.azimuteDe) : undefined) ??
      azimuteBase + (2 * Math.PI * indice) / total + (nuvem.giro ?? 0);
    azimutes.set(nuvem.chave, azimute);
    // **A ordem epistêmica mora na altura, não no raio.**
    //
    // No raio ela brigava com o critério que decide o azimute: uma nuvem pequena e
    // terminal na cadeia — os provedores — era empurrada para 659 unidades do centro só
    // para ficar depois dos modelos, e as suas únicas arestas atravessavam a cena
    // inteira. Na altura as duas regras convivem: quem liga fica perto no plano, e a
    // cadeia que produz o corpus se lê subindo.
    //
    // O divisor é o posto mais alto **declarado**, e não o número de nuvens: a cadeia
    // epistêmica não encolhe porque duas populações passaram a dividir uma região.
    const elevacao = ELEVACAO_DA_CALOTA * ((nuvem.posto ?? indice) / POSTO_MAXIMO);
    const assentar = (distancia: number): Vec3 => {
      const noPlano = Math.cos(elevacao) * distancia;
      return paraMundoNaBase(
        { x: 0, y: 0, z: 0 },
        Math.cos(azimute) * noPlano,
        Math.sin(azimute) * noPlano,
        Math.sin(elevacao) * distancia,
      );
    };

    // **A folga vale entre quaisquer duas nuvens, e não só entre as que se acompanham.**
    //
    // A varredura existia apenas para quem declarava `azimuteDe`, e isso bastava enquanto
    // as três nuvens ficavam a 120° umas das outras. Deixou de bastar: com o quórum girado
    // para não ficar colinear com a computação, as duas passaram a 54° de azimute, e a
    // diferença de altura sozinha não responde por sobreposição. Quem chega depois se
    // afasta até as bordas não se tocarem — no eixo em que já está, sem trocar de lado.
    let distancia = raioDoMiolo + nuvem.raio + FOLGA_ENTRE_NUVENS_DA_CALOTA;
    const anteriores = [
      ...jaAssentadas,
      ...nuvens
        .slice(0, indice)
        .map((outra) => ({ centro: saida[outra.chave], raio: outra.raio }))
        .filter((outra): outra is { centro: Vec3; raio: number } => outra.centro !== undefined),
    ];
    for (let passo = 0; passo < 120; passo += 1) {
      const p = assentar(distancia);
      const apertada = anteriores.some((outra) => {
        // Bordas encostando basta entre duas nuvens que se leem juntas — é por isso que
        // quem compartilha azimute não paga folga: uma é a continuação da outra, e somar
        // folga aqui só afastaria o que se quer perto.
        const exigido =
          nuvem.raio + outra.raio + (nuvem.azimuteDe === undefined ? FOLGA_ENTRE_NUVENS_DA_CALOTA : 0);
        return (
          Math.hypot(p.x - outra.centro.x, p.y - outra.centro.y, p.z - outra.centro.z) < exigido
        );
      });
      if (!apertada) break;
      distancia += FOLGA_ENTRE_NUVENS_DA_CALOTA / 3;
    }
    saida[nuvem.chave] = assentar(distancia);
  });
  return saida;
}

/**
 * Amplitude da calota das nuvens, em radianos.
 *
 * Maior do que era: com a folga menor, é a altura que passa a fazer o trabalho de separar
 * as nuvens, e não a distância. Ganha-se a mesma leitura da ordem epistêmica com a
 * nebulosa inteira mais junta.
 */
const ELEVACAO_DA_CALOTA = 0.78;

/**
 * Folga entre a borda do corpus e a borda de cada nuvem.
 *
 * Caiu de 70 para 26. A folga existe para as bordas não se tocarem, e o raio de cada
 * nuvem já responde por isso — o resto era espaço vazio, e ele afastava justamente as
 * nuvens pequenas, que ficavam pontos distantes ligados por arestas longas.
 */
const FOLGA_ENTRE_NUVENS_DA_CALOTA = 26;
