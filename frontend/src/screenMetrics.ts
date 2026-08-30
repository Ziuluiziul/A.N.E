// Medição de espaço de tela, em dois protocolos.
//
// A auditoria de 3.5-A mediu com a pose que **cada cenário produz** — mesma viewport,
// câmeras diferentes. Isso mistura duas coisas: o que o layout fez e o que o
// autoenquadramento fez. O ganho de ocupação daquele incremento era real, mas atribuível
// ao enquadramento; o de paralaxe não podia ser atribuído ao layout.
//
// Aqui os dois protocolos ficam separados e nomeados:
//
// - **câmera fixa** — posição, alvo, FOV e viewport idênticos entre cenários. Mede
//   causalmente o layout, porque a única variável que muda são as posições.
// - **autoenquadramento** — a pose que `cameraPoseForExtent` produz para cada cenário.
//   Mede o que o usuário recebe, que é outra pergunta e igualmente legítima.
//
// Nenhum dos dois conta aresta, casca ou ambiente: a unidade é a caixa projetada do
// painel. Contar pixels não-fundo mediria sobretudo o emaranhado de arestas, que é
// justamente o que se quer reduzir.

import type { Projection, ProjectionNode } from './contract';
import { cameraPoseForExtent } from './depth';
import type { LayoutMap, Vec3 } from './layout';
import { describePanel } from './panels';
import { panelWorldExtent } from './panelScale';

export interface Viewport {
  width: number;
  height: number;
}

export const VIEWPORT_PADRAO: Viewport = { width: 1600, height: 900 };

export interface CameraPose {
  position: Vec3;
  target: Vec3;
  fov: number;
}

/**
 * A pose fixa do protocolo causal.
 *
 * Os números são constantes declaradas, e não derivadas de extensão nenhuma: derivar
 * seria reintroduzir a dependência do layout que este protocolo existe para eliminar.
 * A direção repete a de `cameraPoseForExtent` para que as duas medições olhem o atlas
 * do mesmo ângulo, e a distância cabe o corpus com folga em qualquer variante testada.
 */
export const POSE_FIXA: CameraPose = {
  position: { x: 108.8, y: -220.8, z: 204.8 },
  target: { x: 0, y: -7.4, z: 0.9 },
  fov: 38,
};

export function poseAutoenquadrada(
  radius: number,
  depth: number,
  viewport: Viewport = VIEWPORT_PADRAO,
): CameraPose {
  const pose = cameraPoseForExtent(radius, depth, viewport.width / viewport.height);
  return { position: pose.position, target: pose.target, fov: pose.fov };
}

export interface CaixaProjetada {
  id: string;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  /** Profundidade ao longo do eixo de visada, para decidir quem oclui quem. */
  depth: number;
}

function subtrai(a: Vec3, b: Vec3): Vec3 {
  return { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z };
}
function cruza(a: Vec3, b: Vec3): Vec3 {
  return { x: a.y * b.z - a.z * b.y, y: a.z * b.x - a.x * b.z, z: a.x * b.y - a.y * b.x };
}
function normaliza(v: Vec3): Vec3 {
  const n = Math.hypot(v.x, v.y, v.z) || 1;
  return { x: v.x / n, y: v.y / n, z: v.z / n };
}
function produto(a: Vec3, b: Vec3): number {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

/**
 * Projeta a caixa de cada painel, do jeito que a cena projeta.
 *
 * As placas são orientadas à câmera, então a caixa projetada é a extensão do painel
 * dividida pela profundidade — não há encurtamento por inclinação a considerar.
 */
export function projetarCaixas(
  projection: Projection,
  positions: LayoutMap,
  ids: ReadonlySet<string>,
  pose: CameraPose,
  viewport: Viewport = VIEWPORT_PADRAO,
): CaixaProjetada[] {
  const paraTras = normaliza(subtrai(pose.position, pose.target));
  const direita = normaliza(cruza({ x: 0, y: 0, z: 1 }, paraTras));
  const acima = normaliza(cruza(paraTras, direita));
  const tanV = Math.tan((pose.fov * Math.PI) / 360);
  const tanH = tanV * (viewport.width / viewport.height);

  const caixas: CaixaProjetada[] = [];
  for (const node of projection.nodes) {
    if (!ids.has(node.id)) continue;
    const p = positions.get(node.id);
    if (!p) continue;
    const rel = subtrai(p, pose.position);
    const profundidade = -produto(rel, paraTras);
    if (profundidade <= 0.1) continue;
    const extensao = panelWorldExtent(describePanel(node));
    const lateral = produto(rel, direita);
    const alto = produto(rel, acima);
    const cx = (lateral / (profundidade * tanH)) * (viewport.width / 2) + viewport.width / 2;
    const cy = viewport.height / 2 - (alto / (profundidade * tanV)) * (viewport.height / 2);
    const meiaL = (extensao.width / 2 / (profundidade * tanH)) * (viewport.width / 2);
    const meiaA = (extensao.height / 2 / (profundidade * tanV)) * (viewport.height / 2);
    caixas.push({
      id: node.id,
      x0: cx - meiaL,
      y0: cy - meiaA,
      x1: cx + meiaL,
      y1: cy + meiaA,
      depth: profundidade,
    });
  }
  return caixas;
}

export interface MetricasDeTela {
  entidades: number;
  paresQueSeIntersectam: number;
  areaDeInterseccao_px2: number;
  areaDeCaixas_px2: number;
  /**
   * Intersecção sobre a **soma das áreas das caixas**.
   *
   * Dois denominadores diferentes são legítimos e medem coisas diferentes, e por isso
   * carregam nomes diferentes. Este divide pela soma — que conta a área sobreposta
   * duas vezes — e responde "que fração do desenho é redundante".
   */
  intersectionOverBoxArea: number;
  /**
   * Intersecção sobre a **área efetivamente ocupada** no viewport.
   *
   * O denominador conta cada pixel uma vez só, então é sempre menor que a soma e o
   * quociente é sempre maior. Responde "quanto do que se vê está disputado". Foi o
   * denominador dos critérios de aceite de 3.5-B, e está aqui nomeado para nunca mais
   * ser confundido com o de cima.
   */
  intersectionOverViewportOccupancy: number;
  totalmenteOcluidas: number;
  recortadasPelaBorda: number;
  ocupacaoDoViewport: number;
}

export function metricasDeTela(
  caixas: CaixaProjetada[],
  viewport: Viewport = VIEWPORT_PADRAO,
): MetricasDeTela {
  let pares = 0;
  let areaInterseccao = 0;
  const ocluidas = new Set<string>();
  for (let i = 0; i < caixas.length; i += 1) {
    for (let j = i + 1; j < caixas.length; j += 1) {
      const a = caixas[i]!;
      const b = caixas[j]!;
      const w = Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0);
      const h = Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0);
      if (w <= 0 || h <= 0) continue;
      pares += 1;
      areaInterseccao += w * h;
      const [perto, longe] = a.depth <= b.depth ? [a, b] : [b, a];
      if (
        perto.x0 <= longe.x0 &&
        perto.x1 >= longe.x1 &&
        perto.y0 <= longe.y0 &&
        perto.y1 >= longe.y1
      ) {
        ocluidas.add(longe.id);
      }
    }
  }

  const passo = 4;
  let ocupados = 0;
  let total = 0;
  for (let y = 0; y < viewport.height; y += passo) {
    for (let x = 0; x < viewport.width; x += passo) {
      total += 1;
      for (const c of caixas) {
        if (x >= c.x0 && x <= c.x1 && y >= c.y0 && y <= c.y1) {
          ocupados += 1;
          break;
        }
      }
    }
  }
  const areaDeCaixas = caixas.reduce((s, c) => s + (c.x1 - c.x0) * (c.y1 - c.y0), 0);

  return {
    entidades: caixas.length,
    paresQueSeIntersectam: pares,
    areaDeInterseccao_px2: Math.round(areaInterseccao),
    areaDeCaixas_px2: Math.round(areaDeCaixas),
    intersectionOverBoxArea: Number((areaInterseccao / Math.max(areaDeCaixas, 1)).toFixed(4)),
    intersectionOverViewportOccupancy: Number(
      (areaInterseccao / Math.max(ocupados * passo * passo, 1)).toFixed(4),
    ),
    totalmenteOcluidas: ocluidas.size,
    recortadasPelaBorda: caixas.filter(
      (c) => c.x0 < 0 || c.y0 < 0 || c.x1 > viewport.width || c.y1 > viewport.height,
    ).length,
    ocupacaoDoViewport: Number((ocupados / total).toFixed(4)),
  };
}

/** Órbita padronizada: mesmos ângulos para qualquer cenário. */
const ORBITA_PADRAO = [0, 0.12, 0.24, 0.36, 0.48];

/**
 * Paralaxe: quanto as posições de tela se reorganizam **entre si** ao orbitar.
 *
 * Medir o deslocamento absoluto premiaria simplesmente afastar a câmera. O que
 * interessa é o movimento relativo — se tudo desliza junto, não há profundidade
 * percebida por mais que os pixels andem. Por isso o deslocamento de cada painel é
 * medido contra a mediana do quadro.
 */
export function parallax(
  projection: Projection,
  positions: LayoutMap,
  ids: ReadonlySet<string>,
  pose: CameraPose,
  viewport: Viewport = VIEWPORT_PADRAO,
): { medianaRelativa_px: number; dispersao_px: number } {
  const raio = Math.hypot(
    pose.position.x - pose.target.x,
    pose.position.y - pose.target.y,
  );
  const alturaCam = pose.position.z - pose.target.z;
  const anguloBase = Math.atan2(pose.position.y - pose.target.y, pose.position.x - pose.target.x);

  const quadros = ORBITA_PADRAO.map((delta) =>
    projetarCaixas(
      projection,
      positions,
      ids,
      {
        ...pose,
        position: {
          x: pose.target.x + Math.cos(anguloBase + delta) * raio,
          y: pose.target.y + Math.sin(anguloBase + delta) * raio,
          z: pose.target.z + alturaCam,
        },
      },
      viewport,
    ),
  );

  const desvios: number[] = [];
  for (let q = 1; q < quadros.length; q += 1) {
    const antes = new Map(quadros[q - 1]!.map((c) => [c.id, c]));
    const passo: number[] = [];
    for (const c of quadros[q]!) {
      const a = antes.get(c.id);
      if (!a) continue;
      passo.push(Math.hypot((c.x0 + c.x1) / 2 - (a.x0 + a.x1) / 2, (c.y0 + c.y1) / 2 - (a.y0 + a.y1) / 2));
    }
    if (passo.length === 0) continue;
    passo.sort((x, y) => x - y);
    const mediana = passo[Math.floor(passo.length / 2)]!;
    for (const d of passo) desvios.push(Math.abs(d - mediana));
  }
  desvios.sort((a, b) => a - b);
  return {
    medianaRelativa_px: Number((desvios[Math.floor(desvios.length / 2)] ?? 0).toFixed(2)),
    dispersao_px: Number(((desvios.at(-1) ?? 0) - (desvios[0] ?? 0)).toFixed(2)),
  };
}

/** Separação angular mínima entre centroides de território, vista da câmera. */
export function separacaoAngular(
  projection: Projection,
  positions: LayoutMap,
  pose: CameraPose,
): { minima_graus: number; mediana_graus: number } {
  const porAncora = new Map<string, Vec3[]>();
  for (const node of projection.nodes) {
    if (node.layer !== 'epistemic') continue;
    const p = positions.get(node.id);
    if (!p) continue;
    const chave = node.kind === 'moc' ? node.id : (node.anchorMocId ?? `d:${node.domainId}`);
    const lista = porAncora.get(chave) ?? [];
    lista.push(p);
    porAncora.set(chave, lista);
  }
  const centroides = [...porAncora.values()].map((ps) => ({
    x: ps.reduce((s, p) => s + p.x, 0) / ps.length,
    y: ps.reduce((s, p) => s + p.y, 0) / ps.length,
    z: ps.reduce((s, p) => s + p.z, 0) / ps.length,
  }));
  const direcoes = centroides.map((c) => normaliza(subtrai(c, pose.position)));
  const angulos: number[] = [];
  for (let i = 0; i < direcoes.length; i += 1) {
    for (let j = i + 1; j < direcoes.length; j += 1) {
      const cos = Math.min(Math.max(produto(direcoes[i]!, direcoes[j]!), -1), 1);
      angulos.push((Math.acos(cos) * 180) / Math.PI);
    }
  }
  angulos.sort((a, b) => a - b);
  return {
    minima_graus: Number((angulos[0] ?? 0).toFixed(2)),
    mediana_graus: Number((angulos[Math.floor(angulos.length / 2)] ?? 0).toFixed(2)),
  };
}

/** Variância por eixo e componentes principais, para não julgar volume só por λ3/λ1. */
export function dispersaoEspacial(
  positions: LayoutMap,
  ids: ReadonlySet<string>,
): {
  varianciaX: number;
  varianciaY: number;
  varianciaZ: number;
  autovalores: number[];
  razaoL3L1: number;
  razaoSigma3Sigma1: number;
} {
  const pts = [...positions].filter(([id]) => ids.has(id)).map(([, p]) => p);
  const n = Math.max(pts.length, 1);
  const m = {
    x: pts.reduce((s, p) => s + p.x, 0) / n,
    y: pts.reduce((s, p) => s + p.y, 0) / n,
    z: pts.reduce((s, p) => s + p.z, 0) / n,
  };
  let cxx = 0, cyy = 0, czz = 0, cxy = 0, cxz = 0, cyz = 0;
  for (const p of pts) {
    const dx = p.x - m.x, dy = p.y - m.y, dz = p.z - m.z;
    cxx += dx * dx; cyy += dy * dy; czz += dz * dz;
    cxy += dx * dy; cxz += dx * dz; cyz += dy * dz;
  }
  cxx /= n; cyy /= n; czz /= n; cxy /= n; cxz /= n; cyz /= n;

  let A = [[cxx, cxy, cxz], [cxy, cyy, cyz], [cxz, cyz, czz]];
  for (let varredura = 0; varredura < 100; varredura += 1) {
    let p = 0, q = 1, maior = Math.abs(A[0]![1]!);
    if (Math.abs(A[0]![2]!) > maior) { maior = Math.abs(A[0]![2]!); p = 0; q = 2; }
    if (Math.abs(A[1]![2]!) > maior) { maior = Math.abs(A[1]![2]!); p = 1; q = 2; }
    if (maior < 1e-10) break;
    const theta = (A[q]![q]! - A[p]![p]!) / (2 * A[p]![q]!);
    const t = Math.sign(theta || 1) / (Math.abs(theta) + Math.sqrt(theta * theta + 1));
    const c = 1 / Math.sqrt(t * t + 1), s = t * c;
    const B = A.map((r) => [...r]);
    for (let k = 0; k < 3; k += 1) {
      B[p]![k] = c * A[p]![k]! - s * A[q]![k]!;
      B[q]![k] = s * A[p]![k]! + c * A[q]![k]!;
    }
    const C = B.map((r) => [...r]);
    for (let k = 0; k < 3; k += 1) {
      C[k]![p] = c * B[k]![p]! - s * B[k]![q]!;
      C[k]![q] = s * B[k]![p]! + c * B[k]![q]!;
    }
    A = C;
  }
  const auto = [A[0]![0]!, A[1]![1]!, A[2]![2]!].sort((a, b) => b - a);
  return {
    varianciaX: Number(cxx.toFixed(2)),
    varianciaY: Number(cyy.toFixed(2)),
    varianciaZ: Number(czz.toFixed(2)),
    autovalores: auto.map((v) => Number(v.toFixed(2))),
    razaoL3L1: Number((auto[2]! / auto[0]!).toFixed(5)),
    razaoSigma3Sigma1: Number(Math.sqrt(auto[2]! / auto[0]!).toFixed(4)),
  };
}

export function idsEpistemicos(projection: Projection): ReadonlySet<string> {
  return new Set(
    projection.nodes.filter((n: ProjectionNode) => n.layer === 'epistemic').map((n) => n.id),
  );
}


// --- métricas de relação -----------------------------------------------------

export interface MetricasDeRelacao {
  /** Relações dirigidas no registro semântico. Invariante: nunca diminui. */
  relacoesSemanticas: number;
  /** Pares canônicos: a unidade que a cena desenha. */
  paresCanonicos: number;
  /** Segmentos efetivamente emitidos. */
  segmentos: number;
  /** Cruzamentos entre segmentos, em espaço de tela. */
  cruzamentosProjetados: number;
  /** Fração do viewport coberta por linha. */
  ocupacaoPorLinhas: number;
  /** Fração do viewport com duas ou mais linhas sobrepostas. */
  ocupacaoComSobreposicao: number;
  /** Maior densidade de linhas numa célula da grade de tela. */
  densidadeMaximaPorCelula: number;
  /** Segmentos exatamente coincidentes: o defeito que 3.5-C existe para eliminar. */
  segmentosCoincidentes: number;
}

interface Segmento {
  x0: number; y0: number; x1: number; y1: number;
}

/** Projeta um ponto de mundo para a tela. Devolve `null` atrás da câmera. */
function projetarPonto(
  p: Vec3,
  pose: CameraPose,
  viewport: Viewport,
): { x: number; y: number } | null {
  const paraTras = normaliza(subtrai(pose.position, pose.target));
  const direita = normaliza(cruza({ x: 0, y: 0, z: 1 }, paraTras));
  const acima = normaliza(cruza(paraTras, direita));
  const tanV = Math.tan((pose.fov * Math.PI) / 360);
  const tanH = tanV * (viewport.width / viewport.height);
  const rel = subtrai(p, pose.position);
  const d = -produto(rel, paraTras);
  if (d <= 0.1) return null;
  return {
    x: (produto(rel, direita) / (d * tanH)) * (viewport.width / 2) + viewport.width / 2,
    y: viewport.height / 2 - (produto(rel, acima) / (d * tanV)) * (viewport.height / 2),
  };
}

function cruzam(a: Segmento, b: Segmento): boolean {
  const o = (px: number, py: number, qx: number, qy: number, rx: number, ry: number): number => {
    const v = (qy - py) * (rx - qx) - (qx - px) * (ry - qy);
    return Math.abs(v) < 1e-9 ? 0 : v > 0 ? 1 : 2;
  };
  const o1 = o(a.x0, a.y0, a.x1, a.y1, b.x0, b.y0);
  const o2 = o(a.x0, a.y0, a.x1, a.y1, b.x1, b.y1);
  const o3 = o(b.x0, b.y0, b.x1, b.y1, a.x0, a.y0);
  const o4 = o(b.x0, b.y0, b.x1, b.y1, a.x1, a.y1);
  return o1 !== o2 && o3 !== o4;
}

/**
 * Mede o desenho das relações em espaço de tela.
 *
 * Os segmentos chegam em coordenadas de mundo, como a cena os emite; a projeção
 * acontece aqui, com a mesma pose usada para os painéis, de modo que os dois conjuntos
 * de métricas descrevam o mesmo quadro.
 */
export function metricasDeRelacao(
  segmentosDeMundo: [Vec3, Vec3][],
  relacoesSemanticas: number,
  paresCanonicos: number,
  pose: CameraPose,
  viewport: Viewport = VIEWPORT_PADRAO,
): MetricasDeRelacao {
  const segs: Segmento[] = [];
  for (const [a, b] of segmentosDeMundo) {
    const pa = projetarPonto(a, pose, viewport);
    const pb = projetarPonto(b, pose, viewport);
    if (!pa || !pb) continue;
    segs.push({ x0: pa.x, y0: pa.y, x1: pb.x, y1: pb.y });
  }

  let cruzamentos = 0;
  for (let i = 0; i < segs.length; i += 1) {
    for (let j = i + 1; j < segs.length; j += 1) if (cruzam(segs[i]!, segs[j]!)) cruzamentos += 1;
  }

  // Coincidência exata em mundo: é o defeito, e ele some antes de virar pixel.
  const vistos = new Map<string, number>();
  let coincidentes = 0;
  for (const [a, b] of segmentosDeMundo) {
    const chave = [a.x, a.y, a.z, b.x, b.y, b.z]
      .map((v) => v.toFixed(4))
      .join(',');
    const inverso = [b.x, b.y, b.z, a.x, a.y, a.z].map((v) => v.toFixed(4)).join(',');
    const anterior = (vistos.get(chave) ?? 0) + (vistos.get(inverso) ?? 0);
    if (anterior > 0) coincidentes += 1;
    vistos.set(chave, (vistos.get(chave) ?? 0) + 1);
  }

  // Grade de tela: cobertura, sobreposição e pico de densidade numa passada.
  const celula = 8;
  const colunas = Math.ceil(viewport.width / celula);
  const linhas = Math.ceil(viewport.height / celula);
  const contagem = new Int32Array(colunas * linhas);
  for (const s of segs) {
    const passos = Math.max(
      2,
      Math.ceil(Math.hypot(s.x1 - s.x0, s.y1 - s.y0) / (celula / 2)),
    );
    const tocadas = new Set<number>();
    for (let k = 0; k <= passos; k += 1) {
      const x = s.x0 + ((s.x1 - s.x0) * k) / passos;
      const y = s.y0 + ((s.y1 - s.y0) * k) / passos;
      if (x < 0 || y < 0 || x >= viewport.width || y >= viewport.height) continue;
      tocadas.add(Math.floor(y / celula) * colunas + Math.floor(x / celula));
    }
    for (const c of tocadas) contagem[c] = (contagem[c] ?? 0) + 1;
  }
  let comLinha = 0;
  let comVarias = 0;
  let pico = 0;
  for (const c of contagem) {
    if (c > 0) comLinha += 1;
    if (c > 1) comVarias += 1;
    if (c > pico) pico = c;
  }
  const totalCelulas = colunas * linhas;

  return {
    relacoesSemanticas,
    paresCanonicos,
    segmentos: segs.length,
    cruzamentosProjetados: cruzamentos,
    ocupacaoPorLinhas: Number((comLinha / totalCelulas).toFixed(4)),
    ocupacaoComSobreposicao: Number((comVarias / totalCelulas).toFixed(4)),
    densidadeMaximaPorCelula: pico,
    segmentosCoincidentes: coincidentes,
  };
}
