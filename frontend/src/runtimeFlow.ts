// O fluxo das arestas vivas: luz que anda no fio, na direção em que a informação vai.
//
// Até aqui a atividade acendia a **placa** e deixava o fio calado: uma linha de cor
// fixa entre dois painéis acesos diz que existe ligação, não que existe trabalho
// atravessando ela — e não diz para que lado. Numa cena com dezenas de execuções
// abertas, "quem está alimentando quem" era exatamente o que faltava.
//
// **A direção não é decorativa.** Ela sai da própria aresta da trilha, e por isso é
// decidida aqui, num módulo puro que o teste alcança sem GPU: `flowDirection` é a
// tradução de "quem trabalha, e para onde a informação vai" para "de que ponta o pulso
// parte".
//
// **A velocidade é do mundo, não do segmento.** Normalizar cada aresta em 0..1 faria o
// pulso atravessar uma ligação curta na mesma duração de uma longa — as curtas
// pareceriam rápidas e as longas, lentas, sem que velocidade nenhuma tivesse mudado.
// O atributo carrega distância em unidades de mundo, e o passo também.

import * as THREE from 'three';

import type { RuntimeActivitySegment } from './runtimeLayer';

/** De que ponta o pulso parte. `forward` é `from → to`. */
export type FlowDirection = 'forward' | 'reverse';

const PREFIXO_PROVEDOR = 'runtime:provider:';

/**
 * Para onde a luz corre num segmento vivo.
 *
 * A regra é uma só: **o pulso vai na direção em que a informação vai**, e quando as
 * duas pontas trabalham, ele segue a causalidade que a trilha registrou.
 *
 * - `modelo → evento` e `evento → evento` já nascem na direção causal: o modelo produz
 *   o evento, e o evento anterior precede o seguinte. Segue em frente.
 * - `modelo → provedor` é vínculo, não produção: quem atende é o provedor, e quem
 *   trabalha é o modelo. O pulso desce do provedor para o modelo.
 * - a haste liga o modelo vivo ao mesmo modelo no catálogo — duas representações da
 *   mesma identidade. A luz corre para a viva, que é a que está executando.
 */
export function flowDirection(segment: RuntimeActivitySegment): FlowDirection {
  if (segment.kind === 'tether') return 'reverse';
  if (segment.target.startsWith(PREFIXO_PROVEDOR)) return 'reverse';
  return 'forward';
}

export interface FlowAttributes {
  /** `x,y,z` por vértice, dois vértices por segmento. */
  position: Float32Array;
  /** Distância em unidades de mundo desde a origem do fluxo daquele segmento. */
  flow: Float32Array;
  /** A mesma distância, normalizada em 0..1. Sem movimento, é ela que diz o sentido. */
  progress: Float32Array;
}

/**
 * Os buffers de um conjunto de segmentos, já orientados.
 *
 * A direção é **assada no atributo**: o vértice de onde o pulso parte recebe zero, e o
 * outro recebe o comprimento. Assim o shader não precisa saber de aresta nenhuma, e
 * inverter um segmento não custa um `uniform` por linha — que seria uma chamada de
 * desenho por linha, exatamente o que esta cena existe para não ter.
 */
export function flowAttributes(segments: readonly RuntimeActivitySegment[]): FlowAttributes {
  const position = new Float32Array(segments.length * 6);
  const flow = new Float32Array(segments.length * 2);
  const progress = new Float32Array(segments.length * 2);
  segments.forEach((segment, indice) => {
    const p = indice * 6;
    position[p] = segment.from.x;
    position[p + 1] = segment.from.y;
    position[p + 2] = segment.from.z;
    position[p + 3] = segment.to.x;
    position[p + 4] = segment.to.y;
    position[p + 5] = segment.to.z;

    const comprimento = Math.hypot(
      segment.to.x - segment.from.x,
      segment.to.y - segment.from.y,
      segment.to.z - segment.from.z,
    );
    const adiante = flowDirection(segment) === 'forward';
    const f = indice * 2;
    flow[f] = adiante ? 0 : comprimento;
    flow[f + 1] = adiante ? comprimento : 0;
    progress[f] = adiante ? 0 : 1;
    progress[f + 1] = adiante ? 1 : 0;
  });
  return { position, flow, progress };
}

/**
 * Velocidade do pulso, em unidades de mundo por segundo.
 *
 * A cena mede ~100 unidades de anel e ~5 de placa; a esta velocidade o pulso cruza uma
 * ligação típica entre modelo e evento em pouco mais de um segundo, que lê como fluxo
 * e não como piscada.
 */
const VELOCIDADE = 26;
/** Distância entre dois pulsos consecutivos no mesmo fio. */
const PASSO = 19;

const VERTEX = `
attribute float aFlow;
attribute float aProgresso;
varying float vFlow;
varying float vProgresso;
void main() {
  vFlow = aFlow;
  vProgresso = aProgresso;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

// A cauda é uma potência, e não um degrau: um pulso com borda dura lê como serrilha
// nos fios finos, e o que se quer dizer é "isto está correndo", não "isto pisca".
const FRAGMENT = `
uniform vec3 uCor;
uniform float uTempo;
uniform float uVelocidade;
uniform float uPasso;
uniform float uBase;
uniform float uMovimento;
varying float vFlow;
varying float vProgresso;
void main() {
  float cauda;
  if (uMovimento > 0.5) {
    float p = fract((vFlow - uTempo * uVelocidade) / uPasso);
    cauda = pow(1.0 - p, 5.0);
  } else {
    // Sem movimento a direção ainda precisa ser dita, senão o fio volta a ser um fio:
    // ele clareia em direção ao destino, e a informação sobrevive à animação.
    cauda = vProgresso * vProgresso;
  }
  float alfa = clamp(uBase + cauda * (1.0 - uBase), 0.0, 1.0);
  gl_FragColor = vec4(uCor * (0.72 + 0.5 * cauda), alfa);
}
`;

export interface FlowMaterial {
  material: THREE.ShaderMaterial;
  /** Avança o relógio do fluxo e ajusta o brilho de repouso do fio. */
  advance: (seconds: number, base: number, motion: boolean) => void;
}

/** O material do fluxo. Um só, compartilhado por todos os segmentos vivos. */
export function createFlowMaterial(color = 0x9be4fc): FlowMaterial {
  const material = new THREE.ShaderMaterial({
    uniforms: {
      uCor: { value: new THREE.Color(color) },
      uTempo: { value: 0 },
      uVelocidade: { value: VELOCIDADE },
      uPasso: { value: PASSO },
      uBase: { value: 0.24 },
      uMovimento: { value: 1 },
    },
    vertexShader: VERTEX,
    fragmentShader: FRAGMENT,
    transparent: true,
    depthTest: false,
    depthWrite: false,
    toneMapped: false,
  });
  return {
    material,
    advance(seconds, base, motion) {
      material.uniforms.uTempo!.value = seconds;
      material.uniforms.uBase!.value = Math.max(0, Math.min(1, base));
      material.uniforms.uMovimento!.value = motion ? 1 : 0;
    },
  };
}
