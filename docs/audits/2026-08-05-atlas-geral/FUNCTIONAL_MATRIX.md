# Matriz funcional — 2026-08-05

Classificação conforme §4.2 do prompt. `FUNCIONA` exige evidência de execução, não
presença de componente. Evidência: `C` código, `R` runtime medido, `T` teste que prende
o comportamento.

| # | Capacidade | Veredicto | Evidência |
|---|---|---|---|
| 1 | Carregamento do corpus | **FUNCIONA** | R: 84 notas, 672 wikilinks, fingerprint `e48f4791…` idêntico ao do auditor. C: `corpus/reader.py`. T: `make audit` zerado |
| 2 | Identidade dos nós | **FUNCIONA** | R: 362 slots, um por entidade. Wikilink ambíguo reprova a construção (`reader.py:347`) |
| 3 | Relações | **DEFEITUOSO** | Dado íntegro (555 arestas, zero duplicata). Renderização dobra 129 pares — F-02, F-12 |
| 4 | MOCs | **FUNCIONA** | R: 15 MOCs, âncoras calculadas com recusa explícita de desempate (`projection.py:177`) |
| 5 | Pontes | **DEFEITUOSO** | 23 de 52 pares recebem dois filamentos, 10 com relação contraditória — F-03 |
| 6 | LOD textual | **FUNCIONA** | R: 5 níveis com histerese 0,78; `lodChanges` 822 sob movimento, 0 em quadro parado. Ressalva: recorte de texto em `legible` — F-10 |
| 7 | Expansão no próprio nó | **FUNCIONA** | R: `EXPANSAO = 2.2` aplicada síncrona; placa da frente substitui a instância sem duplo desenho |
| 8 | Foco de câmera | **PARCIAL** | `aproximarDe` enquadra corretamente (~120 unidades para um MOC). Zoom manual quebra — F-01 |
| 9 | Troca de visões `L/F/M/G` | **PARCIAL** | C: os quatro controles existem. `F` não alcança a camada viva (F-13) e pode coexistir com a espinha (F-12) |
| 10 | Painel lateral | **PARCIAL** | R: 3 abas servidas por snapshot real. Falhas sem estrutura (F-09), Trabalhadores desalinhado da execução (F-07) |
| 11 | Snapshot de controle | **FUNCIONA** | R: `GET /api/control/snapshot` responde com `schema_version 1`, 4 provedores, 7 workers, bloco `operation` |
| 12 | Cadastro e teste de provedores | **FUNCIONA** | C: `PUT/DELETE /providers/{id}/credential`, `POST /providers/{id}/test`. R: 4 provedores com chave configurada e sufixo redigido |
| 13 | Catálogo de endpoints | **FUNCIONA** | R: 193 endpoints catalogados (58 google, 15 groq, 102 nvidia, 18 ollama), com recorte, sondagem e descarte por modalidade |
| 14 | Configuração de workers | **FUNCIONA** | R: 7 papéis, 2 classes, simultaneidade por classe, ativação |
| 15 | Scheduler | **PARCIAL** | R: `queued 21`, `capacity 15`, `last_cycle` de 7h antes. Roda fora da API e está travado — F-08 |
| 16 | Execução de worker | **FUNCIONA** | R: 105 atribuições de membro persistidas em 35 painéis, com provedor/endpoint/família/papel |
| 17 | Geração de candidatos | **FUNCIONA** | R: `proposal.final_response` por painel, com detecção e remoção de bloco de raciocínio |
| 18 | Revisão | **FUNCIONA** | R: 104 votos com decisão, confiança, ação recomendada, evidências por claim e questões bloqueantes |
| 19 | Síntese | **FUNCIONA** | C: `quorum/synthesis.py`. R: campo `synthesis` presente em `decision.json` |
| 20 | Arbitragem | **FUNCIONA** | R: `outcome: escalate` emitido com motivo e apuração |
| 21 | Quórum (mecanismo) | **FUNCIONA** | R: proponente fora do painel, 2 provedores, 3 famílias, invariantes em `_assert_panel_invariants` |
| 21b | Quórum autônomo — disponibilidade corrente | **BLOQUEADO** | R: `queued 21`, `running 0`, `last_cycle` de 7h antes, zero promoções — F-08. Linha auxiliar, não conta no total de 28 |
| 22 | Decisão final | **FUNCIONA** | R: 34 decisões persistidas com apuração completa |
| 23 | Persistência da execução | **FUNCIONA** | R: `runtime/quorum/<id>/` com task, members, proposal, votes, decision, events |
| 24 | Orçamento | **PARCIAL** | R: `budget: "6 chamadas por execução"` declarado; `calls: null`, com motivo — não é persistido entre execuções |
| 25 | Falhas | **DEFEITUOSO** | R: lista de strings, sem código, severidade, timestamp nem agregação — F-09 |
| 26 | Auditoria | **PARCIAL** | `make audit` funciona e zera. `last_audit: null` no snapshot, com motivo declarado: roda fora da API |
| 27 | Telemetria | **PARCIAL** | R: pool de texto e contadores de sincronização instrumentados. Sem FPS, frame time nem custo por execução |
| 28 | Observabilidade 3D | **PARCIAL** | R: 278 nós operacionais chegam à cena. Sem diferenciação espacial (F-06) e sem painel de deliberação (F-14) |

## Invariantes da baseline declarada (§2.2)

| Invariante | Resultado | Medição |
|---|---|---|
| Endpoint `GET /api/control/snapshot` | **confirmado** | responde 200 com `schema_version 1` |
| Pool de texto com exatamente 64 objetos Troika | **confirmado** | `capacity 64`, `createdObjects 64` |
| `visibleObjects ≤ allocatedSlots ≤ 64` | **confirmado** | 64 ≤ 64 ≤ 64 |
| Zero sincronizações espúrias em quadro estável | **confirmado** | `syncCalls` 556 antes e 556 depois de 1,5 s parado |
| Corpus com 84 notas e 672 wikilinks | **confirmado** | `make audit` |
| Zero links quebrados, órfãs e relações fora do vocabulário | **confirmado** | `make audit`, todas as linhas em 0 |
| Working tree limpa no fechamento anterior | **confirmado** | `git status --short` vazio em `1457d93` |
| Incremento visual 3.4 A–D concluído | **não verificável como unidade** | os invariantes acima passam; "concluído" não tem critério medível declarado |

## Prontidão operacional, separada do mecanismo

Distinção exigida pelo parecer de aceitação. Execução histórica não é prova de saúde
corrente.

| Dimensão | Veredicto | Medição |
|---|---|---|
| `quorum_engine` | **FUNCIONA** | 35 painéis, 104 votos, 34 decisões persistidos |
| `autonomous_quorum_availability` | **BLOQUEADO** | cardinalidade insuficiente: 3 endpoints úteis para os 4+ exigidos |
| `autonomous_loop_readiness` | **NÃO PRONTO** | `queued 21`, `running 0`, `last_cycle` +7h, zero propostas promovidas |

## Gates

| Gate | Resultado |
|---|---|
| `make audit` | **APROVADO** — todas as linhas de defeito em 0 |
| `make test` | **APROVADO** — 387 pytest, 217 vitest, 14 arquivos |
| `make lint` | **APROVADO** — ruff, mypy, eslint, saída 0 |

Os três gates passam. Nenhum dos 14 achados desta auditoria é capturado por eles — o que
é informação sobre a cobertura dos gates, não sobre a gravidade dos achados.
