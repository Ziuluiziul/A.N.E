// O estado temporal de cada modelo, lido da trilha — e só dela.
//
// **Por que ele existe.** O raciocínio era mais uma categoria de nós: 167 eventos com a
// mesma aparência, entre os quais o que está acontecendo agora se perdia. Um modelo é uma
// entidade temporal — ele fica latente, é convocado, trabalha, responde, e o que respondeu
// permanece até a próxima convocação —, e nada na cena dizia em qual desses momentos cada
// um estava.
//
// **O limite, que é o ponto mais importante.** O Atlas exibe o que o endpoint realmente
// disponibiliza. A trilha declara chamada aberta, chamada concluída, voto pedido, voto
// recebido, decisão tomada, e uma frase de acompanhamento em linguagem natural.
//
// **A frase é do orquestrador, não do provedor** — e esta linha corrige um engano que
// esteve aqui. `metadata.narration` é composta por `QuorumOrchestrator._narrar`, em
// f-strings sobre o próprio processo: "Consultando groq/qwen3.6-27b como
// revisor-estrutural", "respondeu em 1240 ms: ok", "registrada como evidência". Medido na
// trilha real, 88 de 1265 eventos a carregam, e nenhum deles carrega texto do modelo — o
// orquestrador tem `strip_reasoning` e **remove** bloco de raciocínio antes de gravar.
//
// Enquanto `narration` decidia entre `acting` e `reasoning`, a cena exibia "Consultando X
// como revisor-estrutural" como se fosse o raciocínio do modelo. É a síntese de cadeia de
// pensamento que este módulo existe para não fazer, cometida pelo próprio módulo.
//
// Agora narração da trilha é atividade: ela descreve o que o **sistema** faz.
// `reasoning` só entra quando o canal `/runtime/cognition` traz texto do provedor,
// via `withCognition`. A trilha operacional continua sem carregar scratchpad.
//
// Módulo puro: recebe o instantâneo e devolve estado por modelo. Sem Three.js, sem rede.

import type { CognitionFrame } from './cognition';
import type { RuntimeEvent, RuntimeEventType, RuntimeSnapshot } from './runtime';

export type CognitiveState = 'latent' | 'reasoning' | 'acting' | 'final' | 'error';

export interface CognitiveStatus {
  /** Provedor e endpoint, como a trilha os declara. */
  provider: string;
  endpoint: string;
  state: CognitiveState;
  /**
   * A frase que o provedor forneceu para o momento atual, quando forneceu.
   *
   * `null` não é ausência de atividade: é ausência de narração. São coisas diferentes, e
   * confundi-las faria a cena dizer que um modelo silencioso está parado.
   */
  narration: string | null;
  /**
   * O que ficou da última convocação, e permanece até a próxima.
   *
   * É o que faz um painel não ser "texto que aparece": terminada a chamada, o fluxo entra
   * em repouso e o resultado continua ali, legível, até o modelo ser convocado de novo.
   */
  result: string | null;
  /** A revisão do evento que decidiu este estado. Ordena sem depender de relógio. */
  revision: number;
  timestamp: string;
}

/** Eventos que **abrem** trabalho: depois deles o modelo está ocupado. */
const ABRE: ReadonlySet<RuntimeEventType> = new Set<RuntimeEventType>([
  'call_started',
  'vote_requested',
  'task_assigned',
  'promotion_started',
  'quorum_started',
]);

/** Eventos que registram um fechamento; o modelo só repousa se nenhuma abertura restar. */
const FECHA: ReadonlySet<RuntimeEventType> = new Set<RuntimeEventType>([
  'call_completed',
  'vote_received',
  'quorum_decided',
  'promotion_completed',
  'commit_created',
  'evidence_recorded',
  'proposal_created',
]);

/** A identidade do modelo que um evento declara, ou `null` quando ele não declara. */
function modeloDo(event: RuntimeEvent): string | null {
  if (!event.provider || !event.endpoint) return null;
  return `${event.provider}/${event.endpoint}`;
}

export type CognitiveWorkKind = 'call' | 'vote' | 'quorum' | 'promotion';

/**
 * Fallback para eventos antigos que ainda não declaravam o prazo. O backend atual
 * impõe 240 s à unidade externa inteira; a margem absorve entrega e persistência,
 * sem transformar uma queda do processo em pulso eterno.
 */
export const DEFAULT_CALL_DEADLINE_SECONDS = 240;
export const CALL_EVENT_DELIVERY_GRACE_MS = 15_000;
export const OPEN_COGNITIVE_WORK_EVIDENCE_MS =
  DEFAULT_CALL_DEADLINE_SECONDS * 1_000 + CALL_EVENT_DELIVERY_GRACE_MS;

/** Uma abertura ainda sem o fechamento correlato visível na trilha. */
export interface OpenCognitiveWork {
  kind: CognitiveWorkKind;
  provider: string;
  endpoint: string;
  task: string | null;
  eventId: string;
  revision: number;
  timestamp: string;
  narration: string | null;
  /** Papel no painel, quando a trilha o declara. */
  role: string | null;
  /** Instante após o qual a abertura sozinha já não prova execução atual. */
  evidenceExpiresAt: number;
}

const WORK_OPEN_KIND: Partial<Record<RuntimeEventType, CognitiveWorkKind>> = {
  call_started: 'call',
  vote_requested: 'vote',
  quorum_started: 'quorum',
  promotion_started: 'promotion',
};

const WORK_CLOSE_KIND: Partial<Record<RuntimeEventType, CognitiveWorkKind>> = {
  call_completed: 'call',
  vote_received: 'vote',
  quorum_decided: 'quorum',
  promotion_completed: 'promotion',
};

function workKey(event: RuntimeEvent, kind: CognitiveWorkKind): string | null {
  const model = modeloDo(event);
  if (model === null) return null;
  // `task` é a correlação mais específica presente nos dois lados da chamada.
  // Quando ela não existe, duas aberturas do mesmo modelo continuam sendo um multiset:
  // cada fechamento consome uma, sem transformar a ausência em identificador inventado.
  return `${kind}\u0000${model}\u0000${event.task ?? ''}`;
}

/**
 * Trabalho cuja abertura permanece sem fechamento correlato no snapshot.
 *
 * A correlação é `tipo + provedor + endpoint + tarefa`, e cada chave guarda uma fila
 * de aberturas. Assim chamadas sobrepostas ao mesmo endpoint não se sobrescrevem, nem o
 * fechamento de uma tarefa encerra outra. Se o início caiu fora da janela truncada, um
 * fechamento órfão é apenas ignorado: a trilha não permite reconstruir o que não veio.
 */
export function openCognitiveWork(snapshot: RuntimeSnapshot): OpenCognitiveWork[] {
  const abertas = new Map<string, OpenCognitiveWork[]>();
  for (const event of [...snapshot.events].sort((a, b) => a.revision - b.revision)) {
    if (event.task && event.type === 'task_assigned') {
      // Uma atribuição nova é a fronteira de tentativa. Na recuperação do worker ela
      // também é a única evidência persistida de que a chamada da tentativa anterior
      // foi interrompida; nenhuma abertura velha pode atravessar essa fronteira.
      for (const [key, queue] of abertas) {
        const restantes = queue.filter((work) => work.task !== event.task);
        if (restantes.length > 0) abertas.set(key, restantes);
        else abertas.delete(key);
      }
    }
    if (event.task && event.type === 'evidence_recorded' && !event.provider) {
      // O evento terminal da tarefa não nomeia endpoint. Ele fecha qualquer sobra cuja
      // telemetria de `call_completed` tenha falhado, sem tocar em outra tarefa.
      for (const [key, queue] of abertas) {
        const restantes = queue.filter((work) => work.task !== event.task);
        if (restantes.length > 0) abertas.set(key, restantes);
        else abertas.delete(key);
      }
    }

    const openKind = WORK_OPEN_KIND[event.type];
    if (openKind !== undefined) {
      const key = workKey(event, openKind);
      if (key === null) continue;
      const work: OpenCognitiveWork = {
        kind: openKind,
        provider: event.provider!,
        endpoint: event.endpoint!,
        task: event.task ?? null,
        eventId: event.id,
        revision: event.revision,
        timestamp: event.timestamp,
        narration: event.narration ?? null,
        role: event.role ?? null,
        evidenceExpiresAt:
          Date.parse(event.timestamp) +
          (event.deadlineSeconds ?? DEFAULT_CALL_DEADLINE_SECONDS) * 1_000 +
          CALL_EVENT_DELIVERY_GRACE_MS,
      };
      const queue = abertas.get(key);
      if (queue) queue.push(work);
      else abertas.set(key, [work]);
      continue;
    }

    const closeKind = WORK_CLOSE_KIND[event.type];
    if (closeKind === undefined) continue;
    const key = workKey(event, closeKind);
    if (key === null) continue;
    const queue = abertas.get(key);
    if (!queue || queue.length === 0) continue;
    queue.shift();
    if (queue.length === 0) abertas.delete(key);
  }
  return [...abertas.values()].flat().sort((a, b) => a.revision - b.revision);
}

/** Aberturas cuja idade ainda permite chamá-las de atividade atual. */
export function observableCognitiveWork(
  snapshot: RuntimeSnapshot,
  now = Date.now(),
): OpenCognitiveWork[] {
  return openCognitiveWork(snapshot).filter((work) => {
    const startedAt = Date.parse(work.timestamp);
    return Number.isFinite(startedAt) && now >= startedAt && now < work.evidenceExpiresAt;
  });
}

/**
 * O que ficou de um evento de fechamento, em linguagem natural.
 *
 * Sai dos campos que o contrato já permite — decisão, ação, confiança — e nunca de resposta
 * livre: a lista branca de `OperationalMetadata` é deliberadamente pequena, e ampliá-la por
 * aqui contornaria a razão de ela existir.
 */
function resultadoDe(event: RuntimeEvent): string | null {
  if (event.decision) {
    const confianca =
      event.confidence === undefined
        ? ''
        : `, com confiança ${(event.confidence * 100).toFixed(0)}%`;
    return `Votou ${event.decision}${confianca}.`;
  }
  if (event.action) return `Quórum decidiu ${event.action}.`;
  if (event.narration) return event.narration;
  return null;
}

/**
 * O estado de cada modelo que a trilha menciona, por `provedor/endpoint`.
 *
 * A leitura é em ordem de revisão, que cresce monotonicamente no servidor: ela é a ordem de
 * chegada mesmo quando os relógios discordam. Cada evento registra a observação mais
 * recente; ao final, as aberturas correlacionadas prevalecem sobre um fechamento de outra
 * tarefa no mesmo endpoint. O resultado só é apagado quando ainda existe trabalho aberto.
 *
 * Modelo que a janela de eventos não menciona **não aparece aqui**. Devolver `latent` para
 * ele seria afirmar que ele está em repouso, quando o que se sabe é que nada se sabe: a
 * janela guarda os últimos eventos, e o silêncio dentro dela não é silêncio do modelo.
 */
export function cognitiveStates(
  snapshot: RuntimeSnapshot,
  now?: number,
): Map<string, CognitiveStatus> {
  const porModelo = new Map<string, CognitiveStatus>();
  for (const event of [...snapshot.events].sort((a, b) => a.revision - b.revision)) {
    const chave = modeloDo(event);
    if (chave === null) continue;
    const anterior = porModelo.get(chave);
    const base: CognitiveStatus = anterior ?? {
      provider: event.provider!,
      endpoint: event.endpoint!,
      state: 'latent',
      narration: null,
      result: null,
      revision: event.revision,
      timestamp: event.timestamp,
    };

    let state: CognitiveState = base.state;
    let result = base.result;
    if (event.schemaValid === false) {
      // A única falha que a trilha declara: a resposta chegou e não casou com o contrato.
      state = 'error';
      result = 'A resposta não casou com o contrato esperado.';
    } else if (ABRE.has(event.type)) {
      // Convocação nova apaga o resultado anterior: ele pertencia à convocação passada.
      state = 'acting';
      result = null;
    } else if (FECHA.has(event.type)) {
      state = 'final';
      result = resultadoDe(event) ?? base.result;
    }

    porModelo.set(chave, {
      ...base,
      state,
      result,
      narration: event.narration ?? null,
      revision: event.revision,
      timestamp: event.timestamp,
    });
  }

  // A passagem escalar acima preserva o último resultado para os consumidores atuais.
  // A atividade, porém, precisa da correlação: o fechamento mais recente de A não pode
  // colocar o endpoint em repouso enquanto B ainda está aberto no mesmo modelo.
  const abertasPorModelo = new Map<string, OpenCognitiveWork[]>();
  const abertas = now === undefined
    ? openCognitiveWork(snapshot)
    : observableCognitiveWork(snapshot, now);
  for (const work of abertas) {
    const key = `${work.provider}/${work.endpoint}`;
    const abertas = abertasPorModelo.get(key);
    if (abertas) abertas.push(work);
    else abertasPorModelo.set(key, [work]);
  }
  for (const [key, base] of porModelo) {
    if (!isWorking(base) || abertasPorModelo.has(key)) continue;
    // A passagem escalar não vê uma recuperação/encerramento que não nomeie modelo,
    // nem sabe que o prazo declarado venceu. A correlação sabe: sem abertura vigente,
    // continuar dizendo "há uma chamada aberta" seria inventar atividade.
    porModelo.set(key, {
      ...base,
      state: 'latent',
      narration: null,
    });
  }
  for (const [key, abertas] of abertasPorModelo) {
    const atual = abertas.at(-1)!;
    const base = porModelo.get(key);
    if (!base) continue;
    porModelo.set(key, {
      ...base,
      // Estes campos precisam prevalecer sobre o fechamento de outra tarefa que pode
      // ter sido o último evento do modelo na passagem escalar.
      state: 'acting',
      narration: atual.narration,
      result: null,
      revision: atual.revision,
      timestamp: atual.timestamp,
    });
  }
  return porModelo;
}

/**
 * Sobrepõe o raciocínio que o provedor emitiu à leitura da trilha.
 *
 * Só vale enquanto o modelo está trabalhando: o canal cognitivo é efêmero e não
 * afirma estado depois que a chamada fechou. A trilha operacional continua sem
 * carregar esse texto.
 */
export function withCognition(
  states: Map<string, CognitiveStatus>,
  frames: readonly CognitionFrame[],
): Map<string, CognitiveStatus> {
  if (frames.length === 0) return states;
  const next = new Map(states);
  for (const frame of frames) {
    const key = `${frame.provider}/${frame.endpoint}`;
    const base = next.get(key);
    if (!base || !isWorking(base)) continue;
    if (
      frame.kind !== 'reasoning' &&
      frame.kind !== 'reasoning-summary' &&
      frame.kind !== 'output-delta'
    ) {
      continue;
    }
    if (!frame.text.trim()) continue;
    next.set(key, {
      ...base,
      state: 'reasoning',
      narration: frame.text,
    });
  }
  return next;
}

/** O modelo está trabalhando **agora**? É o que decide o pulso de atividade na cena. */
export function isWorking(status: CognitiveStatus): boolean {
  return status.state === 'acting' || status.state === 'reasoning';
}

/** A frase que o painel do modelo mostra, no estado em que ele está. */
export function describeCognitiveState(status: CognitiveStatus): string {
  switch (status.state) {
    case 'reasoning':
      return status.narration ?? 'Relatando o próprio raciocínio.';
    case 'acting':
      // A narração, quando existe, é do orquestrador: ela diz o que o sistema está
      // fazendo com o modelo, e é isso que se mostra. Sem ela, resta o fato observável.
      return status.narration ?? 'Convocado: há uma chamada aberta, e ela ainda não voltou.';
    case 'final':
      return status.result ?? 'Respondeu, e está em repouso até a próxima convocação.';
    case 'error':
      return status.result ?? 'A última chamada terminou em erro.';
    case 'latent':
      return 'Sem trabalho aberto vigente na trilha.';
  }
}
