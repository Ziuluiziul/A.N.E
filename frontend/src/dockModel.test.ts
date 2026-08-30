// O painel de controle não pode inventar dado nem tocar em segredo. É o que este
// arquivo prende, antes de existir um elemento de DOM.

import { describe, expect, it } from 'vitest';

import type { ControlSnapshot, ProviderState, WorkerState } from './controlApi';
import {
  AGUARDANDO_BACKEND,
  DOCK_TABS,
  DOCK_TAB_IDS,
  SEM_INFORMACAO,
  badge,
  describeDock,
  emptyDockData,
  type DockData,
} from './dockModel';

const LEGENDA = 'PAINÉIS\nMOC: largo 16:9';

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

function trabalhador(patch: Partial<WorkerState> = {}): WorkerState {
  return {
    id: 'verificador-factual',
    role: 'verificador-factual',
    class_name: 'avaliador',
    summary: 'procura erros objetivos',
    area: 'knowledge/',
    status: 'espera',
    provider: 'groq',
    model: 'qwen/qwen3',
    resolved_by: 'auto',
    reasoning: { supported: false, options: [], value: null, reason: 'o catálogo não declara' },
    concurrency: 1,
    concurrency_min: 0,
    concurrency_max: 3,
    enabled: true,
    running: 0,
    detail: 'resolvido pela política canônica',
    palette_token: 'D08',
    ...patch,
  };
}

function snapshot(patch: Partial<ControlSnapshot> = {}): ControlSnapshot {
  return {
    schema_version: 1,
    generated_at: '2026-08-05T00:00:00+00:00',
    providers: [provedor()],
    workers: [trabalhador()],
    operation: {
      auto: true,
      active_workers: 2,
      capacity: 6,
      queued: 0,
      running: null,
      last_cycle: null,
      next_run: null,
      calls: null,
      budget: '6 chamadas por execução',
      failures: [],
      last_audit: null,
      unavailable: {
        running: 'a fila ainda não foi criada',
        last_cycle: 'nenhuma tentativa registrada ainda',
        next_run: 'depende do worker, que roda fora da API',
        calls: 'não persistido entre execuções',
        last_audit: 'roda fora da API',
      },
    },
    notices: [],
    ...patch,
  };
}

function dados(patch: Partial<DockData> = {}): DockData {
  return { ...emptyDockData(LEGENDA), phase: 'pronto', snapshot: snapshot(), ...patch };
}

describe('ausência é dita com o motivo, nunca preenchida com zero', () => {
  it('cada medida ausente sai como ausência explícita e justificada', () => {
    const operacao = describeDock(dados()).tabs.find((tab) => tab.id === 'operacao')!;
    const faltantes = operacao.rows.filter((linha) => linha.missing);
    expect(faltantes.length).toBeGreaterThan(0);
    for (const linha of faltantes) {
      expect(linha.value).toBe(SEM_INFORMACAO);
      // O defeito que isto impede: "0 chamadas" e "não sei quantas chamadas" são
      // afirmações diferentes, e a segunda não pode ser publicada como a primeira.
      expect(linha.value).not.toBe('0');
      expect(linha.hint).not.toBe('');
    }
  });

  it('zero medido sobrevive ao caminho e não vira ausência', () => {
    const operacao = describeDock(dados()).tabs.find((tab) => tab.id === 'operacao')!;
    const fila = operacao.rows.find((linha) => linha.label === 'Fila atual')!;
    expect(fila.missing).toBe(false);
    expect(fila.value).toBe('0');
  });

  it('endpoints sem catálogo dizem por que não foram contados', () => {
    const semCatalogo = snapshot({
      providers: [
        provedor({ endpoint_count: null, unavailable: { endpoint_count: 'descoberta não rodou' } }),
      ],
    });
    const linha = describeDock(dados({ snapshot: semCatalogo })).tabs
      .find((tab) => tab.id === 'provedores')!
      .providers[0]!;
    expect(linha.endpointCount).toBeNull();
    expect(linha.endpointReason).toBe('descoberta não rodou');
  });

  it('antes da primeira resposta, as abas dizem que aguardam', () => {
    const modelo = describeDock(emptyDockData(LEGENDA));
    expect(modelo.phase).toBe('carregando');
    for (const tab of modelo.tabs) expect(tab.empty).toBe(AGUARDANDO_BACKEND);
  });

  it('backend fora do ar vira indisponibilidade com motivo, não tela vazia', () => {
    const modelo = describeDock(
      dados({ phase: 'indisponivel', snapshot: null, reason: 'sem resposta do backend' }),
    );
    expect(modelo.banner).toBe('sem resposta do backend');
    expect(modelo.tabs[0]!.empty).toBe('sem resposta do backend');
  });

  it('leitura antiga é mostrada, mas anunciada como antiga', () => {
    const modelo = describeDock(dados({ stale: true }));
    expect(modelo.banner).toContain('desatualizada');
    // O conteúdo continua lá: uma leitura anterior ainda serve, desde que não se
    // apresente como sendo de agora.
    expect(modelo.tabs.find((tab) => tab.id === 'provedores')!.providers).toHaveLength(1);
  });
});

describe('AUTO se diz em palavras', () => {
  it('desconhecido não passa por desligado', () => {
    const modelo = describeDock(emptyDockData(LEGENDA));
    expect(modelo.autoKnown).toBe(false);
    expect(modelo.autoOn).toBe(false);
    expect(modelo.autoLabel).toContain(SEM_INFORMACAO);
    expect(modelo.autoLabel).not.toContain('DESLIGADO');
  });

  it('ligado e desligado têm rótulos distintos e explícitos', () => {
    const ligado = describeDock(dados());
    const desligado = describeDock(
      dados({ snapshot: snapshot({ operation: { ...snapshot().operation, auto: false } }) }),
    );
    expect(ligado.autoLabel).toBe('AUTO ATIVO');
    expect(desligado.autoLabel).toBe('AUTO DESLIGADO');
    expect(ligado.autoOn).toBe(true);
    expect(desligado.autoOn).toBe(false);
  });
});

describe('nenhum estado depende só de cor', () => {
  it('todo estado traz palavra e sinal, e os sinais são distintos', () => {
    const estados = (['ativo', 'inativo', 'erro', 'espera', 'desconhecido'] as const).map(badge);
    for (const estado of estados) {
      expect(estado.label.length).toBeGreaterThan(0);
      expect(estado.mark.length).toBeGreaterThan(0);
    }
    expect(new Set(estados.map((e) => e.mark)).size).toBe(estados.length);
    expect(new Set(estados.map((e) => e.label)).size).toBe(estados.length);
  });

  it('os cinco estados de provedor não se confundem entre si', () => {
    const rotulos = (['disponivel', 'configurado', 'ausente', 'invalido', 'erro'] as const).map(
      (status) =>
        describeDock(dados({ snapshot: snapshot({ providers: [provedor({ status })] }) })).tabs
          .find((tab) => tab.id === 'provedores')!
          .providers[0]!.status.label,
    );
    expect(new Set(rotulos).size).toBe(rotulos.length);
  });
});

describe('o modelo nunca carrega segredo', () => {
  it('não existe campo de chave, e a dica é curta demais para ser uma', () => {
    const modelo = describeDock(dados());
    const serializado = JSON.stringify(modelo);
    expect(serializado).not.toMatch(/apikey|api_key|secret|token|bearer/i);
    const linha = modelo.tabs.find((tab) => tab.id === 'provedores')!.providers[0]!;
    expect(linha.keyHint!.length).toBeLessThanOrEqual(4);
    expect(Object.keys(linha)).not.toContain('key');
  });
});

describe('raciocínio e simultaneidade só existem onde são reais', () => {
  it('opção de raciocínio inexistente não é simulada', () => {
    const worker = describeDock(dados()).tabs.find((tab) => tab.id === 'trabalhadores')!
      .workers[0]!;
    expect(worker.reasoning.supported).toBe(false);
    expect(worker.reasoning.options).toEqual([]);
    expect(worker.reasoning.reason).not.toBe('');
  });

  it('níveis declarados atravessam exatamente como vieram', () => {
    const comNiveis = snapshot({
      workers: [
        trabalhador({
          reasoning: { supported: true, options: ['low', 'high'], value: 'high', reason: '' },
        }),
      ],
    });
    const worker = describeDock(dados({ snapshot: comNiveis })).tabs.find(
      (tab) => tab.id === 'trabalhadores',
    )!.workers[0]!;
    expect(worker.reasoning.options).toEqual(['low', 'high']);
    expect(worker.reasoning.value).toBe('high');
  });

  it('a simultaneidade declara o teto junto com o valor', () => {
    const worker = describeDock(dados()).tabs.find((tab) => tab.id === 'trabalhadores')!
      .workers[0]!;
    expect(worker.concurrency.value).toBeLessThanOrEqual(worker.concurrency.max);
    expect(worker.concurrency.min).toBeLessThanOrEqual(worker.concurrency.value);
  });

  it('quem resolveu provedor e modelo é dito, e não suposto', () => {
    const auto = describeDock(dados()).tabs.find((t) => t.id === 'trabalhadores')!.workers[0]!;
    expect(auto.origin).toContain('AUTO');
    const semResolucao = describeDock(
      dados({
        snapshot: snapshot({
          workers: [
            trabalhador({
              resolved_by: 'indisponivel',
              provider: null,
              model: null,
              detail: 'AUTO desligado e sem preferência manual declarada',
            }),
          ],
        }),
      }),
    ).tabs.find((t) => t.id === 'trabalhadores')!.workers[0]!;
    expect(semResolucao.provider).toBeNull();
    expect(semResolucao.origin).toContain('sem resolução');
  });
});

describe('a legenda mora no dock', () => {
  it('o texto da cena atravessa até a aba Operação', () => {
    expect(describeDock(dados()).legend).toBe(LEGENDA);
  });

  it('as três abas existem, na ordem declarada', () => {
    expect(describeDock(dados()).tabs.map((t) => t.id)).toEqual(DOCK_TAB_IDS);
  });

  // A doca desenha uma; o modelo descreve três. `provedores` alimenta a face da placa
  // e `operacao` alimenta o cartão — o que saiu foi a segunda superfície, não o dado.
  it('a doca não desenha provedores nem operação', () => {
    expect(DOCK_TABS.map((t) => t.id)).toEqual(['trabalhadores']);
    expect(describeDock(dados()).tabs.some((t) => t.id === 'provedores')).toBe(true);
    expect(describeDock(dados()).tabs.some((t) => t.id === 'operacao')).toBe(true);
  });
});
