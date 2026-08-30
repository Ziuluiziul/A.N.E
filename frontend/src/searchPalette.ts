// Busca sobre a projeção, na cena 3D: título, identidade e domínio, sem acento e
// sem caixa — quem procura "estatistica" precisa achar "Estatística".
//
// Vive aqui, e não dentro do main, para que a normalização e o filtro tenham
// teste próprio. O modo textual tem a busca dele em `fallback.ts`; as duas não
// compartilham código, mas compartilham a regra: acento e caixa nunca contam.

import type { Projection } from './contract';

export interface SearchEntry {
  id: string;
  title: string;
  domainLabel: string;
  kind: string;
  chave: string;
}

export function normalizar(texto: string): string {
  return texto
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase();
}

/** Só o corpus é buscável: painel operacional e placa de modelo não são leitura. */
export function searchIndex(projection: Projection): SearchEntry[] {
  return projection.nodes
    .filter((node) => node.layer === 'epistemic')
    .map((node) => ({
      id: node.id,
      title: node.title,
      domainLabel: node.domainLabel,
      kind: node.kind,
      chave: normalizar(`${node.title} ${node.id} ${node.domainLabel}`),
    }));
}

export function searchMatches(
  index: readonly SearchEntry[],
  consulta: string,
  limite = 8,
): SearchEntry[] {
  const alvo = normalizar(consulta.trim());
  if (alvo === '') return [];
  return index.filter((entrada) => entrada.chave.includes(alvo)).slice(0, limite);
}

export interface SearchPaletteHandle {
  element: HTMLDivElement;
  open(): void;
  close(): void;
  dispose(): void;
}

/**
 * A paleta é um diálogo mínimo: um campo e uma lista de até `limite` itens.
 * Setas navegam, Enter escolhe, Esc fecha — e o Esc **não** vaza para a cena,
 * porque fechar a busca não pode soltar a seleção que o usuário já tinha.
 */
export function createSearchPalette(opcoes: {
  index: readonly SearchEntry[];
  onSelect: (id: string) => void;
  announce: (mensagem: string) => void;
}): SearchPaletteHandle {
  const { index, onSelect, announce } = opcoes;

  const element = document.createElement('div');
  element.className = 'search-palette';
  element.setAttribute('role', 'dialog');
  element.setAttribute('aria-label', 'Buscar entidade do corpus');
  element.hidden = true;

  const campo = document.createElement('input');
  campo.type = 'text';
  campo.placeholder = 'Buscar por título ou domínio…';
  campo.setAttribute('aria-label', 'Texto da busca');

  const lista = document.createElement('ul');
  lista.className = 'search-palette__lista';
  lista.setAttribute('role', 'listbox');

  const dica = document.createElement('p');
  dica.className = 'search-palette__vazio';
  dica.textContent = 'Digite para buscar; ↑↓ navegam, Enter escolhe, Esc fecha.';

  element.append(campo, dica, lista);

  let ativo = -1;
  let resultados: readonly SearchEntry[] = [];

  const itens = (): HTMLElement[] => Array.from(lista.querySelectorAll<HTMLElement>('[role="option"]'));

  function redesenhar(): void {
    resultados = searchMatches(index, campo.value);
    lista.replaceChildren();
    if (resultados.length === 0) {
      dica.hidden = false;
      ativo = -1;
      return;
    }
    dica.hidden = true;
    resultados.forEach((entrada, indice) => {
      const item = document.createElement('li');
      const botao = document.createElement('button');
      botao.type = 'button';
      botao.className = 'search-palette__item';
      botao.setAttribute('role', 'option');
      botao.setAttribute('aria-selected', 'false');
      const titulo = document.createElement('span');
      titulo.className = 'search-palette__titulo';
      titulo.textContent = entrada.title;
      const dominio = document.createElement('span');
      dominio.className = 'search-palette__dominio';
      dominio.textContent = entrada.domainLabel;
      botao.append(titulo, dominio);
      botao.addEventListener('click', () => escolher(indice));
      item.append(botao);
      lista.append(item);
    });
    ativo = 0;
    pintarAtivo();
  }

  function pintarAtivo(): void {
    const botoes = itens();
    botoes.forEach((botao, indice) => {
      const ligado = indice === ativo;
      botao.classList.toggle('search-palette__item--ativa', ligado);
      botao.setAttribute('aria-selected', String(ligado));
    });
    if (ativo >= 0 && ativo < botoes.length) {
      botoes[ativo]?.scrollIntoView({ block: 'nearest' });
    }
  }

  function escolher(indice: number): void {
    const entrada = resultados[indice];
    if (!entrada) return;
    close();
    onSelect(entrada.id);
  }

  campo.addEventListener('input', redesenhar);
  campo.addEventListener('keydown', (evento) => {
    if (evento.key === 'ArrowDown') {
      evento.preventDefault();
      if (resultados.length > 0) ativo = (ativo + 1) % resultados.length;
      pintarAtivo();
    } else if (evento.key === 'ArrowUp') {
      evento.preventDefault();
      if (resultados.length > 0) ativo = (ativo + resultados.length - 1) % resultados.length;
      pintarAtivo();
    } else if (evento.key === 'Enter') {
      evento.preventDefault();
      escolher(ativo);
    } else if (evento.key === 'Escape') {
      // Fechar a busca não é gesto da cena: a seleção atual fica como estava.
      evento.stopPropagation();
      close();
    }
  });

  function open(): void {
    element.hidden = false;
    campo.value = '';
    redesenhar();
    campo.focus();
    announce('Busca aberta. Digite o nome de uma nota; Enter leva até ela.');
  }

  function close(): void {
    if (element.hidden) return;
    element.hidden = true;
    campo.blur();
  }

  function dispose(): void {
    element.remove();
  }

  return { element, open, close, dispose };
}
