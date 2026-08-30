// Ponto de entrada: carrega a projeção, monta o Atlas e mantém a camada acessível.
//
// Credencial e trabalhador moram na placa. AUTO é o círculo `A` ao lado do `?`.
// O resumo da operação mora no cartão. Esc só solta a escolha.

import './style.css';

import { createAnchorRail, type AnchorRail } from './anchorRail';
import { anchorTargets } from './anchorRailModel';
import { createAtlas, type AtlasHandle } from './atlas';
import { createFreeSimulationByPopulation } from './freeLayout';
import {
  ContractError,
  isBackendProjectionOrigin,
  loadProjection,
  shouldReplaceStaticProjection,
  type Projection,
  watchProjection,
} from './contract';
import { ControlError, createControlClient, type ControlSnapshot } from './controlApi';
import type { RuntimeWorker } from './workerEntities';
import {
  ControlPollingTimeoutError,
  controlPollingMode,
  createControlPolling,
  createSerialTaskQueue,
} from './controlPolling';
import { SCENE_LEGEND } from './controls3d';
import { oklchToHex, tokenColor } from './palette';
import { buildSceneLegend } from './sceneLegend';
import { controlId } from './dock';
import { emptyDockData, type DockData } from './dockModel';
import { modoTextualPedido, montarModoTextual, webglDisponivel } from './fallback';
import { describeLiveActivity, type LiveActivityStream } from './liveActivity';
import { composeLayout } from './composeLayout';
import {
  loadOperationalSlots,
  loadPositions,
  mergePositions,
  savePositions,
  saveOperationalSlots,
} from './layoutStore';
import { selectThoughts, watchCognition, type CognitionFrame } from './cognition';
import { createFrameCoalescer } from './frameCoalescer';
import { providerIdOf, workerIdOf } from './providerNode';
import { createProviderFace, type ProviderFaceHandle } from './providerFace';
import { createSearchPalette, searchIndex, type SearchPaletteHandle } from './searchPalette';
import {
  describeProviderFace,
  describeWorkerFace,
  providerControlId,
  workerControlId,
} from './providerPanel';
import {
  advanceRuntime,
  runtimeEventLabel,
  type RuntimeSnapshot,
  watchRuntime,
} from './runtime';
import type { BackendConnectionStatus } from './transport';

const palco = exigir<HTMLDivElement>('#stage');
const vivo = exigir<HTMLParagraphElement>('#live');
const sumario = exigir<HTMLDivElement>('#a11y');
const conexao = exigir<HTMLParagraphElement>('#connection');
const legendaBotao = exigir<HTMLButtonElement>('#legend-toggle');
const legendaPainel = exigir<HTMLElement>('#legend-panel');
const atividade = exigir<HTMLElement>('#activity');
const tituloDaAtividade = exigir<HTMLElement>('#activity-title');
const detalheDaAtividade = exigir<HTMLElement>('#activity-detail');
const fluxosDaAtividade = exigir<HTMLElement>('#activity-streams');
const metaDaAtividade = exigir<HTMLElement>('#activity-meta');
const autoDaAtividade = exigir<HTMLButtonElement>('#activity-auto');
let atlasAtivo: AtlasHandle | null = null;
let railDeAncoras: AnchorRail | null = null;
let pararWatcher: (() => void) | null = null;
let runtimeAtual: RuntimeSnapshot = { runtimeRevision: 0, events: [], entityByTask: new Map() };
/**
 * O raciocínio de agora, por `provedor/endpoint`.
 *
 * Raciocínio, resumo ou os tokens de saída enquanto a chamada está aberta. O `final`
 * limpa o mapa — é o que faz o "Pensando" desaparecer em vez de congelar na última
 * frase. Sem os tokens, o proponente trabalhava mudo: ele emite JSON, não scratchpad.
 */
let pensamentos: ReadonlyMap<string, string> = new Map();
let modoTextoAtivo = false;
let dadosDoDock: DockData | null = null;
let pararPolling: (() => void) | null = null;
let pedirSnapshotDeControle: (() => void) | null = null;
/**
 * O último roster de trabalhadores que o controle afirmou.
 *
 * Guardado aqui porque a ligação precisa ser idempotente **nos dois sentidos**: o
 * snapshot pode chegar antes de a cena existir, e a cena pode nascer depois de o snapshot
 * já ter chegado. Depender da ordem de inicialização faria os sete aparecerem ou não
 * conforme quem ganhasse a corrida.
 */
let rosterDeTrabalhadores: RuntimeWorker[] | undefined;

function sincronizarTrabalhadores(): void {
  if (!atlasAtivo || rosterDeTrabalhadores === undefined) return;
  atlasAtivo.syncWorkers(rosterDeTrabalhadores);
}

function lerRoster(snapshot: ControlSnapshot): RuntimeWorker[] {
  return snapshot.workers.map((worker) => ({
    id: worker.id,
    role: worker.role,
    className: worker.class_name,
    summary: worker.summary,
    area: worker.area,
    paletteToken: worker.palette_token,
    concurrencyMax: worker.concurrency_max,
  }));
}
let alvoDaAtividade: string | null = null;
let assinaturaDosFluxos = '';
let transicaoDaAtividade: ReturnType<typeof setTimeout> | null = null;
const cicloAplicacao = new AbortController();
type ConnectionPhase = BackendConnectionStatus | 'static';
let conexaoCorpus: ConnectionPhase = 'connecting';
let conexaoRuntime: ConnectionPhase = 'connecting';
/** Snapshot válido recebido na conexão SSE atual, não apenas socket aberto. */
let runtimeSnapshotDaConexao = false;

function exigir<T extends HTMLElement>(selector: string): T {
  const elemento = document.querySelector<T>(selector);
  if (!elemento) throw new Error(`elemento ausente no index.html: ${selector}`);
  return elemento;
}

function anunciar(mensagem: string): void {
  vivo.textContent = mensagem;
}

/** A face aberta sobre a placa de um provedor, quando há uma. */
let faceAtiva: ProviderFaceHandle | null = null;
/** A paleta de busca do corpus, quando a cena 3D existe. */
let paletaDeBusca: SearchPaletteHandle | null = null;
/** O quadro que mantém a face colada na placa. */
let quadroDaFace = 0;
/** O que a face aberta configura: um provedor ou um trabalhador, e qual. */
let alvoDaFace: { tipo: 'provider' | 'worker'; id: string } | null = null;
let confirmandoNaFace = false;


/**
 * A legenda, em dois blocos: como navegar e como ler o Atlas.
 *
 * Nada aqui é digitado à mão. A navegação vem de `SCENE_LEGEND`, ao lado dos atalhos; a
 * leitura vem de `buildSceneLegend`, que compõe silhueta, proporção, corpo, linha e cor
 * a partir das tabelas que de fato desenham a cena. Legenda escrita à mão envelhece
 * calada, e uma legenda errada sobre o critério de leitura é pior que legenda nenhuma
 * num Atlas cuja razão de existir é afirmar com rigor.
 */
function bloco(titulo: string, nota: string | undefined, itens: HTMLElement[]): HTMLElement {
  const secao = document.createElement('section');
  const cabecalho = document.createElement('h2');
  cabecalho.textContent = titulo;
  secao.append(cabecalho);
  if (nota) {
    const explicacao = document.createElement('p');
    explicacao.textContent = nota;
    secao.append(explicacao);
  }
  if (itens.length > 0) {
    const lista = document.createElement('ul');
    lista.append(...itens);
    secao.append(lista);
  }
  return secao;
}

function linhaDaLegenda(marca: Node | string, significado: string): HTMLElement {
  const item = document.createElement('li');
  const esquerda = document.createElement('span');
  esquerda.className = 'legend-mark';
  esquerda.append(marca);
  const direita = document.createElement('span');
  direita.textContent = significado;
  item.append(esquerda, direita);
  return item;
}

/** O traço da relação, desenhado com o mesmo array que a aresta usa. */
function amostraDeTraco(pattern: readonly number[] | undefined, doubled: boolean): SVGElement {
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('width', '46');
  svg.setAttribute('height', doubled ? '9' : '5');
  svg.setAttribute('aria-hidden', 'true');
  const cotas = doubled ? [2.5, 6.5] : [2.5];
  for (const y of cotas) {
    const linha = document.createElementNS(NS, 'line');
    linha.setAttribute('x1', '1');
    linha.setAttribute('x2', '45');
    linha.setAttribute('y1', String(y));
    linha.setAttribute('y2', String(y));
    linha.setAttribute('stroke', '#9fb3c6');
    linha.setAttribute('stroke-width', '1.4');
    if (pattern && pattern.length > 0) {
      // O array é medido em unidades de mundo; aqui ele vira pixels na mesma proporção,
      // então a diferença entre um tracejado longo e um cerrado sobrevive na amostra.
      linha.setAttribute('stroke-dasharray', pattern.map((n) => n * 3.2).join(' '));
    }
    svg.append(linha);
  }
  return svg;
}

function amostraDeCor(token: string, rotulo: string): HTMLElement {
  const marca = document.createElement('span');
  const cor = document.createElement('span');
  cor.className = 'legend-swatch';
  // `oklchToHex` devolve o inteiro que o Three consome; o CSS quer a notação `#rrggbb`.
  cor.style.background = `#${oklchToHex(tokenColor(token)).toString(16).padStart(6, '0')}`;
  const nome = document.createElement('span');
  nome.textContent = rotulo;
  marca.append(cor, nome);
  return marca;
}

function montarLegenda(projection: Projection): void {
  const navegacao = bloco(
    'Navegação',
    'Um clique escolhe; dois aproximam.',
    SCENE_LEGEND.map(({ keys, action }) => {
      const tecla = document.createElement('kbd');
      tecla.textContent = keys;
      return linhaDaLegenda(tecla, action);
    }),
  );

  const leitura = buildSceneLegend(projection).map((secao) =>
    bloco(
      secao.title,
      secao.note,
      secao.items.map((item) => {
        if (item.token !== undefined) {
          return linhaDaLegenda(amostraDeCor(item.token, item.mark), item.meaning);
        }
        if (item.pattern !== undefined) {
          const marca = document.createElement('span');
          marca.append(amostraDeTraco(item.pattern, item.doubled === true));
          return linhaDaLegenda(marca, `${item.mark} — ${item.meaning}`);
        }
        return linhaDaLegenda(item.mark, item.meaning);
      }),
    ),
  );

  legendaPainel.replaceChildren(navegacao, ...leitura);
}

function alternarLegenda(aberta: boolean): void {
  legendaBotao.setAttribute('aria-expanded', String(aberta));
  legendaPainel.hidden = !aberta;
}

legendaBotao.addEventListener(
  'click',
  () => {
    alternarLegenda(legendaBotao.getAttribute('aria-expanded') !== 'true');
  },
  { signal: cicloAplicacao.signal },
);

const CONNECTION_LABEL: Record<ConnectionPhase, string> = {
  connecting: 'conectando',
  online: 'vivo',
  reconnecting: 'reconectando',
  timeout: 'sem resposta',
  static: 'estático/offline',
};

function atualizarConexao(
  channel: 'corpus' | 'runtime',
  phase: ConnectionPhase,
): void {
  if (channel === 'corpus') conexaoCorpus = phase;
  else {
    conexaoRuntime = phase;
    // `timeout` pode ser o watchdog de uma conexão half-open. Conservamos a prova do
    // snapshot daquela conexão para que um heartbeat válido a restaure; uma conexão
    // nova, porém, precisa entregar seu próprio snapshot antes de voltar a afirmar vida.
    if (phase === 'connecting' || phase === 'reconnecting' || phase === 'static') {
      runtimeSnapshotDaConexao = false;
    }
  }
  conexao.textContent =
    `corpus: ${CONNECTION_LABEL[conexaoCorpus]} · ` +
    `runtime: ${CONNECTION_LABEL[conexaoRuntime]}`;
  conexao.dataset.state =
    conexaoCorpus === 'online' && conexaoRuntime === 'online' ? 'online' : 'degraded';
  atualizarAtividade();
}

function encerrarAplicacao(): void {
  cicloAplicacao.abort(new DOMException('ciclo da aplicação encerrado', 'AbortError'));
  if (transicaoDaAtividade !== null) globalThis.clearTimeout(transicaoDaAtividade);
  transicaoDaAtividade = null;
  pararWatcher?.();
  pararWatcher = null;
  atlasAtivo?.dispose();
  atlasAtivo = null;
  railDeAncoras?.dispose();
  railDeAncoras = null;
  pararPolling?.();
  pararPolling = null;
  pedirSnapshotDeControle = null;
  if (quadroDaFace !== 0) cancelAnimationFrame(quadroDaFace);
  quadroDaFace = 0;
  faceAtiva?.dispose();
  faceAtiva = null;
  paletaDeBusca?.dispose();
  paletaDeBusca = null;
  alvoDaFace = null;
  nodeIdDaFace = null;
  dadosDoDock = null;
  window.removeEventListener('beforeunload', encerrarAplicacao);
}

window.addEventListener('beforeunload', encerrarAplicacao, { once: true });
// O Vite preserva a página durante HMR. Sem dispose, canvas, RAF e EventSource da
// versão anterior continuariam vivos por baixo do módulo recém-carregado.
if (import.meta.hot) import.meta.hot.dispose(encerrarAplicacao);

/** Falha visível, em texto grande no palco. Melhor que um atlas silenciosamente errado. */
function falhar(mensagem: string): void {
  palco.innerHTML = '';
  const bloco = document.createElement('pre');
  bloco.className = 'failure';
  bloco.textContent = mensagem;
  palco.appendChild(bloco);
  anunciar(`Falha ao carregar o atlas. ${mensagem}`);
}

/** Lista navegável do corpus para leitor de tela e busca do navegador. */
function preencherAcessibilidade(projection: Projection, origem: string): void {
  const meta = projection.meta;
  const resumo = document.createElement('p');
  resumo.textContent =
    `Atlas do corpus. Contrato v${meta.contractVersion}, origem ${meta.source}, ` +
    `carregado de ${origem}. ${meta.counts.notes} entidades, ${meta.counts.mocs} MOCs, ` +
    `${meta.counts.wikilinks} wikilinks, ${meta.counts.claims} claims, ` +
    `${meta.domains.length} domínios. Impressão do corpus ${meta.corpusFingerprint}.`;

  const lista = document.createElement('ul');
  for (const node of projection.nodes) {
    const item = document.createElement('li');
    item.textContent =
      `${node.title} — ${node.domainLabel}, ${node.kind}, ` +
      `${node.claimCount} claims, ${node.incomingDegree + node.outgoingDegree} relações.`;
    lista.append(item);
  }
  sumario.replaceChildren(resumo, lista);
}

function runtimeSection(snapshot: RuntimeSnapshot, id: string): HTMLElement {
  const section = document.createElement('section');
  section.id = id;
  const title = document.createElement('h2');
  title.textContent = 'Atividade operacional ao vivo';
  const status = document.createElement('p');
  status.textContent =
    `Revisão operacional ${snapshot.runtimeRevision}. ` +
    `${snapshot.events.length} evento(s) recente(s) na camada separada do corpus.`;
  const list = document.createElement('ul');
  for (const event of snapshot.events.slice(-40).reverse()) {
    const item = document.createElement('li');
    const subject = event.entity ?? event.task ?? event.provider ?? 'sem entidade declarada';
    const endpoint =
      event.provider && event.endpoint ? ` · ${event.provider}/${event.endpoint}` : '';
    item.textContent =
      `${runtimeEventLabel(event.type)} · ${subject}${endpoint} · ` +
      `${event.timestamp} · revisão ${event.revision}`;
    list.append(item);
  }
  section.append(title, status, list);
  return section;
}

/**
 * O cartão sempre visível é a porta de entrada da nuvem viva.
 *
 * Ele não decide atividade por processo ou conexão: `describeLiveActivity` exige
 * chamada aberta na trilha, e usa o controle apenas para fila/automação. Clicar leva
 * ao painel correspondente dentro da cena em vez de duplicar seu conteúdo no DOM.
 */
function atualizarAtividade(): void {
  const agora = Date.now();
  const controlFreshness = !dadosDoDock || dadosDoDock.phase === 'carregando'
    ? 'loading'
    : dadosDoDock.phase === 'indisponivel'
      ? 'unavailable'
      : dadosDoDock.stale
        ? 'stale'
        : dadosDoDock.snapshot
          ? 'fresh'
          : 'loading';
  const operacao = dadosDoDock?.snapshot?.operation;
  const view = describeLiveActivity(
    runtimeAtual,
    {
      operation: operacao
        ? {
            auto: operacao.auto,
            queued: operacao.queued,
            running: operacao.running,
            budget: operacao.budget,
            lastCycle: operacao.last_cycle,
            nextRun: operacao.next_run,
            failures: operacao.failures,
          }
        : null,
      controlFreshness,
      runtimeConnection: conexaoRuntime,
      runtimeSnapshotReady: runtimeSnapshotDaConexao,
      thoughts: pensamentos,
    },
    agora,
  );
  atividade.dataset.state = view.phase;
  const streams = view.streams ?? [];
  const split = (view.layout ?? (streams.length > 1 ? 'split' : 'single')) === 'split';
  atividade.dataset.layout = split ? 'split' : 'single';
  if (tituloDaAtividade.textContent !== view.headline) {
    tituloDaAtividade.textContent = view.headline;
  }
  if (detalheDaAtividade.textContent !== view.detail) {
    detalheDaAtividade.textContent = view.detail;
  }
  detalheDaAtividade.hidden = split;
  pintarFluxos(streams, split);
  if (metaDaAtividade.textContent !== view.meta) metaDaAtividade.textContent = view.meta;
  alvoDaAtividade = view.targetId;
  const clicavel = !split && alvoDaAtividade !== null && atlasAtivo !== null;
  if (split) atividade.removeAttribute('aria-disabled');
  else atividade.setAttribute('aria-disabled', String(!clicavel));
  atividade.setAttribute('role', split ? 'group' : 'button');
  atividade.tabIndex = split ? -1 : 0;
  const rotulo =
    `Atividade operacional: ${view.headline}. ${view.detail}. ${view.meta}. ` +
    (split
      ? 'Cada modelo tem um botão para abrir no Atlas.'
      : alvoDaAtividade
        ? 'Ative para abrir no Atlas.'
        : '');
  if (atividade.getAttribute('aria-label') !== rotulo) {
    atividade.setAttribute('aria-label', rotulo);
  }
  atlasAtivo?.refreshRuntimeActivity(agora);
  atlasAtivo?.setRuntimeActivityEnabled(view.phase === 'active');

  if (transicaoDaAtividade !== null) globalThis.clearTimeout(transicaoDaAtividade);
  transicaoDaAtividade = null;
  if (view.expiresAt !== null) {
    const espera = Math.max(view.expiresAt - Date.now(), 0);
    transicaoDaAtividade = globalThis.setTimeout(atualizarAtividade, espera + 1);
  }
  atualizarAuto();
}

function atualizarAuto(): void {
  const operacao = dadosDoDock?.snapshot?.operation;
  const pending = dadosDoDock?.pending.has(controlId.auto()) ?? false;
  const known = typeof operacao?.auto === 'boolean';
  const ligado = operacao?.auto === true;
  autoDaAtividade.disabled = !known || pending;
  autoDaAtividade.setAttribute('aria-pressed', String(ligado));
  autoDaAtividade.textContent = 'A';
  const rotulo = pending
    ? 'AUTO — aplicando'
    : !known
      ? 'AUTO — não informado'
      : ligado
        ? 'Desligar o modo automático'
        : 'Ligar o modo automático';
  autoDaAtividade.title = rotulo;
  autoDaAtividade.setAttribute('aria-label', rotulo);
}

function pintarFluxos(streams: readonly LiveActivityStream[], split: boolean): void {
  if (!split) {
    fluxosDaAtividade.hidden = true;
    if (assinaturaDosFluxos !== '') {
      fluxosDaAtividade.replaceChildren();
      assinaturaDosFluxos = '';
    }
    return;
  }
  fluxosDaAtividade.hidden = false;
  const assinatura = streams
    .map((stream) => `${stream.targetId}\t${stream.who}\t${stream.role ?? ''}\t${stream.text}`)
    .join('\n');
  if (assinatura === assinaturaDosFluxos) return;
  assinaturaDosFluxos = assinatura;
  const nos = streams.map((stream) => {
    const botao = document.createElement('button');
    botao.type = 'button';
    botao.className = stream.thinking
      ? 'activity-stream activity-stream--thinking'
      : 'activity-stream';
    botao.dataset.target = stream.targetId;
    const quem = document.createElement('span');
    quem.className = 'activity-stream__who';
    quem.textContent = stream.role ? `${stream.who} · ${stream.role}` : stream.who;
    const texto = document.createElement('span');
    texto.className = 'activity-stream__text';
    texto.textContent = stream.text;
    botao.append(quem, texto);
    botao.setAttribute('aria-label', `${quem.textContent}: ${stream.text}`);
    return botao;
  });
  fluxosDaAtividade.replaceChildren(...nos);
}

atividade.addEventListener(
  'click',
  (evento) => {
    const fluxo = (evento.target as HTMLElement | null)?.closest('.activity-stream');
    if (fluxo instanceof HTMLButtonElement && fluxo.dataset.target) {
      atlasAtivo?.focusRuntime(fluxo.dataset.target);
      return;
    }
    if (atividade.dataset.layout !== 'split' && alvoDaAtividade) {
      atlasAtivo?.focusRuntime(alvoDaAtividade);
    }
  },
  { signal: cicloAplicacao.signal },
);

atividade.addEventListener(
  'keydown',
  (evento) => {
    if (atividade.dataset.layout === 'split') return;
    if (evento.key !== 'Enter' && evento.key !== ' ') return;
    evento.preventDefault();
    if (alvoDaAtividade) atlasAtivo?.focusRuntime(alvoDaAtividade);
  },
  { signal: cicloAplicacao.signal },
);

function atualizarDock(): void {
  atualizarFace();
  atualizarAtividade();
}

/**
 * Redesenha a face aberta a partir do retrato atual do controle.
 *
 * Chamada em toda mudança do retrato, e não só na abertura: o estado muda por fora —
 * uma gravação termina, um teste falha, o AUTO resolve outro modelo — e uma face que
 * continuasse mostrando o retrato do instante do clique afirmaria o que já não é
 * verdade.
 */
function atualizarFace(): void {
  const face = faceAtiva;
  const alvo = alvoDaFace;
  if (!face || !alvo || !dadosDoDock || !atlasAtivo) return;
  const linhas = atlasAtivo.panelLines(nodeIdDaFace ?? '');
  const modelo =
    alvo.tipo === 'provider'
      ? describeProviderFace(dadosDoDock, alvo.id, linhas, {
          confirming: confirmandoNaFace,
          canApply: true,
          canTest: true,
          canRemove: true,
        })
      : describeWorkerFace(dadosDoDock, alvo.id, linhas, {
          canToggle: true,
          canSetConcurrency: true,
          canSetReasoning: true,
        });
  if (!modelo) {
    // O nó existe na cena e não no retrato do controle. Dizer isso é melhor que manter
    // uma face que não tem como configurar coisa nenhuma.
    fecharFace();
    anunciar(
      `Configuração de ${alvo.id} indisponível: o painel de controle ainda não ` +
        'recebeu este item.',
    );
    return;
  }
  face.render(
    alvo.tipo === 'provider'
      ? { kind: 'provider', ...(modelo as ReturnType<typeof describeProviderFace> & object) }
      : { kind: 'worker', ...(modelo as ReturnType<typeof describeWorkerFace> & object) },
  );
  face.place(atlasAtivo.panelFaceRect());
}

/** O nó cuja placa a face está cobrindo. É dele que saem as frases e a projeção. */
let nodeIdDaFace: string | null = null;

function fecharFace(): void {
  faceAtiva?.close();
  alvoDaFace = null;
  nodeIdDaFace = null;
  confirmandoNaFace = false;
  atlasAtivo?.setPanelFace(null);
}

/**
 * O canal cognitivo chegou. A cena passa a dizer o que o modelo está pensando.
 *
 * O mapa é reconstruído inteiro a cada lote porque o canal já entrega o último quadro
 * por endpoint: guardar histórico aqui só criaria uma segunda verdade sobre o agora.
 */
function aplicarCognicao(frames: readonly CognitionFrame[]): void {
  pensamentos = selectThoughts(frames);
  cognicaoPendente = frames;
  agendarRedesenho();
}

/**
 * A cena redesenha **uma vez por quadro**, e não uma vez por evento.
 *
 * Um quórum não emite evento; emite rajada. Cada `call_started`, `vote_requested` e
 * `vote_received` chegava separado no SSE e disparava uma reconstrução inteira da camada
 * viva — projeção, corpos, posições e texto —, de modo que oito eventos no mesmo
 * instante custavam oito reconstruções das quais só a última sobrevivia na tela. É esse
 * o travamento até os painéis novos aparecerem: não era o tamanho da cena, era a
 * quantidade de vezes que ela foi montada para o mesmo quadro.
 *
 * O estado continua avançando evento a evento — a trilha não pode perder nenhum. O que
 * espera pelo quadro é só o desenho.
 */
let trilhaPendente = false;
let cognicaoPendente: readonly CognitionFrame[] | null = null;

const redesenho = createFrameCoalescer(() => {
  {
    const quadros = cognicaoPendente;
    const trilha = trilhaPendente;
    cognicaoPendente = null;
    trilhaPendente = false;
    // A trilha primeiro: ela recria os corpos, e a cognição só sobrepõe leitura. Na
    // ordem inversa o raciocínio seria escrito numa camada que a linha seguinte
    // reconstruiria por inteiro.
    if (trilha) atlasAtivo?.updateRuntime(runtimeAtual);
    if (quadros) atlasAtivo?.updateCognition(quadros);
    atualizarAtividade();
    if (!trilha) return;
    sumario.querySelector('#runtime-a11y')?.remove();
    sumario.append(runtimeSection(runtimeAtual, 'runtime-a11y'));
    if (modoTextoAtivo) {
      palco.querySelector('#runtime-textual')?.remove();
      palco.append(runtimeSection(runtimeAtual, 'runtime-textual'));
    }
    anunciar(
      `Camada operacional atualizada para a revisão ${runtimeAtual.runtimeRevision}, ` +
        `sem mover a projeção do corpus.`,
    );
  }
});

function agendarRedesenho(): void {
  redesenho.request();
}

function aplicarRuntime(snapshot: RuntimeSnapshot): void {
  runtimeAtual = snapshot;
  trilhaPendente = true;
  agendarRedesenho();
}

async function iniciar(): Promise<void> {
  anunciar('Carregando a projeção do corpus.');
  try {
    const { projection, origin } = await loadProjection(cicloAplicacao.signal);
    atualizarConexao('corpus', isBackendProjectionOrigin(origin) ? 'online' : 'static');
    preencherAcessibilidade(projection, origin);
    montarLegenda(projection);

    // Quem abre o Atlas pela primeira vez não sabe que a legenda existe; abrir
    // sozinha na primeira visita custa um clique e ensina a ler a cena. Depois,
    // fechada é o estado normal — ela responde a uma pergunta que só se faz uma vez.
    const LEGENDA_JA_VISTA = 'atlas-legenda-vista';
    if (localStorage.getItem(LEGENDA_JA_VISTA) === null) {
      alternarLegenda(true);
      try {
        localStorage.setItem(LEGENDA_JA_VISTA, '1');
      } catch {
        // Armazenamento indisponível: a legenda só deixa de abrir sozinha.
      }
    }

    // A assinatura acontece somente depois de montar o modo textual ou persistir o
    // layout 3D. Se algo mudou nesse intervalo, o evento `current` traz outro SHA e
    // recarrega; abrir o canal antes poderia interromper a primeira gravação espacial.
    // Mesmo o snapshot estático assina: quando o backend volta, somente um evento
    // `current` válido prova que há uma projeção viva pronta para substituir o artefato.
    const observarCorpus = (): void => {
      let recargaPedida = false;
      const recarregar = (mensagem: string): void => {
        if (recargaPedida) return;
        recargaPedida = true;
        anunciar(mensagem);
        window.location.reload();
      };
      const stops = [
        watchProjection(
          projection.meta.corpusFingerprint,
          () => recarregar('Nova revisão do corpus recebida; atualizando o Atlas.'),
          (detail) => anunciar(`Watcher do corpus: ${detail}`),
          {
            signal: cicloAplicacao.signal,
            onConnectionStatus: (status) => {
              atualizarConexao(
                'corpus',
                !isBackendProjectionOrigin(origin) ? 'static' : status,
              );
              if (status === 'timeout') {
                anunciar('Watcher do corpus ainda sem conexão; mantendo a projeção atual.');
              }
            },
            onCurrent: (fingerprint) => {
              if (shouldReplaceStaticProjection(origin, fingerprint)) {
                recarregar('Backend recuperado; trocando o snapshot estático pela projeção viva.');
              }
            },
          },
        ),
        watchRuntime(
          (snapshot) => {
            runtimeSnapshotDaConexao = true;
            aplicarRuntime(snapshot);
          },
          (event) => {
            aplicarRuntime(advanceRuntime(runtimeAtual, event));
            if (
              event.type === 'task_assigned' ||
              event.type === 'call_started' ||
              event.type === 'call_completed' ||
              event.type === 'evidence_recorded' ||
              event.type === 'quorum_decided' ||
              event.type === 'promotion_completed'
            ) {
              pedirSnapshotDeControle?.();
            }
          },
          (detail) => anunciar(`Runtime: ${detail}`),
          {
            signal: cicloAplicacao.signal,
            onConnectionStatus: (status) => {
              atualizarConexao('runtime', status);
              if (status === 'timeout') {
                anunciar('Runtime ainda sem conexão; mantendo a última camada válida.');
              }
            },
          },
        ),
        // O canal cognitivo não entra no indicador de conexão: ele é efêmero por
        // definição, e ficar sem raciocínio ao vivo não degrada a leitura do corpus nem
        // a da trilha. Anunciar sua queda como falha diria mais do que ela significa.
        watchCognition(aplicarCognicao, { signal: cicloAplicacao.signal }),
      ];
      pararWatcher = () => {
        for (const stop of stops) stop();
      };
    };

    // O 3D não pode ser o único caminho até o corpus. Pedido explícito por `?texto=1`
    // ou WebGL indisponível levam ao modo textual, que substitui a cena — não é um
    // painel ao lado dela.
    const pedido = modoTextualPedido(window.location.search);
    const semWebgl = !webglDisponivel();
    if (pedido || semWebgl) {
      modoTextoAtivo = true;
      montarModoTextual(
        palco,
        projection,
        origin,
        pedido
          ? 'Modo textual pedido por ?texto=1. O Atlas 3D está em /.'
          : 'WebGL indisponível neste navegador; o corpus continua acessível aqui.',
      );
      anunciar(
        `Modo textual: ${projection.meta.counts.notes} entidades, ` +
          `${projection.meta.counts.claims} claims. Use a busca para localizar.`,
      );
      observarCorpus();
      return;
    }

    // Memória espacial: o que já foi colocado fica onde estava; só o que é novo é
    // assentado. Sem backend não há gravação, e o layout determinístico basta.
    // Dois frames: o corpus e o observatório de execuções. Só o corpus tem memória
    // espacial — ver `composeLayout`. Gravar posição de execução sob a impressão do
    // corpus faria uma execução nova reaparecer no lugar de uma antiga.
    const fingerprint = projection.meta.corpusFingerprint;
    // Ordinais das execuções: gravados uma vez, respeitados para sempre. Sem eles, uma
    // execução importada fora de ordem deslocaria as que já estavam assentadas.
    const ordinais = await loadOperationalSlots(cicloAplicacao.signal);
    // `mergePositions` logo abaixo é quem reaplica o gravado; passá-lo também aqui
    // duplicaria a mesma sobreposição.
    // **O modo solto**, por `?layout=livre`.
    //
    // É o experimento que a ADR-004 deixou em aberto: posição decidida pela relação
    // declarada, e não pelo diretório. Fica atrás de um interruptor porque trocar um
    // layout pelo outro sem comparar seria repetir o erro da esfera livre original, que
    // saiu por oclusão e perda de referência. Com os dois abertos, a escolha se mede.
    const modoLivre = new URLSearchParams(window.location.search).get('layout') === 'livre';
    let composto = composeLayout(projection, {}, undefined, ordinais);
    let persistenciaOperacional = 'sem execuções' as
      | 'sem execuções'
      | 'gravada'
      | 'recusada'
      | 'resposta inválida'
      | 'backend ausente';
    if (composto.slots.size > 0) {
      // O backend preserva a primeira atribuição sob lock. Duas abas podem propor o
      // mesmo ordinal ao mesmo tempo; montar a cena antes de ler a resposta deixaria
      // uma delas desenhando um lugar que nunca foi aceito no estado canônico.
      const resultado = await saveOperationalSlots(composto.slots, cicloAplicacao.signal);
      persistenciaOperacional =
        resultado.status === 'stored'
          ? 'gravada'
          : resultado.status === 'rejected'
            ? 'recusada'
            : resultado.status === 'invalid-response'
              ? 'resposta inválida'
              : 'backend ausente';
      if (resultado.status === 'stored') {
        composto = composeLayout(projection, {}, undefined, resultado.slots);
      }
    }
    // A memória é lida **depois** de compor, e não antes: o que está gravado é relativo
    // à origem do corpus, e só a composição sabe onde ela ficou. Lida antes, ela chegava
    // num frame que ainda não existia.
    const gravadas = await loadPositions(
      fingerprint,
      composto.origin.corpus,
      cicloAplicacao.signal,
    );
    // O modo solto entra **aqui**, e não junto da primeira composição: o bloco de slots
    // acima recompõe quando o backend aceita os ordinais, e uma aplicação anterior seria
    // descartada por essa recomposição. Antes do merge porque a memória gravada continua
    // valendo — quem já tem posição de corpus persistida a mantém, e o experimento vale
    // para o que ainda não tem.
    // No modo solto a cena **nasce onde o ancorado a poria** e se reorganiza na tela.
    // Assentar antes de desenhar devolveria um mapa pronto e congelaria a aba; deixar a
    // física correr por quadro mostra o grafo se organizando, que é a informação que um
    // grafo de notas dá ao abrir — quais nós caem juntos, quais resistem, onde a
    // estrutura declarada aperta.
    //
    // Uma população por vez: o campo livre puro junta corpus, quórum e modelos num bolo
    // só. Não por sobreposição real — medida, deu 2 colisões em 1408 nós — mas por
    // projeção, e a cena deixava de dizer quem é quem.
    const simulacaoLivre = modoLivre
      ? createFreeSimulationByPopulation(projection, [
          { ids: composto.ids.corpus, origin: composto.origin.corpus },
          { ids: composto.ids.operacional, origin: composto.origin.operacional },
          {
            ids: new Set([...composto.ids.modelos, ...composto.ids.provedores]),
            origin: composto.origin.modelos,
          },
        ])
      : null;
    const compostoFinal = composto;
    if (modoLivre) anunciar('Layout solto: a cena se organiza pelas relações declaradas.');
    const { positions, reused, placed } = mergePositions(compostoFinal.positions, gravadas);
    const persistencia = await savePositions(
      fingerprint,
      positions,
      composto.ids.corpus,
      composto.origin.corpus,
      cicloAplicacao.signal,
    );
    const textoPersistenciaCorpus = {
      stored: 'gravadas',
      'stale-fingerprint': 'não gravadas (a projeção mudou durante a abertura)',
      rejected: 'não gravadas (backend recusou o contrato)',
      'backend-unavailable': 'não gravadas (backend ausente)',
    }[persistencia];
    if (composto.diagnostics.orphans.length > 0) {
      // Órfão é reportado, nunca espalhado em silêncio: nó de quórum sem execução é
      // defeito de projeção, e escondê-lo numa posição plausível transformaria a causa
      // em ruído visual que ninguém liga a ela.
      console.warn(
        `[atlas] ${composto.diagnostics.orphans.length} nó(s) operacional(is) sem execução: ` +
          composto.diagnostics.orphans.slice(0, 5).join(', '),
      );
    }

    // O miolo reservado atravessa a fronteira junto com as posições: é a composição que
    // decide onde a nuvem viva mora, e a cena não tem por que redescobrir isso medindo
    // centros alheios.
    const atlas = createAtlas(
      palco,
      projection,
      positions,
      anunciar,
      composto.core,
      composto.origin.corpus,
      composto.workerAnchors,
    );
    atlasAtivo = atlas;
    // O outro sentido da idempotência: se o controle já respondeu antes de a cena
    // existir, os sete entram agora, sem esperar o próximo polling.
    sincronizarTrabalhadores();

    if (simulacaoLivre) {
      // Poucas passagens por quadro: o bastante para o assentamento ser visível sem a
      // física roubar o orçamento do desenho. Quando ela termina, o laço termina — não é
      // animação perpétua, é uma cena que se assenta e para.
      //
      // `setTimeout` e não `requestAnimationFrame`: aba sem composição não recebe quadro,
      // e a cena ficaria congelada no estado inicial sem nenhum erro para acusar. O
      // relógio corre mesmo quando o compositor não.
      const PASSAGENS_POR_QUADRO = 3;
      const avancar = (): void => {
        const continua = simulacaoLivre.step(PASSAGENS_POR_QUADRO);
        atlasAtivo?.setPositions(simulacaoLivre.positions());
        if (continua) setTimeout(avancar, 16);
        else anunciar('Layout solto assentado.');
      };
      setTimeout(avancar, 16);
    }
    // A régua é o índice espacial estável: MOCs, provedores e trabalhadores da projeção
    // principal. Âncoras internas da trilha viva são efêmeras e duplicariam esses alvos.
    railDeAncoras = createAnchorRail(anchorTargets(projection), (id) => atlas.focusOn(id));
    for (const regua of railDeAncoras.elements) palco.parentElement?.append(regua);

    // O dock é sobreposição. Abrir e fechar configuração não muda câmera nem layout.
    const cliente = createControlClient();
    const pendentes = new Set<string>();
    const erros = new Map<string, string>();
    const conflitos = new Map<string, string>();

    const sincronizar = (patch: Partial<DockData> = {}): void => {
      if (!dadosDoDock) return;
      dadosDoDock = {
        ...dadosDoDock,
        ...patch,
        pending: new Set(pendentes),
        errors: new Map(erros),
        conflicts: new Map(conflitos),
      };
      atualizarDock();
    };

    const polling = createControlPolling<ControlSnapshot>({
      request: (signal) => cliente.snapshot({ signal }),
      onValue: (snapshot) => {
        // O roster é do runtime, e vai direto a quem o possui. O dock continua recebendo
        // o snapshot inteiro para o que é dele — configuração e leitura.
        rosterDeTrabalhadores = lerRoster(snapshot);
        sincronizarTrabalhadores();
        sincronizar({ phase: 'pronto', snapshot, reason: null, stale: false });
      },
      onError: (erro) => {
        const motivo =
          erro instanceof ControlError || erro instanceof ControlPollingTimeoutError
            ? erro.message
            : String(erro);
        // Uma leitura anterior continua útil: ela vira `stale` em vez de sumir. Sem
        // leitura nenhuma, aí sim o painel se declara indisponível.
        sincronizar(
          dadosDoDock?.snapshot
            ? { stale: true, reason: motivo }
            : { phase: 'indisponivel', reason: motivo },
        );
      },
    });
    pedirSnapshotDeControle = () => polling.refresh();
    let liberarPolling: (() => void) | null = null;
    const filaMutacoes = createSerialTaskQueue((ocupada) => {
      if (ocupada) {
        liberarPolling ??= polling.hold();
      } else {
        liberarPolling?.();
        liberarPolling = null;
      }
    });

    /**
     * Uma mutação, com pendência isolada no controle que a pediu.
     *
     * Bloquear o dock inteiro por causa de um checkbox faria o painel parecer travado
     * a cada clique. O que bloqueia é o controle, e só até a resposta chegar.
     */
    const mutar = (
      id: string,
      acao: () => Promise<ControlSnapshot>,
      conferir?: (snapshot: ControlSnapshot) => string | null,
    ): void => {
      pendentes.add(id);
      erros.delete(id);
      conflitos.delete(id);
      sincronizar();
      filaMutacoes.enqueue(async () => {
        try {
          const snapshot = await acao();
          if (cicloAplicacao.signal.aborted) return;
          const conflito = conferir?.(snapshot) ?? null;
          if (conflito) conflitos.set(id, conflito);
          sincronizar({ phase: 'pronto', snapshot, reason: null, stale: false });
        } catch (erro) {
          if (!cicloAplicacao.signal.aborted) {
            erros.set(id, erro instanceof ControlError ? erro.message : String(erro));
            sincronizar();
          }
        } finally {
          pendentes.delete(id);
          sincronizar();
        }
      });
    };

    autoDaAtividade.addEventListener(
      'click',
      () => {
        const atual = dadosDoDock?.snapshot?.operation?.auto;
        if (typeof atual !== 'boolean') return;
        mutar(controlId.auto(), () =>
          cliente.setAuto(!atual, { signal: cicloAplicacao.signal }),
        );
      },
      { signal: cicloAplicacao.signal },
    );

    /**
     * O painel do provedor **é** a configuração dele — na própria placa.
     *
     * A tentativa anterior levava a doca inteira para o lado do nó: a mesma superfície
     * de `Esc`, com abas e título de sistema, aparecendo por dois caminhos. Duas
     * superfícies para a mesma credencial é o defeito, não a ancoragem.
     *
     * Agora a face é desenhada **sobre a área de leitura da placa**, projetada quadro a
     * quadro, e o texto 3D daquele painel sai do quadro enquanto ela existe. A face diz
     * as mesmas frases que a placa dizia e acrescenta o que a cena não tem como
     * oferecer: campo mascarado, foco e confirmação em dois passos.
     */
    const face = createProviderFace({
      applyKey: (providerId, key) =>
        mutar(providerControlId(providerId).key, async () => {
          await cliente.putCredential(providerId, key, { signal: cicloAplicacao.signal });
          return cliente.snapshot({ signal: cicloAplicacao.signal });
        }),
      testKey: (providerId, key) =>
        mutar(providerControlId(providerId).test, async () => {
          const resultado = await cliente.testProvider(providerId, key, {
            signal: cicloAplicacao.signal,
          });
          if (resultado.status === 'invalido' || resultado.status === 'erro') {
            throw new ControlError(resultado.detail);
          }
          return cliente.snapshot({ signal: cicloAplicacao.signal });
        }),
      removeKey: (providerId) =>
        mutar(providerControlId(providerId).key, async () => {
          await cliente.deleteCredential(providerId, { signal: cicloAplicacao.signal });
          return cliente.snapshot({ signal: cicloAplicacao.signal });
        }),
      setWorkerEnabled: (workerId, enabled) =>
        mutar(workerControlId(workerId).enabled, () =>
          cliente.patchWorker(workerId, { enabled }, { signal: cicloAplicacao.signal }),
        ),
      setWorkerReasoning: (workerId, reasoning) =>
        mutar(workerControlId(workerId).reasoning, () =>
          cliente.patchWorker(workerId, { reasoning }, { signal: cicloAplicacao.signal }),
        ),
      setWorkerConcurrency: (workerId, concurrency) =>
        mutar(
          workerControlId(workerId).concurrency,
          () =>
            cliente.patchWorker(workerId, { concurrency }, { signal: cicloAplicacao.signal }),
          (snapshot) => {
            // O backend é autoridade sobre o teto. Pedir cinco e receber três não é
            // erro: é conflito, e a face diz isso em vez de mostrar o cinco.
            const efetivo = snapshot.workers.find((item) => item.id === workerId);
            if (!efetivo || efetivo.concurrency === concurrency) return null;
            return `pedido ${concurrency}, efetivo ${efetivo.concurrency} (teto ${efetivo.concurrency_max})`;
          },
        ),
      onClose: () => atlas.select(null),
      onConfirmChange: (confirmando) => {
        confirmandoNaFace = confirmando;
        atualizarFace();
      },
    });
    faceAtiva = face;
    document.body.append(face.element);

    /**
     * Provedor e trabalhador abrem face; o resto a fecha.
     *
     * O modelo daquele provedor não abre: ele tem dono, mas a chave é do provedor, e
     * configurar a credencial sobre a placa do modelo afirmaria duas contas onde há
     * uma. Nota e evento também não: configuração aberta sobre um nó que não a possui
     * afirmaria um vínculo que não existe.
     */
    atlas.onSelectionChange((escolha) => {
      railDeAncoras?.setActive(escolha.id);
      // A ligação acompanha a escolha: `#<id>` torna o que se vê endereçável, e
      // compartilhar a URL compartilha a entidade. `replaceState` de propósito:
      // cada seleção substitui a anterior — o histórico do botão voltar continua
      // pertencendo à aba, não à câmera.
      if (escolha.id !== null) {
        history.replaceState(null, '', `#${encodeURIComponent(escolha.id)}`);
      } else if (window.location.hash) {
        history.replaceState(null, '', window.location.pathname + window.location.search);
      }
      const provedor = providerIdOf(escolha.id);
      const trabalhador = provedor ? null : workerIdOf(escolha.id);
      const alvo = provedor
        ? ({ tipo: 'provider', id: provedor } as const)
        : trabalhador
          ? ({ tipo: 'worker', id: trabalhador } as const)
          : null;
      if (!alvo || escolha.id === null) {
        fecharFace();
        return;
      }
      alvoDaFace = alvo;
      nodeIdDaFace = escolha.id;
      confirmandoNaFace = false;
      atlas.setPanelFace(escolha.id);
      atualizarFace();
      if (alvoDaFace === null) return;
      // A câmera vai até a placa porque a face **é** a placa: um formulário projetado
      // a cem metros nasce ilegível, e pedir que a pessoa se aproxime sozinha para
      // poder ler o que ela acabou de abrir é cobrar por um gesto que o sistema sabe
      // fazer. Vale para painel que virou superfície de digitação; o resto da cena
      // continua com a regra de sempre — um clique escolhe, o duplo traz.
      atlas.focusOn(escolha.id);
      face.focusKey();
    });

    dadosDoDock = emptyDockData(atlas.legendText());
    atualizarDock();

    // A face acompanha a placa. Sem isto ela ficaria parada onde a projeção estava no
    // instante do clique, e o primeiro giro da câmera a deixaria flutuando ao lado de
    // um painel qualquer — que é exatamente o que ela existe para não ser.
    const seguirAPlaca = (): void => {
      if (cicloAplicacao.signal.aborted) return;
      quadroDaFace = requestAnimationFrame(seguirAPlaca);
      if (face.open) face.place(atlas.panelFaceRect());
    };
    quadroDaFace = requestAnimationFrame(seguirAPlaca);

    atlas.fitToGraph();

    // A seleção é endereçável: `#<id>` abre a mesma entidade, inclusive de uma URL
    // compartilhada. A câmera voa depois do enquadramento global, que é o estado de
    // onde toda leitura parte.
    const idDaLiga = (hash: string): string | null => {
      if (!hash.startsWith('#')) return null;
      const id = decodeURIComponent(hash.slice(1));
      return projection.nodes.some((n) => n.layer === 'epistemic' && n.id === id) ? id : null;
    };
    const ligacaoInicial = idDaLiga(window.location.hash);
    if (ligacaoInicial !== null) {
      atlas.select(ligacaoInicial);
      atlas.focusOn(ligacaoInicial);
      anunciar(`Ligação da URL: abrindo ${ligacaoInicial}.`);
    }
    window.addEventListener(
      'hashchange',
      () => {
        const id = idDaLiga(window.location.hash);
        if (id === null) return;
        atlas.select(id);
        atlas.focusOn(id);
      },
      { signal: cicloAplicacao.signal },
    );

    // Busca do corpus na própria cena: Ctrl+K ou `/`. O modo textual tem a busca
    // dele; aqui a paleta vive sobre o Atlas e a escolha leva a câmera até a nota.
    paletaDeBusca = createSearchPalette({
      index: searchIndex(projection),
      onSelect: (id) => {
        atlas.select(id);
        atlas.focusOn(id);
        anunciar(`Busca: indo até ${id}.`);
      },
      announce: anunciar,
    });
    document.body.append(paletaDeBusca.element);
    const alvoEditavel = (alvo: EventTarget | null): boolean =>
      alvo instanceof HTMLInputElement ||
      alvo instanceof HTMLTextAreaElement ||
      alvo instanceof HTMLSelectElement ||
      (alvo instanceof HTMLElement && alvo.isContentEditable);
    window.addEventListener(
      'keydown',
      (evento) => {
        const pediuBusca =
          evento.key === '/' || (evento.ctrlKey && evento.key.toLowerCase() === 'k');
        if (!pediuBusca || alvoEditavel(evento.target) || !paletaDeBusca) return;
        evento.preventDefault();
        paletaDeBusca.open();
      },
      { signal: cicloAplicacao.signal },
    );

    // Esquecer a memória espacial, com confirmação. O reset grava um mapa vazio e
    // recarrega: a cena determinística é o estado que a composição já sabe
    // produzir, e nenhum reset parcial precisa ser inventado.
    const resetLayout = exigir<HTMLButtonElement>('#layout-reset');
    resetLayout.hidden = false;
    resetLayout.addEventListener(
      'click',
      () => {
        if (
          !window.confirm(
            'Esquecer todas as posições gravadas? A cena volta ao cálculo determinístico e a página recarrega.',
          )
        ) {
          return;
        }
        anunciar('Esquecendo posições gravadas.');
        void savePositions(
          fingerprint,
          new Map(),
          undefined,
          compostoFinal.origin.corpus,
          cicloAplicacao.signal,
        ).then((resultado) => {
          if (cicloAplicacao.signal.aborted) return;
          if (resultado === 'stored') {
            anunciar('Posições esquecidas; recarregando a cena determinística.');
            window.location.reload();
          } else {
            anunciar(`Reset não gravado (${resultado}); nada foi alterado.`);
          }
        });
      },
      { signal: cicloAplicacao.signal },
    );

    // O documento é a porta do polling. Sem dock, a cadência é a do cartão: lenta
    // enquanto a aba está visível, pausada quando não está. Mutações suspendem.
    const ajustarPolling = (): void => {
      polling.setMode(
        controlPollingMode(false, false, document.visibilityState === 'visible'),
      );
    };
    const aoTrocarVisibilidade = (): void => {
      ajustarPolling();
    };
    document.addEventListener('visibilitychange', aoTrocarVisibilidade);
    ajustarPolling();
    pararPolling = () => {
      document.removeEventListener('visibilitychange', aoTrocarVisibilidade);
      filaMutacoes.dispose();
      polling.dispose();
      pedirSnapshotDeControle = null;
    };

    observarCorpus();
    // Ponto de verificação, só em desenvolvimento: o build de produção não o define.
    // Serve para conferir chamadas de desenho e exercer a seleção de fora, o que uma
    // aba sem composição não permitiria de outro jeito.
    if (import.meta.env.DEV) {
      const capturar = async (name: string, w = 1920, h = 1080): Promise<unknown> => {
        // O troika gera os glifos fora do quadro atual. Sem esta espera a captura
        // sai sem rótulo nenhum — que foi exatamente o que aconteceu na primeira
        // tentativa deste ciclo.
        atlas.renderOnce();
        await new Promise((resolve) => setTimeout(resolve, 900));
        const dataUrl = atlas.captureAt(w, h);
        const resposta = await fetch('/__capture', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ name, dataUrl }),
        });
        return resposta.json();
      };
      // O harness entra por import dinâmico dentro do ramo de desenvolvimento: em
      // produção `import.meta.env.DEV` é literalmente `false` e o módulo inteiro sai
      // do bundle, junto com a espera de parede que ele precisa fazer.
      const { createCaptureHarness } = await import('./harness');
      const harness = createCaptureHarness(atlas, projection, capturar, 'atlas');
      (window as unknown as { __atlas?: unknown }).__atlas = {
        atlas,
        projection,
        capturar,
        harness,
        // A face acompanha a placa por `requestAnimationFrame`, e uma aba que não
        // compõe quadros nunca o chama — sem isto não haveria como conferir de fora
        // que ela cai sobre o painel, que é justamente o que ela promete.
        sincronizarFace: () => face.place(atlas.panelFaceRect()),
      };
    }
    anunciar(
      `Atlas pronto: ${projection.meta.counts.notes} entidades em ` +
        `${projection.meta.domains.length} domínios. ` +
        'Arraste o fundo para girar a câmera, role para aproximar, clique para selecionar, ' +
        'duplo clique ou Enter para recentrar. ' +
        'A régua à direita leva aos painéis principais fixos. ' +
        'Teclas: G restaura a visão global; Esc solta a escolha. ' +
        `Memória espacial: ${reused} posições reaproveitadas, ${placed} novas, ` +
        `${textoPersistenciaCorpus}; ` +
        `ordinais operacionais: ${persistenciaOperacional}.`,
    );
  } catch (error) {
    if (cicloAplicacao.signal.aborted) return;
    falhar(error instanceof ContractError ? error.message : String(error));
  }
}

void iniciar();
