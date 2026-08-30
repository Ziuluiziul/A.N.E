// O contrato do painel de controle e o transporte que o busca.
//
// **Uma leitura, não cinco.** O backend serve um snapshot agregado, e é ele que o dock
// desenha. Montar a verdade a partir de várias respostas produziria vários instantes
// diferentes: um trabalhador ligado a um endpoint que a resposta seguinte já não lista.
//
// **Mutação devolve o snapshot novo.** Nenhuma rota de mutação responde "ok": todas
// devolvem a leitura já atualizada. Sem isso o frontend teria de adivinhar o efeito do
// que pediu, e adivinhar é como nasce a divergência entre o que a tela mostra e o que
// o sistema faz.
//
// **A chave só trafega em uma direção.** Ela sobe no corpo de `PUT` e de `POST /test`,
// e nunca desce: a resposta tem estado e, quando muito, quatro caracteres finais. Este
// módulo não guarda o valor em variável de módulo, não o registra e não o repete.

import {
  PayloadError,
  payloadArray,
  payloadBoolean,
  payloadEnum,
  payloadNullableString,
  payloadNumber,
  payloadRecord,
  payloadString,
  payloadText,
  payloadUnique,
} from './payload';
import {
  BackendTimeoutError,
  MUTATION_FETCH_TIMEOUT_MS,
  PROVIDER_TEST_TIMEOUT_MS,
  backendFetch,
} from './transport';

const BASE = '/api/control';

export type ProviderStatus =
  | 'configurado'
  | 'ausente'
  | 'invalido'
  | 'disponivel'
  | 'erro';

export type WorkerStatus = 'ativo' | 'inativo' | 'espera' | 'erro' | 'desconhecido';

export interface ReasoningSupport {
  supported: boolean;
  options: string[];
  value: string | null;
  reason: string;
}

export interface ProviderState {
  id: string;
  name: string;
  status: ProviderStatus;
  detail: string;
  key_configured: boolean;
  key_hint: string | null;
  endpoint_count: number | null;
  enabled: boolean;
  supports_custom_endpoint: boolean;
  unavailable: Record<string, string>;
}

export interface WorkerState {
  id: string;
  role: string;
  class_name: string;
  summary: string;
  area: string;
  status: WorkerStatus;
  provider: string | null;
  model: string | null;
  resolved_by: 'auto' | 'manual' | 'indisponivel';
  reasoning: ReasoningSupport;
  concurrency: number;
  concurrency_min: number;
  concurrency_max: number;
  enabled: boolean;
  running: number;
  detail: string;
  /** O token de paleta desta linha. Ver ADR-005: quem possui a entidade a descreve. */
  palette_token: string;
}

export interface OperationState {
  auto: boolean;
  active_workers: number | null;
  capacity: number | null;
  queued: number | null;
  running: number | null;
  last_cycle: string | null;
  next_run: string | null;
  calls: number | null;
  budget: string | null;
  failures: string[];
  last_audit: string | null;
  unavailable: Record<string, string>;
}

export interface ControlSnapshot {
  schema_version: number;
  generated_at: string;
  providers: ProviderState[];
  workers: WorkerState[];
  operation: OperationState;
  notices: string[];
}

export interface CredentialResult {
  provider: string;
  key_configured: boolean;
  key_hint: string | null;
  status: ProviderStatus;
  detail: string;
}

export class ControlError extends Error {}

const PROVIDER_STATUSES = [
  'configurado',
  'ausente',
  'invalido',
  'disponivel',
  'erro',
] as const;
const WORKER_STATUSES = ['ativo', 'inativo', 'espera', 'erro', 'desconhecido'] as const;
const RESOLVED_BY = ['auto', 'manual', 'indisponivel'] as const;

function textMap(value: unknown, path: string): Record<string, string> {
  const source = payloadRecord(value, path);
  return Object.fromEntries(
    Object.entries(source).map(([key, item]) => [key, payloadText(item, `${path}.${key}`)]),
  );
}

function textArray(value: unknown, path: string): string[] {
  return payloadArray(value, path).map((item, index) =>
    payloadText(item, `${path}[${index}]`),
  );
}

function nullableInteger(value: unknown, path: string): number | null {
  return value === null
    ? null
    : payloadNumber(value, path, { integer: true, min: 0 });
}

function keyHint(value: unknown, path: string): string | null {
  const hint = payloadNullableString(value, path);
  if (hint !== null && hint.length > 4) {
    throw new PayloadError(path, 'esperada string com no máximo 4 caracteres ou null');
  }
  return hint;
}

function parseReasoning(value: unknown, path: string): ReasoningSupport {
  const source = payloadRecord(value, path);
  const options = textArray(source.options, `${path}.options`);
  if (options.length > 16) throw new PayloadError(`${path}.options`, 'máximo de 16 itens');
  payloadUnique(options, `${path}.options`);
  const selected = payloadNullableString(source.value, `${path}.value`);
  if (selected !== null && selected.length > 64) {
    throw new PayloadError(`${path}.value`, 'máximo de 64 caracteres');
  }
  return {
    supported: payloadBoolean(source.supported, `${path}.supported`),
    options,
    value: selected,
    reason: payloadText(source.reason, `${path}.reason`),
  };
}

function parseProvider(value: unknown, path: string): ProviderState {
  const source = payloadRecord(value, path);
  return {
    id: payloadString(source.id, `${path}.id`),
    name: payloadString(source.name, `${path}.name`),
    status: payloadEnum(source.status, `${path}.status`, PROVIDER_STATUSES),
    detail: payloadText(source.detail, `${path}.detail`),
    key_configured: payloadBoolean(source.key_configured, `${path}.key_configured`),
    key_hint: keyHint(source.key_hint, `${path}.key_hint`),
    endpoint_count: nullableInteger(source.endpoint_count, `${path}.endpoint_count`),
    enabled: payloadBoolean(source.enabled, `${path}.enabled`),
    supports_custom_endpoint: payloadBoolean(
      source.supports_custom_endpoint,
      `${path}.supports_custom_endpoint`,
    ),
    unavailable: textMap(source.unavailable, `${path}.unavailable`),
  };
}

function parseWorker(value: unknown, path: string): WorkerState {
  const source = payloadRecord(value, path);
  const concurrency = payloadNumber(source.concurrency, `${path}.concurrency`, {
    integer: true,
    min: 0,
  });
  const concurrencyMin = payloadNumber(source.concurrency_min, `${path}.concurrency_min`, {
    integer: true,
    min: 0,
  });
  const concurrencyMax = payloadNumber(source.concurrency_max, `${path}.concurrency_max`, {
    integer: true,
    min: 0,
  });
  if (concurrencyMin > concurrencyMax) {
    throw new PayloadError(`${path}.concurrency_min`, 'maior que concurrency_max');
  }
  if (concurrency < concurrencyMin || concurrency > concurrencyMax) {
    throw new PayloadError(`${path}.concurrency`, 'fora de concurrency_min..concurrency_max');
  }
  return {
    id: payloadString(source.id, `${path}.id`),
    role: payloadString(source.role, `${path}.role`),
    class_name: payloadString(source.class_name, `${path}.class_name`),
    summary: payloadText(source.summary, `${path}.summary`),
    area: payloadText(source.area, `${path}.area`),
    status: payloadEnum(source.status, `${path}.status`, WORKER_STATUSES),
    provider: payloadNullableString(source.provider, `${path}.provider`),
    model: payloadNullableString(source.model, `${path}.model`),
    resolved_by: payloadEnum(source.resolved_by, `${path}.resolved_by`, RESOLVED_BY),
    reasoning: parseReasoning(source.reasoning, `${path}.reasoning`),
    concurrency,
    concurrency_min: concurrencyMin,
    concurrency_max: concurrencyMax,
    enabled: payloadBoolean(source.enabled, `${path}.enabled`),
    running: payloadNumber(source.running, `${path}.running`, { integer: true, min: 0 }),
    detail: payloadText(source.detail, `${path}.detail`),
    palette_token: payloadString(source.palette_token, `${path}.palette_token`),
  };
}

function parseOperation(value: unknown, path: string): OperationState {
  const source = payloadRecord(value, path);
  const failures = textArray(source.failures, `${path}.failures`);
  if (failures.length > 20) throw new PayloadError(`${path}.failures`, 'máximo de 20 itens');
  return {
    auto: payloadBoolean(source.auto, `${path}.auto`),
    active_workers: nullableInteger(source.active_workers, `${path}.active_workers`),
    capacity: nullableInteger(source.capacity, `${path}.capacity`),
    queued: nullableInteger(source.queued, `${path}.queued`),
    running: nullableInteger(source.running, `${path}.running`),
    last_cycle: payloadNullableString(source.last_cycle, `${path}.last_cycle`),
    next_run: payloadNullableString(source.next_run, `${path}.next_run`),
    calls: nullableInteger(source.calls, `${path}.calls`),
    budget: payloadNullableString(source.budget, `${path}.budget`),
    failures,
    last_audit: payloadNullableString(source.last_audit, `${path}.last_audit`),
    unavailable: textMap(source.unavailable, `${path}.unavailable`),
  };
}

function controlContract<T>(parse: () => T): T {
  try {
    return parse();
  } catch (error) {
    if (error instanceof ControlError) throw error;
    if (error instanceof PayloadError) {
      throw new ControlError(`resposta de controle inválida: ${error.message}`);
    }
    throw error;
  }
}

/** Valida e reconstrói o snapshot agregado antes que qualquer controle o use. */
export function parseControlSnapshot(value: unknown): ControlSnapshot {
  return controlContract(() => {
    const source = payloadRecord(value, '$');
    const schemaVersion = payloadNumber(source.schema_version, '$.schema_version', {
      integer: true,
    });
    if (schemaVersion !== 1) throw new PayloadError('$.schema_version', 'esperado 1');
    const generatedAt = payloadString(source.generated_at, '$.generated_at');
    if (!Number.isFinite(Date.parse(generatedAt))) {
      throw new PayloadError('$.generated_at', 'esperada data válida');
    }
    const providers = payloadArray(source.providers, '$.providers').map((item, index) =>
      parseProvider(item, `$.providers[${index}]`),
    );
    const workers = payloadArray(source.workers, '$.workers').map((item, index) =>
      parseWorker(item, `$.workers[${index}]`),
    );
    const notices = textArray(source.notices, '$.notices');
    if (notices.length > 20) throw new PayloadError('$.notices', 'máximo de 20 itens');
    payloadUnique(
      providers.map((provider) => provider.id),
      '$.providers',
    );
    payloadUnique(
      workers.map((worker) => worker.id),
      '$.workers',
    );
    return {
      schema_version: 1,
      generated_at: generatedAt,
      providers,
      workers,
      operation: parseOperation(source.operation, '$.operation'),
      notices,
    };
  });
}

/** Valida a resposta sanitizada de credencial; o segredo não faz parte deste tipo. */
export function parseCredentialResult(value: unknown): CredentialResult {
  return controlContract(() => {
    const source = payloadRecord(value, '$');
    return {
      provider: payloadString(source.provider, '$.provider'),
      key_configured: payloadBoolean(source.key_configured, '$.key_configured'),
      key_hint: keyHint(source.key_hint, '$.key_hint'),
      status: payloadEnum(source.status, '$.status', PROVIDER_STATUSES),
      detail: payloadText(source.detail, '$.detail'),
    };
  });
}

async function pedir<T>(
  caminho: string,
  parse: (value: unknown) => T,
  init: RequestInit = {},
  options: { signal?: AbortSignal; timeoutMs?: number } = {},
): Promise<T> {
  let resposta: Response;
  try {
    resposta = await backendFetch(`${BASE}${caminho}`, {
      ...init,
      ...(options.signal === undefined ? {} : { signal: options.signal }),
      headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) },
    }, options.timeoutMs);
  } catch (erro) {
    // Falha de transporte não é falha do backend. A distinção importa porque uma diz
    // "o Vault não está de pé" e a outra diz "o Vault recusou o que você pediu".
    if (options.signal?.aborted) throw (options.signal.reason ?? erro);
    throw new ControlError(
      erro instanceof BackendTimeoutError
        ? erro.message
        : `sem resposta do backend: ${String(erro)}`,
    );
  }
  if (!resposta.ok) {
    const detalhe = await resposta
      .json()
      .then((corpo: unknown) => {
        if (typeof corpo !== 'object' || corpo === null || Array.isArray(corpo)) {
          return resposta.statusText;
        }
        const detail = (corpo as Record<string, unknown>).detail;
        return typeof detail === 'string' ? detail : resposta.statusText;
      })
      .catch(() => resposta.statusText);
    throw new ControlError(detalhe);
  }
  let payload: unknown;
  try {
    payload = await resposta.json();
  } catch {
    throw new ControlError('resposta de controle não contém JSON válido');
  }
  return parse(payload);
}

export interface ControlClient {
  snapshot(options?: ControlRequestOptions): Promise<ControlSnapshot>;
  setAuto(auto: boolean, options?: ControlRequestOptions): Promise<ControlSnapshot>;
  patchWorker(
    workerId: string,
    patch: WorkerPatch,
    options?: ControlRequestOptions,
  ): Promise<ControlSnapshot>;
  testProvider(
    providerId: string,
    key?: string,
    options?: ControlRequestOptions,
  ): Promise<CredentialResult>;
  putCredential(
    providerId: string,
    key: string,
    options?: ControlRequestOptions,
  ): Promise<CredentialResult>;
  deleteCredential(providerId: string, options?: ControlRequestOptions): Promise<CredentialResult>;
}

export interface ControlRequestOptions {
  signal?: AbortSignal;
}

export interface WorkerPatch {
  enabled?: boolean;
  provider?: string;
  endpoint_id?: string;
  reasoning?: string;
  concurrency?: number;
}

export function createControlClient(): ControlClient {
  return {
    snapshot: (options) => pedir('/snapshot', parseControlSnapshot, {}, options),
    setAuto: (auto, options) =>
      pedir('/auto', parseControlSnapshot, {
        method: 'PATCH',
        body: JSON.stringify({ auto }),
      }, { ...options, timeoutMs: MUTATION_FETCH_TIMEOUT_MS }),
    patchWorker: (workerId, patch, options) =>
      pedir(`/workers/${encodeURIComponent(workerId)}`, parseControlSnapshot, {
        method: 'PATCH',
        body: JSON.stringify(patch),
      }, { ...options, timeoutMs: MUTATION_FETCH_TIMEOUT_MS }),
    testProvider: (providerId, key, options) =>
      pedir(`/providers/${encodeURIComponent(providerId)}/test`, parseCredentialResult, {
        method: 'POST',
        // Sem chave no corpo, o backend testa a que já está configurada. Com chave,
        // ele testa a candidata **sem persistir** — é o que separa Testar de Aplicar.
        body: key === undefined ? 'null' : JSON.stringify({ key }),
      }, { ...options, timeoutMs: PROVIDER_TEST_TIMEOUT_MS }),
    putCredential: (providerId, key, options) =>
      pedir(`/providers/${encodeURIComponent(providerId)}/credential`, parseCredentialResult, {
        method: 'PUT',
        body: JSON.stringify({ key }),
      }, { ...options, timeoutMs: MUTATION_FETCH_TIMEOUT_MS }),
    deleteCredential: (providerId, options) =>
      pedir(`/providers/${encodeURIComponent(providerId)}/credential`, parseCredentialResult, {
        method: 'DELETE',
      }, { ...options, timeoutMs: MUTATION_FETCH_TIMEOUT_MS }),
  };
}
