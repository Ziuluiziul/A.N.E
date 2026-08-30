// Markdown resolvido: fica o texto, some a marcação que diz como escrevê-lo.
//
// Nasceu dentro de `noteDocument.ts`, que formata o documento de uma nota em blocos. Saiu
// de lá quando ficou claro que o problema é maior que o corpus: a deliberação também
// escreve Markdown, e escreve mais. Medido na projeção viva, 31 nós operacionais trazem
// `**Texto da Proposta:**`, cercas de ``` e blocos YAML inteiros no campo que o painel
// desenha — texto que um modelo escreveu para ser renderizado, e que o painel exibia cru.
//
// Dois níveis, porque são duas perguntas:
//
// - `semMarcacao` resolve o que é **inline**: ênfase, link, wikilink, código curto,
//   comentário HTML. É o que uma frase precisa.
// - `textoCorrido` resolve também o que é **de linha** — heading, item, citação, cerca —
//   e devolve uma linha só. É o que um campo de painel precisa, porque ali não há bloco:
//   há uma frase, e ela ou se lê ou não.
//
// Quem quer hierarquia de verdade — heading em caixa alta, item com marcador, bloco
// separado — usa `documentLines`, que trabalha com o documento inteiro.
//
// Módulo puro: sem rede, sem Three.js, sem DOM.

/**
 * Resolve a marcação inline: fica o texto, some o que o declarava.
 *
 * A ordem importa. O comentário sai primeiro, porque ele pode conter qualquer coisa; a
 * imagem antes do link, porque `![alt](url)` casa também com o padrão de link; e a ênfase
 * depois dos links, para não comer os asteriscos de um texto de link.
 */
export function semMarcacao(texto: string): string {
  return texto
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    // Wikilink: o que se lê é o apelido quando ele existe, e o nome da nota quando não.
    // O caminho até ela é endereço, não texto — `Física/Entropia` se lê "Entropia".
    .replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (_, alvo: string, apelido?: string) =>
      (apelido ?? alvo.split('/').at(-1) ?? alvo).trim(),
    )
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
    .replace(/(?<![\w*])\*([^*\n]+)\*(?![\w*])/g, '$1')
    .replace(/~~([^~]+)~~/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\s+/g, ' ')
    // O que sai deixa buraco: `[[Nota]] <!-- relation:x -->.` vira "Nota ." se ninguém
    // recolher o espaço que o comentário ocupava. Pontuação não flutua.
    .replace(/\s+([.,;:!?%)\]}])/g, '$1')
    .replace(/([([{])\s+/g, '$1')
    .trim();
}

/**
 * O mesmo texto reduzido a **uma linha legível**, marcação de linha incluída.
 *
 * É o que serve a um campo de painel, que não tem blocos: a cerca de código some, o
 * heading perde os `#` e vira frase, o item perde o hífen e ganha um separador visível. O
 * conteúdo continua inteiro — o que se recusa é mostrar a instrução de formatação no
 * lugar do que ela formata.
 */
export function textoCorrido(bruto: string): string {
  const linhas = bruto
    .split(/\r?\n/)
    // A cerca é pura marcação: nem o delimitador nem o nome da linguagem dizem algo que
    // o texto de dentro não diga melhor.
    .filter((linha) => !/^\s*```/.test(linha))
    .map((linha) =>
      linha
        .replace(/^\s*#{1,6}\s+/, '')
        .replace(/^\s*>\s?/, '')
        .replace(/^\s*[-*+]\s+/, '· ')
        .replace(/^\s*(\d+)[.)]\s+/, '$1. '),
    );
  return semMarcacao(linhas.join(' '));
}
