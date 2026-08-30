import { describe, expect, it, vi } from 'vitest';

import { createFrameCoalescer } from './frameCoalescer';

function relogioDeQuadros(): {
  schedule: (callback: () => void) => number;
  unschedule: (handle: number) => void;
  avancar: () => void;
  pendentes: () => number;
} {
  const fila = new Map<number, () => void>();
  let proximo = 0;
  return {
    schedule(callback) {
      proximo += 1;
      fila.set(proximo, callback);
      return proximo;
    },
    unschedule(handle) {
      fila.delete(handle);
    },
    avancar() {
      const agora = [...fila.entries()];
      fila.clear();
      for (const [, callback] of agora) callback();
    },
    pendentes: () => fila.size,
  };
}

describe('o desenho espera pelo quadro', () => {
  it('uma rajada de eventos custa um desenho, não oito', () => {
    const relogio = relogioDeQuadros();
    const desenhar = vi.fn();
    const coalescer = createFrameCoalescer(desenhar, relogio.schedule, relogio.unschedule);

    for (let i = 0; i < 8; i += 1) coalescer.request();
    expect(desenhar).not.toHaveBeenCalled();
    expect(relogio.pendentes()).toBe(1);

    relogio.avancar();
    expect(desenhar).toHaveBeenCalledTimes(1);
  });

  it('o quadro seguinte volta a desenhar: coalescer não é engolir', () => {
    const relogio = relogioDeQuadros();
    const desenhar = vi.fn();
    const coalescer = createFrameCoalescer(desenhar, relogio.schedule, relogio.unschedule);

    coalescer.request();
    relogio.avancar();
    coalescer.request();
    relogio.avancar();

    expect(desenhar).toHaveBeenCalledTimes(2);
  });

  it('o pedido feito de dentro do desenho vale para o quadro seguinte', () => {
    // A cena reage ao que acabou de aparecer, e por isso `draw` pode pedir outro quadro.
    // Se a marca fosse zerada depois do desenho, esse pedido cairia no vazio e a cena
    // ficaria com uma atualização pendente que nunca chega.
    const relogio = relogioDeQuadros();
    let reentrou = false;
    const coalescer = createFrameCoalescer(
      () => {
        if (reentrou) return;
        reentrou = true;
        coalescer.request();
      },
      relogio.schedule,
      relogio.unschedule,
    );

    coalescer.request();
    relogio.avancar();

    expect(coalescer.pending()).toBe(true);
  });

  it('cancelar desiste do desenho pendente e libera o próximo pedido', () => {
    const relogio = relogioDeQuadros();
    const desenhar = vi.fn();
    const coalescer = createFrameCoalescer(desenhar, relogio.schedule, relogio.unschedule);

    coalescer.request();
    coalescer.cancel();
    relogio.avancar();
    expect(desenhar).not.toHaveBeenCalled();
    expect(coalescer.pending()).toBe(false);

    coalescer.request();
    relogio.avancar();
    expect(desenhar).toHaveBeenCalledTimes(1);
  });
});
