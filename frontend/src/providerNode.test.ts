import { describe, expect, it } from 'vitest';

import { providerIdOf, workerIdOf } from './providerNode';

describe('qual nó abre a configuração de um provedor', () => {
  it('reconhece o provedor da nuvem de provedores, que é o cadastro dele', () => {
    expect(providerIdOf('op/provider/groq')).toBe('groq');
  });

  it('recusa o provedor da camada viva, que é execução e não cadastro', () => {
    // O nó vivo diz "este provedor atendeu nesta chamada". Oferecer campo de chave
    // sobre um passo de raciocínio seria oferecer configurar o passado.
    expect(providerIdOf('runtime:provider:groq')).toBeNull();
  });

  it('recusa o que não é provedor, incluindo o modelo daquele provedor', () => {
    // O modelo tem dono, mas não tem credencial própria: a chave é do provedor. Abrir
    // a configuração sobre a placa do modelo diria que existem duas contas.
    expect(providerIdOf('runtime:model:groq/qwen3')).toBeNull();
    expect(providerIdOf('op/model/groq/qwen3')).toBeNull();
    expect(providerIdOf('runtime:event:runtime-00000000000000000001')).toBeNull();
    expect(providerIdOf('Física/Entropia')).toBeNull();
  });

  it('o trabalhador tem nó próprio, e ele não é provedor', () => {
    expect(workerIdOf('op/worker/verificador-factual')).toBe('verificador-factual');
    expect(providerIdOf('op/worker/verificador-factual')).toBeNull();
    // Um voto é a execução de um papel, não o papel: ele não configura nada.
    expect(workerIdOf('op/quorum/abc/vote/def')).toBeNull();
    expect(workerIdOf('op/provider/groq')).toBeNull();
    expect(workerIdOf('op/worker/')).toBeNull();
    expect(workerIdOf(null)).toBeNull();
  });

  it('recusa ausência e nome vazio em vez de devolver algo configurável', () => {
    expect(providerIdOf(null)).toBeNull();
    expect(providerIdOf(undefined)).toBeNull();
    expect(providerIdOf('op/provider/')).toBeNull();
    expect(providerIdOf('op/provider/   ')).toBeNull();
  });
});
