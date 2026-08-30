// Os materiais da placa. Nenhuma primitiva sobrou aqui.
//
// Este módulo já foi a fábrica de um corpo geométrico por tipo de entidade — esfera
// para nota, cilindro com anel para MOC, toro para proposta. A ADR-002 tirou o corpo
// de cena e a direção de 3.4 fechou a questão: **o painel visível é o próprio nó**, e
// a ontologia mora na proporção da placa e no cabeçalho escrito, não na primitiva.
//
// O que restou é o que a placa precisa: o material do corpo, onde a solidez carrega o
// estado canônico, e o material do halo que marca a seleção sem virar segundo objeto
// de leitura.

import * as THREE from 'three';

import type { Layer } from './contract';
import { NEUTRALS, oklchToHex } from './palette';

// Estados que não são conhecimento consolidado não podem ser sólidos e opacos.
const NAO_SOLIDOS: ReadonlySet<string> = new Set(['proposed', 'temporary', 'rejected']);

/** Opacidade da placa canônica: fundo suficiente para o texto ser lido sobre ele. */
const OPACIDADE_CANONICA = 0.88;
/** Provisório é mais translúcido, e é assim que ele se distingue sem virar gaiola. */
const OPACIDADE_PROVISORIA = 0.55;

/**
 * Material do corpo. Solidez carrega o estado canônico.
 *
 * Sólido versus vazado é a codificação mais direta que existe para "já é
 * conhecimento" versus "ainda não é" — e é redundante com o cabeçalho escrito, de
 * modo que a distinção sobrevive em escala de cinza.
 */
export function bodyMaterial(
  canonicalState = 'canonical',
  layer: Layer = 'epistemic',
): THREE.MeshStandardMaterial {
  const provisorio = NAO_SOLIDOS.has(canonicalState);
  return new THREE.MeshStandardMaterial({
    emissive: oklchToHex(NEUTRALS.backgroundSecondary),
    emissiveIntensity: layer === 'operational' ? 0.2 : 0.08,
    roughness: layer === 'operational' ? 0.48 : 0.6,
    metalness: layer === 'operational' ? 0.08 : 0.025,
    flatShading: false,
    transparent: true,
    // Painel inativo é mais transparente; o selecionado ganha opacidade em
    // `panelBodies`. Nenhum deles é vazado: wireframe era a representação padrão de
    // `temporary`, e com 278 painéis de quórum mais 167 eventos ao vivo isso virava a
    // floresta de gaiolas que dominava a cena inteira. Provisoriedade se lê pela
    // solidez e pelo cabeçalho escrito, não por uma grade.
    opacity: provisorio ? OPACIDADE_PROVISORIA : OPACIDADE_CANONICA,
    depthWrite: false,
  });
}

/**
 * Opacidade máxima do halo de seleção.
 *
 * Caiu de 0,3 junto com a placa da frente, e pela consequência dela: o halo fica **atrás**
 * da placa, e uma placa mais transparente passou a deixá-lo aparecer por baixo do texto
 * em vez de só contorná-lo. O halo marca qual painel está escolhido; ele não é fundo de
 * leitura.
 */
export const HALO_OPACITY = 0.22;

/**
 * Halo do painel selecionado: uma placa um pouco maior, atrás da que se lê.
 *
 * Três decisões que a versão anterior errava e que a direção de 3.4 corrigiu.
 * `DoubleSide` porque uma casca `BackSide` sobre um plano orientado à câmera
 * simplesmente não aparece — ela era invisível e ninguém tinha percebido.
 * `depthWrite: false` porque o halo não pode ocultar a placa que ele marca. E
 * opacidade baixa porque brilho forte permanente é exatamente o que a direção
 * proíbe: o realce é local, curto e ligado a um estado.
 */
export function panelHaloMaterial(color: number): THREE.MeshBasicMaterial {
  return new THREE.MeshBasicMaterial({
    color,
    side: THREE.DoubleSide,
    transparent: true,
    opacity: HALO_OPACITY,
    depthWrite: false,
  });
}
