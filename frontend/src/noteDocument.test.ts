// O documento da nota vira linhas sem perder o que o Markdown carrega — e sem mostrar a
// marcação que o carrega.
//
// O painel aberto mostrava cabeçalho, uma frase de resumo e uma contagem de afirmações —
// e depois espaço vazio. A rolagem não estava quebrada: não havia o que rolar. Resolvido
// isso, sobrou o outro defeito: o painel exibia `## Finalidade` e `**negrito**` como
// texto. Estes testes prendem os dois contratos: conteúdo até o EOF, e conteúdo lido.

import { describe, expect, it } from 'vitest';

import { documentLines } from './noteDocument';

const DOCUMENTO = `---
title: Memória
kind: nota
epistemic_status: supported
---

# Memória

Como uma experiência vira um traço durável?
E o que acontece com ele ao longo do tempo?

## Afirmações

- CLM-COG-MEM-001 — a consolidação depende de síntese proteica.
- CLM-COG-MEM-002 — reconsolidação reabre o traço.

Ver [[Bases Neurais da Cognição]] <!-- relation:prerequisite -->.

\`\`\`python
def consolidar(traco):
    return traco

\`\`\`

Última linha antes do EOF.
`;

describe('o documento da nota', () => {
  const linhas = documentLines(DOCUMENTO, { title: 'Memória' });
  const textos = linhas.map((linha) => linha.text);

  it('vai até o EOF', () => {
    expect(textos.at(-1)).toBe('Última linha antes do EOF.');
  });

  it('não leva o frontmatter, que é metadado e não corpo', () => {
    expect(textos.join('\n')).not.toContain('epistemic_status');
    expect(textos.join('\n')).not.toContain('kind: nota');
  });

  it('não repete o título que o painel já desenha acima da placa', () => {
    expect(textos.join('\n')).not.toContain('# Memória');
    // Mas um heading de nível dois com o mesmo nome continuaria valendo: o que sai é o
    // título de abertura, não qualquer menção.
    expect(documentLines('## Memória\n', { title: 'Memória' }).map((l) => l.text)).toEqual([
      'MEMÓRIA',
    ]);
  });

  it('reconhece o título mesmo escrito em outra caixa e sem acento', () => {
    // O caso real: o frontmatter diz "Bioenergética e Termodinâmica dos Sistemas Vivos"
    // e o corpo abre com a mesma frase em caixa de frase. São o mesmo título, e o painel
    // escrevia os dois — um acima da placa, outro dentro dela.
    const linhas = documentLines('# bioenergetica e termodinamica\n\nCorpo.\n', {
      title: 'Bioenergética e Termodinâmica',
    });
    expect(linhas.map((l) => l.text)).toEqual(['Corpo.']);
  });

  it('dá hierarquia ao heading e marcador ao item, sem mostrar a marcação', () => {
    expect(textos).toContain('AFIRMAÇÕES');
    expect(textos).toContain('• CLM-COG-MEM-001 — a consolidação depende de síntese proteica.');
    expect(textos.join('\n')).not.toContain('##');
    expect(textos.join('\n')).not.toContain('- CLM');
  });

  it('o nível do heading vira recuo, porque o corpo da fonte é um só', () => {
    const linhas = documentLines('## Dois\n\n### Três\n\n#### Quatro\n');
    expect(linhas.map((l) => l.text).filter((t) => t.trim() !== '')).toEqual([
      'DOIS',
      '  TRÊS',
      '    QUATRO',
    ]);
  });

  it('resolve wikilink, link e ênfase: fica o texto, some o que o declarava', () => {
    expect(textos.some((t) => t.includes('Ver Bases Neurais da Cognição.'))).toBe(true);
    expect(textos.join('\n')).not.toContain('[[');
    expect(textos.join('\n')).not.toContain('relation:');
    expect(documentLines('**forte** e *fraco* e `código`.').map((l) => l.text)).toEqual([
      'forte e fraco e código.',
    ]);
    expect(documentLines('Ver [o dossiê](https://exemplo/x).').map((l) => l.text)).toEqual([
      'Ver o dossiê.',
    ]);
    // O caminho do wikilink é endereço, não texto: quem lê quer o nome da nota.
    expect(documentLines('Ver [[Física/Entropia|entropia]].').map((l) => l.text)).toEqual([
      'Ver entropia.',
    ]);
    expect(documentLines('Ver [[Física/Entropia]].').map((l) => l.text)).toEqual([
      'Ver Entropia.',
    ]);
  });

  it('separa blocos com uma linha vazia, e não separa itens da mesma lista', () => {
    const linhas = documentLines('Um.\n\nDois.\n\n## Seção\n\n- a\n- b\n');
    expect(linhas.map((l) => l.text)).toEqual(['Um.', ' ', 'Dois.', ' ', 'SEÇÃO', ' ', '• a', '• b']);
  });

  it('junta as linhas de um parágrafo e separa parágrafos diferentes', () => {
    // Duas linhas de origem, um parágrafo só — é assim que o Markdown se lê.
    expect(textos).toContain(
      'Como uma experiência vira um traço durável? E o que acontece com ele ao longo do tempo?',
    );
  });

  it('preserva o bloco de código linha a linha, inclusive a vazia', () => {
    const inicio = textos.indexOf('│ PYTHON');
    expect(inicio).toBeGreaterThanOrEqual(0);
    // Indentação preservada: um bloco de código reflowado deixa de ser código. A cerca
    // sai porque é marcação; a guia à esquerda é o que diz "isto aqui é código".
    expect(textos[inicio + 1]).toBe('│ def consolidar(traco):');
    expect(textos[inicio + 2]).toBe('│     return traco');
    expect(textos[inicio + 3]).toBe(' ');
    expect(textos.join('\n')).not.toContain('```');
  });

  it('põe todas as linhas abaixo de qualquer frase derivada do descritor', () => {
    // `linesUpTo` ordena por prioridade decrescente com ordenação estável: prioridade
    // comum e menor que a de qualquer derivada é o que faz o documento chegar depois
    // delas e na ordem em que foi escrito.
    expect(new Set(linhas.map((l) => l.priority))).toEqual(new Set([-1]));
  });

  it('devolve lista vazia para documento sem corpo', () => {
    expect(documentLines('---\ntitle: X\n---\n')).toEqual([]);
    expect(documentLines('')).toEqual([]);
  });
});
