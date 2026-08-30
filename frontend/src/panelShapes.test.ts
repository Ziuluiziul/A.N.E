// A silhueta identifica o tipo — e não pode, de carona, medir importância.

import { describe, expect, it } from 'vitest';

import { OPERATIONAL_KINDS, type EntityKind } from './contract';
import {
  SHAPE_BY_KIND,
  disposePanelShapes,
  panelShapeGeometry,
  shapeOf,
  textAlignmentOf,
  textAreaOf,
  type PanelShape,
} from './panelShapes';

const TIPOS: EntityKind[] = ['moc', 'note', 'reference', 'register', ...OPERATIONAL_KINDS];

/** Área do polígono desenhado, pela soma dos triângulos da geometria. */
function areaDe(kind: EntityKind): number {
  const geometry = panelShapeGeometry(shapeOf(kind));
  const posicao = geometry.getAttribute('position');
  const indice = geometry.getIndex();
  let area = 0;
  const total = indice ? indice.count : posicao.count;
  for (let i = 0; i < total; i += 3) {
    const [a, b, c] = indice
      ? [indice.getX(i), indice.getX(i + 1), indice.getX(i + 2)]
      : [i, i + 1, i + 2];
    const ax = posicao.getX(a!), ay = posicao.getY(a!);
    const bx = posicao.getX(b!), by = posicao.getY(b!);
    const cx = posicao.getX(c!), cy = posicao.getY(c!);
    area += Math.abs((bx - ax) * (cy - ay) - (cx - ax) * (by - ay)) / 2;
  }
  return area;
}

describe('a forma do painel', () => {
  it('todo tipo declara uma silhueta', () => {
    for (const kind of TIPOS) expect(SHAPE_BY_KIND[kind]).toBeDefined();
  });

  it('todas as silhuetas têm a mesma área, para a forma não virar tamanho', () => {
    // Um hexágono inscrito no mesmo retângulo teria três quartos da área, e a silhueta
    // passaria a medir importância sem que ninguém tivesse decidido isso.
    for (const kind of TIPOS) expect(areaDe(kind)).toBeCloseTo(1, 4);
  });

  it('a geometria é compartilhada por forma, e não por painel', () => {
    expect(panelShapeGeometry('hexagono')).toBe(panelShapeGeometry('hexagono'));
    expect(panelShapeGeometry('hexagono')).not.toBe(panelShapeGeometry('octogono'));
  });

  it('cada silhueta é plana e fechada', () => {
    for (const forma of ['retangulo', 'hexagono', 'octogono', 'losango', 'triangulo'] as const) {
      const posicao = panelShapeGeometry(forma).getAttribute('position');
      expect(posicao.count).toBeGreaterThanOrEqual(3);
      for (let i = 0; i < posicao.count; i += 1) expect(posicao.getZ(i)).toBe(0);
    }
    disposePanelShapes();
  });
});

describe('a caixa de texto cabe na silhueta', () => {
  // O teste que faltava. O contorno era descrito duas vezes — uma em polígono, outra em
  // fatores escritos à mão — e as duas discordavam: os cantos do texto do octógono
  // ficavam fora da forma, e o triângulo, que é apoiado em cima com a ponta para baixo,
  // recebia o texto empurrado justamente para dentro da ponta. Nada olhava o contorno
  // real, então nada disso aparecia.

  /** O contorno desenhado, lido da própria geometria que vai para a GPU. */
  function contornoDe(shape: PanelShape): Array<[number, number]> {
    const posicao = panelShapeGeometry(shape).getAttribute('position');
    const vistos = new Map<string, [number, number]>();
    for (let i = 0; i < posicao.count; i += 1) {
      vistos.set(`${posicao.getX(i).toFixed(6)}|${posicao.getY(i).toFixed(6)}`, [
        posicao.getX(i),
        posicao.getY(i),
      ]);
    }
    // Ordenar pelo ângulo fecha o polígono na ordem certa, sem depender da triangulação.
    return [...vistos.values()].sort((a, b) => Math.atan2(a[1], a[0]) - Math.atan2(b[1], b[0]));
  }

  function dentro(ponto: [number, number], poligono: Array<[number, number]>): boolean {
    // Convexo e anti-horário: dentro é ficar à esquerda de toda aresta. A folga absorve
    // o arredondamento do float.
    return poligono.every(([x0, y0], i) => {
      const [x1, y1] = poligono[(i + 1) % poligono.length]!;
      return (x1 - x0) * (ponto[1] - y0) - (y1 - y0) * (ponto[0] - x0) >= -1e-6;
    });
  }

  const FORMAS: PanelShape[] = ['retangulo', 'hexagono', 'octogono', 'losango', 'triangulo'];

  it('os quatro cantos do texto ficam dentro do contorno desenhado', () => {
    for (const forma of FORMAS) {
      const contorno = contornoDe(forma);
      const area = textAreaOf(forma, { width: 1, height: 1 });
      for (const dx of [-1, 1]) {
        for (const dy of [-1, 1]) {
          const canto: [number, number] = [
            (dx * area.width) / 2,
            area.offsetY + (dy * area.height) / 2,
          ];
          expect(dentro(canto, contorno), `${forma} canto ${dx},${dy}`).toBe(true);
        }
      }
    }
  });

  it('a caixa é a maior que cabe: 4% a mais já põe canto para fora', () => {
    // Sem isto, uma caixa minúscula passaria calada no teste de contenção.
    for (const forma of FORMAS) {
      const contorno = contornoDe(forma);
      const area = textAreaOf(forma, { width: 1, height: 1 });
      const canto: [number, number] = [area.width * 0.52, area.offsetY + area.height * 0.52];
      expect(dentro(canto, contorno), forma).toBe(false);
    }
  });

  it('a caixa guarda a proporção do painel, e a linha mantém o ritmo em toda forma', () => {
    // A de maior área no hexágono seria uma coluna estreita e alta dentro de uma forma
    // larga. A silhueta diz o tipo da entidade; ela não tem por que mudar a leitura.
    for (const forma of FORMAS) {
      const larga = textAreaOf(forma, { width: 8, height: 3 });
      expect(larga.width / larga.height, forma).toBeCloseTo(8 / 3, 6);
    }
  });

  it('o triângulo sobe o texto, porque é embaixo que fica a ponta', () => {
    expect(textAreaOf('triangulo', { width: 1, height: 1 }).offsetY).toBeGreaterThan(0.05);
    for (const forma of ['retangulo', 'hexagono', 'octogono', 'losango'] as PanelShape[]) {
      expect(textAreaOf(forma, { width: 1, height: 1 }).offsetY, forma).toBeCloseTo(0, 6);
    }
  });

  it('forma pontiaguda centra o texto; a folha retangular alinha à esquerda', () => {
    expect(textAlignmentOf('retangulo')).toEqual({ textAlign: 'left', anchorX: 'left' });
    for (const forma of ['hexagono', 'octogono', 'losango', 'triangulo'] as PanelShape[]) {
      expect(textAlignmentOf(forma), forma).toEqual({ textAlign: 'center', anchorX: 'center' });
    }
  });
});
