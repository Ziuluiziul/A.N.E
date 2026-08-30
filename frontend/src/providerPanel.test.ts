// A face de um provedor é o painel dele. Ela não pode inventar estado, não pode
// prometer ação que não há como executar e não pode calar o que a placa já dizia.

import { describe, expect, it } from 'vitest';

import type { ControlSnapshot, ProviderState, WorkerState } from './controlApi';
import { emptyDockData, type DockData } from './dockModel';
import {
  describeProviderFace,
  describeWorkerFace,
  providerControlId,
  workerControlId,
  SEM_PORTA,
  SOB_AUTO,
} from './providerPanel';

const LEGENDA = 'PAINÉIS\nMOC: largo 16:9';
const FRASES = ['Reúne 52 modelos.', '21 de 52 responderam na última sonda.'];

function provedor(patch: Partial<ProviderState> = {}): ProviderState {
  return {
    id: 'groq',
    name: 'Groq',
    status: 'configurado',
    detail: '',
    key_configured: true,
    key_hint: '9f2c',
    endpoint_count: 4,
    enabled: true,
    supports_custom_endpoint: false,
    unavailable: {},
    ...patch,
  };
}

function snapshot(patch: Partial<ControlSnapshot> = {}): ControlSnapshot {
  return {
    schema_version: 1,
    generated_at: '2026-08-13T00:00:00+00:00',
    providers: [provedor()],
    workers: [],
    operation: {
      auto: true,
      active_workers: null,
      capacity: null,
      queued: 0,
      running: null,
      last_cycle: null,
      next_run: null,
      calls: null,
      budget: null,
      failures: [],
      last_audit: null,
      unavailable: {},
    },
    notices: [],
    ...patch,
  };
}

function dados(patch: Partial<DockData> = {}): DockData {
  return { ...emptyDockData(LEGENDA), phase: 'pronto', snapshot: snapshot(), ...patch };
}

const TUDO_PERMITIDO = { confirming: false, canApply: true, canTest: true, canRemove: true };

describe('a face diz o que o painel dizia', () => {
  it('as frases da placa atravessam intactas, na ordem em que chegaram', () => {
    const face = describeProviderFace(dados(), 'groq', FRASES, TUDO_PERMITIDO)!;
    expect(face.lines).toEqual(FRASES);
  });

  it('provedor fora do retrato do controle não vira face vazia', () => {
    expect(describeProviderFace(dados(), 'openrouter', FRASES, TUDO_PERMITIDO)).toBeNull();
  });
});

describe('segredo não passa pelo modelo', () => {
  it('a chave configurada aparece como dica, nunca como valor', () => {
    const face = describeProviderFace(dados(), 'groq', [], TUDO_PERMITIDO)!;
    expect(face.keyLine).toBe('Chave configurada, terminada em 9f2c.');
    expect(JSON.stringify(face)).not.toContain('gsk_');
  });

  it('sem chave, a frase diz isso em vez de sugerir uma', () => {
    const sem = snapshot({
      providers: [provedor({ key_configured: false, key_hint: null, status: 'ausente' })],
    });
    const face = describeProviderFace(dados({ snapshot: sem }), 'groq', [], TUDO_PERMITIDO)!;
    expect(face.keyLine).toBe('Sem chave configurada.');
    // Não há o que remover: o botão não é oferecido.
    expect(face.remove).toBeNull();
  });
});

describe('ausência é dita com o motivo', () => {
  it('catálogo que não cobriu o provedor não vira zero endpoint', () => {
    const sem = snapshot({
      providers: [
        provedor({
          endpoint_count: null,
          unavailable: { endpoint_count: 'a última descoberta não cobriu este provedor' },
        }),
      ],
    });
    const face = describeProviderFace(dados({ snapshot: sem }), 'groq', [], TUDO_PERMITIDO)!;
    expect(face.endpointLine).toContain('não informado');
    expect(face.endpointLine).toContain('não cobriu este provedor');
    expect(face.endpointLine).not.toContain('0 endpoint');
  });

  it('o detalhe do provedor vira nota visível, e não texto perdido', () => {
    const comDetalhe = snapshot({
      providers: [provedor({ detail: 'opt-in free-tier sem teto configurado' })],
    });
    const face = describeProviderFace(dados({ snapshot: comDetalhe }), 'groq', [], TUDO_PERMITIDO)!;
    expect(face.notes).toContain('opt-in free-tier sem teto configurado');
  });
});

describe('ação sem porta é bloqueada com o motivo escrito', () => {
  it('porta ausente não vira botão que finge funcionar', () => {
    const face = describeProviderFace(dados(), 'groq', [], {
      confirming: false,
      canApply: false,
      canTest: false,
      canRemove: false,
    })!;
    expect(face.apply.blocked).toBe(SEM_PORTA);
    expect(face.test.blocked).toBe(SEM_PORTA);
    expect(face.remove?.blocked).toBe(SEM_PORTA);
  });

  it('gravação em voo bloqueia a própria ação, e diz que está gravando', () => {
    const ids = providerControlId('groq');
    const face = describeProviderFace(
      dados({ pending: new Set([ids.key]) }),
      'groq',
      [],
      TUDO_PERMITIDO,
    )!;
    expect(face.saving).toBe(true);
    expect(face.apply.blocked).toBe('Gravando…');
    // Testar não depende da gravação: bloquear tudo faria a face parecer travada.
    expect(face.test.blocked).toBeNull();
  });

  it('erro e conflito do controle chegam à face como nota', () => {
    const ids = providerControlId('groq');
    const face = describeProviderFace(
      dados({
        errors: new Map([[ids.test, 'a chave é válida, mas precisa de teto USD 0']]),
        conflicts: new Map([[ids.key, 'pedido gravar, efetivo recusado']]),
      }),
      'groq',
      [],
      TUDO_PERMITIDO,
    )!;
    expect(face.notes).toContain('a chave é válida, mas precisa de teto USD 0');
    expect(face.notes).toContain('pedido gravar, efetivo recusado');
  });
});

describe('gravar exige o segundo clique', () => {
  it('a confirmação atravessa o modelo, e não é inventada por ele', () => {
    expect(describeProviderFace(dados(), 'groq', [], TUDO_PERMITIDO)!.confirming).toBe(false);
    expect(
      describeProviderFace(dados(), 'groq', [], { ...TUDO_PERMITIDO, confirming: true })!
        .confirming,
    ).toBe(true);
  });
});

function trabalhador(patch: Partial<WorkerState> = {}): WorkerState {
  return {
    id: 'verificador-factual',
    role: 'verificador-factual',
    class_name: 'avaliador',
    summary: 'procura erros objetivos',
    area: 'knowledge/',
    status: 'espera',
    provider: 'google',
    model: 'gemini-3.6-flash',
    resolved_by: 'auto',
    reasoning: { supported: false, options: [], value: null, reason: 'o catálogo não declara' },
    concurrency: 3,
    concurrency_min: 0,
    concurrency_max: 3,
    enabled: true,
    running: 0,
    detail: '',
    palette_token: 'D08',
    ...patch,
  };
}

const TUDO_LIBERADO = { canToggle: true, canSetConcurrency: true, canSetReasoning: true };

function comTrabalhador(patch: Partial<WorkerState> = {}, auto = false): DockData {
  return dados({
    snapshot: snapshot({
      workers: [trabalhador(patch)],
      operation: {
        auto,
        active_workers: null,
        capacity: null,
        queued: 0,
        running: null,
        last_cycle: null,
        next_run: null,
        calls: null,
        budget: null,
        failures: [],
        last_audit: null,
        unavailable: {},
      },
    }),
  });
}

describe('a face de um trabalhador configura o papel, não a execução dele', () => {
  it('diz provedor e modelo resolvidos, sem repetir a origem na mesma frase', () => {
    const face = describeWorkerFace(comTrabalhador(), 'verificador-factual', [], TUDO_LIBERADO)!;
    expect(face.resolutionLine).toBe('Provedor: google · Modelo: gemini-3.6-flash');
    expect(face.originLine).toContain('AUTO');
  });

  it('papel fora do retrato do controle não vira face vazia', () => {
    expect(describeWorkerFace(comTrabalhador(), 'arbitro', [], TUDO_LIBERADO)).toBeNull();
  });

  it('nível de raciocínio que o endpoint não declara não é oferecido nem simulado', () => {
    const face = describeWorkerFace(comTrabalhador(), 'verificador-factual', [], TUDO_LIBERADO)!;
    expect(face.reasoning.options).toBeNull();
    expect(face.reasoning.reason).toBe('o catálogo não declara');
  });

  it('quando o endpoint declara níveis, eles chegam como estão', () => {
    const face = describeWorkerFace(
      comTrabalhador({
        reasoning: {
          supported: true,
          options: ['baixo', 'alto'],
          value: 'alto',
          reason: 'o catálogo declara dois níveis',
        },
      }),
      'verificador-factual',
      [],
      TUDO_LIBERADO,
    )!;
    expect(face.reasoning.options).toEqual(['baixo', 'alto']);
    expect(face.reasoning.value).toBe('alto');
  });

  it('sob AUTO os controles resolvidos ficam visíveis e travados, com o motivo escrito', () => {
    const face = describeWorkerFace(comTrabalhador({}, true), 'verificador-factual', [], TUDO_LIBERADO)!;
    expect(face.concurrency.blocked).toBe(SOB_AUTO);
    expect(face.reasoning.blocked).toBe(SOB_AUTO);
    // Ligar e desligar continua valendo: o AUTO resolve provedor e modelo, e não
    // decide se o papel participa.
    expect(face.enabledAction.blocked).toBeNull();
  });

  it('o teto do papel vem do backend, e o efetivo não o ultrapassa por conta própria', () => {
    const face = describeWorkerFace(
      comTrabalhador({ concurrency: 2, concurrency_max: 3 }),
      'verificador-factual',
      [],
      TUDO_LIBERADO,
    )!;
    expect(face.concurrency).toMatchObject({ value: 2, min: 0, max: 3 });
  });

  it('conflito de simultaneidade chega à face como nota', () => {
    const ids = workerControlId('verificador-factual');
    const base = comTrabalhador();
    const face = describeWorkerFace(
      { ...base, conflicts: new Map([[ids.concurrency, 'pedido 5, efetivo 3 (teto 3)']]) },
      'verificador-factual',
      [],
      TUDO_LIBERADO,
    )!;
    expect(face.notes).toContain('pedido 5, efetivo 3 (teto 3)');
  });
});
