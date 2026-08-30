// Navegação direta pelas referências que o próprio layout declara fixas.
//
// É DOM porque um alvo de navegação precisa de foco, nome acessível e tooltip. A cena
// continua sendo a autoridade da posição; o botão apenas chama a câmera existente.

import { oklchToHex, tokenColor } from './palette';
import {
  ANCHOR_GROUP_LABEL,
  ANCHOR_SIDE,
  type AnchorGroup,
  type AnchorSide,
  type AnchorTarget,
} from './anchorRailModel';

export interface AnchorRail {
  /** A régua direita: provedores em cima, conhecimento abaixo. */
  elements: HTMLElement[];
  setActive(id: string | null): void;
  dispose(): void;
}

export function createAnchorRail(
  targets: readonly AnchorTarget[],
  focus: (id: string) => void,
): AnchorRail {
  const buttons = new Map<string, HTMLButtonElement>();
  const groups = new Map<AnchorGroup, AnchorTarget[]>();
  for (const target of targets) groups.set(target.group, [...(groups.get(target.group) ?? []), target]);

  const reguas = new Map<AnchorSide, HTMLElement>();
  const reguaDe = (lado: AnchorSide): HTMLElement => {
    const existente = reguas.get(lado);
    if (existente) return existente;
    const nav = document.createElement('nav');
    nav.className = `anchor-rail anchor-rail--${lado}`;
    nav.setAttribute('aria-label', 'Provedores e territórios do conhecimento');
    reguas.set(lado, nav);
    return nav;
  };

  for (const [group, items] of groups) {
    const element = reguaDe(ANCHOR_SIDE[group]);
    const section = document.createElement('section');
    section.className = 'anchor-rail__group';
    section.dataset.group = group;
    section.setAttribute('aria-label', ANCHOR_GROUP_LABEL[group]);
    // O cabeçalho era `sr-only`: quem enxerga via 27 nomes seguidos e não sabia onde
    // o conhecimento terminava e os trabalhadores começavam. Visível, ele é a separação.
    const heading = document.createElement('h2');
    heading.className = 'anchor-rail__heading';
    heading.textContent = ANCHOR_GROUP_LABEL[group];
    section.append(heading);

    for (const target of items) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'anchor-rail__target';
      button.dataset.anchorId = target.id;
      button.setAttribute('aria-label', `Ir para ${target.label}`);
      button.title = target.label;
      const color = oklchToHex(tokenColor(target.paletteToken));
      button.style.setProperty('--anchor-color', `#${color.toString(16).padStart(6, '0')}`);
      const name = document.createElement('span');
      name.className = 'anchor-rail__name';
      name.textContent = target.name;
      button.append(name);
      button.addEventListener('click', () => focus(target.id));
      buttons.set(target.id, button);
      section.append(button);
    }
    element.append(section);
  }

  return {
    elements: [...reguas.values()],
    setActive(id) {
      for (const [targetId, button] of buttons) {
        if (targetId === id) button.setAttribute('aria-current', 'true');
        else button.removeAttribute('aria-current');
      }
    },
    dispose() {
      for (const regua of reguas.values()) regua.remove();
      buttons.clear();
    },
  };
}
