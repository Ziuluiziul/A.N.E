// Modo textual: o corpus continua alcançável quando o 3D não está.
//
// O dossiê reprova a cena que é o **único** modo de localizar ou auditar informação.
// Zero painéis laterais é coerente com a estética, mas não prova acessibilidade — se
// o WebGL falhar, ou se quem usa não enxerga, precisa existir outro caminho.
//
// Este modo não é um painel ao lado do Atlas: é um substituto dele, ativado por
// `?texto=1` ou automaticamente quando o WebGL não inicializa. Continua somente
// leitura, como todo o resto do visualizador.

import { loadNoteDocument, type Projection, type ProjectionEdge, type ProjectionNode } from './contract';
import { isEditableTarget } from './keyboardTarget';
import { documentLines } from './noteDocument';

const TIPOS: Record<ProjectionNode['kind'], string> = {
  note: 'nota',
  moc: 'MOC',
  reference: 'referência',
  register: 'registro',
  agent: 'agente',
  activity: 'atividade',
  evidence: 'evidência',
  proposal: 'proposta',
  commit: 'commit',
  rejection: 'rejeição',
  'temporary-file': 'arquivo temporário',
  'quorum-panel': 'painel de quórum',
  'quorum-member': 'membro do quórum',
  'quorum-vote': 'voto estruturado',
  'quorum-decision': 'decisão do quórum',
};

/** O WebGL está disponível de fato? Contexto criado, não apenas API presente. */
export function webglDisponivel(): boolean {
  try {
    const canvas = document.createElement('canvas');
    return Boolean(
      canvas.getContext('webgl2') ??
        canvas.getContext('webgl') ??
        canvas.getContext('experimental-webgl'),
    );
  } catch {
    return false;
  }
}

export function modoTextualPedido(search: string): boolean {
  const parametros = new URLSearchParams(search);
  return parametros.get('texto') === '1' || parametros.get('text') === '1';
}

/** Só o corpus tem arquivo. Pedir documento de um painel de quórum inventaria 404. */
export function referenciaDocumental(node: ProjectionNode): string | null {
  if (node.layer !== 'epistemic' || node.path === null || node.path === '') return null;
  return node.path;
}

export async function carregarCorpoTextual(
  node: ProjectionNode,
  load: (referencia: string) => Promise<string> = loadNoteDocument,
): Promise<string | null> {
  const referencia = referenciaDocumental(node);
  if (referencia === null) return null;
  return load(referencia);
}

/** Markdown da nota, já resolvido para leitura — a mesma transformação da placa 3D. */
export function corpoTextualVisivel(markdown: string, title?: string): string {
  return documentLines(markdown, { title }).map((linha) => linha.text).join('\n');
}

export type AtalhoTextual = 'focus-search' | 'clear-search' | null;

/**
 * Gramática do modo textual: `/` e Ctrl+K abrem a busca; Escape a limpa.
 *
 * Sem isto, `?texto=1` é um índice clicável. Com isto, teclado chega na nota
 * sem passar pelo 3D.
 */
export function atalhoDoModoTextual(
  key: string,
  target: EventTarget | null,
  ctrlOrMeta = false,
): AtalhoTextual {
  if (key === 'Escape') return 'clear-search';
  if (isEditableTarget(target)) return null;
  if (key === '/' || (ctrlOrMeta && (key === 'k' || key === 'K'))) return 'focus-search';
  return null;
}

function vizinhas(projection: Projection, id: string): ProjectionEdge[] {
  return projection.edges.filter(
    (edge) => edge.kind !== 'aggregated' && (edge.source === id || edge.target === id),
  );
}

/**
 * Monta a lista navegável e a busca.
 *
 * A busca casa por título, identidade e domínio, sem acento e sem caixa — quem
 * procura "estatistica" precisa achar "Estatística".
 */
export function montarModoTextual(
  container: HTMLElement,
  projection: Projection,
  origem: string,
  motivo: string,
): void {
  const normalizar = (texto: string) =>
    texto
      .normalize('NFD')
      .replace(/\p{Diacritic}/gu, '')
      .toLowerCase();

  container.replaceChildren();
  container.classList.add('modo-texto');

  const pular = document.createElement('a');
  pular.className = 'skip-link';
  pular.href = '#busca';
  pular.textContent = 'Ir à busca';

  const cabecalho = document.createElement('header');
  const titulo = document.createElement('h1');
  titulo.textContent = 'Atlas — modo textual';
  const porque = document.createElement('p');
  porque.className = 'motivo';
  porque.textContent = motivo;
  const resumo = document.createElement('p');
  const meta = projection.meta;
  resumo.textContent =
    `Contrato v${meta.contractVersion} · origem ${meta.source} · camada operacional ` +
    `${meta.operationalSource} · ${meta.counts.notes} entidades, ${meta.counts.mocs} MOCs, ` +
    `${meta.counts.wikilinks} wikilinks, ${meta.counts.claims} claims · ` +
    `carregado de ${origem} · impressão ${meta.corpusFingerprint}`;
  cabecalho.append(titulo, porque, resumo);

  const busca = document.createElement('input');
  busca.type = 'search';
  busca.id = 'busca';
  busca.placeholder = 'Buscar por título, identidade ou domínio';
  const rotuloBusca = document.createElement('label');
  rotuloBusca.htmlFor = 'busca';
  rotuloBusca.textContent = 'Buscar no corpus';
  rotuloBusca.className = 'sr-only';

  const contagem = document.createElement('p');
  contagem.setAttribute('role', 'status');
  contagem.setAttribute('aria-live', 'polite');

  const lista = document.createElement('ul');
  lista.className = 'entidades';

  const itens = projection.nodes.map((node) => {
    const item = document.createElement('li');
    const detalhe = document.createElement('details');
    const sumario = document.createElement('summary');
    sumario.textContent = `${node.title} — ${node.domainLabel} · ${TIPOS[node.kind]}`;

    const definicoes = document.createElement('dl');
    const relacoes = vizinhas(projection, node.id);
    const linhas: [string, string][] = [
      ['identidade', node.id],
      ['tipo', TIPOS[node.kind]],
      ['camada', node.layer],
      ['estado', node.canonicalState],
      ['estado epistêmico', node.epistemicStatus],
      ['domínio', node.domainLabel],
      ['claims', String(node.claimCount)],
      ['relações', `${node.incomingDegree} de entrada, ${node.outgoingDegree} de saída`],
      ['arquivo', node.path ?? '— (camada operacional)'],
      ['atualizada', node.updatedAt ?? '—'],
      ['verificada', node.verifiedAt ?? '—'],
    ];
    const operacional = node.operational;
    if (operacional) {
      if (operacional.panelId) linhas.push(['painel', operacional.panelId]);
      if (operacional.provider) linhas.push(['provedor', operacional.provider]);
      if (operacional.endpoint) linhas.push(['endpoint', operacional.endpoint]);
      if (operacional.family) linhas.push(['família', operacional.family]);
      if (operacional.decision) linhas.push(['voto', operacional.decision]);
      if (operacional.action) linhas.push(['ação', operacional.action]);
      if (operacional.confidence !== undefined) {
        linhas.push(['confiança', operacional.confidence.toFixed(2)]);
      }
      if (operacional.tally) {
        linhas.push([
          'contagem',
          Object.entries(operacional.tally)
            .map(([decision, count]) => `${decision}: ${count}`)
            .join(', '),
        ]);
      }
      if (operacional.reasoningBlockDetected !== undefined) {
        linhas.push([
          'bloco de raciocínio detectado',
          operacional.reasoningBlockDetected ? 'sim' : 'não',
        ]);
      }
      if (operacional.reasoningBlockRemoved !== undefined) {
        linhas.push([
          'bloco de raciocínio removido',
          operacional.reasoningBlockRemoved ? 'sim' : 'não',
        ]);
      }
    }
    for (const [chave, valor] of linhas) {
      const dt = document.createElement('dt');
      dt.textContent = chave;
      const dd = document.createElement('dd');
      dd.textContent = valor;
      definicoes.append(dt, dd);
    }

    if (relacoes.length > 0) {
      const dt = document.createElement('dt');
      dt.textContent = 'ligações';
      const dd = document.createElement('dd');
      const sublista = document.createElement('ul');
      for (const edge of relacoes) {
        const li = document.createElement('li');
        const outro = edge.source === node.id ? edge.target : edge.source;
        const sentido = edge.source === node.id ? '→' : '←';
        li.textContent = `${sentido} ${outro} (${edge.relations.join(', ')})`;
        sublista.append(li);
      }
      dd.append(sublista);
      definicoes.append(dt, dd);
    }

    const corpo = document.createElement('pre');
    corpo.className = 'corpo-nota';
    const referencia = referenciaDocumental(node);
    if (referencia !== null) {
      corpo.hidden = true;
      let pedido = false;
      detalhe.addEventListener('toggle', () => {
        if (!detalhe.open) {
          corpo.hidden = true;
          return;
        }
        corpo.hidden = false;
        if (pedido) return;
        pedido = true;
        corpo.textContent = 'Carregando documento…';
        void carregarCorpoTextual(node)
          .then((texto) => {
            corpo.textContent =
              texto === null || texto === '' ? '' : corpoTextualVisivel(texto, node.title);
          })
          .catch((erro: unknown) => {
            corpo.textContent = `Documento indisponível: ${String(erro)}`;
          });
      });
    }

    detalhe.append(sumario, definicoes);
    if (referencia !== null) detalhe.append(corpo);
    item.append(detalhe);
    lista.append(item);
    return { item, chave: normalizar(`${node.title} ${node.id} ${node.domainLabel}`) };
  });

  function filtrar(): void {
    const alvo = normalizar(busca.value.trim());
    let visiveis = 0;
    for (const { item, chave } of itens) {
      const mostra = alvo === '' || chave.includes(alvo);
      item.hidden = !mostra;
      if (mostra) visiveis += 1;
    }
    contagem.textContent = `${visiveis} de ${itens.length} entidades`;
  }

  busca.addEventListener('input', filtrar);
  filtrar();

  const noTeclado = (evento: KeyboardEvent) => {
    const acao = atalhoDoModoTextual(
      evento.key,
      evento.target,
      evento.ctrlKey || evento.metaKey,
    );
    if (acao === 'focus-search') {
      evento.preventDefault();
      busca.focus();
      busca.select();
      return;
    }
    if (acao === 'clear-search' && document.activeElement === busca) {
      if (busca.value !== '') {
        busca.value = '';
        filtrar();
      } else {
        busca.blur();
      }
      evento.preventDefault();
    }
  };
  document.addEventListener('keydown', noTeclado);

  container.append(pular, cabecalho, rotuloBusca, busca, contagem, lista);
}
