// Objetos de texto criados uma vez, que mudam de dono. Dois por vaga: corpo e título.
//
// Subetapa 3.3b da ADR-002. O pool lógico de `textPool.ts` decide **quem** recebe
// texto; este módulo é o que de fato desenha, e a regra que o governa é uma só:
// nenhum `Text` nasce ou morre fora da inicialização e do descarte.
//
// **Por que o objeto é por vaga e não por entidade.** Amarrar o objeto gráfico à
// entidade faria a contagem crescer com o corpus, que é exatamente o que o teto
// existe para impedir. A vaga é fixa, a entidade passa por ela.
//
// **Por que a medição real importa.** O layout puro estima encaixe contando
// caracteres, e caractere não tem largura uniforme: uma linha de `i` cabe onde uma de
// `M` estoura. A estimativa serve de orçamento; a autoridade é o bloco medido depois
// do `sync()`. Medir custa, então só se remede quando entidade, conteúdo, extensão ou
// composição mudaram — nunca porque a câmera girou.

import type { LodLevel } from './lod';
import type { PanelDescriptor, PanelLine } from './panels';
import type { WorldExtent } from './panelScale';
import { shapeHeightRatio, textAreaOf } from './panelShapes';
import {
  composeText,
  layoutPanelText,
  type PanelTextLayout,
} from './panelTextLayout';
import { TOTAL_TEXT_SLOTS, type TextAllocation } from './textPool';

/** Ordem de desenho do texto: imediatamente acima da placa, nunca acima da cena. */
export const TEXT_RENDER_ORDER = 2;
/**
 * Objetos `Text` que cada vaga aloca: o corpo e o título.
 *
 * Existe como constante exportada porque três lugares precisavam saber disso e dois
 * deles supunham `1` — a métrica deste módulo e o invariante do harness. Um número que
 * três arquivos derivam por conta própria é um número que vai divergir.
 */
export const TEXT_OBJECTS_PER_SLOT = 2;
/**
 * A ordem do texto do painel expandido.
 *
 * Ele acompanha a placa da frente, que desenha acima de todas as outras. Se ficasse
 * na ordem comum, a própria placa que o carrega o cobriria — e o painel escolhido
 * apareceria cheio de superfície e vazio de conteúdo, que é o defeito que a placa da
 * frente foi criada para desfazer.
 */
export const TEXT_FRONT_RENDER_ORDER = 4;
/** Teto de correções por atualização. Duas passagens, nunca um laço até caber. */
const MAX_CORRECOES = 2;
/** O título é maior que o corpo: é ele que identifica à distância. */
const PROPORCAO_DO_TITULO = 1.9;
/** Folga entre a borda de cima da placa e a base do título, em corpos de fonte. */
const FOLGA_DO_TITULO = 0.45;

/** O mínimo que este módulo exige de um objeto de texto. */
export interface TextLike {
  text: string;
  fontSize: number;
  maxWidth: number;
  lineHeight: number;
  anchorX: string;
  anchorY: string;
  textAlign: string;
  visible: boolean;
  renderOrder: number;
  depthOffset?: number;
  position: { set(x: number, y: number, z: number): void };
  quaternion: { set(x: number, y: number, z: number, w: number): void };
  sync(callback?: () => void): void;
  dispose(): void;
  textRenderInfo?: { blockBounds?: number[] } | null;
  /**
   * Recorte, no espaço do próprio objeto: `[minX, minY, maxX, maxY]`.
   *
   * É o que permite o painel selecionado mostrar mais conteúdo do que a placa comporta
   * sem que o excedente vaze por cima dos vizinhos. Quem não rola recebe `null` e
   * desenha como sempre desenhou.
   */
  clipRect?: [number, number, number, number] | null;
  /**
   * O material desenhado, quando o objeto expõe um.
   *
   * `renderOrder` sozinho não basta para o texto do painel expandido. O three.js
   * desenha a fila opaca inteira antes da transparente, e o troika entrega um
   * material que não é necessariamente transparente: o texto caía na fila opaca,
   * era testado contra a profundidade dos vizinhos e desaparecia atrás deles — a
   * placa da frente ficava cheia de superfície e vazia de conteúdo. Tirar o teste de
   * profundidade **de uma vaga só**, a que a placa da frente carrega, é o que põe as
   * duas na mesma fila e na ordem certa.
   */
  material?: { depthTest: boolean; transparent: boolean; needsUpdate: boolean } | null;
}

export interface PanelTransform {
  position: { x: number; y: number; z: number };
  quaternion: { x: number; y: number; z: number; w: number };
  extent: WorldExtent;
}

export interface PanelTextFrame {
  allocations: TextAllocation[];
  /** Origem por entidade, para a telemetria distinguir corpus de runtime. */
  sources?: ReadonlyMap<string, 'corpus' | 'runtime'>;
  descriptors: ReadonlyMap<string, PanelDescriptor>;
  transforms: ReadonlyMap<string, PanelTransform>;
  lines: ReadonlyMap<string, PanelLine[]>;
  /**
   * Marca de versão das linhas, para quem as troca por algo que o descritor não deriva.
   *
   * O cache de layout tinha na chave entidade, nível, extensão e rolagem — e isso bastava
   * enquanto as linhas eram função pura do descritor e do nível. Deixou de bastar no dia
   * em que o painel aberto passou a receber o documento da nota, que chega depois, pela
   * rede: as quatro grandezas da chave continuavam iguais, o cache respondia com o layout
   * anterior, e o documento nunca aparecia. Quem troca as linhas declara aqui que trocou.
   */
  lineRevision?: ReadonlyMap<string, string>;
  /** Deslocamento de leitura por entidade, para o painel que rola. */
  scroll?: ReadonlyMap<string, number>;
  /** Nível por entidade. Sem ele o layout não sabe o que o degrau permite escrever. */
  levels: ReadonlyMap<string, LodLevel>;
  /** A entidade desenhada pela placa da frente, se houver. Só o texto dela sobe. */
  front?: string | null;
}

/**
 * Por que uma sincronização aconteceu.
 *
 * Contador total não prova estabilidade: `+19` em 40 quadros tanto pode ser LOD
 * mudando de verdade quanto o pool trocando de dono sem motivo. A causa separa as
 * duas leituras — e nenhuma delas pode ser transformação de câmera.
 */
export type TextSyncReason =
  | 'initial'
  | 'owner-changed'
  | 'content-changed'
  | 'extent-changed'
  | 'overflow-secondary-removed'
  | 'overflow-title-ellipsized';

export const SYNC_REASONS: TextSyncReason[] = [
  'initial',
  'owner-changed',
  'content-changed',
  'extent-changed',
  'overflow-secondary-removed',
  'overflow-title-ellipsized',
];

/** Quanto um painel rolável comporta, para quem controla a roda saber o limite. */
export interface PanelScrollExtent {
  entityId: string;
  maxScroll: number;
  contentHeight: number;
}

export interface PanelTextMetrics {
  capacity: number;
  allocatedSlots: number;
  createdObjects: number;
  visibleObjects: number;
  syncCalls: number;
  syncByReason: Record<TextSyncReason, number>;
  /** Vagas que mudaram de entidade proprietária desde a inicialização. */
  allocationOwnerChanges: number;
  contentKeyChanges: number;
  corpusAllocated: number;
  runtimeAllocated: number;
}

export interface PanelTextRenderer {
  /** Os objetos gráficos, para quem precisa adicioná-los à cena. */
  objects(): TextLike[];
  update(frame: PanelTextFrame): void;
  metrics(): PanelTextMetrics;
  /** O que o último quadro apurou sobre a rolagem de cada painel rolável. */
  scrollExtents(): PanelScrollExtent[];
  entityAt(slotId: number): string | null;
  dispose(): void;
}

interface GraphicTextSlot {
  slotId: number;
  /** O título, desenhado acima e fora da placa. */
  titulo: TextLike;
  /** O que o título já mostra, para não sincronizar sem mudança. */
  tituloEscrito: string;
  /** O layout já calculado, e a chave que o valida. */
  layoutCache: PanelTextLayout | null;
  layoutKey: string;
  source: 'corpus' | 'runtime' | null;
  entityId: string | null;
  text: TextLike;
  /**
   * Assinatura da composição **pedida** neste quadro.
   *
   * Separada do que está desenhado de propósito. A correção de estouro altera o
   * texto depois de medido, e comparar contra o texto corrigido faria a chave nunca
   * mais bater com a composição pedida: o painel voltaria a sincronizar em todo
   * quadro, para sempre, sem que LOD ou dono tivessem mudado.
   */
  requestKey: string;
  /** Assinatura do que está efetivamente desenhado, já com correções aplicadas. */
  contentKey: string;
  /**
   * Altura **medida** do bloco, e a assinatura do conteúdo a que ela pertence.
   *
   * Só o painel rolável a usa, e só para o limite de rolagem. A chave é obrigatória
   * porque a medição do troika é assíncrona: sem ela, a altura de um documento longo
   * sobreviveria à troca de conteúdo e o painel seguinte prometeria uma rolagem que não
   * tem.
   */
  medidaDoConteudo: { key: string; height: number } | null;
  /**
   * Geração monotônica da vaga.
   *
   * A medição do troika é assíncrona: o retorno de `sync` pode chegar depois de a
   * vaga já pertencer a outra entidade, e aí a correção de estouro de A reescreveria
   * o texto de B. `contentKey` sozinho não protege, porque um conteúdo anterior pode
   * reaparecer numa realocação. A geração protege, porque nunca se repete.
   */
  generation: number;
}

export interface PanelTextRendererOptions {
  capacity?: number;
  createText: () => TextLike;
}

function assinatura(entityId: string, conteudo: string, extent: WorldExtent): string {
  return `${entityId}|${conteudo}|${extent.width.toFixed(4)}x${extent.height.toFixed(4)}`;
}

/**
 * Gira um deslocamento local pelo quaternion da placa.
 *
 * O layout devolve coordenadas **locais** à placa. Somá-las direto à posição de mundo
 * só estaria certo se a placa nunca girasse — e ela gira todo quadro, acompanhando a
 * câmera. Sem esta rotação o texto se afasta da própria placa conforme a órbita anda.
 */
function girar(
  q: { x: number; y: number; z: number; w: number },
  v: { x: number; y: number; z: number },
): { x: number; y: number; z: number } {
  const ix = q.w * v.x + q.y * v.z - q.z * v.y;
  const iy = q.w * v.y + q.z * v.x - q.x * v.z;
  const iz = q.w * v.z + q.x * v.y - q.y * v.x;
  const iw = -q.x * v.x - q.y * v.y - q.z * v.z;
  return {
    x: ix * q.w + iw * -q.x + iy * -q.z - iz * -q.y,
    y: iy * q.w + iw * -q.y + iz * -q.x - ix * -q.z,
    z: iz * q.w + iw * -q.z + ix * -q.y - iy * -q.x,
  };
}

/** Largura e altura reais do bloco desenhado, quando o objeto sabe informá-las. */
function medido(text: TextLike): { width: number; height: number } | null {
  const bounds = text.textRenderInfo?.blockBounds;
  if (!bounds || bounds.length < 4) return null;
  const [x0, y0, x1, y1] = bounds as [number, number, number, number];
  return { width: Math.abs(x1 - x0), height: Math.abs(y1 - y0) };
}

export function createPanelTextRenderer(
  options: PanelTextRendererOptions,
): PanelTextRenderer {
  const capacity = Math.max(0, Math.floor(options.capacity ?? TOTAL_TEXT_SLOTS));
  let descartado = false;
  let syncCalls = 0;
  let allocationOwnerChanges = 0;
  /** Reaproveitado entre quadros: medir rolagem não pode alocar a cada atualização. */
  const extensoesDeRolagem: PanelScrollExtent[] = [];
  let contentKeyChanges = 0;
  const syncByReason: Record<TextSyncReason, number> = Object.fromEntries(
    SYNC_REASONS.map((reason) => [reason, 0]),
  ) as Record<TextSyncReason, number>;

  /**
   * Objetos de texto realmente alocados, contados um a um.
   *
   * Era `slots.length`, o que valia enquanto cada vaga tinha um objeto só. Desde que o
   * título virou um segundo `Text`, a conta passou a dizer metade do que existe — e a
   * métrica que deveria denunciar vazamento passou a escondê-lo. Contar na criação é o
   * que impede a conta de mentir de novo se um terceiro objeto aparecer aqui.
   */
  let objetosCriados = 0;
  const criarTexto = (): TextLike => {
    objetosCriados += 1;
    return options.createText();
  };

  // Toda a criação acontece aqui, e só aqui.
  const slots: GraphicTextSlot[] = Array.from({ length: capacity }, (_, slotId) => {
    const text = criarTexto();
    text.visible = false;
    text.text = '';
    text.renderOrder = TEXT_RENDER_ORDER;
    // O título é um segundo objeto, e não uma primeira linha do bloco.
    //
    // Dentro da placa ele disputava as linhas com o conteúdo, e um painel pequeno
    // gastava metade da área dizendo o próprio nome. Fora e acima, ele identifica à
    // distância — que é quando o nome importa — e devolve a placa inteira ao texto.
    const titulo = criarTexto();
    titulo.visible = false;
    titulo.text = '';
    titulo.renderOrder = TEXT_RENDER_ORDER;
    titulo.anchorX = 'center';
    titulo.anchorY = 'bottom';
    titulo.textAlign = 'center';
    return {
      slotId,
      source: null,
      entityId: null,
      text,
      titulo,
      tituloEscrito: '',
      requestKey: '',
      contentKey: '',
      medidaDoConteudo: null,
      layoutCache: null,
      layoutKey: '',
      generation: 0,
    };
  });
  let candidateSource: ReadonlyMap<string, 'corpus' | 'runtime'> = new Map();

  function limpar(slot: GraphicTextSlot): void {
    if (slot.entityId === null && slot.text.text === '') {
      slot.text.visible = false;
      slot.titulo.visible = false;
      return;
    }
    // O título é limpo junto: vaga liberada com texto residual é a mesma falha que
    // este caminho existe para impedir, e o resíduo apareceria flutuando sem placa.
    slot.titulo.visible = false;
    slot.titulo.text = '';
    slot.tituloEscrito = '';
    slot.entityId = null;
    slot.source = null;
    slot.requestKey = '';
    slot.contentKey = '';
    slot.generation += 1;
    allocationOwnerChanges += 1;
    slot.text.text = '';
    slot.text.visible = false;
    // Sincroniza o esvaziamento: sem isso o bloco anterior continua desenhado e o
    // texto de outra entidade reaparece quando a vaga volta a ficar visível.
    slot.text.sync();
    syncCalls += 1;
    syncByReason['owner-changed'] += 1;
  }

  /**
   * Sincroniza e, no retorno, corrige o estouro medido de verdade.
   *
   * A ordem preserva significado: caem primeiro linhas de corpo, que são acessórias,
   * e só depois o título encurta. Teto de duas passagens — nunca um laço até caber.
   *
   * **Quantas linhas caem é proporcional ao excesso medido**, não "todas". O bloco
   * medido diz de quanto ele passou da caixa; manter a fração que caberia derruba o
   * mínimo necessário. Apagar o corpo inteiro por uma linha a mais era o que
   * transformava um painel de seis frases em um painel de zero.
   */
  function sincronizar(
    slot: GraphicTextSlot,
    layout: ReturnType<typeof layoutPanelText>,
    extent: WorldExtent,
    passagem: number,
    motivo: TextSyncReason,
  ): void {
    slot.generation += 1;
    const geracao = slot.generation;
    const dono = slot.entityId;
    syncCalls += 1;
    syncByReason[motivo] += 1;
    slot.text.sync(() => {
      // A vaga trocou de dono ou de conteúdo enquanto a medição vinha: este retorno
      // não fala mais por ninguém.
      if (slot.generation !== geracao || slot.entityId !== dono || dono === null) return;
      if (passagem >= MAX_CORRECOES) return;
      const real = medido(slot.text);
      if (!real) return;

      // **No painel que rola, estouro não é defeito: é o que há para rolar.**
      //
      // A correção abaixo existe para o painel de tamanho fixo, onde texto que passa da
      // placa vaza para fora dela e precisa ser cortado. Aplicada ao painel aberto, ela
      // cortava justamente o documento: com 81 linhas medindo oito vezes a altura útil,
      // a primeira passagem guardava dez linhas, a segunda cortava de novo, e o que
      // sobrava era o cabeçalho e duas linhas. Era esta a causa de o painel aberto parar
      // no título e na descrição — e ela é anterior ao documento chegar, porque já
      // cortava as frases derivadas do descritor pela mesma conta.
      //
      // O que o painel rolável faz com a medida é outra coisa: guardá-la. A altura
      // estimada por `layoutPanelText` conta glifos por uma largura média, e num
      // documento de 14 mil caracteres o erro dessa média decide se as últimas linhas
      // são alcançáveis. Medido é melhor que estimado, e aqui a medida existe.
      if (layout.scrollable) {
        slot.medidaDoConteudo = { key: slot.contentKey, height: real.height };
        return;
      }
      if (real.height <= layout.maxHeight) return;

      let corrigido: ReturnType<typeof layoutPanelText>;
      let motivoDaCorrecao: TextSyncReason;
      if (layout.body.length > 0) {
        const cabem = Math.floor((layout.body.length * layout.maxHeight) / real.height);
        const manter = Math.max(0, Math.min(cabem, layout.body.length - 1));
        corrigido = { ...layout, body: layout.body.slice(0, manter) };
        motivoDaCorrecao = 'overflow-secondary-removed';
      } else if (!layout.titleTruncated && layout.title.length > 4) {
        corrigido = {
          ...layout,
          title: `${layout.title.slice(0, Math.max(layout.title.length - 8, 3))}…`,
          titleTruncated: true,
        };
        motivoDaCorrecao = 'overflow-title-ellipsized';
      } else {
        return;
      }
      const conteudo = composeText(corrigido);
      slot.text.text = conteudo;
      slot.contentKey = assinatura(dono, conteudo, extent);
      contentKeyChanges += 1;
      sincronizar(slot, corrigido, extent, passagem + 1, motivoDaCorrecao);
    });
  }

  return {
    objects() {
      return slots.flatMap((slot) => [slot.text, slot.titulo]);
    },
    entityAt(slotId) {
      return slots[slotId]?.entityId ?? null;
    },
    update(frame) {
      if (descartado) return;
      candidateSource = frame.sources ?? new Map();
      extensoesDeRolagem.length = 0;
      const porVaga = new Map<number, TextAllocation>();
      for (const allocation of frame.allocations) {
        if (allocation.slotId >= 0 && allocation.slotId < capacity) {
          porVaga.set(allocation.slotId, allocation);
        }
      }

      for (const slot of slots) {
        const allocation = porVaga.get(slot.slotId);
        const descriptor = allocation
          ? frame.descriptors.get(allocation.entityId)
          : undefined;
        const transform = allocation ? frame.transforms.get(allocation.entityId) : undefined;
        if (!allocation || !descriptor || !transform) {
          limpar(slot);
          continue;
        }

        const linhas = frame.lines.get(allocation.entityId) ?? [];
        const nivel = frame.levels.get(allocation.entityId) ?? 'legible';
        // O layout é caro e quase sempre o mesmo.
        //
        // Ele mede a quebra de cada linha na largura útil, e com quinhentos painéis
        // escrevendo isso passou a ser o quadro inteiro: 60 ms por quadro com **zero**
        // sincronizações, ou seja, tempo gasto recalculando o que não mudou. A chave
        // cobre tudo que o layout enxerga — entidade, nível, extensão e rolagem. Posição
        // e orientação continuam reescritas todo quadro, porque essas mudam de verdade.
        const rolagem = frame.scroll?.get(allocation.entityId) ?? 0;
        // O texto é disposto no retângulo **inscrito** na silhueta, e não na caixa
        // envolvente dela: num hexágono ele começava fora do polígono, e num losango
        // escapava pelos quatro cantos.
        const forma = descriptor.shape;
        const areaDeTexto = textAreaOf(forma, transform.extent);
        const chaveDeLayout =
          `${allocation.entityId}|${nivel}|` +
          `${areaDeTexto.width.toFixed(4)}x${areaDeTexto.height.toFixed(4)}|` +
          `${rolagem.toFixed(3)}|` +
          `${frame.lineRevision?.get(allocation.entityId) ?? ''}`;
        if (slot.layoutCache === null || slot.layoutKey !== chaveDeLayout) {
          slot.layoutCache = layoutPanelText(descriptor, areaDeTexto, linhas, nivel, rolagem);
          slot.layoutKey = chaveDeLayout;
        }
        const layout = slot.layoutCache;
        const conteudo = composeText(layout);
        const chave = assinatura(allocation.entityId, conteudo, transform.extent);
        if (layout.scrollable) {
          // A medida vence a estimativa quando ela existe **e é deste conteúdo**. Sem
          // isso, o limite de rolagem de um documento de 14 mil caracteres saía de uma
          // largura de glifo média, e as últimas linhas ficavam inalcançáveis pelo erro
          // acumulado dessa média.
          const medida =
            slot.medidaDoConteudo?.key === chave ? slot.medidaDoConteudo.height : null;
          const alturaDoConteudo = Math.max(medida ?? 0, layout.contentHeight);
          extensoesDeRolagem.push({
            entityId: allocation.entityId,
            maxScroll: Math.max(alturaDoConteudo - layout.maxHeight, 0),
            contentHeight: alturaDoConteudo,
          });
        }

        if (chave !== slot.requestKey) {
          const donoAnterior = slot.entityId;
          const extensaoAnterior = slot.requestKey.split('|')[2];
          const motivo: TextSyncReason =
            donoAnterior === null
              ? 'initial'
              : donoAnterior !== allocation.entityId
                ? 'owner-changed'
                : extensaoAnterior !==
                    `${transform.extent.width.toFixed(4)}x${transform.extent.height.toFixed(4)}`
                  ? 'extent-changed'
                  : 'content-changed';
          if (donoAnterior !== null && donoAnterior !== allocation.entityId) {
            allocationOwnerChanges += 1;
          }
          contentKeyChanges += 1;
          slot.source = candidateSource.get(allocation.entityId) ?? null;
          slot.entityId = allocation.entityId;
          slot.requestKey = chave;
          slot.contentKey = chave;
          slot.text.fontSize = layout.fontSize;
          slot.text.maxWidth = layout.maxWidth;
          slot.text.lineHeight = layout.lineHeight;
          slot.text.anchorX = layout.anchorX;
          slot.text.anchorY = layout.anchorY;
          slot.text.textAlign = layout.textAlign;
          slot.text.text = conteudo;
          slot.text.clipRect = layout.scrollable ? layout.clipRect : null;
          sincronizar(slot, layout, transform.extent, 0, motivo);
        }

        // Posição e orientação mudam todo quadro e **não** exigem sincronização: o
        // bloco desenhado é o mesmo, só a matriz do objeto muda.
        // O recorte acompanha a rolagem e muda sem trocar o conteúdo, então ele é
        // reescrito fora do bloco de sincronização — como a posição.
        if (layout.scrollable) slot.text.clipRect = layout.clipRect;
        const deslocamento = girar(transform.quaternion, {
          x: layout.localX,
          y: layout.localY + areaDeTexto.offsetY,
          z: layout.localZ,
        });
        slot.text.position.set(
          transform.position.x + deslocamento.x,
          transform.position.y + deslocamento.y,
          transform.position.z + deslocamento.z,
        );
        slot.text.quaternion.set(
          transform.quaternion.x,
          transform.quaternion.y,
          transform.quaternion.z,
          transform.quaternion.w,
        );
        // O título acompanha a placa: mesma orientação, acima da borda superior,
        // centrado. A escala é da placa **compacta**, para expandir um painel não inflar
        // o nome dele junto. A borda que conta é a da **silhueta**, não a da extensão:
        // como a área é normalizada, o losango passa 41% da caixa e o triângulo 32%, e
        // medir pela extensão punha o título dentro da própria forma.
        const nomeDesejado = descriptor.title;
        if (slot.tituloEscrito !== nomeDesejado) {
          slot.titulo.text = nomeDesejado;
          slot.titulo.maxWidth = transform.extent.width * 2.2;
          slot.tituloEscrito = nomeDesejado;
          slot.titulo.sync();
        }
        slot.titulo.fontSize = layout.fontSize * PROPORCAO_DO_TITULO;
        slot.titulo.lineHeight = 1.15;
        const acimaDaPlaca = girar(transform.quaternion, {
          x: 0,
          y:
            (transform.extent.height * shapeHeightRatio(forma)) / 2 +
            slot.titulo.fontSize * FOLGA_DO_TITULO,
          z: layout.localZ,
        });
        slot.titulo.position.set(
          transform.position.x + acimaDaPlaca.x,
          transform.position.y + acimaDaPlaca.y,
          transform.position.z + acimaDaPlaca.z,
        );
        slot.titulo.quaternion.set(
          transform.quaternion.x,
          transform.quaternion.y,
          transform.quaternion.z,
          transform.quaternion.w,
        );
        slot.titulo.visible = true;

        const naFrente =
          frame.front !== null &&
          frame.front !== undefined &&
          frame.front === allocation.entityId;
        slot.text.renderOrder = naFrente ? TEXT_FRONT_RENDER_ORDER : TEXT_RENDER_ORDER;
        slot.titulo.renderOrder = slot.text.renderOrder;
        const material = slot.text.material;
        if (material && (material.depthTest === naFrente || material.transparent !== true)) {
          material.depthTest = !naFrente;
          material.transparent = true;
          material.needsUpdate = true;
        }
        slot.text.visible = true;
      }
    },
    scrollExtents() {
      return [...extensoesDeRolagem];
    },
    metrics() {
      return {
        capacity,
        allocatedSlots: slots.filter((slot) => slot.entityId !== null).length,
        createdObjects: objetosCriados,
        // Título visível é objeto desenhando. Contar só o corpo subnotificava a metade
        // da cena que identifica painel à distância.
        visibleObjects: slots.filter((slot) => slot.text.visible).length
          + slots.filter((slot) => slot.titulo.visible).length,
        syncCalls,
        syncByReason: { ...syncByReason },
        allocationOwnerChanges,
        contentKeyChanges,
        corpusAllocated: slots.filter((s) => s.source === 'corpus').length,
        runtimeAllocated: slots.filter((s) => s.source === 'runtime').length,
      };
    },
    dispose() {
      if (descartado) return;
      descartado = true;
      for (const slot of slots) {
        slot.entityId = null;
        // Os dois, porque são dois. O título ficava alocado depois do descarte: em
        // recarga a quente isso é um vazamento por ciclo, e numa sessão longa é
        // memória de GPU que só cresce.
        slot.text.dispose();
        slot.titulo.dispose();
      }
    },
  };
}
