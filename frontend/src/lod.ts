// Nível de detalhe por tamanho projetado em tela, com histerese.
//
// Distância no mundo não serve como critério: o mesmo afastamento produz glifos de
// tamanhos diferentes conforme o campo de visão e a altura da janela. O que importa
// é quantos pixels a entidade ocupa — é isso que decide se um rótulo é legível.
//
// A histerese existe porque um limiar seco faz o rótulo piscar quando a câmera
// treme sobre a fronteira. Subir exige ultrapassar o limiar; descer exige cair
// abaixo dele menos uma folga.

export type LodLevel = 'distant' | 'structural' | 'identifiable' | 'legible' | 'expanded';

export const LOD_ORDER: LodLevel[] = [
  'distant',
  'structural',
  'identifiable',
  'legible',
  'expanded',
];

/** Limiares em pixels de diâmetro projetado, conforme o dossiê. */
export const LOD_THRESHOLDS: { level: LodLevel; minPixels: number }[] = [
  { level: 'expanded', minPixels: 80 },
  { level: 'legible', minPixels: 28 },
  { level: 'identifiable', minPixels: 10 },
  { level: 'structural', minPixels: 4 },
  { level: 'distant', minPixels: 0 },
];

const HYSTERESIS = 0.78;

/**
 * Diâmetro aparente em pixels de uma esfera de `radius` a `distance` da câmera.
 *
 * `viewportHeight / (2 tan(fov/2))` é a distância focal em pixels; multiplicada pelo
 * diâmetro e dividida pela distância, dá o tamanho projetado.
 */
export function projectedPixels(
  radius: number,
  distance: number,
  fovDegrees: number,
  viewportHeight: number,
): number {
  if (distance <= 1e-6) return viewportHeight;
  const focal = viewportHeight / (2 * Math.tan((fovDegrees * Math.PI) / 360));
  return (2 * radius * focal) / distance;
}

export function levelFor(pixels: number): LodLevel {
  for (const { level, minPixels } of LOD_THRESHOLDS) {
    if (pixels >= minPixels) return level;
  }
  return 'distant';
}

/**
 * Nível novo dado o anterior. Descer de nível exige folga; subir, não.
 *
 * A assimetria é de propósito: ganhar detalhe ao aproximar deve ser imediato, e
 * perdê-lo ao afastar deve custar um pouco mais que o ruído da câmera.
 */
export function levelWithHysteresis(pixels: number, previous: LodLevel | undefined): LodLevel {
  const bruto = levelFor(pixels);
  if (previous === undefined) return bruto;
  const indiceBruto = LOD_ORDER.indexOf(bruto);
  const indiceAnterior = LOD_ORDER.indexOf(previous);
  if (indiceBruto >= indiceAnterior) return bruto;

  const limiarAnterior = LOD_THRESHOLDS.find((item) => item.level === previous)?.minPixels ?? 0;
  return pixels >= limiarAnterior * HYSTERESIS ? previous : bruto;
}

export function showsLabel(level: LodLevel): boolean {
  return level === 'identifiable' || level === 'legible' || level === 'expanded';
}

/**
 * O painel já está perto o bastante para se ler frase, não só nome.
 *
 * É o critério que decide se a câmera precisa se mexer quando um nó é selecionado.
 * Nível ainda não medido conta como "não legível": aproximar do que não se sabe onde
 * está é o comportamento seguro, e a primeira medida chega no quadro seguinte.
 */
export function readsText(level: LodLevel | undefined): boolean {
  return level === 'legible' || level === 'expanded';
}

export function showsBody(level: LodLevel): boolean {
  return level !== 'distant';
}
