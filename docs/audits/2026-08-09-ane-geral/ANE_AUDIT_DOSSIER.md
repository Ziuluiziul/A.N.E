# Dossiê independente — A.N.E. / Atlas Neural-Epistêmico

Auditoria de leitura iniciada em 9 de agosto de 2026 e encerrada em 10 de agosto de
2026, sobre `main@61f2da448b234bde0318237965ac954c2c591c17` e o diff não commitado de
abertura.

## 1. Resumo executivo

[OBSERVADO] O A.N.E. é um corpus Markdown versionado, projetado por uma API Python para
um Atlas 3D, acompanhado de um runtime de tarefas, adaptadores de quatro provedores,
painéis de quórum, eventos SSE e um Promoter Git que deveria ser a única entrada
automatizada no corpus.

[OBSERVADO] A base técnica local é substancial: `make audit`, `make test` e `make lint`
passaram; 84 notas, 672 wikilinks e 267 claims projetaram-se em uma cena viva de 442 nós
e 1.122 arestas; 39 painéis reais preservam membros, votos e decisões; ausência de
credencial aparece como ausência, não como zero.

[OBSERVADO] O núcleo de governança, porém, não fecha de ponta a ponta. O worker termina
uma tarefa aprovada sem chamar o Promoter; os três painéis `promote` não têm patch, os
nove patches são `escalate` e não existe `promotion.json`. Em ensaio isolado, o Promoter
promoveu alvo ASCII, mas recusou alvo Unicode real, descartou veto estrutural ao
recomputar quórum e, sob crash depois do fast-forward, deixou o corpus avançado sem
registro de procedência.

[OBSERVADO] A pergunta central da auditoria tem resposta negativa em vários pontos: a
interface parece governar workers, mas suas preferências não são lidas pela execução;
anuncia atalhos que não existem; mantém seleção runtime que a placa perde no próximo
SSE; mede 640 textos onde cria 1.280; e captura teclas de navegação dentro do campo de
credencial.

[OBSERVADO] A segurança de armazenamento passou os testes positivos principais, mas a
API reflete uma candidata sintética inteira no 422 de validação e pode ecoá-la no detalhe
de um adaptador. Nenhum segredo real foi encontrado pelos padrões examinados, mas o
mecanismo demonstrou capacidade de vazar um valor real futuro.

[INFERIDO] Decisão Alpha: **HOLD**. Não há P0 nem corrupção parcial canônica demonstrada,
mas há P1 em segurança, promoção, identidade de voto, crash recovery e honestidade da
interface; o fluxo crítico de promoção não é utilizável nas condições dos artefatos
reais.

[INFERIDO] Decisão GitHub: **NOT READY**. Antes de qualquer push público são obrigatórios
o fechamento dos vazamentos, uma licença deliberada para software/corpus/evidências,
atualização de dependências vulneráveis, sanitização de documentos pessoais/históricos e
reconciliação da documentação com o produto.

## 2. Baseline

[OBSERVADO] A abertura confirmou branch `main`, HEAD `61f2da4`, 94 commits, tag
`baseline-pos-migracao-2026-07-30`, nenhum remote e 20,30 MiB de objetos soltos.

[OBSERVADO] A árvore já estava suja em seis arquivos do frontend (`+136/-24`) e tinha o
prompt mestre não rastreado. Esse sétimo item divergia da emissão, que declarava zero
untracked. Nada foi guardado, descartado ou commitado.

[OBSERVADO] A saída integral de baseline está no pacote em
`evidence/baseline-opening.txt`; o fechamento aparece no manifesto. O inventário textual
separado contém árvore, contagens, arquivos rastreados e ignorados e rankings de tamanho.

## 3. Arquitetura reconstruída

[OBSERVADO] As fronteiras efetivas são:

- [OBSERVADO] `knowledge/`: produto autoral e estado canônico.
- [OBSERVADO] `vault.corpus`/`projection`: parser, diagnóstico, watcher e projeção.
- [OBSERVADO] `vault.autonomy`/`work`: fila, planejamento, chamadas e transições.
- [OBSERVADO] `providers/`: identidade hospedada, adapters, inventário e aptidão.
- [OBSERVADO] `vault.quorum`: painel, parser, engine, síntese e store.
- [OBSERVADO] `vault.promotion`: patch restrito e worktree Git temporária.
- [OBSERVADO] `vault.events`/API: persistência operacional e SSE.
- [OBSERVADO] `vault.control`: snapshot, preferências e credenciais; preferências não
  cruzam para a execução.
- [OBSERVADO] `frontend/src`: contrato parcialmente validado, cena, navegação, camada
  viva e dock.

### Cinco fluxos ponta a ponta

[OBSERVADO] **Corpus→cena:** watcher → `CorpusReader.build_graph` → `build_projection` →
`/corpus/projection` → cast/validação parcial em `contract.ts` → `createAtlas`. Este fluxo
foi visto ao vivo com corpus real.

[OBSERVADO] **Tarefa→modelo→trilha:** `AutonomousWorker` →
`OrchestratedTaskExecutor` → planner → adapter → recorder/store → `/runtime/events` →
`runtimeLayer`. `make work` usa outro entrypoint e não instancia o recorder.

[OBSERVADO] **Proposta→quórum→corpus:** o orquestrador persiste proposta, patch, votos e
decisão no painel. A execução termina aí. Só `tools/promote.py` chama o Promoter; logo o
fluxo autônomo não alcança o corpus.

[OBSERVADO] **Painel→runtime:** credenciais gravadas entram em Settings de processos
subsequentes; AUTO, enabled, provider, model, reasoning e concurrency entram apenas em
`control.json` e no próprio snapshot.

[OBSERVADO] **Edição→cena sem reload:** watcher publica revisão e SSE; frontend recarrega
projeção. O mecanismo existe, mas o watcher aceita diagnósticos estruturais como revisão
válida e o snapshot operacional tem janela de perda de evento.

### Contratos, estado e concorrência

[OBSERVADO] Quórum, votos, eventos, controle e patch têm modelos Pydantic fechados. A
projeção é `dict[str, Any]`; o TypeScript confia em casts para grande parte da forma.

[OBSERVADO] Fila, eventos, preferências, painéis e patches usam arquivos privados e, em
vários pontos, escrita atômica. Não há transação que una efeito externo, ledger,
`queue.finish`, decisão, fast-forward e procedência.

[OBSERVADO] Os adapters definem timeouts de rede (Google/Groq 30 s, NVIDIA 60 s),
classificam 429 e aplicam `AdaptiveBackoff`. O orquestrador faz uma chamada por
atribuição, sem retry/failover oculto; o worker persiste `retry_wait` em atrasos padrão de
60/300 s. O backoff do adapter vive em memória e o ledger só é salvo no final do runner.

[MEDIDO] Há 20 `except Exception|BaseException` em código de produção. A maioria é
fronteira deliberada que classifica/reergue ou persiste falha; os casos materiais que
perdem verdade são recorder best-effort, falha inicial runtime silenciosa e o tratamento
pós-fast-forward já registrados nos achados.

[OBSERVADO] Limites explícitos incluem 64 KiB por evento, profundidade JSON 8, 256 itens
por coleção, 4.000 caracteres por texto, snapshot SSE de até 2.000 eventos e 160 eventos
visíveis. O log não tem compactação e não há teto global demonstrado de nós/projeção.

[MEDIDO] Seis módulos de produção passam de 700 linhas; `atlas.ts`, `orchestrator.py` e
`operational.py` concentram lifecycle, política e representação em superfícies largas.

[NÃO VERIFICADO] Uma análise formal completa de ciclos de importação não foi produzida.
Os gates e imports de teste não encontraram ciclo impeditivo.

## 4. Inventário funcional — realidade, superfície e narrativa

| Capacidade | Existe de verdade | Só interface | Só documento | Evidência/juízo |
| --- | --- | --- | --- | --- |
| Leitura e projeção do corpus | [OBSERVADO] Sim | — | — | 84 notas reais chegaram à cena |
| Diagnóstico estrutural | [OBSERVADO] Parcial | — | — | links/relations/IDs duplicados; não status/campos/identificadores |
| Watcher + SSE corpus | [OBSERVADO] Sim, permissivo | — | — | publica revisão com link quebrado |
| Eventos operacionais + SSE | [OBSERVADO] Sim | — | — | 1.166 eventos; race no cursor |
| Worker autônomo | [OBSERVADO] Sim, processo externo à API | — | — | crash real e retomada at-least-once |
| Quórum multimodelo | [OBSERVADO] Sim | — | — | 39 painéis; 37 decisões |
| Promoção autônoma | — | [OBSERVADO] Tarefa vira completed | [DECLARADO] README/AGENTS descrevem caminho | worker nunca chama Promoter |
| CLI Promoter | [OBSERVADO] Parcial | — | — | funciona ASCII; falha Unicode/crash/veto |
| `/proposals` | [OBSERVADO] Store legado vazio | [OBSERVADO] API aparenta fila corrente | [DECLARADO] validação humana/manual | não recebe patches atuais |
| AUTO/workers | [OBSERVADO] Persiste preferência | [OBSERVADO] Controles aparentam governar execução | — | nenhum consumidor operacional |
| Credenciais | [OBSERVADO] Gravação real | [OBSERVADO] Dock real | — | armazenamento positivo; dois leaks de entrada |
| Catálogo/aptidão | [OBSERVADO] 193 endpoints catalogados | [OBSERVADO] Cotas exibidas | — | grande parte heurística/desconhecida |
| Atlas corpus | [OBSERVADO] Cena viva real | — | — | 442 nós/1.122 arestas |
| Atlas runtime | [OBSERVADO] Dados reais | [OBSERVADO] seleção/ênfase divergem após SSE | — | lifecycle destrói estado visual |
| L/F/M | — | [OBSERVADO] Anunciados, sem efeito | [DECLARADO] README/mensagem | só G permanece |
| Camada demo | [OBSERVADO] Opt-in explícito | — | — | default falso; falha não ativa demo |
| Telemetria de texto | [OBSERVADO] Contadores existem | [OBSERVADO] subcontam objetos | — | 640 slots criam 1.280 Text |
| Google Workspace | [NÃO VERIFICADO] Código presente | — | [DECLARADO] Guia | OAuth/credencial não exercitados |

### Matriz controle/interação ↔ efeito real

| Controle/interação | Efeito observado/código | Estado tocado | Honestidade |
| --- | --- | --- | --- |
| Arraste | [OBSERVADO] OrbitControls gira câmera | local | honesto |
| Roda sem seleção | [OBSERVADO] zoom com guarda por extensão | local | F-01 antigo não revalidado ao vivo |
| Roda com corpus | [OBSERVADO] rola painel, depois zoom | local | honesto; runtime não rola |
| WASD | [OBSERVADO] translada câmera+alvo | local | correto fora de input; F-11 dentro dele |
| G | [OBSERVADO] limpa foco e reenquadra | local | funciona; compensa F-14 |
| L/F/M | [OBSERVADO] nenhum efeito | nenhum | anunciados, inexistentes |
| Clique corpus | [OBSERVADO] expande, vizinhos/arestas | projeção + local | honesto |
| Clique runtime | [OBSERVADO] expande e acende vínculo | snapshot + local | quebra no próximo SSE |
| Duplo clique | [OBSERVADO] recentra corpus/runtime | local | funciona |
| Enter/Esc | [OBSERVADO] só tratam corpus | local/dock | promessa genérica é falsa para runtime |
| Dock provedor | [OBSERVADO] testa/aplica/remove | secrets via API | real; F-01/F-11 comprometem fronteiras |
| Dock workers/AUTO | [OBSERVADO] PATCH control.json | preferência | aparenta governar execução, mas não governa |
| `setLayer` | [OBSERVADO] filtra quatro camadas | local | API órfã, sem controle de produção |
| SSE runtime | [OBSERVADO] reconstrói nuvem/narração | event log + local | dados reais; perde seleção/ênfase |
| Projeção | [OBSERVADO] monta Atlas | backend ou snapshot estático | validação parcial; offline congela |
| Layout startup | [OBSERVADO] reaplica e tentaria persistir | runtime via backend | mock recusou PUT; não toca corpus |
| Dock oculto | [OBSERVADO] nenhum pixel | GET a cada ~2,5 s | custo/race sem usuário olhando |

## 5. Estado do runtime

[MEDIDO] Há 39 painéis, 117 membros, 115 votos, 37 decisões, 9 patches e zero promoção
registrada. Resultados: 23 escalate, 11 reject, 3 promote; nenhum promote tem patch.

[MEDIDO] 39 votos são schema-invalid; 46 abstenções; nenhuma das 39 tentativas de reparo
foi bem-sucedida. O proponente foi excluído corretamente em todos os painéis.

[OBSERVADO] A fila tem evidência durável de uma execução interrompida e repetida. O
estado corrente do painel mostra workers em “espera” sem verificar se processo algum
está vivo.

[INFERIDO] Os artefatos provam que o mecanismo de deliberação rodou; não provam que uma
promoção real entregou o produto. O núcleo é implementado, mas operacionalmente não
fechado.

## 6. Testes

[OBSERVADO] Passaram 392 testes Python e 302 TypeScript, além de typecheck, ruff, mypy e
eslint. As contagens do prompt (339/~292) estavam defasadas.

[OBSERVADO] Há bons testes de pureza do engine, parser, escrita atômica, restart da fila,
projeção e módulos visuais menores. Um controle positivo em clone confirmou que o
Promoter consegue concluir um patch ASCII.

[OBSERVADO] Os testes não impediram: perda do veto estrutural, alvo Unicode, crash
pós-fast-forward, controles sem consumidor, candidata refletida pelo handler global,
teclado em input, perda de seleção SSE e leak do título do pool.

[INFERIDO] As lacunas mais caras são testes de contrato entre componentes e de
lifecycle: worker→Promoter, decisão persistida→revalidação, FastAPI global→segredo,
SSE→seleção visual, input→atalho e crash em cada fronteira durável.

| Área crítica | O que a suíte observa | O que permanece fora |
| --- | --- | --- |
| Engine/quórum | [OBSERVADO] Pureza, maioria, diversidade, parser e orquestração com fakes | decisão persistida com falha/síntese → Promoter; identidade canônica cross-host |
| Promoção | [OBSERVADO] 393 linhas de testes, escopo de patch, audit e FF em casos normais | Unicode real; SIGKILL pós-FF; journal/recovery; integração automática |
| Credenciais | [OBSERVADO] 523 linhas, escrita/máscara/redação e rotas com adapters falsos | handler global 422; candidata ecoada; teclado no input; parent permissivo |
| Projeção/watcher | [OBSERVADO] parser, projeção e continuidade em temporários | policy que barra diagnóstico estrutural; rajada concorrente; 800 notas |
| Orquestrador/operacional | [OBSERVADO] arquivos dedicados e fakes de SDK | sem chamada externa; crash entre efeito e checkpoint; rota manual sem recorder |
| Atlas | [OBSERVADO] 18 arquivos testam helpers/camadas; não existe `atlas.test.ts` | montagem/lifecycle WebGL integrado, foco, teclado, SSE, dispose e captura viva |

[OBSERVADO] Toda integração externa é simulada na suíte. Os artefatos reais mostram que
a simulação de “resposta parseável” não representa 39/115 votos schema-invalid, 39
reparos sem sucesso nem o crash durável observado.

[INFERIDO] Não foram identificadas asserções literalmente tautológicas em massa; o
harness de texto é a exceção material: compara contador derivado da capacidade fixa e,
portanto, não detecta a segunda alocação por slot.

## 7. Segurança

[OBSERVADO] A varredura por formatos conhecidos não encontrou segredo real no working
tree ou histórico alcançável. Os matches eram valores sintéticos de testes. `.env` real
e arquivos de OAuth não estão versionados.

[OBSERVADO] O caminho de credencial viola o invariante “nunca devolver o valor” em duas
reproduções sintéticas: Pydantic/FastAPI inclui o `input` no 422; `_probe` redige com
Settings que não conhece a candidata.

[OBSERVADO] Escrita atômica, `0600`, preservação e máscara funcionaram nos casos
testados. Um diretório preexistente permissivo não é corrigido para `0700`.

[NÃO VERIFICADO] Busca por regex e chunks PNG não exclui segredo sem formato nem dado
visual sensível. Uma revisão humana final dos artefatos é requisito de publicação.

## 8. GitHub readiness

**NOT READY**.

[OBSERVADO] Não há remote, então a sanitização é preventiva. Não existem LICENSE,
SECURITY, CONTRIBUTING ou CODE_OF_CONDUCT. Sem licença, o copyright padrão não concede
permissão geral de reutilização; corpus e evidências visuais ainda exigem decisão própria.

[OBSERVADO] Há 22 caminhos `/home/ziul` em nove documentos, caminhos de backup pessoal,
e-mail nos 94 commits, 67 trailers de coautoria, 10 handoffs/prompts obsoletos e uma
auditoria histórica que ocupa 84,4% dos bytes rastreados.

[OBSERVADO] O ambiente instalado contém uma vulnerabilidade conhecida em
`cryptography`; o toolchain npm contém duas altas. O caminho criptográfico específico
não foi encontrado no produto, mas versões afetadas estão resolvidas nos lockfiles.

[INFERIDO] A lista exata e ordenada está em `ANE_GITHUB_SANITIZATION.md`. Enquanto os
itens bloqueadores não forem fechados e rechecados, “ready after sanitation” sugeriria
um estado mais próximo da publicação do que a evidência permite.

## 9. Alpha readiness

**HOLD**.

[OBSERVADO] Passam corpus estrutural, gates, render real e opt-in de demo. Falham o
fluxo de promoção, honestidade, segurança de entrada, robustez, observabilidade e
configuração; validação corpus→cena é parcial.

[INFERIDO] A decisão decorre da regra fixada antes dos resultados em
`ANE_ALPHA_GATE.md`; não é média subjetiva entre itens verdes e vermelhos.

## 10. Achados

[OBSERVADO] Não há achado P0. Os achados seguem em ordem de severidade e impacto.

### F-01 — Credencial candidata pode voltar integralmente pela API

- **ID:** F-01
- **Severidade:** P1
- **Domínio:** segurança
- **Rótulo:** OBSERVADO
- **Descrição:** o handler 422 e uma exceção de adapter podem refletir a candidata que a rota promete nunca devolver.
- **Evidência:** TestClient isolado: `422`, `candidate_full_in_response=True`, `input_length=513`; adapter falso: `candidate_prefix_in_detail=True`.
- **Arquivos:** `control/models.py:136-143`; `control/routes.py:153-178,196-208`; `config.py:25-27,103-126`.
- **Reprodução:** enviar `key` sintética com 513 caracteres; depois testar candidata de até 512 com adapter falso que a inclui na exceção; procurar a sequência nas respostas.
- **Impacto:** um segredo real digitado pode aparecer em resposta HTTP, log de proxy, DevTools ou telemetria de erro.
- **Probabilidade:** alta para erro de comprimento; condicionada a SDK/adapter ecoar entrada no segundo caminho.
- **Consequência:** quebra explícita do invariante de segredo e bloqueio de Alpha/publicação.
- **Recomendação:** handler de validação que remova `input`; `SecretStr`/modelo seguro; redigir também pela candidata em memória; testar todos os provedores.
- **Fechamento:** testes provam que nenhum corpo 4xx/5xx, detalhe, log ou traceback contém candidata integral ou fragmento não permitido.

### F-02 — O Promoter elimina o veto estrutural ao recomputar quórum

- **ID:** F-02
- **Severidade:** P1
- **Domínio:** quórum
- **Rótulo:** OBSERVADO
- **Descrição:** `verify_quorum` chama o engine sem as falhas estruturais que produziram `reject`.
- **Evidência:** painel real `15b0dfb87750`: persistido `reject` com 3 falhas; recomputado `promote`, 3 votos/2 provedores/3 famílias.
- **Arquivos:** `work/orchestrator.py:639,1120`; `quorum/engine.py:66-86`; `promotion/promoter.py:104-143`.
- **Reprodução:** carregar o painel e comparar `panel.decision` com `decide_panel(panel)`.
- **Impacto:** conteúdo objetivamente inválido pode atravessar a última guarda se um futuro painel equivalente tiver patch.
- **Probabilidade:** média; os artefatos já contêm a configuração lógica, embora esse painel não tenha patch.
- **Consequência:** bypass da regra central de governança do corpus.
- **Recomendação:** persistir/rederivar as falhas canônicas, comparar decisão integral e recusar divergência.
- **Fechamento:** painel com votos favoráveis e qualquer falha estrutural é recusado pelo Promoter; decisão persistida e recomputada são equivalentes.

### F-03 — Alvos Unicode reais não passam pelo Promoter

- **ID:** F-03
- **Severidade:** P1
- **Domínio:** quórum
- **Rótulo:** OBSERVADO
- **Descrição:** nomes Git escapados são comparados como texto com caminhos Unicode declarados.
- **Evidência:** clone temporário de `Índice.md` recusou `"knowledge/\\303\\215ndice.md"` contra `knowledge/Índice.md`; controle ASCII promoveu.
- **Arquivos:** `promotion/promoter.py:328-335`.
- **Reprodução:** promover patch aprovado para um alvo acentuado com `core.quotePath` padrão.
- **Impacto:** os nove patches reais, todos com alvos não ASCII, não são promovíveis pelo caminho implementado.
- **Probabilidade:** certa nos artefatos atuais caso alcancem aprovação.
- **Consequência:** a governança não entrega o corpus real apesar de gates verdes.
- **Recomendação:** usar saída NUL/raw (`-z`) ou desabilitar quoting e comparar paths como bytes/Path normalizados.
- **Fechamento:** testes Linux com todos os nove alvos reais e nomes Unicode variados passam sem relaxar escopo do diff.

### F-04 — Crash pós-fast-forward deixa promoção sem procedência

- **ID:** F-04
- **Severidade:** P1
- **Domínio:** arquitetura
- **Rótulo:** OBSERVADO
- **Descrição:** o Git avança antes do evento final e de `promotion.json`, sem journal/recovery.
- **Evidência:** RuntimeError e `os._exit(86)` injetados após merge deixaram HEAD/conteúdo avançados; o primeiro registrou `refused`, o segundo deixou worktree e nenhum artefato.
- **Arquivos:** `promotion/promoter.py:224-265,285-310`; `tools/promote.py:104-111`.
- **Reprodução:** em clone temporário, interromper `emit('corpus_changed')` após o `merge --ff-only`.
- **Impacto:** corpus e trilha de procedência discordam; retry pode interpretar promoção concluída como ausente.
- **Probabilidade:** baixa por execução, inevitável ao longo do tempo sem recovery para SIGKILL/queda de energia.
- **Consequência:** auditoria não consegue provar quem aprovou uma mudança já canônica.
- **Recomendação:** journal durável antes do merge, promoção idempotente e reconciliação de startup entre HEAD, commit candidato e artefato.
- **Fechamento:** crash em cada ponto de injeção converge, após restart, para exatamente “não promovido” ou “promovido com procedência completa”, sem worktree órfã.

### F-05 — O painel de workers grava preferências que a execução não lê

- **ID:** F-05
- **Severidade:** P1
- **Domínio:** provedores
- **Rótulo:** OBSERVADO
- **Descrição:** AUTO, enable, provedor, modelo, reasoning e concorrência governam apenas `control.json`/snapshot.
- **Evidência:** busca de `PreferenceStore|ControlPreferences|control.json` encontra consumidores somente em `vault/control`; runner fixa concurrency 1.
- **Arquivos:** `control/routes.py:75-117`; `control/preferences.py:53`; `control/snapshot.py:177-204`; `tools/run_worker.py:184`.
- **Reprodução:** PATCH AUTO/worker em runtime temporário e executar planner; seleção/cadência permanecem iguais.
- **Impacto:** o operador acredita ter parado ou reconfigurado trabalho externo sem efeito real.
- **Probabilidade:** certa ao usar qualquer controle operacional.
- **Consequência:** custo, provedor, diversidade e comportamento podem divergir da UI.
- **Recomendação:** tornar preferências entrada canônica do claim/planner/adapters ou rotular/remover controles simulados.
- **Fechamento:** testes ponta a ponta mostram cada mutação alterando a próxima alocação; snapshot distingue preferência, plano e processo vivo.

### F-06 — “Promote” autônomo termina a tarefa sem promover

- **ID:** F-06
- **Severidade:** P1
- **Domínio:** arquitetura
- **Rótulo:** OBSERVADO
- **Descrição:** o worker converte veredito `promote` em `completed`, mas nunca chama `ProposalPromoter`.
- **Evidência:** `worker.py:213-221,428-494`; apenas `tools/promote.py:104-111` chama e persiste a promoção; zero `promotion.json`.
- **Arquivos:** `autonomy/worker.py:213-221,428-494`; `tools/promote.py:104-111`; `proposals/store.py`.
- **Reprodução:** seguir o retorno de `OrchestratedTaskExecutor` até `_transition`; procurar chamada de Promoter no caminho do worker.
- **Impacto:** fila afirma conclusão enquanto corpus não muda; `/proposals` continua vazio por ser store legado.
- **Probabilidade:** certa para decisão autônoma `promote`.
- **Consequência:** o produto central não é entregue e o estado oculta a pendência.
- **Recomendação:** estado durável `approved_pending_promotion` ou promoção integrada, idempotente; remover/unificar ProposalStore legado.
- **Fechamento:** um ensaio isolado completo termina com commit canônico, `promotion.json`, eventos e estado de fila coerentes; falha termina explicitamente pendente/recusada.

### F-07 — O mesmo modelo hospedado pode contar como dois votos independentes

- **ID:** F-07
- **Severidade:** P1
- **Domínio:** quórum
- **Rótulo:** OBSERVADO
- **Descrição:** identidade é `provider/endpoint`, não identidade canônica de pesos/modelo; família heurística influencia governança.
- **Evidência:** Groq e NVIDIA com `openai/gpt-oss-120b` mais Qwen produziram `promote`, 3 votos, 2 providers, 2 families.
- **Arquivos:** `quorum/models.py:75`; `providers/registry.py:73`; `providers/base.py:264`; `quorum/engine.py:19,58-59`; `work/orchestrator.py:1159`.
- **Reprodução:** criar três `ParseResult` aprovando com os endpoints acima e chamar `decide_panel`.
- **Impacto:** redundância de hospedagem é confundida com independência epistêmica.
- **Probabilidade:** real; os mesmos IDs aparecem nos catálogos de dois provedores.
- **Consequência:** quórum pode ser satisfeito por duas cópias do mesmo modelo.
- **Recomendação:** identidade canônica curada dos pesos e limite de um voto por identidade; taxonomia de família versionada.
- **Fechamento:** duplicata cross-provider é recusada/colapsada e testes cobrem aliases e forks conhecidos.

### F-08 — Crash de worker duplicou chamadas e abandonou painel

- **ID:** F-08
- **Severidade:** P1
- **Domínio:** runtime
- **Rótulo:** OBSERVADO
- **Descrição:** efeito externo precede checkpoint, e recovery reabre a tarefa sem panel/endpoints/ledger suficientes para retomar.
- **Evidência:** tarefa `aut-8349e507b41388463a4e` abriu `e626137bd0cb`, morreu após `call_started` NVIDIA e no restart abriu `9999849aff4b`, repetindo quatro endpoints.
- **Arquivos:** `autonomy/worker.py:169-190`; `autonomy/queue.py:126-155`; `tools/run_worker.py:197-210`.
- **Reprodução:** correlacionar fila, `events.jsonl` e os dois painéis; ou SIGKILL após uma chamada em runtime temporário.
- **Impacto:** consumo duplicado, painel órfão, ledger subcontado e ausência de continuidade deliberativa.
- **Probabilidade:** observada uma vez em 189 inícios; qualquer queda na janela repete.
- **Consequência:** custo e evidência operacional não são exatamente atribuíveis.
- **Recomendação:** checkpoint por chamada, ledger incremental, chave idempotente e retomada do painel existente.
- **Fechamento:** matriz de crashes prova nenhuma chamada duplicada sem marca explícita e recuperação do mesmo panel ID.

### F-09 — Snapshot SSE pode avançar o cursor além do último evento enviado

- **ID:** F-09
- **Severidade:** P1
- **Domínio:** runtime
- **Rótulo:** OBSERVADO
- **Descrição:** eventos e revisão são lidos separadamente; append intermediário cria perda permanente para o cliente.
- **Evidência:** snapshot declarou revisão 2 contendo só evento 1; replay após cursor 2 ficou vazio embora evento 2 não tivesse sido enviado.
- **Arquivos:** `events/bus.py:68-74`; `app.py:216-235`.
- **Reprodução:** store temporário, monkeypatch/gancho entre `read` e `latest_revision`, append evento 2, conectar/replay.
- **Impacto:** a cena pode perder transição sem saber que há lacuna.
- **Probabilidade:** pequena por conexão, aumenta com taxa de eventos/reconexões.
- **Consequência:** observabilidade visual deixa de ser reprodução fiel do log.
- **Recomendação:** snapshot/revisão sob a mesma leitura/lock; cursor igual ao último evento efetivamente enviado.
- **Fechamento:** teste concorrente repetido não produz gap; cursor e frame têm invariante formal.

### F-10 — Watcher publica corpus estruturalmente inválido

- **ID:** F-10
- **Severidade:** P1
- **Domínio:** corpus
- **Rótulo:** OBSERVADO
- **Descrição:** diagnósticos obrigatórios não impedem uma nova projeção válida aos olhos do watcher.
- **Evidência:** cópia temporária com link quebrado avançou revisão 1→2, `broken=1`, `edges=0`, `last_error=None`.
- **Arquivos:** `corpus/reader.py:340,395`; `corpus/watcher.py:122-180,258`.
- **Reprodução:** iniciar watcher em corpus mínimo válido, quebrar wikilink, chamar refresh/aguardar evento.
- **Impacto:** a cena troca conhecimento válido por estado que `make audit` rejeitaria.
- **Probabilidade:** alta durante edição incompleta ou falha de escrita em vários arquivos.
- **Consequência:** interface representa corrupção transitória como atualização canônica bem-sucedida.
- **Recomendação:** gate estrutural antes de publish e conservação explícita da última projeção válida.
- **Fechamento:** mutações inválidas produzem erro diagnosticável, nenhuma revisão nova e projeção anterior byte a byte intacta.

### F-11 — Atalhos globais interceptam o campo de credencial

- **ID:** F-11
- **Severidade:** P1
- **Domínio:** atlas
- **Rótulo:** OBSERVADO
- **Descrição:** WASD/G são tratados sem excluir `input`, `select` ou elemento editável.
- **Evidência:** `onKeyDown` global não consulta `event.target`; o dock usa input de segredo real.
- **Arquivos:** `frontend/src/atlas.ts:1615-1627`; `frontend/src/dock.ts:234-245`.
- **Reprodução:** focar o campo de chave e digitar candidata sintética contendo `w`, `a`, `s`, `d` ou `g`.
- **Impacto:** a candidata pode ser truncada/corrompida e a câmera se move enquanto o operador configura segurança.
- **Probabilidade:** alta; os alfabetos de chaves reais incluem essas letras.
- **Consequência:** credencial válida pode ser persistida incorretamente, gerando diagnóstico falso.
- **Recomendação:** ignorar atalhos quando o alvo/ancestral for editável e testar composição, paste e acessibilidade.
- **Fechamento:** digitação/paste de todas as teclas de atalho preserva o valor byte a byte e não altera a câmera.

### F-12 — Atualização SSE rompe a seleção runtime sem limpar o estado superior

- **ID:** F-12
- **Severidade:** P1
- **Domínio:** atlas
- **Rótulo:** OBSERVADO
- **Descrição:** a camada viva destrói/recria objetos e zera seleção, enquanto `runtimeSelected` permanece.
- **Evidência:** `runtimeLayer.update/clear` zera `selecionado`; `atlas.updateRuntime` não reaplica `setSelected`; Enter/Esc consultam só corpus.
- **Arquivos:** `frontend/src/runtimeLayer.ts:527-544`; `frontend/src/atlas.ts:1410-1436,1629-1637,2172-2179`; `main.ts:423-430`.
- **Reprodução:** selecionar evento runtime, entregar próximo frame SSE, observar placa perder expansão/elevação e usar Enter/Esc.
- **Impacto:** texto/halo/estado lógico e corpo visível discordam; Esc pode abrir dock com evento ainda selecionado.
- **Probabilidade:** certa no próximo evento após seleção.
- **Consequência:** navegação operacional não é confiável em sistema vivo.
- **Recomendação:** preservar identidade/objetos ou reaplicar seleção atomicamente; unificar comandos para corpus/runtime.
- **Fechamento:** seleção sobrevive updates do mesmo ID, é limpa se o ID sai e Enter/Esc têm semântica única testada.

### F-13 — Dois escritores disputam a ênfase do corpus

- **ID:** F-13
- **Severidade:** P1
- **Domínio:** atlas
- **Rótulo:** OBSERVADO
- **Descrição:** foco/hover e vínculo runtime sobrescrevem todos os slots na ordem de eventos.
- **Evidência:** `aplicarEnfase` e `acenderOutraPonta` percorrem todos os corpos; hover e snapshot chamam o primeiro depois do segundo.
- **Arquivos:** `frontend/src/atlas.ts:754-772,1436-1457,1815-1824,2172-2179`.
- **Reprodução:** selecionar runtime ligado a entidade, depois mover hover ou receber SSE; observar a outra ponta apagar com seleção lógica ativa.
- **Impacto:** o vínculo operacional mais importante pisca/desaparece sem ação semântica.
- **Probabilidade:** alta em sessão viva.
- **Consequência:** a cena mente sobre qual entidade o evento toca.
- **Recomendação:** estado de ênfase composto em uma única função, com prioridades explícitas e razões independentes.
- **Fechamento:** testes de todas as ordens de evento produzem o mesmo vetor de ênfase e captura viva confirma estabilidade.

### F-14 — Runtime chega depois do único enquadramento automático

- **ID:** F-14
- **Severidade:** P1
- **Domínio:** atlas
- **Rótulo:** OBSERVADO
- **Descrição:** startup enquadra a projeção antes de assinar SSE e não reenquadra a geometria adicionada.
- **Evidência:** captura inicial corta topo de Modelos/Provedores; G/refit mostra o conjunto; ordem em `main.ts:367,392`.
- **Arquivos:** `frontend/src/main.ts:367,392`; `frontend/src/atlas.ts:2172-2179`.
- **Reprodução:** abrir Atlas limpo, aguardar primeiro snapshot runtime, comparar com quadro após G.
- **Impacto:** primeira impressão omite parte do sistema e reintroduz F-11 visual da auditoria anterior.
- **Probabilidade:** certa quando runtime expande bounds após startup.
- **Consequência:** usuário interpreta corte como ausência ou layout defeituoso.
- **Recomendação:** primeiro fit após corpus+primeiro snapshot, ou fit transitório delimitado sem roubar câmera do usuário.
- **Fechamento:** captura automática inicial contém bounds ativos e updates posteriores não movem câmera após interação.

### F-15 — Pool de texto vaza títulos e sua telemetria subconta pela metade

- **ID:** F-15
- **Severidade:** P1
- **Domínio:** performance
- **Rótulo:** OBSERVADO
- **Descrição:** cada slot cria corpo+título, mas dispose e contadores acompanham só corpo.
- **Evidência:** 640 slots criam 1.280 `Text`; `dispose` chama somente `slot.text.dispose`; harness fixa `criados=slots.length`.
- **Arquivos:** `frontend/src/textPool.ts:41`; `panelTextRenderer.ts:249-280,281,533-553`; `harness.ts:40-43,170-174`.
- **Reprodução:** criar/dispor renderer, instrumentar `Text.dispose` para corpo e título; comparar alocações com métricas.
- **Impacto:** leak de recursos e falsa garantia de que navegação não aloca texto.
- **Probabilidade:** certa em dispose/HMR; crescimento em sessão normal depende do lifecycle.
- **Consequência:** memória/GPU pode crescer e a própria telemetria não alerta.
- **Recomendação:** liberar ambos, contar objetos reais e testar criação/destruição por identidade.
- **Fechamento:** contadores igualam alocações físicas, todos os Text são dispostos uma vez e perfil longo estabiliza.

### F-16 — Decisão por síntese não é revalidável pelo Promoter

- **ID:** F-16
- **Severidade:** P2
- **Domínio:** quórum
- **Rótulo:** OBSERVADO
- **Descrição:** árbitro externo produz `decided/promote`, mas `load_panel` o exclui e o Promoter recomputa o empate original.
- **Evidência:** ensaio em memória: persistível `decided promote`; `verify_quorum` recusa “nenhuma decisão obteve maioria simples”.
- **Arquivos:** `quorum/synthesis.py:17-57`; `quorum/store.py:153-189`; `promotion/promoter.py:128`.
- **Reprodução:** painel 1-1-1, voto válido de árbitro externo, salvar/carregar e verificar.
- **Impacto:** caminho documentado de desempate não pode terminar em promoção.
- **Probabilidade:** baixa/média; ocorre em empates que a síntese resolve por promote.
- **Consequência:** decisão canônica e guarda final divergem.
- **Recomendação:** tornar arbitragem parte persistível/recomputável do contrato e vinculá-la ao patch.
- **Fechamento:** round-trip de síntese mantém decisão e passa/recusa Promoter de modo determinístico.

### F-17 — `promote --dry-run` não executa as guardas que anuncia

- **ID:** F-17
- **Severidade:** P2
- **Domínio:** docs
- **Rótulo:** OBSERVADO
- **Descrição:** a ajuda promete base, audit e worktree, mas o código só verifica quórum e imprime commits.
- **Evidência:** contraste entre `tools/promote.py:2-9,35-38` e `:93-102`.
- **Arquivos:** `tools/promote.py:2-9,35-38,93-102`.
- **Reprodução:** usar patch com base divergente/Unicode e quórum válido; dry-run não alcança a falha real.
- **Impacto:** operador recebe falsa aprovação antes de executar ação canônica.
- **Probabilidade:** certa ao confiar no dry-run.
- **Consequência:** janela de manutenção falha no comando real por problema que o ensaio prometia detectar.
- **Recomendação:** executar pipeline completo em worktree sem merge ou reduzir nome/ajuda à verificação real.
- **Fechamento:** cada guarda real tem caso que falha identicamente no dry-run, exceto o avanço de HEAD.

### F-18 — O gate estrutural aceita status, campos e identificadores inválidos

- **ID:** F-18
- **Severidade:** P2
- **Domínio:** corpus
- **Rótulo:** OBSERVADO
- **Descrição:** regras normativas de frontmatter/status/fonte não são impostas por `audit.py`.
- **Evidência:** cópia com `title` ausente, `invented-status` e DOI falso ainda saiu 0/APROVADO.
- **Arquivos:** `tools/audit.py:1-260`; `AGENTS.md`; `knowledge/Política Epistêmica e de Linkagem.md`.
- **Reprodução:** fazer as três mutações em cópia e executar `python3 tools/audit.py COPIA`.
- **Impacto:** gate verde pode acompanhar metadados e afirmações fora do vocabulário.
- **Probabilidade:** média em edição humana/modelo; identificador plausível errado é indetectável por desenho atual.
- **Consequência:** aprovação estrutural pode ser interpretada como garantia epistemológica indevida.
- **Recomendação:** separar nominalmente os níveis e adicionar validações determinísticas possíveis; manter verificação científica humana/independente.
- **Fechamento:** testes negativos cobrem campos/status; resolução/título têm gate próprio ou estado explicitamente não verificado.

### F-19 — 403 é colapsado em “credencial inválida”

- **ID:** F-19
- **Severidade:** P2
- **Domínio:** provedores
- **Rótulo:** OBSERVADO
- **Descrição:** negação de acesso a modelo/plano é apresentada como falha de autenticação.
- **Evidência:** Google agrupa 401/403; Groq/NVIDIA agrupam auth/permission; `_probe` procura `403` e retorna `invalido`; Ollama separa.
- **Arquivos:** `providers/google/adapter.py:57`; adapters Groq/NVIDIA; `control/routes.py:169-178`; `providers/ollama/adapter.py:102`.
- **Reprodução:** adapter falso retorna permission denied/403 com chave sintética e inspecionar status.
- **Impacto:** operador rotaciona chave correta em vez de trocar modelo/plano.
- **Probabilidade:** comum quando catálogo lista modelo sem acesso contratado.
- **Consequência:** diagnóstico e remediação errados.
- **Recomendação:** estado `sem_permissao/fora_do_plano`; só 401 sustenta “inválida”.
- **Fechamento:** matriz 401/403/404/429/5xx gera estados distintos e iguais nos quatro provedores.

### F-20 — Contratos de rede são parcialmente confiados por cast

- **ID:** F-20
- **Severidade:** P2
- **Domínio:** arquitetura
- **Rótulo:** OBSERVADO
- **Descrição:** payload plausível, mas fora do contrato, pode entrar na cena/dock sem validação estrutural completa.
- **Evidência:** `loadProjection` e `pedir<T>` retornam casts; backend de projeção não tem response model.
- **Arquivos:** `frontend/src/contract.ts:222-255,497-512`; `controlApi.ts:102-124`; `backend/src/vault/app.py:156`.
- **Reprodução:** servir arrays/tipos/enums/IDs duplicados inválidos que preservem major do contrato.
- **Impacto:** erro backend vira mentira visual ou exceção distante sem causa contextual.
- **Probabilidade:** média durante evolução independente de Python/TypeScript.
- **Consequência:** deriva de contrato sobrevive ao typecheck.
- **Recomendação:** schema runtime compartilhado/versionado e validação na fronteira, com última projeção válida.
- **Fechamento:** corpus de payloads inválidos falha antes da cena com diagnóstico de path e nenhum estado parcial.

### F-21 — Origem fixa e fallback silencioso limitam instalação e honestidade

- **ID:** F-21
- **Severidade:** P2
- **Domínio:** arquitetura
- **Rótulo:** OBSERVADO
- **Descrição:** quatro módulos embutem localhost:8000; sem backend o Atlas usa snapshot real estático e falha runtime silenciosamente.
- **Evidência:** literais em `controlApi.ts`, `contract.ts`, `layoutStore.ts`, `runtime.ts`; watcher só liga para origem backend.
- **Arquivos:** `frontend/src/controlApi.ts:18`; `contract.ts:419-420`; `layoutStore.ts:14`; `runtime.ts:95,316-353`; `main.ts:173-193`.
- **Reprodução:** servir frontend em host/porta distintos, desligar backend e observar fallback congelado/ausência runtime.
- **Impacto:** terceiro precisa editar código; Atlas pode parecer completo com dados velhos.
- **Probabilidade:** certa fora do layout local previsto.
- **Consequência:** publicação não é instalável/configurável como produto.
- **Recomendação:** origem configurável, indicador persistente de modo estático/offline e retry/timeout observável.
- **Fechamento:** deploy em origem arbitrária funciona só por config; perda/recovery backend aparece na UI e atualiza sem reload.

### F-22 — Superfície de controle e documentação carregam funções removidas

- **ID:** F-22
- **Severidade:** P2
- **Domínio:** docs
- **Rótulo:** OBSERVADO
- **Descrição:** UI anuncia L/F/M, código legado continua exportado e dock oculto mantém polling agressivo.
- **Evidência:** `CONTROLS` só tem G; mensagem anuncia L/F/M/G; `controlBar.ts` e APIs de camada não têm consumidor; 146 polls a ~2,5 s com `dock--oculto`.
- **Arquivos:** `controls3d.ts:36-38,52`; `main.ts:353-380,428`; `controlBar.ts:29`; `atlas.ts:2159-2162`.
- **Reprodução:** abrir cena, pressionar L/F/M; ocultar dock e contar GETs de snapshot.
- **Impacto:** ajuda mente, código morto aumenta deriva e backend recebe carga sem usuário olhando.
- **Probabilidade:** certa.
- **Consequência:** operador perde confiança e races de resposta podem sobrescrever estado novo.
- **Recomendação:** remover/restaurar controles de forma coerente; pausar polling oculto; serializar/abortar requests.
- **Fechamento:** toda ação anunciada tem efeito testado; zero API pública órfã; dock oculto não faz polling curto.

### F-23 — Observabilidade termina antes de fronteiras críticas

- **ID:** F-23
- **Severidade:** P2
- **Domínio:** runtime
- **Rótulo:** OBSERVADO
- **Descrição:** rota manual não emite eventos, recorder é best-effort, health omite worker/watcher e falhas são strings.
- **Evidência:** `tools/run_work.py` não instancia recorder; `/health` só expõe versão/corpus/credentials; `operation.failures` é `list[str]`.
- **Arquivos:** `tools/run_work.py:78-130`; `events/recorder.py:18-45`; `app.py:97`; `control/models.py:95-107`.
- **Reprodução:** executar caminho manual em runtime temporário e comparar event log; inspecionar health/snapshot.
- **Impacto:** incidente não é correlacionável entre tarefa, tentativa, painel, endpoint, custo e cena.
- **Probabilidade:** alta em falhas reais.
- **Consequência:** diagnóstico depende de reconstrução forense manual.
- **Recomendação:** IDs estruturados comuns, health de componentes, falhas tipadas/agregadas e evento obrigatório em todos os runners.
- **Fechamento:** uma falha injetada é rastreável ponta a ponta por um ID e health acusa componente degradado.

### F-24 — Dependências resolvidas incluem três vulnerabilidades conhecidas

- **ID:** F-24
- **Severidade:** P2
- **Domínio:** dependências
- **Rótulo:** OBSERVADO
- **Descrição:** lock/ambiente contêm `cryptography 49.0.0`, `brace-expansion 5.0.8` e `nanoid 3.3.16` em faixas afetadas.
- **Evidência:** `pip-audit` encontrou PYSEC-2026-3552; `pnpm audit` encontrou duas altas; versões corrigidas 50.0.0, 5.0.9 e 3.3.17.
- **Arquivos:** `uv.lock:242-248`; `frontend/pnpm-lock.yaml`.
- **Reprodução:** `uv run --with pip-audit pip-audit`; `cd frontend && pnpm audit --json`.
- **Impacto:** supply chain pública parte de versões conhecidamente afetadas; o CVE Python exige uso PKCS#7 não encontrado no app.
- **Probabilidade:** baixa para exploração observada de cryptography; advisories npm afetam toolchain.
- **Consequência:** alerta de segurança e risco evitável no build/ambiente.
- **Recomendação:** atualizar lockfiles, revisar breaking changes e repetir audit/test/lint.
- **Fechamento:** scanners retornam zero vulnerabilidade conhecida aplicável e gates permanecem verdes.

### F-25 — O repositório não tem licença nem fronteira pública definida

- **ID:** F-25
- **Severidade:** P2
- **Domínio:** higiene
- **Rótulo:** OBSERVADO
- **Descrição:** software, corpus e evidências não têm licença/proveniência separadas; documentos pessoais/históricos dominam o pacote.
- **Evidência:** ausência de LICENSE/SECURITY/CONTRIBUTING; 22 paths pessoais; auditoria antiga 84,4% dos bytes rastreados; asset sem NOTICE.
- **Arquivos:** raiz; `docs/`; `docs/audits/2026-08-05-atlas-geral/`; `tools/atlas.svg`.
- **Reprodução:** `find` dos arquivos de publicação, `rg -l '/home/ziul'`, soma de bytes rastreados.
- **Impacto:** terceiros não recebem permissão clara e a publicação expõe contexto pessoal desnecessário.
- **Probabilidade:** certa em push público do estado atual.
- **Consequência:** risco jurídico, privacidade e clone inflado.
- **Recomendação:** licenças separadas, políticas públicas, sanitização e artefatos pesados fora do histórico principal.
- **Fechamento:** revisão jurídica/autoral documentada, arquivos públicos mínimos e scan final aprovado.

### F-26 — Escrita privada não corrige diretório permissivo preexistente

- **ID:** F-26
- **Severidade:** P3
- **Domínio:** segurança
- **Rótulo:** OBSERVADO
- **Descrição:** `mkdir(mode=0700, exist_ok=True)` não aplica chmod a diretório já existente.
- **Evidência:** ensaio em `/tmp`: arquivo `0600`, diretório permaneceu `0755`.
- **Arquivos:** `control/atomic.py:21-48`.
- **Reprodução:** criar parent `0755`, chamar `write_atomic`, medir `stat.S_IMODE`.
- **Impacto:** nomes/metadados/temporários podem ficar enumeráveis por outros usuários locais, conforme permissões do sistema.
- **Probabilidade:** depende de instalação em diretório já criado permissivamente.
- **Consequência:** proteção declarada do diretório não se cumpre.
- **Recomendação:** validar/corrigir mode do parent ou recusar com diagnóstico, respeitando política explícita.
- **Fechamento:** teste com parents novos e existentes resulta em política documentada e mode esperado.

## 11. Inventário de dívida

- **Bloqueadora:** [INFERIDO] F-01 a F-10 e F-11 a F-15 impedem Alpha por violarem
  segurança, governança, entrega ponta a ponta, recuperação ou fidelidade viva.
- **Alta:** [INFERIDO] F-16 a F-21 e F-23 precisam cair antes de uma Alpha distribuível;
  ampliam a mesma superfície, mas não demonstram perda imediata por si sós.
- **Média:** [INFERIDO] F-22, F-24 e F-25 cabem numa fase de estabilização/publicação,
  desde que concluídas antes do primeiro push público.
- **Baixa:** [INFERIDO] F-26 e lifecycle HMR/picking secundário podem entrar no backlog
  depois das invariantes críticas.

## 12. Riscos agregados

- [INFERIDO] **Epistemológico:** uma decisão que deveria ser veto pode virar promote e
  independência de modelos pode ser supercontada.
- [INFERIDO] **Transacional:** chamadas e commits ocorrem antes da prova durável do
  efeito, deixando retries ambíguos.
- [INFERIDO] **Representacional:** cena e painel retêm estados convincentes que não
  correspondem à execução ou ao lifecycle atual.
- [INFERIDO] **Segurança:** entrada secreta pode escapar antes/depois da lógica de
  armazenamento que, isoladamente, é cuidadosa.
- [INFERIDO] **Publicação:** licença ausente, documentos históricos, identidade e assets
  sem proveniência tornam push prematuro.

## 13. Recomendações priorizadas

1. [INFERIDO] Fechar F-01 com testes de resposta/log antes de qualquer uso real do dock.
2. [INFERIDO] Definir uma decisão canônica verificável pelo Promoter: falhas estruturais,
   síntese e identidade de modelo fazem parte do artefato assinado/recomputado.
3. [INFERIDO] Tornar promoção crash-consistente e Unicode-safe; depois integrar o worker
   com estado `pending_promotion` e demonstrar um E2E em clone.
4. [INFERIDO] Fazer preferências governarem o planner ou retirar a aparência de controle;
   diferenciar processo vivo, preferência e plano.
5. [INFERIDO] Tornar efeitos externos recuperáveis por checkpoint/idempotência e corrigir
   o snapshot SSE/watcher antes de confiar na trilha viva.
6. [INFERIDO] Unificar estado visual de seleção/ênfase, proteger inputs dos atalhos,
   corrigir pool e reenquadramento; validar em cena GPU real.
7. [INFERIDO] Validar contratos em runtime, configurar origem do backend e tornar modo
   offline explícito.
8. [INFERIDO] Só então atualizar dependências, documentação, licenças e sanitização para
   preparar a publicação.

## 14. Decisão final

[INFERIDO] **A.N.E. hoje é um protótipo integrado forte, não uma Alpha confiável.** O
corpus, a projeção, a deliberação e a cena existem; a falha está nas juntas que deveriam
transformar esses subsistemas em um único sistema governado e recuperável.

[INFERIDO] **Alpha: HOLD. GitHub: NOT READY.** Um novo gate pode ser aberto quando F-01 a
F-15 tiverem fechamento objetivo e um clone isolado demonstrar proposta→quórum→promoção
com crash recovery e caminho Unicode.

## 15. Regressão contra a auditoria de 2026-08-05

| Achado anterior | Estado atual | Evidência |
| --- | --- | --- |
| F-01 zoom/minDistance | [NÃO VERIFICADO] Corrigido estaticamente; não revalidado por gesto vivo | guarda dinâmica presente; captura não exerceu limite |
| F-02 arestas recíprocas coincidentes | [OBSERVADO] Corrigido em código/teste | registry por par não ordenado |
| F-03 agregadas dirigidas duplicadas | [OBSERVADO] Corrigido/testado; visual agregado depois removido | 75→52 no fechamento histórico; caminho atual diferente |
| F-04 runtime desloca MOCs | [OBSERVADO] Corrigido e testado até 1.000 operações | coordenadas compostas independentes |
| F-05 floresta wireframe | [OBSERVADO] Corrigido; não reapareceu na captura atual | cena viva nova |
| F-06 nuvem operacional sem ontologia | [OBSERVADO] Corrigido, arquitetura visual mudou | nuvens separadas e zero overlap de esferas |
| F-07 aba workers ≠ execução | [OBSERVADO] Não corrigido e ampliado | F-05 atual |
| F-08 fila parada/mensagem errada | [OBSERVADO] Parcial | fila voltou a executar; texto de diversidade permanece impreciso |
| F-09 falhas texto puro | [OBSERVADO] Não corrigido | `OperationState.failures: list[str]` |
| F-10 texto cortado | [NÃO VERIFICADO] Correção estática/teste; cena não revalidada | instrumento não focou caso |
| F-11 operacional domina fit | [OBSERVADO] Reintroduzido | captura antes/depois de G; F-14 atual |
| F-12 espinha+famílias | [OBSERVADO] Reintroduzido por `d141ba7` | famílias permanentes/camada todas |
| F-13 runtime ignora filtro | [OBSERVADO] Encerrado por remoção do filtro; docs defasadas | L/F/M sem função |
| F-14 deliberação não chega à cena | [OBSERVADO] Parcial | nós/painéis chegam; progressão/seleção viva falham |

[OBSERVADO] Fechamento 3.5-A está parcial/regredido; 3.5-B é histórico/parcial; 3.5-C
preserva registries, mas regrediu orçamento visual; 3.5-D está majoritariamente
preservado, sem progressão ao vivo completa.

## Apêndice A — classificação de cada documento

[OBSERVADO] “Publicar” abaixo significa integrar ao produto público principal; evidência
histórica pode ser preservada fora do histórico principal depois de sanitizada.

| Arquivo(s) | Classe | Publicação |
| --- | --- | --- |
| `README.md` | [OBSERVADO] contraditório/parcialmente atual | Não antes de reescrever contagens, controles e instalação |
| `AGENTS.md` | [OBSERVADO] normativo, com conflito de governança | Só após reconciliar revisão/promoção |
| `CLAUDE.md` | [OBSERVADO] normativo; symlink de `AGENTS.md` | Mesmo destino |
| `.env.example` | [OBSERVADO] atual, sem valores | Sim |
| `knowledge/Índice.md` | [OBSERVADO] normativo, metadados quantitativos datados | Após licença/revisão autoral |
| `knowledge/Política Epistêmica e de Linkagem.md` | [OBSERVADO] normativo, contraditório com AGENTS em revisão humana | Bloqueado até decisão de governança |
| `docs/ADR-001-paleta-oklch.md` | [OBSERVADO] normativo/atual | Sim |
| `docs/ADR-002-painel-como-no.md` | [OBSERVADO] parcialmente atual | Atualizar ou marcar superseded |
| `docs/BOOTSTRAP-2026-07-30.md` | [OBSERVADO] histórico com dados pessoais | Não sem sanitização |
| `docs/CICLO-1-ATLAS-FULL-3D-2026-08-02.md` | [OBSERVADO] histórico | Só em arquivo histórico sanitizado |
| `docs/CICLO-1.1-FECHAMENTO-ATLAS-2026-08-02.md` | [OBSERVADO] histórico | Só em arquivo histórico sanitizado |
| `docs/CICLO-2-WATCHER-E-PROVEDORES-2026-08-02.md` | [OBSERVADO] histórico/parcial | Sanitizar paths e marcar data |
| `docs/CICLO-2.1-CONTINUIDADE-ESPACIAL-2026-08-02.md` | [OBSERVADO] histórico | Só em arquivo histórico |
| `docs/GOOGLE-WORKSPACE.md` | [OBSERVADO] atual/parcial | Substituir caminhos pessoais |
| `docs/HANDOFF-2026-08-02.md` | [OBSERVADO] obsoleto | Não |
| `docs/HANDOFF-CLAUDE-OPUS-5-ULTRACODE-2026-08-02.md` | [OBSERVADO] obsoleto | Não |
| `docs/HANDOFF-GPT-5.6-SOL-2026-08-02.md` | [OBSERVADO] obsoleto | Não |
| `docs/HANDOFF-GPT-5.6-SOL-ULTRA-FINALIZACAO-2026-08-04.md` | [OBSERVADO] obsoleto | Não |
| `docs/HANDOFF-GPT-SOL-5.6-2026-08-03.md` | [OBSERVADO] obsoleto | Não |
| `docs/PROMPT-A-QWEN3.8MAX-ACERVO-PROVEDORES-COTAS-2026-08-04.md` | [OBSERVADO] obsoleto/interno | Não |
| `docs/PROMPT-A-QWEN3.8MAX-AUTOCONTIDO-2026-08-04.md` | [OBSERVADO] obsoleto/interno | Não |
| `docs/PROMPT-B-GEMINI-3.6-CONFORMIDADE-E-QUORUM-2026-08-04.md` | [OBSERVADO] obsoleto/interno | Não |
| `docs/PROMPT-C-SOL-5.6-PAINEL-DE-TRABALHADORES-2026-08-04.md` | [OBSERVADO] obsoleto/interno | Não |
| `docs/PROMPT-GPT-5.6-SOL-ULTRA-FINALIZACAO-2026-08-04.md` | [OBSERVADO] obsoleto/interno | Não |
| `docs/PROMPT-AUDITORIA-MESTRE-ANE-GPT-5.6-SOL-2026-08-09.md` | [OBSERVADO] instrução atual que vira histórico; não rastreado | Não no produto |
| Auditoria 05/08: `ADENDO`, `AUDITORIA_GERAL`, `DEFECT_ORIGIN_MAP`, `FECHAMENTO-3.5-A/B/C/D`, `FINDINGS`, `FUNCTIONAL_MATRIX`, `REMEDIATION_ROADMAP` | [OBSERVADO] dez Markdown históricos | Artefato externo sanitizado |
| Auditoria 05/08: `graph-integrity`, `metrics-3.5-A/B/C`, `operational-ontology`, `performance-metrics`, `quorum-capabilities`, `runtime-snapshot.redacted`, `visual-metrics` | [OBSERVADO] nove JSON históricos | Artefato externo sanitizado |
| Auditoria 05/08 screenshots `ac-01`, `ac-02`, `ac-03`, `audit-01`, `audit-02`, `audit-03`, `audit-04`, `bc-01`, `bc-02`, `bc-03`, `bc-04` | [OBSERVADO] evidência visual histórica | Externa após revisão de privacidade/direitos |
| Auditoria 05/08 screenshots `cc-01`, `cc-02`, `cc-03`, `cc-04`, `cc-05`, `d1-01`, `d4-01`, `d4-02`, `d4-03`, `d4-04`, `d4-05` | [OBSERVADO] evidência visual histórica | Externa após revisão |
| Auditoria 05/08 screenshots `e-01`, `g-01`, `h-01`, `h-02`, `h-03`, `h-04`, `i-01`, `i-02`, `j-01`, `j-02` | [OBSERVADO] evidência visual histórica | Externa após revisão |
| `docs/audits/2026-08-05-atlas-geral.zip` | [OBSERVADO] pacote histórico ignorado | Não versionar/publicar junto |

[MEDIDO] Os três grupos de screenshots enumeram 32 arquivos rastreados; `git ls-files`
confirma esse total. A classificação não transfere licença nem declara direito de
redistribuição.
