// O descritor de painel: o que cada entidade do atlas **é**, antes de existir pixel.
//
// Módulo puro e determinístico. Não importa Three.js, troika nem DOM, não lê câmera
// nem estado global, e não devolve coordenada final nem geometria. A mesma entidade
// com o mesmo contexto produz sempre o mesmo descritor — é isso que permite provar a
// gramática visual da ADR-002 sem GPU, antes de a cena mudar.
//
// **Silhueta não é grandeza.** Tipos diferentes têm proporções diferentes porque a
// proporção comunica função. O que a proporção não pode fazer é criar importância:
// `panelExtent` deriva largura e altura de uma **área constante por degrau**, de modo
// que uma ponte 21:9 e um MOC 16:9 do mesmo degrau ocupem exatamente a mesma área.
// Ênfase, prioridade de LOD e área de captura também não olham para a proporção.
//
// **Linguagem natural.** Toda linha é frase, não campo. `ok · 4552 ms · n=17` vira
// "Respondeu em 4,5 s na última sonda, com histórico de 17 medições". Acessível sem
// empobrecer: nenhum conceito é trocado por versão vaga.

import { shapeOf, type PanelShape } from './panelShapes';
import type {
  CanonicalState,
  EntityKind,
  OperationalMetadata,
  ProjectionNode,
  RelationFamily,
} from './contract';
import { LOD_ORDER, type LodLevel } from './lod';
import { textoCorrido } from './markdownText';

export type PanelType =
  | 'moc'
  | 'note'
  | 'bridge'
  | 'quorum'
  | 'task'
  | 'endpoint'
  | 'provider'
  | 'worker'
  | 'evento';

export type PanelEdgeSide = 'top' | 'bottom' | 'left' | 'right';

/** Variante tipográfica: peso do título, presença de subtítulo, densidade do corpo. */
export type TypographicVariant =
  | 'ancora'
  | 'densa'
  | 'travessia'
  | 'deliberativa'
  | 'transitoria'
  | 'operacional';

export type SectionId =
  | 'escopo'
  | 'rotas'
  | 'contagem'
  | 'descricao'
  | 'claims'
  | 'relacoes'
  | 'liga'
  | 'mecanismo'
  | 'escopo-negativo'
  | 'hipotese'
  | 'evidencias'
  | 'objecoes'
  | 'votos'
  | 'confianca'
  | 'incerteza'
  | 'proxima-acao'
  | 'objetivo'
  | 'estado'
  | 'proximo-passo'
  | 'procedencia'
  // Seções da deliberação observável: o pedido, o que foi proposto e o que o quórum
  // concluiu. Entraram em 3.5-D, quando o conteúdo dessas execuções deixou de ficar
  // só em disco.
  | 'tarefa'
  | 'artefato'
  | 'sintese';

export interface PanelLine {
  /** Seção a que a frase pertence; o renderizador agrupa por ela. */
  section: SectionId;
  text: string;
  /** Maior sobrevive primeiro quando o orçamento de texto aperta. */
  priority: number;
}

export interface PanelAnchors {
  out: PanelEdgeSide;
  in: PanelEdgeSide;
}

/**
 * Truncamento: o título encurta, o corpo some inteiro.
 *
 * Cortar uma frase no meio produz afirmação que o painel não fez. Um título
 * abreviado continua sendo um nome; meia sentença de evidência é outra evidência.
 */
export interface TruncationPolicy {
  titleMaxChars: number;
  titlePolicy: 'ellipsis';
  bodyPolicy: 'omit-whole-line';
}

export interface PanelDescriptor {
  entityId: string;
  panelType: PanelType;
  /** A silhueta desenhada. Quem dispõe texto precisa dela para caber dentro da forma. */
  shape: PanelShape;
  /** Categoria por extenso, nunca sigla: é ela que carrega a ontologia no cabeçalho. */
  category: string;
  header: string;
  title: string;
  subtitle: string | null;
  /** Largura dividida por altura. Comunica função; não comunica importância. */
  proportion: number;
  /** Degrau discreto de área. Igual para todo MOC, inclusive o de raiz. */
  sizeStep: number;
  paletteToken: string;
  variant: TypographicVariant;
  sections: SectionId[];
  /** Frases permitidas em cada nível, acumulativas na ordem de `LOD_ORDER`. */
  contentByLod: Record<LodLevel, PanelLine[]>;
  anchors: Record<RelationFamily, PanelAnchors>;
  /** `epistemic_status` para corpus, estado operacional para runtime. */
  state: string;
  emphasis: CanonicalState;
  /** Ordem de atendimento quando o orçamento de texto não cobre todos os painéis. */
  lodPriority: number;
  truncation: TruncationPolicy;
}

// --- gramática por tipo -----------------------------------------------------

// A proporção decide o tamanho do texto mais do que a área decide.
//
// O corpo é dimensionado pela **largura** disponível — é o comprimento da linha que
// manda, não a altura da placa —, e o quórum era retrato (3/4). Com a mesma área do MOC
// ele lia com fonte 0,41 contra 0,68: os painéis da nuvem operacional pareciam sussurrar
// ao lado dos do corpus, e o rótulo acima deles, que é múltiplo da mesma fonte, encolhia
// junto. Deitar o quórum devolve a largura sem lhe dar área nenhuma a mais.
const PROPORTION: Record<PanelType, number> = {
  moc: 16 / 9,
  note: 4 / 3,
  bridge: 21 / 9,
  quorum: 3 / 2,
  // A tarefa era o único painel quadrado, e o corpo é dimensionado pela largura: com
  // proporção 1 ela ficava com a menor fonte de todas — 0,41 contra 0,48 da nota e 0,78
  // do quórum. É o painel da nuvem viva, e era ele que aparecia ilegível. Deitada, ela
  // entra no mesmo padrão dos outros seis sem ganhar área nenhuma.
  task: 3 / 2,
  endpoint: 3 / 2,
  // O provedor é a âncora da nuvem de modelos, e lê como um MOC lê no corpus.
  provider: 16 / 9,
  // O trabalhador tem a proporção do provedor pelo mesmo motivo: é uma âncora, e o
  // painel dele é onde se configura o papel — leitura curta e três controles.
  worker: 16 / 9,
  evento: 3 / 2,
};

// Degraus discretos, como manda a ADR-001. Corpus acima de operacional; dentro do
// corpus, MOC e ponte no mesmo degrau — a ponte não é mais importante que o MOC.
/**
 * Degrau de tamanho por tipo.
 *
 * Quórum, tarefa e endpoint sobem um degrau. Eles não tinham menos a dizer que uma
 * nota — desde que a deliberação passou a chegar à cena, um painel de quórum carrega
 * tarefa, proposta, avaliação, motivo e apuração —, mas ocupavam menos espaço que ela
 * e o texto não cabia. O MOC fica onde estava: ele já comporta o que mostra.
 */
const SIZE_STEP: Record<PanelType, number> = {
  moc: 3,
  bridge: 3,
  note: 2,
  quorum: 3,
  task: 2,
  endpoint: 2,
  provider: 3,
  worker: 3,
  evento: 2,
};

const VARIANT: Record<PanelType, TypographicVariant> = {
  moc: 'ancora',
  bridge: 'travessia',
  note: 'densa',
  quorum: 'deliberativa',
  task: 'transitoria',
  endpoint: 'operacional',
  provider: 'ancora',
  worker: 'ancora',
  evento: 'operacional',
};

const SECTIONS: Record<PanelType, SectionId[]> = {
  moc: ['escopo', 'rotas', 'contagem'],
  bridge: ['liga', 'mecanismo', 'escopo-negativo'],
  note: ['descricao', 'claims', 'relacoes'],
  quorum: [
    'tarefa',
    'hipotese',
    'evidencias',
    'objecoes',
    'artefato',
    'votos',
    'sintese',
    'confianca',
    'incerteza',
    'proxima-acao',
  ],
  task: ['objetivo', 'estado', 'proximo-passo'],
  endpoint: ['estado', 'procedencia', 'contagem'],
  provider: ['contagem', 'estado'],
  worker: ['escopo', 'estado'],
  evento: ['estado', 'objetivo', 'votos', 'confianca', 'proximo-passo'],
};

/** Sem este bloco a ponte vira nota larga: ela precisa dizer o que **não** afirma. */
const MANDATORY_SECTION: Partial<Record<PanelType, SectionId>> = {
  bridge: 'escopo-negativo',
};

const CATEGORY: Record<PanelType, string> = {
  moc: 'Mapa de conteúdo',
  bridge: 'Ponte interdisciplinar',
  note: 'Nota',
  quorum: 'Deliberação',
  task: 'Tarefa',
  endpoint: 'Modelo',
  provider: 'Provedor',
  worker: 'Trabalhador',
  // A nuvem se chama RACIOCÍNIO, e a categoria do painel **não** pode: essa palavra está
  // na lista que protege contra vazamento de cadeia de pensamento, e um descritor que a
  // carregue faz o guarda disparar. O nome da nuvem é rótulo de cena e não atravessa o
  // descritor; a categoria atravessa. "Passo" diz o que o painel é sem tocar na palavra.
  evento: 'Passo',
};

// Dependência corre na vertical; contraste e evidência correm na horizontal. É o que
// faz a relação costurar painéis em vez de atravessá-los pelo meio.
const ANCHORS: Record<RelationFamily, PanelAnchors> = {
  prerequisite: { out: 'top', in: 'bottom' },
  extends: { out: 'bottom', in: 'top' },
  navigation: { out: 'bottom', in: 'top' },
  contrasts: { out: 'left', in: 'right' },
  evidence: { out: 'right', in: 'left' },
  operational: { out: 'right', in: 'left' },
  historical: { out: 'left', in: 'right' },
};

export const VERTICAL_RELATIONS: RelationFamily[] = ['prerequisite', 'extends', 'navigation'];
export const HORIZONTAL_RELATIONS: RelationFamily[] = [
  'contrasts',
  'evidence',
  'operational',
  'historical',
];

const TRUNCATION: TruncationPolicy = {
  titleMaxChars: 64,
  titlePolicy: 'ellipsis',
  bodyPolicy: 'omit-whole-line',
};

/** Domínio das notas de travessia. Acoplamento declarado, e preso por teste. */
export const BRIDGE_DOMAIN = 'pontes';

/** Domínios das nuvens operacionais. Acoplamento declarado, e preso por teste. */
export const MODEL_DOMAIN = 'operacional/modelos';
export const PROVIDER_DOMAIN = 'operacional/provedores';
export const WORKER_DOMAIN = 'operacional/trabalhadores';
export const QUORUM_DOMAIN = 'operacional/quorum';

const QUORUM_KINDS: EntityKind[] = [
  'quorum-panel',
  'quorum-member',
  'quorum-vote',
  'quorum-decision',
  'evidence',
  'rejection',
];
const TASK_KINDS: EntityKind[] = ['activity', 'proposal', 'temporary-file', 'commit'];

/** Proporção e degrau de um tipo, para quem precisa medir sem ter um nó em mãos. */
export function proportionOf(type: PanelType): number {
  return PROPORTION[type];
}

export function sizeStepOf(type: PanelType): number {
  return SIZE_STEP[type];
}

export function panelTypeOf(node: ProjectionNode): PanelType {
  if (node.kind === 'moc') return node.domainId === BRIDGE_DOMAIN ? 'bridge' : 'moc';
  // Provedor e modelo se reconhecem pelo que **declaram**, não pelo domínio em que
  // estão. Pelo domínio, os mesmos papéis na nuvem viva liam como deliberação: um modelo
  // que executou um evento aparecia com painel de quórum e categoria "Deliberação".
  const meta = node.operational;
  // **Evento nunca é modelo.** A regra por metadados dizia que provedor mais endpoint sem
  // painel era um modelo do registro, e um evento ao vivo declara exatamente isso: uma
  // chamada concluída passou a ser desenhada como painel de modelo, com categoria
  // "Modelo" e o texto de um catálogo. `eventType` é o que separa os dois, e só o evento
  // o tem.
  // **Todo evento da trilha viva é um passo de raciocínio.**
  //
  // Eles se espalhavam por dois tipos conforme o `kind` que a projeção lhes dava: uma
  // evidência registrada lia "Deliberação" e uma chamada iniciada lia "Tarefa", na mesma
  // nuvem e na mesma sequência. São passos do mesmo processo, e agora têm um tipo só —
  // com a categoria que nomeia a nuvem onde moram.
  const eEvento = meta?.eventType !== undefined;
  if (eEvento) return 'evento';
  // O trabalhador vem antes das regras por metadados: ele declara `role`, e `role`
  // também aparece em execução de modelo. Quem o distingue é o domínio, que é dele e
  // de mais ninguém.
  if (node.domainId === WORKER_DOMAIN) return 'worker';
  {
    if (meta?.modelCount !== undefined || (node.kind === 'agent' && meta?.provider !== undefined)) {
      return 'provider';
    }
    if (meta?.provider !== undefined && meta.endpoint !== undefined && meta.panelId === undefined) {
      return 'endpoint';
    }
  }
  if (node.domainId === PROVIDER_DOMAIN) return 'provider';
  if (node.domainId === MODEL_DOMAIN) return node.kind === 'agent' ? 'provider' : 'endpoint';
  if (node.kind === 'agent') return 'endpoint';
  if (QUORUM_KINDS.includes(node.kind)) return 'quorum';
  if (TASK_KINDS.includes(node.kind)) return 'task';
  return 'note';
}

/**
 * Largura e altura a partir de área constante por degrau.
 *
 * É aqui que "silhueta não vira grandeza" deixa de ser intenção e vira aritmética:
 * a área depende só do degrau, e a proporção só redistribui essa área.
 */
export function panelExtent(descriptor: PanelDescriptor): { width: number; height: number } {
  const area = descriptor.sizeStep * descriptor.sizeStep;
  const height = Math.sqrt(area / descriptor.proportion);
  return { width: height * descriptor.proportion, height };
}

// --- linguagem natural ------------------------------------------------------

/** Primeira letra maiúscula. O resumo do papel vem em minúscula, e frase começa em alta. */
function maiuscula(texto: string): string {
  return texto.length === 0 ? texto : texto[0]!.toUpperCase() + texto.slice(1);
}

function plural(n: number, singular: string, muitos: string): string {
  return n === 1 ? `1 ${singular}` : `${n} ${muitos}`;
}

// Nota de dívida: a ADR-002 dá como exemplo "Respondeu em 4,5 s na última sonda".
// `OperationalMetadata` não tem campo de latência, então essa frase **não** é
// construída aqui. Inventá-la a partir de outro campo seria dado fabricado; ela entra
// quando o contrato da projeção expuser a medição.

const ESTADO_EPISTEMICO: Record<string, string> = {
  established: 'consolidado',
  supported: 'sustentado por evidência',
  'model-dependent': 'dependente de modelo',
  hypothesis: 'em hipótese',
  speculative: 'especulativo',
  open: 'em aberto',
  refuted: 'refutado',
  operational: 'registro operacional',
  mixed: 'de status misto',
  quarantine: 'em quarentena',
};

const ACAO: Record<string, string> = {
  promote: 'promover a proposta',
  revise: 'revisar a proposta',
  reject: 'recusar a proposta',
  escalate: 'buscar mais avaliação',
};

/**
 * Três contagens existem no quórum e não podem ser confundidas:
 *
 * 1. **recebidos** — quantos avaliadores responderam;
 * 2. **estruturalmente válidos** — quantos couberam no schema fechado;
 * 3. **computados** — quantos entraram na decisão.
 *
 * Elas divergem: um voto pode ser válido e não contar, por abstenção declarada, por
 * exclusão do proponente ou por falta de diversidade. `validVotes` do contrato é a
 * terceira — o backend a calcula como `schema_valid e não abstenção`
 * (`quorum/engine.py`) — e é a única que chega ao navegador.
 *
 * As outras duas **não têm campo na projeção**. Enquanto não tiverem, esta frase diz
 * só o que sabe: dizer "recebeu N votos" a partir da contagem de computados apagaria
 * exatamente a distinção que o painel existe para mostrar.
 *
 * Dívida de contrato registrada, a ser paga pelo backend:
 *
 * ```text
 * receivedVotes     quantos avaliadores responderam
 * schemaValidVotes  quantos couberam no schema fechado
 * countedVotes      quantos entraram na decisão   (hoje chamado validVotes)
 * ```
 *
 * `validVotes` está mal nomeado: ele é o terceiro. A interface o trata como
 * `countedVotes` e nunca como total recebido nem como total estruturalmente válido.
 */
function descreveVotos(meta: OperationalMetadata): string | null {
  const computados = meta.validVotes;
  if (computados === undefined) return null;
  const provedores = meta.providerCount;
  const familias = meta.familyCount;
  const partes = [`A decisão computou ${plural(computados, 'voto', 'votos')}`];
  const representacao: string[] = [];
  if (provedores !== undefined) {
    representacao.push(plural(provedores, 'provedor', 'provedores'));
  }
  if (familias !== undefined) {
    representacao.push(`${plural(familias, 'família', 'famílias')} de modelo`);
  }
  if (representacao.length > 0) partes.push(`representando ${representacao.join(' e ')}`);
  return `${partes.join(', ')}.`;
}

function descreveDecisao(meta: OperationalMetadata): string | null {
  if (meta.decision === undefined) return null;
  const legenda: Record<string, string> = {
    approve: 'Este avaliador foi favorável',
    reject: 'Este avaliador foi contrário',
    revise: 'Este avaliador pediu revisão',
    abstain: 'Este avaliador se absteve',
  };
  const base = legenda[meta.decision] ?? 'Este avaliador respondeu';
  if (meta.confidence === undefined) return `${base}.`;
  const pct = Math.round(meta.confidence * 100);
  return `${base}, com ${pct}% de confiança declarada.`;
}

function descreveLeitura(meta: OperationalMetadata): string | null {
  if (meta.schemaValid === undefined) return null;
  // Passar na estrutura não é o mesmo que contar: um voto válido ainda pode ficar
  // fora por abstenção declarada, por vir do proponente ou por não somar diversidade.
  return meta.schemaValid
    ? 'A resposta passou pela validação estrutural.'
    : 'A resposta não contou porque falhou na estrutura exigida.';
}

function descreveEndpoint(meta: OperationalMetadata): string | null {
  if (meta.provider === undefined) return null;
  const familia = meta.family ? `, da família ${meta.family}` : '';
  return `Atendido pelo provedor ${meta.provider}${familia}.`;
}

/**
 * O que um provedor reúne, e o quanto ele foi usado.
 *
 * É o mesmo papel que a contagem tem num MOC: o painel-âncora responde "quantos e
 * quanto" antes de qualquer navegação. Sem isto, o provedor era um painel com um nome
 * e mais nada, e a nuvem de modelos não dizia quem carregou o trabalho.
 */
function descreveProvedor(meta: OperationalMetadata): string | null {
  if (meta.modelCount === undefined) return null;
  const modelos = plural(meta.modelCount, 'modelo', 'modelos');
  if (meta.executionCount === undefined) return `Reúne ${modelos}.`;
  return `Reúne ${modelos}, com ${plural(meta.executionCount, 'participação', 'participações')} em execuções de quórum.`;
}

/** Quanto um modelo trabalhou. A carga é o que distingue um modelo do outro aqui. */
function descreveCarga(meta: OperationalMetadata): string | null {
  if (meta.executionCount === undefined) return null;
  // Zero não é ausência de informação: é a informação de que o modelo está instalado e
  // nunca foi chamado, e some se a frase for escrita só para quem tem contagem.
  if (meta.executionCount === 0) return 'Ainda não participou de nenhuma execução.';
  return `Avaliou em ${plural(meta.executionCount, 'execução', 'execuções')}.`;
}

/**
 * O que a sonda mais recente observou naquele endpoint.
 *
 * Um catálogo que mostrasse os 30 endpoints com o mesmo peso mentiria por omissão: no
 * Ollama Cloud, 11 dos 18 respondem 403 por estarem fora do plano. Estar listado e
 * estar disponível são coisas diferentes, e é esta linha que as separa.
 */
const ESTADO_DO_ENDPOINT: Record<string, string> = {
  ok: 'Responde no plano gratuito.',
  reachable: 'Alcançável, mas não devolveu texto na sonda.',
  rate_limited: 'Alcançável, com limite de taxa atingido na sonda.',
  account_exhausted: 'Conta sem crédito neste provedor.',
  auth: 'Recusado por credencial.',
  unavailable: 'Fora do plano gratuito neste provedor.',
  error: 'A sonda falhou.',
};

function descreveEstado(meta: OperationalMetadata): string | null {
  if (meta.endpointStatus === undefined) return null;
  return ESTADO_DO_ENDPOINT[meta.endpointStatus] ?? 'Estado não observado.';
}

/**
 * O que está acontecendo, em português, a partir dos campos do evento.
 *
 * Não é invenção: cada frase usa só o que o evento declara. É a leitura possível de um
 * processo observável — o que foi pedido, a quem, sobre o quê, e o que voltou.
 */
const ACAO_DO_EVENTO: Record<string, string> = {
  task_created: 'Uma tarefa entrou na fila.',
  task_assigned: 'A tarefa foi atribuída a um trabalhador.',
  call_started: 'Uma chamada ao modelo começou; a resposta ainda não voltou.',
  call_completed: 'A chamada ao modelo terminou.',
  vote_requested: 'Um avaliador foi convidado a votar.',
  vote_received: 'O voto chegou e passou pela validação.',
  evidence_recorded: 'Uma evidência foi registrada na trilha.',
  proposal_created: 'Uma proposta foi redigida e está à espera de quórum.',
  quorum_started: 'O quórum abriu e começou a coletar votos.',
  quorum_decided: 'O quórum fechou e decidiu.',
  temporary_created: 'Um arquivo temporário foi criado fora do corpus.',
  rejection_recorded: 'Uma recusa foi registrada com o motivo dela.',
};

function descreveEventoVivo(meta: OperationalMetadata): string | null {
  if (meta.eventType === undefined) return null;
  const base = ACAO_DO_EVENTO[meta.eventType];
  if (base === undefined) return null;
  // O que o evento trouxe de resultado entra na mesma frase: sem isso, "o voto chegou"
  // não diz qual foi, e o painel volta a ser um aviso em vez de uma leitura.
  if (meta.decision !== undefined) {
    const legenda: Record<string, string> = {
      approve: 'foi favorável',
      reject: 'foi contrário',
      revise: 'pediu revisão',
      abstain: 'se absteve',
    };
    const veredito = legenda[meta.decision] ?? 'respondeu';
    const confianca =
      meta.confidence === undefined ? '' : `, com ${Math.round(meta.confidence * 100)}% de confiança`;
    return `${base} O avaliador ${veredito}${confianca}.`;
  }
  if (meta.action !== undefined) {
    // O mesmo vocabulário do painel de quórum: duas legendas para a mesma ação fariam a
    // cena dizer "promover ao corpus" num lugar e "promover a proposta" no outro.
    return `${base} A ação escolhida foi ${ACAO[meta.action] ?? meta.action}.`;
  }
  return base;
}

/** Quem agiu: o modelo quando há um, o trabalhador quando não há. */
function descreveQuemAgiu(meta: OperationalMetadata): string | null {
  if (meta.provider !== undefined && meta.endpoint !== undefined) {
    return `Quem executou: ${meta.provider} · ${meta.endpoint}.`;
  }
  if (meta.actor !== undefined) return `Quem executou: ${meta.actor}.`;
  return null;
}

/** Sobre o que: a entidade do corpus, se houver; a tarefa, na falta dela. */
function descreveSobreOQue(meta: OperationalMetadata): string | null {
  if (meta.entity !== undefined) return `Sobre: ${meta.entity}.`;
  if (meta.task !== undefined) return `Tarefa: ${textoCorrido(meta.task)}.`;
  return null;
}

/** Quantos dos modelos de um provedor responderam de fato. */
function descreveDisponiveis(meta: OperationalMetadata): string | null {
  if (meta.availableCount === undefined || meta.modelCount === undefined) return null;
  return `${meta.availableCount} de ${meta.modelCount} responderam na última sonda.`;
}

// --- construção do descritor ------------------------------------------------

function vazio(): Record<LodLevel, PanelLine[]> {
  return { distant: [], structural: [], identifiable: [], legible: [], expanded: [] };
}

function corpusLines(node: ProjectionNode, tipo: PanelType): Record<LodLevel, PanelLine[]> {
  const content = vazio();
  const estado = ESTADO_EPISTEMICO[node.epistemicStatus] ?? node.epistemicStatus;

  if (tipo === 'bridge') {
    const [a, b] = node.title.replace(/^Ponte\s+—\s+/, '').split(/\s+e\s+|\s+↔\s+/);
    content.legible.push({
      section: 'liga',
      text: b ? `Liga ${a} e ${b}.` : `Organiza travessias entre domínios.`,
      priority: 90,
    });
    content.legible.push({
      section: 'mecanismo',
      text: `Reúne ${plural(node.incomingDegree + node.outgoingDegree, 'aresta já declarada', 'arestas já declaradas')} entre notas existentes; não cria relação nova.`,
      priority: 80,
    });
    content.expanded.push({
      section: 'escopo-negativo',
      text: 'Vocabulário compartilhado não funda ligação: o que não tem mecanismo declarado fica de fora.',
      priority: 70,
    });
  } else if (tipo === 'moc') {
    content.legible.push({
      section: 'escopo',
      text: `Organiza o domínio ${node.domainLabel}.`,
      priority: 90,
    });
    content.legible.push({
      section: 'contagem',
      text: `Aponta para ${plural(node.outgoingDegree, 'nota', 'notas')} e é citado por ${plural(node.incomingDegree, 'outra', 'outras')}.`,
      priority: 80,
    });
    content.expanded.push({
      section: 'rotas',
      text: `Estado do conjunto: ${estado}.`,
      priority: 60,
    });
  } else {
    content.legible.push({
      section: 'descricao',
      text: `Nota de ${node.domainLabel}, ${estado}.`,
      priority: 90,
    });
    // A abertura da nota, quando ela existe. Entra em `expanded` porque é prosa: lida
    // de longe ela seria ruído, e lida de perto é a primeira coisa que se quer.
    if (node.summary) {
      content.expanded.push({ section: 'descricao', text: node.summary, priority: 88 });
    }
    for (const [ordem, claim] of (node.claims ?? []).entries()) {
      const estadoDoClaim = ESTADO_EPISTEMICO[claim.status] ?? claim.status;
      content.expanded.push({
        section: 'claims',
        text: `${claim.id} — ${claim.statement} [${estadoDoClaim}]`,
        // Decrescente pela ordem no arquivo: quando o orçamento apertar, some do fim,
        // que é onde a nota já pôs o que depende do que veio antes.
        priority: 80 - ordem,
      });
      if (claim.evidence) {
        content.expanded.push({
          section: 'evidencias',
          text: `Evidência de ${claim.id}: ${claim.evidence}`,
          priority: 79 - ordem,
        });
      }
    }
    if (node.claimCount > 0) {
      content.legible.push({
        section: 'claims',
        text: `Sustenta ${plural(node.claimCount, 'afirmação com status próprio', 'afirmações com status próprio')}.`,
        priority: 80,
      });
    }
    content.expanded.push({
      section: 'relacoes',
      text: `Depende de ${plural(node.incomingDegree, 'nota', 'notas')} e é usada por ${plural(node.outgoingDegree, 'outra', 'outras')}.`,
      priority: 60,
    });
  }

  if (node.updatedAt) {
    content.expanded.push({
      section: tipo === 'note' ? 'relacoes' : 'contagem',
      text: `Última edição em ${node.updatedAt}.`,
      priority: 30,
    });
  }
  return content;
}

function operationalLines(
  node: ProjectionNode,
  tipo: PanelType,
): Record<LodLevel, PanelLine[]> {
  const content = vazio();
  // Lista branca explícita: nenhum campo desconhecido do runtime vira frase, e
  // resposta de modelo, prompt e raciocínio não têm campo por onde entrar.
  const meta = node.operational ?? {};

  // O que está acontecendo agora vale para **qualquer** tipo de painel vivo.
  //
  // A frase morava só no ramo de tarefa, e a maioria dos eventos não passa por ele: um
  // voto recebido é projetado como `quorum-vote` e caía no ramo de deliberação, onde a
  // frase não existia. Quem decide se ela entra é o evento ter tipo, não o painel.
  if (meta.eventType !== undefined) {
    const frase = meta.narration ? textoCorrido(meta.narration) : descreveEventoVivo(meta);
    if (frase) content.identifiable.push({ section: 'estado', text: frase, priority: 99 });
    const quem = descreveQuemAgiu(meta);
    if (quem) content.legible.push({ section: 'estado', text: quem, priority: 90 });
    const sobre = descreveSobreOQue(meta);
    if (sobre) content.legible.push({ section: 'objetivo', text: sobre, priority: 89 });
    // A apuração é **conteúdo**, e não propriedade do ramo em que o painel caiu: um
    // evento de quórum decidido carrega a contagem e a representação, e elas sumiram
    // quando ele deixou de ser desenhado como painel de deliberação.
    const votos = descreveVotos(meta);
    if (votos) content.legible.push({ section: 'votos', text: votos, priority: 88 });
    const leitura = descreveLeitura(meta);
    if (leitura) content.expanded.push({ section: 'confianca', text: leitura, priority: 60 });
  }

  if (tipo === 'quorum') {
    if (meta.narration && meta.eventType === undefined) {
      content.identifiable.push({
        section: 'estado',
        text: textoCorrido(meta.narration),
        priority: 99,
      });
    }
    // Modelo do registro: ele não pertence a execução nenhuma, e o que tem a dizer é
    // de quem é e quanto trabalhou.
    const carga = descreveCarga(meta);
    if (carga) content.legible.push({ section: 'contagem', text: carga, priority: 97 });
    const procedencia = descreveEndpoint(meta);
    if (procedencia && meta.panelId === undefined) {
      content.legible.push({ section: 'procedencia', text: procedencia, priority: 96 });
    }
    // A deliberação primeiro: é o que o usuário veio ver. Contagens e procedência
    // continuam existindo, mas atrás do que a execução tem a dizer.
    if (meta.task) {
      content.legible.push({
        section: 'tarefa',
        text: `Tarefa: ${textoCorrido(meta.task)}`,
        priority: 98,
      });
    }
    if (meta.candidate) {
      content.expanded.push({
        section: 'artefato',
        text: `Proposta: ${textoCorrido(meta.candidate)}`,
        priority: 88,
      });
    }
    if (meta.assessment) {
      content.legible.push({
        section: 'evidencias',
        text: `Examinou: ${textoCorrido(meta.assessment)}`,
        priority: 92,
      });
    }
    if (meta.blockingIssue) {
      content.legible.push({
        section: 'objecoes',
        text: `A política recusou: ${textoCorrido(meta.blockingIssue)}`,
        priority: 86,
      });
    }
    // O gate estrutural tem um rótulo opaco. Quando a regra quebrou já chegou,
    // o rótulo não acrescenta leitura — só repete que houve recusa.
    if (
      meta.reason &&
      !(
        meta.reason === 'falha estrutural objetiva registrada' &&
        meta.blockingIssue
      )
    ) {
      content.legible.push({
        section: 'votos',
        text: `Motivo: ${textoCorrido(meta.reason)}`,
        priority: 84,
      });
    }
    if (meta.synthesis) {
      content.expanded.push({
        section: 'sintese',
        text: `Síntese: ${meta.synthesis}`,
        priority: 82,
      });
    }
    const votos = descreveVotos(meta);
    if (votos) content.legible.push({ section: 'votos', text: votos, priority: 90 });
    const decisao = descreveDecisao(meta);
    if (decisao) content.legible.push({ section: 'votos', text: decisao, priority: 85 });
    const leitura = descreveLeitura(meta);
    if (leitura) content.expanded.push({ section: 'objecoes', text: leitura, priority: 70 });
    if (meta.action) {
      content.legible.push({
        section: 'proxima-acao',
        text: `Próxima ação: ${ACAO[meta.action] ?? meta.action}.`,
        priority: 80,
      });
    }
    if (meta.validVotes !== undefined && meta.validVotes < 3) {
      content.expanded.push({
        section: 'incerteza',
        text: 'Faltou avaliador legível para o painel poder decidir.',
        priority: 65,
      });
    }
  } else if (tipo === 'worker') {
    // O painel diz o que o papel **é**; o que ele está fazendo agora — provedor
    // resolvido, simultâneas efetivas, se está ligado — vem do painel de controle, e
    // aparece na face. Repetir aqui um estado gravado na projeção faria a placa
    // afirmar a resolução de ontem.
    if (meta.summary) {
      content.identifiable.push({ section: 'escopo', text: `${maiuscula(meta.summary)}.`, priority: 93 });
    }
    if (meta.workerClass) {
      content.legible.push({
        section: 'estado',
        text:
          meta.workerClass === 'avaliador'
            ? 'Avalia proposta alheia: conta para o mínimo de votos.'
            : 'Produz a alteração; não conta como avaliador.',
        priority: 92,
      });
    }
    if (meta.area) {
      content.legible.push({ section: 'escopo', text: `Age em ${meta.area}.`, priority: 91 });
    }
    // O teto do papel **não** entra: a face o diz no rótulo do próprio controle
    // ("Simultâneas (máximo 3)"), e dito duas vezes ele ocupa uma linha da superfície
    // de leitura para não acrescentar nada.
  } else if (tipo === 'provider' || tipo === 'endpoint') {
    // A âncora diz o que reúne; a folha diz de quem é e quanto trabalhou. É a mesma
    // divisão que MOC e nota fazem no corpus, e por isso não precisa ser aprendida.
    const reune = descreveProvedor(meta);
    if (reune) content.legible.push({ section: 'contagem', text: reune, priority: 92 });
    const disponiveis = descreveDisponiveis(meta);
    if (disponiveis) {
      content.legible.push({ section: 'estado', text: disponiveis, priority: 91.5 });
    }
    // O que o modelo está fazendo **agora**, antes do que o catálogo diz dele.
    //
    // A projeção já escrevia esta frase no nó do modelo, e nenhum ramo a desenhava: o
    // painel de endpoint é o único que não a tinha, e por isso o estado temporal do
    // modelo — inclusive o raciocínio que o provedor emite — era dado morto. Vale a
    // mesma guarda dos outros ramos: narração de evento pertence ao evento.
    if (meta.narration && meta.eventType === undefined) {
      content.identifiable.push({
        section: 'estado',
        text: textoCorrido(meta.narration),
        priority: 94,
      });
    }
    const estado = descreveEstado(meta);
    if (estado) content.identifiable.push({ section: 'estado', text: estado, priority: 93 });
    const carga = descreveCarga(meta);
    if (carga && meta.modelCount === undefined) {
      content.legible.push({ section: 'contagem', text: carga, priority: 91 });
    }
    // "Atendido pelo provedor groq" no painel do próprio groq é tautologia: a
    // procedência só informa quando quem a diz não é o provedor.
    const proc = meta.modelCount === undefined ? descreveEndpoint(meta) : null;
    if (proc) content.legible.push({ section: 'procedencia', text: proc, priority: 90 });
    if (meta.role) {
      content.expanded.push({
        section: 'estado',
        text: `Trabalha como ${meta.role}.`,
        priority: 60,
      });
    }
  } else {
    // O que está sendo feito agora vem antes do que aconteceu: um painel de worker em
    // execução dizia apenas "Registro operacional de call_started", e o usuário ficava
    // sabendo que algo acontecia sem saber o quê.
    // **Só quando o evento não a trouxe.** O primeiro bloco desta função já escreve a
    // narração de todo painel que declara `eventType`, e este ramo a escrevia de novo:
    // duas linhas idênticas em prioridades diferentes, que é o texto duplicado que
    // aparecia na nuvem de raciocínio — onde quase todo painel é um evento com narração.
    // O guarda é o mesmo que o ramo de quórum já usava.
    if (meta.narration && meta.eventType === undefined) {
      content.identifiable.push({
        section: 'estado',
        text: textoCorrido(meta.narration),
        priority: 95,
      });
    }
  }
  return content;
}

/**
 * O descritor de um nó. Determinístico: mesma entrada, mesma saída.
 *
 * `entityId` é o `id` do nó e não muda com o nível de LOD — aproximar amplia o mesmo
 * painel, não instancia outro. Seleção, foco e ligação continuam presas a este campo.
 */
export function describePanel(node: ProjectionNode): PanelDescriptor {
  const panelType = panelTypeOf(node);
  const isCorpus = node.layer === 'epistemic';
  const content = isCorpus ? corpusLines(node, panelType) : operationalLines(node, panelType);

  const category = CATEGORY[panelType];
  content.structural.push({ section: 'estado', text: category, priority: 100 });
  content.identifiable.push({ section: 'estado', text: node.shortLabel, priority: 95 });

  const sections = [...SECTIONS[panelType]];
  const obrigatoria = MANDATORY_SECTION[panelType];
  if (obrigatoria && !sections.includes(obrigatoria)) sections.push(obrigatoria);

  return {
    entityId: node.id,
    panelType,
    shape: shapeOf(node.kind),
    category,
    header: `${category} · ${node.domainLabel}`,
    title: node.title,
    subtitle: isCorpus ? node.domainLabel : (node.operational?.provider ?? null),
    proportion: PROPORTION[panelType],
    sizeStep: SIZE_STEP[panelType],
    paletteToken: node.visual.paletteToken,
    variant: VARIANT[panelType],
    sections,
    contentByLod: content,
    anchors: ANCHORS,
    state: isCorpus ? node.epistemicStatus : (node.operational?.eventType ?? 'operacional'),
    emphasis: node.canonicalState,
    // Prioridade vem do grau, como já vinha em `visual.labelPriority`. Proporção não
    // entra na conta: painel largo não fura fila de leitura.
    lodPriority: node.visual.labelPriority,
    truncation: TRUNCATION,
  };
}

/** Frases visíveis até um nível, acumuladas na ordem de `LOD_ORDER`. */
export function linesUpTo(descriptor: PanelDescriptor, level: LodLevel): PanelLine[] {
  const limite = LOD_ORDER.indexOf(level);
  const reunidas: PanelLine[] = [];
  for (const [indice, nivel] of LOD_ORDER.entries()) {
    if (indice > limite) break;
    reunidas.push(...descriptor.contentByLod[nivel]);
  }
  return reunidas.sort((a, b) => b.priority - a.priority);
}

export function describePanels(nodes: ProjectionNode[]): PanelDescriptor[] {
  return nodes.map(describePanel);
}
