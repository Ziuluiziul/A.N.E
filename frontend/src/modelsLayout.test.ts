// O que a região de computação precisa prender: o modelo mora junto do provedor.
//
// Estes testes reprovavam antes deste incremento. Provedores e modelos eram duas nuvens
// em lugares diferentes do mundo, e cada uma das 163 arestas provedor→modelo atravessava
// o vão entre elas — todas na mesma direção. Medido sobre a projeção real, a mediana
// dessas arestas era 210,0 unidades e o alinhamento das direções, 0,918: um feixe.

import { describe, expect, it } from 'vitest';

import { composeLayout } from './composeLayout';
import type { Projection, ProjectionNode } from './contract';
import { edge, node, projectionFixture } from './fixture';
import {
  MODEL_DOMAIN,
  PROVIDER_DOMAIN,
  WORKER_DOMAIN,
  layoutModels,
  workerAnchorPoses,
} from './modelsLayout';

function provedor(nome: string): ProjectionNode {
  return node(`op/provider/${nome}`, {
    kind: 'agent',
    layer: 'operational',
    path: null,
    canonicalState: 'temporary',
    domainId: PROVIDER_DOMAIN,
    domainLabel: 'provedores',
    operational: { provider: nome },
  });
}

function modelo(nome: string, endpoint: string): ProjectionNode {
  return node(`op/model/${nome}/${endpoint}`, {
    kind: 'quorum-member',
    layer: 'operational',
    path: null,
    canonicalState: 'temporary',
    domainId: MODEL_DOMAIN,
    domainLabel: 'modelos',
    operational: { provider: nome, endpoint },
  });
}

/** Quatro provedores com famílias de tamanhos diferentes, como o acervo real. */
function acervoFixture(porProvedor: Record<string, number>): Projection {
  const projection = projectionFixture();
  for (const [nome, quantos] of Object.entries(porProvedor)) {
    projection.nodes.push(provedor(nome));
    for (let i = 0; i < quantos; i += 1) {
      const endpoint = `m${String(i).padStart(2, '0')}`;
      projection.nodes.push(modelo(nome, endpoint));
      projection.edges.push(
        edge(`op/provider/${nome}`, `op/model/${nome}/${endpoint}`, 'operational', 'operational', {
          matchedBy: 'model-provider',
        }),
      );
    }
  }
  return projection;
}

const ACERVO = { groq: 48, cerebras: 12, ollama: 61, together: 42 };

 /** Comprimento de cada aresta provedor→modelo no mundo composto. */
function arestasDaFamilia(projection: Projection): number[] {
  const { positions } = composeLayout(projection);
  const saida: number[] = [];
  for (const e of projection.edges) {
    if (e.matchedBy !== 'model-provider') continue;
    const a = positions.get(e.source)!;
    const b = positions.get(e.target)!;
    saida.push(Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z));
  }
  return saida;
}

describe('a região de computação', () => {
  it('põe cada modelo mais perto do próprio provedor que de qualquer outro', () => {
    // É a afirmação inteira do incremento. Enquanto os provedores moravam numa nuvem
    // separada, isto era falso para todos os 163 modelos ao mesmo tempo: os quatro
    // provedores estavam juntos, longe, e a distância até o próprio não distinguia nada.
    const projection = acervoFixture(ACERVO);
    const { positions } = layoutModels(projection);
    const provedores = Object.keys(ACERVO).map((nome) => `op/provider/${nome}`);

    for (const node of projection.nodes) {
      if (node.domainId !== MODEL_DOMAIN) continue;
      const p = positions.get(node.id)!;
      const meu = `op/provider/${node.operational!.provider!}`;
      const distancias = provedores.map((id) => {
        const q = positions.get(id)!;
        return { id, d: Math.hypot(p.x - q.x, p.y - q.y, p.z - q.z) };
      });
      distancias.sort((a, b) => a.d - b.d);
      expect(distancias[0]!.id, node.id).toBe(meu);
    }
  });

  it('não deixa duas famílias se cobrirem', () => {
    const projection = acervoFixture(ACERVO);
    const { positions } = layoutModels(projection);
    // O centro de cada família e o alcance dela, medidos do que foi assentado.
    const familias = new Map<string, { pontos: { x: number; y: number; z: number }[] }>();
    for (const node of projection.nodes) {
      if (node.domainId !== MODEL_DOMAIN) continue;
      const chave = node.operational!.provider!;
      const grupo = familias.get(chave) ?? { pontos: [] };
      grupo.pontos.push(positions.get(node.id)!);
      familias.set(chave, grupo);
    }
    const medidas = [...familias].map(([chave, { pontos }]) => {
      const centro = pontos.reduce(
        (a, p) => ({ x: a.x + p.x / pontos.length, y: a.y + p.y / pontos.length, z: a.z + p.z / pontos.length }),
        { x: 0, y: 0, z: 0 },
      );
      const raio = Math.max(
        ...pontos.map((p) => Math.hypot(p.x - centro.x, p.y - centro.y, p.z - centro.z)),
      );
      return { chave, centro, raio };
    });
    for (let i = 0; i < medidas.length; i += 1) {
      for (let j = i + 1; j < medidas.length; j += 1) {
        const a = medidas[i]!;
        const b = medidas[j]!;
        const dist = Math.hypot(
          a.centro.x - b.centro.x,
          a.centro.y - b.centro.y,
          a.centro.z - b.centro.z,
        );
        expect(dist, `${a.chave} × ${b.chave}`).toBeGreaterThan(a.raio + b.raio);
      }
    }
  });

  it('a aresta provedor→modelo atravessa da calota até a nuvem viva', () => {
    // A reparentação: o modelo subiu com o quórum para a nuvem viva (topo da coluna), e o
    // provedor ficou na calota. A aresta não é mais curta — ela é a travessia honesta
    // entre as duas regiões, e não o feixe que escondíamos. Ela precisa sair da nuvem viva
    // para alcançar a calota.
    const projection = acervoFixture(ACERVO);
    const { positions, extent } = composeLayout(projection);
    const comprimentos = arestasDaFamilia(projection);
    expect(comprimentos).toHaveLength(163);
    for (const d of comprimentos) expect(d).toBeGreaterThan(extent.operacional.radius);
    void positions;
  });

  it('não é abalada pelo tamanho de outra família', () => {
    // Uma família que cresce reacomoda a si mesma; ela não pode reposicionar o provedor
    // de outra. É a mesma promessa que o corpus faz sobre os MOCs, no nível das nuvens, e
    // quem a cumpre é o degrau do raio da casca: sem ele, um endpoint novo na **maior**
    // família mudaria a escala da região inteira.
    const antes = layoutModels(acervoFixture(ACERVO));
    const alvo = 'op/provider/together';
    for (const crescida of [
      { ...ACERVO, cerebras: 13 },
      { ...ACERVO, ollama: ACERVO.ollama + 1 },
    ]) {
      const depois = layoutModels(acervoFixture(crescida));
      expect(depois.positions.get(alvo)).toEqual(antes.positions.get(alvo));
    }
  });
});

describe('a âncora do trabalhador, extraída para a migração de propriedade', () => {
  function trabalhador(nome: string): ProjectionNode {
    return node(`op/worker/${nome}`, {
      kind: 'agent',
      layer: 'operational',
      path: null,
      canonicalState: 'canonical',
      domainId: WORKER_DOMAIN,
      domainLabel: 'trabalhadores',
      operational: { role: nome },
    });
  }

  const PAPEIS = [
    'arbitro',
    'critico-epistemologico',
    'proponente',
    'revisor-estrutural',
    'revisor-interdisciplinar',
    'sintetizador',
    'verificador-factual',
  ];

  it('o layout não materializa mais trabalhador nenhum', () => {
    // A outra metade da troca atômica: quem os assenta é a `runtimeLayer`. Se este
    // layout voltasse a produzi-los, existiriam catorze — dois subsistemas capazes de
    // reposicionar a mesma entidade, que é a doença que a ADR-005 trata.
    //
    // Este teste substituiu o de paridade que vivia aqui. Ele comparava a âncora pela
    // identidade contra a que `layoutModels` produzia — e no instante em que o layout
    // parou de produzi-las, passou a iterar sobre um mapa vazio e a **passar por
    // vacuidade**. Verde por construção é o defeito que o A-10 da auditoria nomeou; a
    // paridade de verdade agora é medida na cena viva, contra as poses do dono novo.
    const projection: Projection = {
      ...projectionFixture(),
      nodes: PAPEIS.map(trabalhador),
      edges: [],
    };
    const assentados = layoutModels(projection).positions;
    for (const id of PAPEIS.map((nome) => `op/worker/${nome}`)) {
      expect(assentados.has(id)).toBe(false);
    }
    // E a âncora continua existindo, para quem a possui perguntar por ela.
    expect(workerAnchorPoses(PAPEIS.map((nome) => `op/worker/${nome}`), 0).size).toBe(
      PAPEIS.length,
    );
  });

  it('a ordem é a do identificador, e não a de chegada', () => {
    const direto = workerAnchorPoses(['op/worker/a', 'op/worker/b', 'op/worker/c'], 40);
    const invertido = workerAnchorPoses(['op/worker/c', 'op/worker/b', 'op/worker/a'], 40);
    for (const [id, ponto] of direto) {
      const outro = invertido.get(id)!;
      expect(Math.hypot(ponto.x - outro.x, ponto.y - outro.y, ponto.z - outro.z)).toBeLessThan(
        1e-9,
      );
    }
  });

  it('a casca empurra o anel para fora, e o piso das placas o segura', () => {
    const ids = PAPEIS.map((nome) => `op/worker/${nome}`);
    const raioDe = (mapa: ReturnType<typeof workerAnchorPoses>): number => {
      const p = [...mapa.values()][0]!;
      return Math.hypot(p.x, p.y, p.z);
    };
    // Casca grande manda; casca zero cai no raio que as próprias placas exigem, e ele
    // não é zero — senão os sete nasceriam empilhados na origem.
    expect(raioDe(workerAnchorPoses(ids, 400))).toBeGreaterThan(raioDe(workerAnchorPoses(ids, 0)));
    expect(raioDe(workerAnchorPoses(ids, 0))).toBeGreaterThan(0);
  });

  it('lista vazia não inventa anel', () => {
    expect(workerAnchorPoses([], 100).size).toBe(0);
  });
});
