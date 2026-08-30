// A escala mundial e o layout interno: uma autoridade só, e texto que não vaza.

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { projectionFixture } from './fixture';
import { MODEL_DOMAIN, WORKER_DOMAIN, describePanel, panelExtent, type PanelType } from './panels';
import { PANEL_WORLD_SCALE, panelPickExtent, panelWorldExtent } from './panelScale';
import { composeText, layoutPanelText } from './panelTextLayout';
import { linesUpTo } from './panels';

const projecao = projectionFixture();
const base = projecao.nodes.find((n) => n.kind === 'note')!;

function comTipo(tipo: PanelType) {
  const patch: Record<PanelType, Partial<typeof base>> = {
    moc: { kind: 'moc', domainId: 'fisica' },
    bridge: { kind: 'moc', domainId: 'pontes', title: 'Ponte — Teste' },
    note: { kind: 'note' },
    quorum: { kind: 'quorum-decision', layer: 'operational' },
    task: { kind: 'activity', layer: 'operational' },
    endpoint: { kind: 'quorum-member', layer: 'operational', domainId: MODEL_DOMAIN },
    provider: { kind: 'agent', layer: 'operational', domainId: MODEL_DOMAIN },
    worker: { kind: 'agent', layer: 'operational', domainId: WORKER_DOMAIN },
    // Todo evento da trilha viva é um passo de raciocínio, qualquer que seja o `kind`.
    evento: { kind: 'activity', layer: 'operational', operational: { eventType: 'call_started' } },
  };
  return describePanel({ ...base, ...patch[tipo] });
}

const TIPOS: PanelType[] = ['moc', 'bridge', 'note', 'quorum', 'task', 'endpoint', 'provider', 'evento'];

describe('a escala mundial tem uma definição só', () => {
  it('PANEL_WORLD_SCALE é definido em um único módulo', () => {
    const arquivos = ['panels.ts', 'panelBodies.ts', 'atlas.ts', 'panelTextLayout.ts'];
    for (const arquivo of arquivos) {
      const fonte = readFileSync(join(__dirname, arquivo), 'utf-8');
      expect(fonte).not.toMatch(/const PANEL_WORLD_SCALE/);
    }
    const dono = readFileSync(join(__dirname, 'panelScale.ts'), 'utf-8');
    expect(dono).toMatch(/export const PANEL_WORLD_SCALE/);
  });

  it('panelExtent continua semântico e intocado pela escala', () => {
    for (const tipo of TIPOS) {
      const d = comTipo(tipo);
      const semantica = panelExtent(d);
      const mundo = panelWorldExtent(d);
      expect(mundo.width).toBeCloseTo(semantica.width * PANEL_WORLD_SCALE, 10);
      expect(mundo.height).toBeCloseTo(semantica.height * PANEL_WORLD_SCALE, 10);
    }
    // Um MOC continua valendo 4,00 × 2,25 em semântica, com ou sem renderizador.
    const moc = panelExtent(comTipo('moc'));
    expect(moc.width).toBeCloseTo(4, 6);
    expect(moc.height).toBeCloseTo(2.25, 6);
  });

  it('a escala é uniforme e não muda a equivalência de área por degrau', () => {
    const moc = panelWorldExtent(comTipo('moc'));
    const ponte = panelWorldExtent(comTipo('bridge'));
    expect(moc.width * moc.height).toBeCloseTo(ponte.width * ponte.height, 6);
    expect(ponte.width).toBeGreaterThan(moc.width);
  });

  it('a margem de clique é uniforme, não proporcional à largura', () => {
    const ponte = panelWorldExtent(comTipo('bridge'));
    const nota = panelWorldExtent(comTipo('note'));
    const folgaPonte = panelPickExtent(comTipo('bridge')).width - ponte.width;
    const folgaNota = panelPickExtent(comTipo('note')).width - nota.width;
    expect(folgaPonte).toBeCloseTo(folgaNota, 10);
  });

  it('a área de clique nunca é menor que a placa', () => {
    for (const tipo of TIPOS) {
      const mundo = panelWorldExtent(comTipo(tipo));
      const clique = panelPickExtent(comTipo(tipo));
      expect(clique.width).toBeGreaterThanOrEqual(mundo.width);
      expect(clique.height).toBeGreaterThanOrEqual(mundo.height);
    }
  });
});

describe('o texto habita a placa sem vazar', () => {
  it('os seis tipos produzem recorte coincidente com a área útil da placa', () => {
    // O recorte é expresso no espaço do **objeto de texto**, cuja origem é o canto
    // superior esquerdo útil e cujo conteúdo desce. Antes ele estava em coordenadas do
    // painel, centradas — e por isso recortava o lugar errado, o que só não causava
    // defeito porque nunca chegava a ser aplicado ao objeto.
    for (const tipo of TIPOS) {
      const d = comTipo(tipo);
      const extent = panelWorldExtent(d);
      const layout = layoutPanelText(d, extent, linesUpTo(d, 'legible'), 'expanded');
      const [x0, y0, x1, y1] = layout.clipRect;
      // O recorte acompanha a âncora: centrado nas silhuetas pontiagudas, à esquerda
      // na folha retangular. Em qualquer uma, ele cobre exatamente a largura útil e
      // desce com a rolagem.
      expect(x1 - x0).toBeCloseTo(layout.maxWidth, 9);
      expect(layout.anchorX === 'center' ? x0 + x1 : x0).toBeCloseTo(0, 9);
      expect(y1).toBe(-layout.scrollOffset);
      expect(y0).toBeCloseTo(-layout.maxHeight - layout.scrollOffset, 9);
      expect(layout.maxWidth).toBeLessThanOrEqual(extent.width);
      expect(layout.maxHeight).toBeLessThanOrEqual(extent.height);
      expect(layout.fontSize).toBeGreaterThan(0);
    }
  });

  it('o painel selecionado mostra o conteúdo inteiro e informa quanto pode rolar', () => {
    const d = comTipo('note');
    const frases = Array.from({ length: 30 }, (_, i) => ({
      section: 'descricao' as const,
      text: `Frase número ${i} com texto suficiente para ocupar uma linha inteira da placa.`,
      priority: 100 - i,
    }));
    const layout = layoutPanelText(d, panelWorldExtent(d), frases, 'expanded');
    expect(layout.scrollable).toBe(true);
    // Nada é descartado: quem escolheu o painel pediu para ler.
    expect(layout.omittedLines).toBe(0);
    expect(layout.body).toHaveLength(frases.length);
    expect(layout.contentHeight).toBeGreaterThan(layout.maxHeight);
    expect(layout.maxScroll).toBeCloseTo(layout.contentHeight - layout.maxHeight, 9);
  });

  it('a rolagem é limitada ao que existe abaixo, nos dois extremos', () => {
    const d = comTipo('note');
    const frases = Array.from({ length: 30 }, (_, i) => ({
      section: 'descricao' as const,
      text: `Frase número ${i} com texto suficiente para ocupar uma linha inteira da placa.`,
      priority: 100 - i,
    }));
    const extent = panelWorldExtent(d);
    const limite = layoutPanelText(d, extent, frases, 'expanded').maxScroll;
    expect(layoutPanelText(d, extent, frases, 'expanded', -50).scrollOffset).toBe(0);
    expect(layoutPanelText(d, extent, frases, 'expanded', 1e6).scrollOffset).toBeCloseTo(limite, 9);
    // Rolar move o bloco para cima e o recorte desce junto, para os dois continuarem
    // coincidindo com a placa.
    const rolado = layoutPanelText(d, extent, frases, 'expanded', limite / 2);
    expect(rolado.localY).toBeGreaterThan(
      layoutPanelText(d, extent, frases, 'expanded', 0).localY,
    );
    expect(rolado.clipRect[3]).toBeCloseTo(-limite / 2, 9);
  });

  it('bloco curto se centra na forma; bloco que rola parte do topo', () => {
    // Texto curto ancorado no topo deixava a metade de baixo do losango vazia, e o
    // bloco lia como se tivesse escorregado para fora do lugar. Centrar só é possível
    // quando não há rolagem: havendo, o topo é de onde a rolagem parte.
    const d = comTipo('quorum'); // losango: a forma em que o vazio embaixo saltava aos olhos
    const extent = panelWorldExtent(d);
    const curto = layoutPanelText(d, extent, [{ section: 'descricao', text: 'uma linha só', priority: 1 }], 'expanded');
    expect(curto.maxScroll).toBe(0);
    expect(curto.verticalPadding).toBeGreaterThan(0);

    const longo = layoutPanelText(d, extent, linesUpTo(d, 'expanded'), 'expanded', 0);
    if (longo.maxScroll > 0) expect(longo.verticalPadding).toBe(0);
  });

  it('nível que não rola continua omitindo o que não cabe', () => {
    // A abertura ao conteúdo inteiro vale para o painel escolhido, e só para ele: um
    // painel distante que despejasse tudo seria ilegível.
    const d = comTipo('note');
    const frases = Array.from({ length: 30 }, (_, i) => ({
      section: 'descricao' as const,
      text: `Frase número ${i} com texto suficiente para ocupar uma linha inteira da placa.`,
      priority: 100 - i,
    }));
    const layout = layoutPanelText(d, panelWorldExtent(d), frases, 'legible');
    expect(layout.scrollable).toBe(false);
    expect(layout.maxScroll).toBe(0);
    expect(layout.body.length).toBeLessThan(frases.length);
  });

  it('o afastamento em z é constante e não nulo', () => {
    const alturas = TIPOS.map((t) => layoutPanelText(comTipo(t), panelWorldExtent(comTipo(t)), [], 'expanded').localZ);
    expect(new Set(alturas).size).toBe(1);
    expect(alturas[0]!).toBeGreaterThan(0);
  });

  it('a proporção continua mandando no espaço disponível', () => {
    const ponte = layoutPanelText(comTipo('bridge'), panelWorldExtent(comTipo('bridge')), [], 'expanded');
    const quorum = layoutPanelText(comTipo('quorum'), panelWorldExtent(comTipo('quorum')), [], 'expanded');
    // A ponte é a mais deitada de todas, e o quórum — deitado desde 3.5-F, para o texto
    // parar de encolher — continua atrás dela. Proporção distingue tipo; ela não faz
    // dois tipos convergirem para a mesma placa.
    expect(ponte.maxWidth).toBeGreaterThan(ponte.maxHeight);
    expect(ponte.maxWidth / ponte.maxHeight).toBeGreaterThan(quorum.maxWidth / quorum.maxHeight);
  });
});

describe('cada degrau de LOD mostra outra coisa', () => {
  const d = comTipo('moc');
  const extent = panelWorldExtent(d);
  const frases = linesUpTo(d, 'expanded');
  const em = (nivel: Parameters<typeof layoutPanelText>[3]) =>
    layoutPanelText(d, extent, frases, nivel);

  it('distante e estrutural não escrevem nada', () => {
    for (const nivel of ['distant', 'structural'] as const) {
      expect(composeText(em(nivel))).toBe('');
    }
  });

  it('identificável resolve o título, e o bloco da placa fica vazio', () => {
    // O título saiu de dentro da placa: ele é desenhado acima e fora dela, por um
    // objeto próprio. O layout continua **resolvendo** o título — com elipse e limite —
    // porque quem desenha precisa do texto já ajustado; o que mudou é que ele não entra
    // mais no bloco, e por isso a placa não gasta linha dizendo o próprio nome.
    const layout = em('identifiable');
    expect(layout.header).toBe('');
    expect(layout.title).not.toBe('');
    expect(layout.body).toEqual([]);
    expect(composeText(layout)).toBe('');
  });

  it('legível acrescenta categoria e uma frase', () => {
    const layout = em('legible');
    expect(layout.header).toBe(d.category);
    expect(layout.body.length).toBeLessThanOrEqual(1);
    expect(composeText(layout).split('\n')[0]).toBe(d.category.toUpperCase());
  });

  it('expandido é o único que abre o conteúdo estruturado', () => {
    const legivel = em('legible');
    const expandido = em('expanded');
    expect(expandido.body.length).toBeGreaterThan(legivel.body.length);
  });

  it('a densidade nunca diminui ao subir de degrau', () => {
    // Um degrau que mostra menos que o anterior não é degrau: é oscilação.
    const ordem = ['distant', 'structural', 'identifiable', 'legible', 'expanded'] as const;
    const tamanhos = ordem.map((nivel) => composeText(em(nivel)).length);
    expect(tamanhos).toEqual([...tamanhos].sort((a, b) => a - b));
  });
});

describe('o truncamento acontece na saída, nunca no descritor', () => {
  it('o título canônico permanece íntegro e só a saída ganha elipse', () => {
    const longo = 'Ç'.repeat(300);
    const d = describePanel({ ...base, title: longo });
    const layout = layoutPanelText(d, panelWorldExtent(d), [], 'expanded');
    expect(d.title).toBe(longo);
    expect(layout.title.length).toBeLessThan(longo.length);
    expect(layout.title.endsWith('…')).toBe(true);
    expect(layout.titleTruncated).toBe(true);
  });

  it('linha de corpo que não cabe é omitida inteira, nunca cortada', () => {
    const d = comTipo('endpoint');
    const frases = [
      { section: 'estado' as const, text: 'Uma frase longa. '.repeat(40), priority: 90 },
      { section: 'estado' as const, text: 'Outra frase longa. '.repeat(40), priority: 80 },
    ];
    // Medido num nível que não rola: onde há omissão, ela é da frase inteira. No nível
    // expandido não há omissão nenhuma — ver o teste da rolagem.
    const layout = layoutPanelText(d, panelWorldExtent(d), frases, 'legible');
    for (const linha of layout.body) {
      expect(frases.some((f) => f.text === linha)).toBe(true);
    }
    expect(layout.omittedLines).toBeGreaterThan(0);
  });

  it('a composição é categoria e exatamente o corpo aprovado', () => {
    // Até 3.3 esta composição parava na primeira linha de corpo, mesmo quando o
    // layout tinha aprovado outras: era por isso que aproximar aumentava o painel
    // sem aumentar o que se lia. Agora sai tudo o que coube — e nada além disso.
    //
    // O título deixou de entrar aqui em 3.5-E: ele é desenhado fora da placa.
    const d = comTipo('moc');
    const layout = layoutPanelText(d, panelWorldExtent(d), linesUpTo(d, 'expanded'), 'expanded');
    const linhas = composeText(layout).split('\n');
    expect(linhas[0]).toBe(d.category.toUpperCase());
    // Uma linha vazia separa a categoria do corpo: colada, ela lia como se fosse o
    // primeiro heading do texto. O orçamento do layout já conta com ela.
    expect(linhas[1]).toBe(' ');
    expect(linhas.slice(2)).toEqual(layout.body);
    expect(linhas).not.toContain(layout.title);
  });

  it('expandir a placa nunca reduz o que o painel mostra', () => {
    // É a propriedade que sustenta o estado expandido: ele não tem regra de layout
    // própria — é a mesma placa maior, e o conteúdo cresce como consequência.
    for (const tipo of TIPOS) {
      const d = comTipo(tipo);
      const compacto = panelWorldExtent(d);
      const expandido = { width: compacto.width * 2.2, height: compacto.height * 2.2 };
      const frases = linesUpTo(d, 'expanded');
      const antes = layoutPanelText(d, compacto, frases, 'expanded');
      const depois = layoutPanelText(d, expandido, frases, 'expanded');
      expect(depois.body.length).toBeGreaterThanOrEqual(antes.body.length);
      expect(depois.omittedLines).toBeLessThanOrEqual(antes.omittedLines);
      expect(depois.fontSize).toBeGreaterThan(antes.fontSize);
    }
  });

  it('a raiz não recebe tipografia privilegiada', () => {
    const mocs = projecao.nodes.filter((n) => n.kind === 'moc').map(describePanel);
    const fontes = mocs.map(
      (d) => layoutPanelText(d, panelWorldExtent(d), [], 'expanded').fontSize,
    );
    expect(new Set(fontes.map((f) => f.toFixed(9))).size).toBe(1);
  });
});
