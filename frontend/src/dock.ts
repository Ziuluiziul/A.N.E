// Identificadores de controle. A doca DOM (`createDock`) saiu: credencial e
// trabalhador moram na placa, AUTO no cartão `A`. Estes ids continuam sendo a
// chave de pendência/erro nas mutações.

/** Identificadores de controle. É por eles que pendência, erro e conflito se ligam. */
export const controlId = {
  auto: () => 'auto',
  workerEnabled: (id: string) => `worker:${id}:enabled`,
  workerConcurrency: (id: string) => `worker:${id}:concurrency`,
  workerReasoning: (id: string) => `worker:${id}:reasoning`,
};
