// O que 3.5-A precisa prender: a camada viva não move o corpus, e cada execução é um
// sistema local íntegro.
//
// Os testes de estabilidade abaixo **reprovavam antes deste incremento**. Enquanto
// `layoutAtlas` assentava a projeção inteira, os nós de quórum contavam para
// `ringRadius` e um balde de 32 empurrava o anel de âncoras — o MOC de Ciências da Vida
// saía de x=79,9 para x=149,0 sem que uma linha do corpus tivesse mudado.

import { describe, expect, it } from 'vitest';

import { composeLayout } from './composeLayout';
import type { Projection, ProjectionNode } from './contract';
import { node, projectionFixture } from './fixture';
import { DIRECAO_CANONICA, extentOf } from './layout';
import {
  SEPARACAO_ENTRE_EXECUCOES,
  groupQuorumSystems,
  layoutOperational,
} from './operationalLayout';
import { describePanel } from './panels';
import { panelWorldExtent } from './panelScale';
import { shapeExtentRatio } from './panelShapes';
import { BASE_LOCAL } from './screenBasis';
import { comExecucoes, comAssunto } from './quorumScenario';

/** A mesma base que `operationalLayout` usa, reconstruída para as asserções. */
const BASE_DA_TELA = (() => {
  const cruzar = (a: typeof DIRECAO_CANONICA, b: typeof DIRECAO_CANONICA) => ({
    x: a.y * b.z - a.z * b.y,
    y: a.z * b.x - a.x * b.z,
    z: a.x * b.y - a.y * b.x,
  });
  const norm = (v: typeof DIRECAO_CANONICA) => {
    const n = Math.hypot(v.x, v.y, v.z) || 1;
    return { x: v.x / n, y: v.y / n, z: v.z / n };
  };
  const direita = norm(cruzar({ x: 0, y: 0, z: 1 }, DIRECAO_CANONICA));
  return { direita, acima: norm(cruzar(DIRECAO_CANONICA, direita)) };
})();


const epistemicos = (p: Projection): ProjectionNode[] =>
  p.nodes.filter((n) => n.layer === 'epistemic');

describe('a camada viva não move o corpus', () => {
  // Antes de 3.5-A este bloco reprovava: `ringRadius` recebia a contagem da projeção
  // inteira, então bastava acumular execuções para o anel inteiro se reescalar.
  it.each([1, 32, 100, 1000])(
    'deslocamento zero de MOC e de nota com %i nós de execução',
    (execucoes) => {
      const semOperacao = composeLayout(projectionFixture());
      const comOperacao = composeLayout(comExecucoes(execucoes));

      let piorMoc = 0;
      let piorNota = 0;
      for (const no of epistemicos(projectionFixture())) {
        const antes = semOperacao.positions.get(no.id)!;
        const depois = comOperacao.positions.get(no.id)!;
        const desvio = Math.hypot(antes.x - depois.x, antes.y - depois.y, antes.z - depois.z);
        if (no.kind === 'moc') piorMoc = Math.max(piorMoc, desvio);
        else piorNota = Math.max(piorNota, desvio);
      }
      expect(piorMoc).toBe(0);
      expect(piorNota).toBe(0);
    },
    // Teto explícito porque o caso de mil execuções é deliberadamente pesado: o
    // relaxamento da casca é quadrático na contagem e roda sessenta passadas, o que
    // sozinho já ocupa a maior parte do padrão de 5 s. Encostado no limite, ele reprovava
    // conforme a carga da máquina — e um gate que oscila com a carga não é gate.
    20_000,
  );

  it('o raio do corpus não conhece a camada viva', () => {
    const so = composeLayout(projectionFixture());
    const com = composeLayout(comExecucoes(40));
    expect(com.extent.corpus).toEqual(so.extent.corpus);
    // E o observatório mora fora do corpus, sem invadi-lo — agora em qualquer direção,
    // porque a direção deixou de ser o eixo `+x` fixo.
    const distancia = Math.hypot(
      com.origin.operacional.x,
      com.origin.operacional.y,
      com.origin.operacional.z,
    );
    expect(distancia).toBeGreaterThan(
      com.extent.corpus.radius + com.extent.operacional.radius,
    );
  });

  describe('a coluna epistêmica', () => {
    // O eixo da coluna é o "acima" da tela, o mesmo em que o nome de cada nuvem sobe.
    const naColuna = (p: { x: number; y: number; z: number }): number =>
      p.x * BASE_LOCAL.acima.x + p.y * BASE_LOCAL.acima.y + p.z * BASE_LOCAL.acima.z;
    const foraDaColuna = (p: { x: number; y: number; z: number }): number => {
      const altura = naColuna(p);
      return Math.hypot(
        p.x - BASE_LOCAL.acima.x * altura,
        p.y - BASE_LOCAL.acima.y * altura,
        p.z - BASE_LOCAL.acima.z * altura,
      );
    };

    it('põe o conhecimento embaixo e o quórum em cima, no mesmo eixo', () => {
      const composto = composeLayout(comExecucoes(20));
      expect(naColuna(composto.origin.corpus)).toBeLessThan(0);
      expect(naColuna(composto.origin.operacional)).toBeGreaterThan(0);
      // Na coluna de verdade: sem componente lateral que faça uma escapar da outra.
      expect(foraDaColuna(composto.origin.corpus)).toBeLessThan(1e-6);
      expect(foraDaColuna(composto.origin.operacional)).toBeLessThan(1e-6);
    });

    it('deixa o miolo livre para a nuvem viva', () => {
      const composto = composeLayout(comExecucoes(20));
      const distancia = (p: { x: number; y: number; z: number }): number =>
        Math.hypot(p.x, p.y, p.z);
      // Cada nuvem fica a pelo menos a reserva do miolo da origem, mais o próprio raio:
      // é isso que garante que o raciocínio não nasça dentro de nenhuma delas.
      expect(distancia(composto.origin.corpus)).toBeGreaterThanOrEqual(
        composto.core.radius + composto.extent.corpus.radius,
      );
      expect(distancia(composto.origin.operacional)).toBeGreaterThanOrEqual(
        composto.core.radius + composto.extent.operacional.radius,
      );
      expect(distancia(composto.origin.modelos)).toBeGreaterThanOrEqual(
        composto.core.radius + composto.extent.modelos.radius,
      );
    });

    it('o miolo mede pelo menos o que o conhecimento media, em degraus', () => {
      // A nuvem viva herda o lugar **e** a medida: sem isso ela teria de adivinhar de
      // que tamanho é o buraco que lhe reservaram.
      const composto = composeLayout(comExecucoes(20));
      expect(composto.core.radius).toBeGreaterThanOrEqual(composto.extent.corpus.radius);
      expect(composto.core.origin).toEqual({ x: 0, y: 0, z: 0 });
    });
  });
});

describe('determinismo', () => {
  it('a ordem de entrada dos nós não altera nenhuma posição', () => {
    const projection = comExecucoes(12);
    const embaralhada: Projection = {
      ...projection,
      nodes: [...projection.nodes].reverse(),
      edges: [...projection.edges].reverse(),
    };
    const a = composeLayout(projection).positions;
    const b = composeLayout(embaralhada).positions;
    expect(b.size).toBe(a.size);
    for (const [id, p] of a) expect(b.get(id)).toEqual(p);
  });

  it('a mesma projeção produz as mesmas posições', () => {
    const projection = comExecucoes(7);
    expect([...composeLayout(projection).positions]).toEqual([
      ...composeLayout(projection).positions,
    ]);
  });

  it('acrescentar execução não move as anteriores', () => {
    const antes = layoutOperational(comExecucoes(9)).positions;
    const depois = layoutOperational(comExecucoes(10)).positions;
    for (const [id, p] of antes) expect(depois.get(id)).toEqual(p);
    expect(depois.size).toBeGreaterThan(antes.size);
  });
});

describe('integridade de cada execução', () => {
  it('N painéis produzem N sistemas locais, sem mistura', () => {
    const projection = comExecucoes(35);
    const { systems, diagnostics } = groupQuorumSystems(projection);
    expect(systems).toHaveLength(35);
    expect(diagnostics.orphans).toEqual([]);
    expect(diagnostics.votesWithoutMember).toEqual([]);

    const donoDe = new Map<string, string>();
    const avaliadores = new Set<string>();
    for (const sistema of systems) {
      // O que pertence à execução são votos e decisão. O avaliador, desde 3.5-F, é
      // identidade canônica da nuvem de modelos: ele é **compartilhado** de propósito,
      // e exigir o `panelId` dentro dele seria exigir de volta a duplicação que saiu.
      const proprios = [...sistema.decisionIds, ...[...sistema.votesByMember.values()].flat()];
      for (const id of proprios) {
        expect(donoDe.has(id)).toBe(false);
        donoDe.set(id, sistema.panelId);
        expect(id).toContain(sistema.panelId);
      }
      for (const membro of sistema.memberIds) {
        expect(membro.startsWith('op/model/')).toBe(true);
        avaliadores.add(membro);
      }
      expect(sistema.memberIds).toHaveLength(3);
      expect(sistema.decisionIds).toHaveLength(1);
    }
    // 35 execuções, 4 nós próprios cada; e os mesmos 3 avaliadores em todas elas.
    expect(donoDe.size).toBe(35 * 4);
    expect(avaliadores.size).toBe(3);
  });

  it('cada voto acompanha o avaliador que ele mesmo declara', () => {
    // A associação vinha de uma aresta até um nó de avaliador local. Agora vem do
    // próprio voto, que carrega provedor e endpoint — a fonte que não pode divergir.
    const projection = comExecucoes(4);
    const porId = new Map(projection.nodes.map((n) => [n.id, n]));
    const { systems } = groupQuorumSystems(projection);
    for (const sistema of systems) {
      for (const [membro, votos] of sistema.votesByMember) {
        expect(sistema.memberIds).toContain(membro);
        for (const voto of votos) {
          const meta = porId.get(voto)!.operational!;
          expect(`op/model/${meta.provider}/${meta.endpoint}`).toBe(membro);
        }
      }
    }
  });

  it('nó de quórum sem execução é reportado, não espalhado', () => {
    const projection = comExecucoes(2);
    const orfao = node('op/quorum/fantasma/vote/99', {
      kind: 'quorum-vote',
      layer: 'operational',
      path: null,
      canonicalState: 'temporary',
      domainId: 'operacional/quorum',
      domainLabel: 'quórum',
      operational: { panelId: 'painel-que-nao-existe' },
    });
    const comOrfao: Projection = { ...projection, nodes: [...projection.nodes, orfao] };
    const { positions, diagnostics } = layoutOperational(comOrfao);
    expect(diagnostics.orphans).toEqual([orfao.id]);
    // Não recebe posição: um órfão assentado viraria ruído visual sem causa aparente.
    expect(positions.has(orfao.id)).toBe(false);
  });

  it('voto sem avaliador é contado e ainda assim assentado no próprio painel', () => {
    const projection = comExecucoes(1);
    // Sem provedor nem endpoint declarados, o voto não tem avaliador a que pertencer.
    const semAresta: Projection = {
      ...projection,
      nodes: projection.nodes.map((n) =>
        n.id.endsWith('/vote/00')
          ? { ...n, operational: { panelId: n.operational!.panelId } }
          : n,
      ),
    };
    const { positions, diagnostics } = layoutOperational(semAresta);
    expect(diagnostics.votesWithoutMember).toHaveLength(1);
    expect(positions.has(diagnostics.votesWithoutMember[0]!)).toBe(true);
  });
});

describe('topologia local: a profundidade mede o processo', () => {
  it('painel na base, avaliador, voto e decisão no topo — medido na base da tela', () => {
    // A progressão deixou de subir em `z` do mundo: `z` é a componente dominante da
    // visada canônica, e empilhar nela punha a decisão entre a câmera e o voto. As
    // asserções passam a ser feitas na mesma base que o layout usa.
    const { positions, systems } = layoutOperational(comExecucoes(1));
    const sistema = systems[0]!;
    const painel = positions.get(sistema.panelNodeId!)!;
    const voto = positions.get(sistema.votesByMember.get(sistema.memberIds[0]!)![0]!)!;
    const decisao = positions.get(sistema.decisionIds[0]!)!;
    // O avaliador não é mais assentado aqui: ele mora na nuvem de modelos.
    expect(positions.has(sistema.memberIds[0]!)).toBe(false);

    const rel = (p: { x: number; y: number; z: number }) => ({
      lateral: (p.x - painel.x) * BASE_DA_TELA.direita.x + (p.y - painel.y) * BASE_DA_TELA.direita.y + (p.z - painel.z) * BASE_DA_TELA.direita.z,
      progresso: (p.x - painel.x) * BASE_DA_TELA.acima.x + (p.y - painel.y) * BASE_DA_TELA.acima.y + (p.z - painel.z) * BASE_DA_TELA.acima.z,
      profundidade: (p.x - painel.x) * DIRECAO_CANONICA.x + (p.y - painel.y) * DIRECAO_CANONICA.y + (p.z - painel.z) * DIRECAO_CANONICA.z,
    });
    const v = rel(voto);
    const d = rel(decisao);

    expect(v.progresso).toBeGreaterThan(0);
    expect(d.progresso).toBeGreaterThan(v.progresso);

    // A decisão é terminal e fica sozinha no eixo do painel — sem deslocamento lateral
    // e sem profundidade própria.
    expect(d.lateral).toBeCloseTo(0, 6);
    expect(d.profundidade).toBeCloseTo(0, 6);

    // O voto abre para fora do eixo do painel: é o leque por avaliador, que continua
    // organizando a execução mesmo sem placa de avaliador nenhuma.
    expect(Math.hypot(v.lateral, v.profundidade)).toBeGreaterThan(0);
  });

  it('a coluna da execução não empilha na direção da visada', () => {
    // O defeito que o clique revelou: com a progressão em `z`, a decisão ficava entre a
    // câmera e o voto e o raio de seleção entregava a decisão a quem clicou no voto.
    const { positions, systems } = layoutOperational(comExecucoes(1));
    const sistema = systems[0]!;
    const ids = [
      sistema.panelNodeId!,
      ...[...sistema.votesByMember.values()].flat(),
      ...sistema.decisionIds,
    ];
    const profundidades = ids.map((id) => {
      const p = positions.get(id)!;
      return p.x * DIRECAO_CANONICA.x + p.y * DIRECAO_CANONICA.y + p.z * DIRECAO_CANONICA.z;
    });
    const faixa = Math.max(...profundidades) - Math.min(...profundidades);
    // O invariante é a **razão**, e não um teto em unidades: a coluna se abre na tela e
    // não para dentro dela. Preso a 14 unidades, o teste reprovava por a execução ter
    // ficado maior — que era o pedido —, e não por ela ter voltado a empilhar.
    const naTela = ids.map((id) => {
      const p = positions.get(id)!;
      return {
        lateral: p.x * BASE_DA_TELA.direita.x + p.y * BASE_DA_TELA.direita.y + p.z * BASE_DA_TELA.direita.z,
        alto: p.x * BASE_DA_TELA.acima.x + p.y * BASE_DA_TELA.acima.y + p.z * BASE_DA_TELA.acima.z,
      };
    });
    const abertura = Math.max(
      Math.max(...naTela.map((p) => p.lateral)) - Math.min(...naTela.map((p) => p.lateral)),
      Math.max(...naTela.map((p) => p.alto)) - Math.min(...naTela.map((p) => p.alto)),
    );
    expect(faixa).toBeLessThan(abertura * 0.5);
  });

  it('execuções mantêm a separação declarada entre centros', () => {
    // Comparava um raio circunscrito contra a distância entre centros, e isso media
    // demais: a coluna de uma execução é alta e estreita, então o raio dela conta a
    // altura como se fosse largura em toda direção. O que a grade promete é separação
    // entre centros; se as placas se cobrem é assunto do teste de sobreposição, que
    // mede caixa contra caixa.
    const { positions, systems } = layoutOperational(comExecucoes(35));
    const centros = systems.map((s) => positions.get(s.panelNodeId!)!);
    let minima = Infinity;
    for (let i = 0; i < centros.length; i += 1) {
      for (let j = i + 1; j < centros.length; j += 1) {
        minima = Math.min(
          minima,
          Math.hypot(
            centros[i]!.x - centros[j]!.x,
            centros[i]!.y - centros[j]!.y,
            centros[i]!.z - centros[j]!.z,
          ),
        );
      }
    }
    expect(minima).toBeGreaterThan(SEPARACAO_ENTRE_EXECUCOES * 0.999);
  });

  // O teste do raio circunscrito saiu aqui. Ele comparava a distância entre centros
  // contra um raio que media a caixa inteira do sistema — alta e estreita, porque a
  // coluna sobe do painel até a decisão — como se ela fosse redonda. Media demais numa
  // direção e de menos noutra, e o que ele reprovava ou aprovava não era sobreposição.
  // Quem responde por isso é o bloco 'nenhuma placa cobre outra', que mede caixa contra
  // caixa, e o teste de separação entre centros logo acima.
});

describe('enquadramento por camada', () => {
  it('a extensão do corpus ignora o observatório e vice-versa', () => {
    const projection = comExecucoes(20);
    const composto = composeLayout(projection);
    // Medida **em torno da origem do corpus**, e não da origem do mundo: desde que a
    // coluna epistêmica existe, o corpus mora abaixo do miolo, e medir do mundo somaria
    // a altura da coluna ao raio dele. A extensão declarada continua sendo a intrínseca —
    // é ela que enquadra o corpus, e ela não conhece a operação.
    const deslocadas = new Map(
      [...composto.positions].map(([id, p]) => [
        id,
        {
          x: p.x - composto.origin.corpus.x,
          y: p.y - composto.origin.corpus.y,
          z: p.z - composto.origin.corpus.z,
        },
      ]),
    );
    const soCorpus = extentOf(deslocadas, composto.ids.corpus);
    const tudo = extentOf(composto.positions);

    expect(soCorpus.radius).toBeCloseTo(composto.extent.corpus.radius, 9);
    // Medir tudo é medir muito mais: era esta diferença que afastava a câmera e
    // encolhia o corpus para caber um anexo que ninguém pediu para ver.
    expect(tudo.radius).toBeGreaterThan(soCorpus.radius * 2);
  });
});

describe('a execução mora perto do que ela avaliou', () => {
  // Todas as execuções ficavam na grade do observatório, longe do corpus, inclusive as
  // que avaliaram uma nota específica: quem olhava a nota não tinha como saber que ela
  // passou por quórum. O vínculo existia na projeção e não existia no espaço.
  const notas = (p: Projection) => p.nodes.filter((n) => n.kind === 'note').map((n) => n.id);

  it('encurta a distância até o assunto, e sai da grade do observatório', () => {
    const base = comExecucoes(6);
    const alvo = notas(base)[0]!;
    const ancorada = comAssunto(base, { exec0001: alvo });

    const solta = composeLayout(base);
    const presa = composeLayout(ancorada);
    const painel = 'op/quorum/exec0001/panel';
    const distancia = (c: ReturnType<typeof composeLayout>) => {
      const a = c.positions.get(painel)!;
      const b = c.positions.get(alvo)!;
      return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
    };
    expect(distancia(presa)).toBeLessThan(distancia(solta));
  });

  it('fica fora da casca do corpus, e não em cima das notas', () => {
    const base = comExecucoes(6);
    const alvos = notas(base).slice(0, 3);
    const composto = composeLayout(
      comAssunto(base, { exec0001: alvos[0]!, exec0002: alvos[1]!, exec0003: alvos[2]! }),
    );
    for (const panelId of ['exec0001', 'exec0002', 'exec0003']) {
      const p = composto.positions.get(`op/quorum/${panelId}/panel`)!;
      expect(Math.hypot(p.x, p.y, p.z)).toBeGreaterThan(composto.extent.corpus.radius);
    }
  });

  it('duas execuções sobre a mesma nota não caem no mesmo ponto', () => {
    // Caíam: a menor distância entre duas ancoradas era zero, medida no corpus real.
    const base = comExecucoes(4);
    const alvo = notas(base)[0]!;
    const composto = composeLayout(comAssunto(base, { exec0001: alvo, exec0002: alvo }));
    const a = composto.positions.get('op/quorum/exec0001/panel')!;
    const b = composto.positions.get('op/quorum/exec0002/panel')!;
    expect(Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z)).toBeGreaterThan(20);
  });

  it('o sistema local anda inteiro, sem deformar', () => {
    // O deslocamento é rígido: se o leque esticasse, a leitura de "painel embaixo,
    // decisão em cima" mudaria de execução para execução.
    const base = comExecucoes(4);
    const alvo = notas(base)[0]!;
    const solta = composeLayout(base);
    const presa = composeLayout(comAssunto(base, { exec0001: alvo }));
    const ids = [
      'op/quorum/exec0001/panel',
      'op/quorum/exec0001/vote/00',
      'op/quorum/exec0001/decision',
    ];
    const distancias = (c: ReturnType<typeof composeLayout>) =>
      ids.map((id) => {
        const p = c.positions.get(id)!;
        const q = c.positions.get(ids[0]!)!;
        return Math.hypot(p.x - q.x, p.y - q.y, p.z - q.z);
      });
    const antes = distancias(solta);
    const depois = distancias(presa);
    antes.forEach((valor, i) => expect(depois[i]!).toBeCloseTo(valor, 9));
  });

  it('ancorar uma execução não move o corpus, e a não-ancorada segue na nuvem viva', () => {
    const base = comExecucoes(4);
    const alvo = notas(base)[0]!;
    const solta = composeLayout(base);
    const presa = composeLayout(comAssunto(base, { exec0001: alvo }));
    // O corpus não se mexe — a assimetria da composição continua valendo.
    for (const no of epistemicos(base)) {
      expect(presa.positions.get(no.id)).toEqual(solta.positions.get(no.id));
    }
    // A execução que não se ancorou continua um nó operacional, na nuvem viva acima do
    // corpus. A força reacomoda a nuvem inteira, então a posição exata não é estável — o
    // que se garante é que ela pertence à camada viva e não ao corpus.
    const presa3 = presa.positions.get('op/quorum/exec0003/panel')!;
    expect(presa3).toBeDefined();
    expect(presa.ids.operacional.has('op/quorum/exec0003/panel')).toBe(true);
  });

  it('ancorar execução não move nenhuma entidade do corpus', () => {
    const base = comExecucoes(6);
    const alvo = notas(base)[0]!;
    const solta = composeLayout(base);
    const presa = composeLayout(comAssunto(base, { exec0001: alvo }));
    for (const no of epistemicos(base)) {
      expect(presa.positions.get(no.id)).toEqual(solta.positions.get(no.id));
    }
  });
});

describe('nenhuma placa cobre outra', () => {
  // A medida que faltava. Havia teste de "execuções não se encostam" comparando centros
  // com um raio calculado, e ele passava enquanto cinco pares de placas se cobriam de
  // fato: o raio media o alcance do sistema, não o tamanho das placas nele. Aqui a
  // sobreposição é medida como ela é vista — caixa contra caixa.
  function sobrepostos(projection: Projection, filtro: (n: ProjectionNode) => boolean): number {
    const composto = composeLayout(projection);
    const alvos = projection.nodes.filter(filtro).filter((n) => composto.positions.has(n.id));
    // A caixa medida é a da **silhueta**: como a área é normalizada, o triângulo é 1,52
    // vez mais largo que a extensão da placa e o losango 1,41. Medir pela extensão dava
    // zero colisões enquanto três votos vizinhos já se tocavam na tela.
    const caixa = new Map(
      alvos.map((n) => {
        const descritor = describePanel(n);
        const extensao = panelWorldExtent(descritor);
        const razao = shapeExtentRatio(descritor.shape);
        return [
          n.id,
          { width: extensao.width * razao.width, height: extensao.height * razao.height },
        ] as const;
      }),
    );
    let colididos = 0;
    for (let i = 0; i < alvos.length; i += 1) {
      for (let j = i + 1; j < alvos.length; j += 1) {
        const a = composto.positions.get(alvos[i]!.id)!;
        const b = composto.positions.get(alvos[j]!.id)!;
        const ca = caixa.get(alvos[i]!.id)!;
        const cb = caixa.get(alvos[j]!.id)!;
        if (
          Math.abs(a.x - b.x) < (ca.width + cb.width) / 2 &&
          Math.abs(a.y - b.y) < (ca.height + cb.height) / 2 &&
          Math.abs(a.z - b.z) < (ca.height + cb.height) / 2
        ) {
          colididos += 1;
        }
      }
    }
    return colididos;
  }

  // A cobertura máxima, relativa à **largura dominante** da placa: a métrica de leitura.
  // Profundidade é quanto uma placa entra na outra no eixo de maior interpenetração;
  // dividir pela largura dominante diz quanto da placa ficou escondido. Contar pares
  // não dizia isso — no anel denso cada vizinho tangencial é um par, e o que importa é
  // que nenhuma placa desapareça debaixo da outra.
  function piorCobertura(projection: Projection, filtro: (n: ProjectionNode) => boolean): number {
    const composto = composeLayout(projection);
    const alvos = projection.nodes.filter(filtro).filter((n) => composto.positions.has(n.id));
    const caixa = new Map(
      alvos.map((n) => {
        const descritor = describePanel(n);
        const extensao = panelWorldExtent(descritor);
        const razao = shapeExtentRatio(descritor.shape);
        return [
          n.id,
          { width: extensao.width * razao.width, height: extensao.height * razao.height },
        ] as const;
      }),
    );
    let pior = 0;
    for (let i = 0; i < alvos.length; i += 1) {
      for (let j = i + 1; j < alvos.length; j += 1) {
        const a = composto.positions.get(alvos[i]!.id)!;
        const b = composto.positions.get(alvos[j]!.id)!;
        const ca = caixa.get(alvos[i]!.id)!;
        const cb = caixa.get(alvos[j]!.id)!;
        const dx = Math.abs(a.x - b.x) - (ca.width + cb.width) / 2;
        const dy = Math.abs(a.y - b.y) - (ca.height + cb.height) / 2;
        const dz = Math.abs(a.z - b.z) - (ca.height + cb.height) / 2;
        const maior = Math.max(dx, dy, dz);
        if (maior < 0) {
          const dominante = Math.max(ca.width, cb.width, ca.height, cb.height);
          pior = Math.max(pior, -maior / dominante);
        }
      }
    }
    return pior;
  }

  it('nem dentro de uma execução, nem entre execuções vizinhas', () => {
    const projection = comExecucoes(24);
    expect(sobrepostos(projection, (n) => n.domainId === 'operacional/quorum')).toBe(0);
  });

  it('nas âncoras densas, nenhuma placa fica coberta além da metade', () => {
    // O anel denso é faixa contínua por decisão do observador: o passo caiu para um
    // terço da grade, e a placa vizinha pode enterrar até ~50% da largura da outra.
    // O que o teste prende é o limite: cobertura na medida do passo, nunca placa
    // escondida. O passo /4 enterrava 64% da largura e reprova aqui.
    const base = comExecucoes(12);
    const notas = base.nodes.filter((n) => n.kind === 'note').map((n) => n.id);
    const ancorada = comAssunto(base, {
      exec0001: notas[0]!,
      exec0002: notas[0]!,
      exec0003: notas[1]!,
      exec0004: notas[2]!,
      exec0005: notas[3]!,
    });
    expect(piorCobertura(ancorada, (n) => n.domainId === 'operacional/quorum')).toBeLessThan(0.55);
  });

  it('nem quando os assuntos se concentram e o anel fecha a volta', () => {
    // A varredura angular empurra para frente e não olha para trás: com muitos assuntos
    // no mesmo setor, o acúmulo passava da volta inteira e a última execução ia parar
    // exatamente sobre a primeira — quatro pares coincidentes, painel sobre painel.
    // No anel denso a varredura ainda é o pior caso: a cobertura sobe para ~49% da
    // largura (medido no passo /3), e o teste segura que ela não ultrapasse o limite.
    const base = comExecucoes(14);
    const alvo = base.nodes.find((n) => n.kind === 'note')!.id;
    const todas = Object.fromEntries(
      Array.from({ length: 14 }, (_, i) => [`exec${String(i + 1).padStart(4, '0')}`, alvo]),
    );
    expect(piorCobertura(comAssunto(base, todas), (n) => n.domainId === 'operacional/quorum')).toBeLessThan(0.55);
  });

  it('nem no corpus', () => {
    expect(sobrepostos(comExecucoes(8), (n) => n.layer === 'epistemic')).toBe(0);
  });
});
