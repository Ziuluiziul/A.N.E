// Declaração do subconjunto de `troika-three-text` que o Atlas usa.
//
// O pacote não publica tipos. `declare module 'troika-three-text'` resolveria o erro
// dando `any` a tudo, o que desligaria a checagem justamente na parte que mais mexe
// com strings e números soltos. Declarar só o que se usa mantém o rigor e documenta
// a superfície da dependência.

declare module 'troika-three-text' {
  import type { Mesh } from 'three';

  export class Text extends Mesh {
    text: string;
    fontSize: number;
    color: number | string;
    anchorX: 'left' | 'center' | 'right' | number | string;
    anchorY: 'top' | 'middle' | 'bottom' | number | string;
    maxWidth: number;
    lineHeight: number | 'normal';
    letterSpacing: number;
    whiteSpace: 'normal' | 'nowrap';
    outlineWidth: number | string;
    outlineColor: number | string;
    textAlign: 'left' | 'right' | 'center' | 'justify';
    /** Reprocessa o layout de glifos. Assíncrono por dentro, fora do frame. */
    sync(callback?: () => void): void;
    dispose(): void;
  }
}
