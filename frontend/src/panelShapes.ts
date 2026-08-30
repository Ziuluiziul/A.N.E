// A silhueta do painel diz de que tipo ele é.
//
// Até aqui tudo era retângulo, e a ontologia vivia só na cor e no cabeçalho escrito.
// Cor sozinha não sobrevive a daltonismo nem a escala de cinza, e o cabeçalho só se lê
// de perto — de longe, uma cena de trezentos retângulos coloridos não distingue nota de
// decisão de quórum. A forma resolve os dois casos: ela é legível em silhueta, a
// qualquer distância, e independe de matiz.
//
// **A área é a mesma para todas.** Se o hexágono fosse desenhado dentro do mesmo
// retângulo, ele teria três quartos da área — e a forma passaria a medir importância
// sem que ninguém tivesse decidido isso. Cada polígono é escalado para que a área do
// que se vê seja a que `panelScale` mandou, e a proporção do descritor continua sendo a
// única coisa que muda o tamanho.
//
// A regra da ADR-002 continua valendo: o painel **é** o nó. A forma não é um corpo novo
// ao lado da placa; é o contorno da própria placa.

import * as THREE from 'three';

import type { EntityKind } from './contract';

/** Quantos lados cada tipo desenha. Dois é o retângulo, que não é polígono regular. */
export type PanelShape = 'retangulo' | 'hexagono' | 'octogono' | 'losango' | 'triangulo';

/**
 * A forma de cada tipo de entidade.
 *
 * As escolhas seguem uma leitura, e não a estética: o que **organiza** ganha muitos
 * lados, o que **afirma** fica retangular como uma folha de texto, e o que **decide**
 * ganha ponta. Assim a silhueta responde "isto é mapa, nota, ou veredicto?" antes de
 * qualquer palavra ser lida.
 */
export const SHAPE_BY_KIND: Record<EntityKind, PanelShape> = {
  // Organizam: muitos lados, silhueta próxima do círculo.
  moc: 'hexagono',
  'quorum-panel': 'octogono',
  agent: 'hexagono',
  // Afirmam: a folha de texto continua sendo uma folha.
  note: 'retangulo',
  reference: 'retangulo',
  register: 'retangulo',
  proposal: 'retangulo',
  'temporary-file': 'retangulo',
  evidence: 'retangulo',
  // Decidem ou julgam: ponta.
  'quorum-decision': 'losango',
  'quorum-vote': 'triangulo',
  rejection: 'losango',
  commit: 'losango',
  // Acontecem: o evento é um passo, e passo é retângulo achatado pela proporção.
  activity: 'retangulo',
  'quorum-member': 'hexagono',
};

const LADOS: Record<Exclude<PanelShape, 'retangulo'>, number> = {
  triangulo: 3,
  losango: 4,
  hexagono: 6,
  octogono: 8,
};

/**
 * Os vértices da silhueta, em coordenadas locais — as mesmas em que ela é desenhada.
 *
 * Isto é a **fonte única** da forma: a geometria e a caixa de texto saem daqui, e por
 * isso não podem discordar. A versão anterior descrevia a silhueta duas vezes, uma em
 * polígono e outra em fatores escritos à mão, e as duas descrições divergiam: os cantos
 * do texto do octógono caíam fora do contorno, e o triângulo — que é apoiado no lado de
 * cima, com a ponta para baixo — recebia o texto empurrado justamente para a ponta.
 *
 * A normalização é por **área**, não por caixa: um polígono regular de `n` lados e raio
 * `r` tem área `n·r²·sen(2π/n)/2`, e igualar isso a 1 faz toda silhueta gastar a mesma
 * tinta que o retângulo unitário. O preço é que a caixa envolvente deixa de ser o
 * quadrado unitário — o hexágono é largo e baixo, o losango transborda nos quatro lados —
 * e é por isso que a caixa de texto precisa ser procurada dentro do contorno real.
 */
function verticesDe(shape: PanelShape): Array<[number, number]> {
  if (shape === 'retangulo') {
    return [
      [-0.5, -0.5],
      [0.5, -0.5],
      [0.5, 0.5],
      [-0.5, 0.5],
    ];
  }
  const lados = LADOS[shape];
  // O giro põe um lado plano no alto ou embaixo em vez de um vértice: uma forma apoiada
  // lê como objeto assentado, e uma equilibrada na ponta lê como coisa prestes a cair.
  const giro = shape === 'losango' ? Math.PI / 2 : Math.PI / 2 + Math.PI / lados;
  const raio = Math.sqrt(2 / (lados * Math.sin((2 * Math.PI) / lados)));
  const vertices: Array<[number, number]> = [];
  for (let i = 0; i < lados; i += 1) {
    const angulo = giro + (2 * Math.PI * i) / lados;
    vertices.push([Math.cos(angulo) * raio, Math.sin(angulo) * raio]);
  }
  return vertices;
}

const CACHE = new Map<PanelShape, THREE.BufferGeometry>();

/**
 * A geometria da silhueta, compartilhada entre todas as instâncias do mesmo tipo.
 *
 * Uma geometria por forma, e não por painel: são cinco no total, e é o que mantém o
 * desenho instanciado — cada painel continua sendo uma matriz num buffer, não um objeto.
 */
export function panelShapeGeometry(shape: PanelShape): THREE.BufferGeometry {
  const existente = CACHE.get(shape);
  if (existente) return existente;
  const vertices = verticesDe(shape);
  const forma = new THREE.Shape();
  vertices.forEach(([x, y], i) => (i === 0 ? forma.moveTo(x, y) : forma.lineTo(x, y)));
  forma.closePath();
  const geometry = new THREE.ShapeGeometry(forma);
  CACHE.set(shape, geometry);
  return geometry;
}

/**
 * Meia-largura da silhueta à altura `y`, medida no contorno real.
 *
 * Todas as formas são simétricas em torno do eixo vertical, então uma travessia das
 * arestas basta: o polígono é convexo, logo a horizontal o corta em exatamente dois
 * pontos, e a distância entre eles é a largura disponível ali.
 */
function meiaLargura(vertices: Array<[number, number]>, y: number): number {
  let esquerda = Number.POSITIVE_INFINITY;
  let direita = Number.NEGATIVE_INFINITY;
  for (let i = 0; i < vertices.length; i += 1) {
    const [x0, y0] = vertices[i]!;
    const [x1, y1] = vertices[(i + 1) % vertices.length]!;
    if (y0 === y1) {
      if (y0 !== y) continue;
      esquerda = Math.min(esquerda, x0, x1);
      direita = Math.max(direita, x0, x1);
      continue;
    }
    const t = (y - y0) / (y1 - y0);
    if (t < 0 || t > 1) continue;
    const x = x0 + (x1 - x0) * t;
    esquerda = Math.min(esquerda, x);
    direita = Math.max(direita, x);
  }
  return direita > esquerda ? (direita - esquerda) / 2 : 0;
}

/** Cache da caixa útil: a busca roda cinco vezes na vida do processo, não por quadro. */
const CAIXA = new Map<PanelShape, { lado: number; centro: number }>();

/**
 * A **maior caixa da proporção do painel** que cabe dentro da silhueta.
 *
 * Não é a de maior área: no hexágono, que é largo e baixo, a de maior área é uma coluna
 * estreita e alta, e texto em coluna dentro de uma forma larga lê como erro. Fixar a
 * proporção na do próprio painel mantém o comprimento de linha comparável entre formas —
 * a silhueta muda o tipo da entidade, não o ritmo da leitura. Em coordenadas locais isso
 * é procurar o maior **quadrado**, porque a escala do painel já leva o quadrado à
 * proporção certa.
 *
 * A busca varre pares de alturas: a caixa cabe até onde couber na mais estreita das duas
 * bordas, e como a forma é convexa isso basta para garantir que os quatro cantos estão
 * dentro. `centro` é onde ela ficou — no triângulo ela sobe sozinha, fugindo da ponta.
 */
function caixaUtil(shape: PanelShape): { lado: number; centro: number } {
  const guardada = CAIXA.get(shape);
  if (guardada) return guardada;
  const vertices = verticesDe(shape);
  const alturas = vertices.map(([, y]) => y);
  const teto = Math.max(...alturas);
  const piso = Math.min(...alturas);
  const PASSOS = 240;
  let melhor = { lado: 0, centro: 0 };
  for (let i = 0; i <= PASSOS; i += 1) {
    const topo = teto - ((teto - piso) * i) / PASSOS;
    const larguraNoTopo = meiaLargura(vertices, topo);
    if (larguraNoTopo <= melhor.lado / 2) continue;
    for (let j = i + 1; j <= PASSOS; j += 1) {
      const base = teto - ((teto - piso) * j) / PASSOS;
      const largura = 2 * Math.min(larguraNoTopo, meiaLargura(vertices, base));
      const lado = Math.min(largura, topo - base);
      if (lado > melhor.lado) melhor = { lado, centro: (topo + base) / 2 };
    }
  }
  CAIXA.set(shape, melhor);
  return melhor;
}

/**
 * A área de texto de uma silhueta, dada a extensão da placa.
 *
 * `offsetY` é o centro da caixa encontrada, na mesma escala local em que a geometria é
 * desenhada — é ele que impede o texto de cair na ponta das formas assimétricas.
 */
export function textAreaOf(
  shape: PanelShape,
  extent: { width: number; height: number },
): { width: number; height: number; offsetY: number } {
  const { lado, centro } = caixaUtil(shape);
  return {
    width: extent.width * lado,
    height: extent.height * lado,
    offsetY: extent.height * centro,
  };
}

/**
 * Como o texto se acomoda em cada silhueta.
 *
 * Alinhar à esquerda e ancorar no topo é o certo numa folha retangular e o pior caso
 * numa forma pontiaguda: a primeira linha nasce onde a forma é mais estreita, e o bloco
 * fica visivelmente descolado do contorno. Onde a silhueta é simétrica em torno do eixo,
 * o texto também é.
 */
/**
 * Quanto a silhueta ultrapassa a caixa da placa, no eixo vertical.
 *
 * Como a normalização é por área, a forma não cabe no retângulo de mesma extensão: o
 * losango sobe 41% além dele e o triângulo 32%. Um título posicionado pela extensão
 * cairia **dentro** da própria forma nesses dois casos. Este fator é o que o afasta.
 */
export function shapeHeightRatio(shape: PanelShape): number {
  return shapeExtentRatio(shape).height;
}

/**
 * Quanto a silhueta ultrapassa a caixa da placa, nos dois eixos.
 *
 * Como a normalização é por área, a forma não cabe no retângulo de mesma extensão: o
 * triângulo é 1,52 vez mais largo que ela e o losango 1,41 em cada eixo. Quem mede
 * distância entre painéis precisa disto — medir pela extensão dizia que três votos
 * cabiam lado a lado quando os triângulos deles já se tocavam.
 */
export function shapeExtentRatio(shape: PanelShape): { width: number; height: number } {
  const vertices = verticesDe(shape);
  const xs = vertices.map(([x]) => x);
  const ys = vertices.map(([, y]) => y);
  return {
    width: Math.max(...xs) - Math.min(...xs),
    height: Math.max(...ys) - Math.min(...ys),
  };
}

export function textAlignmentOf(shape: PanelShape): {
  textAlign: 'left' | 'center';
  anchorX: 'left' | 'center';
} {
  return shape === 'retangulo'
    ? { textAlign: 'left', anchorX: 'left' }
    : { textAlign: 'center', anchorX: 'center' };
}

export function shapeOf(kind: EntityKind): PanelShape {
  return SHAPE_BY_KIND[kind] ?? 'retangulo';
}

/** Libera o cache. Só os testes precisam disto; a cena vive com as cinco formas. */
export function disposePanelShapes(): void {
  for (const geometry of CACHE.values()) geometry.dispose();
  CACHE.clear();
}
