// O Atlas solto: posição decidida pelas relações, e não pela pasta.
//
// Este é o experimento que a ADR-004 deixou em aberto, agora executável. A pergunta que
// ele responde não é estética — é se a estrutura declarada, sozinha, produz um mapa
// legível. Hoje a posição de uma nota vem do diretório dela; a Política é explícita em
// que diretório é só localização, e que o que estrutura é a relação declarada.
//
// **É um modo, e não uma substituição.** O layout ancorado continua sendo o padrão, e
// este roda sob `?layout=livre`. Trocar um pelo outro sem comparar seria repetir o erro
// que a esfera livre original cometeu — ela saiu por oclusão, perda de referência e
// reorganização do mapa inteiro a cada nota nova, e essas três coisas se medem.
//
// Determinístico a partir da semente: um mapa que muda de forma a cada recarga não é
// navegável, e um teste não conseguiria prendê-lo.

import type { Projection, ProjectionNode } from './contract';
import { hash32, type LayoutMap, type Vec3 } from './layout';
import { panelSweepRadius } from './panelScale';
import { describePanel } from './panels';

export interface FreeLayoutOptions {
  /** Quantas passagens de força. Mais que isto não muda a leitura, só o custo. */
  iterations?: number;
  seed?: number;
  /** Comprimento de repouso de uma aresta, em raios médios de placa. */
  restLength?: number;
  /** Metade da espessura da faixa de profundidade, como no layout ancorado. */
  zBand?: number;
}

const DEFAULTS = {
  iterations: 220,
  seed: 20260815,
  restLength: 2.6,
  zBand: 54,
} as const;

/**
 * Alcance da repulsão, em múltiplos do comprimento de repouso.
 *
 * Sem corte a repulsão é O(n²) por passagem — com 1362 nós são 1,86 milhão de pares, e
 * 220 passagens não terminam em tempo de tela. O corte não é aproximação grosseira: a
 * força cai com o quadrado da distância, e além de poucos comprimentos ela já não move
 * ninguém o suficiente para ser vista.
 */
const ALCANCE_DA_REPULSAO = 3.2;

/** Passo inicial, em fração do comprimento de repouso. Esfria até quase zero. */
const PASSO_INICIAL = 0.62;

function raioDaPlaca(node: ProjectionNode): number {
  return panelSweepRadius(describePanel(node));
}

interface Celula {
  indices: number[];
}

/**
 * Grade uniforme para a repulsão só olhar vizinhança.
 *
 * É o que troca O(n²) por O(n) amortizado sem mudar o resultado onde ele importa: dois
 * nós a mais de `ALCANCE_DA_REPULSAO` comprimentos não se empurram de forma perceptível,
 * e passar por eles é gastar quadro para confirmar que nada acontece.
 */
function construirGrade(
  xs: Float64Array,
  ys: Float64Array,
  zs: Float64Array,
  lado: number,
): Map<string, Celula> {
  const grade = new Map<string, Celula>();
  for (let i = 0; i < xs.length; i += 1) {
    const chave = `${Math.floor(xs[i]! / lado)},${Math.floor(ys[i]! / lado)},${Math.floor(zs[i]! / lado)}`;
    const celula = grade.get(chave);
    if (celula) celula.indices.push(i);
    else grade.set(chave, { indices: [i] });
  }
  return grade;
}

/**
 * Assenta a projeção inteira pela força das relações declaradas.
 *
 * Três forças, e nenhuma decorativa: aresta puxa, placa empurra, e um centro fraco
 * impede que componentes desconexos escapem para o infinito. O nó começa numa esfera
 * determinística da própria identidade — não no centro, porque nascer todo mundo no
 * mesmo ponto faz a primeira passagem explodir.
 */
export interface FreeSimulation {
  /** Avança `quantas` passagens. Devolve `false` quando não há mais o que fazer. */
  step: (quantas?: number) => boolean;
  /** As posições no estado atual da simulação. */
  positions: () => LayoutMap;
  /** Quanto do trabalho já foi feito, de 0 a 1. */
  progress: () => number;
}

/**
 * A mesma física, avançável quadro a quadro.
 *
 * `layoutFree` calcula as 220 passagens de uma vez e congela a aba por 2,6 s. Aqui a
 * simulação vira estado: quem chama decide quantas passagens cabem num quadro, e a cena
 * mostra o grafo se organizando em vez de aparecer pronto.
 *
 * Não é enfeite. Ver o assentamento **é** informação — quais nós caem juntos, quais
 * resistem, onde a estrutura declarada aperta. É o que um grafo de notas mostra ao abrir,
 * e é a diferença entre um mapa que se lê e um mapa que se recebe.
 *
 * Sem clique e sem arrasto de propósito: a posição continua saindo da relação declarada,
 * e não da mão. Arrastar um nó afirmaria uma posição que nenhuma aresta sustenta.
 */
export function createFreeSimulation(
  projection: Projection,
  options: FreeLayoutOptions = {},
): FreeSimulation {
  const estado = prepararCampo(projection, options);
  let feitas = 0;
  return {
    step(quantas = 1) {
      const alvo = Math.min(estado.config.iterations, feitas + Math.max(quantas, 1));
      while (feitas < alvo) {
        avancarUmaPassagem(estado, feitas);
        feitas += 1;
      }
      return feitas < estado.config.iterations;
    },
    positions: () => colher(estado),
    progress: () => feitas / estado.config.iterations,
  };
}

export function layoutFree(projection: Projection, options: FreeLayoutOptions = {}): LayoutMap {
  const simulacao = createFreeSimulation(projection, options);
  while (simulacao.step(32));
  return simulacao.positions();
}

interface Campo {
  config: Required<FreeLayoutOptions>;
  nodes: readonly ProjectionNode[];
  total: number;
  raios: Float64Array;
  xs: Float64Array;
  ys: Float64Array;
  zs: Float64Array;
  dx: Float64Array;
  dy: Float64Array;
  dz: Float64Array;
  arestas: Array<[number, number]>;
  repouso: number;
  alcance: number;
  alcance2: number;
}

function colher(campo: Campo): LayoutMap {
  const posicoes: LayoutMap = new Map();
  for (let i = 0; i < campo.total; i += 1) {
    posicoes.set(campo.nodes[i]!.id, {
      x: campo.xs[i]!,
      y: campo.ys[i]!,
      z: campo.zs[i]!,
    } satisfies Vec3);
  }
  return posicoes;
}

function prepararCampo(projection: Projection, options: FreeLayoutOptions): Campo {
  const config = { ...DEFAULTS, ...options };
  const nodes = projection.nodes;
  const total = nodes.length;

  const indicePorId = new Map<string, number>();
  const raios = new Float64Array(total);
  const xs = new Float64Array(total);
  const ys = new Float64Array(total);
  const zs = new Float64Array(total);

  let somaDeRaios = 0;
  for (let i = 0; i < total; i += 1) {
    const node = nodes[i]!;
    indicePorId.set(node.id, i);
    raios[i] = raioDaPlaca(node);
    somaDeRaios += raios[i]!;
    // Semente na identidade: mesma nota, mesmo ponto de partida, em qualquer máquina.
    const a = hash32(node.id, config.seed) * Math.PI * 2;
    const b = Math.acos(2 * hash32(node.id, config.seed + 1) - 1);
    const r = 40 + 240 * hash32(node.id, config.seed + 2);
    xs[i] = Math.sin(b) * Math.cos(a) * r;
    ys[i] = Math.sin(b) * Math.sin(a) * r;
    zs[i] = Math.cos(b) * r * 0.3;
  }

  const raioMedio = somaDeRaios / total;
  const repouso = raioMedio * config.restLength;
  const alcance = repouso * ALCANCE_DA_REPULSAO;
  const alcance2 = alcance * alcance;

  const arestas: Array<[number, number]> = [];
  for (const edge of projection.edges) {
    const a = indicePorId.get(edge.source);
    const b = indicePorId.get(edge.target);
    if (a !== undefined && b !== undefined && a !== b) arestas.push([a, b]);
  }

  return {
    config,
    nodes,
    total,
    raios,
    xs,
    ys,
    zs,
    dx: new Float64Array(total),
    dy: new Float64Array(total),
    dz: new Float64Array(total),
    arestas,
    repouso,
    alcance,
    alcance2,
  };
}

function avancarUmaPassagem(campo: Campo, passo: number): void {
  const { config, total, raios, xs, ys, zs, dx, dy, dz, arestas } = campo;
  const { repouso, alcance, alcance2 } = campo;
  {
    dx.fill(0);
    dy.fill(0);
    dz.fill(0);

    // **Repulsão**, só entre vizinhos de grade.
    const grade = construirGrade(xs, ys, zs, alcance);
    for (const celula of grade.values()) {
      for (const i of celula.indices) {
        const cx = Math.floor(xs[i]! / alcance);
        const cy = Math.floor(ys[i]! / alcance);
        const cz = Math.floor(zs[i]! / alcance);
        for (let ox = -1; ox <= 1; ox += 1) {
          for (let oy = -1; oy <= 1; oy += 1) {
            for (let oz = -1; oz <= 1; oz += 1) {
              const vizinha = grade.get(`${cx + ox},${cy + oy},${cz + oz}`);
              if (!vizinha) continue;
              for (const j of vizinha.indices) {
                if (j <= i) continue;
                let ex = xs[i]! - xs[j]!;
                let ey = ys[i]! - ys[j]!;
                let ez = zs[i]! - zs[j]!;
                let d2 = ex * ex + ey * ey + ez * ez;
                if (d2 > alcance2) continue;
                if (d2 < 1e-6) {
                  ex = Math.cos(i * 0.7 + j);
                  ey = Math.sin(i + j * 0.7);
                  ez = Math.cos(i - j) * 0.4;
                  d2 = ex * ex + ey * ey + ez * ez;
                }
                const d = Math.sqrt(d2);
                // Mínimo pela soma dos raios: placa é área, não ponto, e ignorar isso
                // devolve exatamente a oclusão que tirou a esfera livre da cena.
                const minima = (raios[i]! + raios[j]!) * 1.35;
                const forca = ((repouso * repouso) / d2 + (d < minima ? (minima - d) * 2.2 : 0)) / d;
                dx[i]! += ex * forca;
                dy[i]! += ey * forca;
                dz[i]! += ez * forca;
                dx[j]! -= ex * forca;
                dy[j]! -= ey * forca;
                dz[j]! -= ez * forca;
              }
            }
          }
        }
      }
    }

    // **Atração** ao longo da relação declarada. É esta força que faz a posição
    // significar estrutura, e é a que o layout ancorado não tem.
    for (const [a, b] of arestas) {
      const ex = xs[b]! - xs[a]!;
      const ey = ys[b]! - ys[a]!;
      const ez = zs[b]! - zs[a]!;
      const d = Math.hypot(ex, ey, ez) || 1e-6;
      const forca = (d - repouso) / d / 6;
      dx[a]! += ex * forca;
      dy[a]! += ey * forca;
      dz[a]! += ez * forca;
      dx[b]! -= ex * forca;
      dy[b]! -= ey * forca;
      dz[b]! -= ez * forca;
    }

    // **Centro fraco.** Sem ele, um componente desconexo — e a projeção tem vários —
    // sai empurrado para longe e nunca volta, levando o enquadramento junto.
    const temperatura = PASSO_INICIAL * repouso * (1 - passo / config.iterations);
    for (let i = 0; i < total; i += 1) {
      dx[i]! -= xs[i]! * 0.0016;
      dy[i]! -= ys[i]! * 0.0016;
      dz[i]! -= zs[i]! * 0.0016;
      const passoDoNo = Math.hypot(dx[i]!, dy[i]!, dz[i]!) || 1;
      const limite = Math.min(passoDoNo, temperatura) / passoDoNo;
      xs[i]! += dx[i]! * limite;
      ys[i]! += dy[i]! * limite;
      // A profundidade continua sendo faixa, e não eixo livre: `z` separa camadas e
      // desfaz sobreposição, mas não mede nada, e soltá-lo devolve a oclusão sem
      // devolver informação. É o mesmo limite que o layout ancorado aplica.
      zs[i]! = Math.max(-config.zBand, Math.min(config.zBand, zs[i]! + dz[i]! * limite));
    }
  }
}

/**
 * O mesmo campo de forças, **uma população por vez**, nos lugares que a composição já deu.
 *
 * O modo solto puro resolve a aresta e perde a leitura: sem noção de população, corpus,
 * quórum e modelos colapsam num bolo só, e a 897 unidades de distância aquilo lê como
 * massa — não por sobreposição real, que medida deu 2 colisões em 1408 nós, mas por
 * projeção. A cena tinha deixado de dizer quem é quem.
 *
 * Aqui a relação decide a posição **dentro** de cada nuvem, e a composição continua
 * decidindo onde cada nuvem fica. É a divisão que a ADR-003 já fixou por outro caminho:
 * a política local governa o tecido, a cartografia governa o território.
 *
 * A aresta que cruza populações continua longa, e isso é honesto — ela **é** uma
 * travessia. O que deixa de existir é a travessia longa entre coisas da mesma nuvem.
 */
export function layoutFreeByPopulation(
  projection: Projection,
  populations: ReadonlyArray<{ ids: ReadonlySet<string>; origin: Vec3 }>,
  options: FreeLayoutOptions = {},
): LayoutMap {
  const resultado: LayoutMap = new Map();
  for (const { ids, origin } of populations) {
    if (ids.size === 0) continue;
    const nodes = projection.nodes.filter((node) => ids.has(node.id));
    if (nodes.length === 0) continue;
    const edges = projection.edges.filter(
      (edge) => ids.has(edge.source) && ids.has(edge.target),
    );
    const local = layoutFree({ ...projection, nodes, edges }, options);
    for (const [id, ponto] of local) {
      resultado.set(id, {
        x: ponto.x + origin.x,
        y: ponto.y + origin.y,
        z: ponto.z + origin.z,
      });
    }
  }
  return resultado;
}

/**
 * Uma simulação por população, avançando juntas, cada uma na origem que a composição deu.
 *
 * É a versão viva de `layoutFreeByPopulation`. Cada nuvem tem o próprio campo — o corpus
 * não sente o quórum se organizar — e o passo de todas acontece no mesmo quadro, para a
 * cena assentar como um todo em vez de uma nuvem de cada vez.
 */
export function createFreeSimulationByPopulation(
  projection: Projection,
  populations: ReadonlyArray<{ ids: ReadonlySet<string>; origin: Vec3 }>,
  options: FreeLayoutOptions = {},
): FreeSimulation {
  const partes = populations.flatMap(({ ids, origin }) => {
    if (ids.size === 0) return [];
    const nodes = projection.nodes.filter((node) => ids.has(node.id));
    if (nodes.length === 0) return [];
    const edges = projection.edges.filter(
      (edge) => ids.has(edge.source) && ids.has(edge.target),
    );
    return [
      {
        origin,
        simulacao: createFreeSimulation({ ...projection, nodes, edges }, options),
      },
    ];
  });

  return {
    step(quantas = 1) {
      let continua = false;
      for (const parte of partes) continua = parte.simulacao.step(quantas) || continua;
      return continua;
    },
    positions() {
      const total: LayoutMap = new Map();
      for (const { simulacao, origin } of partes) {
        for (const [id, p] of simulacao.positions()) {
          total.set(id, { x: p.x + origin.x, y: p.y + origin.y, z: p.z + origin.z });
        }
      }
      return total;
    },
    progress() {
      if (partes.length === 0) return 1;
      return partes.reduce((s, p) => s + p.simulacao.progress(), 0) / partes.length;
    },
  };
}
