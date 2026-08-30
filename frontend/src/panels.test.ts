// O contrato do descritor de painel, provado sem GPU.
//
// Este arquivo é o gate do incremento 1 da ADR-002: se a gramática visual estiver
// errada, ela erra aqui, antes de existir pixel. Nada abaixo instancia cena.

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import type { EntityKind, ProjectionNode } from './contract';
import { node, projectionFixture } from './fixture';
import { LOD_ORDER } from './lod';
import {
  BRIDGE_DOMAIN,
  MODEL_DOMAIN,
  WORKER_DOMAIN,
  HORIZONTAL_RELATIONS,
  VERTICAL_RELATIONS,
  describePanel,
  linesUpTo,
  panelExtent,
  panelTypeOf,
  type PanelType,
} from './panels';

const projecao = projectionFixture();

function nodeOf(overrides: Partial<ProjectionNode> = {}): ProjectionNode {
  const base = projecao.nodes.find((n) => n.kind === 'note')!;
  return { ...base, ...overrides };
}

function comKind(kind: EntityKind, overrides: Partial<ProjectionNode> = {}): ProjectionNode {
  const operacional = kind !== 'note' && kind !== 'moc' && kind !== 'reference';
  return nodeOf({
    kind,
    layer: operacional ? 'operational' : 'epistemic',
    ...overrides,
  });
}

const EXEMPLARES: Record<PanelType, ProjectionNode> = {
  moc: comKind('moc', { id: 'Física/MOC — Física Teórica', domainId: 'fisica' }),
  bridge: comKind('moc', {
    id: 'Pontes/Ponte — Formalismo Matemático da Física',
    title: 'Ponte — Formalismo Matemático da Física',
    domainId: BRIDGE_DOMAIN,
    domainLabel: 'pontes',
  }),
  note: comKind('note'),
  quorum: comKind('quorum-decision', {
    operational: { validVotes: 3, providerCount: 2, familyCount: 3, action: 'promote' },
  }),
  // Sem `eventType`: uma atividade que **não** vem da trilha viva. Com ele, ela seria
  // classificada como passo, que é o que todo evento é agora.
  task: comKind('activity', { operational: { task: 'aut-0001', actor: 'worker' } }),
  // A nuvem de modelos, desde 3.5-F: o provedor é âncora e o modelo é folha, e os dois
  // se distinguem pelo domínio — que é o mesmo mecanismo que distingue ponte de MOC.
  endpoint: comKind('quorum-member', {
    id: 'op/model/groq/llama-3.3',
    domainId: MODEL_DOMAIN,
    operational: { provider: 'groq', endpoint: 'llama-3.3', executionCount: 12 },
  }),
  provider: comKind('agent', {
    id: 'op/provider/groq',
    domainId: MODEL_DOMAIN,
    operational: { provider: 'groq', modelCount: 3, executionCount: 70 },
  }),
  // O papel do trabalho. Ele declara `role` como uma execução declara, e o que o separa
  // dela é o domínio: quem executou é história; o trabalhador é configuração.
  worker: comKind('agent', {
    id: 'op/worker/verificador-factual',
    domainId: WORKER_DOMAIN,
    operational: {
      role: 'verificador-factual',
      workerClass: 'avaliador',
      summary: 'procura erros objetivos',
      area: 'knowledge/',
      concurrencyMax: 3,
    },
  }),
  // Um passo da trilha viva. O `kind` varia — atividade, evidência, voto —, e o tipo de
  // painel não: eles são a mesma coisa lida na mesma nuvem.
  evento: comKind('evidence', {
    id: 'runtime:event:runtime-000001',
    domainId: 'operacional/live',
    operational: { eventType: 'evidence_recorded', actor: 'orquestrador' },
  }),
};

describe('cada tipo de painel tem descritor próprio', () => {
  it('classifica todos e nenhum cai fora da taxonomia', () => {
    for (const [esperado, node] of Object.entries(EXEMPLARES)) {
      expect(panelTypeOf(node)).toBe(esperado);
      expect(describePanel(node).panelType).toBe(esperado);
    }
  });

  it('MOC no domínio de pontes vira ponte, e só ali', () => {
    expect(panelTypeOf(EXEMPLARES.bridge)).toBe('bridge');
    expect(panelTypeOf(comKind('moc', { domainId: 'fisica' }))).toBe('moc');
  });
});

describe('a categoria carrega a ontologia', () => {
  it('sai por extenso, nunca como sigla', () => {
    for (const node of Object.values(EXEMPLARES)) {
      const { category } = describePanel(node);
      // Palavra, não sigla: começa em maiúscula e tem minúsculas no corpo. "Nota"
      // é curta e legítima; "MOC" seria sigla e reprovaria aqui.
      expect(category).toMatch(/^[A-ZÀ-Ú][a-zà-ú]/);
      expect(category).not.toMatch(/^[A-Z]{2,6}$/);
    }
  });

  it('aparece já no nível estrutural, antes de qualquer título', () => {
    const descritor = describePanel(EXEMPLARES.moc);
    const estrutural = linesUpTo(descritor, 'structural').map((l) => l.text);
    expect(estrutural).toContain(descritor.category);
  });
});

describe('cor vem do domínio e de mais nada', () => {
  it('o token é o do nó, sem variação por tipo de painel', () => {
    const token = 'D07';
    for (const node of Object.values(EXEMPLARES)) {
      const comToken = { ...node, visual: { ...node.visual, paletteToken: token } };
      expect(describePanel(comToken).paletteToken).toBe(token);
    }
  });

  it('nenhum campo do descritor guarda cor fora do token', () => {
    const serializado = JSON.stringify(describePanel(EXEMPLARES.bridge));
    expect(serializado).not.toMatch(/#[0-9a-f]{6}/i);
    expect(serializado).not.toMatch(/oklch|rgb\(/i);
  });
});

describe('silhueta não vira grandeza', () => {
  it('ponte e MOC ocupam a mesma área, mudando só a forma', () => {
    const ponte = describePanel(EXEMPLARES.bridge);
    const moc = describePanel(EXEMPLARES.moc);
    const areaPonte = panelExtent(ponte).width * panelExtent(ponte).height;
    const areaMoc = panelExtent(moc).width * panelExtent(moc).height;

    expect(areaPonte).toBeCloseTo(areaMoc, 10);
    expect(ponte.proportion).toBeGreaterThan(moc.proportion);
    expect(panelExtent(ponte).width).toBeGreaterThan(panelExtent(moc).width);
  });

  it('o MOC de raiz não tem tratamento superior ao dos demais MOCs', () => {
    const mocs = projecao.nodes.filter((n) => n.kind === 'moc').map(describePanel);
    const raiz = mocs.find((m) => m.entityId.includes('Índice')) ?? mocs[0]!;
    for (const moc of mocs) {
      expect(moc.sizeStep).toBe(raiz.sizeStep);
      expect(moc.proportion).toBe(raiz.proportion);
      expect(moc.variant).toBe(raiz.variant);
      expect(moc.truncation).toEqual(raiz.truncation);
    }
  });

  it('proporção não entra na prioridade de leitura', () => {
    const largo = describePanel({
      ...EXEMPLARES.bridge,
      visual: { ...EXEMPLARES.bridge.visual, labelPriority: 5 },
    });
    const estreito = describePanel({
      ...EXEMPLARES.quorum,
      visual: { ...EXEMPLARES.quorum.visual, labelPriority: 5 },
    });
    expect(largo.lodPriority).toBe(estreito.lodPriority);
  });
});

describe('a ponte declara o que não afirma', () => {
  it('tem bloco obrigatório de escopo negativo', () => {
    const ponte = describePanel(EXEMPLARES.bridge);
    expect(ponte.sections).toContain('escopo-negativo');
    const texto = linesUpTo(ponte, 'expanded')
      .filter((l) => l.section === 'escopo-negativo')
      .map((l) => l.text)
      .join(' ');
    expect(texto).not.toBe('');
    expect(texto.toLowerCase()).toContain('não');
  });

  it('nenhum outro tipo recebe esse bloco por engano', () => {
    for (const [tipo, node] of Object.entries(EXEMPLARES)) {
      if (tipo === 'bridge') continue;
      expect(describePanel(node).sections).not.toContain('escopo-negativo');
    }
  });
});

describe('nada privado atravessa para a projeção visual', () => {
  const PROIBIDOS = [
    '<think',
    'reasoning',
    'raciocínio',
    'prompt',
    'api_key',
    'apikey',
    'gsk_',
    'sk-or-v1-',
    'nvapi-',
    'AIza',
    'raw_response',
  ];

  it('nenhuma frase de nenhum tipo carrega marca proibida', () => {
    for (const node of Object.values(EXEMPLARES)) {
      const serializado = JSON.stringify(describePanel(node)).toLowerCase();
      for (const marca of PROIBIDOS) {
        expect(serializado).not.toContain(marca.toLowerCase());
      }
    }
  });

  it('campo desconhecido do runtime não vira frase', () => {
    const contaminado = comKind('quorum-vote', {
      operational: {
        validVotes: 2,
        // Campo fora da lista branca: precisa ser ignorado, não interpolado.
        ...({ segredo: 'RACIOCINIO_INTERNO_NAO_PERSISTIR' } as Record<string, unknown>),
      },
    });
    const serializado = JSON.stringify(describePanel(contaminado));
    expect(serializado).not.toContain('RACIOCINIO_INTERNO_NAO_PERSISTIR');
    expect(serializado).not.toContain('segredo');
  });
});

describe('o LOD aumenta densidade sem trocar a entidade', () => {
  it('cada nível só acrescenta, nunca substitui', () => {
    const descritor = describePanel(EXEMPLARES.note);
    let anterior = 0;
    for (const nivel of LOD_ORDER) {
      const total = linesUpTo(descritor, nivel).length;
      expect(total).toBeGreaterThanOrEqual(anterior);
      anterior = total;
    }
  });

  it('o nível distante não mostra letra alguma', () => {
    for (const node of Object.values(EXEMPLARES)) {
      expect(linesUpTo(describePanel(node), 'distant')).toEqual([]);
    }
  });

  it('o entityId é o mesmo em todos os níveis', () => {
    const descritor = describePanel(EXEMPLARES.quorum);
    for (const nivel of LOD_ORDER) {
      const linhas = linesUpTo(descritor, nivel);
      expect(descritor.entityId).toBe(EXEMPLARES.quorum.id);
      expect(linhas.every((l) => typeof l.text === 'string')).toBe(true);
    }
  });

  it('a ordem devolvida respeita a prioridade declarada', () => {
    const linhas = linesUpTo(describePanel(EXEMPLARES.quorum), 'expanded');
    const prioridades = linhas.map((l) => l.priority);
    expect([...prioridades].sort((a, b) => b - a)).toEqual(prioridades);
  });
});

describe('entrada difícil não quebra o descritor', () => {
  it('título longo continua íntegro no descritor, com política de corte declarada', () => {
    const longo = 'Ç'.repeat(400);
    const descritor = describePanel(nodeOf({ title: longo }));
    // O descritor não trunca: ele declara como truncar. Cortar aqui perderia o
    // título canônico para quem precisa dele inteiro.
    expect(descritor.title).toBe(longo);
    expect(descritor.truncation.titleMaxChars).toBeGreaterThan(0);
    expect(descritor.truncation.titlePolicy).toBe('ellipsis');
    expect(descritor.truncation.bodyPolicy).toBe('omit-whole-line');
  });

  it('Unicode composto e emoji atravessam sem mutilar', () => {
    const titulo = 'Seleção Natural Cosmológica ⇄ Física 🜂';
    expect(describePanel(nodeOf({ title: titulo })).title).toBe(titulo);
  });

  it('campos ausentes encurtam o painel em vez de inventar texto', () => {
    const magro = comKind('quorum-vote', { operational: {} });
    const descritor = describePanel(magro);
    const frases = linesUpTo(descritor, 'expanded');
    expect(frases.every((l) => l.text.trim().length > 0)).toBe(true);
    expect(frases.some((l) => l.text.includes('undefined'))).toBe(false);
    expect(frases.some((l) => l.text.includes('null'))).toBe(false);
  });
});

describe('a saída é determinística', () => {
  it('a mesma entidade produz o mesmo descritor byte a byte', () => {
    for (const node of Object.values(EXEMPLARES)) {
      expect(JSON.stringify(describePanel(node))).toBe(JSON.stringify(describePanel(node)));
    }
  });
});

describe('as âncoras separam dependência de contraste', () => {
  it('relação vertical entra e sai por topo ou rodapé', () => {
    const { anchors } = describePanel(EXEMPLARES.note);
    for (const familia of VERTICAL_RELATIONS) {
      expect(['top', 'bottom']).toContain(anchors[familia].out);
      expect(['top', 'bottom']).toContain(anchors[familia].in);
      expect(anchors[familia].out).not.toBe(anchors[familia].in);
    }
  });

  it('relação horizontal entra e sai por lateral', () => {
    const { anchors } = describePanel(EXEMPLARES.note);
    for (const familia of HORIZONTAL_RELATIONS) {
      expect(['left', 'right']).toContain(anchors[familia].out);
      expect(['left', 'right']).toContain(anchors[familia].in);
      expect(anchors[familia].out).not.toBe(anchors[familia].in);
    }
  });

  it('toda família do contrato tem âncora, sem sobra nem falta', () => {
    const { anchors } = describePanel(EXEMPLARES.moc);
    const declaradas = [...VERTICAL_RELATIONS, ...HORIZONTAL_RELATIONS].sort();
    expect(Object.keys(anchors).sort()).toEqual(declaradas);
  });
});

describe('o módulo é puro', () => {
  it('não importa Three.js, troika nem DOM', () => {
    const fonte = readFileSync(join(__dirname, 'panels.ts'), 'utf-8');
    const imports = [...fonte.matchAll(/^import[^;]+from\s+'([^']+)'/gm)].map(
      (m) => m[1]!,
    );
    for (const origem of imports) {
      expect(origem).not.toMatch(/three|troika|dom/i);
      expect(origem.startsWith('.')).toBe(true);
    }
    expect(fonte).not.toMatch(/\b(document|window|navigator|globalThis)\b/);
  });
});

describe('as três contagens do quórum não se confundem', () => {
  it('a frase de votos fala de computados, não de recebidos', () => {
    const descritor = describePanel(
      comKind('quorum-decision', {
        operational: { validVotes: 2, providerCount: 2, familyCount: 2 },
      }),
    );
    const votos = linesUpTo(descritor, 'expanded')
      .filter((l) => l.section === 'votos')
      .map((l) => l.text)
      .join(' ');
    expect(votos).toContain('A decisão computou');
    expect(votos).not.toMatch(/recebeu|legív/i);
  });

  it('validação estrutural e cômputo são ditos como coisas distintas', () => {
    const valido = describePanel(
      comKind('quorum-vote', { operational: { schemaValid: true, validVotes: 1 } }),
    );
    const frases = linesUpTo(valido, 'expanded').map((l) => l.text);
    const estrutural = frases.find((t) => t.includes('validação estrutural'));
    expect(estrutural).toBeDefined();
    // Passar na estrutura não afirma ter contado.
    expect(estrutural).not.toMatch(/comput|contad/i);
  });

  it('a recusa estrutural mostra a regra da política, não o rótulo do gate', () => {
    const descritor = describePanel(
      comKind('quorum-decision', {
        operational: {
          action: 'reject',
          reason: 'falha estrutural objetiva registrada',
          blockingIssue:
            'Nenhum wikilink foi declarado com as relações do vocabulário permitido.',
          validVotes: 2,
          providerCount: 2,
          familyCount: 2,
        },
      }),
    );
    const frases = linesUpTo(descritor, 'legible').map((l) => l.text);
    expect(frases.join(' ')).toContain(
      'A política recusou: Nenhum wikilink foi declarado com as relações do vocabulário permitido.',
    );
    expect(frases.join(' ')).not.toContain('falha estrutural objetiva registrada');
  });
});

describe('a nota mostra o próprio conteúdo, não só o que se sabe sobre ela', () => {
  it('abertura e claims entram no nível expandido, com status e evidência', () => {
    // A projeção levava só metadado, e o painel aberto mostrava frases sobre a nota e
    // nenhuma linha dela — não havia o que rolar porque não havia conteúdo.
    const nota = node('Física/Entropia', {
      kind: 'note',
      summary: 'A abertura da nota, dita em prosa.',
      claims: [
        {
          id: 'CLM-FIS-ENT-001',
          statement: 'Entropia cresce em sistema isolado.',
          status: 'established',
          evidence: 'Callen, cap. 4.',
        },
        {
          id: 'CLM-FIS-ENT-002',
          statement: 'A seta do tempo não decorre disso sozinha.',
          status: 'model-dependent',
          evidence: null,
        },
      ],
    });
    const linhas = linesUpTo(describePanel(nota), 'expanded').map((l) => l.text);
    const tudo = linhas.join('\n');

    expect(tudo).toContain('A abertura da nota, dita em prosa.');
    expect(tudo).toContain('CLM-FIS-ENT-001');
    expect(tudo).toContain('Entropia cresce em sistema isolado.');
    // O status sai por extenso, e não como token do vocabulário fechado.
    expect(tudo).toContain('consolidado');
    expect(tudo).toContain('dependente de modelo');
    expect(tudo).toContain('Evidência de CLM-FIS-ENT-001: Callen, cap. 4.');
    // Claim sem evidência não inventa uma linha de evidência vazia.
    expect(tudo).not.toContain('Evidência de CLM-FIS-ENT-002');
  });

  it('nota sem claims nem abertura continua descrevendo o que sabe', () => {
    const linhas = linesUpTo(describePanel(node('Física/Vazia', { kind: 'note' })), 'expanded');
    expect(linhas.length).toBeGreaterThan(0);
  });
});

describe('a deliberação também é lida, não exibida em bruto', () => {
  // O modelo escreve para ser renderizado, e escreve muito: medido na projeção viva, 31
  // nós operacionais trazem `**Texto da Proposta:**`, cercas de código e blocos YAML no
  // campo que o painel desenha. O padrão tipográfico valia só para o corpus, e a
  // deliberação — que é onde nasce quase todo o texto da cena — continuava crua.
  const comProposta = (candidate: string) =>
    linesUpTo(
      describePanel(
        node('op/quorum/abc/panel', {
          kind: 'quorum-panel',
          layer: 'operational',
          domainId: 'operacional',
          operational: { panelId: 'abc', candidate },
        }),
      ),
      'expanded',
    )
      .map((linha) => linha.text)
      .join('\n');

  it('resolve ênfase, cerca e heading no texto que o modelo escreveu', () => {
    const tudo = comProposta(
      '```markdown\n# PROPOSTA\n\n**Texto:** a padronização de metadados `reduz` a divergência.\n```',
    );
    expect(tudo).toContain('Proposta: PROPOSTA Texto: a padronização de metadados reduz a divergência.');
    expect(tudo).not.toContain('```');
    expect(tudo).not.toContain('**');
    expect(tudo).not.toContain('# ');
  });

  it('mantém o item de lista legível quando ele vira linha corrida', () => {
    const tudo = comProposta('- primeiro ponto\n- segundo ponto');
    expect(tudo).toContain('· primeiro ponto · segundo ponto');
  });

  it('resolve wikilink na tarefa, como faz na nota', () => {
    const linhas = linesUpTo(
      describePanel(
        node('op/quorum/def/panel', {
          kind: 'quorum-panel',
          layer: 'operational',
          domainId: 'operacional',
          operational: { panelId: 'def', task: 'Revisar [[Física/Entropia|entropia]].' },
        }),
      ),
      'expanded',
    ).map((linha) => linha.text);
    expect(linhas.join('\n')).toContain('Tarefa: Revisar entropia.');
  });
});

describe('o painel vivo não diz a mesma coisa duas vezes', () => {
  // Na nuvem de raciocínio quase todo painel é um evento com narração, e a narração era
  // escrita por dois caminhos: o bloco que vale para qualquer painel vivo e o ramo de
  // evento, que a repetia numa prioridade diferente. O painel exibia a mesma frase duas
  // vezes, uma embaixo da outra.
  it('escreve a narração uma vez só', () => {
    const linhas = linesUpTo(
      describePanel(
        node('runtime:event:x', {
          kind: 'activity',
          layer: 'operational',
          domainId: 'operacional/live',
          operational: {
            eventId: 'x',
            eventType: 'call_started',
            narration: 'Consultando o provedor sobre a proposta.',
            provider: 'groq',
            endpoint: 'qwen/qwen3',
          },
        }),
      ),
      'expanded',
    ).map((linha) => linha.text);
    const repetida = linhas.filter(
      (texto) => texto === 'Consultando o provedor sobre a proposta.',
    );
    expect(repetida).toHaveLength(1);
    expect(new Set(linhas).size).toBe(linhas.length);
  });
});
