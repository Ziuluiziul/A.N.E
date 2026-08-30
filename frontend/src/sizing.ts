// Tamanho por classe, em degraus discretos.
//
// O raio não pode medir grau, claims e importância ao mesmo tempo: uma esfera maior
// que combina três variáveis não declaradas não informa nada. Aqui o tamanho diz
// apenas de que tipo é a entidade, e a métrica quantitativa fica para uma lente
// analítica futura, com legenda própria.

import type { EntityKind } from './contract';

export const BASE_RADIUS: Record<EntityKind, number> = {
  moc: 2.6,
  register: 1.5,
  reference: 1.4,
  note: 1.05,
  // Operacionais: menores que a nota canônica, porque procedência acompanha o
  // conhecimento e não compete com ele pela atenção.
  agent: 1.2,
  activity: 1.15,
  evidence: 0.75,
  proposal: 1.0,
  commit: 0.9,
  rejection: 1.0,
  'temporary-file': 1.1,
  'quorum-panel': 1.2,
  'quorum-member': 0.82,
  'quorum-vote': 0.78,
  'quorum-decision': 1.05,
};

/** Faixa de `z` por tipo. Profundidade separa camadas; não mede nada. */
export const Z_LAYER: Record<EntityKind, number> = {
  moc: 1.8,
  register: 0.9,
  reference: 0.7,
  note: 0,
  // A rede operacional vive numa faixa própria, acima da epistêmica: coordenada com
  // ela, e visivelmente não misturada.
  agent: 5,
  activity: 4.6,
  proposal: 4.4,
  rejection: 4.4,
  evidence: 4.2,
  commit: 4.8,
  'temporary-file': 3.8,
  'quorum-panel': 5.6,
  'quorum-member': 5.2,
  'quorum-vote': 4.8,
  'quorum-decision': 5.4,
};
