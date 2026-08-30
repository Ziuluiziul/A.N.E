// Os quinze casos que 3.5-C precisa prender.
//
// A regra que todos servem: reduzir o que se desenha nunca pode reduzir o que se sabe.
// Cada teste que fala de primitiva confere também que a proveniência volta.

import { describe, expect, it } from 'vitest';

import type { ProjectionEdge, RelationFamily } from './contract';
import { buildRelationLines } from './edges';
import { edge } from './fixture';
import type { LayoutMap } from './layout';
import { buildRelationRegistry, pairKeyOf, relationCountOf } from './relationRegistry';

const posicoes = (ids: string[]): LayoutMap =>
  new Map(ids.map((id, i) => [id, { x: i * 30, y: (i % 2) * 20, z: (i % 3) * 5 }]));

function segmentos(edges: ProjectionEdge[], ids: string[]): number {
  let total = 0;
  for (const build of buildRelationLines(edges, posicoes(ids))) {
    total += build.lines.geometry.getAttribute('position').count / 2;
    build.lines.geometry.dispose();
  }
  return total;
}

describe('registro semântico e canônico', () => {
  it('1. relação simples A→B vira um par com um sentido', () => {
    const r = buildRelationRegistry([edge('A', 'B', 'prerequisite')]);
    expect(r.semantic).toHaveLength(1);
    expect(r.pairs).toHaveLength(1);
    const par = r.pairs[0]!;
    expect(par.forward).toHaveLength(1);
    expect(par.backward).toHaveLength(0);
    expect(par.reciprocal).toBe(false);
    expect(par.relationCount).toBe(1);
  });

  it('2. recíproca da mesma família: um par, dois sentidos, uma primitiva', () => {
    const edges = [edge('A', 'B', 'prerequisite'), edge('B', 'A', 'prerequisite')];
    const r = buildRelationRegistry(edges);
    expect(r.semantic).toHaveLength(2);
    expect(r.pairs).toHaveLength(1);
    const par = r.pairs[0]!;
    expect(par.reciprocal).toBe(true);
    expect(par.familiesDifferByDirection).toBe(false);
    // Antes de 3.5-C isto desenhava dois segmentos sobre o mesmo caminho.
    expect(segmentos(edges, ['A', 'B'])).toBe(1);
    expect(r.provenanceOf(par.key)).toHaveLength(2);
  });

  it('3. recíproca com famílias diferentes não vira duas linhas coincidentes', () => {
    const edges = [edge('A', 'B', 'prerequisite'), edge('B', 'A', 'contrasts')];
    const r = buildRelationRegistry(edges);
    const par = r.pairs[0]!;
    expect(par.familiesDifferByDirection).toBe(true);
    expect(par.families).toEqual(['contrasts', 'prerequisite']);
    // Duas faixas deslocadas, e nenhuma delas sobre o eixo do par.
    const p = posicoes(['A', 'B']);
    const builds = buildRelationLines(edges, p);
    const pontos: number[][] = [];
    for (const b of builds) {
      const attr = b.lines.geometry.getAttribute('position');
      for (let i = 0; i < attr.count; i += 1) {
        pontos.push([attr.getX(i), attr.getY(i), attr.getZ(i)]);
      }
      b.lines.geometry.dispose();
    }
    const a = p.get('A')!;
    const sobreOEixo = pontos.filter(
      ([x, y]) => Math.abs((x ?? 0) - a.x) < 1e-9 && Math.abs((y ?? 0) - a.y) < 1e-9,
    );
    expect(sobreOEixo).toHaveLength(0);
  });

  it('4. três famílias no mesmo par são todas registradas', () => {
    const r = buildRelationRegistry([
      edge('A', 'B', 'prerequisite'),
      edge('A', 'B', 'evidence'),
      edge('B', 'A', 'contrasts'),
    ]);
    const par = r.pairs[0]!;
    expect(par.families).toEqual(['contrasts', 'evidence', 'prerequisite']);
    expect(par.relationCount).toBe(3);
    expect(par.contrasting).toBe(true);
    expect(r.provenanceOf(par.key)).toHaveLength(3);
  });

  it('5. par inter-MOC nos dois sentidos é um par só', () => {
    const r = buildRelationRegistry([
      edge('MOC A', 'MOC B', 'navigation', 'aggregated'),
      edge('MOC B', 'MOC A', 'navigation', 'aggregated'),
    ]);
    expect(r.pairs).toHaveLength(1);
    expect(r.pairs[0]!.reciprocal).toBe(true);
  });

  it('6. relações contraditórias ficam declaradas, não silenciadas', () => {
    const r = buildRelationRegistry([
      edge('A', 'B', 'prerequisite'),
      edge('B', 'A', 'contrasts'),
    ]);
    const par = r.pairs[0]!;
    expect(par.contrasting).toBe(true);
    expect(par.familiesDifferByDirection).toBe(true);
    // A relação de cada sentido continua recuperável, com a família de origem.
    expect(par.forward[0]!.relations).toEqual(['prerequisite']);
    expect(par.backward[0]!.relations).toEqual(['contrasts']);
  });

  it('7. ponte explícita e agregação entre os mesmos MOCs não se fundem', () => {
    // Uma é relação declarada, a outra é soma de relações. Fundi-las faria a cena
    // afirmar que existe uma relação onde há apenas uma contagem.
    const r = buildRelationRegistry([
      edge('MOC A', 'MOC B', 'navigation', 'canonical'),
      edge('MOC A', 'MOC B', 'navigation', 'aggregated'),
    ]);
    expect(r.pairs).toHaveLength(2);
    expect(new Set(r.pairs.map((p) => p.aggregation))).toEqual(
      new Set(['canonical', 'aggregated']),
    );
  });

  it('8. self-link é registrado e não vira segmento', () => {
    const edges = [edge('A', 'A', 'extends')];
    const r = buildRelationRegistry(edges);
    expect(r.pairs[0]!.selfLink).toBe(true);
    expect(r.pairs[0]!.reciprocal).toBe(false);
    expect(segmentos(edges, ['A'])).toBe(0);
  });

  it('11. a ordem de entrada não muda o registro', () => {
    const edges = [
      edge('A', 'B', 'prerequisite'),
      edge('B', 'A', 'contrasts'),
      edge('B', 'C', 'evidence'),
    ];
    const direto = buildRelationRegistry(edges);
    const invertido = buildRelationRegistry([...edges].reverse());
    expect(invertido.pairs.map((p) => p.key)).toEqual(direto.pairs.map((p) => p.key));
    for (const par of direto.pairs) {
      const outro = invertido.pairByKey.get(par.key)!;
      expect(outro.relationCount).toBe(par.relationCount);
      expect(outro.families).toEqual(par.families);
      expect(outro.reciprocal).toBe(par.reciprocal);
      expect(outro.dominantFamily).toBe(par.dominantFamily);
    }
  });

  it('12. corpus sem relações produz registro vazio, e não erro', () => {
    const r = buildRelationRegistry([]);
    expect(r.semantic).toEqual([]);
    expect(r.pairs).toEqual([]);
    expect(segmentos([], ['A'])).toBe(0);
  });

  it('13. relações SSE não entram no orçamento do corpus', () => {
    const epistemica = edge('A', 'B', 'prerequisite');
    const viva: ProjectionEdge = {
      ...edge('E1', 'E2', 'operational'),
      kind: 'operational',
      layer: 'operational',
    };
    const r = buildRelationRegistry([epistemica, viva]);
    const doCorpus = r.pairs.filter((p) => p.layer === 'epistemic');
    const daOperacao = r.pairs.filter((p) => p.layer === 'operational');
    expect(doCorpus).toHaveLength(1);
    expect(daOperacao).toHaveLength(1);
    // Quem desenha o corpus filtra por camada e não vê a outra.
    expect(segmentos([epistemica], ['A', 'B'])).toBe(1);
  });

  it('14. de toda primitiva se recupera a proveniência dirigida', () => {
    const edges: ProjectionEdge[] = [
      edge('A', 'B', 'prerequisite'),
      edge('B', 'A', 'extends'),
      edge('B', 'C', 'evidence'),
      edge('C', 'A', 'navigation'),
    ];
    const r = buildRelationRegistry(edges);
    const recuperadas = new Set<string>();
    for (const par of r.pairs) {
      for (const rel of r.provenanceOf(par.key)) recuperadas.add(rel.directedKey);
    }
    expect(recuperadas.size).toBe(edges.length);
    // E o caminho de volta: de uma relação dirigida chega-se ao par que a desenha.
    for (const e of edges) {
      const par = r.pairFor(e.source, e.target);
      expect(par).toBeDefined();
      expect(par!.key).toContain(pairKeyOf(e.source, e.target));
    }
  });

  it('nenhuma relação some entre os dois registros', () => {
    const familias: RelationFamily[] = ['prerequisite', 'extends', 'evidence', 'contrasts'];
    const edges = familias.flatMap((f, i) => [
      edge(`N${i}`, `N${i + 1}`, f),
      edge(`N${i + 1}`, `N${i}`, familias[(i + 1) % familias.length]!),
    ]);
    const r = buildRelationRegistry(edges);
    expect(r.semantic).toHaveLength(edges.length);
    expect(relationCountOf(r)).toBe(edges.length);
  });
});
