// Atalhos que pertencem à cena.
//
// A antiga ilha 3D e a barra DOM deixaram de ter consumidor quando os filtros foram
// removidos. A lista permanece como contrato único entre o teclado e a ação real: hoje
// somente `G` reenquadra o Atlas.

/**
 * Um só, e ele age.
 *
 * Eram cinco. `C` e `F` ligavam camadas e relações, e com tudo em cena por padrão
 * passaram a alternar entre "como está" e "faltando coisa". `L` levava à legenda, que
 * mora na configuração. `M` repetia uma preferência que o navegador já declara e que a
 * cena já respeita. Sobrou `G`, que reenquadra — a única das cinco que fazia algo que
 * a navegação não faz sozinha.
 */
export const CONTROLS = [{ id: 'global', shortcut: 'g' }] as const;

/**
 * A gramática de navegação, dita em voz alta na faixa de baixo.
 *
 * Ela mora aqui e não no HTML porque o atalho e a legenda dele são a mesma afirmação:
 * separá-los é combinar que alguém vai lembrar de mudar os dois. Quem mudar a tecla
 * quebra o teste desta lista, e é assim que a legenda continua verdadeira.
 *
 * O gesto do mouse entra junto, embora não passe pelo teclado: para quem lê a faixa, a
 * pergunta é "o que eu faço para chegar lá", e não "qual subsistema responde".
 */
export const SCENE_LEGEND = [
  { keys: 'clique', action: 'escolher' },
  // O duplo clique e o Enter fazem a mesma coisa, e listá-los separados sugeria que
  // fossem dois gestos com dois efeitos. São dois caminhos para o mesmo.
  { keys: 'duplo clique · Enter', action: 'aproximar da escolha' },
  { keys: 'arrastar', action: 'girar' },
  { keys: 'scroll', action: 'aproximar e afastar' },
  { keys: 'WASD', action: 'andar' },
  { keys: 'Esc', action: 'soltar a escolha' },
  { keys: 'G', action: 'reenquadrar tudo' },
] as const;
