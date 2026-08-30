// O nome de cada nuvem, escrito grande o bastante para se ler de longe.
//
// A cena tem quatro populações em lugares distintos do mundo, e nada dizia qual era
// qual. Quem chegava de fora via três aglomerados e um enxame, e a única forma de
// descobrir de quem era cada um era aproximar até ler o texto de um painel — o que
// obriga a perder a visão de conjunto para conseguir a informação que orienta a visão
// de conjunto.
//
// O título é deliberadamente **grande**: ele não compete com painel, porque não está na
// mesma escala de leitura. De longe é o único texto legível da cena; de perto ele sai do
// caminho por estar acima da nuvem, fora do volume que os painéis ocupam.

import * as THREE from 'three';
import { Text } from 'troika-three-text';

import { NEUTRALS, oklchToHex } from './palette';
import { BASE_LOCAL } from './screenBasis';

/** As populações que ganham nome. `vivo` só existe quando há trilha ao vivo. */
export type CloudKey =
  | 'corpus'
  | 'operacional'
  | 'modelos'
  | 'provedores'
  | 'trabalhadores'
  | 'vivo';

export const NOME_DA_NUVEM: Record<CloudKey, string> = {
  corpus: 'CONHECIMENTO',
  operacional: 'QUÓRUM',
  modelos: 'MODELOS',
  provedores: 'PROVEDORES',
  trabalhadores: 'TRABALHADORES',
  vivo: 'RACIOCÍNIO',
};

/** O nome do mundo inteiro, hierarquicamente acima dos nomes de população. */
export const TITULO_DO_ATLAS = 'ATLAS NEURAL EPISTÊMICO';

/**
 * Quão grande, e por que **não** proporcional ao raio.
 *
 * Amarrado linearmente ao raio, o nome da maior nuvem virava o maior objeto da cena e
 * dominava o quadro — o rótulo passava a competir com aquilo que ele rotula. O trabalho
 * do nome é identificação, e identificação não escala com o tamanho do que se identifica:
 * passado o ponto em que se lê, maior só ocupa espaço.
 *
 * A lei sublinear mantém a relação — nuvem maior, nome maior — e comprime a faixa: entre
 * a menor e a maior nuvem da cena, o corpo varia menos de duas vezes em vez de quatro.
 * A referência é o raio do corpus, que é a nuvem que serve de exemplo para o resto.
 */
const RAIO_DE_REFERENCIA = 110;
const CORPO_NA_REFERENCIA = 21;
const EXPOENTE_DO_CORPO = 0.6;
/**
 * Quanto **acima da borda** o nome se assenta, em frações do raio.
 *
 * Medido do centro, e não da borda, o nome caía dentro da própria nuvem e disputava
 * espaço com os painéis que deveria nomear — foi o que aconteceu com o corpus, que é
 * denso e tem raio grande. A conta soma o raio antes da folga.
 */
const ALTURA_SOBRE_A_NUVEM = 0.14;
/**
 * Teto do quanto o nome sobe, em múltiplos do próprio corpo.
 *
 * Proporcional ao raio e sem teto, o nome da nuvem maior subia 445 unidades e saía do
 * quadro — justamente na nuvem em que ele serve mais. Amarrado ao corpo da letra, ele
 * fica sempre a poucas linhas da borda, e nunca longe o bastante para se perder.
 */
const SUBIDA_MAXIMA_EM_LINHAS = 1.6;

export interface CloudTitle {
  key: CloudKey;
  center: THREE.Vector3;
  radius: number;
}

/**
 * Faixa em que o corpo do nome pode variar na tela, em pixels de altura.
 *
 * O nome tinha tamanho de mundo: aproximar a câmera o inflava até virar o objeto maior da
 * cena, e afastar até deixar de se ler. Nenhuma das duas coisas serve a um rótulo, cujo
 * trabalho é identificar — passado o ponto em que se lê, maior só ocupa espaço.
 *
 * A faixa não é um valor único de propósito: fixar o tamanho na tela tiraria do nome a
 * única pista que ele dá sobre profundidade, e as cinco nuvens ficariam à mesma distância
 * aparente. Dentro da faixa a relação sobrevive; fora dela, o limite manda.
 */
const CORPO_EM_TELA = { minimo: 15, maximo: 46 };

/**
 * Opacidade do nome, cheia e apagada.
 *
 * Nome que cruza outro nome não é ambiguidade de leitura: é ilegibilidade dos dois. Quem
 * cede não desaparece — continua marcando o território, só deixa de disputar a leitura.
 */
const OPACIDADE = { cheia: 0.36, apagada: 0.12 };
/** Hierarquia do título global, medida na tela e não em unidades arbitrárias do mundo. */
const TITULO_EM_TELA = {
  proporcao: 1.65,
  minimo: 52,
  maximo: 76,
  larguraMaxima: 0.82,
};
const OPACIDADE_DO_TITULO = 0.62;
/** Largura média observada do alfabeto em caixa alta com o tracking do título. */
const LARGURA_MEDIA_DO_GLIFO = 0.64;

/**
 * Quem vence quando dois nomes se cruzam. Maior número, mais direito de ser lido.
 *
 * A primeira versão comparava **raio**, e ela se enganava exatamente onde mais importa: o
 * raio de uma nuvem é medido no percentil das distâncias ao centro, e o quórum alargado
 * passou a medir mais que o corpus. Resultado: CONHECIMENTO apagava para QUÓRUM ficar
 * legível — a nuvem que dá razão a todas as outras cedendo para uma que existe por causa
 * dela.
 *
 * A ordem aqui é a mesma que decide a altura de cada nuvem na calota: o corpus primeiro
 * porque é ele que dá razão ao resto, depois quem age sobre ele, depois quem o instrumenta.
 * É uma tabela de cinco linhas e não um critério derivado, porque a precedência é
 * editorial e derivá-la de uma medida foi justamente o erro.
 */
const PRECEDENCIA: Record<CloudKey, number> = {
  corpus: 4,
  operacional: 3,
  vivo: 2,
  modelos: 1,
  provedores: 0,
  // A menor precedência da cena, e de propósito: sete placas de configuração não
  // disputam identificação com as nuvens que carregam o trabalho.
  trabalhadores: -1,
};

export interface CloudTitles {
  group: THREE.Group;
  /** Reposiciona e redimensiona os nomes. Chamar quando uma nuvem muda de tamanho. */
  place(nuvens: CloudTitle[]): void;
  /** Gira os nomes para a câmera, como os painéis fazem. */
  orient(quaternion: THREE.Quaternion): void;
  /**
   * Ajusta o que só a câmera decide: tamanho aparente e disputa entre nomes.
   *
   * Separado de `place` porque muda todo quadro, enquanto a posição muda quando uma nuvem
   * muda de tamanho. E feito por **escala do objeto**, nunca por `fontSize`: mexer no
   * corpo da fonte obrigaria o troika a reconstruir os glifos a cada quadro em que a
   * câmera andasse, que é quase todos.
   */
  updateView(camera: THREE.PerspectiveCamera, alturaEmPixels: number): void;
  setVisible(visible: boolean): void;
  /**
   * Onde cada nome está e quanto ele ocupa, para o enquadramento contar com ele.
   *
   * Sem isto, os nomes das nuvens grandes caíam fora do quadro: eles se assentam acima da
   * borda da nuvem, então quanto maior a nuvem, mais longe do que a câmera enquadrava.
   */
  bounds(): { position: THREE.Vector3; halfWidth: number; halfHeight: number }[];
  dispose(): void;
}

/** Um ponto deslocado do centro ao longo de um eixo. */
function somar(centro: THREE.Vector3, eixo: THREE.Vector3Like, quanto: number): THREE.Vector3 {
  return new THREE.Vector3(
    centro.x + eixo.x * quanto,
    centro.y + eixo.y * quanto,
    centro.z + eixo.z * quanto,
  );
}

function distancia(a: THREE.Vector3, b: THREE.Vector3): number {
  return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
}

function componente(ponto: THREE.Vector3Like, eixo: THREE.Vector3Like): number {
  return ponto.x * eixo.x + ponto.y * eixo.y + ponto.z * eixo.z;
}

function noMundo(lateral: number, altura: number, profundidade: number): THREE.Vector3 {
  return new THREE.Vector3(
    BASE_LOCAL.direita.x * lateral +
      BASE_LOCAL.acima.x * altura +
      BASE_LOCAL.profundidade.x * profundidade,
    BASE_LOCAL.direita.y * lateral +
      BASE_LOCAL.acima.y * altura +
      BASE_LOCAL.profundidade.y * profundidade,
    BASE_LOCAL.direita.z * lateral +
      BASE_LOCAL.acima.z * altura +
      BASE_LOCAL.profundidade.z * profundidade,
  );
}

export function atlasTitleScreenSize(
  largestCloudPixels: number,
  viewportWidth: number,
): number {
  const byHierarchy = Math.min(
    Math.max(largestCloudPixels * TITULO_EM_TELA.proporcao, TITULO_EM_TELA.minimo),
    TITULO_EM_TELA.maximo,
  );
  const byWidth =
    (viewportWidth * TITULO_EM_TELA.larguraMaxima) /
    (TITULO_DO_ATLAS.length * LARGURA_MEDIA_DO_GLIFO);
  return Math.min(byHierarchy, byWidth);
}

export function atlasTitlePlacement(
  clouds: readonly CloudTitle[],
  cloudBodies: ReadonlyMap<CloudKey, number>,
): { position: THREE.Vector3; fontSize: number } | null {
  if (clouds.length === 0) return null;
  let left = Number.POSITIVE_INFINITY;
  let right = Number.NEGATIVE_INFINITY;
  let top = Number.NEGATIVE_INFINITY;
  let depth = 0;
  let largestBody = 0;
  for (const cloud of clouds) {
    const lateral = componente(cloud.center, BASE_LOCAL.direita);
    left = Math.min(left, lateral - cloud.radius);
    right = Math.max(right, lateral + cloud.radius);
    top = Math.max(top, componente(cloud.center, BASE_LOCAL.acima) + cloud.radius);
    depth += componente(cloud.center, BASE_LOCAL.profundidade);
    largestBody = Math.max(largestBody, cloudBodies.get(cloud.key) ?? 0);
  }
  const fontSize = Math.max(largestBody * TITULO_EM_TELA.proporcao, 12);
  return {
    position: noMundo((left + right) / 2, top + fontSize * 1.45, depth / clouds.length),
    fontSize,
  };
}

export function createCloudTitles(): CloudTitles {
  const group = new THREE.Group();
  group.name = 'cloud-titles';
  const escritos = new Map<CloudKey, Text>();

  const titulo = new Text();
  titulo.name = 'atlas-neural-epistemico';
  titulo.text = TITULO_DO_ATLAS;
  titulo.anchorX = 'center';
  titulo.anchorY = 'bottom';
  titulo.whiteSpace = 'nowrap';
  titulo.textAlign = 'center';
  titulo.color = oklchToHex(NEUTRALS.textPrimary);
  titulo.letterSpacing = 0.055;
  const materialDoTitulo = titulo.material as THREE.MeshBasicMaterial;
  materialDoTitulo.transparent = true;
  materialDoTitulo.opacity = OPACIDADE_DO_TITULO;
  materialDoTitulo.depthWrite = false;
  titulo.renderOrder = -1;
  titulo.raycast = () => undefined;
  titulo.visible = false;
  titulo.sync();
  group.add(titulo);

  function textoDe(key: CloudKey): Text {
    const existente = escritos.get(key);
    if (existente) return existente;
    const texto = new Text() as Text & {
      text: string;
      fontSize: number;
      color: number;
      anchorX: string;
      anchorY: string;
      material: THREE.Material;
      sync: () => void;
      dispose: () => void;
    };
    texto.text = NOME_DA_NUVEM[key];
    texto.anchorX = 'center';
    texto.anchorY = 'bottom';
    texto.color = oklchToHex(NEUTRALS.textPrimary);
    // Translúcido, e sem escrever profundidade: o nome pertence ao fundo da cena, não à
    // frente dela. Opaco, ele apagaria os painéis que passassem atrás.
    const material = texto.material as THREE.MeshBasicMaterial;
    material.transparent = true;
    material.opacity = OPACIDADE.cheia;
    material.depthWrite = false;
    texto.renderOrder = -1;
    // O nome não é alvo de clique: ele orienta, não seleciona.
    texto.raycast = () => undefined;
    texto.sync();
    group.add(texto);
    escritos.set(key, texto);
    return texto;
  }

  return {
    group,
    place(nuvens) {
      const presentes = new Set(nuvens.map((nuvem) => nuvem.key));
      for (const [key, texto] of escritos) {
        texto.visible = presentes.has(key);
      }
      // Nomes já colocados nesta passada, para o próximo não pousar em cima deles.
      const assentados: { lateral: number; altura: number; meiaLargura: number }[] = [];
      for (const nuvem of nuvens) {
        const texto = textoDe(nuvem.key);
        texto.visible = true;
        texto.fontSize = Math.min(
          80,
          Math.max(
            CORPO_NA_REFERENCIA * Math.pow(Math.max(nuvem.radius, 1) / RAIO_DE_REFERENCIA, EXPOENTE_DO_CORPO),
            6,
          ),
        );
        // Acima no **eixo da tela**, e não no `+z` do mundo: as nuvens são assentadas no
        // plano da visada canônica, e subir em `z` deixaria o nome atrás ou à frente da
        // nuvem em vez de sobre ela.
        const corpo = texto.fontSize as number;
        const subida =
          nuvem.radius + Math.min(nuvem.radius * ALTURA_SOBRE_A_NUVEM, corpo * SUBIDA_MAXIMA_EM_LINHAS);
        // **Acima, a menos que acima seja de outra nuvem.**
        //
        // A regra de subir vinha de quando as nuvens orbitavam o corpus em azimutes
        // repartidos: acima de cada uma havia vazio. Deixou de haver quando a composição
        // virou coluna — conhecimento, raciocínio e quórum no mesmo eixo da tela —, e o
        // nome de cada uma passou a subir para dentro da barriga da de cima. A opacidade
        // resolvia a ilegibilidade apagando um dos dois, o que é remédio para cruzamento
        // eventual, não para colisão por construção.
        //
        // Quando o lugar de cima está tomado, o nome vai para o lado. Lateral é a segunda
        // melhor posição e não a primeira, porque acima é onde se procura um rótulo.
        // **Acima, a menos que acima já seja de alguém** — e "alguém" inclui outro nome,
        // não só outra nuvem. A regra antiga só testava contra o volume das nuvens, então
        // um nome desviado para a direita podia pousar exatamente em cima do nome vizinho:
        // foi o que aconteceu com PROVEDORES sobre TRABALHADORES quando o corpus apertou e
        // as nuvens se aproximaram. A verificação de volume continua, e a de nome entra
        // junto, porque as duas colisões produzem o mesmo defeito para quem lê.
        const meiaLargura = (texto.text as string).length * corpo * 0.3;
        const livre = (posicao: THREE.Vector3): boolean => {
          const dentroDeNuvem = nuvens.some(
            (outra) => outra.key !== nuvem.key && distancia(posicao, outra.center) < outra.radius,
          );
          if (dentroDeNuvem) return false;
          return !assentados.some(
            (posto) =>
              Math.abs(componente(posicao, BASE_LOCAL.direita) - posto.lateral) <
                meiaLargura + posto.meiaLargura &&
              Math.abs(componente(posicao, BASE_LOCAL.acima) - posto.altura) < corpo * 1.4,
          );
        };
        const lateral = nuvem.radius + corpo * SUBIDA_MAXIMA_EM_LINHAS;
        const candidatos: [THREE.Vector3Like, number][] = [
          [BASE_LOCAL.acima, subida],
          [BASE_LOCAL.direita, lateral],
          [BASE_LOCAL.direita, -lateral],
          [BASE_LOCAL.acima, -subida],
        ];
        let escolhido = somar(nuvem.center, BASE_LOCAL.acima, subida);
        for (const [eixo, afastamento] of candidatos) {
          const tentativa = somar(nuvem.center, eixo, afastamento);
          if (livre(tentativa)) {
            escolhido = tentativa;
            break;
          }
        }
        assentados.push({
          lateral: componente(escolhido, BASE_LOCAL.direita),
          altura: componente(escolhido, BASE_LOCAL.acima),
          meiaLargura,
        });
        texto.position.copy(escolhido);
        texto.sync();
      }
      if (nuvens.length === 0) {
        titulo.visible = false;
        return;
      }

      // O envelope é calculado no plano da visada canônica. O centro horizontal do
      // título não pertence à nuvem mais populosa, e sim ao mundo que todas ocupam.
      const placement = atlasTitlePlacement(
        nuvens,
        new Map(nuvens.map((nuvem) => [nuvem.key, textoDe(nuvem.key).fontSize as number])),
      )!;
      titulo.fontSize = placement.fontSize;
      // Finito de propósito: `Infinity` atravessa a serialização interna do worker do
      // Troika de forma diferente entre navegadores e já produziu glifos repetidos.
      titulo.maxWidth = placement.fontSize * TITULO_DO_ATLAS.length * 2;
      titulo.position.copy(placement.position);
      titulo.visible = true;
      titulo.sync();
    },
    orient(quaternion) {
      for (const texto of escritos.values()) texto.quaternion.copy(quaternion);
      titulo.quaternion.copy(quaternion);
    },
    updateView(camera, alturaEmPixels) {
      const tangente = Math.tan((camera.fov * Math.PI) / 360) * 2;
      const visiveis: {
        texto: Text;
        precedencia: number;
        centro: THREE.Vector2;
        meia: THREE.Vector2;
      }[] = [];
      let maiorNomeEmPixels = 0;
      for (const [key, texto] of escritos) {
        if (!texto.visible) continue;
        const distancia = Math.max(camera.position.distanceTo(texto.position), 1e-3);
        const corpo = texto.fontSize as number;
        // Altura aparente que o corpo teria sem correção, em pixels.
        const emPixels = (corpo / (distancia * tangente)) * alturaEmPixels;
        const alvo = Math.min(Math.max(emPixels, CORPO_EM_TELA.minimo), CORPO_EM_TELA.maximo);
        maiorNomeEmPixels = Math.max(maiorNomeEmPixels, alvo);
        texto.scale.setScalar(alvo / emPixels);
        // Caixa aparente, para saber quem cruza quem. A largura sai do corpo e do número
        // de glifos, como em `bounds`: exata não é preciso — o que se decide é se dois
        // nomes disputam o mesmo pedaço de tela.
        const projetado = texto.position.clone().project(camera);
        const alturaAparente = alvo / alturaEmPixels;
        visiveis.push({
          texto,
          precedencia: PRECEDENCIA[key],
          centro: new THREE.Vector2(projetado.x, projetado.y),
          meia: new THREE.Vector2(
            (alturaAparente * (texto.text as string).length * 0.6) / camera.aspect,
            alturaAparente,
          ),
        });
      }
      // Quem cede é o de menor precedência. Empate não existe: a tabela é total.
      for (const item of visiveis) {
        const material = item.texto.material as THREE.MeshBasicMaterial;
        const cruzado = visiveis.some(
          (outro) =>
            outro !== item &&
            outro.precedencia > item.precedencia &&
            Math.abs(outro.centro.x - item.centro.x) < outro.meia.x + item.meia.x &&
            Math.abs(outro.centro.y - item.centro.y) < outro.meia.y + item.meia.y,
        );
        material.opacity = cruzado ? OPACIDADE.apagada : OPACIDADE.cheia;
      }
      if (titulo.visible) {
        const distanciaDoTitulo = Math.max(camera.position.distanceTo(titulo.position), 1e-3);
        const corpoDoTitulo = titulo.fontSize as number;
        const tituloEmPixels =
          (corpoDoTitulo / (distanciaDoTitulo * tangente)) * alturaEmPixels;
        const larguraEmPixels = alturaEmPixels * camera.aspect;
        const alvo = atlasTitleScreenSize(maiorNomeEmPixels, larguraEmPixels);
        titulo.scale.setScalar(alvo / Math.max(tituloEmPixels, 1e-3));
      }
    },
    setVisible(visible) {
      group.visible = visible;
    },
    bounds() {
      const saida: { position: THREE.Vector3; halfWidth: number; halfHeight: number }[] = [];
      for (const texto of escritos.values()) {
        if (!texto.visible) continue;
        // Meia-caixa aproximada pelo corpo e pelo número de glifos: exata não é preciso,
        // porque o que se quer é não cortar o nome, e errar por excesso só afasta um
        // pouco a câmera.
        const escala = texto.scale.x;
        const largura = (texto.text as string).length * (texto.fontSize as number) * 0.6 * escala;
        const altura = (texto.fontSize as number) * escala;
        const acimaDaCamera = new THREE.Vector3(0, 1, 0).applyQuaternion(texto.quaternion);
        saida.push({
          position: texto.position.clone().addScaledVector(acimaDaCamera, altura / 2),
          halfWidth: largura / 2,
          halfHeight: altura / 2,
        });
      }
      if (titulo.visible) {
        const altura = (titulo.fontSize as number) * titulo.scale.x;
        const largura = TITULO_DO_ATLAS.length * altura * LARGURA_MEDIA_DO_GLIFO;
        const acimaDaCamera = new THREE.Vector3(0, 1, 0).applyQuaternion(titulo.quaternion);
        saida.push({
          position: titulo.position.clone().addScaledVector(acimaDaCamera, altura / 2),
          halfWidth: largura / 2,
          halfHeight: altura / 2,
        });
      }
      return saida;
    },
    dispose() {
      for (const texto of escritos.values()) {
        group.remove(texto);
        texto.dispose();
      }
      escritos.clear();
      group.remove(titulo);
      titulo.dispose();
    },
  };
}
