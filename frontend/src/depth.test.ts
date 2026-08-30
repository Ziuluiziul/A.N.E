import { describe, expect, it } from 'vitest';

import { cameraPoseForExtent } from './depth';

describe('enquadramento perceptivo', () => {
  it('usa lente moderada e uma visada oblíqua elevada', () => {
    const pose = cameraPoseForExtent(100, 24, 16 / 9);
    // 55° desde 3.5-G: a 38° o enquadramento das três nuvens ia a 9 mil unidades e
    // cada painel virava um ponto. A lente é declarada, e é por isso que o teste a fixa.
    expect(pose.fov).toBe(55);
    expect(pose.position.x).not.toBe(0);
    expect(pose.position.y).toBeLessThan(pose.target.y);
    expect(pose.position.z).toBeGreaterThan(pose.target.z);
    expect(pose.near).toBeGreaterThan(0);
    expect(pose.far).toBeGreaterThan(pose.distance);
    expect(pose.fogDensity).toBeGreaterThan(0);
  });

  it('afasta a câmera quando a largura da janela passa a limitar o quadro', () => {
    const wide = cameraPoseForExtent(100, 24, 16 / 9);
    const narrow = cameraPoseForExtent(100, 24, 9 / 16);
    expect(narrow.distance).toBeGreaterThan(wide.distance);
  });
});
