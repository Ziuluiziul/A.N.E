// Arestas tipadas por padrão, marcador e direção — não por cor.
//
// Uma cor por relação competiria com a cor de domínio e destruiria os dois canais.
// Aqui a matiz das linhas é neutra e a distinção vem da forma: traço contínuo,
// tracejado, traço-ponto, pontilhado e linha dupla.
//
// As setas nas pontas saíram em 3.5-E: com todas as relações desenhadas por padrão,
// cada ponta virava um objeto instanciado a mais, e a direção — que é o que elas
// diziam — já é recuperável pela seleção, que abre a proveniência do par.
//
// O padrão é construído na própria geometria, subdividindo cada aresta em pedaços,
// em vez de depender de `LineDashedMaterial` — que só sabe um par traço/intervalo e
// não faria traço-ponto. Como o layout é estático entre mudanças, o custo é pago uma
// vez e o resultado é uma chamada de desenho por família.

import * as THREE from 'three';

import type { ProjectionEdge, RelationFamily } from './contract';
import { dashPath, edgePath, type EdgeObstacle } from './edgePath';
import type { LayoutMap, Vec3 } from './layout';
import { NEUTRALS, oklchToHex } from './palette';
import {
  buildRelationRegistry,
  type CanonicalPair,
  type SemanticRelation,
} from './relationRegistry';

/** Afastamento de cada faixa quando os dois sentidos declaram famílias diferentes. */
const SEPARACAO_DE_FAIXA = 0.55;

/** A família dominante de um conjunto de relações do mesmo sentido. */
function dominante(relacoes: SemanticRelation[]): RelationFamily | null {
  const contagem = new Map<RelationFamily, number>();
  for (const r of relacoes) {
    for (const f of r.relations) contagem.set(f, (contagem.get(f) ?? 0) + 1);
  }
  return (
    [...contagem.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0]?.[0] ?? null
  );
}


export interface EdgeStyle {
  /** Sequência traço/intervalo em unidades de mundo. Vazio = linha contínua. */
  pattern: number[];
  /** Duas linhas paralelas, para `contrasts`. */
  doubled: boolean;
  opacity: number;
  label: string;
}

/**
 * As opacidades caíram cerca de 40%, todas na mesma proporção.
 *
 * A calibração anterior foi feita quando a placa era menor e a linha ia de centro a
 * centro: uma aresta precisava de peso para se separar do fundo entre dois pontos
 * pequenos. Com a placa em 5,0 e a linha aparada na borda, o que sobrou foi o oposto — a
 * malha de fios passou a ser a coisa mais presente da cena, e o painel, que é o objeto de
 * leitura, ficou atrás dela.
 *
 * A proporção é uniforme de propósito: a ordem entre as famílias é a calibração de 3.4
 * — pré-requisito pesa mais que navegação porque dependência se lê antes de rota — e ela
 * não estava errada. O que estava errado era o nível de todas.
 *
 * Espessura não é um canal disponível aqui: `linewidth` de `LineBasicMaterial` é ignorado
 * por praticamente todo driver, e a linha é sempre de um pixel. "Mais fina" só existe
 * como "mais transparente" — quem tem espessura de verdade é a fita do foco, que é
 * `LineSegments2` e cobra o próprio ajuste.
 */
export const EDGE_STYLES: Record<RelationFamily, EdgeStyle> = {
  navigation: {
    pattern: [0.9, 1.1],
    doubled: false,
    opacity: 0.2,
    label: 'navegação',
  },
  prerequisite: {
    pattern: [],
    doubled: false,
    opacity: 0.44,
    label: 'pré-requisito',
  },
  extends: {
    // Traço longo com respiro curto. `prerequisite`, `extends` e `evidence` eram as
    // três contínuas, distinguidas só pela seta da ponta; sem a seta elas ficariam
    // idênticas, e a distinção por forma — que é o que substitui a cor — deixaria de
    // existir para quase metade das relações. Cada uma ganhou padrão próprio.
    pattern: [2.6, 0.6],
    doubled: false,
    opacity: 0.37,
    label: 'extensão',
  },
  contrasts: {
    pattern: [],
    doubled: true,
    opacity: 0.37,
    label: 'contraste',
  },
  evidence: {
    // Traço curto e cerrado: lê como uma linha "cheia" de perto e como pontilhado denso
    // à distância, o que combina com evidência ser acúmulo de apoios.
    pattern: [0.55, 0.4],
    doubled: false,
    opacity: 0.4,
    label: 'evidência',
  },
  operational: {
    pattern: [1.6, 0.7, 0.25, 0.7],
    doubled: false,
    opacity: 0.3,
    label: 'operacional',
  },
  historical: {
    pattern: [0.3, 0.9],
    doubled: false,
    opacity: 0.3,
    label: 'histórico',
  },
};

const EDGE_COLOR = oklchToHex(NEUTRALS.edgeInactive);

/** O mesmo caminho, deslocado em bloco. Uma faixa é a outra andada de lado. */
function deslocar(pontos: Vec3[], offset: Vec3, sinal: number): Vec3[] {
  return pontos.map((ponto) => ({
    x: ponto.x + offset.x * sinal,
    y: ponto.y + offset.y * sinal,
    z: ponto.z + offset.z * sinal,
  }));
}

/** Deslocamento perpendicular no plano, para desenhar a linha dupla de `contrasts`. */
function perpendicular(a: Vec3, b: Vec3, amount: number): Vec3 {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const norma = Math.hypot(dx, dy) || 1;
  return { x: (-dy / norma) * amount, y: (dx / norma) * amount, z: 0 };
}

export interface EdgeBuild {
  family: RelationFamily;
  lines: THREE.LineSegments;
  markers: THREE.InstancedMesh | null;
}

/**
 * Um grupo por família de relação, **uma primitiva por par não ordenado**.
 *
 * Antes esta função desenhava uma linha por aresta dirigida. Como A→B e B→A têm os
 * mesmos dois extremos, as duas linhas caíam sobre o mesmo caminho: 129 pares
 * sobredesenhados, e em 49 deles as assinaturas de famílias diferentes se somavam no
 * mesmo pixel. Agora o desenho parte do registro canônico — um par, uma primitiva — e
 * a direção vira marcador em vez de segunda linha.
 *
 * O que se perde em quantidade de linhas não se perde em informação: o par guarda os
 * dois sentidos, e `provenanceOf` devolve as relações dirigidas que a linha representa.
 */
export function buildRelationLines(
  edges: ProjectionEdge[],
  posicoes: LayoutMap,
  /**
   * O raio varrido de cada placa, para a linha parar na borda dela e contornar a que
   * estiver no caminho. Sem o mapa, a linha vai de centro a centro como antes — é o que
   * mantém honesto o teste que só quer saber quantas primitivas saem daqui.
   */
  placas: ReadonlyMap<string, number> = new Map(),
): EdgeBuild[] {
  const obstaculos: EdgeObstacle[] = [];
  for (const [id, radius] of placas) {
    const position = posicoes.get(id);
    if (position) obstaculos.push({ id, position, radius });
  }
  const registro = buildRelationRegistry(
    edges.filter((edge) => edge.kind !== 'aggregated' && edge.primaryRelation),
  );
  const porFamilia = new Map<RelationFamily, CanonicalPair[]>();
  for (const par of registro.pairs) {
    if (par.selfLink || !par.dominantFamily) continue;
    const lista = porFamilia.get(par.dominantFamily) ?? [];
    lista.push(par);
    porFamilia.set(par.dominantFamily, lista);
  }

  const resultado: EdgeBuild[] = [];
  for (const [family, lista] of [...porFamilia].sort((a, b) => a[0].localeCompare(b[0]))) {
    const style = EDGE_STYLES[family];
    const vertices: number[] = [];

    for (const par of lista) {
      const origem = posicoes.get(par.a);
      const destino = posicoes.get(par.b);
      if (!origem || !destino) continue;

      // O caminho é decidido **uma vez** para o par, e as faixas o acompanham. Aparar e
      // desviar cada faixa por conta própria abriria as duas em direções diferentes, e o
      // que se lê como um par viraria dois caminhos que por acaso partem do mesmo lugar.
      const caminho = edgePath(
        origem,
        destino,
        placas.get(par.a) ?? 0,
        placas.get(par.b) ?? 0,
        obstaculos,
        new Set([par.a, par.b]),
      );
      if (!caminho) continue;

      // Famílias diferentes por sentido não podem virar duas linhas coincidentes. Elas
      // viram **duas faixas**, deslocadas perpendicularmente, cada uma com a assinatura
      // do próprio sentido — o par continua legível como um par, e cada sentido conta a
      // própria história.
      const faixas: { pontos: Vec3[]; pattern: number[] }[] = [];
      if (par.familiesDifferByDirection) {
        const offset = perpendicular(origem, destino, SEPARACAO_DE_FAIXA);
        const familiaIda = dominante(par.forward);
        const familiaVolta = dominante(par.backward);
        faixas.push(
          {
            pontos: deslocar(caminho, offset, 1),
            pattern: familiaIda ? EDGE_STYLES[familiaIda].pattern : style.pattern,
          },
          {
            pontos: deslocar(caminho, offset, -1),
            pattern: familiaVolta ? EDGE_STYLES[familiaVolta].pattern : style.pattern,
          },
        );
      } else if (style.doubled) {
        const offset = perpendicular(origem, destino, 0.34);
        for (const sinal of [1, -1]) {
          faixas.push({ pontos: deslocar(caminho, offset, sinal), pattern: style.pattern });
        }
      } else {
        faixas.push({ pontos: caminho, pattern: style.pattern });
      }
      for (const faixa of faixas) vertices.push(...dashPath(faixa.pontos, faixa.pattern));
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    const material = new THREE.LineBasicMaterial({
      color: EDGE_COLOR,
      transparent: true,
      opacity: style.opacity,
      depthWrite: false,
    });
    const lines = new THREE.LineSegments(geometry, material);
    lines.name = `edges:${family}`;
    lines.renderOrder = 1;

    resultado.push({ family, lines, markers: null });
  }
  return resultado;
}

/**
 * Opacidade da espinha na visão de território.
 *
 * A função que construía a espinha saiu daqui em 3.5-C: ela desenhava de uma vez as 223
 * arestas que tocam alguma âncora, e a visão global herdava esse emaranhado. A espinha
 * agora é reescrita por território, em `atlas.ts`, a partir do registro canônico e sob
 * orçamento; o que ficou aqui é a calibração de opacidade, que continua sendo decisão
 * de desenho de aresta.
 */
export const SPINE_OPACITY = 0.13;
