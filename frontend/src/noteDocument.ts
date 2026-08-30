// O documento da nota, do primeiro heading ao EOF, em linhas que a placa sabe dispor.
//
// **Por que ele existe.** A projeção leva `summary` — a abertura do corpo, cortada em
// fronteira de frase — e os claims. Isso basta para um painel dizer o que a nota *é*, e
// não basta para mostrar o que ela *diz*: aberto, o painel exibia o cabeçalho, uma frase
// de resumo e uma contagem de afirmações, e depois espaço vazio. Não havia o que rolar
// porque não havia conteúdo, e a rolagem existente parecia quebrada quando na verdade
// estava correta sobre um documento de quatro linhas.
//
// **O que ele preserva.** Tudo: headings, parágrafos, listas, wikilinks, links, blocos de
// código e o que vier até o EOF. Nada é resumido nem descartado.
//
// **O que mudou, e por quê.** A primeira versão entregava o Markdown cru, com o argumento
// de que a placa desenha um bloco tipográfico único e fingir hierarquia ali seria inventar
// uma que não existe. A captura desmentiu o argumento: o painel aberto mostrava
// `# Bioenergética e termodinâmica`, `## Finalidade` e `**como um organismo mantém ordem
// interna**` — o leitor via a marcação, não o texto. Marcação é instrução de formatação, e
// exibi-la é justamente **não** formatar.
//
// A hierarquia existe no documento e pode ser dita sem segunda fonte de letra:
//
// - heading vira caixa alta, e o nível vira recuo. É o único recurso que sobrevive a um
//   corpo de fonte só, e é forte o bastante para separar seção de parágrafo;
// - item de lista ganha marcador de verdade — `•` — em vez do hífen que o Markdown usa
//   para *dizer* que ali começa um item;
// - ênfase, link e wikilink são **resolvidos**: fica o texto que eles marcam, some a
//   marcação que os declara. O alvo de um wikilink continua no corpus; o painel mostra o
//   que a frase diz;
// - bloco de código mantém indentação e ganha uma guia à esquerda, porque código
//   reflowado deixa de ser código;
// - entre blocos entra uma linha vazia. Sem ela, três parágrafos e dois headings chegam
//   como um bloco contínuo de dez linhas, que é o que a captura mostrava.
//
// **O que ele tira.** O frontmatter, que é metadado e já chega ao painel pelas frases
// derivadas do descritor; o `# Título` de abertura, que o painel desenha à parte, acima da
// placa; e os comentários HTML, que carregam a declaração de relação — dado do grafo, não
// do texto.
//
// Módulo puro: sem rede, sem Three.js, sem DOM. Recebe texto e devolve linhas.

import { semMarcacao } from './markdownText';
import type { PanelLine } from './panels';

/**
 * Prioridade das linhas do documento.
 *
 * Abaixo de qualquer frase derivada, porque `linesUpTo` ordena por prioridade decrescente
 * e a ordenação do JavaScript é estável: com um valor comum a todas, as linhas do
 * documento chegam depois das do descritor e **na ordem do documento**, que é a única em
 * que um texto se lê.
 */
const PRIORIDADE_DO_DOCUMENTO = -1;

/** Delimitador de frontmatter no começo do arquivo. */
const FRONTMATTER = /^---\r?\n[\s\S]*?\r?\n---\r?\n?/;

/**
 * A linha vazia que separa blocos.
 *
 * Um espaço, e não a string vazia: quem compõe o bloco final descarta partes vazias — é
 * assim que cabeçalho e título ausentes somem —, e um separador que some não separa nada.
 */
const SEPARADOR = ' ';

/** Marcador de item, por profundidade. Além do terceiro nível, repete o último. */
const MARCADORES = ['•', '◦', '‣'];

/** Guia à esquerda do bloco de código, no lugar da cerca que o Markdown usa. */
const GUIA_DE_CODIGO = '│ ';

/** Recuo de um nível, em espaços. */
const RECUO = '  ';

export interface DocumentOptions {
  /** Título canônico da nota, para não repetir o `# Título` que o painel já desenha. */
  title?: string;
}

/**
 * Compara títulos como um leitor compara: sem caixa, sem acento e sem pontuação de borda.
 *
 * A comparação exata deixava passar o caso mais comum de todos. O título canônico vem do
 * frontmatter — "Bioenergética e Termodinâmica dos Sistemas Vivos" — e o `# heading` do
 * corpo é escrito em caixa de frase: "Bioenergética e termodinâmica dos sistemas vivos".
 * São o mesmo título, e o painel escrevia os dois, um acima da placa e outro dentro dela.
 */
function mesmoTitulo(a: string, b: string): boolean {
  const normal = (texto: string): string =>
    texto
      .normalize('NFD')
      .replace(/\p{Diacritic}/gu, '')
      .toLowerCase()
      .replace(/[^\p{L}\p{N}]+/gu, ' ')
      .trim();
  return normal(a) === normal(b);
}

/** Profundidade de um item de lista, contada em pares de espaços da indentação. */
function profundidade(indentacao: string): number {
  return Math.floor(indentacao.replace(/\t/g, '  ').length / 2);
}

const HEADING = /^(#{1,6})\s+(.*)$/;
const ITEM = /^(\s*)[-*+]\s+(.*)$/;
const ITEM_NUMERADO = /^(\s*)(\d+)[.)]\s+(.*)$/;
const CITACAO = /^\s*>\s?(.*)$/;
const REGUA = /^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/;
const TABELA = /^\s*\|(.+)\|\s*$/;
const SEPARADOR_DE_TABELA = /^[\s|:-]+$/;

/**
 * As linhas do documento, na ordem em que ele as escreve e na forma em que se leem.
 *
 * Linha em branco do original não vira linha: ela é separador de bloco, e quem emite o
 * separador é a passagem que fecha cada bloco — assim dois parágrafos ficam separados por
 * uma linha vazia só, e não por quantas o autor tiver deixado.
 *
 * Dentro de bloco de código tudo é preservado como está: indentação, linha vazia e o que
 * mais houver, menos a cerca, que é marcação.
 */
export function documentLines(markdown: string, options: DocumentOptions = {}): PanelLine[] {
  const corpo = markdown.replace(FRONTMATTER, '');
  const linhas: PanelLine[] = [];
  let emCodigo = false;
  let paragrafo: string[] = [];
  /** Verdadeiro quando o próximo bloco precisa de uma linha vazia antes de si. */
  let pedeSeparacao = false;

  const emitir = (text: string): void => {
    linhas.push({ section: 'descricao', text, priority: PRIORIDADE_DO_DOCUMENTO });
  };
  /** Abre um bloco: separa do anterior, quando havia um. */
  const abrirBloco = (): void => {
    if (linhas.length > 0 && pedeSeparacao) emitir(SEPARADOR);
    pedeSeparacao = false;
  };
  const fecharParagrafo = (): void => {
    if (paragrafo.length === 0) return;
    const texto = semMarcacao(paragrafo.join(' '));
    paragrafo = [];
    if (texto === '') return;
    abrirBloco();
    emitir(texto);
    pedeSeparacao = true;
  };

  for (const bruta of corpo.split(/\r?\n/)) {
    const linha = bruta.replace(/\s+$/, '');

    const cerca = /^\s*```(.*)$/.exec(linha);
    if (cerca) {
      fecharParagrafo();
      if (!emCodigo) {
        abrirBloco();
        const linguagem = cerca[1]!.trim();
        if (linguagem !== '') emitir(`${GUIA_DE_CODIGO}${linguagem.toUpperCase()}`);
      } else {
        pedeSeparacao = true;
      }
      emCodigo = !emCodigo;
      continue;
    }
    if (emCodigo) {
      // Preservado como está, inclusive a linha vazia: ela é parte do programa.
      emitir(linha === '' ? SEPARADOR : `${GUIA_DE_CODIGO}${linha}`);
      continue;
    }

    if (linha.trim() === '') {
      fecharParagrafo();
      continue;
    }

    const heading = HEADING.exec(linha.trim());
    if (heading) {
      fecharParagrafo();
      const nivel = heading[1]!.length;
      const texto = semMarcacao(heading[2]!);
      // O `# Título` de abertura sai: o painel já o desenha acima da placa. Um heading
      // mais fundo com o mesmo nome continua valendo — o que sai é o título, não a menção.
      if (nivel === 1 && options.title !== undefined && mesmoTitulo(texto, options.title)) {
        continue;
      }
      abrirBloco();
      emitir(`${RECUO.repeat(Math.max(nivel - 2, 0))}${texto.toUpperCase()}`);
      pedeSeparacao = true;
      continue;
    }

    if (REGUA.test(linha)) {
      fecharParagrafo();
      abrirBloco();
      emitir('· · ·');
      pedeSeparacao = true;
      continue;
    }

    const numerado = ITEM_NUMERADO.exec(linha);
    const item = numerado ?? ITEM.exec(linha);
    if (item) {
      fecharParagrafo();
      abrirBloco();
      const nivel = profundidade(item[1]!);
      const marcador = numerado
        ? `${numerado[2]!}.`
        : (MARCADORES[Math.min(nivel, MARCADORES.length - 1)] ?? MARCADORES[0]!);
      const texto = semMarcacao(numerado ? numerado[3]! : item[2]!);
      emitir(`${RECUO.repeat(nivel)}${marcador} ${texto}`);
      // Itens consecutivos são um bloco só: separar cada um do seguinte transformaria
      // uma lista de cinco itens em cinco blocos soltos.
      pedeSeparacao = false;
      continue;
    }

    const citacao = CITACAO.exec(linha);
    if (citacao) {
      fecharParagrafo();
      abrirBloco();
      emitir(`« ${semMarcacao(citacao[1]!)}`);
      pedeSeparacao = false;
      continue;
    }

    const tabela = TABELA.exec(linha);
    if (tabela) {
      fecharParagrafo();
      // A linha de alinhamento (`|---|:--:|`) é instrução de formatação de tabela, e não
      // tem o que dizer num bloco de texto corrido.
      if (SEPARADOR_DE_TABELA.test(tabela[1]!)) continue;
      abrirBloco();
      emitir(
        tabela[1]!
          .split('|')
          .map((celula) => semMarcacao(celula))
          .filter((celula) => celula !== '')
          .join(' · '),
      );
      pedeSeparacao = false;
      continue;
    }

    paragrafo.push(linha.trim());
  }
  fecharParagrafo();
  return linhas;
}
