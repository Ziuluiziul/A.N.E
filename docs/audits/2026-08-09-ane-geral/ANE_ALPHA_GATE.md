# Gate Alpha do A.N.E.

Critérios fixados em 2026-08-09T23:41:00-03:00, depois do baseline forense e antes da
avaliação funcional. Os resultados abaixo foram preenchidos sem mudar a regra.

| Critério | Estado | Evidência | Bloqueador? |
| --- | --- | --- | --- |
| Integridade estrutural do corpus: `make audit` termina com código 0 e zero em cada linha de defeito | PASS | [OBSERVADO] 84 notas, 672 wikilinks, 267 claims, zero nos oito defeitos e código 0; manifesto `e48f…a2b3`. | Não |
| Gates do código: `make test` e `make lint` terminam com código 0 no baseline auditado | PASS | [OBSERVADO] 392 testes Python e 302 TypeScript passaram; ruff, mypy, typecheck e eslint passaram. | Não |
| Fluxo corpus→projeção→Atlas: o corpus real é servido, validado e efetivamente renderizado na cena viva | PARCIAL | [OBSERVADO] Cena viva com 442 nós e 1.122 arestas; [OBSERVADO] o frontend faz casts e só valida parte do contrato recebido. | Sim |
| Fluxo proposta→quórum→promoção: um caso completo é demonstrável em cópia isolada, incluindo rejeições e persistência | FAIL | [OBSERVADO] Patch ASCII promove em clone; alvo Unicode real falha, veto estrutural pode ser perdido, crash pós-FF deixa HEAD sem procedência e o worker nunca chama o Promoter. | Sim |
| Honestidade da interface: nenhum controle ou estado material aparenta capacidade que o runtime não executa ou não mede | FAIL | [OBSERVADO] AUTO/workers só alteram `control.json`; atalhos L/F/M não existem; seleção/ênfase runtime divergem após SSE; métricas de texto subcontam objetos. | Sim |
| Segurança: nenhum segredo real no working tree ou histórico e nenhum valor de credencial vaza pelos caminhos exercitados | FAIL | [OBSERVADO] Nenhum segredo real foi detectado pelos padrões; duas reproduções com candidatas sintéticas mostram reflexão integral em 422 e detalhe de adaptador. | Sim |
| Robustez mínima: degrada de modo explícito sem backend, credencial ou corpus e diante de corpus inválido | FAIL | [OBSERVADO] Ausência de credencial é explícita; fallback sem backend congela; watcher publica corpus estruturalmente inválido como revisão válida. | Sim |
| Observabilidade: falhas típicas têm erro, contexto e identificador suficientes para diagnóstico entre API, worker e cena | FAIL | [OBSERVADO] Crash real duplicou chamadas e abandonou painel; rota manual não emite eventos; snapshot SSE pode perder evento; falhas do painel são strings. | Sim |
| Dados sintéticos: nenhum caminho de falha produz `demo` sem opt-in explícito | PASS | [OBSERVADO] `demo_operational` inicia falso, fallback é projeção real e nenhum caminho de falha observado ativa demo. | Não |
| Instalabilidade/configuração: um terceiro consegue instalar e apontar o frontend ao backend sem editar código-fonte | FAIL | [OBSERVADO] Quatro módulos embutem `http://127.0.0.1:8000`; não há configuração de origem. | Sim para publicação; não isoladamente para Alpha local |

## Regra de decisão fixada antes da avaliação

- `PASS — ALPHA`: todos os critérios Alpha estão aprovados; o último pode falhar
  apenas para publicação.
- `CONDITIONAL PASS`: no máximo três correções pequenas, enumeradas, sem P0/P1 e sem
  fluxo crítico ausente.
- `HOLD`: qualquer fluxo crítico não demonstrado, achado P1 de honestidade/segurança,
  gate local falho ou evidência visual obrigatória indisponível.
- `FAIL`: P0 confirmado, perda/corrupção canônica reproduzível, segredo real exposto ou
  promoção capaz de contornar os invariantes centrais.

Esta regra não será ajustada para acomodar o resultado.

## Decisão

**HOLD**.

[INFERIDO] Não há P0 nem corrupção parcial do corpus demonstrada, portanto `FAIL` seria
mais forte que a evidência. Há, porém, vários P1 de segurança, governança, honestidade de
interface e recuperação, além de o fluxo crítico de promoção falhar em condições reais;
isso satisfaz diretamente a regra de `HOLD` fixada antes dos testes.
