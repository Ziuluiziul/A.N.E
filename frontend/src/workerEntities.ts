// O trabalhador como entidade do runtime — ADR-005, primeira transferência de propriedade.
//
// Aqui mora só a construção do nó a partir do que o snapshot de controle declara. A
// geometria não entra: quem a fornece é `workerAnchorPoses`, injetada em quem possui a
// entidade. Se este módulo soubesse raio ou ângulo, o runtime passaria a possuir também
// uma parte do layout, e a separação que a ADR fixou voltaria a se misturar.
//
// **Por que o descritor visual vem do controle e não daqui.** A cor de um trabalhador
// segue uma regra que depende da ordem do papel e de ele avaliar ou produzir, e essa
// regra vive no backend. Reimplementá-la neste arquivo quebraria a identidade visual em
// silêncio no dia em que alguém mexesse num dos dois lados — que é exatamente o defeito
// que o gate de paridade da migração procura. Quem possui a entidade descreve a entidade.

import type { ProjectionNode } from './contract';

/** O que o snapshot de controle afirma sobre um trabalhador. */
export interface RuntimeWorker {
  id: string;
  role: string;
  className: string;
  summary: string;
  area: string;
  paletteToken: string;
  concurrencyMax: number;
}

export const WORKER_DOMAIN = 'operacional/trabalhadores';
const WORKER_DOMAIN_LABEL = 'trabalhadores';

/**
 * O instante que o nó declara.
 *
 * Fixo, e não `Date.now()`: o trabalhador é um papel do sistema, não um evento. Carimbar
 * a hora da leitura faria a mesma entidade parecer nova a cada sincronização, e qualquer
 * coisa que compare nós por conteúdo — cache de texto, assinatura de reconstrução —
 * passaria a reconstruir sete placas por polling.
 */
const NASCIMENTO_DO_PAPEL = '2026-08-02T12:00:00+00:00';

export function workerNodeId(role: string): string {
  return `op/worker/${role}`;
}

/**
 * O nó visual de um trabalhador, na forma que a projeção operacional produzia.
 *
 * A paridade é literal e é o gate da migração: mesma identidade, mesmo título, mesmo
 * rótulo curto, mesmo domínio, mesmo estado canônico, mesma âncora e mesmo token de
 * paleta. O que muda é **quem** o constrói.
 */
export function workerNode(worker: RuntimeWorker): ProjectionNode {
  return {
    id: workerNodeId(worker.role),
    title: `Trabalhador — ${worker.role}`,
    shortLabel: worker.role,
    path: null,
    kind: 'agent',
    layer: 'operational',
    canonicalState: 'canonical',
    epistemicStatus: 'not-specified',
    domainId: WORKER_DOMAIN,
    domainLabel: WORKER_DOMAIN_LABEL,
    anchorMocId: null,
    mocIds: [],
    claimCount: 0,
    incomingDegree: 0,
    outgoingDegree: 0,
    degreeByRelation: {},
    createdAt: NASCIMENTO_DO_PAPEL,
    updatedAt: NASCIMENTO_DO_PAPEL,
    verifiedAt: null,
    visual: {
      paletteToken: worker.paletteToken,
      lodClass: 1,
      labelPriority: 0,
      isAnchor: true,
    },
    operational: {
      role: worker.role,
      workerClass: worker.className,
      summary: worker.summary,
      area: worker.area,
      concurrencyMax: worker.concurrencyMax,
    },
  };
}

/**
 * A diferença entre dois rosters, por identidade.
 *
 * `undefined` e `[]` **não** significam a mesma coisa, e confundi-los é o defeito que
 * este contrato existe para impedir: ausência de informação viraria ausência das
 * entidades, e um polling que falhasse apagaria os sete da cena. `undefined` é "nenhum
 * snapshot novo, preserve"; `[]` é "o runtime afirma que não há nenhum".
 */
export interface WorkerDiff {
  created: RuntimeWorker[];
  updated: RuntimeWorker[];
  removed: string[];
  /** A composição de ids mudou, e só então os corpos precisam ser reconstruídos. */
  membershipChanged: boolean;
}

export function diffWorkers(
  atuais: ReadonlyMap<string, RuntimeWorker>,
  proximos: readonly RuntimeWorker[] | undefined,
): WorkerDiff {
  if (proximos === undefined) {
    return { created: [], updated: [], removed: [], membershipChanged: false };
  }
  const porId = new Map(proximos.map((worker) => [worker.id, worker]));
  const created: RuntimeWorker[] = [];
  const updated: RuntimeWorker[] = [];
  for (const worker of porId.values()) {
    (atuais.has(worker.id) ? updated : created).push(worker);
  }
  const removed = [...atuais.keys()].filter((id) => !porId.has(id));
  return {
    created,
    updated,
    removed,
    membershipChanged: created.length > 0 || removed.length > 0,
  };
}
