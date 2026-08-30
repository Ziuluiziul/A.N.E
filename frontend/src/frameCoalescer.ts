// Redesenhar uma vez por quadro, e não uma vez por evento.
//
// Um quórum não emite evento: emite rajada. Cada `call_started`, `vote_requested` e
// `vote_received` chega separado no SSE, e cada um disparava uma reconstrução inteira da
// camada viva — projeção, corpos, posições e texto. Oito eventos no mesmo instante
// custavam oito montagens das quais só a última sobrevivia na tela, e é essa a pausa
// até os painéis novos aparecerem: não era o tamanho da cena, era quantas vezes ela foi
// montada para o mesmo quadro.
//
// O estado continua avançando evento a evento — a trilha não pode perder nenhum. O que
// espera pelo quadro é só o desenho.
//
// Módulo próprio porque `main.ts` não tem teste: ele precisa de DOM e de contexto WebGL.
// A regra de coalescência é pura, então ela é testável, e o desenho fica onde já estava.

export interface FrameCoalescer {
  /** Pede um desenho. Vários pedidos no mesmo quadro valem um. */
  request: () => void;
  /** Desiste do desenho pendente, se houver. Usado no encerramento do ciclo. */
  cancel: () => void;
  /** Há desenho pendente? Existe para o teste poder afirmar o estado sem esperar. */
  pending: () => boolean;
}

export function createFrameCoalescer(
  draw: () => void,
  schedule: (callback: () => void) => number = (callback) => requestAnimationFrame(callback),
  unschedule: (handle: number) => void = (handle) => {
    cancelAnimationFrame(handle);
  },
): FrameCoalescer {
  let agendado: number | null = null;
  return {
    request() {
      if (agendado !== null) return;
      agendado = schedule(() => {
        // Zerado **antes** do desenho: se `draw` pedir outro quadro — e ele pode, porque
        // a cena reage ao que acabou de aparecer —, esse pedido é do quadro seguinte, e
        // não um pedido perdido dentro deste.
        agendado = null;
        draw();
      });
    },
    cancel() {
      if (agendado === null) return;
      unschedule(agendado);
      agendado = null;
    },
    pending() {
      return agendado !== null;
    },
  };
}
