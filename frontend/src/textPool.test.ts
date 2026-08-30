// O orçamento de texto: teto fixo, prioridade declarada e atribuição que não treme.

import { describe, expect, it } from 'vitest';

import type { LodLevel } from './lod';
import {
  MIN_CORPUS_SLOTS,
  MIN_RUNTIME_SLOTS,
  TOTAL_TEXT_SLOTS,
  classOf,
  createTextPool,
  type TextCandidate,
} from './textPool';

function candidato(
  entityId: string,
  lod: LodLevel = 'legible',
  extra: Partial<TextCandidate> = {},
): TextCandidate {
  return {
    entityId,
    lod,
    selected: false,
    hovered: false,
    projectedSize: 100,
    distance: 50,
    source: 'corpus',
    ...extra,
  };
}

function muitos(n: number, prefixo = 'n', extra: Partial<TextCandidate> = {}): TextCandidate[] {
  return Array.from({ length: n }, (_, i) =>
    candidato(`${prefixo}-${String(i).padStart(3, '0')}`, 'legible', {
      projectedSize: 1000 - i,
      ...extra,
    }),
  );
}

describe('o teto é fixo e não acompanha o corpus', () => {
  it('nunca atribui mais vagas que a capacidade', () => {
    const pool = createTextPool();
    expect(pool.allocate(muitos(TOTAL_TEXT_SLOTS * 2)).length).toBe(TOTAL_TEXT_SLOTS);
  });

  it('o teto continua sendo teto: passar dele não cria objeto', () => {
    // O número subiu de 64 para cobrir a cena inteira, mas o teto não deixou de
    // existir: pool sem limite é vazamento esperando acontecer.
    const acima = TOTAL_TEXT_SLOTS + 200;
    expect(createTextPool().allocate(muitos(acima)).length).toBe(TOTAL_TEXT_SLOTS);
    expect(createTextPool().allocate(muitos(acima * 2)).length).toBe(TOTAL_TEXT_SLOTS);
  });

  it('capacidade menor é respeitada à risca', () => {
    expect(createTextPool(5, 2, 1).allocate(muitos(50)).length).toBe(5);
  });
});

describe('a prioridade é a declarada', () => {
  it('as classes ficam na ordem selecionado, hover, expanded, legible, identifiable', () => {
    const ordem = [
      classOf(candidato('a', 'distant', { selected: true })),
      classOf(candidato('b', 'distant', { hovered: true })),
      classOf(candidato('c', 'expanded')),
      classOf(candidato('d', 'legible')),
      classOf(candidato('e', 'identifiable')),
    ];
    expect(ordem).toEqual([...ordem].sort((x, y) => y - x));
    expect(classOf(candidato('f', 'structural'))).toBe(0);
    expect(classOf(candidato('g', 'distant'))).toBe(0);
  });

  it('o selecionado entra mesmo com o pool lotado, desalojando o menor', () => {
    const pool = createTextPool(4, 1, 1);
    pool.allocate(muitos(4));
    const comSelecao = [
      ...muitos(4),
      candidato('tardio', 'distant', { selected: true, projectedSize: 1 }),
    ];
    const ids = pool.allocate(comSelecao).map((a) => a.entityId);
    expect(ids).toContain('tardio');
    expect(ids.length).toBe(4);
  });

  it('hover entra depois da seleção e antes do resto', () => {
    const pool = createTextPool(2, 1, 1);
    const ids = pool
      .allocate([
        candidato('selecionado', 'distant', { selected: true, projectedSize: 1 }),
        candidato('hover', 'distant', { hovered: true, projectedSize: 1 }),
        candidato('grande', 'expanded', { projectedSize: 9999 }),
      ])
      .map((a) => a.entityId);
    expect(ids).toContain('selecionado');
    expect(ids).toContain('hover');
    expect(ids).not.toContain('grande');
  });

  it('nível distante não consome vaga sozinho', () => {
    expect(createTextPool().allocate(muitos(30, 'd', { lod: 'distant' }))).toEqual([]);
  });
});

describe('corpus e runtime dividem o mesmo teto com pisos', () => {
  it('o runtime conserva o piso quando o corpus lota', () => {
    const pool = createTextPool();
    const atribuicao = pool.allocate([
      ...muitos(200, 'corpus'),
      ...muitos(30, 'runtime', { source: 'runtime' }),
    ]);
    const doRuntime = atribuicao.filter((a) => a.entityId.startsWith('runtime'));
    expect(doRuntime.length).toBeGreaterThanOrEqual(MIN_RUNTIME_SLOTS);
  });

  it('o corpus conserva o piso sob rajada de eventos', () => {
    const pool = createTextPool();
    const atribuicao = pool.allocate([
      ...muitos(20, 'corpus'),
      ...muitos(400, 'runtime', { source: 'runtime', projectedSize: 5000 }),
    ]);
    const doCorpus = atribuicao.filter((a) => a.entityId.startsWith('corpus'));
    expect(doCorpus.length).toBeGreaterThanOrEqual(Math.min(MIN_CORPUS_SLOTS, 20));
  });

  it('piso é chão, não partição: vaga não usada é emprestada', () => {
    const pool = createTextPool();
    const atribuicao = pool.allocate([
      ...muitos(TOTAL_TEXT_SLOTS * 2, 'corpus'),
      ...muitos(2, 'runtime', { source: 'runtime' }),
    ]);
    // O runtime só pediu duas; o resto do piso volta para o corpus.
    expect(atribuicao.length).toBe(TOTAL_TEXT_SLOTS);
    expect(atribuicao.filter((a) => a.entityId.startsWith('runtime')).length).toBe(2);
  });
});

describe('a atribuição não treme', () => {
  it('oscilação de tamanho dentro da mesma classe não troca titular', () => {
    const pool = createTextPool(3, 1, 1);
    const base = [candidato('a'), candidato('b'), candidato('c'), candidato('d')];
    const primeira = pool.allocate(base);
    const titulares = primeira.map((x) => x.entityId).sort();

    // 'd' fica marginalmente maior que os titulares, mas continua na mesma classe.
    const oscilado = base.map((c) =>
      c.entityId === 'd' ? { ...c, projectedSize: 101 } : c,
    );
    const segunda = pool.allocate(oscilado);
    expect(segunda.map((x) => x.entityId).sort()).toEqual(titulares);
  });

  it('classe estritamente superior desaloja o titular', () => {
    const pool = createTextPool(2, 1, 1);
    pool.allocate([candidato('a'), candidato('b'), candidato('c')]);
    const depois = pool
      .allocate([
        candidato('a'),
        candidato('b'),
        candidato('c', 'expanded', { projectedSize: 1 }),
      ])
      .map((x) => x.entityId);
    expect(depois).toContain('c');
    expect(depois.length).toBe(2);
  });

  it('o titular conserva a mesma vaga entre quadros', () => {
    const pool = createTextPool(4, 1, 1);
    pool.allocate(muitos(4));
    const antes = pool.slotOf('n-000');
    pool.allocate([...muitos(4), candidato('novo', 'identifiable')]);
    expect(pool.slotOf('n-000')).toBe(antes);
  });
});

describe('a colisão em tela é decidida junto com o orçamento', () => {
  const caixa = (x: number, y: number, w = 100, h = 40) => ({ x, y, width: w, height: h });

  it('sobrepor deixou de recusar: todo painel escreve', () => {
    // A recusa por colisão mantinha a cena limpa ao custo de emudecer painéis, e o
    // silêncio não avisava que havia texto ali. A direção trocou: todos escrevem, e a
    // leitura se resolve escolhendo um painel, que fica opaco na frente.
    const ids = createTextPool(8, 1, 1)
      .allocate([
        candidato('grande', 'expanded', { projectedSize: 900, screen: caixa(500, 500) }),
        candidato('coberto', 'legible', { projectedSize: 100, screen: caixa(510, 505) }),
        candidato('afastado', 'legible', { projectedSize: 100, screen: caixa(900, 500) }),
      ])
      .map((a) => a.entityId);
    expect(ids).toContain('grande');
    expect(ids).toContain('coberto');
    expect(ids).toContain('afastado');
  });

  it('a recusa por colisão continua existindo, e funciona quando pedida', () => {
    // O mecanismo não foi apagado — ele deixou de ser o padrão. Mantê-lo testado é o
    // que permite voltar atrás sem redescobrir como ele se comportava.
    const pool = createTextPool(8, 1, 1, false);
    const ids = pool
      .allocate([
        candidato('grande', 'expanded', { projectedSize: 900, screen: caixa(500, 500) }),
        // Mesmo lugar, classe menor: não pode roubar a leitura de quem já está lá.
        candidato('coberto', 'legible', { projectedSize: 100, screen: caixa(510, 505) }),
        candidato('afastado', 'legible', { projectedSize: 100, screen: caixa(900, 500) }),
      ])
      .map((a) => a.entityId);
    expect(ids).toContain('grande');
    expect(ids).toContain('afastado');
    expect(ids).not.toContain('coberto');
  });

  it('o selecionado nunca é o recusado, esteja onde estiver', () => {
    const pool = createTextPool(8, 1, 1, false);
    const ids = pool
      .allocate([
        candidato('vizinho', 'expanded', { projectedSize: 9999, screen: caixa(500, 500) }),
        candidato('escolhido', 'legible', {
          selected: true,
          projectedSize: 1,
          screen: caixa(505, 500),
        }),
      ])
      .map((a) => a.entityId);
    expect(ids).toContain('escolhido');
    expect(ids).not.toContain('vizinho');
  });

  it('sem caixa, a decisão continua sendo só de classe', () => {
    const pool = createTextPool(4, 1, 1);
    expect(pool.allocate(muitos(4)).length).toBe(4);
  });

  it('a recusa devolve a vaga em vez de deixá-la vazia', () => {
    const pool = createTextPool(3, 1, 1, false);
    const atribuicao = pool.allocate([
      candidato('a', 'legible', { projectedSize: 900, screen: caixa(100, 100) }),
      candidato('b', 'legible', { projectedSize: 800, screen: caixa(105, 100) }),
      candidato('c', 'legible', { projectedSize: 700, screen: caixa(600, 100) }),
      candidato('d', 'legible', { projectedSize: 600, screen: caixa(1100, 100) }),
    ]);
    // 'b' colide com 'a'; a vaga que sobra vai para 'd', não fica ociosa.
    expect(atribuicao.map((x) => x.entityId).sort()).toEqual(['a', 'c', 'd']);
  });
});

describe('a atribuição é determinística e sem colisão', () => {
  it('medidas idênticas desempatam pelo entityId, sempre igual', () => {
    const iguais = ['zeta', 'alfa', 'meio'].map((id) => candidato(id));
    const uma = createTextPool(2, 1, 1).allocate(iguais).map((a) => a.entityId);
    const outra = createTextPool(2, 1, 1).allocate([...iguais].reverse()).map((a) => a.entityId);
    expect(uma.sort()).toEqual(outra.sort());
    expect(uma).toContain('alfa');
  });

  it('nenhuma vaga fica com duas entidades', () => {
    const pool = createTextPool();
    for (const lote of [muitos(80), muitos(30, 'outro'), muitos(200, 'terceiro')]) {
      const atribuicao = pool.allocate(lote);
      const slots = atribuicao.map((a) => a.slotId);
      expect(new Set(slots).size).toBe(slots.length);
      expect(slots.every((s) => s >= 0 && s < TOTAL_TEXT_SLOTS)).toBe(true);
    }
  });

  it('quem deixa de ser elegível perde a vaga de forma previsível', () => {
    const pool = createTextPool(3, 1, 1);
    pool.allocate([candidato('a'), candidato('b'), candidato('c')]);
    const depois = pool.allocate([candidato('a'), candidato('b', 'distant'), candidato('c')]);
    expect(depois.map((x) => x.entityId)).not.toContain('b');
    expect(pool.slotOf('b')).toBeNull();
  });

  it('release e dispose limpam sem deixar vaga presa', () => {
    const pool = createTextPool(4, 1, 1);
    pool.allocate(muitos(4));
    pool.release(['n-000']);
    expect(pool.slotOf('n-000')).toBeNull();
    expect(pool.current().length).toBe(3);
    pool.dispose();
    expect(pool.current()).toEqual([]);
    // Depois do descarte, o pool volta a funcionar do zero.
    expect(pool.allocate(muitos(2)).length).toBe(2);
  });

  it('a associação por entityId sobrevive à reordenação da entrada', () => {
    const pool = createTextPool(3, 1, 1);
    const lote = muitos(3);
    pool.allocate(lote);
    const antes = new Map(pool.current().map((a) => [a.entityId, a.slotId]));
    pool.allocate([...lote].reverse());
    for (const [entityId, slot] of antes) expect(pool.slotOf(entityId)).toBe(slot);
  });
});
