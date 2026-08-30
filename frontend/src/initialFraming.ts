// O runtime chega depois da primeira composição do Atlas.
//
// O enquadramento inicial, portanto, tem duas fases: primeiro a projeção conhecida no
// startup; depois, uma única correção quando a camada viva ganha geometria. Essa segunda
// fase só pode mover a câmera enquanto a pessoa ainda não a tomou para si.

export type InitialRuntimeFramingAction = 'wait' | 'fit' | 'preserve';

export interface InitialRuntimeFramingState {
  /** A primeira chegada útil do runtime já foi decidida. */
  resolved: boolean;
  /** O snapshot produziu ao menos um painel vivo. */
  hasRuntimePanels: boolean;
  /** A camada viva participa da visão corrente. */
  runtimeVisible: boolean;
  /** A pessoa já girou, aproximou, moveu ou escolheu algo. */
  userInteracted: boolean;
  /** Há um painel do corpus ou do runtime em leitura. */
  hasSelection: boolean;
}

/**
 * Decide a única oportunidade de completar o enquadramento de startup.
 *
 * Snapshot vazio não consome a oportunidade: o primeiro evento ainda precisa caber.
 * Conteúdo oculto, seleção ou qualquer gesto consomem-na sem mover a câmera. Depois
 * disso, atualizações SSE preservam incondicionalmente a pose escolhida.
 */
export function initialRuntimeFramingAction(
  state: InitialRuntimeFramingState,
): InitialRuntimeFramingAction {
  if (state.resolved) return 'preserve';
  if (!state.hasRuntimePanels) return 'wait';
  if (!state.runtimeVisible || state.userInteracted || state.hasSelection) return 'preserve';
  return 'fit';
}
