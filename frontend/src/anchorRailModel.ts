// O índice das referências espaciais do Atlas.
//
// O rail não decide o que é fixo. Essa política já viaja na projeção persistente como
// `visual.isAnchor`, usada pelo layout; duplicá-la por `kind` faria interface e mundo
// divergirem no primeiro tipo novo de âncora. Raízes efêmeras da trilha viva não entram:
// elas organizam eventos, mas não são os painéis principais estáveis que orientam a
// câmera e abrem configuração.

import type { Projection, ProjectionNode } from './contract';
import { PROVIDER_DOMAIN, WORKER_DOMAIN } from './modelsLayout';

export type AnchorGroup = 'knowledge' | 'providers' | 'workers' | 'operation';

/**
 * De que lado da tela cada grupo se assenta.
 *
 * Uma régua só, à direita: provedores em cima — são poucos e procurados primeiro —
 * e o conhecimento logo abaixo, na mesma peça. A esquerda ficou para a cena e para
 * o cartão de atividade.
 */
export type AnchorSide = 'esquerda' | 'direita';

export const ANCHOR_SIDE: Record<AnchorGroup, AnchorSide> = {
  knowledge: 'direita',
  providers: 'direita',
  workers: 'direita',
  operation: 'direita',
};

/**
 * Os grupos que a régua **não** oferece.
 *
 * Trabalhador saiu da navegação: sete papéis de configuração não são destino de câmera,
 * e ocupavam um terço de uma régua cuja função é chegar a território. Eles continuam na
 * cena e continuam selecionáveis — o que sai é o atalho, não a entidade.
 */
const FORA_DA_REGUA: ReadonlySet<AnchorGroup> = new Set<AnchorGroup>(['workers']);

export interface AnchorTarget {
  id: string;
  label: string;
  name: string;
  group: AnchorGroup;
  paletteToken: string;
}

export const ANCHOR_GROUP_LABEL: Record<AnchorGroup, string> = {
  knowledge: 'Conhecimento',
  providers: 'Provedores',
  workers: 'Trabalhadores',
  operation: 'Operação',
};

const GROUP_ORDER: AnchorGroup[] = ['providers', 'knowledge', 'workers', 'operation'];

function groupOf(node: ProjectionNode): AnchorGroup {
  if (node.layer === 'epistemic') return 'knowledge';
  if (node.domainId === PROVIDER_DOMAIN) return 'providers';
  if (node.domainId === WORKER_DOMAIN) return 'workers';
  return 'operation';
}

/**
 * O nome que o botão mostra.
 *
 * É o rótulo curto da própria projeção, sem reescrita: `MOC — Física Teórica`, `groq`,
 * `critico-epistemologico`. Inventar uma forma de exibição aqui faria a régua discordar
 * do painel e do log, que chamam a mesma coisa pelo nome do sistema. `MOC —` e `Ponte —`
 * ficam porque distinguem núcleo de travessia dentro do mesmo grupo — o grupo diz
 * "Conhecimento", não qual dos dois. O título inteiro continua em `aria-label` e tooltip,
 * que é onde a linha cortada por elipse se completa.
 */
export function anchorName(node: Pick<ProjectionNode, 'shortLabel' | 'title'>): string {
  return node.shortLabel.trim() || node.title.trim();
}

export function anchorTargets(projection: Projection): AnchorTarget[] {
  return projection.nodes
    .filter((node) => node.visual.isAnchor)
    .map((node) => ({
      id: node.id,
      label: node.title,
      name: anchorName(node),
      group: groupOf(node),
      paletteToken: node.visual.paletteToken,
    }))
    .filter((target) => !FORA_DA_REGUA.has(target.group))
    .sort(
      (left, right) =>
        GROUP_ORDER.indexOf(left.group) - GROUP_ORDER.indexOf(right.group) ||
        left.label.localeCompare(right.label, 'pt-BR'),
    );
}
