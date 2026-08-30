import * as THREE from 'three';
import { describe, expect, it } from 'vitest';

import {
  atlasTitlePlacement,
  atlasTitleScreenSize,
  type CloudTitle,
} from './cloudTitles';
import { BASE_LOCAL } from './screenBasis';

function component(point: THREE.Vector3, axis: THREE.Vector3Like): number {
  return point.x * axis.x + point.y * axis.y + point.z * axis.z;
}

describe('o título do Atlas', () => {
  it('fica acima do envelope de todas as nuvens e no centro horizontal do conjunto', () => {
    const clouds: CloudTitle[] = [
      { key: 'corpus', center: new THREE.Vector3(-30, 10, 0), radius: 20 },
      { key: 'operacional', center: new THREE.Vector3(45, 40, 5), radius: 15 },
    ];
    const placement = atlasTitlePlacement(
      clouds,
      new Map([
        ['corpus', 20],
        ['operacional', 30],
      ]),
    )!;
    const top = Math.max(
      ...clouds.map((cloud) => component(cloud.center, BASE_LOCAL.acima) + cloud.radius),
    );
    expect(component(placement.position, BASE_LOCAL.acima)).toBeGreaterThan(
      top + placement.fontSize,
    );

    const left = Math.min(
      ...clouds.map((cloud) => component(cloud.center, BASE_LOCAL.direita) - cloud.radius),
    );
    const right = Math.max(
      ...clouds.map((cloud) => component(cloud.center, BASE_LOCAL.direita) + cloud.radius),
    );
    expect(component(placement.position, BASE_LOCAL.direita)).toBeCloseTo((left + right) / 2);
    expect(placement.fontSize).toBeCloseTo(30 * 1.65);
  });

  it('é 1,65 vez o maior nome, respeita a faixa e cede à largura da janela', () => {
    expect(atlasTitleScreenSize(40, 1920)).toBe(66);
    expect(atlasTitleScreenSize(10, 1920)).toBe(52);
    expect(atlasTitleScreenSize(60, 1920)).toBe(76);
    expect(atlasTitleScreenSize(46, 1366)).toBeCloseTo(46 * 1.65);
    expect(atlasTitleScreenSize(46, 360)).toBeLessThan(52);
  });
});
