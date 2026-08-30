// Quem acende, quem apaga e quem fica igual. Uma regra, num lugar só.
//
// Havia duas funções escrevendo a ênfase de todos os painéis do corpus: uma derivada da
// seleção e do sobrevoo, outra derivada do vínculo entre o evento vivo selecionado e a
// nota que ele anota. Cada uma varria a cena inteira, e quem rodasse por último vencia.
// Mover o mouse apagava o vínculo aceso; um quadro SSE apagava o vínculo aceso; e a
// seleção viva continuava ativa o tempo todo, sem contraparte visual.
//
// É o F-13 da auditoria de 2026-08-09. A correção não é ordenar as chamadas — ordem é
// acordo que se quebra na próxima função que precisar escrever aqui. É haver uma função
// que conhece **todas** as entradas.
//
// Ela mora fora de `atlas.ts` porque lá dentro não haveria como testá-la: instanciar o
// atlas exige contexto WebGL. A decisão é pura, então ela é testável; o desenho fica
// onde já estava.

import type { PanelEmphasis } from './panelBodies';

/** Tudo que determina a ênfase de um painel do corpus, num instante. */
export interface EmphasisState {
  /** Entidade do corpus selecionada, se houver. */
  selected: string | null;
  /** Entidade sob o cursor, se houver. */
  hovered: string | null;
  /**
   * Entidade do corpus na outra ponta da haste do evento vivo selecionado.
   *
   * Ela acende quando não há seleção de corpus: a haste atravessa a cena e termina numa
   * nota que, sem isso, ficava indistinguível das vizinhas. Com seleção de corpus ativa,
   * quem manda é a seleção — duas coisas acesas por motivos diferentes seriam duas
   * respostas para a mesma pergunta.
   */
  linkedEntity: string | null;
  /** Vizinhas da seleção de corpus. Só elas acompanham o destaque. */
  neighbours: ReadonlySet<string> | undefined;
}

/**
 * O foco efetivo da cena: a seleção do corpus, ou o vínculo vivo na falta dela.
 *
 * Exportado porque a precedência é a parte da regra que se esquece — e um teste que a
 * fixa vale mais que um comentário que a descreve.
 */
export function focusOf(state: EmphasisState): string | null {
  return state.selected ?? state.linkedEntity;
}

/** A ênfase de um painel. Pura, sem alocar, chamada uma vez por painel por quadro. */
export function emphasisFor(id: string, state: EmphasisState): PanelEmphasis {
  const foco = focusOf(state);
  if (id === foco) return 'highlighted';
  // A vizinhança acompanha **a seleção do corpus**, e não o vínculo vivo: a vizinhança
  // de uma nota apontada por um evento não é o que o evento está dizendo.
  if (state.selected !== null && state.neighbours?.has(id) === true) return 'highlighted';
  if (foco !== null) return 'dimmed';
  if (id === state.hovered) return 'highlighted';
  return 'normal';
}
