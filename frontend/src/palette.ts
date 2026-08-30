// Paleta OKLCH do dossiê, convertida em tempo de execução.
//
// Os tokens são escritos em OKLCH e não em hex porque é assim que a distância
// perceptual entre eles foi escolhida: doze matizes de luminosidade próxima e croma
// moderado. Guardar só o hex perderia a razão dos números e tornaria impossível
// verificar, num teste, que dois domínios não ficaram perceptivelmente juntos.
//
// A conversão é OKLCH → OKLab → LMS → sRGB linear → sRGB. Nenhuma biblioteca: são
// vinte linhas de álgebra e uma dependência a menos.

export interface Oklch {
  l: number; // 0..1
  c: number;
  h: number; // graus
}

// Doze matizes igualmente espaçadas a 30°, dentro da envoltória de luminosidade e
// croma que o dossiê especifica (L 0.72–0.79, C 0.10–0.14).
//
// **Desvio deliberado da tabela do dossiê, com motivo.** A tabela original põe D12 em
// h=105 e D03 em h=90 — quinze graus de distância, o que dá 0.036 em OKLab e reprova
// o gate de discriminabilidade que o próprio dossiê exige ("recalculada com métodos
// de maximização de distância como Colorgorical ou Glasbey"). Doze pontos igualmente
// espaçados num círculo de croma 0.12 ficam a 0.062 uns dos outros, com folga sobre
// o limiar. Os demais tokens mudam pouco; D12 é o que sai do lugar.
export const DOMAIN_TOKENS: Record<string, Oklch> = {
  D01: { l: 0.73, c: 0.13, h: 25 },
  D02: { l: 0.75, c: 0.12, h: 55 },
  D03: { l: 0.78, c: 0.12, h: 85 },
  D04: { l: 0.73, c: 0.12, h: 115 },
  D05: { l: 0.74, c: 0.12, h: 145 },
  D06: { l: 0.76, c: 0.11, h: 175 },
  D07: { l: 0.72, c: 0.13, h: 205 },
  D08: { l: 0.72, c: 0.14, h: 235 },
  D09: { l: 0.74, c: 0.13, h: 265 },
  D10: { l: 0.73, c: 0.13, h: 295 },
  D11: { l: 0.76, c: 0.11, h: 325 },
  D12: { l: 0.79, c: 0.12, h: 355 },
};

/**
 * A cor de cada provedor: o **matiz da marca**, na luminosidade da cena.
 *
 * O hex oficial não entra direto. Ele foi medido em OKLCH e só o matiz sobrevive; a
 * luminosidade e o croma voltam para a envoltória do dossiê (L 0.72–0.79, C 0.10–0.14),
 * que é o que mantém a placa legível sobre o fundo e coerente com o corpus ao lado.
 * Groq #F55036 → h 32; Google #4285F4 → h 260; NVIDIA #76B900 → h 131.
 *
 * **Duas marcas são de baixo croma por escolha delas, e continuam assim.** O slate da
 * OpenRouter (#94A3B8) mede C 0.035, e a Ollama é monocromática — não declara matiz
 * nenhum. Levá-las ao croma da cena inventaria uma cor que elas não usam, e ainda por
 * cima jogaria a OpenRouter (h 257) em cima do azul do Google (h 260), deixando dois
 * provedores indistinguíveis. Aqui elas se separam pelo croma, que é o que a marca de
 * fato afirma.
 *
 * Estes tokens ficam **fora** de `DOMAIN_TOKENS`: aquela tabela é doze matizes cuja
 * distância mútua é gate do dossiê, e um provedor entrando nela reprovaria a conta sem
 * que houvesse defeito nenhum. A camada viva e o corpus não disputam a mesma escala.
 */
export const PROVIDER_TOKENS: Record<string, Oklch> = {
  'P:groq': { l: 0.74, c: 0.13, h: 32 },
  'P:google': { l: 0.73, c: 0.13, h: 260 },
  'P:nvidia': { l: 0.75, c: 0.13, h: 131 },
  'P:openrouter': { l: 0.74, c: 0.05, h: 257 },
  'P:ollama': { l: 0.76, c: 0.012, h: 257 },
  // A Nous é monocromática de marca — não declara matiz. O croma 0.09 é atribuído
  // pela casa (não pela marca) para separá-la da OpenRouter (0.05) e da Ollama
  // (0.012), que disputam o mesmo território neutro; o matiz 295 é o violeta mais
  // distante dos provedores já ocupados e fica abaixo do limiar de marca.
  'P:nous': { l: 0.76, c: 0.09, h: 295 },
};

/** O token de um provedor, quando ele tem cor declarada. Nunca inventa uma. */
export function providerToken(provider: string | undefined): string | null {
  if (!provider) return null;
  const token = `P:${provider.toLowerCase()}`;
  return token in PROVIDER_TOKENS ? token : null;
}

export const NEUTRALS = {
  backgroundDeep: { l: 0.17, c: 0.015, h: 255 },
  backgroundSecondary: { l: 0.22, c: 0.018, h: 255 },
  surfaceEmbedded: { l: 0.27, c: 0.018, h: 255 },
  edgeInactive: { l: 0.58, c: 0.025, h: 250 },
  textPrimary: { l: 0.96, c: 0.01, h: 255 },
  textSecondary: { l: 0.82, c: 0.02, h: 255 },
  focus: { l: 0.88, c: 0.08, h: 220 },
} as const satisfies Record<string, Oklch>;

function srgbTransfer(value: number): number {
  const clamped = Math.min(Math.max(value, 0), 1);
  return clamped <= 0.0031308
    ? 12.92 * clamped
    : 1.055 * Math.pow(clamped, 1 / 2.4) - 0.055;
}

/** OKLCH → inteiro 0xRRGGBB. Fora do gamut, satura por canal em vez de girar a matiz. */
export function oklchToHex(color: Oklch): number {
  const hueRad = (color.h * Math.PI) / 180;
  const a = color.c * Math.cos(hueRad);
  const b = color.c * Math.sin(hueRad);

  const lCube = color.l + 0.3963377774 * a + 0.2158037573 * b;
  const mCube = color.l - 0.1055613458 * a - 0.0638541728 * b;
  const sCube = color.l - 0.0894841775 * a - 1.291485548 * b;

  const l = lCube ** 3;
  const m = mCube ** 3;
  const s = sCube ** 3;

  const r = srgbTransfer(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s);
  const g = srgbTransfer(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s);
  const bl = srgbTransfer(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s);

  const to255 = (v: number) => Math.round(Math.min(Math.max(v, 0), 1) * 255);
  return (to255(r) << 16) | (to255(g) << 8) | to255(bl);
}

export function hexString(color: Oklch): string {
  return `#${oklchToHex(color).toString(16).padStart(6, '0')}`;
}

/** Distância perceptual em OKLab. É a métrica que o teste da paleta usa. */
export function perceptualDistance(a: Oklch, b: Oklch): number {
  const rad = (deg: number) => (deg * Math.PI) / 180;
  const ax = a.c * Math.cos(rad(a.h));
  const ay = a.c * Math.sin(rad(a.h));
  const bx = b.c * Math.cos(rad(b.h));
  const by = b.c * Math.sin(rad(b.h));
  return Math.hypot(a.l - b.l, ax - bx, ay - by);
}

const FALLBACK: Oklch = { l: 0.7, c: 0.02, h: 255 };

export function tokenColor(token: string): Oklch {
  return PROVIDER_TOKENS[token] ?? DOMAIN_TOKENS[token] ?? FALLBACK;
}

/**
 * A cor de um **link**: mais clara e mais saturada que a do corpo.
 *
 * `emissiveOf` serve à superfície da placa, e por isso baixa o croma — numa área grande,
 * cor saturada vira ruído. Num fio de poucos pixels acontece o contrário: o pouco croma
 * que sobra se perde contra o fundo, e o degradê chega esbranquiçado, sem dizer quais
 * dois domínios ele liga. Aqui o croma **sobe**, e é ele que faz a linha ler como luz
 * colorida em vez de risco branco.
 */
export function linkColorOf(color: Oklch): Oklch {
  return { l: Math.min(color.l + 0.1, 0.92), c: Math.min(color.c * 1.3, 0.37), h: color.h };
}

/**
 * Luminosidade a partir da qual a tinta escura lê melhor que a clara.
 *
 * `l` em OKLCH já é luminosidade **perceptual**, então o corte é direto: não há a
 * distorção que faz o amarelo de sRGB passar por escuro. O valor fica acima de meio
 * porque a placa é translúcida sobre um fundo carvão — a cor que chega ao olho é
 * sempre um pouco mais escura que o token.
 */
const LIMIAR_DE_TINTA = 0.66;

/**
 * A tinta que se lê sobre uma superfície desta cor.
 *
 * Existe porque a face do painel escreve **sobre a placa**, e a placa tem a cor do
 * domínio: a mesma tinta clara que se lê sobre o azul-ardósia do openrouter some sobre
 * o verde-claro do nvidia. Escolher por luminosidade mantém a identidade da cor e
 * devolve o contraste — em vez de tapar a placa com um retângulo escuro, que apagaria
 * justamente o que diz de quem é o painel.
 */
export function inkOn(background: Oklch): 'clara' | 'escura' {
  return background.l >= LIMIAR_DE_TINTA ? 'escura' : 'clara';
}

/** Versão emissiva: mesma matiz, mais luminosa. Nunca branco somado por cima. */
export function emissiveOf(color: Oklch): Oklch {
  return { l: Math.min(color.l + 0.14, 0.97), c: color.c * 0.85, h: color.h };
}

/**
 * Mistura duas cores **na própria OKLCH**, pelo arco curto de matiz.
 *
 * Interpolar em sRGB atravessa um meio cinzento: as duas pontas se anulam e o degradê
 * do link empalidecia justamente no trecho que deveria dizer "isto liga aqueles dois".
 * Em OKLCH a matiz gira em vez de se cancelar, então o miolo continua colorido e a
 * luminosidade percorre um caminho previsível — sem precisar de reforço somado depois,
 * que era o que estourava a cor para branco.
 */
export function mixOklch(a: Oklch, b: Oklch, t: number): Oklch {
  const passo = Math.min(Math.max(t, 0), 1);
  // O arco curto: 350° e 10° são vizinhos, e a média ingênua deles cairia em 180°.
  const giro = ((((b.h - a.h) % 360) + 540) % 360) - 180;
  return {
    l: a.l + (b.l - a.l) * passo,
    c: a.c + (b.c - a.c) * passo,
    h: a.h + giro * passo,
  };
}
