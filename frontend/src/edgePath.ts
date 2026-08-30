// O caminho que uma aresta percorre entre duas placas — e o que ela contorna no meio.
//
// **Por que isto existe.** A aresta ia de centro a centro, em linha reta, e as duas
// pontas ficavam enterradas dentro das placas que ela liga. Medido na projeção viva, com
// 993 pares desenhados, 235 deles atravessavam ainda uma **terceira** placa: a linha
// entrava por cima do texto de uma nota que não tinha nada a ver com aquela relação. É a
// mesma classe de defeito que a sobreposição de placas, só que ninguém a media.
//
// **O que este módulo garante, e o que não garante.** A aparagem é exata: a linha começa
// e termina fora do círculo que cada placa varre ao girar para a câmera, então ela nunca
// entra na placa dos próprios extremos, seja qual for o ângulo. O desvio é aproximado: um
// número fixo de tentativas empurrando o ponto de controle para fora do pior obstáculo.
// Ele desfaz a maioria das travessias e não promete desfazer todas — prometer isso exigiria
// roteamento global, que muda o traço de uma aresta por causa de outra que ninguém está
// olhando.
//
// **Por que o círculo varrido, e não a caixa.** A placa é orientada à câmera: ela gira, e o
// que ela ocupa ao longo de uma órbita inteira é o círculo circunscrito. Aparar pela caixa
// deixaria a linha correta numa direção e por dentro da placa na direção seguinte, e a
// geometria é construída uma vez só — não há como remedi-la por quadro.
//
// Módulo puro: sem Three.js, sem DOM. Recebe pontos e devolve pontos.

import type { Vec3 } from './layout';

/** Uma placa que a linha precisa evitar: onde ela está e quanto ela varre. */
export interface EdgeObstacle {
  id: string;
  position: Vec3;
  radius: number;
}

/**
 * Onde a ponta da linha para, em frações do raio varrido pela placa.
 *
 * Era 1,06 — fora do círculo inteiro, com folga. O raciocínio estava certo para o
 * **meio** do caminho e errado para a ponta: o círculo varrido é o que a placa cobre ao
 * longo de uma órbita completa, e usá-lo nos dois extremos abria um vão do tamanho da
 * meia-diagonal entre a linha e a placa que ela liga. De longe, a relação parecia não
 * chegar a lugar nenhum.
 *
 * Na ponta a exigência é outra, e é mais fraca: a linha pode entrar **por baixo da
 * própria placa**, porque a placa a esconde — ela é opaca e escreve profundidade. O que
 * não pode é atravessar uma placa de terceiros, e disso cuida o desvio, que continua
 * usando o círculo inteiro com folga.
 *
 * 0,82 é a medida da caixa, não um gosto: numa nota 4:3 a meia-largura vale 0,80 do raio
 * varrido e a meia-altura, 0,60. A linha termina, portanto, na borda lateral da placa ou
 * ligeiramente sob ela — encostada, que é o que se pediu.
 */
const FOLGA_DA_PONTA = 0.82;

/**
 * Folga que o desvio abre além do raio do obstáculo.
 *
 * O desvio que apenas tangencia não se distingue da travessia: a linha passa raspando a
 * borda da placa, e de outro ângulo volta a cruzá-la.
 */
const FOLGA_DO_DESVIO = 1.12;

/** Quantas vezes o ponto de controle é reempurrado antes de a curva ser aceita como está. */
const TENTATIVAS_DE_DESVIO = 6;

/** Em quantos pedaços a curva é amostrada. Menos que isto e o arco vira um bico. */
const AMOSTRAS_DA_CURVA = 14;

/**
 * O mínimo de linha que sobra para valer o desenho, em frações do raio das duas placas.
 *
 * Duas placas quase encostadas produziriam um toco de dois pixels entre elas, que não lê
 * como ligação e ainda soma uma primitiva. A relação continua existindo no registro e na
 * seleção; o que se recusa é desenhar um traço que não se lê.
 */
const TRECHO_MINIMO = 0.12;

function subtrair(a: Vec3, b: Vec3): Vec3 {
  return { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z };
}

function comprimento(v: Vec3): number {
  return Math.hypot(v.x, v.y, v.z);
}

function interpolar(a: Vec3, b: Vec3, t: number): Vec3 {
  return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, z: a.z + (b.z - a.z) * t };
}

/** O ponto do segmento mais próximo de `p`, e a que distância ele passa. */
function aproximacao(a: Vec3, b: Vec3, p: Vec3): { ponto: Vec3; distancia: number; t: number } {
  const direcao = subtrair(b, a);
  const total = direcao.x * direcao.x + direcao.y * direcao.y + direcao.z * direcao.z;
  const t =
    total < 1e-9
      ? 0
      : Math.min(
          Math.max(
            ((p.x - a.x) * direcao.x + (p.y - a.y) * direcao.y + (p.z - a.z) * direcao.z) / total,
            0,
          ),
          1,
        );
  const ponto = interpolar(a, b, t);
  return { ponto, distancia: comprimento(subtrair(ponto, p)), t };
}

/**
 * Apara as duas pontas na borda das placas que a aresta liga.
 *
 * Devolve `null` quando o que sobra é curto demais para ler como ligação — o que só
 * acontece entre duas placas praticamente encostadas.
 */
export function trimEdge(
  a: Vec3,
  b: Vec3,
  raioA: number,
  raioB: number,
): { a: Vec3; b: Vec3 } | null {
  const total = comprimento(subtrair(b, a));
  if (total < 1e-6) return null;
  const recuoA = raioA * FOLGA_DA_PONTA;
  const recuoB = raioB * FOLGA_DA_PONTA;
  const sobra = total - recuoA - recuoB;
  if (sobra <= (raioA + raioB) * TRECHO_MINIMO) return null;
  return {
    a: interpolar(a, b, recuoA / total),
    b: interpolar(a, b, 1 - recuoB / total),
  };
}

/**
 * O caminho da aresta: aparado nas pontas e desviado do que atravessaria no meio.
 *
 * Devolve dois pontos quando a reta já está livre — que é o caso comum, e o que mantém a
 * geometria barata —, e a curva amostrada quando foi preciso contornar.
 *
 * O desvio é uma quadrática de um ponto de controle só. Com dois obstáculos em lados
 * opostos ela não resolve os dois, e é por isso que existe um teto de tentativas em vez
 * de um laço até caber: a linha que insiste em contornar tudo deixa de ler como ligação
 * entre dois pontos e vira um caminho com opinião própria sobre o mapa.
 */
export function edgePath(
  a: Vec3,
  b: Vec3,
  raioA: number,
  raioB: number,
  obstaculos: readonly EdgeObstacle[],
  excluir: ReadonlySet<string>,
): Vec3[] | null {
  const aparada = trimEdge(a, b, raioA, raioB);
  if (!aparada) return null;
  if (obstaculos.length === 0) return [aparada.a, aparada.b];

  // Só entram na conta as placas que **poderiam** estar no caminho: as que cabem na
  // esfera que envolve o segmento, com margem para o desvio se abrir. Sem esta peneira,
  // cada aresta era medida contra as 479 placas da cena a cada tentativa, e o custo de
  // construir a geometria crescia com o produto das duas populações.
  const meio = interpolar(aparada.a, aparada.b, 0.5);
  const meioComprimento = comprimento(subtrair(aparada.b, aparada.a)) / 2;
  const relevantes = obstaculos.filter(
    (obstaculo) =>
      !excluir.has(obstaculo.id) &&
      comprimento(subtrair(obstaculo.position, meio)) <
        meioComprimento + obstaculo.radius * (1 + FOLGA_DO_DESVIO),
  );
  let controle = interpolar(aparada.a, aparada.b, 0.5);
  let desviou = false;

  for (let tentativa = 0; tentativa < TENTATIVAS_DE_DESVIO; tentativa += 1) {
    const pontos = desviou ? amostrar(aparada.a, controle, aparada.b) : [aparada.a, aparada.b];
    const pior = piorObstaculo(pontos, relevantes);
    if (!pior) return desviou ? pontos : [aparada.a, aparada.b];
    // O empurrão vai do centro do obstáculo para o ponto em que a linha passa mais
    // perto dele — a direção mais curta para sair. Dobrado porque a quadrática só
    // alcança metade do ponto de controle no meio do arco.
    const fuga = subtrair(pior.ponto, pior.obstaculo.position);
    const norma = comprimento(fuga);
    const direcao =
      norma < 1e-6
        ? perpendicularA(subtrair(aparada.b, aparada.a))
        : { x: fuga.x / norma, y: fuga.y / norma, z: fuga.z / norma };
    const empurrao = (pior.obstaculo.radius * FOLGA_DO_DESVIO - pior.distancia) * 2;
    controle = {
      x: controle.x + direcao.x * empurrao,
      y: controle.y + direcao.y * empurrao,
      z: controle.z + direcao.z * empurrao,
    };
    desviou = true;
  }
  return amostrar(aparada.a, controle, aparada.b);
}

/** Um vetor qualquer perpendicular ao dado. Só serve ao caso degenerado do desvio. */
function perpendicularA(v: Vec3): Vec3 {
  const outro = Math.abs(v.z) < Math.abs(v.x) ? { x: 0, y: 0, z: 1 } : { x: 1, y: 0, z: 0 };
  const cruz = {
    x: v.y * outro.z - v.z * outro.y,
    y: v.z * outro.x - v.x * outro.z,
    z: v.x * outro.y - v.y * outro.x,
  };
  const norma = comprimento(cruz) || 1;
  return { x: cruz.x / norma, y: cruz.y / norma, z: cruz.z / norma };
}

/** A quadrática amostrada, com as duas pontas exatas. */
function amostrar(a: Vec3, controle: Vec3, b: Vec3): Vec3[] {
  const pontos: Vec3[] = [];
  for (let i = 0; i <= AMOSTRAS_DA_CURVA; i += 1) {
    const t = i / AMOSTRAS_DA_CURVA;
    const um = 1 - t;
    pontos.push({
      x: um * um * a.x + 2 * um * t * controle.x + t * t * b.x,
      y: um * um * a.y + 2 * um * t * controle.y + t * t * b.y,
      z: um * um * a.z + 2 * um * t * controle.z + t * t * b.z,
    });
  }
  return pontos;
}

/** O obstáculo mais penetrado pela polilinha, ou nada quando ela está livre. */
function piorObstaculo(
  pontos: Vec3[],
  obstaculos: readonly EdgeObstacle[],
): { obstaculo: EdgeObstacle; ponto: Vec3; distancia: number } | null {
  let pior: { obstaculo: EdgeObstacle; ponto: Vec3; distancia: number } | null = null;
  let maiorPenetracao = 0;
  for (const obstaculo of obstaculos) {
    for (let i = 0; i + 1 < pontos.length; i += 1) {
      const { ponto, distancia } = aproximacao(pontos[i]!, pontos[i + 1]!, obstaculo.position);
      const penetracao = obstaculo.radius - distancia;
      if (penetracao > maiorPenetracao) {
        maiorPenetracao = penetracao;
        pior = { obstaculo, ponto, distancia };
      }
    }
  }
  return pior;
}

/**
 * Recorta uma polilinha segundo o padrão, em unidades de mundo.
 *
 * A fase corre ao longo do caminho **inteiro**, e não por pedaço: recomeçar o padrão a
 * cada amostra da curva faria um traço-ponto virar um pontilhado uniforme, e a
 * assinatura da família — que é o que substitui a cor — deixaria de distinguir.
 *
 * Padrão vazio devolve a polilinha inteira, em pares de vértices. A fase começa
 * desenhando, de modo que o traço nasça junto à origem.
 */
/** Teto de segmentos por caminho. Sem ele, uma aresta de comprimento não finito
 *  ou um observatório com milhares de painéis enche o array até o motor lançar
 *  `RangeError: Invalid array length`. */
const MAX_SEGMENTOS_TRACEJADOS = 2_048;

export function dashPath(pontos: Vec3[], pattern: number[]): number[] {
  const vertices: number[] = [];
  if (pontos.length < 2) return vertices;
  if (pattern.length === 0) {
    for (let i = 0; i + 1 < pontos.length; i += 1) {
      const a = pontos[i]!;
      const b = pontos[i + 1]!;
      // Pedaço de comprimento nulo não vira geometria: ele desenharia nada e ainda
      // ocuparia dois vértices no buffer.
      const trecho = comprimento(subtrair(b, a));
      if (!Number.isFinite(trecho) || trecho < 1e-6) continue;
      vertices.push(a.x, a.y, a.z, b.x, b.y, b.z);
    }
    return vertices;
  }

  let indice = 0;
  let restanteNoPasso = pattern[0]!;
  let desenhando = true;
  for (let i = 0; i + 1 < pontos.length; i += 1) {
    const a = pontos[i]!;
    const b = pontos[i + 1]!;
    const total = comprimento(subtrair(b, a));
    if (!Number.isFinite(total) || total < 1e-9) continue;
    let percorrido = 0;
    while (percorrido < total) {
      if (vertices.length / 6 >= MAX_SEGMENTOS_TRACEJADOS) return vertices;
      if (!Number.isFinite(restanteNoPasso) || restanteNoPasso <= 0) break;
      const passo = Math.min(restanteNoPasso, total - percorrido);
      if (desenhando) {
        const t0 = percorrido / total;
        const t1 = (percorrido + passo) / total;
        const de = interpolar(a, b, t0);
        const para = interpolar(a, b, t1);
        vertices.push(de.x, de.y, de.z, para.x, para.y, para.z);
      }
      percorrido += passo;
      restanteNoPasso -= passo;
      if (restanteNoPasso <= 1e-9) {
        indice += 1;
        restanteNoPasso = pattern[indice % pattern.length]!;
        desenhando = !desenhando;
      }
    }
  }
  return vertices;
}
