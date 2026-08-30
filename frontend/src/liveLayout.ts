import type { Projection } from './contract';
import { type Vec3 } from './layout';
import { type OperationalPlacement } from './operationalLayout';
import { isModelNode, type ModelPlacement } from './modelsLayout';

export interface LiveCloud {
  /** painelNodeId -> centro da execução no frame da nuvem viva. */
  execucoes: Map<string, Vec3>;
  /** modelId -> centro do modelo no frame da nuvem viva. */
  modelos: Map<string, Vec3>;
}

/**
 * Assenta a nuvem viva, no frame dela.
 *
 * `operacional` e `computacao` chegam em seus próprios frames (cada um centrado na
 * origem); o chamador é quem translada o resultado para o lugar da cena. As execuções
 * que se ancoram num assunto do corpus ficam de fora — elas orbitam o corpus, e não
 * pertenceem à constelação viva.
 *
 * A dinâmica de repulsão e atração que o usuário pediu vira isto: as execuções mantêm o
 * seu leque repulsivo, que já garante que nenhuma placa cobre a outra, e cada modelo é
 * atraído para o centro de massa das execuções que o avaliam. O subgrafo em estrela
 * colapsa em torno do hub — a aresta `quorum-model` que antes varria a cena, de uma
 * nuvem de execuções lonjura a uma calota de modelos, agora nasce curta, porque o modelo
 * mora no meio das execuções que o invocam. Nada é escondido: o fio continua lá, só
 * deixou de atravessar o vazio.
 */
export function layoutLiveCloud(
  projection: Projection,
  operacional: OperationalPlacement,
  computacao: ModelPlacement,
  slotsConhecidos?: OperationalPlacement['slots'],
): LiveCloud {
  void slotsConhecidos;
  const ancoradas = new Set<string>();
  for (const edge of projection.edges) {
    if (edge.matchedBy === 'quorum-entity') ancoradas.add(edge.source);
  }

  // As execuções ficam onde o leque repulsivo as deixou: garantidamente sem sobreposição.
  const execucoes = new Map<string, Vec3>();
  for (const sistema of operacional.systems) {
    if (sistema.panelNodeId === null) continue;
    if (ancoradas.has(sistema.panelNodeId)) continue;
    const p = operacional.positions.get(sistema.panelNodeId);
    if (!p) continue;
    execucoes.set(sistema.panelNodeId, { x: p.x, y: p.y, z: p.z });
  }

  // Cada modelo é atraído para o centro de massa das execuções que o avaliam.
  const execPorModelo = new Map<string, Vec3[]>();
  for (const edge of projection.edges) {
    if (edge.matchedBy !== 'quorum-model') continue;
    const centro = execucoes.get(edge.source);
    if (!centro) continue;
    const lista = execPorModelo.get(edge.target);
    if (lista) lista.push(centro);
    else execPorModelo.set(edge.target, [centro]);
  }

  const modelos = new Map<string, Vec3>();
  for (const [id, p] of computacao.positions) {
    const no = projection.nodes.find((n) => n.id === id);
    if (!no) continue;
    if (!isModelNode(no)) continue;
    const execs = execPorModelo.get(id);
    if (execs && execs.length > 0) {
      let x = 0;
      let y = 0;
      let z = 0;
      for (const c of execs) {
        x += c.x;
        y += c.y;
        z += c.z;
      }
      const n = execs.length;
      modelos.set(id, { x: x / n, y: y / n, z: z / n });
    } else {
      // Modelo sem execução apontando para ele: mantém o posto da calota.
      modelos.set(id, { x: p.x, y: p.y, z: p.z });
    }
  }

  return { execucoes, modelos };
}
