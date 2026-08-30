// Profundidade perceptiva: enquadramento, atmosfera e volume dos territórios.
//
// O layout continua sendo a fonte das posições. Este módulo não "corrige" z nem
// inventa hierarquia: ele transforma a extensão já calculada em uma câmera oblíqua
// coerente e em cascas translúcidas que tornam o volume local de cada território
// perceptível por paralaxe, oclusão e iluminação.

import * as THREE from 'three';

import type { Vec3 } from './layout';

export interface CameraPose {
  fov: number;
  near: number;
  far: number;
  distance: number;
  position: Vec3;
  target: Vec3;
  fogDensity: number;
}

/**
 * Enquadra a extensão espacial com uma lente moderadamente longa e elevação real.
 *
 * O cálculo usa os dois campos de visão: numa janela estreita é a largura que limita
 * o enquadramento, numa janela larga é a altura. A direção assimétrica evita que as
 * alturas se comprimam umas sobre as outras como aconteceria olhando de um eixo puro.
 */
export function cameraPoseForExtent(radius: number, depth: number, aspect: number): CameraPose {
  const safeRadius = Math.max(radius, 1);
  const safeDepth = Math.max(depth, 1);
  const safeAspect = Math.max(aspect, 0.25);
  // Lente mais aberta.
  //
  // 38° é uma lente longa, e ela custava distância: cabendo três nuvens na tela, o
  // enquadramento ia a 9 mil unidades e cada painel virava um ponto. A 55° a mesma
  // extensão cabe a 62% da distância, e o que se ganha é escala aparente — o painel
  // volta a ter tamanho sem que ninguém precise se aproximar. Acima disso a perspectiva
  // começa a distorcer as bordas, e uma placa no canto lê como trapézio.
  const fov = 55;
  const vertical = (fov * Math.PI) / 180;
  const horizontal = 2 * Math.atan(Math.tan(vertical / 2) * safeAspect);
  // Painéis e rótulos vivem além do último centro de entidade; a margem os enquadra
  // sem empurrar a câmera tão longe que toda forma vire um ponto.
  const halfWidth = safeRadius * 1.18;
  // A projeção oblíqua traz parte do raio horizontal para o eixo vertical da tela;
  // 0.82 evita cortar o território próximo sem recuar até perder leitura.
  const halfHeight = Math.max(safeRadius * 0.82, safeDepth * 1.55);
  const distance =
    Math.max(halfWidth / Math.tan(horizontal / 2), halfHeight / Math.tan(vertical / 2)) * 1.08;
  const direction = normalize({ x: 0.34, y: -0.69, z: 0.64 });
  // O semiplano próximo (y negativo) cresce mais em perspectiva. Um alvo levemente
  // deslocado para ele compensa esse peso e mantém a borda inferior enquadrada.
  const target = { x: 0, y: -safeRadius * 0.08, z: safeDepth * 0.04 };

  return {
    fov,
    near: 0.35,
    far: Math.max(1200, distance + safeRadius * 9),
    distance,
    position: {
      x: target.x + direction.x * distance,
      y: target.y + direction.y * distance,
      z: target.z + direction.z * distance,
    },
    target,
    // FogExp2 é escalada à malha: aumentar o corpus não transforma o horizonte em
    // parede opaca, e aproximar continua devolvendo contraste local.
    fogDensity: 1 / Math.max(safeRadius * 5.4, 240),
  };
}

function normalize(value: Vec3): Vec3 {
  const length = Math.hypot(value.x, value.y, value.z) || 1;
  return { x: value.x / length, y: value.y / length, z: value.z / length };
}

export interface DepthEnvironment {
  group: THREE.Group;
  update: () => void;
  dispose: () => void;
}

/**
 * O ambiente de profundidade, de volta ao que ele tem função para ser: nada.
 *
 * Ele já foi cascas territoriais e anéis equatoriais — três objetos por domínio, sempre
 * ligados —, que a direção de 3.5-D tirou porque gaiola persistente não fica. Depois foi
 * um campo de 1100 grãos correndo ao longo da coluna quando havia trabalho aberto. A
 * intenção era responder "o ambiente ganha movimento conforme o que está acontecendo", e
 * a resposta estava errada: movimento de fundo é estética que não foi pedida, e ela
 * ocupava o lugar da pergunta de verdade — **quais painéis e quais linhas** estão
 * trabalhando agora.
 *
 * A atividade voltou para onde ela é informação: no pulso do painel que está em ciclo
 * aberto e na linha que liga o que está trabalhando. Ver `panelBodies.setActivity` e o
 * realce de arestas em `atlas.ts`.
 *
 * A função continua existindo para não espalhar `if` pelo atlas: devolve um grupo vazio e
 * um `update` que não faz nada.
 */
export function createDepthEnvironment(): DepthEnvironment {
  const group = new THREE.Group();
  group.name = 'depth-environment';
  return {
    group,
    update() {
      // Sem geometria de ambiente não há o que avançar.
    },
    dispose() {
      // Nada a devolver: este ambiente não aloca.
    },
  };
}
