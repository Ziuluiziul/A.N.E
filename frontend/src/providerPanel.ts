// O que o painel de um provedor mostra quando ele **é** a configuração dele.
//
// Módulo puro, pelo mesmo motivo de `dockModel.ts`: as regras que importam aqui — não
// inventar estado, não prometer ação que não há como executar, nunca tocar em segredo —
// dão para provar sem abrir janela nem instanciar WebGL.
//
// **A face não substitui o painel; ela é o painel.** Por isso o modelo carrega as
// frases que a placa já dizia (`panelLines`) junto com o estado do controle: escolher
// um provedor não pode trocar o que ele afirma por um formulário sem contexto. O que a
// face acrescenta é a parte que a cena não tem como oferecer — campo mascarado, foco e
// confirmação —, e é só isso.
//
// **Segredo não passa por aqui.** Existe `keyHint`, que são os últimos caracteres que o
// backend escolheu devolver, e `keyConfigured`, que é um booleano. O valor digitado vive
// no DOM entre o clique e a porta, e em lugar nenhum mais.

import { describeDock, type DockData, type StatusBadge } from './dockModel';

/** O que a face pode pedir, e o motivo quando não pode. */
export interface FaceAction {
  label: string;
  /** `null` quando dá para agir; a frase do impedimento quando não dá. */
  blocked: string | null;
}

export interface ProviderFaceModel {
  id: string;
  name: string;
  status: StatusBadge;
  /**
   * O que este painel afirma, na ordem de leitura da placa.
   *
   * Vem do descritor da cena, e não é reescrito aqui: a face desenha a mesma leitura
   * que o texto desenhava, porque é a mesma superfície.
   */
  lines: string[];
  /** O estado da credencial, em uma frase. */
  keyLine: string;
  /** Quantos endpoints o catálogo conhece, ou por que ele não sabe. */
  endpointLine: string;
  keyConfigured: boolean;
  saving: boolean;
  testing: boolean;
  /** A gravação está aguardando o segundo clique, o que autoriza de fato. */
  confirming: boolean;
  apply: FaceAction;
  test: FaceAction;
  remove: FaceAction | null;
  /** Erro e conflito dos controles desta credencial, já resolvidos em texto. */
  notes: string[];
}

/** Estado que é da interface, e não do backend. */
export interface FaceUiState {
  confirming: boolean;
  /** Portas ausentes viram ação bloqueada **com o motivo escrito**. */
  canApply: boolean;
  canTest: boolean;
  canRemove: boolean;
}

export const SEM_PORTA = 'ainda não conectado ao backend';

/** Identificadores de controle, iguais aos do dock: pendência e erro se ligam por eles. */
export function providerControlId(providerId: string): { key: string; test: string } {
  return { key: `provider:${providerId}:key`, test: `provider:${providerId}:test` };
}

function acao(label: string, permitida: boolean, ocupada: string | null): FaceAction {
  if (ocupada !== null) return { label: ocupada, blocked: ocupada };
  return { label, blocked: permitida ? null : SEM_PORTA };
}

/**
 * A face de um provedor, ou `null` quando o controle ainda não conhece esse provedor.
 *
 * Devolver `null` é a resposta honesta para "o nó existe na cena e o backend não o
 * listou": abrir uma face vazia sobre a placa afirmaria uma configuração que não há.
 */
export function describeProviderFace(
  data: DockData,
  providerId: string,
  lines: readonly string[],
  ui: FaceUiState,
): ProviderFaceModel | null {
  const aba = describeDock(data).tabs.find((item) => item.id === 'provedores');
  const linha = aba?.providers.find((item) => item.id === providerId);
  if (!linha) return null;

  const ids = providerControlId(providerId);
  const gravando = data.pending.has(ids.key);
  const testando = data.pending.has(ids.test);

  const notas: string[] = [];
  for (const id of [ids.key, ids.test]) {
    const erro = data.errors.get(id);
    if (erro) notas.push(erro);
    const conflito = data.conflicts.get(id);
    if (conflito) notas.push(conflito);
  }
  // O detalhe do provedor entra como nota quando existe: é lá que mora "opt-in
  // free-tier" e "nenhuma credencial no arquivo de segredos".
  if (linha.detail) notas.push(linha.detail);

  return {
    id: linha.id,
    name: linha.name,
    status: linha.status,
    lines: [...lines],
    keyLine: linha.keyConfigured
      ? `Chave configurada${linha.keyHint ? `, terminada em ${linha.keyHint}` : ''}.`
      : 'Sem chave configurada.',
    endpointLine:
      linha.endpointCount === null
        ? `Endpoints: não informado — ${linha.endpointReason ?? 'sem motivo declarado'}.`
        : `${linha.endpointCount} endpoint(s) catalogado(s).`,
    keyConfigured: linha.keyConfigured,
    saving: gravando,
    testing: testando,
    confirming: ui.confirming,
    apply: acao('Aplicar chave', ui.canApply, gravando ? 'Gravando…' : null),
    test: acao('Testar conexão', ui.canTest, testando ? 'Testando…' : null),
    // Remover só existe onde há o que remover: um botão que não tem alvo é ruído.
    remove: linha.keyConfigured
      ? acao('Remover chave', ui.canRemove, gravando ? 'Gravando…' : null)
      : null,
    notes: notas,
  };
}

/**
 * A face de um trabalhador: o mesmo painel, outros controles.
 *
 * O que o papel **é** — classe, resumo, área, teto — já está nas frases da placa, que
 * vêm da projeção. O que a face acrescenta é o que muda: se ele está ligado, quantas
 * tarefas simultâneas, e o nível de raciocínio quando o endpoint declara níveis.
 */
export interface WorkerFaceModel {
  id: string;
  name: string;
  status: StatusBadge;
  lines: string[];
  /** Provedor e modelo resolvidos agora, e por quem. */
  resolutionLine: string;
  /** Quem resolveu provedor e modelo: AUTO, escolha manual, ou nada. */
  originLine: string;
  enabled: boolean;
  enabledAction: FaceAction;
  concurrency: {
    value: number;
    min: number;
    max: number;
    blocked: string | null;
  };
  reasoning: {
    /** `null` quando o endpoint não declara níveis — opção inexistente não é simulada. */
    options: string[] | null;
    value: string | null;
    blocked: string | null;
    /** Por que não há níveis, quando não há. */
    reason: string | null;
  };
  runningLine: string | null;
  notes: string[];
}

/** Com AUTO ligado a política canônica resolve tudo; o controle mostra, e não muda. */
export const SOB_AUTO = 'AUTO ativo: a política canônica resolve isto';

/** Identificadores de controle de um trabalhador, iguais aos que o dock já usava. */
export function workerControlId(workerId: string): {
  enabled: string;
  concurrency: string;
  reasoning: string;
} {
  return {
    enabled: `worker:${workerId}:enabled`,
    concurrency: `worker:${workerId}:concurrency`,
    reasoning: `worker:${workerId}:reasoning`,
  };
}

/**
 * A face de um trabalhador, ou `null` quando o controle não conhece esse papel.
 *
 * Mesma regra do provedor: face vazia sobre a placa afirmaria uma configuração que não
 * existe, e dizer "o painel de controle não tem este papel" é a resposta honesta.
 */
export function describeWorkerFace(
  data: DockData,
  workerId: string,
  lines: readonly string[],
  ui: { canToggle: boolean; canSetConcurrency: boolean; canSetReasoning: boolean },
): WorkerFaceModel | null {
  const modelo = describeDock(data);
  const aba = modelo.tabs.find((item) => item.id === 'trabalhadores');
  const linha = aba?.workers.find((item) => item.id === workerId);
  if (!linha) return null;

  const ids = workerControlId(workerId);
  const auto = modelo.autoOn;
  const trava = (pendente: boolean, permitido: boolean): string | null => {
    if (pendente) return 'aplicando…';
    if (auto) return SOB_AUTO;
    return permitido ? null : SEM_PORTA;
  };

  const notas: string[] = [];
  for (const id of [ids.enabled, ids.concurrency, ids.reasoning]) {
    const erro = data.errors.get(id);
    if (erro) notas.push(erro);
    const conflito = data.conflicts.get(id);
    if (conflito) notas.push(conflito);
  }

  return {
    id: linha.id,
    name: linha.role,
    status: linha.status,
    lines: [...lines],
    // A origem sai da mesma linha: `origin` já traz "resolvido pelo AUTO" e o detalhe
    // do backend costuma repetir a frase com outras palavras. Numa face de duzentos
    // pixels, a repetição custa uma linha inteira de leitura real.
    resolutionLine:
      `Provedor: ${linha.provider ?? 'não informado'} · ` +
      `Modelo: ${linha.model ?? 'não informado'}`,
    originLine: linha.origin,
    enabled: linha.enabled,
    // Ligar e desligar continua valendo sob AUTO: o modo automático resolve provedor,
    // modelo e simultaneidade, e não decide se o papel participa.
    enabledAction: acao(
      linha.enabled ? 'Desligar' : 'Ligar',
      ui.canToggle,
      data.pending.has(ids.enabled) ? 'aplicando…' : null,
    ),
    concurrency: {
      value: linha.concurrency.value,
      min: linha.concurrency.min,
      max: linha.concurrency.max,
      blocked: trava(data.pending.has(ids.concurrency), ui.canSetConcurrency),
    },
    reasoning: {
      options: linha.reasoning.supported && linha.reasoning.options.length > 0
        ? [...linha.reasoning.options]
        : null,
      value: linha.reasoning.value,
      blocked: trava(data.pending.has(ids.reasoning), ui.canSetReasoning),
      reason: linha.reasoning.reason,
    },
    runningLine:
      linha.running > 0 ? `${linha.running} tarefa(s) em execução agora.` : null,
    notes: notas,
  };
}
