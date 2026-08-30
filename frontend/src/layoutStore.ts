// Cliente da memória espacial. Degrada em silêncio, de propósito.
//
// Sem backend não há persistência, e isso é aceitável: o layout é determinístico, de
// modo que a cena reabre idêntica enquanto o corpus não muda. O que a persistência
// acrescenta é sobreviver a uma nota nova sem recalcular o território — melhoria real,
// mas nunca condição para a cena abrir.
//
// Por isso todo erro aqui vira "não havia posições gravadas". Uma falha ao gravar
// coordenadas não pode impedir alguém de ler o corpus.

import type { LayoutMap, Vec3 } from './layout';
import { OPERATIONAL_LAYOUT_VERSION } from './operationalLayout';
import { MUTATION_FETCH_TIMEOUT_MS, backendFetch } from './transport';

function rethrowAbort(signal: AbortSignal | undefined, error: unknown): void {
  if (signal?.aborted) throw (signal.reason ?? error);
}

/**
 * Versão do algoritmo de layout do corpus, enviada como dado do contrato.
 *
 * A impressão digital identifica o conteúdo, não a geometria. O backend mantém o path
 * como o SHA-256 puro e confere este campo antes de devolver posições. A versão
 * operacional é outro contrato: misturá-la aqui invalidava o corpus quando só a nuvem
 * de execuções mudava.
 *
 * Vai em 6 porque a espiral do território passou a somar o afastamento mínimo em
 * quadratura, e cada nota do corpus mudou de lugar. Vai em 5 porque a **ordem dos
 * domínios no anel** deixou de ser alfabética e passou a
 * sair da afinidade entre eles. Um arquivo da versão 4 poria cada MOC no azimute que a
 * inicial do nome lhe dava, e o corpus reabriria com a disposição que esta versão
 * justamente desfez.
 */
export const LAYOUT_ALGORITHM_VERSION = '6';

interface StoredPosition {
  x: number;
  y: number;
  z: number;
  pinned?: boolean;
}

function isPosition(value: unknown): value is StoredPosition {
  if (typeof value !== 'object' || value === null) return false;
  const p = value as Record<string, unknown>;
  return (
    Number.isFinite(p.x as number) &&
    Number.isFinite(p.y as number) &&
    Number.isFinite(p.z as number)
  );
}

/**
 * Posições gravadas para esta impressão do corpus. Mapa vazio se não houver.
 *
 * `origem` é onde o corpus mora no mundo composto. O que se grava é **relativo a ela**:
 * a memória espacial existe para preservar onde cada nota ficou *dentro do território*,
 * e isso não deveria depender de onde a composição resolveu pôr o território. Gravando
 * mundo, a recomposição de 2026-08-12 — que desceu o corpus para debaixo do quórum —
 * teria feito toda nota reabrir na posição antiga enquanto o resto da cena mudava.
 */
export async function loadPositions(
  fingerprint: string,
  origem: Vec3 = { x: 0, y: 0, z: 0 },
  signal?: AbortSignal,
): Promise<LayoutMap> {
  const posicoes: LayoutMap = new Map();
  try {
    const query = new URLSearchParams({ algorithmVersion: LAYOUT_ALGORITHM_VERSION });
    const response = await backendFetch(
      `/layout/${encodeURIComponent(fingerprint)}?${query.toString()}`,
      signal === undefined ? {} : { signal },
    );
    if (!response.ok) return posicoes;
    const payload = (await response.json()) as {
      corpusFingerprint?: unknown;
      algorithmVersion?: unknown;
      positions?: Record<string, unknown>;
    };
    if (
      payload.corpusFingerprint !== fingerprint ||
      payload.algorithmVersion !== LAYOUT_ALGORITHM_VERSION
    ) {
      return posicoes;
    }
    for (const [id, valor] of Object.entries(payload.positions ?? {})) {
      if (isPosition(valor)) {
        posicoes.set(id, {
          x: valor.x + origem.x,
          y: valor.y + origem.y,
          z: valor.z + origem.z,
        });
      }
    }
  } catch (error) {
    rethrowAbort(signal, error);
    // Backend ausente: a cena abre com o layout determinístico.
  }
  return posicoes;
}

/**
 * Grava as posições. Devolve se conseguiu, para o relatório da cena poder dizê-lo.
 *
 * `only` restringe o que é gravado, e a camada viva fica de fora de propósito: a chave
 * é a impressão digital do **corpus**, que não muda quando um painel de quórum entra.
 * Gravar posição de execução sob essa chave faria uma execução nova reaparecer no lugar
 * de uma antiga — memória espacial aplicada a algo que não tem lugar a preservar.
 */
export async function savePositions(
  fingerprint: string,
  positions: LayoutMap,
  only?: ReadonlySet<string>,
  origem: Vec3 = { x: 0, y: 0, z: 0 },
  signal?: AbortSignal,
): Promise<'stored' | 'stale-fingerprint' | 'rejected' | 'backend-unavailable'> {
  const corpo: Record<string, Vec3> = {};
  for (const [id, p] of positions) {
    if (only && !only.has(id)) continue;
    // Relativo à origem do corpus: ver `loadPositions`.
    corpo[id] = { x: p.x - origem.x, y: p.y - origem.y, z: p.z - origem.z };
  }
  try {
    const response = await backendFetch(`/layout/${encodeURIComponent(fingerprint)}`, {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      ...(signal === undefined ? {} : { signal }),
      body: JSON.stringify({
        algorithmVersion: LAYOUT_ALGORITHM_VERSION,
        positions: corpo,
      }),
    }, MUTATION_FETCH_TIMEOUT_MS);
    if (response.ok) return 'stored';
    if (response.status === 409) return 'stale-fingerprint';
    return 'rejected';
  } catch (error) {
    rethrowAbort(signal, error);
    return 'backend-unavailable';
  }
}

/**
 * Endpoint dos ordinais de execução. Independe da impressão do corpus, de propósito:
 * um painel de quórum novo não muda o corpus, e o ordinal precisa sobreviver a isso.
 */
const OPERATIONAL_LAYOUT_ENDPOINT = `/operational-layout/${OPERATIONAL_LAYOUT_VERSION}`;

function parseOperationalSlots(payload: unknown): Map<string, number> | null {
  if (typeof payload !== 'object' || payload === null) return null;
  const record = payload as Record<string, unknown>;
  if (record.algorithmVersion !== OPERATIONAL_LAYOUT_VERSION) return null;
  if (typeof record.slots !== 'object' || record.slots === null) return null;
  const slots = new Map<string, number>();
  const occupied = new Set<number>();
  for (const [panelId, ordinal] of Object.entries(record.slots)) {
    if (!Number.isInteger(ordinal) || (ordinal as number) < 0 || occupied.has(ordinal as number)) {
      return null;
    }
    slots.set(panelId, ordinal as number);
    occupied.add(ordinal as number);
  }
  return slots;
}

/**
 * Ordinais gravados das execuções.
 *
 * O contrato é o que o estado significa: `{panelId: ordinal}`. Antes o ordinal viajava
 * disfarçado de `Position.x` pela rota do corpus; além de mentir sobre o tipo, essa rota
 * rejeitava a chave operacional por não ser o fingerprint vivo.
 */
export async function loadOperationalSlots(signal?: AbortSignal): Promise<Map<string, number>> {
  try {
    const response = await backendFetch(
      OPERATIONAL_LAYOUT_ENDPOINT,
      signal === undefined ? {} : { signal },
    );
    if (!response.ok) return new Map();
    return parseOperationalSlots(await response.json()) ?? new Map();
  } catch (error) {
    rethrowAbort(signal, error);
    // Sem backend não há ordinal gravado; o layout deriva um da ordem de chegada.
    return new Map();
  }
}

/** Grava e devolve os ordinais efetivos que o backend serializou sob lock. */
export async function saveOperationalSlots(
  slots: ReadonlyMap<string, number>,
  signal?: AbortSignal,
): Promise<
  | { status: 'stored'; slots: Map<string, number> }
  | { status: 'rejected' | 'backend-unavailable' | 'invalid-response' }
> {
  const corpo: Record<string, number> = {};
  for (const [panelId, ordinal] of slots) corpo[panelId] = ordinal;
  try {
    const response = await backendFetch(OPERATIONAL_LAYOUT_ENDPOINT, {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      ...(signal === undefined ? {} : { signal }),
      body: JSON.stringify({ slots: corpo }),
    }, MUTATION_FETCH_TIMEOUT_MS);
    if (!response.ok) return { status: 'rejected' };
    const effective = parseOperationalSlots(await response.json());
    return effective === null
      ? { status: 'invalid-response' }
      : { status: 'stored', slots: effective };
  } catch (error) {
    rethrowAbort(signal, error);
    return { status: 'backend-unavailable' };
  }
}

export interface MergeResult {
  positions: LayoutMap;
  reused: number;
  placed: number;
}

/**
 * Junta o que foi gravado com o que acabou de ser calculado.
 *
 * Identidade conhecida mantém a posição gravada; identidade nova fica onde o layout
 * a colocou. É esta assimetria que preserva o mapa mental: uma nota nova aparece sem
 * empurrar nada do que já estava lá.
 */
export function mergePositions(calculated: LayoutMap, stored: LayoutMap): MergeResult {
  const positions: LayoutMap = new Map();
  let reused = 0;
  let placed = 0;
  for (const [id, calculada] of calculated) {
    const gravada = stored.get(id);
    if (gravada) {
      positions.set(id, { ...gravada });
      reused += 1;
    } else {
      positions.set(id, calculada);
      placed += 1;
    }
  }
  return { positions, reused, placed };
}
