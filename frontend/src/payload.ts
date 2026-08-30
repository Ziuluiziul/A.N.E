/** Erro estrutural numa fronteira JSON, sempre com o caminho que falhou. */
export class PayloadError extends Error {
  constructor(path: string, expected: string) {
    super(`${path}: ${expected}`);
    this.name = 'PayloadError';
  }
}

export type PayloadRecord = Record<string, unknown>;

export function payloadRecord(value: unknown, path: string): PayloadRecord {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new PayloadError(path, 'esperado objeto');
  }
  return value as PayloadRecord;
}

export function payloadArray(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value)) throw new PayloadError(path, 'esperado array');
  return value;
}

export function payloadString(value: unknown, path: string): string {
  if (typeof value !== 'string' || value.length === 0) {
    throw new PayloadError(path, 'esperada string não vazia');
  }
  return value;
}

export function payloadText(value: unknown, path: string): string {
  if (typeof value !== 'string') throw new PayloadError(path, 'esperada string');
  return value;
}

export function payloadNullableString(value: unknown, path: string): string | null {
  return value === null ? null : payloadString(value, path);
}

export function payloadBoolean(value: unknown, path: string): boolean {
  if (typeof value !== 'boolean') throw new PayloadError(path, 'esperado booleano');
  return value;
}

export interface NumberOptions {
  integer?: boolean;
  min?: number;
  max?: number;
}

export function payloadNumber(
  value: unknown,
  path: string,
  { integer = false, min, max }: NumberOptions = {},
): number {
  if (
    typeof value !== 'number' ||
    !Number.isFinite(value) ||
    (integer && !Number.isSafeInteger(value)) ||
    (min !== undefined && value < min) ||
    (max !== undefined && value > max)
  ) {
    const kind = integer ? 'inteiro finito' : 'número finito';
    const lower = min === undefined ? '' : ` >= ${min}`;
    const upper = max === undefined ? '' : ` <= ${max}`;
    throw new PayloadError(path, `esperado ${kind}${lower}${upper}`);
  }
  return value;
}

export function payloadEnum<T extends string>(
  value: unknown,
  path: string,
  allowed: readonly T[],
): T {
  if (typeof value !== 'string' || !allowed.includes(value as T)) {
    throw new PayloadError(path, `esperado um de: ${allowed.join(', ')}`);
  }
  return value as T;
}

export function payloadStringArray(value: unknown, path: string): string[] {
  return payloadArray(value, path).map((item, index) =>
    payloadString(item, `${path}[${index}]`),
  );
}

export function payloadUnique(values: readonly string[], path: string): void {
  const seen = new Set<string>();
  for (const value of values) {
    if (seen.has(value)) throw new PayloadError(path, `identificador duplicado: ${value}`);
    seen.add(value);
  }
}
