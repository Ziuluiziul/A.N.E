import { describe, expect, it } from 'vitest';

import { initialRuntimeFramingAction } from './initialFraming';

const pristine = {
  resolved: false,
  hasRuntimePanels: true,
  runtimeVisible: true,
  userInteracted: false,
  hasSelection: false,
};

describe('enquadramento inicial do runtime', () => {
  it('espera até existir geometria viva', () => {
    expect(initialRuntimeFramingAction({ ...pristine, hasRuntimePanels: false })).toBe('wait');
  });

  it('completa uma vez o quadro ainda intocado', () => {
    expect(initialRuntimeFramingAction(pristine)).toBe('fit');
  });

  it('não rouba uma câmera que a pessoa já moveu', () => {
    expect(initialRuntimeFramingAction({ ...pristine, userInteracted: true })).toBe('preserve');
  });

  it('não tira de quadro o painel que já está sendo lido', () => {
    expect(initialRuntimeFramingAction({ ...pristine, hasSelection: true })).toBe('preserve');
  });

  it('não enquadra conteúdo fora da camada corrente', () => {
    expect(initialRuntimeFramingAction({ ...pristine, runtimeVisible: false })).toBe('preserve');
  });

  it('preserva a pose em todo snapshot posterior', () => {
    expect(initialRuntimeFramingAction({ ...pristine, resolved: true })).toBe('preserve');
  });
});
