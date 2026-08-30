// Como se lê o Atlas: forma, proporção, corpo, cor e traço.
//
// Uma legenda que descreve a cena por memória do autor envelhece calada — e neste
// projeto isso seria pior que em outro, porque a cena inteira existe para afirmar coisas
// sobre o corpus com rigor. Uma legenda errada é uma afirmação errada sobre o próprio
// critério, exibida ao lado do conhecimento que ela pretende explicar.
//
// Por isso cada linha daqui é **derivada da tabela que desenha aquilo**: as silhuetas
// vêm de `SHAPE_BY_KIND`, as proporções de `proportionOf`, o traço de `EDGE_STYLES`, os
// domínios do `meta` da projeção e a cor do provedor de `PROVIDER_TOKENS`. Mudar o
// desenho muda a legenda no mesmo commit, ou o teste reprova.
//
// O que **não** está codificado em cor também é dito. O status epistêmico de uma nota é
// escrito na placa, não pintado nela; anunciar uma cor para ele faria a pessoa procurar
// na cena uma distinção que não existe.

import type { EntityKind, Projection, RelationFamily } from './contract';
import { EDGE_STYLES } from './edges';
import { proportionOf, type PanelType } from './panels';
import { PROVIDER_TOKENS } from './palette';
import { shapeOf, type PanelShape } from './panelShapes';

export interface LegendItem {
  /** O que se vê na cena. */
  mark: string;
  /** O que aquilo afirma. */
  meaning: string;
  /** Traço da relação, quando o item é uma linha. Vazio significa contínua. */
  pattern?: readonly number[];
  /** A relação corre em duas faixas paralelas. */
  doubled?: boolean;
  /** Token de cor, quando o item é uma cor. */
  token?: string;
}

export interface LegendSection {
  title: string;
  /** O porquê da seção, quando ele não é evidente do título. */
  note?: string;
  items: LegendItem[];
}

/** As silhuetas, agrupadas pelo que o nó **faz** — que é o critério que as escolheu. */
const INTENCAO: Record<PanelShape, { titulo: string; explica: string }> = {
  hexagono: { titulo: 'hexágono', explica: 'organiza: reúne outros nós sob si' },
  retangulo: { titulo: 'retângulo', explica: 'afirma: carrega texto que se lê' },
  losango: { titulo: 'losango', explica: 'decide: fecha um ciclo com um resultado' },
  triangulo: { titulo: 'triângulo', explica: 'julga: uma opinião entre várias' },
  octogono: { titulo: 'octógono', explica: 'delibera: o ciclo aberto onde se julga' },
};

/** Um exemplo por silhueta, tirado do próprio mapa de formas. */
const EXEMPLO_POR_FORMA: Record<PanelShape, EntityKind[]> = {
  hexagono: ['moc', 'quorum-member'],
  retangulo: ['note', 'evidence'],
  losango: ['quorum-decision', 'commit'],
  triangulo: ['quorum-vote'],
  octogono: ['quorum-panel'],
};

const NOME_DA_ESPECIE: Partial<Record<EntityKind, string>> = {
  moc: 'mapa de conteúdo',
  'quorum-member': 'modelo',
  note: 'nota',
  evidence: 'evidência',
  'quorum-decision': 'decisão do quórum',
  commit: 'commit',
  'quorum-vote': 'voto',
  'quorum-panel': 'painel de quórum',
};

const PROPORCAO_NOMEADA: { tipo: PanelType; nome: string }[] = [
  { tipo: 'moc', nome: 'mapa de conteúdo' },
  { tipo: 'bridge', nome: 'ponte interdisciplinar' },
  { tipo: 'note', nome: 'nota' },
  { tipo: 'quorum', nome: 'deliberação' },
];

function razao(valor: number): string {
  const alvos: [number, string][] = [
    [16 / 9, '16:9'],
    [21 / 9, '21:9'],
    [4 / 3, '4:3'],
    [3 / 2, '3:2'],
    [1, '1:1'],
  ];
  for (const [proporcao, texto] of alvos) {
    if (Math.abs(valor - proporcao) < 0.02) return texto;
  }
  return `${valor.toFixed(2)}:1`;
}

/** A legenda inteira, composta das tabelas que de fato desenham a cena. */
export function buildSceneLegend(projection: Projection): LegendSection[] {
  const formas: LegendItem[] = (
    Object.keys(INTENCAO) as PanelShape[]
  ).map((forma) => {
    const especies = EXEMPLO_POR_FORMA[forma]
      // A conferência não é decorativa: ela impede que a legenda anuncie uma silhueta
      // que o mapa de formas deixou de dar àquela espécie.
      .filter((especie) => shapeOf(especie) === forma)
      .map((especie) => NOME_DA_ESPECIE[especie] ?? especie);
    const { titulo, explica } = INTENCAO[forma];
    return {
      mark: titulo,
      meaning: especies.length > 0 ? `${explica} — ${especies.join(', ')}` : explica,
    };
  });

  const proporcoes: LegendItem[] = PROPORCAO_NOMEADA.map(({ tipo, nome }) => ({
    mark: razao(proportionOf(tipo)),
    meaning: nome,
  }));

  const corpo: LegendItem[] = [
    { mark: 'sólido', meaning: 'consolidado: já é conhecimento do corpus' },
    {
      mark: 'vazado',
      meaning: 'proposto, temporário ou recusado: ainda não é, ou deixou de ser',
    },
  ];

  const relacoes: LegendItem[] = projection.meta.relationFamilies.map((familia) => {
    const estilo = EDGE_STYLES[familia as RelationFamily];
    return {
      mark: estilo.label,
      meaning: estilo.doubled
        ? 'duas faixas paralelas'
        : estilo.pattern.length === 0
          ? 'linha contínua'
          : 'linha tracejada',
      pattern: estilo.pattern,
      doubled: estilo.doubled,
    };
  });

  const cores: LegendItem[] = [
    ...projection.meta.domains.map((dominio) => ({
      mark: dominio.label,
      meaning: 'domínio do corpus',
      token: dominio.paletteToken,
    })),
    ...Object.keys(PROVIDER_TOKENS).map((token) => ({
      mark: token.slice('P:'.length),
      meaning: 'provedor, no matiz da marca',
      token,
    })),
  ];

  return [
    {
      title: 'Silhueta',
      note: 'A forma diz o que o nó faz, e sobrevive em escala de cinza.',
      items: formas,
    },
    { title: 'Proporção', note: 'O formato da placa separa as espécies.', items: proporcoes },
    { title: 'Corpo', note: 'A solidez carrega o estado canônico.', items: corpo },
    {
      title: 'Linhas',
      note: 'Só relação declarada vira aresta. Analogia e vocabulário comum não ligam nada.',
      items: relacoes,
    },
    { title: 'Cor', note: 'Domínio no corpus; marca do provedor na camada viva.', items: cores },
    {
      title: 'Status epistêmico',
      // A tentação seria dar cor a isto. A Política tem dez status, e dez matizes
      // distinguíveis já são a paleta inteira dos domínios — além de que status não é
      // categoria, é grau de confiança, e grau não se lê em matiz.
      note: 'Escrito na placa, nunca pintado nela: leia o cabeçalho da nota.',
      items: [],
    },
  ];
}
