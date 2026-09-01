// Distância mínima da órbita, derivada do alvo — não de uma constante.

/**
 * Piso absoluto, para um alvo minúsculo não permitir chegar a zero.
 *
 * Não é o limite de leitura: é o chão abaixo do qual a conta de um painel
 * degenerado (alcance 0, janela 0) ainda não colapsa a câmera para dentro dele.
 */
export const LIMITE_DE_APROXIMACAO_MINIMO = 12;

/**
 * Folga sobre a distância em que o alvo exatamente preenche a janela útil.
 *
 * O limite existe para o painel não ser recortado. Margem demais vira moldura
 * vazia justamente quando se quer chegar perto para ler.
 */
export const FOLGA_DE_APROXIMACAO = 1.02;

/**
 * Distância em que o alcance do alvo cabe no menor semi-eixo da janela.
 *
 * Era a constante 12. Com fov 38° a 12 unidades a janela mostra ~14,7 × 8,3, e um
 * MOC expandido mede ~28 × 16 — a roda até o fim enchia a tela de texto recortado
 * (F-01). A conta usa o fov e o viewport reais, então sobrevive a troca de lente.
 */
export function distanciaMinimaDaOrbita(args: {
  alcance: number;
  fovDeg: number;
  width: number;
  height: number;
  folga?: number;
  piso?: number;
}): number {
  const folga = args.folga ?? FOLGA_DE_APROXIMACAO;
  const piso = args.piso ?? LIMITE_DE_APROXIMACAO_MINIMO;
  if (!(args.alcance > 0) || !(args.fovDeg > 0)) return piso;
  const altura = args.height > 0 ? args.height : 720;
  const largura = args.width > 0 ? args.width : 1280;
  const tanV = Math.tan((args.fovDeg * Math.PI) / 360);
  if (!(tanV > 0)) return piso;
  const tanH = tanV * (largura / altura);
  const cabe = Math.max(args.alcance / 2 / tanV, args.alcance / 2 / tanH) * folga;
  return Math.max(piso, cabe);
}

/** O alcance cabe na janela a esta distância? Folga já está dentro de `distancia`. */
export function alvoCabeNaJanela(args: {
  alcance: number;
  distancia: number;
  fovDeg: number;
  width: number;
  height: number;
}): boolean {
  if (!(args.distancia > 0) || !(args.fovDeg > 0)) return false;
  const altura = args.height > 0 ? args.height : 720;
  const largura = args.width > 0 ? args.width : 1280;
  const tanV = Math.tan((args.fovDeg * Math.PI) / 360);
  const visivelH = 2 * args.distancia * tanV;
  const visivelW = visivelH * (largura / altura);
  return args.alcance <= visivelW && args.alcance <= visivelH;
}
