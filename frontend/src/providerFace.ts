// A face do painel de um provedor: a superfície dele, desenhada em DOM sobre a placa.
//
// **Por que DOM.** Campo mascarado, foco, gerenciador de senha e leitor de tela já
// existem no navegador. Um `<input type="password">` desenhado com troika não tem nada
// do que faz um campo de senha ser um campo de senha, e a credencial é justamente o que
// não se pode desenhar por aproximação.
//
// **Por que sobre a placa, e não ao lado.** Ao lado é uma segunda superfície: ela
// precisa dizer de quem é, e a pessoa precisa acreditar. Sobre a placa não há o que
// dizer — a face ocupa a área de leitura do próprio painel, projetada quadro a quadro
// pelo Atlas, e por isso ela **é** o painel. Enquanto ela existe, o texto 3D daquele
// painel não é desenhado: a superfície continua sendo uma só.
//
// **Redesenho não atropela digitação.** O retrato do controle é buscado a cada poucos
// segundos. Reconstruir a face a cada busca apagaria a chave sendo digitada; por isso
// ela só é reconstruída quando a assinatura do que ela mostra muda de verdade.
//
// **Segredo.** O campo é `type="password"`, tem `autocomplete="off"`, nunca é lido de
// volta e é esvaziado assim que o valor sai daqui rumo à porta. Gravar exige dois
// cliques: é o segundo, explícito, que constitui a autorização humana.

import type { PanelFaceRect } from './atlas';
import type { ProviderFaceModel, WorkerFaceModel } from './providerPanel';

/**
 * O que a face desenha.
 *
 * Provedor e trabalhador são o mesmo gesto — escolher a placa abre a configuração
 * dela — e superfícies diferentes: um configura credencial, o outro decide se o papel
 * participa e com quanta simultaneidade. A união é discriminada para que nenhum ramo
 * tenha de adivinhar qual dos dois recebeu.
 */
export type FaceModel =
  | ({ kind: 'provider' } & ProviderFaceModel)
  | ({ kind: 'worker' } & WorkerFaceModel);

/** As ações que a face pode pedir. Ausente significa "ainda não há como". */
export interface ProviderFacePorts {
  applyKey?: (providerId: string, key: string) => void;
  testKey?: (providerId: string, key: string | undefined) => void;
  removeKey?: (providerId: string) => void;
  setWorkerEnabled?: (workerId: string, enabled: boolean) => void;
  setWorkerConcurrency?: (workerId: string, value: number) => void;
  setWorkerReasoning?: (workerId: string, value: string) => void;
  /** A face pediu para se fechar — `Esc` dentro dela, ou o botão de fechar. */
  onClose?: () => void;
  /** A confirmação abriu ou fechou; quem mantém o estado precisa saber para redesenhar. */
  onConfirmChange?: (confirming: boolean) => void;
}

export interface ProviderFaceHandle {
  element: HTMLElement;
  /** Desenha o modelo. Reconstrói só o que mudou de assinatura. */
  render: (model: FaceModel) => void;
  /** Põe a face sobre a placa. `null` a tira da tela. */
  place: (rect: PanelFaceRect | null) => void;
  /** Leva o foco ao campo da chave, se ele existir. */
  focusKey: () => void;
  close: () => void;
  readonly open: boolean;
  readonly providerId: string | null;
  dispose: () => void;
}

/**
 * A altura de referência da face, em pixels.
 *
 * A tipografia escala com a placa porque a face **é** a placa: aproximar aumenta o
 * texto do painel, e um formulário que ficasse do mesmo tamanho enquanto a superfície
 * cresce denunciaria que ele não pertence a ela. O valor é a altura da área de leitura
 * de um painel-âncora na distância de leitura, que é onde ele abre.
 */
const ALTURA_DE_REFERENCIA = 210;
/** Piso e teto da escala: ilegível não vira informação, e gigante não vira ênfase. */
const ESCALA_MINIMA = 0.68;
const ESCALA_MAXIMA = 1.7;

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

export function createProviderFace(ports: ProviderFacePorts = {}): ProviderFaceHandle {
  const element = el('section', 'face');
  element.id = 'provider-face';
  element.hidden = true;
  element.setAttribute('aria-hidden', 'true');
  element.setAttribute('aria-label', 'Configuração do painel');

  const corpo = el('div', 'face__corpo');
  element.append(corpo);

  let aberto = false;
  let provedor: string | null = null;
  let assinatura: string | null = null;
  /**
   * A chave digitada, viva apenas entre o clique em Aplicar e a confirmação.
   *
   * Abrir a confirmação muda a assinatura, a face é reconstruída, e a reconstrução
   * cria um campo novo e vazio. Sem isto o segundo clique leria campo vazio e nada
   * seria gravado — foi exatamente o defeito que o dock teve.
   */
  let chavePendente: string | null = null;
  let campo: HTMLInputElement | null = null;

  function fechar(): void {
    if (!aberto) return;
    aberto = false;
    provedor = null;
    assinatura = null;
    chavePendente = null;
    campo = null;
    element.hidden = true;
    element.setAttribute('aria-hidden', 'true');
    if (element.contains(document.activeElement)) {
      (document.activeElement as HTMLElement | null)?.blur();
    }
    corpo.replaceChildren();
  }

  function assinaturaDe(model: FaceModel): string {
    return JSON.stringify(model);
  }

  /** Cabeçalho e frases da placa: iguais nos dois tipos, porque é o painel falando. */
  function desenharTopo(model: FaceModel): void {
    const topo = el('div', 'face__topo');
    topo.append(el('h2', 'face__nome', model.name));
    const marca = el('span', `face__marca face__marca--${model.status.kind}`);
    marca.append(
      el('span', 'face__marca-sinal', model.status.mark),
      document.createTextNode(model.status.label),
    );
    topo.append(marca);
    corpo.append(topo);
    // O nome já está no cabeçalho. A placa o repete como rótulo curto, e numa face de
    // duzentos pixels de altura cada linha repetida empurra uma frase real para fora.
    const nome = model.name.trim().toLowerCase();
    for (const frase of model.lines) {
      if (frase.trim().toLowerCase() === nome) continue;
      corpo.append(el('p', 'face__linha', frase));
    }
  }

  function desenharTrabalhador(model: { kind: 'worker' } & WorkerFaceModel): void {
    corpo.replaceChildren();
    campo = null;
    desenharTopo(model);
    corpo.append(el('p', 'face__linha face__linha--forte', model.resolutionLine));
    corpo.append(el('p', 'face__linha face__linha--fraca', model.originLine));
    if (model.runningLine) corpo.append(el('p', 'face__linha', model.runningLine));

    const acoes = el('div', 'face__acoes');
    const ligar = el('button', 'face__botao', model.enabledAction.label);
    ligar.type = 'button';
    ligar.disabled = model.enabledAction.blocked !== null;
    ligar.setAttribute('aria-pressed', String(model.enabled));
    if (model.enabledAction.blocked) ligar.title = model.enabledAction.blocked;
    ligar.addEventListener('click', () => ports.setWorkerEnabled?.(model.id, !model.enabled));
    acoes.append(ligar);
    corpo.append(acoes);

    // Stepper, não deslizante: o valor é discreto e tem teto declarado pelo backend.
    const rotulo = el('label', 'face__campo');
    rotulo.append(
      el('span', 'face__campo-rotulo', `Simultâneas (máximo ${model.concurrency.max})`),
    );
    const passo = el('input', 'face__entrada face__entrada--num');
    passo.type = 'number';
    passo.min = String(model.concurrency.min);
    passo.max = String(model.concurrency.max);
    passo.step = '1';
    passo.value = String(model.concurrency.value);
    passo.disabled = model.concurrency.blocked !== null;
    if (model.concurrency.blocked) passo.title = model.concurrency.blocked;
    passo.addEventListener('change', () =>
      ports.setWorkerConcurrency?.(model.id, Number(passo.value)),
    );
    rotulo.append(passo);
    corpo.append(rotulo);

    if (model.reasoning.options) {
      const rotuloRaciocinio = el('label', 'face__campo');
      rotuloRaciocinio.append(el('span', 'face__campo-rotulo', 'Raciocínio'));
      const select = el('select', 'face__entrada');
      select.disabled = model.reasoning.blocked !== null;
      if (model.reasoning.blocked) select.title = model.reasoning.blocked;
      for (const opcao of model.reasoning.options) {
        const item = el('option', undefined, opcao);
        item.value = opcao;
        if (opcao === model.reasoning.value) item.selected = true;
        select.append(item);
      }
      select.addEventListener('change', () =>
        ports.setWorkerReasoning?.(model.id, select.value),
      );
      rotuloRaciocinio.append(select);
      corpo.append(rotuloRaciocinio);
    } else if (model.reasoning.reason) {
      // Nível que o endpoint não declara não é oferecido nem simulado. A ausência é
      // dita em uma linha curta, e o motivo inteiro fica no título: é o que separa
      // ausência de esquecimento sem gastar duas linhas da superfície de leitura.
      const sem = el('p', 'face__linha face__linha--fraca', 'Sem níveis de raciocínio.');
      sem.title = model.reasoning.reason;
      corpo.append(sem);
    }

    for (const nota of model.notes) corpo.append(el('p', 'face__nota', nota));
  }

  function desenhar(model: ProviderFaceModel): void {
    // O que já estava digitado atravessa o redesenho. Uma busca do retrato no meio da
    // digitação não pode apagar meia credencial — o guard de assinatura evita a maioria
    // dos redesenhos, e este resgate cobre os que sobram.
    const digitado = campo?.value ?? '';
    corpo.replaceChildren();
    campo = null;

    desenharTopo({ kind: 'provider', ...model });
    corpo.append(el('p', 'face__linha face__linha--forte', model.keyLine));
    corpo.append(el('p', 'face__linha', model.endpointLine));

    const rotulo = el('label', 'face__campo');
    rotulo.append(el('span', 'face__campo-rotulo', 'Chave da API'));
    const entrada = el('input', 'face__entrada');
    entrada.type = 'password';
    entrada.autocomplete = 'off';
    entrada.spellcheck = false;
    entrada.placeholder = 'chave da API';
    entrada.disabled = model.saving;
    entrada.setAttribute('aria-label', `Chave da API de ${model.name}`);
    if (model.confirming && chavePendente !== null) entrada.value = chavePendente;
    else if (digitado !== '') entrada.value = digitado;
    rotulo.append(entrada);
    campo = entrada;
    corpo.append(rotulo);

    const acoes = el('div', 'face__acoes');
    const aplicar = el('button', 'face__botao', model.apply.label);
    aplicar.type = 'button';
    aplicar.disabled = model.apply.blocked !== null;
    if (model.apply.blocked) aplicar.title = model.apply.blocked;

    const testar = el('button', 'face__botao', model.test.label);
    testar.type = 'button';
    testar.disabled = model.test.blocked !== null;
    if (model.test.blocked) testar.title = model.test.blocked;
    testar.addEventListener('click', () => {
      const valor = entrada.value;
      entrada.value = '';
      // Sem valor digitado, testa a chave já configurada. Com valor, testa a
      // candidata — e o backend não a persiste.
      ports.testKey?.(model.id, valor === '' ? undefined : valor);
    });
    acoes.append(aplicar, testar);

    if (model.remove) {
      const remover = el('button', 'face__botao', model.remove.label);
      remover.type = 'button';
      remover.disabled = model.remove.blocked !== null;
      if (model.remove.blocked) remover.title = model.remove.blocked;
      remover.addEventListener('click', () => ports.removeKey?.(model.id));
      acoes.append(remover);
    }
    corpo.append(acoes);

    if (model.confirming) {
      const confirmacao = el('div', 'face__confirmar');
      confirmacao.append(
        el(
          'p',
          'face__linha',
          `Gravar esta chave em ${model.name}? Ela substitui a credencial atual no ` +
            'arquivo de segredos do sistema.',
        ),
      );
      const sim = el('button', 'face__botao face__botao--perigo', 'Confirmar gravação');
      sim.type = 'button';
      sim.addEventListener('click', () => {
        // `chavePendente` tem precedência: é o valor que atravessou o redesenho, e o
        // campo pode ter sido esvaziado por um Testar no meio.
        const valor = chavePendente ?? entrada.value;
        entrada.value = '';
        chavePendente = null;
        ports.onConfirmChange?.(false);
        if (valor !== '') ports.applyKey?.(model.id, valor);
      });
      const nao = el('button', 'face__botao', 'Cancelar');
      nao.type = 'button';
      nao.addEventListener('click', () => {
        chavePendente = null;
        ports.onConfirmChange?.(false);
      });
      const botoes = el('div', 'face__acoes');
      botoes.append(sim, nao);
      confirmacao.append(botoes);
      corpo.append(confirmacao);
    } else {
      aplicar.addEventListener('click', () => {
        if (entrada.value === '') return;
        chavePendente = entrada.value;
        ports.onConfirmChange?.(true);
      });
    }

    for (const nota of model.notes) corpo.append(el('p', 'face__nota', nota));
  }

  element.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    // A tecla morre aqui: o Atlas escuta `Esc` na janela, e sem isto fechar a face
    // limparia a seleção no mesmo gesto.
    event.stopPropagation();
    ports.onClose?.();
  });

  return {
    element,
    render(model) {
      const atual = assinaturaDe(model);
      if (aberto && provedor === model.id && assinatura === atual) return;
      aberto = true;
      provedor = model.id;
      assinatura = atual;
      element.hidden = false;
      element.setAttribute('aria-hidden', 'false');
      if (model.kind === 'worker') desenharTrabalhador(model);
      else desenhar(model);
    },
    place(rect) {
      if (!rect || !aberto) {
        // Fora da tela a face some, mas não se fecha: a câmera pode voltar, e fechar
        // apagaria a chave sendo digitada por causa de um giro do mouse.
        element.style.visibility = 'hidden';
        return;
      }
      const escala = Math.min(
        ESCALA_MAXIMA,
        Math.max(ESCALA_MINIMA, rect.height / ALTURA_DE_REFERENCIA),
      );
      element.style.visibility = 'visible';
      element.dataset.tinta = rect.ink;
      element.style.left = `${Math.round(rect.left)}px`;
      element.style.top = `${Math.round(rect.top)}px`;
      element.style.width = `${Math.round(rect.width)}px`;
      element.style.height = `${Math.round(rect.height)}px`;
      element.style.setProperty('--face-escala', escala.toFixed(3));
    },
    focusKey() {
      // O foco vai ao campo porque foi a credencial que a pessoa veio configurar. A
      // guarda de `keyboardTarget` é o que impede `WASD` de comer a chave enquanto ela
      // digita — ela existe justamente por causa deste caminho.
      campo?.focus();
    },
    close: fechar,
    get open() {
      return aberto;
    },
    get providerId() {
      return provedor;
    },
    dispose() {
      fechar();
      element.remove();
    },
  };
}
