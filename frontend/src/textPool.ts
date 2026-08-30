// Quem ganha texto quando não há texto para todos.
//
// Terceiro incremento da ADR-002, subetapa 3.2. Este módulo é puro: ele não cria
// objeto do troika, não toca na cena e não mede nada por conta própria. Recebe
// candidatos já medidos pelo renderizador e devolve uma atribuição de vagas.
//
// **Por que existe um teto.** Um `Text` do troika é um objeto próprio, com geometria
// e material. Um painel em nível `expanded` pede seis linhas; oitenta e quatro
// painéis pediriam centenas de objetos, e a promessa de poucas chamadas de desenho
// morreria no texto depois de ter sido salva no corpo.
//
// **Por que a estabilidade importa mais que o ranking exato.** Reordenar a cada
// quadro pelo melhor ranking produz troca frenética: dois painéis a distâncias quase
// iguais roubariam a vaga um do outro indefinidamente, e o resultado é cintilação.
// Um titular só é desalojado por candidato de **classe estritamente superior** — a
// mesma disciplina da histerese que o LOD já aplica.
//
// **Por que a colisão se resolve aqui.** Caber no teto e caber na tela são a mesma
// decisão: adiar a segunda para depois de atribuir as vagas gastaria objeto com
// texto que ia ficar por baixo de outro. A caixa em pixels chega pronta do
// renderizador — este módulo continua não medindo nada por conta própria — e a
// ordem, que já favorece titular, garante que quem é recusado seja sempre o rótulo
// novo, nunca o que já estava sendo lido.

import type { LodLevel } from './lod';

/** Teto único, com pisos por camada. Medido em objetos `Text`, não em linhas. */
/**
 * Vagas de texto.
 *
 * Eram 64, e o teto era uma política de leitura: com poucas vagas, o pool escolhia
 * quem escrevia e o resto ficava mudo, o que mantinha a cena limpa e tornava a maior
 * parte dos painéis caixas sem palavra. A direção mudou — todo painel escreve, mesmo
 * que os textos se sobreponham, e a legibilidade passa a ser resolvida escolhendo um
 * painel, que fica opaco.
 *
 * O teto continua existindo porque um pool sem limite é um vazamento esperando
 * acontecer; ele agora cobre a cena inteira com folga, e quem limita de fato é o
 * enquadramento: painel fora da tela não vira candidato.
 */
export const TOTAL_TEXT_SLOTS = 640;
/** Piso do corpus: seleção de corpus não pode ser apagada por rajada de eventos. */
export const MIN_CORPUS_SLOTS = 16;
/** Piso do runtime: leitura operacional não pode sumir porque o corpus encheu. */
export const MIN_RUNTIME_SLOTS = 8;

export type TextSource = 'corpus' | 'runtime';

/** Caixa do painel em pixels de tela, com origem no centro. */
export interface ScreenBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface TextCandidate {
  entityId: string;
  lod: LodLevel;
  selected: boolean;
  hovered: boolean;
  projectedSize: number;
  distance: number;
  source: TextSource;
  /**
   * Onde o painel cai na tela. Opcional: sem ela o pool decide só por classe.
   *
   * Com ela, um candidato é recusado quando sua área colide com a de alguém já
   * admitido. Como a ordem já põe selecionado, sobrevoado e titular na frente, a
   * recusa sempre atinge o rótulo **novo** — que é a regra de estabilidade pedida:
   * nada novo aparece por cima do que já estava priorizado.
   */
  screen?: ScreenBox;
}

/** Sobreposição de duas caixas centradas. Toque de borda não conta como colisão. */
function colide(a: ScreenBox, b: ScreenBox): boolean {
  return (
    Math.abs(a.x - b.x) < (a.width + b.width) / 2 &&
    Math.abs(a.y - b.y) < (a.height + b.height) / 2
  );
}

export interface TextAllocation {
  entityId: string;
  slotId: number;
  priority: number;
}

// Classes de prioridade. O degrau entre elas é grande de propósito: nenhuma
// combinação de tamanho projetado e distância promove um candidato de classe.
const CLASSE_SELECIONADO = 5000;
const CLASSE_HOVER = 4000;
const CLASSE_POR_LOD: Record<LodLevel, number> = {
  expanded: 3000,
  legible: 2000,
  identifiable: 1000,
  structural: 0,
  distant: 0,
};

/** Classe de um candidato. Zero significa inelegível a texto neste quadro. */
export function classOf(candidate: TextCandidate): number {
  if (candidate.selected) return CLASSE_SELECIONADO;
  if (candidate.hovered) return CLASSE_HOVER;
  return CLASSE_POR_LOD[candidate.lod];
}

export interface TextPool {
  readonly capacity: number;
  /** Vagas atribuídas agora, por entidade. */
  current(): TextAllocation[];
  slotOf(entityId: string): number | null;
  /** Reatribui as vagas a partir dos candidatos deste quadro. */
  allocate(candidates: TextCandidate[]): TextAllocation[];
  /** Devolve vagas específicas — usado quando a entidade some da projeção. */
  release(entityIds: string[]): void;
  dispose(): void;
}

interface Classificado {
  candidate: TextCandidate;
  classe: number;
  titular: boolean;
}

/**
 * Ordem total e determinística.
 *
 * Classe primeiro; **titular ganha do desafiante de mesma classe**, que é o
 * mecanismo de estabilidade; depois tamanho projetado, distância e, por último, o
 * `entityId`, que garante desempate reprodutível mesmo com medidas idênticas.
 */
function comparar(a: Classificado, b: Classificado): number {
  if (a.classe !== b.classe) return b.classe - a.classe;
  if (a.titular !== b.titular) return a.titular ? -1 : 1;
  if (a.candidate.projectedSize !== b.candidate.projectedSize) {
    return b.candidate.projectedSize - a.candidate.projectedSize;
  }
  if (a.candidate.distance !== b.candidate.distance) {
    return a.candidate.distance - b.candidate.distance;
  }
  return a.candidate.entityId.localeCompare(b.candidate.entityId);
}

export function createTextPool(
  capacity = TOTAL_TEXT_SLOTS,
  minCorpus = MIN_CORPUS_SLOTS,
  minRuntime = MIN_RUNTIME_SLOTS,
  permitirSobreposicao = true,
): TextPool {
  const teto = Math.max(0, Math.floor(capacity));
  let porEntidade = new Map<string, number>();
  let prioridadePorEntidade = new Map<string, number>();

  function livres(ocupadas: Set<number>): number[] {
    const vagas: number[] = [];
    for (let slot = 0; slot < teto; slot += 1) if (!ocupadas.has(slot)) vagas.push(slot);
    return vagas;
  }

  return {
    capacity: teto,
    current() {
      return [...porEntidade.entries()]
        .map(([entityId, slotId]) => ({
          entityId,
          slotId,
          priority: prioridadePorEntidade.get(entityId) ?? 0,
        }))
        .sort((a, b) => a.slotId - b.slotId);
    },
    slotOf(entityId) {
      return porEntidade.get(entityId) ?? null;
    },
    allocate(candidates) {
      const elegiveis: Classificado[] = [];
      for (const candidate of candidates) {
        const classe = classOf(candidate);
        if (classe <= 0) continue;
        elegiveis.push({ candidate, classe, titular: porEntidade.has(candidate.entityId) });
      }
      elegiveis.sort(comparar);

      // Pisos por camada: garantem presença mínima quando existe demanda, e nada
      // além disso. Vaga que uma camada não usa volta para o bolo comum.
      const escolhidos: Classificado[] = [];
      const dentro = new Set<string>();
      const ocupadasNaTela: ScreenBox[] = [];
      const piso: Record<TextSource, number> = { corpus: minCorpus, runtime: minRuntime };

      // Sobrepor deixou de ser motivo de recusa.
      //
      // A recusa por colisão existia para nenhum rótulo cair sobre outro. O preço era
      // um painel emudecer porque um vizinho chegou primeiro, e o silêncio não avisava
      // que havia texto ali. Agora todos escrevem; quem resolve a leitura é a seleção,
      // que traz o painel escolhido para a frente e opaco.
      const cabeNaTela = (item: Classificado): boolean =>
        permitirSobreposicao || !item.candidate.screen
          ? true
          : !ocupadasNaTela.some((outra) => colide(outra, item.candidate.screen!));
      const admitir = (item: Classificado): void => {
        escolhidos.push(item);
        dentro.add(item.candidate.entityId);
        if (item.candidate.screen) ocupadasNaTela.push(item.candidate.screen);
      };

      for (const fonte of ['corpus', 'runtime'] as TextSource[]) {
        let usadas = 0;
        for (const item of elegiveis) {
          if (escolhidos.length >= teto || usadas >= Math.min(piso[fonte], teto)) break;
          if (item.candidate.source !== fonte) continue;
          if (dentro.has(item.candidate.entityId) || !cabeNaTela(item)) continue;
          admitir(item);
          usadas += 1;
        }
      }
      for (const item of elegiveis) {
        if (escolhidos.length >= teto) break;
        if (dentro.has(item.candidate.entityId) || !cabeNaTela(item)) continue;
        admitir(item);
      }

      // Titular conserva a vaga; quem entra ocupa as que sobraram, em ordem.
      const novasPorEntidade = new Map<string, number>();
      const ocupadas = new Set<number>();
      for (const item of escolhidos) {
        const anterior = porEntidade.get(item.candidate.entityId);
        if (anterior !== undefined && anterior < teto && !ocupadas.has(anterior)) {
          novasPorEntidade.set(item.candidate.entityId, anterior);
          ocupadas.add(anterior);
        }
      }
      const vagas = livres(ocupadas);
      let proxima = 0;
      for (const item of escolhidos) {
        if (novasPorEntidade.has(item.candidate.entityId)) continue;
        const slot = vagas[proxima];
        proxima += 1;
        if (slot === undefined) break;
        novasPorEntidade.set(item.candidate.entityId, slot);
      }

      porEntidade = novasPorEntidade;
      prioridadePorEntidade = new Map(
        escolhidos.map((item) => [item.candidate.entityId, item.classe]),
      );
      return this.current();
    },
    release(entityIds) {
      for (const entityId of entityIds) {
        porEntidade.delete(entityId);
        prioridadePorEntidade.delete(entityId);
      }
    },
    dispose() {
      porEntidade = new Map();
      prioridadePorEntidade = new Map();
    },
  };
}
