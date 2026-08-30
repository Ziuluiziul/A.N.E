import { readFileSync } from 'node:fs';

import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  BACKEND_SOURCE,
  ContractError,
  isBackendProjectionOrigin,
  loadProjection,
  parseCorpusEventPayload,
  parseProjection,
  shouldReplaceStaticProjection,
  shouldReloadProjection,
  watchProjection,
} from './contract';
import { edge, node, projectionFixture } from './fixture';

afterEach(() => vi.unstubAllGlobals());

describe('revisão viva da projeção', () => {
  const atual = 'a'.repeat(64);

  it('recarrega somente para outro fingerprint SHA-256 válido', () => {
    expect(shouldReloadProjection(atual, 'b'.repeat(64))).toBe(true);
    expect(shouldReloadProjection(atual, atual)).toBe(false);
    expect(shouldReloadProjection(atual, 'b'.repeat(63))).toBe(false);
    expect(shouldReloadProjection(atual, 'G'.repeat(64))).toBe(false);
    expect(shouldReloadProjection(atual, null)).toBe(false);
  });

  it('só considera viva a origem exata do backend', () => {
    expect(BACKEND_SOURCE).toBe('/corpus/projection');
    expect(isBackendProjectionOrigin(BACKEND_SOURCE)).toBe(true);
    expect(isBackendProjectionOrigin('/projection.json')).toBe(false);
    expect(isBackendProjectionOrigin(`${BACKEND_SOURCE}?cache=1`)).toBe(false);
  });

  it('troca o snapshot estático somente após um current vivo válido', () => {
    expect(shouldReplaceStaticProjection('/projection.json', null)).toBe(false);
    expect(shouldReplaceStaticProjection('/projection.json', 'online')).toBe(false);
    expect(shouldReplaceStaticProjection('/projection.json', atual)).toBe(true);
    expect(shouldReplaceStaticProjection(BACKEND_SOURCE, atual)).toBe(false);
  });

  it('confirma recuperação só com evento current válido, mesmo sem revisão nova', () => {
    const listeners = new Map<string, (event: Event) => void>();
    class EventSourceFake {
      addEventListener(kind: string, listener: EventListener): void {
        listeners.set(kind, listener);
      }
      close(): void {}
    }
    vi.stubGlobal('EventSource', EventSourceFake);
    const onChange = vi.fn();
    const onError = vi.fn();
    const onCurrent = vi.fn();
    watchProjection(atual, onChange, onError, { onCurrent });

    listeners.get('current')?.(
      new MessageEvent('current', {
        data: JSON.stringify({ fingerprint: atual, revision: 2, detail: null }),
      }),
    );

    expect(onCurrent).toHaveBeenCalledOnce();
    expect(onCurrent).toHaveBeenCalledWith(atual);
    expect(onChange).not.toHaveBeenCalled();

    listeners.get('current')?.(
      new MessageEvent('current', {
        data: JSON.stringify({ fingerprint: null, revision: 3, detail: 'indisponível' }),
      }),
    );

    expect(onCurrent).toHaveBeenCalledOnce();
    expect(onChange).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledWith(expect.stringContaining('evento current inválido'));
  });

  it('não perde revisão quando um erro posterior compacta o evento changed', () => {
    const listeners = new Map<string, (event: Event) => void>();
    class EventSourceFake {
      addEventListener(kind: string, listener: EventListener): void {
        listeners.set(kind, listener);
      }
      close(): void {}
    }
    vi.stubGlobal('EventSource', EventSourceFake);
    const onChange = vi.fn();
    const onError = vi.fn();
    watchProjection(atual, onChange, onError);

    listeners.get('error')?.(
      new MessageEvent('error', {
        data: JSON.stringify({
          fingerprint: 'b'.repeat(64),
          revision: 2,
          detail: 'memória indisponível',
        }),
      }),
    );

    expect(onChange).toHaveBeenCalledOnce();
    expect(onChange).toHaveBeenCalledWith('b'.repeat(64));
    expect(onError).toHaveBeenCalledWith('memória indisponível');
  });

  it('propaga recuperação sem recarregar fingerprint idêntico', () => {
    const listeners = new Map<string, (event: Event) => void>();
    class EventSourceFake {
      addEventListener(kind: string, listener: EventListener): void {
        listeners.set(kind, listener);
      }
      close(): void {}
    }
    vi.stubGlobal('EventSource', EventSourceFake);
    const onChange = vi.fn();
    const onStatus = vi.fn();
    watchProjection(atual, onChange, onStatus);

    listeners.get('recovered')?.(
      new MessageEvent('recovered', {
        data: JSON.stringify({
          fingerprint: atual,
          revision: 1,
          detail: 'corpus válido novamente',
        }),
      }),
    );

    expect(onChange).not.toHaveBeenCalled();
    expect(onStatus).toHaveBeenCalledWith('corpus válido novamente');
  });

  it('diagnostica payload SSE inválido sem pedir recarga', () => {
    const listeners = new Map<string, (event: Event) => void>();
    class EventSourceFake {
      addEventListener(kind: string, listener: EventListener): void {
        listeners.set(kind, listener);
      }
      close(): void {}
    }
    vi.stubGlobal('EventSource', EventSourceFake);
    const onChange = vi.fn();
    const onError = vi.fn();
    watchProjection(atual, onChange, onError);

    listeners.get('changed')?.(
      new MessageEvent('changed', {
        data: JSON.stringify({ fingerprint: 'não-é-sha', revision: 2, detail: null }),
      }),
    );

    expect(onChange).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledWith(expect.stringContaining('$.fingerprint'));
  });

  it('valida todos os campos do envelope SSE', () => {
    expect(
      parseCorpusEventPayload({ fingerprint: atual, revision: 4, detail: null }),
    ).toEqual({ fingerprint: atual, revision: 4, detail: null });
    expect(() =>
      parseCorpusEventPayload({ fingerprint: atual, revision: 1.5, detail: null }),
    ).toThrow(/\$\.revision/);
  });
});

describe('parser da projeção', () => {
  it('aceita o artefato real atualmente publicado pelo frontend', () => {
    const payload = JSON.parse(
      readFileSync(new URL('../public/projection.json', import.meta.url), 'utf8'),
    ) as unknown;
    const parsed = parseProjection(payload);

    expect(parsed.nodes).toHaveLength(parsed.meta.counts.notes);
    expect(parsed.meta.corpusFingerprint).toMatch(/^[0-9a-f]{64}$/);
  });

  it('reconstrói uma fixture válida e descarta campos alheios ao contrato', () => {
    const raw = { ...projectionFixture(), segredoAcidental: 'não atravessa' };
    const parsed = parseProjection(raw);

    expect(parsed).not.toBe(raw);
    expect(parsed.nodes[0]).not.toBe(raw.nodes[0]);
    expect(parsed).not.toHaveProperty('segredoAcidental');
  });

  it.each([
    ['$.nodes', (raw: Record<string, unknown>) => (raw.nodes = null)],
    [
      '$.nodes[0].kind',
      (raw: Record<string, unknown>) => {
        const nodes = raw.nodes as Array<Record<string, unknown>>;
        nodes[0]!.kind = 'coisa';
      },
    ],
    [
      '$.edges[0].weight',
      (raw: Record<string, unknown>) => {
        const edges = raw.edges as Array<Record<string, unknown>>;
        edges[0]!.weight = Number.NaN;
      },
    ],
    [
      '$.meta.corpusFingerprint',
      (raw: Record<string, unknown>) => {
        const meta = raw.meta as Record<string, unknown>;
        meta.corpusFingerprint = 'f'.repeat(63);
      },
    ],
    [
      '$.nodes[0].epistemicStatus',
      (raw: Record<string, unknown>) => {
        const nodes = raw.nodes as Array<Record<string, unknown>>;
        nodes[0]!.epistemicStatus = 'banana';
      },
    ],
    [
      '$.nodes[0].claims[0].status',
      (raw: Record<string, unknown>) => {
        const nodes = raw.nodes as Array<Record<string, unknown>>;
        nodes[0]!.claimCount = 1;
        nodes[0]!.claims = [
          { id: 'CLM-TESTE-STATUS-001', statement: 'teste', status: 'banana', evidence: null },
        ];
      },
    ],
  ])('recusa forma inválida em %s', (path, mutate) => {
    const raw = structuredClone(projectionFixture()) as unknown as Record<string, unknown>;
    mutate(raw);
    expect(() => parseProjection(raw)).toThrow(path);
  });

  it('recusa identidades de nó, claim e domínio duplicadas', () => {
    const duplicateNode = structuredClone(projectionFixture());
    duplicateNode.nodes[1]!.id = duplicateNode.nodes[0]!.id;
    expect(() => parseProjection(duplicateNode)).toThrow(/\$\.nodes.*duplicado/);

    const duplicateClaim = structuredClone(projectionFixture());
    for (const node of duplicateClaim.nodes.slice(0, 2)) {
      node.claimCount = 1;
      node.claims = [
        { id: 'CLM-TESTE-DUP-001', statement: 'teste', status: 'open', evidence: null },
      ];
    }
    expect(() => parseProjection(duplicateClaim)).toThrow(/claims.*duplicado/);

    const duplicateDomain = structuredClone(projectionFixture());
    duplicateDomain.meta.domains[1]!.id = duplicateDomain.meta.domains[0]!.id;
    expect(() => parseProjection(duplicateDomain)).toThrow(/domains.*duplicado/);
  });

  it('recusa divergência entre tipo e camada e contagem declarada', () => {
    const wrongLayer = structuredClone(projectionFixture());
    wrongLayer.nodes[0]!.layer = 'operational';
    expect(() => parseProjection(wrongLayer)).toThrow(/\$\.nodes\[0\]\.layer/);

    const wrongCount = structuredClone(projectionFixture());
    wrongCount.meta.counts.notes += 1;
    expect(() => parseProjection(wrongCount)).toThrow(/\$\.meta\.counts\.notes/);
  });

  it('recusa metadado operacional desconhecido ou mal tipado', () => {
    const raw = structuredClone(projectionFixture()) as unknown as {
      nodes: Array<Record<string, unknown>>;
    };
    raw.nodes[0]!.operational = { modelCount: 'muitos' };
    expect(() => parseProjection(raw)).toThrow(/\$\.nodes\[0\]\.operational\.modelCount/);

    raw.nodes[0]!.operational = { surpresa: true };
    expect(() => parseProjection(raw)).toThrow(/surpresa/);
  });

  it('aceita e reconstrói a camada operacional declarada', () => {
    const raw = projectionFixture();
    const panel = node('op/quorum/painel-teste/panel', {
      kind: 'quorum-panel',
      layer: 'operational',
      path: null,
      canonicalState: 'temporary',
      domainId: 'operacional/quorum',
      domainLabel: 'quórum',
      claimCount: 0,
      operational: { panelId: 'painel-teste', runtimeRevision: 4 },
    });
    raw.nodes.push(panel);
    raw.edges.push(
      edge(panel.id, raw.nodes[0]!.id, 'operational', 'operational', {
        matchedBy: 'runtime',
      }),
    );
    raw.meta.operationalSource = 'quorum';
    raw.meta.counts.operationalNodes = 1;

    const parsed = parseProjection(raw);

    expect(parsed.nodes.at(-1)?.operational).toEqual({
      panelId: 'painel-teste',
      runtimeRevision: 4,
    });
  });

  it('não usa o fallback estático quando o backend respondeu um contrato corrompido', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ meta: {}, nodes: [], edges: [] }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(loadProjection()).rejects.toBeInstanceOf(ContractError);
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it('usa o artefato estático após falha de transporte do backend', async () => {
    const staticProjection = projectionFixture();
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('offline'))
      .mockResolvedValueOnce({ ok: true, json: async () => staticProjection });
    vi.stubGlobal('fetch', fetchMock);

    await expect(loadProjection()).resolves.toEqual({
      projection: parseProjection(staticProjection),
      origin: '/projection.json',
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('não transforma cancelamento do ciclo em fallback estático', async () => {
    const controller = new AbortController();
    const fetchMock = vi.fn((_url: string, init: RequestInit) =>
      new Promise<Response>((_resolve, reject) => {
        init.signal?.addEventListener('abort', () => reject(init.signal?.reason));
      }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const reason = new DOMException('fim do ciclo', 'AbortError');
    const request = loadProjection(controller.signal);
    const assertion = expect(request).rejects.toBe(reason);

    controller.abort(reason);

    await assertion;
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
