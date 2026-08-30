// A primeira transferência de propriedade da ADR-005, prendida em teste.
//
// Cada caso aqui é uma das propriedades que o mantenedor exigiu antes do corte no
// backend. Elas existem porque um defeito de propriedade não aparece na tela: a cena
// continua desenhando sete placas mesmo quando dois subsistemas disputam quem as move.

import { describe, expect, it } from 'vitest';

import { workerAnchorPoses } from './modelsLayout';
import {
  WORKER_DOMAIN,
  diffWorkers,
  workerNode,
  workerNodeId,
  type RuntimeWorker,
} from './workerEntities';

const PAPEIS = [
  ['proponente', 'produtor', 'D02'],
  ['verificador-factual', 'avaliador', 'D08'],
  ['critico-epistemologico', 'avaliador', 'D08'],
  ['revisor-estrutural', 'avaliador', 'D08'],
  ['revisor-interdisciplinar', 'avaliador', 'D08'],
  ['sintetizador', 'avaliador', 'D08'],
  ['arbitro', 'avaliador', 'D08'],
] as const;

function roster(): RuntimeWorker[] {
  return PAPEIS.map(([role, className, paletteToken]) => ({
    id: role,
    role,
    className,
    summary: 'faz o que o papel diz',
    area: 'runtime/',
    paletteToken,
    concurrencyMax: 1,
  }));
}

function mapa(workers: readonly RuntimeWorker[]): Map<string, RuntimeWorker> {
  return new Map(workers.map((worker) => [worker.id, worker]));
}

describe('o nó do trabalhador possuído pelo runtime', () => {
  it('reproduz a identidade que a projeção operacional produzia', () => {
    // Paridade literal: o gate da migração é que nada mude de aparência quando o dono
    // muda. Estes valores são os do nó servido hoje em `/corpus/projection`.
    const no = workerNode(roster()[0]!);
    expect(no.id).toBe('op/worker/proponente');
    expect(no.title).toBe('Trabalhador — proponente');
    expect(no.shortLabel).toBe('proponente');
    expect(no.kind).toBe('agent');
    expect(no.layer).toBe('operational');
    expect(no.canonicalState).toBe('canonical');
    expect(no.domainId).toBe(WORKER_DOMAIN);
    expect(no.domainLabel).toBe('trabalhadores');
    expect(no.visual.isAnchor).toBe(true);
    expect(no.visual.paletteToken).toBe('D02');
  });

  it('o token vem do controle, e não de uma tabela reimplementada aqui', () => {
    const avaliador = workerNode(roster()[1]!);
    expect(avaliador.visual.paletteToken).toBe('D08');
    // Trocar o que o controle afirma troca a cor, sem este módulo saber a regra.
    const inventado = workerNode({ ...roster()[1]!, paletteToken: 'D12' });
    expect(inventado.visual.paletteToken).toBe('D12');
  });

  it('o instante do nó é fixo: papel não é evento', () => {
    // `Date.now()` faria a mesma entidade parecer nova a cada sincronização, e qualquer
    // comparação por conteúdo reconstruiria sete placas por polling.
    expect(workerNode(roster()[0]!).createdAt).toBe(workerNode(roster()[0]!).createdAt);
    expect(workerNode(roster()[0]!).updatedAt).toBe(workerNode(roster()[0]!).createdAt);
  });
});

describe('o diff do roster, por identidade', () => {
  it('sete ids exatamente, sem duplicação', () => {
    const passo = diffWorkers(new Map(), roster());
    expect(passo.created).toHaveLength(7);
    expect(new Set(passo.created.map((w) => w.id)).size).toBe(7);
  });

  it('`undefined` preserva o que existe; `[]` remove tudo', () => {
    // A distinção que impede um polling falho de apagar os sete da cena.
    const atuais = mapa(roster());
    const semNoticia = diffWorkers(atuais, undefined);
    expect(semNoticia.removed).toHaveLength(0);
    expect(semNoticia.membershipChanged).toBe(false);

    const vazioCanonico = diffWorkers(atuais, []);
    expect(vazioCanonico.removed).toHaveLength(7);
    expect(vazioCanonico.membershipChanged).toBe(true);
  });

  it('mesmos ids não recriam corpos', () => {
    const passo = diffWorkers(mapa(roster()), roster());
    expect(passo.created).toHaveLength(0);
    expect(passo.updated).toHaveLength(7);
    expect(passo.membershipChanged).toBe(false);
  });

  it('remover um id remove exatamente um', () => {
    const passo = diffWorkers(mapa(roster()), roster().slice(1));
    expect(passo.removed).toEqual(['proponente']);
    expect(passo.membershipChanged).toBe(true);
  });

  it('o id que volta é criado de novo, e só ele', () => {
    const semUm = mapa(roster().slice(1));
    const passo = diffWorkers(semUm, roster());
    expect(passo.created.map((w) => w.id)).toEqual(['proponente']);
    expect(passo.removed).toHaveLength(0);
  });
});

describe('a âncora não depende da ordem de chegada', () => {
  it('reordenar o snapshot não troca trabalhador de lugar', () => {
    // Uma regressão dessas pareceria movimento morfogênico e seria, na verdade,
    // nondeterminismo de ordenação — o backend devolvendo os mesmos sete noutra ordem
    // após reinício ou serialização.
    const ids = roster().map((w) => workerNodeId(w.role));
    const direto = workerAnchorPoses(ids, 120);
    const embaralhado = workerAnchorPoses([...ids].reverse(), 120);
    expect(embaralhado.size).toBe(direto.size);
    for (const [id, ponto] of direto) {
      const outro = embaralhado.get(id)!;
      expect(Math.hypot(ponto.x - outro.x, ponto.y - outro.y, ponto.z - outro.z)).toBeLessThan(
        1e-9,
      );
    }
  });
});
