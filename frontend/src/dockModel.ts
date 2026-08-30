// O que o dock mostra, decidido antes de existir um só elemento de DOM.
//
// Módulo puro: não toca no documento, não faz requisição e não guarda estado. Ele
// recebe o snapshot que o backend serviu, mais o que o cliente sabe sobre mutações em
// voo, e devolve linhas prontas para desenhar. É o mesmo padrão de descritor que
// `panels.ts` usa para a cena, e existe pela mesma razão: as regras que importam aqui
// — não inventar dado, não depender de cor, nunca tocar em segredo — dão para provar
// sem abrir janela.
//
// **A regra central é a ausência.** Um valor que o backend não mediu é `null`, e
// `null` vira texto explícito de ausência acompanhado do motivo, nunca zero. "0
// chamadas" e "não sei quantas chamadas" são afirmações diferentes, e trocar a segunda
// pela primeira é fabricar dado — a mesma falha que a política epistêmica do corpus
// proíbe.
//
// **Segredo não passa por aqui.** Não existe campo de chave neste módulo. O que existe
// é `keyHint`, que são os quatro últimos caracteres que o backend escolheu devolver, e
// `keyConfigured`, que é um booleano.

import type {
  ControlSnapshot,
  ProviderState,
  ProviderStatus,
  WorkerState,
  WorkerStatus,
} from './controlApi';

/** Texto único de ausência. Uma frase só, para o olho aprender a reconhecê-la. */
export const SEM_INFORMACAO = 'não informado';
/** Ausência com causa conhecida: ainda não houve resposta do backend. */
export const AGUARDANDO_BACKEND = 'aguardando o backend';

export type DockTabId = 'provedores' | 'trabalhadores' | 'operacao';

/**
 * As abas que a doca **desenha**.
 *
 * `provedores` e `operacao` saíram daqui e continuam no modelo: a credencial mora na
 * placa, o estado da operação mora no cartão. Desenhar de novo faria duas superfícies
 * para o mesmo fato.
 */
export const DOCK_TABS: { id: DockTabId; label: string }[] = [
  { id: 'trabalhadores', label: 'Trabalhadores' },
];

/** Tudo que `describeDock` descreve, desenhado ou não. A face lê `provedores` daqui. */
export const DOCK_TAB_IDS: DockTabId[] = ['provedores', 'trabalhadores', 'operacao'];

/**
 * A fase da leitura. Não é o mesmo que o conteúdo dela.
 *
 * `carregando` é a primeira busca; `indisponivel` é backend fora do ar; `pronto` é
 * leitura válida. `stale` atravessa por fora porque uma leitura antiga ainda é útil —
 * o que não pode é ser apresentada como se fosse de agora.
 */
export type DockPhase = 'carregando' | 'pronto' | 'indisponivel';

export type StatusKind = 'ativo' | 'inativo' | 'erro' | 'espera' | 'desconhecido';

/**
 * Um estado, dito de três formas redundantes.
 *
 * `label` é a palavra, `mark` é o sinal tipográfico e a cor entra depois, na folha de
 * estilo. Quem enxerga cor lê os três; quem não enxerga lê dois. Nenhum estado desta
 * interface pode ser distinguido só pelo matiz.
 */
export interface StatusBadge {
  kind: StatusKind;
  label: string;
  mark: string;
}

const BADGES: Record<StatusKind, StatusBadge> = {
  ativo: { kind: 'ativo', label: 'ativo', mark: '●' },
  inativo: { kind: 'inativo', label: 'desligado', mark: '○' },
  erro: { kind: 'erro', label: 'falha', mark: '▲' },
  espera: { kind: 'espera', label: 'em espera', mark: '◐' },
  desconhecido: { kind: 'desconhecido', label: 'estado desconhecido', mark: '—' },
};

export function badge(kind: StatusKind): StatusBadge {
  return BADGES[kind];
}

/** Estado do provedor, traduzido sem perder a distinção entre as cinco situações. */
const PROVIDER_BADGE: Record<ProviderStatus, StatusBadge> = {
  disponivel: { kind: 'ativo', label: 'disponível', mark: '●' },
  configurado: { kind: 'espera', label: 'chave configurada', mark: '◐' },
  ausente: { kind: 'inativo', label: 'sem chave', mark: '○' },
  invalido: { kind: 'erro', label: 'chave recusada', mark: '▲' },
  erro: { kind: 'erro', label: 'falha', mark: '▲' },
};

const WORKER_BADGE: Record<WorkerStatus, StatusBadge> = {
  ativo: BADGES.ativo,
  inativo: BADGES.inativo,
  espera: BADGES.espera,
  erro: BADGES.erro,
  desconhecido: BADGES.desconhecido,
};

export interface ProviderRow {
  id: string;
  name: string;
  status: StatusBadge;
  detail: string;
  keyConfigured: boolean;
  keyHint: string | null;
  endpointCount: number | null;
  endpointReason: string | null;
  enabled: boolean;
  supportsCustomEndpoint: boolean;
}

export interface WorkerRow {
  id: string;
  className: string;
  role: string;
  summary: string;
  area: string;
  status: StatusBadge;
  provider: string | null;
  model: string | null;
  /** Quem decidiu, em palavras. É o que separa resolvido de escolhido. */
  origin: string;
  reasoning: { supported: boolean; options: string[]; value: string | null; reason: string };
  concurrency: { value: number; min: number; max: number };
  enabled: boolean;
  running: number;
}

export interface OperationRow {
  label: string;
  value: string;
  /** Verdadeiro quando o valor é ausência, e não medida. */
  missing: boolean;
  /** Por que falta. Vazio quando não falta. */
  hint: string;
}

/** O que o cliente sabe além do snapshot: o que está em voo, o que falhou. */
export interface DockData {
  phase: DockPhase;
  reason: string | null;
  /** A leitura mostrada é anterior à última tentativa de atualização. */
  stale: boolean;
  snapshot: ControlSnapshot | null;
  legend: string;
  /** Ids de controle com mutação pendente. Só eles bloqueiam. */
  pending: ReadonlySet<string>;
  /** Erro por controle, já com a mensagem do backend. */
  errors: ReadonlyMap<string, string>;
  /**
   * Divergência entre o que foi pedido e o que ficou valendo.
   *
   * O backend é autoridade sobre limites: pedir cinco e receber três não é erro, é
   * conflito, e o painel diz isso em vez de mostrar o cinco que não vingou.
   */
  conflicts: ReadonlyMap<string, string>;
}

export interface DockTabModel {
  id: DockTabId;
  label: string;
  empty: string | null;
  rows: OperationRow[];
  providers: ProviderRow[];
  workers: WorkerRow[];
}

export interface DockModel {
  phase: DockPhase;
  banner: string | null;
  tabs: DockTabModel[];
  autoLabel: string;
  autoKnown: boolean;
  autoOn: boolean;
  legend: string;
  notices: string[];
}

function linha(
  label: string,
  value: number | string | null,
  reason: string | undefined,
): OperationRow {
  if (value === null || value === undefined) {
    return {
      label,
      value: SEM_INFORMACAO,
      missing: true,
      hint: reason ?? '',
    };
  }
  return { label, value: String(value), missing: false, hint: '' };
}

function providerRow(state: ProviderState): ProviderRow {
  return {
    id: state.id,
    name: state.name,
    status: PROVIDER_BADGE[state.status] ?? BADGES.desconhecido,
    detail: state.detail,
    keyConfigured: state.key_configured,
    keyHint: state.key_hint,
    endpointCount: state.endpoint_count,
    endpointReason: state.unavailable.endpoint_count ?? null,
    enabled: state.enabled,
    supportsCustomEndpoint: state.supports_custom_endpoint,
  };
}

const ORIGEM: Record<WorkerState['resolved_by'], string> = {
  auto: 'resolvido pelo AUTO',
  manual: 'escolha manual',
  indisponivel: 'sem resolução',
};

function workerRow(state: WorkerState): WorkerRow {
  return {
    id: state.id,
    className: state.class_name,
    role: state.role,
    summary: state.summary,
    area: state.area,
    status: WORKER_BADGE[state.status] ?? BADGES.desconhecido,
    provider: state.provider,
    model: state.model,
    origin: `${ORIGEM[state.resolved_by]}${state.detail ? ` · ${state.detail}` : ''}`,
    reasoning: {
      supported: state.reasoning.supported,
      options: state.reasoning.options,
      value: state.reasoning.value,
      reason: state.reasoning.reason,
    },
    concurrency: {
      value: state.concurrency,
      min: state.concurrency_min,
      max: state.concurrency_max,
    },
    enabled: state.enabled,
    running: state.running,
  };
}

export function describeDock(data: DockData): DockModel {
  const snapshot = data.snapshot;
  const vazio =
    data.phase === 'carregando'
      ? AGUARDANDO_BACKEND
      : snapshot === null
        ? (data.reason ?? AGUARDANDO_BACKEND)
        : null;

  const operacao = snapshot?.operation ?? null;
  const indisponivel = operacao?.unavailable ?? {};

  const capacidade =
    operacao === null || operacao.active_workers === null || operacao.capacity === null
      ? null
      : `${operacao.active_workers} de ${operacao.capacity}`;

  const rows: OperationRow[] = operacao
    ? [
        linha('Trabalhadores ativos', capacidade, indisponivel.active_workers),
        linha('Em execução', operacao.running, indisponivel.running),
        linha('Fila atual', operacao.queued, indisponivel.queued),
        linha('Último ciclo', operacao.last_cycle, indisponivel.last_cycle),
        linha('Próxima execução', operacao.next_run, indisponivel.next_run),
        linha('Chamadas', operacao.calls, indisponivel.calls),
        linha('Orçamento', operacao.budget, indisponivel.budget),
        linha('Última auditoria', operacao.last_audit, indisponivel.last_audit),
        linha(
          'Falhas recentes',
          operacao.failures.length === 0 ? null : operacao.failures.join(' · '),
          'nenhuma falha registrada na fila atual',
        ),
      ]
    : [];

  const auto = operacao?.auto ?? null;
  return {
    phase: data.phase,
    banner: data.stale
      ? 'leitura desatualizada; a última atualização falhou'
      : data.phase === 'indisponivel'
        ? (data.reason ?? 'painel indisponível')
        : null,
    tabs: [
      {
        id: 'provedores',
        label: 'Provedores',
        empty: vazio,
        rows: [],
        providers: (snapshot?.providers ?? []).map(providerRow),
        workers: [],
      },
      {
        id: 'trabalhadores',
        label: 'Trabalhadores',
        empty: vazio,
        rows: [],
        providers: [],
        workers: (snapshot?.workers ?? []).map(workerRow),
      },
      { id: 'operacao', label: 'Operação', empty: vazio, rows, providers: [], workers: [] },
    ],
    autoLabel:
      auto === null ? `AUTO — ${SEM_INFORMACAO}` : auto ? 'AUTO ATIVO' : 'AUTO DESLIGADO',
    autoKnown: auto !== null,
    autoOn: auto === true,
    legend: data.legend,
    notices: snapshot?.notices ?? [],
  };
}

/** O estado inicial: nada do backend ainda, e a legenda que a cena já sabe montar. */
export function emptyDockData(legend: string): DockData {
  return {
    phase: 'carregando',
    reason: null,
    stale: false,
    snapshot: null,
    legend,
    pending: new Set<string>(),
    errors: new Map<string, string>(),
    conflicts: new Map<string, string>(),
  };
}
