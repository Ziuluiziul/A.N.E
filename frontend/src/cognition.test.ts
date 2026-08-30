import { describe, expect, it, vi } from 'vitest';

import { selectThoughts, watchCognition, type CognitionFrame } from './cognition';

function quadro(revision: number, extra: Partial<CognitionFrame> = {}): string {
  return JSON.stringify({
    id: `cognition-${String(revision).padStart(20, '0')}`,
    revision,
    timestamp: '2026-08-12T23:00:00.000000+00:00',
    kind: 'reasoning',
    provider: 'groq',
    endpoint: 'qwen/qwen3.6-27b',
    text: `passo ${revision}`,
    ...extra,
  });
}

function fonteFalsa(): {
  listeners: Map<string, (event: Event) => void>;
  urls: string[];
  close: ReturnType<typeof vi.fn>;
} {
  const listeners = new Map<string, (event: Event) => void>();
  const urls: string[] = [];
  const close = vi.fn();
  class EventSourceFake {
    constructor(url: string) {
      urls.push(url);
    }
    addEventListener(kind: string, listener: EventListener): void {
      listeners.set(kind, listener);
    }
    removeEventListener(): void {}
    close(): void {
      close();
    }
  }
  vi.stubGlobal('EventSource', EventSourceFake);
  return { listeners, urls, close };
}

describe('canal cognitivo', () => {
  it('abre no endpoint próprio, e não no da trilha operacional', () => {
    const { urls } = fonteFalsa();
    watchCognition(vi.fn());
    expect(urls).toEqual(['/runtime/cognition']);
  });

  it('entrega o snapshot e depois o quadro vivo, em ordem de revisão', () => {
    const { listeners } = fonteFalsa();
    const lotes: CognitionFrame[][] = [];
    watchCognition((frames) => lotes.push(frames));

    listeners.get('cognition_snapshot')?.(
      new MessageEvent('cognition_snapshot', {
        data: JSON.stringify({ revision: 2, frames: [JSON.parse(quadro(1))] }),
      }),
    );
    listeners.get('reasoning')?.(
      new MessageEvent('reasoning', {
        data: quadro(2, { provider: 'google', endpoint: 'gemini-3.6-flash' }),
      }),
    );

    expect(lotes.at(-1)).toEqual([
      expect.objectContaining({ revision: 1, provider: 'groq' }),
      expect.objectContaining({ revision: 2, provider: 'google' }),
    ]);
  });

  it('guarda um quadro por modelo: o painel mostra o agora, não o histórico', () => {
    const { listeners } = fonteFalsa();
    const lotes: CognitionFrame[][] = [];
    watchCognition((frames) => lotes.push(frames));

    listeners.get('reasoning')?.(new MessageEvent('reasoning', { data: quadro(1) }));
    listeners.get('reasoning')?.(new MessageEvent('reasoning', { data: quadro(2) }));

    expect(lotes.at(-1)).toHaveLength(1);
    expect(lotes.at(-1)?.[0]?.text).toBe('passo 2');
  });

  it('ignora quadro que chega atrasado, para o texto não andar para trás', () => {
    const { listeners } = fonteFalsa();
    const lotes: CognitionFrame[][] = [];
    watchCognition((frames) => lotes.push(frames));

    listeners.get('reasoning')?.(new MessageEvent('reasoning', { data: quadro(5) }));
    listeners.get('reasoning')?.(new MessageEvent('reasoning', { data: quadro(4) }));

    expect(lotes.at(-1)?.[0]?.revision).toBe(5);
  });

  it('recusa payload sem os campos que identificam o emissor', () => {
    const { listeners } = fonteFalsa();
    const aoReceber = vi.fn();
    watchCognition(aoReceber);

    for (const invalido of [
      '{"revision":1,"kind":"reasoning","provider":"","endpoint":"x","text":"a"}',
      '{"revision":0,"kind":"reasoning","provider":"groq","endpoint":"x","text":"a"}',
      '{"revision":1,"kind":"palpite","provider":"groq","endpoint":"x","text":"a"}',
      'isto não é json',
    ]) {
      listeners.get('reasoning')?.(new MessageEvent('reasoning', { data: invalido }));
    }

    expect(aoReceber).not.toHaveBeenCalled();
  });

  it('não deixa o delta de saída apagar o raciocínio do mesmo modelo', () => {
    const { listeners } = fonteFalsa();
    const lotes: CognitionFrame[][] = [];
    watchCognition((frames) => lotes.push(frames));

    listeners.get('reasoning')?.(new MessageEvent('reasoning', { data: quadro(1) }));
    listeners.get('output-delta')?.(
      new MessageEvent('output-delta', { data: quadro(2, { kind: 'output-delta', text: '{' }) }),
    );

    expect(lotes.at(-1)?.[0]?.kind).toBe('reasoning');
    expect(lotes.at(-1)?.[0]?.text).toBe('passo 1');
  });

  it('mostra o delta quando o modelo não emite raciocínio — o proponente não fica mudo', () => {
    const { listeners } = fonteFalsa();
    const lotes: CognitionFrame[][] = [];
    watchCognition((frames) => lotes.push(frames));

    listeners.get('output-delta')?.(
      new MessageEvent('output-delta', {
        data: quadro(1, { kind: 'output-delta', text: '{"proposal_id"' }),
      }),
    );

    expect(lotes.at(-1)?.[0]?.kind).toBe('output-delta');
    expect(selectThoughts(lotes.at(-1) ?? []).get('groq/qwen/qwen3.6-27b')).toContain(
      'proposal_id',
    );
  });

  it('o final limpa o pensamento, para o cartão não congelar na última frase', () => {
    const { listeners } = fonteFalsa();
    const lotes: CognitionFrame[][] = [];
    watchCognition((frames) => lotes.push(frames));

    listeners.get('reasoning')?.(new MessageEvent('reasoning', { data: quadro(1) }));
    listeners.get('final')?.(
      new MessageEvent('final', { data: quadro(2, { kind: 'final', text: '' }) }),
    );

    expect(lotes.at(-1)).toEqual([]);
    expect(selectThoughts(lotes.at(-1) ?? []).size).toBe(0);
  });

  it('fecha o transporte quando quem escuta desiste', () => {
    const { close } = fonteFalsa();
    const parar = watchCognition(vi.fn());
    parar();
    expect(close).toHaveBeenCalled();
  });
});
