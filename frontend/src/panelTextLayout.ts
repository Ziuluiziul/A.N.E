// Onde o texto cabe dentro da placa — e o que fica de fora quando não cabe.
//
// Módulo puro: sem Three.js, sem troika, sem câmera. Recebe o descritor, a extensão
// mundial da placa e as frases candidatas, e devolve a caixa tipográfica com o
// recorte já resolvido. É o que permite provar, sem GPU, que nenhuma linha atravessa
// a borda de nenhum dos seis tipos de painel.
//
// **A proporção manda no que cabe.** Uma ponte 21:9 é larga e baixa: sobra largura
// para o título e falta altura para linhas. Um quórum 3:4 é o inverso. O layout não
// tenta corrigir isso — é justamente a diferença que faz a silhueta comunicar função.
//
// **Truncamento acontece aqui, nunca no descritor.** O título canônico continua
// íntegro em `PanelDescriptor.title`; a elipse existe só na saída. Linha de corpo que
// não cabe é omitida inteira, porque meia frase de evidência é outra evidência.
//
// **Um corpo de fonte por painel, e o orçamento medido nele.** Um `Text` do troika
// tem um único `fontSize` para o bloco inteiro: não existe título maior que o corpo
// dentro do mesmo objeto, e dar um objeto a cada um dobraria o pool de 64 que o teto
// existe para segurar. A versão anterior estimava o encaixe com um corpo 28% menor do
// que o que a GPU de fato desenhava — o bloco estourava a placa sempre, e a correção
// de estouro respondia apagando o corpo inteiro. Era por isso que o painel nunca
// mostrava mais que uma linha. Aqui a estimativa usa exatamente a fonte desenhada.
//
// A hierarquia tipográfica passa a vir da posição e da caixa: a categoria em
// maiúsculas ocupa a primeira linha e faz o papel da faixa de cabeçalho, o título vem
// logo abaixo, e o corpo segue. Nenhuma dessas distinções depende de cor.

import type { LodLevel } from './lod';
import type { PanelDescriptor, PanelLine } from './panels';
import { textAlignmentOf } from './panelShapes';
import type { WorldExtent } from './panelScale';

/**
 * O que cada nível deixa escrever. É a tabela da ADR-002, e nada além dela.
 *
 * Até aqui o painel desenhava cabeçalho, título e corpo em qualquer nível, e a
 * densidade de leitura vinha só de quantas linhas cabiam. Isso apagava a diferença
 * entre `identifiable` — em que se quer reconhecer um nome de longe — e `legible`,
 * em que se quer ler uma frase. Um degrau que não muda o que aparece não é degrau.
 */
const MOSTRA_CABECALHO: ReadonlySet<LodLevel> = new Set<LodLevel>(['legible', 'expanded']);
const MOSTRA_TITULO: ReadonlySet<LodLevel> = new Set<LodLevel>([
  'identifiable',
  'legible',
  'expanded',
]);
/** Quantas frases de corpo cada nível admite. `expanded` é o que couber. */
const CORPO_POR_NIVEL: Record<LodLevel, number> = {
  distant: 0,
  structural: 0,
  identifiable: 0,
  legible: 1,
  expanded: Number.POSITIVE_INFINITY,
};

/** Margem interna, como fração da menor dimensão da placa. */
const MARGEM = 0.06;
/** Altura de linha em múltiplos do corpo da fonte. */
const ENTRELINHA = 1.35;
/** Corpo da fonte como fração da altura útil. */
const FONTE_DA_ALTURA = 0.17;
/**
 * Redução da fonte no painel escolhido.
 *
 * Expandir multiplicava a placa **e** os glifos: a superfície crescia 2,2× em cada
 * eixo e continuavam cabendo as mesmas três ou quatro linhas. Um painel de nota com
 * abertura e quatro claims compunha treze linhas e mostrava três — havia rolagem, mas
 * ela virava a única forma de ler o que já caberia na tela.
 *
 * Aqui a placa expandida vira **superfície de leitura**: ela cresce e a tipografia não,
 * de modo que o ganho de área vira ganho de texto visível. O fator desfaz a expansão da
 * placa e ainda aperta um pouco, porque quem escolheu o painel está perto dele e lê
 * confortavelmente um corpo menor.
 */
const FONTE_EXPANDIDA = 0.46;
/** Teto pela largura: sem ele a ponte 21:9 ganharia tipografia desproporcional. */
const FONTE_DA_LARGURA = 0.072;
/** Afastamento em z: tira o texto do plano da placa sem o soltar dela. */
export const TEXT_Z_OFFSET = 0.05;
/** Largura média de um glifo em relação ao corpo da fonte, para estimar o encaixe. */
const LARGURA_DO_GLIFO = 0.52;

export interface PanelTextLayout {
  localX: number;
  localY: number;
  localZ: number;
  maxWidth: number;
  maxHeight: number;
  fontSize: number;
  lineHeight: number;
  textAlign: 'left' | 'center';
  anchorX: 'left' | 'center';
  anchorY: 'top' | 'middle';
  clipRect: [number, number, number, number];
  /** O que efetivamente será desenhado, já recortado. */
  header: string;
  title: string;
  body: string[];
  /** Verdadeiro quando o título precisou de elipse na saída. */
  titleTruncated: boolean;
  /** Frases descartadas inteiras por falta de altura. */
  omittedLines: number;
  /** O painel mostra o conteúdo inteiro e aceita rolagem. */
  scrollable: boolean;
  /** Altura do bloco composto, em unidades de mundo. */
  contentHeight: number;
  /** O máximo que se pode rolar sem revelar vazio abaixo da última linha. */
  maxScroll: number;
  /** Quanto o bloco desceu para ficar centrado na forma. Zero quando há rolagem. */
  verticalPadding: number;
  /** O deslocamento efetivamente aplicado, já limitado. */
  scrollOffset: number;
}

/** Quantas linhas a frase ocupa depois de quebrada na largura útil. */
function linhasOcupadas(texto: string, fontSize: number, largura: number): number {
  const porLinha = Math.max(1, Math.floor(largura / (fontSize * LARGURA_DO_GLIFO)));
  return Math.max(1, Math.ceil(texto.length / porLinha));
}

/** Elipse por largura disponível, aplicada só na saída. */
function comElipse(
  texto: string,
  fontSize: number,
  largura: number,
  maxChars: number,
): { text: string; truncated: boolean } {
  const porLargura = Math.max(1, Math.floor(largura / (fontSize * LARGURA_DO_GLIFO)));
  const limite = Math.min(porLargura, maxChars);
  if (texto.length <= limite) return { text: texto, truncated: false };
  return { text: `${texto.slice(0, Math.max(limite - 1, 1))}…`, truncated: true };
}

/**
 * A caixa de texto de um painel.
 *
 * O ponto de ancoragem é o canto superior esquerdo da área útil, e as coordenadas são
 * locais à placa — quem as leva ao mundo é a mesma matriz que orienta o corpo, para
 * que texto e placa nunca divirjam de orientação.
 *
 * A extensão que chega aqui é a **efetiva**: expandir o painel aumenta a placa, e é
 * por essa via, e só por ela, que o nó expandido passa a caber mais conteúdo. Não há
 * regra de layout separada para o estado expandido.
 */
export function layoutPanelText(
  descriptor: PanelDescriptor,
  /** A caixa **útil** da silhueta, não a extensão da placa. Ver `textAreaOf`. */
  extent: WorldExtent,
  lines: PanelLine[],
  level: LodLevel,
  /**
   * Deslocamento de leitura, em unidades de mundo.
   *
   * Só tem efeito quando o painel é rolável. Zero é o topo do conteúdo; valores
   * positivos revelam o que está abaixo.
   */
  scrollOffset = 0,
): PanelTextLayout {
  const margem = Math.min(extent.width, extent.height) * MARGEM;
  const larguraUtil = Math.max(extent.width - margem * 2, 0.01);
  const alturaUtil = Math.max(extent.height - margem * 2, 0.01);

  const reducao = level === 'expanded' ? FONTE_EXPANDIDA : 1;
  const fonte =
    Math.min(alturaUtil * FONTE_DA_ALTURA, larguraUtil * FONTE_DA_LARGURA) * reducao;
  const entrelinha = fonte * ENTRELINHA;

  const cabecalho = MOSTRA_CABECALHO.has(level)
    ? comElipse(descriptor.category, fonte, larguraUtil, 40)
    : { text: '', truncated: false };
  const titulo = MOSTRA_TITULO.has(level)
    ? comElipse(descriptor.title, fonte, larguraUtil, descriptor.truncation.titleMaxChars)
    : { text: '', truncated: false };

  // Cabeçalho e título consomem orçamento como qualquer outra linha: eles são
  // desenhados no mesmo bloco, e fingir o contrário é o que fazia a caixa estourar.
  //
  // A linha vazia depois do cabeçalho conta junto. Ela existe pela mesma razão que o
  // documento separa os próprios blocos: colada, a categoria lia como se fosse o primeiro
  // heading do texto — "NOTA" e "FINALIDADE" chegavam como um par.
  const ocupadoPeloTopo =
    (cabecalho.text === '' ? 0 : linhasOcupadas(cabecalho.text, fonte, larguraUtil) + 1) +
    (titulo.text === '' ? 0 : linhasOcupadas(titulo.text, fonte, larguraUtil));
  let restante = alturaUtil - ocupadoPeloTopo * entrelinha;
  const teto = CORPO_POR_NIVEL[level];
  // O painel selecionado mostra o conteúdo **inteiro** e rola.
  //
  // Nos outros níveis o corte é política de leitura: um painel distante que despejasse
  // tudo seria ilegível, e a omissão é medida. Já quem escolheu um painel pediu para
  // ler, e devolver-lhe um resumo com "3 omitidas" é negar o que ele pediu enquanto o
  // dado está a um passo. Aqui o corte sai, e quem limita passa a ser o recorte
  // (`clipRect`) mais o deslocamento de leitura.
  const rolavel = level === 'expanded';
  const corpo: string[] = [];
  let omitidas = 0;
  let alturaDoCorpo = 0;
  for (const linha of lines) {
    // O teto do nível não é falta de espaço: `omittedLines` mede o que não coube,
    // e confundir as duas coisas faria a telemetria acusar aperto onde há política.
    if (!rolavel && corpo.length >= teto) break;
    // Nem toda frase candidata acrescenta algo: a categoria já é o cabeçalho, e a
    // linha de nível `identifiable` é o rótulo curto — que para um MOC é o próprio
    // título. Repetido logo abaixo dele, ele lia como se o painel tivesse dois nomes.
    // Repetição não é omissão: não entra na contagem do que se perdeu por falta de
    // espaço, porque nada se perdeu.
    //
    // A comparação é de **igualdade**, e antes era de continência: `title.includes(...)`
    // descartava qualquer linha do corpo que por acaso fosse pedaço do título — e,
    // quando o documento passou a separar blocos, descartou também todas as linhas
    // vazias, porque todo título com duas palavras contém um espaço. O documento
    // chegava sem nenhuma separação, que é justamente o que ela existe para dar.
    const conteudo = linha.text.trim();
    if (conteudo !== '' && (conteudo === descriptor.category || conteudo === descriptor.title)) {
      continue;
    }
    const alturas = linhasOcupadas(linha.text, fonte, larguraUtil) * entrelinha;
    if (!rolavel && alturas > restante) {
      omitidas += 1;
      continue;
    }
    corpo.push(linha.text);
    restante -= alturas;
    alturaDoCorpo += alturas;
  }

  const alturaTotal = ocupadoPeloTopo * entrelinha + alturaDoCorpo;
  // O quanto se pode rolar sem revelar vazio abaixo da última linha.
  const rolagemMaxima = rolavel ? Math.max(alturaTotal - alturaUtil, 0) : 0;
  const rolagem = Math.min(Math.max(scrollOffset, 0), rolagemMaxima);

  // **Cabendo, o texto se centra.** Ancorar sempre no topo é o certo para conteúdo que
  // transborda — é de lá que a rolagem parte —, mas para um bloco curto dentro de uma
  // forma pontiaguda ele deixava o texto grudado na borda de cima e a metade de baixo
  // vazia. Quando não há o que rolar não há de onde partir, e centrar é o que faz o
  // bloco parecer pertencer à silhueta em vez de flutuar dentro dela.
  const sobra = Math.max(alturaUtil - alturaTotal, 0);
  const centragem = rolagemMaxima > 0 ? 0 : sobra / 2;

  return {
    localX:
      textAlignmentOf(descriptor.shape).anchorX === 'center' ? 0 : -extent.width / 2 + margem,
    // Rolar é subir o bloco: o topo do painel continua onde está, e o texto desliza
    // por baixo do recorte.
    localY: extent.height / 2 - margem + rolagem - centragem,
    localZ: TEXT_Z_OFFSET,
    maxWidth: larguraUtil,
    maxHeight: alturaUtil,
    fontSize: fonte,
    lineHeight: ENTRELINHA,
    // Forma pontiaguda centra o texto; folha retangular alinha à esquerda. Ancorar no
    // topo-esquerda de um losango punha a primeira linha onde a forma é mais estreita.
    ...textAlignmentOf(descriptor.shape),
    anchorY: 'top',
    // Recorte no espaço **do objeto de texto**, cuja origem é o canto superior
    // esquerdo útil e cujo conteúdo flui para baixo. Expresso em coordenadas do painel
    // — como estava — ele recortaria o lugar errado, e por isso nunca chegou a ser
    // aplicado. Ele desce com a rolagem para continuar coincidindo com a placa.
    clipRect:
      textAlignmentOf(descriptor.shape).anchorX === 'center'
        ? [-larguraUtil / 2, -alturaUtil - rolagem, larguraUtil / 2, -rolagem]
        : [0, -alturaUtil - rolagem, larguraUtil, -rolagem],
    /** Quanto o bloco desceu para se centrar. Zero quando há rolagem. */
    verticalPadding: centragem,
    scrollable: rolavel,
    contentHeight: alturaTotal,
    maxScroll: rolagemMaxima,
    scrollOffset: rolagem,
    header: cabecalho.text,
    title: titulo.text,
    body: corpo,
    titleTruncated: titulo.truncated,
    omittedLines: omitidas,
  };
}

/**
 * A composição do painel: categoria, título e **todas** as frases que couberam.
 *
 * Até 3.3 esta função descartava tudo depois da primeira linha de corpo, mesmo quando
 * o layout tinha aprovado outras. Era o que impedia o nível `expanded` de existir de
 * fato: aproximar aumentava o painel e não aumentava o que se lia. Quem decide o que
 * cabe é `layoutPanelText`; aqui só se emite o que ele aprovou.
 */
export function composeText(layout: PanelTextLayout): string {
  // O título saiu do bloco: ele é desenhado acima e fora da placa, por um objeto
  // próprio. Repeti-lo aqui faria o painel dizer o próprio nome duas vezes.
  //
  // O espaço depois do cabeçalho é uma linha em branco de verdade, e não `''`: a filtragem
  // abaixo existe para sumir com cabeçalho e título ausentes, e um separador vazio sumiria
  // junto. O orçamento de `layoutPanelText` já contou com ela.
  const cabecalho = layout.header === '' ? [] : [layout.header.toUpperCase(), ' '];
  return [...cabecalho, ...layout.body].filter((parte) => parte !== '').join('\n');
}
