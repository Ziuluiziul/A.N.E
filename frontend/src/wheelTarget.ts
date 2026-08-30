// De quem é a roda: do painel aberto ou da câmera.
//
// Vizinho de `keyboardTarget.ts`, e pelo mesmo motivo: `atlas.ts` precisa de contexto
// WebGL para ser instanciado e por isso não tem teste, enquanto um predicado puro tem. A
// decisão é pequena o bastante para caber numa linha e importante o bastante para ter de
// valer sempre — as duas coisas juntas pedem função pura.
//
// A regra que estava em `atlas.ts` tinha uma condição só: existir painel selecionado com
// rolagem. Ela era ampla demais em dois sentidos, e os dois se sentiam ao usar.
//
// O primeiro é o ponteiro, que não contava: bastava haver algo aberto para a roda parar
// de aproximar a câmera, em qualquer canto da tela, inclusive a mil unidades do painel.
//
// O segundo é a devolução, que era tardia. Como o consumo só cessava ao chegar ao fim do
// conteúdo, sair de um documento longo exigia rolá-lo inteiro antes de o mundo voltar a
// responder. É a sensação descrita como "primeiro preciso terminar de rolar o painel e só
// depois o mundo volta a dar zoom" — e ela não é um defeito de sensibilidade nem de
// suavização: é esta regra, escrita como estava.
//
// **Cada evento decide sozinho.** Não há tempo de espera, carência nem estado residual
// entre rolar e aproximar. É isso que faz a devolução ser imediata em qualquer ponto do
// documento: basta tirar o ponteiro da placa, ou alcançar a ponta na direção em que se
// está girando.

export type WheelOwner = 'panel' | 'camera';

export interface WheelArbitration {
  /** Sinal do giro. Negativo revela o que está acima; positivo, o que está abaixo. */
  deltaY: number;
  /** Deslocamento de leitura atual do painel aberto, em unidades de mundo. */
  scrollOffset: number;
  /** O máximo que ele pode rolar. Zero quando o conteúdo cabe inteiro na placa. */
  maxScroll: number;
  /** O ponteiro está sobre a placa aberta? Quem responde é a cena, com um raio. */
  pointerOverPanel: boolean;
}

/**
 * Quem consome este giro de roda.
 *
 * `panel` exige as duas coisas ao mesmo tempo: ponteiro sobre a placa aberta **e** ainda
 * haver o que revelar **naquela direção**. Faltando qualquer uma, a roda é da câmera no
 * mesmo evento — não no próximo, e não depois de um limiar.
 *
 * A direção é a parte que costuma escapar. Sem ela, um painel rolado até o fim continuava
 * consumindo o giro para baixo, e um painel no topo consumia o giro para cima: as duas
 * pontas do conteúdo viravam paredes em que a cena ficava surda.
 */
export function wheelOwner({
  deltaY,
  scrollOffset,
  maxScroll,
  pointerOverPanel,
}: WheelArbitration): WheelOwner {
  if (!pointerOverPanel) return 'camera';
  if (maxScroll <= 0) return 'camera';
  // Giro nulo não é rolagem nem aproximação; devolvê-lo à câmera é o que não inventa
  // movimento nenhum a partir de evento sem intenção.
  if (deltaY === 0) return 'camera';
  if (deltaY < 0) return scrollOffset > 0 ? 'panel' : 'camera';
  return scrollOffset < maxScroll ? 'panel' : 'camera';
}
