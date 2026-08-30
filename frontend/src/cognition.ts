// Canal efêmero do raciocínio do provedor. Não passa pela trilha operacional.

import { openBackendEvents } from './transport';

export const COGNITION_KINDS = [
  'reasoning',
  'reasoning-summary',
  'output-delta',
  'final',
  'progress',
  'tool-call',
  'tool-result',
] as const;

export type CognitionKind = (typeof COGNITION_KINDS)[number];

const THOUGHT_KIND_RANK: Partial<Record<CognitionKind, number>> = {
  'output-delta': 0,
  'reasoning-summary': 1,
  reasoning: 2,
};

export interface CognitionFrame {
  revision: number;
  kind: CognitionKind;
  provider: string;
  endpoint: string;
  task?: string;
  text: string;
  timestamp: string;
}

const BACKEND_COGNITION = '/runtime/cognition';

/**
 * O texto que a cena deve mostrar agora, por `provedor/endpoint`.
 *
 * O canal mistura raciocínio, tokens de saída e o `final` que fecha a chamada. Sem
 * esta escolha, o `output-delta` do proponente — o JSON do patch — substituía o
 * pensamento e o filtro da UI apagava os dois: o trabalho acontecia, e o painel
 * ficava mudo. Raciocínio vence resumo, resumo vence delta; `final` limpa.
 */
export function selectThoughts(frames: readonly CognitionFrame[]): Map<string, string> {
  const escolhidos = new Map<string, CognitionFrame>();
  for (const frame of frames) {
    const key = `${frame.provider}/${frame.endpoint}`;
    if (frame.kind === 'final') {
      escolhidos.delete(key);
      continue;
    }
    const rank = THOUGHT_KIND_RANK[frame.kind];
    if (rank === undefined) continue;
    const texto = frame.text.trim();
    if (!texto) continue;
    const previous = escolhidos.get(key);
    const previousRank = previous ? THOUGHT_KIND_RANK[previous.kind] : undefined;
    if (previous && previousRank !== undefined && previousRank > rank) continue;
    escolhidos.set(key, frame);
  }
  const thoughts = new Map<string, string>();
  for (const [key, frame] of escolhidos) thoughts.set(key, frame.text.trim());
  return thoughts;
}

function payloadOf(event: Event): unknown {
  if (!(event instanceof MessageEvent) || typeof event.data !== 'string') return null;
  try {
    return JSON.parse(event.data) as unknown;
  } catch {
    return null;
  }
}

function parseFrame(raw: unknown): CognitionFrame | null {
  if (!raw || typeof raw !== 'object') return null;
  const source = raw as Record<string, unknown>;
  if (typeof source.revision !== 'number' || source.revision < 1) return null;
  if (!COGNITION_KINDS.includes(source.kind as CognitionKind)) return null;
  if (typeof source.provider !== 'string' || !source.provider) return null;
  if (typeof source.endpoint !== 'string' || !source.endpoint) return null;
  return {
    revision: source.revision,
    kind: source.kind as CognitionKind,
    provider: source.provider,
    endpoint: source.endpoint,
    task: typeof source.task === 'string' ? source.task : undefined,
    text: typeof source.text === 'string' ? source.text : '',
    timestamp: typeof source.timestamp === 'string' ? source.timestamp : '',
  };
}

export function watchCognition(
  onFrames: (frames: CognitionFrame[]) => void,
  options: { signal?: AbortSignal } = {},
): () => void {
  if (typeof EventSource === 'undefined') return () => undefined;
  const events = openBackendEvents(BACKEND_COGNITION, { signal: options.signal });
  const source = events.source;
  const latest = new Map<string, CognitionFrame>();

  const publish = (): void => {
    onFrames([...latest.values()].sort((a, b) => a.revision - b.revision));
  };

  const accept = (frame: CognitionFrame | null): void => {
    if (!frame) return;
    const key = `${frame.provider}/${frame.endpoint}`;
    if (frame.kind === 'final') {
      latest.delete(key);
      publish();
      return;
    }
    const previous = latest.get(key);
    if (previous && previous.revision > frame.revision) return;
    const previousRank = previous ? THOUGHT_KIND_RANK[previous.kind] : undefined;
    const nextRank = THOUGHT_KIND_RANK[frame.kind];
    if (previous && previousRank !== undefined && nextRank !== undefined && previousRank > nextRank) {
      return;
    }
    latest.set(key, frame);
    publish();
  };

  source.addEventListener('cognition_snapshot', (event) => {
    const payload = payloadOf(event);
    if (!payload || typeof payload !== 'object') return;
    const frames = (payload as { frames?: unknown }).frames;
    if (!Array.isArray(frames)) return;
    latest.clear();
    for (const item of frames) accept(parseFrame(item));
    publish();
  });
  for (const kind of COGNITION_KINDS) {
    source.addEventListener(kind, (event) => {
      accept(parseFrame(payloadOf(event)));
    });
  }
  return () => {
    events.close();
    latest.clear();
  };
}
