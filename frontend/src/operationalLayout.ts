// O observatório operacional: um frame de coordenadas próprio, ao lado do atlas.
//
// Até 3.5-A a camada viva entrava no mesmo espaço do corpus e pagava dois preços. O
// primeiro era do corpus: os 278 nós de quórum contavam para o dimensionamento do anel
// de âncoras, que ia de 87 para 148 unidades, e **todo MOC se movia** por causa de dado
// que nem é do corpus — exatamente a instabilidade que o layout ancorado existe para
// impedir. O segundo era da própria operação: sem âncora e sem domínio, os 278 caíam
// num único agrupamento e viravam uma bola indistinguível, apesar de o contrato já
// declarar quatro tipos e o `panelId` de cada nó.
//
// Aqui os dois preços somem pela mesma decisão: a operação tem frame próprio, e dentro
// dele cada execução é um sistema local.
//
// **A progressão sobe na tela.** O painel na base, os avaliadores abrindo em leque
// acima dele, o voto de cada avaliador adiante de quem o produziu, e a decisão no topo.
// Ler de baixo para cima é ler a execução na ordem em que ela aconteceu.
//
// O eixo era `z` do mundo, e estava errado por um motivo que só aparece ao clicar: `z`
// é a componente dominante da visada canônica, então a coluna empilhava **em
// profundidade**. A decisão ficava entre a câmera e o voto, e quem clicava num voto
// selecionava a decisão. Agora a progressão usa a base da tela — ver `BASE_LOCAL`.
//
// **A espiral guarda a ordem de chegada.** As execuções se assentam numa espiral de
// Fermat, as primeiras no miolo e as seguintes para fora. O índice de cada uma é um
// ordinal atribuído na primeira vez que ela é vista e **gravado**: quem já tem ordinal
// mantém o seu, e quem chega ocupa o menor livre. Ordenar por data produziria a mesma
// espiral no caso comum e quebraria nos outros — importação histórica, correção de
// `created_at`, empate de segundo ou relógio fora de ordem deslocariam execuções já
// assentadas. A data informa a leitura; ela não decide a posição.

import type { EntityKind, Projection, ProjectionNode } from './contract';
import { type LayoutMap, type Vec3 } from './layout';
import { isModelNode } from './modelsLayout';
import { panelWorldExtentOf } from './panelScale';
import { shapeExtentRatio, type PanelShape } from './panelShapes';
import { paraMundoNaBase } from './screenBasis';

/**
 * Versão do algoritmo de posicionamento.
 *
 * Entra na chave do cache de layout. Mudar a geometria sem mudar este número faria a
 * cena reabrir com posições da versão anterior e o defeito pareceria não corrigido —
 * foi o risco registrado no roadmap, e este contador é a resposta a ele.
 */
export const OPERATIONAL_LAYOUT_VERSION = 6;

const ANGULO_AUREO = Math.PI * (3 - Math.sqrt(5));

/**
 * Geometria do sistema local, **derivada do tamanho da placa**.
 *
 * Os números eram escolhidos à mão, e envelheceram no dia em que o painel de quórum
 * deitou para o texto caber: os votos ficaram num raio de 10,2 com 11,8 de largura, e a
 * decisão a 5,8 do voto com 7,8 de altura — encostados, e nada no código dizia isso.
 * Amarrando a geometria à extensão real, mudar a proporção do painel volta a mexer no
 * espaçamento sozinho, que é como deveria ter sido desde o começo.
 *
 * `FOLGA` é o quanto de placa se quer entre duas placas. Um pouco mais que meia é o que
 * separa "vizinhos" de "empilhados" sem espalhar a execução a ponto de ela deixar de
 * ler como um conjunto.
 */
const FOLGA_ENTRE_PLACAS = 0.62;
const SISTEMA = (() => {
  // A medida é a da **silhueta**, não a da caixa da placa. Medindo pela caixa, três
  // votos pareciam caber lado a lado enquanto os triângulos deles já se tocavam: o
  // triângulo ocupa 1,52 vez a largura da caixa, e o losango da decisão, 1,41.
  const caixa = panelWorldExtentOf('quorum');
  const formas: PanelShape[] = ['triangulo', 'losango', 'octogono'];
  const maior = formas.reduce(
    (acumulado, forma) => {
      const razao = shapeExtentRatio(forma);
      return {
        width: Math.max(acumulado.width, razao.width),
        height: Math.max(acumulado.height, razao.height),
      };
    },
    { width: 1, height: 1 },
  );
  const placa = { width: caixa.width * maior.width, height: caixa.height * maior.height };
  const passo = placa.height * (1 + FOLGA_ENTRE_PLACAS);
  return {
    /** Raio do leque de avaliadores em torno do painel. */
    raioMembro: placa.width * 0.72,
    /**
     * Raio do voto.
     *
     * Com `n` avaliadores abrindo em meia volta, dois vizinhos ficam separados por
     * `2·R·sen(π/2n)`. Para três — o caso normal — isso dá exatamente `R`, então o raio
     * precisa valer uma largura de placa mais a folga, ou os votos vizinhos se cobrem.
     */
    raioVoto: placa.width * (1 + FOLGA_ENTRE_PLACAS * 0.5),
    zPainel: 0,
    zMembro: passo * 0.55,
    zVoto: passo,
    zDecisao: passo * 2,
    /** Abertura angular entre votos de um mesmo avaliador. */
    leque: 0.22,
  } as const;
})();

/**
 * Passo da espiral entre execuções.
 *
 * Numa espiral de Fermat com `r = passo · √i` a distância entre vizinhos tende ao
 * passo. O sistema local tem raio horizontal `raioVoto`, então o passo precisa passar
 * de dois raios para os leques não se tocarem; a folga que sobra é deliberada e
 * pequena, porque espalhar mais não acrescentaria leitura.
 */
/**
 * Raio que acomoda `quantos` painéis numa **meia** volta sem que dois se toquem.
 *
 * Com `n` itens em meia volta, dois vizinhos ficam separados por `2·R·sen(π/2n)`; pedir
 * que isso passe da largura da silhueta com folga dá o raio. É o que faz uma execução de
 * seis votos abrir em vez de empilhar — e é por não existir que ela empilhava.
 */
function raioDoArco(quantos: number, minimo: number): number {
  if (quantos <= 1) return minimo;
  const largura =
    panelWorldExtentOf('quorum').width * shapeExtentRatio('triangulo').width * (1 + FOLGA_ENTRE_PLACAS);
  return Math.max(minimo, largura / (2 * Math.sin(Math.PI / (2 * quantos))));
}

/**
 * O alcance de um sistema local: metade da caixa que ele ocupa, com placa e tudo.
 *
 * Duas execuções não se tocam quando seus centros distam de dois alcances. É a única
 * grandeza que o resto do espaçamento precisa conhecer.
 */
const MEDIDA_DO_SISTEMA = (() => {
  const placa = panelWorldExtentOf('quorum');
  return {
    lateral: SISTEMA.raioVoto + (placa.width * shapeExtentRatio('triangulo').width) / 2,
    vertical: SISTEMA.zDecisao + (placa.height * shapeExtentRatio('losango').height) / 2,
  };
})();
export const ALCANCE_DO_SISTEMA = Math.max(MEDIDA_DO_SISTEMA.lateral, MEDIDA_DO_SISTEMA.vertical);
const ALCANCE_LATERAL_DO_SISTEMA = MEDIDA_DO_SISTEMA.lateral;

/**
 * Distância entre centros de duas execuções vizinhas.
 *
 * O alcance mede a caixa inteira do sistema, e ela é alta e estreita: a coluna sobe do
 * painel até a decisão. Separar pelo alcance vertical em **todas** as direções espalhava
 * a grade muito além do necessário na horizontal, e o observatório lia como um campo
 * vazio com execuções distantes. Aqui a separação sai do alcance lateral, e a folga
 * vertical vem da curvatura da calota, que afasta vizinhos em profundidade.
 */
export const SEPARACAO_ENTRE_EXECUCOES = ALCANCE_LATERAL_DO_SISTEMA * 2 * 0.98;


/**
 * Coeficiente da espiral de Fermat — **não** a distância entre vizinhas.
 *
 * Era esta a confusão que inflou o mundo. Numa espiral `r = c·√i` os pontos ficam a
 * cerca de `1,9·c` um do outro: passar a separação desejada como `c` espalhou as 29
 * execuções por um raio de 458 unidades quando 215 bastavam, e foi isso que levou o
 * enquadramento a 9 mil unidades. Dividindo pelo fator, a separação real é a pedida e
 * o observatório encolhe pela metade sem que duas execuções se aproximem.
 */
const FATOR_DA_ESPIRAL = 1.68;
export const PASSO_EXECUCAO = SEPARACAO_ENTRE_EXECUCOES / FATOR_DA_ESPIRAL;

export interface QuorumSystem {
  panelId: string;
  panelNodeId: string | null;
  /**
   * Os avaliadores da execução, pela identidade **canônica** deles.
   *
   * Eram nós desenhados dentro de cada execução, e por isso os mesmos 7 modelos
   * apareciam 114 vezes. Agora são identidades do registro de modelos, que mora em
   * nuvem própria: aqui elas só organizam o leque de votos, e nenhuma placa é
   * assentada por elas.
   */
  memberIds: string[];
  /** Votos por avaliador, na ordem estável do identificador. */
  votesByMember: Map<string, string[]>;
  /** Votos que não declaram avaliador nenhum. */
  looseVoteIds: string[];
  decisionIds: string[];
  /** Data da execução, para a ordenação temporal. */
  createdAt: string | null;
}

export interface OperationalDiagnostics {
  systems: number;
  nodes: number;
  /** Quantas execuções mantiveram o ordinal gravado, e quantas ganharam um novo. */
  slotsReaproveitados?: number;
  slotsNovos?: number;
  /**
   * Nós operacionais sem execução a que pertencer.
   *
   * Órfão é reportado, nunca espalhado em silêncio: um nó de quórum sem painel é
   * defeito de projeção, e escondê-lo numa posição plausível transformaria o defeito
   * em ruído visual que ninguém liga à causa.
   */
  orphans: string[];
  /** Votos sem aresta de avaliador. Assentados em posição própria, e contados. */
  votesWithoutMember: string[];
}

export interface OperationalPlacement {
  positions: LayoutMap;
  systems: QuorumSystem[];
  diagnostics: OperationalDiagnostics;
  /** Ordinal de cada execução, para ser gravado e devolvido na próxima abertura. */
  slots: OperationalSlots;
}

/** `panelId` → ordinal na espiral. Persistido; ver `atribuirSlots`. */
export type OperationalSlots = ReadonlyMap<string, number>;

/**
 * Decide o ordinal de cada execução, e essa decisão é para sempre.
 *
 * A primeira versão ordenava por data e usava o índice como posição. Isso só é estável
 * para inserção cronologicamente posterior — que é o caso comum, e não é o único.
 * Importar uma execução histórica, corrigir um `created_at`, dois painéis no mesmo
 * segundo ou um relógio fora de ordem mudavam o índice e **deslocavam execuções já
 * assentadas**.
 *
 * Agora o ordinal é atribuído uma vez e gravado. Quem já tem ordinal mantém o seu, sem
 * exceção; quem chega ocupa o menor ordinal livre, na ordem cronológica, de modo que o
 * caso comum continua produzindo a mesma espiral de antes. A data informa a leitura
 * temporal — quem entrou primeiro está mais no miolo — mas deixou de ser a fonte da
 * posição.
 */
export function atribuirSlots(
  systems: QuorumSystem[],
  conhecidos: OperationalSlots = new Map(),
): Map<string, number> {
  const slots = new Map<string, number>();
  const ocupados = new Set<number>();
  for (const sistema of systems) {
    const anterior = conhecidos.get(sistema.panelId);
    if (anterior !== undefined && Number.isInteger(anterior) && anterior >= 0) {
      slots.set(sistema.panelId, anterior);
      ocupados.add(anterior);
    }
  }
  let proximo = 0;
  for (const sistema of systems) {
    if (slots.has(sistema.panelId)) continue;
    while (ocupados.has(proximo)) proximo += 1;
    slots.set(sistema.panelId, proximo);
    ocupados.add(proximo);
  }
  return slots;
}

const KINDS_DE_QUORUM: ReadonlySet<EntityKind> = new Set<EntityKind>([
  'quorum-panel',
  'quorum-member',
  'quorum-vote',
  'quorum-decision',
]);

export function isOperational(node: ProjectionNode): boolean {
  return node.layer === 'operational';
}

function panelIdOf(node: ProjectionNode): string | null {
  const declarado = node.operational?.panelId;
  return typeof declarado === 'string' && declarado !== '' ? declarado : null;
}

/**
 * Agrupa a camada viva por execução, pelo `panelId` que o contrato já declara.
 *
 * Agrupar pelo campo declarado, e não por caminho do identificador, é o que impede
 * este módulo de depender do formato do id — que é convenção do backend e pode mudar
 * sem aviso. As arestas entram só para o vínculo voto↔avaliador, que é o único que o
 * campo não carrega.
 */
export function groupQuorumSystems(projection: Projection): {
  systems: QuorumSystem[];
  diagnostics: OperationalDiagnostics;
} {
  // A nuvem de modelos é operacional, mas não é do observatório: ela tem frame próprio.
  // Sem esta exclusão, cada modelo do registro — que não pertence a execução nenhuma —
  // seria contado como nó órfão, e o diagnóstico passaria a acusar defeito onde há
  // separação deliberada.
  const operacionais = projection.nodes.filter((node) => isOperational(node) && !isModelNode(node));
  const porTipo = new Map<string, ProjectionNode[]>();
  for (const node of operacionais) {
    const lista = porTipo.get(node.kind) ?? [];
    lista.push(node);
    porTipo.set(node.kind, lista);
  }

  const paineis = (porTipo.get('quorum-panel') ?? []).filter((node) => panelIdOf(node));
  const porPanelId = new Map<string, QuorumSystem>();
  for (const painel of paineis) {
    const panelId = panelIdOf(painel)!;
    // Dois painéis com o mesmo `panelId` seriam deriva do backend; o primeiro em ordem
    // estável de identificador ganha, e o segundo cai como órfão junto com o resto.
    if (porPanelId.has(panelId)) continue;
    porPanelId.set(panelId, {
      panelId,
      panelNodeId: painel.id,
      memberIds: [],
      votesByMember: new Map(),
      looseVoteIds: [],
      decisionIds: [],
      createdAt: painel.createdAt,
    });
  }

  const orphans: string[] = [];
  const sistemaDe = (node: ProjectionNode): QuorumSystem | null => {
    const panelId = panelIdOf(node);
    if (panelId === null) return null;
    return porPanelId.get(panelId) ?? null;
  };

  // Duas passagens: os avaliadores primeiro, os votos depois. Uma passagem só faria a
  // ligação voto↔avaliador depender da ordem em que os nós aparecem — e ordem de
  // entrada não pode decidir layout, que é justamente um dos invariantes deste
  // incremento.
  const ordenados = [...operacionais].sort((a, b) => a.id.localeCompare(b.id));

  // Quem votou vem do **próprio voto**, que carrega provedor e endpoint, e não mais de
  // uma aresta até um nó de avaliador. A aresta existia porque o avaliador era um nó
  // local da execução; deixando de ser, ela mandaria 112 linhas atravessarem a cena
  // até a nuvem de modelos para dizer o que o voto já diz de si.
  const avaliadorDoVoto = new Map<string, string>();
  for (const node of ordenados) {
    if (node.kind !== 'quorum-vote') continue;
    const provider = node.operational?.provider;
    const endpoint = node.operational?.endpoint;
    if (provider === undefined || endpoint === undefined) continue;
    avaliadorDoVoto.set(node.id, `op/model/${provider}/${endpoint}`);
  }
  // E os participantes da execução são os modelos a que o painel se liga.
  const participantes = new Map<string, Set<string>>();
  for (const edge of projection.edges) {
    if (edge.matchedBy !== 'quorum-model') continue;
    const conjunto = participantes.get(edge.source);
    if (conjunto) conjunto.add(edge.target);
    else participantes.set(edge.source, new Set([edge.target]));
  }


  for (const node of ordenados) {
    if (!KINDS_DE_QUORUM.has(node.kind)) {
      orphans.push(node.id);
      continue;
    }
    const sistema = sistemaDe(node);
    if (node.kind === 'quorum-panel') {
      if (!sistema || sistema.panelNodeId !== node.id) orphans.push(node.id);
      continue;
    }
    if (!sistema) {
      orphans.push(node.id);
      continue;
    }
  }
  for (const sistema of porPanelId.values()) {
    if (sistema.panelNodeId === null) continue;
    sistema.memberIds = [...(participantes.get(sistema.panelNodeId) ?? [])].sort();
  }

  for (const node of ordenados) {
    if (node.kind !== 'quorum-vote' && node.kind !== 'quorum-decision') continue;
    const sistema = sistemaDe(node);
    if (!sistema) continue; // já contado como órfão na primeira passagem
    if (node.kind === 'quorum-decision') sistema.decisionIds.push(node.id);
    else {
      // O voto acompanha o avaliador que o produziu — mas só se os dois estiverem na
      // mesma execução. Um vínculo cruzado poria o voto de um painel dentro de outro,
      // que é a mistura que a integridade desta camada precisa impedir; nesse caso o
      // voto fica solto no próprio painel e entra no diagnóstico.
      const membro = avaliadorDoVoto.get(node.id);
      if (membro !== undefined) {
        const lista = sistema.votesByMember.get(membro) ?? [];
        lista.push(node.id);
        sistema.votesByMember.set(membro, lista);
      } else {
        sistema.looseVoteIds.push(node.id);
      }
    }
  }

  // Ordem temporal, com o identificador desempatando: é ela que decide o índice de
  // cada execução na espiral, e portanto a posição. Sem desempate estável, duas
  // execuções do mesmo instante trocariam de lugar entre recargas.
  const systems = [...porPanelId.values()].sort((a, b) => {
    const data = (a.createdAt ?? '').localeCompare(b.createdAt ?? '');
    return data !== 0 ? data : a.panelId.localeCompare(b.panelId);
  });
  for (const sistema of systems) {
    sistema.memberIds.sort();
    sistema.decisionIds.sort();
    sistema.looseVoteIds.sort();
    for (const [membro, votos] of sistema.votesByMember) {
      sistema.votesByMember.set(membro, [...votos].sort());
    }
  }

  const votesWithoutMember = systems.flatMap((sistema) => sistema.looseVoteIds).sort();
  return {
    systems,
    diagnostics: {
      systems: systems.length,
      nodes: operacionais.length,
      orphans: orphans.sort(),
      votesWithoutMember,
    },
  };
}

/**
 * Onde a execução de índice `i` se assenta: uma **casca**, não uma folha.
 *
 * Duas formas já falharam aqui, e as duas por medida.
 *
 * A espiral de Fermat espalhava as 38 execuções por um raio de 463 quando 258 bastavam,
 * porque `r = c·√i` só garante separação perto do centro se `c` valer a separação
 * inteira. O retículo hexagonal corrigiu isso — é a embalagem mais densa do plano —, mas
 * continuava sendo plano: medido, 1,3% da variância no eixo da visada, contra 23% no
 * corpus. Encurvá-lo num cone não resolveu, porque profundidade monotônica na distância
 * tem alcance e quase nenhuma variância.
 *
 * A casca resolve as duas coisas de uma vez. Numa esfera de raio `R` com `n` pontos bem
 * distribuídos, vizinhos ficam a cerca de `2R·√(π/n)`: pedir que isso valha a separação
 * dá o raio, e ele é **menor** que o do retículo para o mesmo `n` — a esfera tem mais
 * área que o disco de mesmo raio. As execuções ficam mais perto umas das outras e a
 * nuvem passa a ter volume de qualquer ângulo.
 *
 * A distribuição é a de Fibonacci, que é a mesma ideia do ângulo áureo já usado no
 * corpus: o `i`-ésimo ponto não depende de nenhum outro, então acrescentar execução não
 * move as anteriores. O raio é quantizado pelo mesmo motivo que o do corpus é — sem
 * degrau, cada execução nova reescalaria a casca inteira.
 */
export function executionOrigin(index: number, quantas = index + 1): Vec3 {
  // O balde é do **conjunto**, não do índice. Calculado por índice, execuções vizinhas
  // caíam em cascas de raios diferentes, e a separação mínima deixava de valer entre
  // elas: medido, 61,4 unidades onde a declarada era 72,4.
  const total = Math.max(
    BALDE_DE_EXECUCOES,
    (Math.floor(Math.max(quantas - 1, index) / BALDE_DE_EXECUCOES) + 1) * BALDE_DE_EXECUCOES,
  );
  const { pontos, raio } = cascaDe(total);
  const ponto = pontos[Math.min(index, pontos.length - 1)]!;
  // A casca é escrita na base da tela pela mesma razão de sempre: o eixo de profundidade
  // é o da visada, e pôr a distribuição nele é que faria uma execução esconder a outra.
  return paraMundoNaBase({ x: 0, y: 0, z: 0 }, ponto.x * raio, ponto.y * raio, ponto.z * raio);
}

/**
 * Degrau de crescimento da casca, em execuções.
 *
 * Mesma razão do degrau do anel do corpus: sem ele, cada execução nova reescalaria a
 * casca e moveria todas as outras, quando o que se promete é que a posição de uma
 * execução concluída não mude.
 */
const BALDE_DE_EXECUCOES = 16;

/** O `i`-ésimo ponto de Fibonacci na esfera unitária, em cilíndricas. */
function pontoDeFibonacci(
  index: number,
  total: number,
): { altura: number; anel: number; azimute: number } {
  const altura = total === 1 ? 0 : 1 - (2 * index) / (total - 1);
  return {
    altura,
    anel: Math.sqrt(Math.max(1 - altura * altura, 0)),
    azimute: ANGULO_AUREO * index,
  };
}

const CASCA = new Map<number, { pontos: Vec3[]; raio: number }>();

/**
 * Os pontos da casca, **relaxados** até o espaçamento ficar parejo.
 *
 * A distribuição de Fibonacci é boa na média e desigual no detalhe: o par mais próximo
 * fica bem abaixo do espaçamento típico. Como o raio precisa ser ditado pelo pior par —
 * é ele que decide se duas execuções se cobrem —, a casca inteira inflava para acomodar
 * um único par apertado: com 48 execuções, raio 248 onde 141 bastariam se o espaçamento
 * fosse parejo. Setenta e seis por cento de vazio, e foi isso que fez o observatório ler
 * como espalhado demais.
 *
 * O relaxamento é o mesmo remédio que o corpus usa: cada ponto é empurrado para longe de
 * quem está perto demais e devolvido à esfera. Poucas dezenas de passadas bastam para o
 * mínimo encostar na média, e aí o raio cai junto.
 */
function pontosDaCasca(total: number): Vec3[] {
  const pontos: Vec3[] = Array.from({ length: total }, (_, i) => {
    const { altura, anel, azimute } = pontoDeFibonacci(i, total);
    return { x: Math.cos(azimute) * anel, y: Math.sin(azimute) * anel, z: altura };
  });
  if (total < 3) return pontos;
  const alvo = 2 * Math.sqrt(Math.PI / total);
  for (let passada = 0; passada < PASSADAS_DE_RELAXAMENTO; passada += 1) {
    const empurroes: Vec3[] = pontos.map(() => ({ x: 0, y: 0, z: 0 }));
    for (let i = 0; i < total; i += 1) {
      for (let j = i + 1; j < total; j += 1) {
        const a = pontos[i]!;
        const b = pontos[j]!;
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const dz = a.z - b.z;
        const d = Math.hypot(dx, dy, dz);
        if (d >= alvo || d < 1e-9) continue;
        // Só quem está mais perto que o alvo empurra, e só o quanto falta.
        const forca = ((alvo - d) / d) * 0.5;
        empurroes[i]!.x += dx * forca;
        empurroes[i]!.y += dy * forca;
        empurroes[i]!.z += dz * forca;
        empurroes[j]!.x -= dx * forca;
        empurroes[j]!.y -= dy * forca;
        empurroes[j]!.z -= dz * forca;
      }
    }
    for (let i = 0; i < total; i += 1) {
      const p = pontos[i]!;
      const e = empurroes[i]!;
      const x = p.x + e.x;
      const y = p.y + e.y;
      const z = p.z + e.z;
      const n = Math.hypot(x, y, z) || 1;
      pontos[i] = { x: x / n, y: y / n, z: z / n };
    }
  }
  return pontos;
}

/** Passadas de relaxamento. Além disto o mínimo já não melhora o bastante para pagar. */
const PASSADAS_DE_RELAXAMENTO = 60;

/**
 * O raio que faz os **dois vizinhos mais próximos** distarem a separação pedida.
 *
 * A fórmula fechada `2R·√(π/n)` vale na média, e a distribuição de Fibonacci varia em
 * torno dela: com 35 execuções, o par mais próximo ficava a 39,9 unidades onde a
 * separação declarada era 72,4 — quase metade. Arbitrar uma margem cobriria o caso
 * medido e não o próximo. Aqui o mínimo é calculado de fato, uma vez por contagem, e o
 * raio sai dele: a casca fica exatamente do tamanho que precisa, nem mais nem menos.
 */
function cascaDe(total: number): { pontos: Vec3[]; raio: number } {
  const guardada = CASCA.get(total);
  if (guardada !== undefined) return guardada;
  const pontos = pontosDaCasca(total);
  let minimo = Number.POSITIVE_INFINITY;
  for (let i = 0; i < pontos.length; i += 1) {
    for (let j = i + 1; j < pontos.length; j += 1) {
      const a = pontos[i]!;
      const b = pontos[j]!;
      minimo = Math.min(minimo, Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z));
    }
  }
  const raio =
    minimo > 0 && Number.isFinite(minimo)
      ? SEPARACAO_ENTRE_EXECUCOES / minimo
      : SEPARACAO_ENTRE_EXECUCOES;
  const casca = { pontos, raio };
  CASCA.set(total, casca);
  return casca;
}

/**
 * Posições da camada viva, no frame do observatório.
 *
 * As coordenadas saem relativas à origem do observatório; quem compõe os dois frames
 * é o atlas. Manter a composição fora daqui é o que permite enquadrar uma camada sem
 * recalcular a outra.
 */
export function layoutOperational(
  projection: Projection,
  conhecidos: OperationalSlots = new Map(),
): OperationalPlacement {
  const { systems, diagnostics } = groupQuorumSystems(projection);
  const positions: LayoutMap = new Map();
  const slots = atribuirSlots(systems, conhecidos);

  systems.forEach((sistema) => {
    const origem = executionOrigin(slots.get(sistema.panelId)!, systems.length);
    if (sistema.panelNodeId) {
      positions.set(sistema.panelNodeId, paraMundoNaBase(origem, 0, SISTEMA.zPainel, 0));
    }

    // **Um leque só, para todos os votos da execução.**
    //
    // Antes havia dois: um setor por avaliador, e dentro dele um sub-leque de abertura
    // fixa para os votos daquele avaliador. O sub-leque não sabia quantos votos existiam
    // nem de que tamanho era a placa, e o resultado é que uma execução chegou a cobrir os
    // próprios votos — os "juízes muito próximos". Com um leque só, a separação é
    // calculada do total, e a leitura por avaliador sobrevive na **ordem**: os votos de
    // um mesmo avaliador continuam vizinhos, porque é assim que entram na lista.
    //
    // O avaliador em si não é assentado: ele mora na nuvem de modelos, uma vez só.
    const emOrdem: string[] = [];
    for (const memberId of sistema.memberIds) {
      emOrdem.push(...(sistema.votesByMember.get(memberId) ?? []));
    }
    // Voto sem avaliador fica fora deste leque de propósito: ele tem posição própria
    // logo abaixo, para não se esconder no setor de ninguém.
    const raioDoLeque = raioDoArco(emOrdem.length, SISTEMA.raioVoto);
    emOrdem.forEach((voteId, ordem) => {
      const angulo = (Math.PI * (ordem + 0.5)) / Math.max(emOrdem.length, 1);
      positions.set(
        voteId,
        paraMundoNaBase(
          origem,
          Math.cos(angulo) * raioDoLeque,
          SISTEMA.zVoto,
          Math.sin(angulo) * raioDoLeque * 0.6,
        ),
      );
    });

    // Voto sem avaliador não é escondido no leque de ninguém: ele fica no anel de
    // votos, num azimute próprio, e aparece na contagem de diagnóstico.
    const soltos = Math.max(sistema.looseVoteIds.length, 1);
    const raioDosSoltos = raioDoArco(soltos, SISTEMA.raioVoto);
    sistema.looseVoteIds.forEach((voteId, ordem) => {
      const azimute = ANGULO_AUREO * (ordem + 1) + Math.PI / soltos;
      positions.set(
        voteId,
        paraMundoNaBase(
          origem,
          Math.cos(azimute) * raioDosSoltos,
          SISTEMA.zVoto * 0.82,
          Math.sin(azimute) * raioDosSoltos * 0.6,
        ),
      );
    });

    // A decisão é terminal e fica sozinha no eixo. Mais de uma decisão por painel seria
    // deriva do backend; se acontecer, elas se separam no plano sem sair do topo.
    const decisoes = sistema.decisionIds.length;
    sistema.decisionIds.forEach((decisionId, ordem) => {
      const desvio = decisoes > 1 ? (ordem - (decisoes - 1) / 2) * 2.4 : 0;
      positions.set(decisionId, paraMundoNaBase(origem, desvio, SISTEMA.zDecisao, 0));
    });
  });

  return {
    positions,
    systems,
    diagnostics: {
      ...diagnostics,
      slotsReaproveitados: [...slots.keys()].filter((id) => conhecidos.has(id)).length,
      slotsNovos: slots.size - [...slots.keys()].filter((id) => conhecidos.has(id)).length,
    },
    slots,
  };
}

/** Raio horizontal e profundidade do observatório inteiro, no frame dele. */
export function operationalExtent(placement: OperationalPlacement): {
  radius: number;
  depth: number;
} {
  let radius = 1;
  let depth = 1;
  for (const p of placement.positions.values()) {
    radius = Math.max(radius, Math.hypot(p.x, p.y));
    depth = Math.max(depth, Math.abs(p.z));
  }
  return { radius, depth };
}


