// O harness de captura: a cena real, dirigida por um roteiro, com os invariantes
// conferidos enquanto ela roda.
//
// **Por que ele existe.** Os três piores defeitos deste ciclo — texto escondido atrás
// da própria placa, orçamento estimado numa fonte que não era a desenhada, e título
// impresso duas vezes — passaram por 189 testes verdes sem que um só falhasse. Nenhum
// deles era testável fora da GPU: dependiam de profundidade real, de medição real do
// troika e de composição real. Capturar à mão descobre isso uma vez; um roteiro
// descobre toda vez.
//
// **Por que ele não é um teste.** Ele precisa de WebGL, de um servidor de
// desenvolvimento e de tempo de parede para o troika gerar glifos. Fingir que isso
// cabe no `vitest` seria transformar o gate determinístico em algo intermitente. Ele
// roda sob demanda, a partir do console, e é carregado apenas em desenvolvimento.
//
// Ele não decide se a cena está bonita — isso continua sendo julgamento humano sobre
// as capturas. O que ele decide é se os invariantes mecânicos sobreviveram ao passeio.

import type { AtlasHandle } from './atlas';
import type { Projection, ProjectionNode } from './contract';
import { TEXT_OBJECTS_PER_SLOT } from './panelTextRenderer';
import { TOTAL_TEXT_SLOTS } from './textPool';

/** O que o harness grava por passo. */
export interface HarnessStep {
  name: string;
  /** O que este passo existe para mostrar, em uma frase. */
  purpose: string;
  selected: string | null;
  drawCalls: number;
  triangles: number;
  allocatedSlots: number;
  visibleObjects: number;
  capture: string | null;
}

export interface HarnessReport {
  steps: HarnessStep[];
  /** Invariantes mecânicos. Falso em qualquer um é defeito, não questão de gosto. */
  invariants: {
    /** Exatamente 64 objetos `Text`, do início ao fim. */
    textObjectsConstant: boolean;
    /** Nenhum objeto novo nasceu durante o passeio. */
    noTextCreatedDuringRun: boolean;
    /** Quadro parado não sincroniza: nada é alocado por frame. */
    idleFrameDoesNotSync: boolean;
    /** Toda captura pedida foi gravada. */
    allCapturesWritten: boolean;
  };
  failures: string[];
}

export type CaptureFn = (name: string, width?: number, height?: number) => Promise<unknown>;

interface Roteiro {
  name: string;
  purpose: string;
  act: () => void;
}

/** Espera de parede: o troika gera glifos fora do quadro, e a captura precisa deles. */
function esperar(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function primeiroMoc(projection: Projection): ProjectionNode | undefined {
  return projection.nodes.find((node) => node.kind === 'moc');
}

function notaComClaims(projection: Projection): ProjectionNode | undefined {
  return (
    projection.nodes.find((node) => node.kind === 'note' && node.claimCount > 2) ??
    projection.nodes.find((node) => node.kind === 'note')
  );
}

/**
 * Um passeio pela cena, com captura e verificação a cada parada.
 *
 * A sequência é deliberada: global, âncora, conteúdo, troca de seleção, volta ao
 * global. Ela exercita justamente as transições em que o pool troca de dono e o
 * regime de relações muda — que é onde a cintilação e o texto órfão aparecem.
 */
export function createCaptureHarness(
  atlas: AtlasHandle,
  projection: Projection,
  capture: CaptureFn,
  prefix = 'atlas',
): { run: () => Promise<HarnessReport> } {
  return {
    async run() {
      const steps: HarnessStep[] = [];
      const failures: string[] = [];
      const inicio = atlas.textMetrics();

      const moc = primeiroMoc(projection);
      const nota = notaComClaims(projection);
      const roteiro: Roteiro[] = [
        {
          name: 'global',
          purpose: 'A visão de conjunto não pode ser uma massa uniforme de arestas.',
          act: () => atlas.toggle('global'),
        },
      ];
      if (moc) {
        roteiro.push({
          name: 'moc-expandido',
          purpose: 'A âncora expande no próprio lugar, com a espinha do território.',
          act: () => atlas.focusOn(moc.id),
        });
      }
      if (nota) {
        roteiro.push({
          name: 'nota-expandida',
          purpose: 'O conteúdo estruturado completo cabe na placa que cresceu.',
          act: () => atlas.focusOn(nota.id),
        });
        const vizinho = projection.edges.find(
          (edge) => edge.kind !== 'aggregated' && edge.source === nota.id,
        )?.target;
        if (vizinho) {
          roteiro.push({
            name: 'troca-de-selecao',
            purpose: 'Trocar de nó recolhe o anterior e não deixa texto órfão.',
            act: () => atlas.focusOn(vizinho),
          });
        }
      }
      roteiro.push({
        name: 'recolhido',
        purpose: 'Sem seleção, a cena volta ao regime global sem resíduo de foco.',
        act: () => atlas.select(null),
      });

      for (const passo of roteiro) {
        passo.act();
        // Dois quadros e uma espera: o primeiro aplica a decisão, a espera deixa o
        // troika medir, o segundo desenha o que foi medido.
        atlas.renderOnce();
        await esperar(700);
        const desenho = atlas.renderOnce();
        const nome = `${prefix}-${passo.name}`;
        let gravou: string | null = null;
        try {
          const resposta = (await capture(nome, 1920, 1080)) as { written?: string };
          gravou = typeof resposta?.written === 'string' ? resposta.written : null;
        } catch (erro) {
          failures.push(`captura de ${nome} falhou: ${String(erro)}`);
        }
        if (!gravou) failures.push(`captura de ${nome} não foi gravada`);
        const metricas = atlas.textMetrics();
        steps.push({
          name: passo.name,
          purpose: passo.purpose,
          selected: atlas.state.selected,
          drawCalls: desenho.drawCalls,
          triangles: desenho.triangles,
          allocatedSlots: metricas.allocatedSlots,
          visibleObjects: metricas.visibleObjects,
          capture: gravou,
        });
      }

      // Quadro parado: nada mudou, então nada pode sincronizar.
      const antesParado = atlas.textMetrics().syncCalls;
      await esperar(1200);
      const fim = atlas.textMetrics();

      const invariants = {
        // Dois objetos por vaga: corpo e título. O invariante media `TOTAL_TEXT_SLOTS` e
        // por isso passava enquanto a metade dos objetos escapava da contagem.
        textObjectsConstant:
          fim.createdObjects === TOTAL_TEXT_SLOTS * TEXT_OBJECTS_PER_SLOT
          && fim.capacity === TOTAL_TEXT_SLOTS,
        noTextCreatedDuringRun: fim.createdObjects === inicio.createdObjects,
        idleFrameDoesNotSync: fim.syncCalls === antesParado,
        allCapturesWritten: steps.every((passo) => passo.capture !== null),
      };
      for (const [nome, valor] of Object.entries(invariants)) {
        if (!valor) failures.push(`invariante violado: ${nome}`);
      }
      return { steps, invariants, failures };
    },
  };
}
