// O dock: um overlay de DOM acessível, ao lado da cena e fora do renderizador.
//
// **Por que DOM e não 3D.** Seletor e stepper numérico já existem no navegador, com
// foco, teclado e leitor de tela funcionando. Reconstruí-los dentro da cena custaria
// muito e entregaria menos.
//
// **Credencial, operação e AUTO não moram mais aqui.** A chave é da placa do provedor,
// o trabalhador é da placa dele, e o estado da operação + AUTO moram no cartão. Esta
// doca ficou só com a lista de trabalhadores, e a cena não a monta mais.
//
// **O que este módulo não faz.** Ele não fala com o backend e não inventa número. Ele
// desenha um `DockModel` — decidido em `dockModel.ts` — e chama as portas que recebeu.
// Porta ausente vira controle desabilitado **com o motivo escrito**, que é diferente
// de fingir que funciona.
//
// **Redesenho não atropela digitação.** O snapshot é buscado a cada poucos segundos.
// Reconstruir os cartões a cada busca tiraria o foco do stepper. Por isso cada painel
// só é reconstruído quando a sua assinatura muda de verdade.

import {
  DOCK_TABS,
  describeDock,
  type DockData,
  type DockModel,
  type DockTabId,
  type OperationRow,
  type WorkerRow,
} from './dockModel';

/** As ações que o dock pode pedir. Ausente significa "ainda não há como". */
export interface DockPorts {
  setWorkerEnabled?: (workerId: string, enabled: boolean) => void;
  setWorkerConcurrency?: (workerId: string, value: number) => void;
  setWorkerReasoning?: (workerId: string, value: string) => void;
  setAuto?: (auto: boolean) => void;
}

export interface DockHandle {
  element: HTMLElement;
  render: (data: DockData) => void;
  openTab: (id: DockTabId) => void;
  setVisible: (visible: boolean) => void;
  readonly visible: boolean;
  readonly collapsed: boolean;
  onStateChange: (listener: (state: DockState) => void) => () => void;
  dispose: () => void;
}

export interface DockState {
  visible: boolean;
  collapsed: boolean;
}

/** Identificadores de controle. É por eles que pendência, erro e conflito se ligam. */
export const controlId = {
  auto: () => 'auto',
  workerEnabled: (id: string) => `worker:${id}:enabled`,
  workerConcurrency: (id: string) => `worker:${id}:concurrency`,
  workerReasoning: (id: string) => `worker:${id}:reasoning`,
};

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className?: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function badgeNode(status: { kind: string; label: string; mark: string }): HTMLElement {
  const node = el('span', `dock-badge dock-badge--${status.kind}`);
  node.append(el('span', 'dock-badge__mark', status.mark), document.createTextNode(status.label));
  return node;
}

function fieldRow(label: string, control: HTMLElement, hint?: string): HTMLElement {
  const wrap = el('label', 'dock-field');
  wrap.append(el('span', 'dock-field__label', label), control);
  if (hint) wrap.append(el('span', 'dock-field__hint', hint));
  return wrap;
}

const SEM_PORTA = 'ainda não conectado ao backend';

export function createDock(ports: DockPorts = {}): DockHandle {
  const element = el('aside', 'dock');
  element.id = 'dock';
  element.setAttribute('aria-label', 'Painel operacional');
  // Nasce fora da árvore visual e acessível. Quem o abre é `setVisible`, nunca uma
  // classe aplicada de fora depois do primeiro quadro.
  element.hidden = true;
  element.setAttribute('aria-hidden', 'true');

  const header = el('div', 'dock-header');
  const recolher = el('button', 'dock-collapse');
  recolher.type = 'button';
  recolher.setAttribute('aria-controls', 'dock-body');
  header.append(el('h1', 'dock-title', 'Operação do Vault'), recolher);

  const aviso = el('p', 'dock-aviso');
  aviso.setAttribute('role', 'status');
  aviso.hidden = true;

  const tablist = el('div', 'dock-tabs');
  tablist.setAttribute('role', 'tablist');
  const body = el('div', 'dock-body');
  body.id = 'dock-body';
  const footer = el('div', 'dock-footer');
  const autoBotao = el('button', 'dock-auto');
  autoBotao.type = 'button';
  footer.append(autoBotao);

  element.append(header, aviso, tablist, body, footer);

  const paineis = new Map<DockTabId, HTMLElement>();
  const abas = new Map<DockTabId, HTMLButtonElement>();
  const assinaturas = new Map<DockTabId, string>();
  let visivel = false;
  let recolhido = false;
  let ultimo: DockModel | null = null;
  const ouvintesDeEstado = new Set<(state: DockState) => void>();

  function estado(): DockState {
    return { visible: visivel, collapsed: recolhido };
  }

  function avisarEstado(): void {
    const atual = estado();
    for (const ouvinte of ouvintesDeEstado) ouvinte(atual);
  }

  function setVisible(visible: boolean): void {
    if (visible === visivel) return;
    visivel = visible;
    element.hidden = !visible;
    element.setAttribute('aria-hidden', String(!visible));
    if (!visible && element.contains(document.activeElement)) {
      (document.activeElement as HTMLElement | null)?.blur();
    }
    avisarEstado();
  }

  for (const tab of DOCK_TABS) {
    const botao = el('button', 'dock-tab', tab.label);
    botao.type = 'button';
    botao.id = `dock-tab-${tab.id}`;
    botao.setAttribute('role', 'tab');
    botao.setAttribute('aria-controls', `dock-panel-${tab.id}`);
    botao.addEventListener('click', () => abrir(tab.id));
    tablist.append(botao);
    abas.set(tab.id, botao);

    const painel = el('div', 'dock-panel');
    painel.id = `dock-panel-${tab.id}`;
    painel.setAttribute('role', 'tabpanel');
    painel.setAttribute('aria-labelledby', `dock-tab-${tab.id}`);
    body.append(painel);
    paineis.set(tab.id, painel);
  }

  function abrir(id: DockTabId): void {
    // Trocar de aba mexe em `hidden` e `aria-selected`, e em mais nada. O layout do
    // grafo não é recalculado: continuidade espacial é invariante, não cortesia.
    for (const [tabId, botao] of abas) {
      const selecionada = tabId === id;
      botao.setAttribute('aria-selected', String(selecionada));
      botao.classList.toggle('dock-tab--ativa', selecionada);
      botao.tabIndex = selecionada ? 0 : -1;
    }
    for (const [tabId, painel] of paineis) painel.hidden = tabId !== id;
    if (recolhido) toggleCollapsed();
  }

  function toggleCollapsed(): void {
    recolhido = !recolhido;
    element.classList.toggle('dock--recolhido', recolhido);
    recolher.setAttribute('aria-expanded', String(!recolhido));
    recolher.textContent = recolhido ? '›' : '‹';
    recolher.title = recolhido ? 'Abrir o painel operacional' : 'Recolher o painel operacional';
    recolher.setAttribute('aria-label', recolher.title);
    tablist.hidden = recolhido;
    body.hidden = recolhido;
    aviso.hidden = recolhido || aviso.textContent === '';
    avisarEstado();
  }

  recolher.addEventListener('click', toggleCollapsed);
  autoBotao.addEventListener('click', () => {
    if (!ports.setAuto || !ultimo?.autoKnown) return;
    ports.setAuto(!ultimo.autoOn);
  });

  /** Anota erro e conflito de um controle logo abaixo dele. */
  function notas(alvo: HTMLElement, id: string, data: DockData): void {
    const erro = data.errors.get(id);
    if (erro) alvo.append(el('p', 'dock-erro', erro));
    const conflito = data.conflicts.get(id);
    if (conflito) alvo.append(el('p', 'dock-conflito', conflito));
  }

  function desenharTrabalhadores(
    painel: HTMLElement,
    linhas: WorkerRow[],
    vazio: string | null,
    data: DockData,
    autoOn: boolean,
  ): void {
    painel.replaceChildren();
    if (vazio !== null) {
      painel.append(el('p', 'dock-vazio', `Trabalhadores: ${vazio}.`));
      return;
    }
    if (autoOn) {
      // Com AUTO ligado os controles ficam visíveis e bloqueados: esconder faria a
      // interface mudar de forma a cada alternância, e ver o que está resolvido é
      // metade do valor do modo automático.
      painel.append(
        el(
          'p',
          'dock-vazio',
          'AUTO ativo: a política canônica resolve provedor, modelo e simultaneidade. ' +
            'Os controles abaixo mostram os valores resolvidos, em leitura.',
        ),
      );
    }
    for (const worker of linhas) {
      const cartao = el('section', 'dock-card');
      const topo = el('div', 'dock-card__head');
      topo.append(el('h2', 'dock-card__name', worker.role), badgeNode(worker.status));
      cartao.append(topo);
      cartao.append(
        el('p', 'dock-card__hint', `${worker.className} · ${worker.summary} · ${worker.area}`),
      );
      cartao.append(
        el(
          'p',
          'dock-card__hint',
          `Provedor: ${worker.provider ?? 'não informado'} · ` +
            `Modelo: ${worker.model ?? 'não informado'} · ${worker.origin}`,
        ),
      );

      // O seletor de raciocínio só existe onde o endpoint declara os níveis. Opção
      // inexistente não é oferecida e não é simulada.
      if (worker.reasoning.supported && worker.reasoning.options.length > 0) {
        const select = el('select', 'dock-input');
        select.disabled = autoOn || data.pending.has(controlId.workerReasoning(worker.id));
        for (const opcao of worker.reasoning.options) {
          const item = el('option', undefined, opcao);
          item.value = opcao;
          if (opcao === worker.reasoning.value) item.selected = true;
          select.append(item);
        }
        select.addEventListener('change', () =>
          ports.setWorkerReasoning?.(worker.id, select.value),
        );
        cartao.append(fieldRow('Raciocínio', select));
      }

      // Stepper, não slider: o valor é discreto e tem teto declarado pelo backend.
      const passo = el('input', 'dock-input dock-input--num');
      passo.type = 'number';
      passo.min = String(worker.concurrency.min);
      passo.max = String(worker.concurrency.max);
      passo.step = '1';
      passo.value = String(worker.concurrency.value);
      passo.disabled = autoOn || data.pending.has(controlId.workerConcurrency(worker.id));
      passo.addEventListener('change', () =>
        ports.setWorkerConcurrency?.(worker.id, Number(passo.value)),
      );
      cartao.append(
        fieldRow('Simultâneas', passo, `máximo ${worker.concurrency.max} para a classe`),
      );

      const ligar = el('input', 'dock-check');
      ligar.type = 'checkbox';
      ligar.checked = worker.enabled;
      ligar.disabled = data.pending.has(controlId.workerEnabled(worker.id));
      ligar.addEventListener('change', () =>
        ports.setWorkerEnabled?.(worker.id, ligar.checked),
      );
      cartao.append(fieldRow('Ativo', ligar));

      if (worker.running > 0) {
        cartao.append(
          el('p', 'dock-card__hint', `${worker.running} tarefa(s) em execução agora.`),
        );
      }
      notas(cartao, controlId.workerConcurrency(worker.id), data);
      notas(cartao, controlId.workerEnabled(worker.id), data);
      painel.append(cartao);
    }
  }

  function desenharOperacao(
    painel: HTMLElement,
    linhas: OperationRow[],
    vazio: string | null,
    legenda: string,
    notices: string[],
  ): void {
    painel.replaceChildren();
    if (vazio !== null) painel.append(el('p', 'dock-vazio', `Operação: ${vazio}.`));
    for (const nota of notices) painel.append(el('p', 'dock-aviso dock-aviso--inline', nota));

    if (linhas.length > 0) {
      const lista = el('dl', 'dock-lista');
      for (const item of linhas) {
        lista.append(el('dt', undefined, item.label));
        const valor = el('dd', item.missing ? 'dock-ausente' : undefined, item.value);
        if (item.missing && item.hint) valor.title = item.hint;
        lista.append(valor);
        if (item.missing && item.hint) {
          lista.append(el('dt', 'dock-lista__porque', 'por quê'));
          lista.append(el('dd', 'dock-ausente', item.hint));
        }
      }
      painel.append(lista);
    }

    // A legenda sai do bloco flutuante que cobria a cena e vira uma seção recolhível
    // aqui. Ela é texto longo: o lugar dela é onde há rolagem, não sobre o grafo.
    const detalhe = el('details', 'dock-legenda');
    detalhe.append(el('summary', undefined, 'Legenda da cena'));
    detalhe.append(el('pre', 'dock-legenda__texto', legenda));
    painel.append(detalhe);
  }

  function assinaturaDe(tab: DockTabId, modelo: DockModel, data: DockData): string {
    const conteudo = modelo.tabs.find((item) => item.id === tab);
    return JSON.stringify({
      conteudo,
      autoOn: modelo.autoOn,
      pendentes: [...data.pending].sort(),
      erros: [...data.errors].sort(),
      conflitos: [...data.conflicts].sort(),
    });
  }

  function render(data: DockData): void {
    const modelo = describeDock(data);
    ultimo = modelo;

    aviso.textContent = modelo.banner ?? '';
    aviso.hidden = recolhido || modelo.banner === null;

    for (const tab of modelo.tabs) {
      const painel = paineis.get(tab.id);
      if (!painel) continue;
      // Reconstruir sem necessidade apagaria o que está sendo digitado no campo de
      // chave e tiraria o foco do stepper a cada busca do snapshot.
      const assinatura = assinaturaDe(tab.id, modelo, data);
      if (assinaturas.get(tab.id) === assinatura) continue;
      assinaturas.set(tab.id, assinatura);

      if (tab.id === 'trabalhadores') {
        desenharTrabalhadores(painel, tab.workers, tab.empty, data, modelo.autoOn);
      } else {
        desenharOperacao(painel, tab.rows, tab.empty, modelo.legend, modelo.notices);
      }
    }

    autoBotao.textContent = data.pending.has(controlId.auto())
      ? 'AUTO — aplicando…'
      : modelo.autoLabel;
    autoBotao.classList.toggle('dock-auto--ativo', modelo.autoOn);
    autoBotao.setAttribute('aria-pressed', String(modelo.autoOn));
    const bloqueado =
      !ports.setAuto || !modelo.autoKnown || data.pending.has(controlId.auto());
    autoBotao.disabled = bloqueado;
    autoBotao.title = ports.setAuto
      ? 'Alternar o modo automático'
      : SEM_PORTA;
  }

  recolher.setAttribute('aria-expanded', 'true');
  recolher.textContent = '‹';
  recolher.title = 'Recolher o painel operacional';
  recolher.setAttribute('aria-label', recolher.title);
  abrir('trabalhadores');

  return {
    element,
    render,
    openTab: abrir,
    setVisible,
    get visible() {
      return visivel;
    },
    get collapsed() {
      return recolhido;
    },
    onStateChange(listener) {
      ouvintesDeEstado.add(listener);
      return () => ouvintesDeEstado.delete(listener);
    },
    dispose() {
      ouvintesDeEstado.clear();
      element.remove();
    },
  };
}
