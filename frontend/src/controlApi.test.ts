import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  ControlError,
  createControlClient,
  parseControlSnapshot,
  parseCredentialResult,
  type ControlSnapshot,
  type CredentialResult,
} from './controlApi';

afterEach(() => vi.unstubAllGlobals());

function snapshot(): ControlSnapshot {
  return {
    schema_version: 1,
    generated_at: '2026-08-10T12:00:00+00:00',
    providers: [
      {
        id: 'groq',
        name: 'Groq',
        status: 'configurado',
        detail: '',
        key_configured: true,
        key_hint: '1234',
        endpoint_count: 3,
        enabled: true,
        supports_custom_endpoint: false,
        unavailable: {},
      },
    ],
    workers: [
      {
        id: 'verificador-factual',
        role: 'verificador-factual',
        class_name: 'avaliador',
        summary: 'Verifica afirmações.',
        area: 'fontes',
        status: 'espera',
        provider: 'groq',
        model: 'modelo/teste',
        resolved_by: 'auto',
        reasoning: {
          supported: true,
          options: ['low', 'high'],
          value: 'low',
          reason: '',
        },
        concurrency: 1,
        concurrency_min: 0,
        concurrency_max: 4,
        enabled: true,
        running: 0,
        detail: '',
        palette_token: 'D02',
      },
    ],
    operation: {
      auto: true,
      active_workers: 1,
      capacity: 4,
      queued: 0,
      running: 0,
      last_cycle: null,
      next_run: null,
      calls: 2,
      budget: null,
      failures: [],
      last_audit: null,
      unavailable: {},
    },
    notices: [],
  };
}

function credential(): CredentialResult {
  return {
    provider: 'groq',
    key_configured: true,
    key_hint: '1234',
    status: 'disponivel',
    detail: 'provedor respondeu',
  };
}

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('contrato do painel de controle', () => {
  it('reconstrói snapshots e credenciais válidos sem carregar campos extras', () => {
    const rawSnapshot = { ...snapshot(), segredo: 'não atravessa' };
    const rawCredential = { ...credential(), key: 'não atravessa' };

    expect(parseControlSnapshot(rawSnapshot)).toEqual(snapshot());
    expect(parseControlSnapshot(rawSnapshot)).not.toBe(rawSnapshot);
    expect(parseCredentialResult(rawCredential)).toEqual(credential());
    expect(parseCredentialResult(rawCredential)).not.toHaveProperty('key');
  });

  it.each([
    [
      '$.schema_version',
      (raw: Record<string, unknown>) => {
        raw.schema_version = 2;
      },
    ],
    [
      '$.providers[0].status',
      (raw: Record<string, unknown>) => {
        const providers = raw.providers as Array<Record<string, unknown>>;
        providers[0]!.status = 'talvez';
      },
    ],
    [
      '$.workers[0].reasoning.supported',
      (raw: Record<string, unknown>) => {
        const workers = raw.workers as Array<Record<string, unknown>>;
        const reasoning = workers[0]!.reasoning as Record<string, unknown>;
        reasoning.supported = 'sim';
      },
    ],
    [
      '$.operation.running',
      (raw: Record<string, unknown>) => {
        const operation = raw.operation as Record<string, unknown>;
        operation.running = -1;
      },
    ],
  ])('recusa snapshot inválido em %s', (path, mutate) => {
    const raw = structuredClone(snapshot()) as unknown as Record<string, unknown>;
    mutate(raw);
    expect(() => parseControlSnapshot(raw)).toThrow(path);
  });

  it('recusa identidades repetidas e limites de simultaneidade incoerentes', () => {
    const duplicate = structuredClone(snapshot());
    duplicate.providers.push({ ...duplicate.providers[0]! });
    expect(() => parseControlSnapshot(duplicate)).toThrow(/providers.*duplicado/);

    const concurrency = structuredClone(snapshot());
    concurrency.workers[0]!.concurrency = 5;
    expect(() => parseControlSnapshot(concurrency)).toThrow(/\$\.workers\[0\]\.concurrency/);
  });

  it('recusa enum e dica de chave inválidos sem aceitar segredo integral', () => {
    expect(() => parseCredentialResult({ ...credential(), status: 'talvez' })).toThrow(
      /\$\.status/,
    );
    expect(() => parseCredentialResult({ ...credential(), key_hint: 'comprida' })).toThrow(
      /\$\.key_hint/,
    );
  });
});

describe('cliente de controle', () => {
  it('aplica o parser correto nas três leituras/mutações e nas três rotas de credencial', async () => {
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      return Promise.resolve(
        jsonResponse(url.includes('/providers/') ? credential() : snapshot()),
      );
    });
    vi.stubGlobal('fetch', fetchMock);
    const client = createControlClient();

    await expect(client.snapshot()).resolves.toEqual(snapshot());
    await expect(client.setAuto(false)).resolves.toEqual(snapshot());
    await expect(client.patchWorker('verificador-factual', { enabled: false })).resolves.toEqual(
      snapshot(),
    );
    await expect(client.testProvider('groq')).resolves.toEqual(credential());
    await expect(client.putCredential('groq', 'synthetic-test-value')).resolves.toEqual(
      credential(),
    );
    await expect(client.deleteCredential('groq')).resolves.toEqual(credential());
    expect(fetchMock).toHaveBeenCalledTimes(6);
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/api/control/snapshot',
      '/api/control/auto',
      '/api/control/workers/verificador-factual',
      '/api/control/providers/groq/test',
      '/api/control/providers/groq/credential',
      '/api/control/providers/groq/credential',
    ]);
  });

  it('rejeita JSON malformado e contrato divergente como ControlError', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response('{', { status: 200 }))
      .mockResolvedValueOnce(jsonResponse(credential()));
    vi.stubGlobal('fetch', fetchMock);
    const client = createControlClient();

    await expect(client.snapshot()).rejects.toThrow(ControlError);
    await expect(client.snapshot()).rejects.toThrow(/\$\.schema_version/);
  });

  it('preserva o detalhe sanitizado de uma recusa HTTP', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'recusado' }, 409)));

    await expect(createControlClient().snapshot()).rejects.toThrow('recusado');
  });

  it('propaga cancelamento do ciclo sem inventar falha do backend', async () => {
    const controller = new AbortController();
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init.signal?.addEventListener('abort', () => reject(init.signal?.reason));
        }),
      ),
    );
    const reason = new DOMException('fim do ciclo', 'AbortError');
    const request = createControlClient().snapshot({ signal: controller.signal });
    const assertion = expect(request).rejects.toBe(reason);

    controller.abort(reason);

    await assertion;
  });
});
