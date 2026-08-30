// A única conversão entre a semântica do descritor e as unidades da cena.
//
// `panels.ts` diz que um MOC é 4,00 × 2,25 — uma proporção e uma área por degrau,
// sem opinião sobre o tamanho do mundo. Quantas unidades da cena isso ocupa é
// decisão do renderizador, e mora aqui.
//
// Manter as duas coisas separadas é o que impede o erro de multiplicar `panelExtent`
// "só para o texto caber": semântica do descritor e escala do mundo passariam a se
// confundir, e a próxima mudança de fonte viraria mudança de ontologia.
//
// **Autoridade única.** Corpo, caixa de texto, área de clique, casca de foco,
// deslocamento de seleção e as futuras âncoras de aresta consultam esta função. Não
// há multiplicação por escala espalhada pelo código.

import type { ProjectionNode } from './contract';
import {
  describePanel,
  panelExtent,
  proportionOf,
  sizeStepOf,
  type PanelDescriptor,
  type PanelType,
} from './panels';

/**
 * Fator entre a extensão semântica e a unidade da cena.
 *
 * O valor de partida era 3,2, herdado da esfera que a ADR-002 aposentou: o corpo antigo
 * de um MOC tinha raio 2,6, e a placa nasceu do mesmo tamanho só para caber o texto que
 * antes flutuava ao lado dela.
 *
 * **Aumentar não é dar zoom.** Quase tudo aqui é invariante de escala: o LOD mede pixels
 * projetados, a distância de leitura sai da própria placa, e o espaçamento dentro de um
 * território é derivado dela — multiplicar placa e mundo juntos não mudaria um pixel. O
 * que muda é a relação com as grandezas **absolutas** do layout: o anel das âncoras, a
 * faixa de profundidade, a folga entre nuvens. Elas não crescem, e por isso a placa
 * cresce *dentro* do território. Medido na projeção viva, a largura de uma nota passa de
 * 67,7‰ do raio do corpus para 90,7‰ — 34% mais placa para a mesma vizinhança, que é o
 * que se lê como "o painel ficou maior".
 *
 * O teto é a colisão. Em 5,0 a cena composta fica sem um par de placas sobreposto: 479
 * nós, zero pares, com a separação global de `layout.ts` fazendo o acerto fino. Ela não
 * é uma licença para crescer indefinidamente — quanto mais placa, mais ela empurra, e
 * passado o ponto em que a folga acaba o território deixa de caber em si mesmo.
 */
export const PANEL_WORLD_SCALE = 5.0;

/** Margem uniforme de clique ao redor da placa, em unidades da cena. */
export const PICK_MARGIN_WORLD = 0.4;

export interface WorldExtent {
  width: number;
  height: number;
}

/** A extensão da placa na cena. Toda medida visual começa por aqui. */
/**
 * A extensão de mundo de um **tipo** de painel, sem precisar de um nó.
 *
 * Quem assenta painéis precisa saber de que tamanho eles são. Sem isto, o observatório
 * media distâncias com números escolhidos à mão, e eles envelheceram no dia em que o
 * painel de quórum deitou: os votos ficaram a 10,2 unidades de raio com 11,8 de largura,
 * e a decisão a 5,8 do voto com 7,8 de altura — encostados, e ninguém tinha como saber
 * pelo código que estavam.
 */
export function panelWorldExtentOf(type: PanelType): WorldExtent {
  const { width, height } = panelExtent({
    sizeStep: sizeStepOf(type),
    proportion: proportionOf(type),
  } as PanelDescriptor);
  return { width: width * PANEL_WORLD_SCALE, height: height * PANEL_WORLD_SCALE };
}

export function panelWorldExtent(descriptor: PanelDescriptor): WorldExtent {
  const semantica = panelExtent(descriptor);
  return {
    width: semantica.width * PANEL_WORLD_SCALE,
    height: semantica.height * PANEL_WORLD_SCALE,
  };
}

/**
 * O raio do círculo que a placa varre ao girar para a câmera.
 *
 * É a medida certa para tudo que precisa dizer "aqui não cabe mais nada": a placa é
 * orientada à câmera, então o que ela ocupa ao longo de uma órbita inteira não é a caixa
 * — é o círculo circunscrito a ela. Três lugares chegaram a esta mesma conta por conta
 * própria (o layout, a separação global e a aparagem das arestas); ela mora aqui, que é
 * o módulo que já é a autoridade sobre o tamanho da placa no mundo.
 */
export function panelSweepRadius(descriptor: PanelDescriptor): number {
  const { width, height } = panelWorldExtent(descriptor);
  return Math.hypot(width, height) / 2;
}

/** O raio varrido de cada nó, para quem precisa consultar por identidade. */
export function panelSweepRadii(nodes: readonly ProjectionNode[]): Map<string, number> {
  return new Map(nodes.map((node) => [node.id, panelSweepRadius(describePanel(node))]));
}

/**
 * Área de captura: a placa mais uma margem **uniforme**.
 *
 * Uniforme e não proporcional de propósito. Margem por fator faria a ponte, que é a
 * mais larga, ganhar também a maior folga de clique — largura viraria vantagem de
 * interação, que é exatamente o que a ADR-002 proíbe.
 */
export function panelPickExtent(descriptor: PanelDescriptor): WorldExtent {
  const mundo = panelWorldExtent(descriptor);
  return {
    width: mundo.width + PICK_MARGIN_WORLD * 2,
    height: mundo.height + PICK_MARGIN_WORLD * 2,
  };
}
