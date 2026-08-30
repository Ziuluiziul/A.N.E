// O estado temporal de um modelo sai da trilha, e não de suposição sobre a trilha.
//
// O teste que mais importa aqui é o último: `reasoning` não pode ser afirmado quando o
// provedor não fornece nada. A trilha declara chamada aberta, chamada fechada e — às vezes
// — uma frase de acompanhamento; ela não declara cadeia de pensamento, e o Atlas não pode
// inventar uma.

import { describe, expect, it } from 'vitest';

import {
  cognitiveStates,
  describeCognitiveState,
  isWorking,
  observableCognitiveWork,
  openCognitiveWork,
  withCognition,
  type CognitiveState,
} from './cognitiveState';
import type { CognitionFrame } from './cognition';
import type { RuntimeEvent, RuntimeEventType, RuntimeSnapshot } from './runtime';

let revisao = 0;

function evento(type: RuntimeEventType, extra: Partial<RuntimeEvent> = {}): RuntimeEvent {
  revisao += 1;
  return {
    id: `e${revisao}`,
    revision: revisao,
    timestamp: `2026-08-11T12:00:${String(revisao).padStart(2, '0')}+00:00`,
    type,
    provider: 'groq',
    endpoint: 'qwen/qwen3',
    ...extra,
  };
}

function trilha(...events: RuntimeEvent[]): RuntimeSnapshot {
  return { runtimeRevision: events.length, events, entityByTask: new Map() };
}

const MODELO = 'groq/qwen/qwen3';

function estadoDe(...events: RuntimeEvent[]): CognitiveState {
  return cognitiveStates(trilha(...events)).get(MODELO)!.state;
}

describe('o estado temporal do modelo', () => {
  it('fica em acting enquanto a chamada não volta', () => {
    expect(estadoDe(evento('call_started'))).toBe('acting');
    expect(estadoDe(evento('vote_requested'))).toBe('acting');
  });

  it('vai a final quando a chamada fecha, e guarda o que ficou', () => {
    const status = cognitiveStates(
      trilha(
        evento('vote_requested'),
        evento('vote_received', { decision: 'approve', confidence: 0.86 }),
      ),
    ).get(MODELO)!;
    expect(status.state).toBe('final');
    expect(status.result).toBe('Votou approve, com confiança 86%.');
  });

  it('o resultado permanece até a próxima convocação, e some nela', () => {
    // É o que faz o painel não ser "texto que aparece": terminada a chamada, o fluxo
    // repousa e a resposta continua legível.
    const depoisDeResponder = cognitiveStates(
      trilha(evento('vote_requested'), evento('vote_received', { decision: 'reject' })),
    ).get(MODELO)!;
    expect(depoisDeResponder.result).toBe('Votou reject.');

    const convocadoDeNovo = cognitiveStates(
      trilha(
        evento('vote_requested'),
        evento('vote_received', { decision: 'reject' }),
        evento('vote_requested'),
      ),
    ).get(MODELO)!;
    expect(convocadoDeNovo.state).toBe('acting');
    expect(convocadoDeNovo.result).toBeNull();
  });

  it('declara erro só onde a trilha declara falha', () => {
    const status = cognitiveStates(
      trilha(evento('vote_requested'), evento('vote_received', { schemaValid: false })),
    ).get(MODELO)!;
    expect(status.state).toBe('error');
  });

  it('não chama de raciocínio a narração, que é do orquestrador', () => {
    // Este teste afirmava o contrário, e estava errado. `metadata.narration` é composta
    // por `QuorumOrchestrator._narrar` em f-strings sobre o próprio processo — medido na
    // trilha real, 88 de 1265 eventos a carregam e nenhum traz texto do modelo, porque o
    // orquestrador remove bloco de raciocínio antes de gravar.
    //
    // Enquanto a narração decidia entre `acting` e `reasoning`, a cena exibia "Consultando
    // groq/qwen3.6-27b como revisor-estrutural" como se fosse o raciocínio do modelo: a
    // síntese de cadeia de pensamento que este módulo existe para não fazer.
    const narrada = 'Consultando groq/qwen/qwen3 como revisor-estrutural.';
    expect(estadoDe(evento('call_started'))).toBe('acting');
    expect(estadoDe(evento('call_started', { narration: narrada }))).toBe('acting');

    // A frase não se perde — ela aparece como o que é: o que o sistema está fazendo.
    const comNarracao = cognitiveStates(
      trilha(evento('call_started', { narration: narrada })),
    ).get(MODELO)!;
    expect(describeCognitiveState(comNarracao)).toBe(narrada);
  });

  it('deixa reasoning inalcançável enquanto a trilha não trouxer texto do provedor', () => {
    // A ausência é a afirmação verdadeira sobre hoje: `providers/cognitive.py` já sabe
    // classificar raciocínio de provedor, e a trilha ainda não o transporta. Nenhum
    // caminho de evento pode produzir `reasoning` antes desse transporte existir.
    const tipos: RuntimeEventType[] = [
      'call_started',
      'call_completed',
      'vote_requested',
      'vote_received',
      'task_assigned',
      'quorum_started',
      'quorum_decided',
      'evidence_recorded',
      'proposal_created',
    ];
    for (const tipo of tipos) {
      for (const narration of [undefined, 'Qualquer frase que o orquestrador escreva.']) {
        const estado = estadoDe(evento(tipo, narration === undefined ? {} : { narration }));
        expect(estado, `${tipo} com narração=${String(narration)}`).not.toBe('reasoning');
      }
    }
  });

  it('não inventa estado para modelo que a janela não menciona', () => {
    // A janela guarda os últimos eventos; silêncio dentro dela não é silêncio do modelo.
    // Devolver `latent` seria afirmar repouso onde o que se tem é ausência de notícia.
    const estados = cognitiveStates(trilha(evento('call_started')));
    expect(estados.has('outro/endpoint')).toBe(false);
    expect(estados.size).toBe(1);
  });

  it('ignora evento que não declara modelo', () => {
    const estados = cognitiveStates(
      trilha(evento('task_created', { provider: undefined, endpoint: undefined })),
    );
    expect(estados.size).toBe(0);
  });

  it('só acting e reasoning contam como trabalhando agora', () => {
    const daTrilha = (...events: RuntimeEvent[]) => cognitiveStates(trilha(...events)).get(MODELO)!;
    expect(isWorking(daTrilha(evento('call_started')))).toBe(true);
    expect(isWorking(daTrilha(evento('call_started', { narration: 'x' })))).toBe(true);
    expect(isWorking(daTrilha(evento('call_completed')))).toBe(false);
    expect(isWorking(daTrilha(evento('vote_received', { schemaValid: false })))).toBe(false);
  });

  it('mantém o endpoint ativo quando A fecha e B continua no mesmo modelo', () => {
    const inicioA = evento('call_started', { task: 'tarefa-A' });
    const inicioB = evento('call_started', { task: 'tarefa-B' });
    const fimA = evento('call_completed', { task: 'tarefa-A' });
    const snapshot = trilha(inicioA, inicioB, fimA);

    expect(openCognitiveWork(snapshot).map((work) => work.eventId)).toEqual([inicioB.id]);
    const status = cognitiveStates(snapshot).get(MODELO)!;
    expect(isWorking(status)).toBe(true);
    expect(status.revision).toBe(inicioB.revision);
  });

  it('contabiliza duas aberturas da mesma identidade como multiset', () => {
    const primeiro = evento('call_started', { task: 'mesma-tarefa' });
    const segundo = evento('call_started', { task: 'mesma-tarefa' });
    const fechamento = evento('call_completed', { task: 'mesma-tarefa' });

    // Sem call-id não se inventa pareamento: o fechamento consome a abertura mais antiga
    // e conserva a contagem correta da fila correlacionada.
    expect(
      openCognitiveWork(trilha(primeiro, segundo, fechamento)).map((work) => work.eventId),
    ).toEqual([segundo.id]);
  });

  it('ignora fechamento órfão de janela truncada sem encerrar outra tarefa', () => {
    const inicioB = evento('call_started', { task: 'tarefa-B' });
    const fimA = evento('call_completed', { task: 'tarefa-A' });
    const snapshot = trilha(inicioB, fimA);

    expect(openCognitiveWork(snapshot).map((work) => work.eventId)).toEqual([inicioB.id]);
    expect(isWorking(cognitiveStates(snapshot).get(MODELO)!)).toBe(true);
    expect(
      openCognitiveWork(trilha(evento('call_completed', { task: 'fora-da-janela' }))),
    ).toEqual([]);
  });

  it('fecha sobra da tentativa anterior quando a tarefa é recuperada ou termina', () => {
    const inicio = evento('call_started', { task: 'tarefa-A' });
    const recuperada = evento('task_assigned', {
      task: 'tarefa-A',
      provider: undefined,
      endpoint: undefined,
    });
    expect(openCognitiveWork(trilha(inicio, recuperada))).toEqual([]);
    const recuperado = cognitiveStates(trilha(inicio, recuperada)).get(MODELO)!;
    expect(recuperado.state).toBe('latent');
    expect(describeCognitiveState(recuperado)).toContain('Sem trabalho aberto vigente');

    const terminal = evento('evidence_recorded', {
      task: 'tarefa-A',
      provider: undefined,
      endpoint: undefined,
    });
    expect(openCognitiveWork(trilha(inicio, terminal))).toEqual([]);
  });

  it('não chama de observável uma abertura órfã antiga ou futura', () => {
    const inicio = evento('call_started', { task: 'tarefa-A', deadlineSeconds: 1 });
    const startedAt = Date.parse(inicio.timestamp);
    expect(observableCognitiveWork(trilha(inicio), startedAt + 1)).toHaveLength(1);
    expect(observableCognitiveWork(trilha(inicio), startedAt + 16_000)).toEqual([]);
    expect(observableCognitiveWork(trilha(inicio), startedAt - 1)).toEqual([]);
    expect(cognitiveStates(trilha(inicio), startedAt + 16_000).get(MODELO)!.state).toBe(
      'latent',
    );
  });
});

describe('o raciocínio do provedor sobreposto à trilha', () => {
  function pensamento(text: string, kind: CognitionFrame['kind'] = 'reasoning'): CognitionFrame {
    return {
      revision: 1,
      kind,
      provider: 'groq',
      endpoint: 'qwen/qwen3',
      text,
      timestamp: '2026-08-11T12:00:00+00:00',
    };
  }

  it('leva o modelo a reasoning e diz o que ele está pensando', () => {
    const base = cognitiveStates(trilha(evento('call_started')));
    expect(base.get(MODELO)!.state).toBe('acting');

    const comTexto = withCognition(base, [pensamento('estou conferindo o DOI')]);

    const status = comTexto.get(MODELO)!;
    expect(status.state).toBe('reasoning');
    expect(describeCognitiveState(status)).toBe('estou conferindo o DOI');
  });

  it('aceita tokens de saída quando o modelo não emite scratchpad', () => {
    const base = cognitiveStates(trilha(evento('call_started')));
    const comDelta = withCognition(base, [pensamento('{"operations":[', 'output-delta')]);
    expect(comDelta.get(MODELO)!.state).toBe('reasoning');
    expect(describeCognitiveState(comDelta.get(MODELO)!)).toContain('operations');
  });

  it('aceita resumo de raciocínio, que é o que o Google entrega', () => {
    const base = cognitiveStates(trilha(evento('call_started')));
    const comResumo = withCognition(base, [pensamento('resumindo', 'reasoning-summary')]);
    expect(comResumo.get(MODELO)!.state).toBe('reasoning');
  });

  it('não ressuscita quem a trilha já deu por fechado', () => {
    const fechado = cognitiveStates(
      trilha(evento('call_started'), evento('call_completed')),
    );
    expect(fechado.get(MODELO)!.state).toBe('final');

    const depois = withCognition(fechado, [pensamento('pensamento atrasado')]);

    // O canal é efêmero e pode chegar fora de ordem. Deixá-lo reabrir uma chamada
    // encerrada faria a cena afirmar trabalho que a trilha diz que terminou.
    expect(depois.get(MODELO)!.state).toBe('final');
  });

  it('ignora modelo que a trilha não conhece e quadro sem texto', () => {
    const base = cognitiveStates(trilha(evento('call_started')));

    const estranho = withCognition(base, [
      { ...pensamento('texto'), provider: 'nvidia', endpoint: 'z-ai/glm' },
    ]);
    expect(estranho.has('nvidia/z-ai/glm')).toBe(false);

    const vazio = withCognition(base, [pensamento('   ')]);
    expect(vazio.get(MODELO)!.state).toBe('acting');
  });

  it('devolve o mesmo mapa quando não há quadro nenhum', () => {
    const base = cognitiveStates(trilha(evento('call_started')));
    expect(withCognition(base, [])).toBe(base);
  });
});
