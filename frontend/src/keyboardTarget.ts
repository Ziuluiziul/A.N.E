// De quem é a tecla: da cena ou de um campo de digitação.
//
// Os atalhos do Atlas escutam no `window`, e é isso que os faz funcionar sem exigir
// que a cena tenha o foco. O preço é que eles também recebem tudo que se digita num
// campo do dock — e como `WASD` e os atalhos de controle chamam `preventDefault()`, o
// caractere não chegava ao campo.
//
// O caso que doeu: o campo de chave de API. Uma credencial contendo `w`, `a`, `s`, `d`,
// `g`, `l`, `f` ou `m` não podia ser digitada — a letra sumia e a câmera andava. É o
// F-11 da auditoria de 2026-08-09, e ele é vizinho do F-01 no mesmo caminho: um
// engolia a tecla da credencial, o outro devolvia a credencial inteira.
//
// Módulo próprio, e não uma função dentro de `atlas.ts`, porque `atlas.ts` precisa de
// contexto WebGL para ser instanciado e por isso não tem teste. Um predicado puro tem.

/** O alvo do evento aceita digitação? */
export function isEditableTarget(target: EventTarget | null): boolean {
  if (target === null) return false;
  // `instanceof` falharia entre documentos (iframe); a checagem estrutural não.
  const alvo = target as Partial<HTMLElement> & { tagName?: string };
  if (alvo.isContentEditable === true) return true;
  const etiqueta = typeof alvo.tagName === 'string' ? alvo.tagName.toUpperCase() : '';
  return etiqueta === 'INPUT' || etiqueta === 'TEXTAREA' || etiqueta === 'SELECT';
}

export type SelectionKeyboardAction =
  | 'clear-selection'
  | 'focus-corpus'
  | 'focus-runtime'
  | null;

/**
 * O que Enter/Escape significam para a seleção que a pessoa realmente vê.
 *
 * Corpus e runtime guardam a seleção em campos distintos. Deixar a decisão no
 * `onKeyDown` fez o teclado consultar só o primeiro: Escape abria um menu com um
 * evento ainda escolhido, e Enter não recentrava esse evento. A função pura torna
 * explícito que ambos pertencem à mesma gramática de navegação.
 *
 * Escape sem seleção não abre mais nada. Credencial, trabalhador e AUTO moram nas
 * placas e no cartão; um menu por tecla vazia era o caminho velho para as três.
 */
export function selectionKeyboardAction(
  key: string,
  hasCorpusSelection: boolean,
  hasRuntimeSelection: boolean,
): SelectionKeyboardAction {
  if (key === 'Escape') {
    return hasCorpusSelection || hasRuntimeSelection ? 'clear-selection' : null;
  }
  if (key !== 'Enter') return null;
  // O estado normal é mutuamente exclusivo. Se um quadro intermediário expuser os
  // dois, o painel vivo visível vence em vez de o teclado saltar para outro domínio.
  if (hasRuntimeSelection) return 'focus-runtime';
  if (hasCorpusSelection) return 'focus-corpus';
  return null;
}
