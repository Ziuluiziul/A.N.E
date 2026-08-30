// A legenda afirma coisas sobre a cena. Estes testes são o que a impede de mentir.

import { describe, expect, it } from 'vitest';

import { EDGE_STYLES } from './edges';
import { projectionFixture } from './fixture';
import { PROVIDER_TOKENS } from './palette';
import { shapeOf } from './panelShapes';
import { buildSceneLegend } from './sceneLegend';

const projecao = projectionFixture();
const legenda = buildSceneLegend(projecao);
const secao = (titulo: string) => legenda.find((item) => item.title === titulo)!;

describe('a legenda sai das tabelas que desenham a cena', () => {
  it('descreve toda relação que a projeção declara, com o traço real dela', () => {
    const linhas = secao('Linhas');
    expect(linhas.items).toHaveLength(projecao.meta.relationFamilies.length);
    for (const familia of projecao.meta.relationFamilies) {
      const estilo = EDGE_STYLES[familia];
      const item = linhas.items.find((entrada) => entrada.mark === estilo.label);
      expect(item, `relação sem legenda: ${familia}`).toBeDefined();
      // O traço exibido é o mesmo array que a aresta usa. Não há segunda cópia dele.
      expect(item!.pattern).toEqual(estilo.pattern);
      expect(item!.doubled).toBe(estilo.doubled);
    }
  });

  it('só anuncia uma silhueta para a espécie que de fato a recebe', () => {
    // A conferência mora no módulo: se `SHAPE_BY_KIND` mudar a forma de uma espécie, o
    // exemplo sai da linha em vez de continuar prometendo a silhueta antiga.
    const formas = secao('Silhueta');
    const hexagono = formas.items.find((item) => item.mark === 'hexágono')!;
    expect(shapeOf('moc')).toBe('hexagono');
    expect(hexagono.meaning).toContain('mapa de conteúdo');

    const triangulo = formas.items.find((item) => item.mark === 'triângulo')!;
    expect(shapeOf('quorum-vote')).toBe('triangulo');
    expect(triangulo.meaning).toContain('voto');
  });

  it('lista os domínios do corpus e os provedores, cada um com seu token', () => {
    const cores = secao('Cor');
    for (const dominio of projecao.meta.domains) {
      const item = cores.items.find((entrada) => entrada.mark === dominio.label);
      expect(item, `domínio sem legenda: ${dominio.label}`).toBeDefined();
      expect(item!.token).toBe(dominio.paletteToken);
    }
    for (const token of Object.keys(PROVIDER_TOKENS)) {
      expect(cores.items.some((item) => item.token === token)).toBe(true);
    }
  });

  it('não promete cor para o status epistêmico, porque não existe cor para ele', () => {
    // O status é escrito no cabeçalho da placa. Anunciar um matiz faria a pessoa
    // procurar na cena uma distinção que a cena não faz — e é justamente sobre o
    // critério epistêmico que o Atlas não pode induzir a erro.
    const status = secao('Status epistêmico');
    expect(status.items).toEqual([]);
    expect(status.note).toMatch(/escrito/i);
    expect(status.note).toMatch(/nunca pintado/i);
  });

  it('diz que analogia não cria aresta, que é a regra que a cena implementa', () => {
    expect(secao('Linhas').note).toMatch(/analogia/i);
  });
});
