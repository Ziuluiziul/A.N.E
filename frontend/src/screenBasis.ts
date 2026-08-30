// A base do plano da tela, orientada pela visada canônica.
//
// Isto vivia dentro de `operationalLayout`, privado, quando só o observatório precisava
// dele. Passou a ser compartilhado quando a nuvem de modelos ganhou frame próprio: dois
// frames que se orientam pela mesma visada precisam da **mesma** base, senão um deles
// se abre num plano ligeiramente torto e ninguém descobre por que dois grupos vizinhos
// não alinham.
//
// O eixo de progressão já foi `z` do mundo, e isso estava errado por um motivo que só
// aparece ao clicar: `z` é a componente dominante da direção de visada, então os painéis
// empilhavam **em profundidade** em vez de se abrirem na tela, e o raio de seleção —
// que devolve a primeira intersecção — entregava o painel de trás a quem clicou no da
// frente. No plano da tela isso não acontece.

import { DIRECAO_CANONICA, type Vec3 } from './layout';

export const BASE_LOCAL = (() => {
  const cruzar = (a: Vec3, b: Vec3): Vec3 => ({
    x: a.y * b.z - a.z * b.y,
    y: a.z * b.x - a.x * b.z,
    z: a.x * b.y - a.y * b.x,
  });
  const normalizar = (v: Vec3): Vec3 => {
    const n = Math.hypot(v.x, v.y, v.z) || 1;
    return { x: v.x / n, y: v.y / n, z: v.z / n };
  };
  const direita = normalizar(cruzar({ x: 0, y: 0, z: 1 }, DIRECAO_CANONICA));
  const acima = normalizar(cruzar(DIRECAO_CANONICA, direita));
  return { direita, acima, profundidade: DIRECAO_CANONICA };
})();

/** Leva coordenadas locais (lateral, progressão, profundidade) para o mundo. */
export function paraMundoNaBase(
  origem: Vec3,
  lateral: number,
  progresso: number,
  profundidade: number,
): Vec3 {
  return {
    x:
      origem.x +
      BASE_LOCAL.direita.x * lateral +
      BASE_LOCAL.acima.x * progresso +
      BASE_LOCAL.profundidade.x * profundidade,
    y:
      origem.y +
      BASE_LOCAL.direita.y * lateral +
      BASE_LOCAL.acima.y * progresso +
      BASE_LOCAL.profundidade.y * profundidade,
    z:
      origem.z +
      BASE_LOCAL.direita.z * lateral +
      BASE_LOCAL.acima.z * progresso +
      BASE_LOCAL.profundidade.z * profundidade,
  };
}

/** Tira a componente de profundidade de uma direção e normaliza o que sobra. */
export function noPlanoDaTela(preferida: Vec3 | undefined): Vec3 {
  if (!preferida) return BASE_LOCAL.direita;
  const profundidade =
    preferida.x * BASE_LOCAL.profundidade.x +
    preferida.y * BASE_LOCAL.profundidade.y +
    preferida.z * BASE_LOCAL.profundidade.z;
  const plano = {
    x: preferida.x - BASE_LOCAL.profundidade.x * profundidade,
    y: preferida.y - BASE_LOCAL.profundidade.y * profundidade,
    z: preferida.z - BASE_LOCAL.profundidade.z * profundidade,
  };
  const comprimento = Math.hypot(plano.x, plano.y, plano.z);
  // Direção quase toda em profundidade: o que sobra no plano é ruído, não intenção.
  if (comprimento < 1e-6) return BASE_LOCAL.direita;
  return { x: plano.x / comprimento, y: plano.y / comprimento, z: plano.z / comprimento };
}
