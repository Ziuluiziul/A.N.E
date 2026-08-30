import { afterEach, describe, expect, it, vi } from 'vitest';

import type { LayoutMap } from './layout';
import {
  LAYOUT_ALGORITHM_VERSION,
  loadOperationalSlots,
  loadPositions,
  saveOperationalSlots,
  savePositions,
} from './layoutStore';
import { OPERATIONAL_LAYOUT_VERSION } from './operationalLayout';

const FINGERPRINT = 'a'.repeat(64);

function response(payload: unknown, ok = true, status = ok ? 200 : 500): Response {
  return {
    ok,
    status,
    json: async () => payload,
  } as Response;
}

function mockFetch(payload: unknown, ok = true, status?: number): ReturnType<typeof vi.fn> {
  const mocked = vi.fn().mockResolvedValue(response(payload, ok, status));
  vi.stubGlobal('fetch', mocked);
  return mocked;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('contrato da memória espacial do corpus', () => {
  it('mantém o fingerprint puro no path e envia a versão separada', async () => {
    const fetch = mockFetch({
      schemaVersion: 2,
      corpusFingerprint: FINGERPRINT,
      algorithmVersion: LAYOUT_ALGORITHM_VERSION,
      positions: { Nota: { x: 1, y: 2, z: 3, pinned: false } },
    });

    const positions = await loadPositions(FINGERPRINT);

    expect(fetch).toHaveBeenCalledWith(
      `/layout/${FINGERPRINT}?algorithmVersion=${LAYOUT_ALGORITHM_VERSION}`,
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(positions).toEqual(new Map([['Nota', { x: 1, y: 2, z: 3 }]]));
  });

  it('não reaproveita resposta de outro corpus ou algoritmo', async () => {
    mockFetch({
      corpusFingerprint: FINGERPRINT,
      algorithmVersion: 'obsoleto',
      positions: { Nota: { x: 1, y: 2, z: 3 } },
    });
    expect(await loadPositions(FINGERPRINT)).toEqual(new Map());
  });

  it('grava envelope versionado e somente as identidades autorizadas', async () => {
    const fetch = mockFetch({ stored: 1 });
    const positions: LayoutMap = new Map([
      ['Nota', { x: 1, y: 2, z: 3 }],
      ['operacao', { x: 9, y: 8, z: 7 }],
    ]);

    expect(await savePositions(FINGERPRINT, positions, new Set(['Nota']))).toBe('stored');
    expect(fetch).toHaveBeenCalledOnce();
    const [url, init] = fetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`/layout/${FINGERPRINT}`);
    expect(init.method).toBe('PUT');
    expect(JSON.parse(String(init.body))).toEqual({
      algorithmVersion: LAYOUT_ALGORITHM_VERSION,
      positions: { Nota: { x: 1, y: 2, z: 3 } },
    });
  });

  it('distingue revisão obsoleta de backend ausente', async () => {
    mockFetch({ detail: 'stale' }, false, 409);
    expect(await savePositions(FINGERPRINT, new Map())).toBe('stale-fingerprint');

    const rejected = vi.fn().mockRejectedValue(new TypeError('offline'));
    vi.stubGlobal('fetch', rejected);
    expect(await savePositions(FINGERPRINT, new Map())).toBe('backend-unavailable');
  });
});

describe('contrato próprio dos ordinais operacionais', () => {
  it('lê panelId para ordinal sem fingir coordenada x', async () => {
    const fetch = mockFetch({
      schemaVersion: 1,
      algorithmVersion: OPERATIONAL_LAYOUT_VERSION,
      slots: { painelA: 3, painelB: 0 },
    });

    expect(await loadOperationalSlots()).toEqual(
      new Map([
        ['painelA', 3],
        ['painelB', 0],
      ]),
    );
    expect(fetch).toHaveBeenCalledWith(
      `/operational-layout/${OPERATIONAL_LAYOUT_VERSION}`,
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it('grava slots no namespace operacional', async () => {
    const fetch = mockFetch({
      algorithmVersion: OPERATIONAL_LAYOUT_VERSION,
      slots: { painelA: 3 },
    });

    expect(await saveOperationalSlots(new Map([['painelA', 3]]))).toEqual({
      status: 'stored',
      slots: new Map([['painelA', 3]]),
    });
    const [url, init] = fetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`/operational-layout/${OPERATIONAL_LAYOUT_VERSION}`);
    expect(JSON.parse(String(init.body))).toEqual({ slots: { painelA: 3 } });
  });

  it('recusa o snapshot inteiro se o backend duplicar ordinal', async () => {
    mockFetch({
      algorithmVersion: OPERATIONAL_LAYOUT_VERSION,
      slots: { painelA: 0, painelB: 0 },
    });

    expect(await loadOperationalSlots()).toEqual(new Map());
  });

  it('recusa o snapshot inteiro se algum ordinal for inválido', async () => {
    mockFetch({
      algorithmVersion: OPERATIONAL_LAYOUT_VERSION,
      slots: { painelA: 0, painelB: -1 },
    });

    expect(await loadOperationalSlots()).toEqual(new Map());
  });
});
