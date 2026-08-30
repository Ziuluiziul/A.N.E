# Evidências reproduzíveis — auditoria geral do A.N.E.

## 1. Escopo, relógio e disciplina

[OBSERVADO] A coleta começou em `2026-08-09T23:37:15-03:00`, na raiz
`/home/ziul/Projetos/vault-autodidata`, e atravessou a meia-noite local. O baseline
auditado continua sendo o instantâneo de abertura de 9 de agosto; a data no caminho não
foi alterada.

[OBSERVADO] Nenhuma chamada a provedor foi disparada. O arquivo
`~/.config/vault-autodidata/secrets.env` não foi lido, escrito nem inferido. Testes com
credenciais usaram apenas sequências sintéticas em diretórios temporários.

[OBSERVADO] Nenhum arquivo preexistente foi alterado por esta auditoria. As únicas
criações no repositório são os entregáveis e o conteúdo de `ANE_AUDIT_PACKAGE/`.

## 2. Baseline forense

[OBSERVADO] O registro integral dos comandos obrigatórios — inclusive as 136 adições e
24 remoções do diff não commitado — está em
`ANE_AUDIT_PACKAGE/evidence/baseline-opening.txt` (SHA-256
`80580f6fc07ab9e53a773c1cf5d56a55db850c78ba43816760de2774bb978c0e`; a cópia
compartilhável substitui o caminho pessoal por `$REPO`).

[OBSERVADO] Resumo literal da abertura:

```text
branch        main
HEAD          61f2da448b234bde0318237965ac954c2c591c17
subject       Faz o painel do raciocínio se comportar como o do conhecimento
commits       94
tag           baseline-pos-migracao-2026-07-30
remote        [nenhuma saída]
objects       count 1398; size 20.30 MiB; in-pack 0
status        6 modificados + 1 não rastreado
```

[OBSERVADO] O status de abertura foi:

```text
 M frontend/src/atlas.ts
 M frontend/src/composeLayout.ts
 M frontend/src/main.ts
 M frontend/src/runtime.ts
 M frontend/src/runtimeLayer.test.ts
 M frontend/src/runtimeLayer.ts
?? docs/PROMPT-AUDITORIA-MESTRE-ANE-GPT-5.6-SOL-2026-08-09.md
```

[OBSERVADO] A narrativa do prompt divergia em um ponto: declarava zero não rastreados,
mas o próprio prompt já estava presente como arquivo não rastreado. Os seis modificados,
HEAD, branch, contagem de commits e diff `+136/-24` coincidiram.

## 3. Ambiente e inventário

[OBSERVADO] Versões:

```text
Python 3.13.5
uv 0.12.0
Node v24.18.1
pnpm 11.18.0
git 2.47.3
Linux 6.12.101+deb13-amd64 x86_64
```

[OBSERVADO] `.venv/` e `frontend/node_modules/` estavam presentes. `uv sync --locked
--dry-run` informou que não faria mudanças; `pnpm list` resolveu o projeto pelo lockfile.

[MEDIDO] Arquivos/linhas rastreados: `knowledge` 84/6.691; `backend/src/vault`
46/10.459; `providers` 14/2.127; `integrations/google_workspace` 2/345;
`frontend/src` 55/17.833; `tools` 13/1.764; `tests` 25/7.751; `docs` 69/61.992.
Método: `git ls-files -z CAMINHO | xargs -0 wc -l` no HEAD e working tree de abertura.

[MEDIDO] Seis módulos de produção ultrapassam 700 linhas: `atlas.ts` 2.304,
`work/orchestrator.py` 1.328, `operational.py` 1.115, `panels.ts` 832,
`runtimeLayer.ts` 718 e `operationalLayout.ts` 712.

[OBSERVADO] A árvore até profundidade 3, separação rastreado/ignorado e rankings de
tamanho estão íntegros em `ANE_REPOSITORY_INVENTORY.txt`.

## 4. Gates executados

[OBSERVADO] `make audit` saiu 0. Saída de abertura:

```text
Arquivos Markdown: 84
Documentos normativos na raiz: 2
Wikilinks: 672
Wikilinks quebrados: 0
Wikilinks sem relation: 0
Relações inválidas: 0
Notas órfãs: 0
MOCs vazios: 0
Frontmatter inválido: 0
Claims: 267
Claims únicos: 267
Claims duplicados: 0
Manifesto SHA256: e48f47915db6524005241f182cfe98a8bf108c7f6d33d47743061510193da2b3
APROVADO
```

[MEDIDO] A execução de abertura levou 0,090 s nas condições locais.

[OBSERVADO] `make test` saiu 0: 392 testes Python passaram em 12,85 s; 18 arquivos
Vitest, 302 testes TypeScript, passaram em 6,16 s; a invocação completa levou 30,370 s.

[OBSERVADO] `make lint` saiu 0: ruff passou; mypy passou em 99 arquivos-fonte; eslint
passou. A invocação completa levou 42,241 s.

[OBSERVADO] A repetição final integral, com códigos e tempos, está em
`ANE_AUDIT_PACKAGE/evidence/closing-gates.txt`. Cache de uv/XDG foi desviado para `/tmp`.

[INFERIDO] Os gates provam as asserções que executam; não provam render WebGL,
conectividade real de controles, verdade científica, recuperação de SIGKILL ou
integração com provedores.

## 5. Arquitetura reconstruída a partir do código

[OBSERVADO] Fluxo corpus→cena:
`CorpusProjectionWatcher.refresh` (`corpus/watcher.py:122`) →
`_build_stable_projection` (`watcher.py:258`) → `CorpusReader.build_graph`
(`corpus/reader.py:310`) → `build_projection` (`projection.py:269`) →
`GET /corpus/projection` (`app.py:156`) → `loadProjection`/cast parcial
(`frontend/src/contract.ts:497-512`) → `createAtlas` (`main.ts`).

[OBSERVADO] Fluxo tarefa→modelo→evento:
`AutonomousWorker.run_cycle/_run_claimed` (`autonomy/worker.py:132,169`) →
`OrchestratedTaskExecutor.__call__` (`worker.py:303`) → `plan_batch/execute/_call`
(`work/orchestrator.py:122,1184,1252`) → `adapter.generate` →
`OperationalEventRecorder` (`events/recorder.py:30`) →
`OperationalEventStore.append` (`events/store.py:161`) → SSE → camada viva.

[OBSERVADO] Fluxo proposta→quórum:
`QuorumOrchestrator.create_panel` → `parse_corpus_patch/save_patch` →
`collect_votes` → `parse_vote/save_vote` → `decide/decide_panel` →
`save_decision` (`work/orchestrator.py:304,586,639`; `quorum/parser.py:227`;
`quorum/engine.py:66`). O salto decisão→Promoter não existe no worker.

[OBSERVADO] Fluxo painel→controle:
`PATCH /auto` e `/workers` → `PreferenceStore` → `runtime/state/control.json`
(`control/routes.py:75-117`; `preferences.py:53`). `rg` não encontra consumidor de
`PreferenceStore` em `autonomy`, `work`, `run_worker` ou `run_quorum`.

[OBSERVADO] Fluxo credencial:
`PUT /providers/{id}/credential` → `write_credential` → `write_atomic`
(`routes.py:196-210`; `credentials.py:113-128`; `atomic.py:26-48`). Um novo processo lê
Settings; adapters já vivos não são reconstruídos por essa rota.

[OBSERVADO] Fluxo edição→SSE:
watcher `_watch/refresh/_publish/events` (`watcher.py:214-258`) →
`/corpus/events` (`app.py:184`). Eventos operacionais passam por
`OperationalEventBus.snapshot/wait_after` (`events/bus.py:68-74`) →
`/runtime/events` (`app.py:216`).

[OBSERVADO] O backend usa Pydantic fechado em controle, quórum, votos, eventos e patch.
A projeção retorna `dict[str, Any]`, sem `response_model`; o frontend faz cast e valida
apenas major do contrato, algumas arestas e metadados operacionais
(`contract.ts:222-255,497-512`).

[MEDIDO] `rg 'except (Exception|BaseException)'` encontrou 20 catches largos em código
de produção. `rg` encontrou zero catch TypeScript vazio. Adapters têm timeouts de 30–60
s, backoff para 429 e nenhuma repetição oculta por atribuição; worker usa retry durável de
60/300 s entre tentativas.

[OBSERVADO] Limites codificados: 64.000 bytes/evento, profundidade JSON 8, 256 itens por
coleção, 4.000 caracteres/texto, 2.000 eventos por snapshot e 160 eventos na cena. Não há
compactação do log operacional nem teto global observado de nós da projeção.

[NÃO VERIFICADO] Não foi produzido um grafo formal completo de imports para provar
ausência de ciclos. Ruff, mypy e a importação integral nos testes não encontraram ciclo
que impeça execução; isso não exclui ciclos tolerados pelo runtime.

## 6. Estado vivo e quórum real

[MEDIDO] `runtime/` continha 794 arquivos: 113 capturas (51.138.962 bytes), 376 arquivos
de modelos (1.667.901 bytes), 278 artefatos de quórum (532.605 bytes), 22 de estado, 3 de
logs, 2 de eventos e 0 em `runtime/proposals/`.

[MEDIDO] Os 39 painéis somam 117 membros, 115 votos e 37 decisões: 23 `escalate`, 11
`reject`, 3 `promote`. Há 9 patches, todos em painéis `escalate`; os três `promote` não
têm patch; há zero `promotion.json`.

[MEDIDO] O proponente está fora de membros e votos nos 39 painéis. Não há membro/voto
duplicado ou externo. Dos votos, 39 são schema-invalid, 46 são abstenções, 39 tentativas
de reparo falharam e 11 conclusões foram recuperadas de `<think>`.

[MEDIDO] O catálogo contém 193 endpoints: Google 58, Groq 15, NVIDIA 102, Ollama 18. O
registro observado contém 30 endpoints: 14 `ok`, 2 `reachable`, 14 `unavailable`; 14 são
utilizáveis. Só três registros têm limites efetivos provenientes de headers e 24 declaram
fonte de cota `desconhecido`.

[MEDIDO] O log operacional contém 1.166 eventos válidos, revisões 1–1.166 sequenciais,
modo `0600`, 189 `call_started` e 188 `call_completed`.

[OBSERVADO] `runtime/proposals/` é o store legado lido por `/proposals`; o caminho atual
persiste patch dentro de `runtime/quorum/<panel>/`. Portanto zero propostas nesse
diretório não significa que nenhuma proposta foi criada.

[OBSERVADO] O histórico tem só dois commits que tocam `knowledge/`: a migração
`f91591a3` e `65a4d535`, cuja mensagem declara edição direta excepcional autorizada. Não
há evento `promotion_*`, `commit_created` ou `corpus_changed`, nem `promotion.json`.

[NÃO VERIFICADO] A ausência de assinatura atual não prova impossibilidade de artefato
apagado ou mensagem de commit personalizada. O estado disponível não demonstra uma
única claim que tenha chegado ao corpus pelo Promoter.

## 7. Reproduções isoladas do caminho crítico

[OBSERVADO] Veto estrutural descartado. Com o painel real `15b0dfb87750`:

```text
persisted reject
persisted_structural_failures 3
recomputed_without_structural_failures promote
valid_votes 3 providers 2 families 3
```

[OBSERVADO] `promotion/promoter.py:104-143` chama `decide_panel(panel)` sem passar as
falhas estruturais que `work/orchestrator.py:1120` extraiu e que
`quorum/engine.py:77-86` tornou veto.

[OBSERVADO] Alvo Unicode. Em clone temporário, patch aprovado para `knowledge/Índice.md`
foi recusado com:

```text
PromotionRefused: diff fora dos alvos declarados:
['"knowledge/\\303\\215ndice.md"'] ≠ ['knowledge/Índice.md']
```

[OBSERVADO] A comparação vem de `git diff --cached --name-only` sem `-z` nem
`core.quotePath=false` em `promoter.py:328-335`. Os nove patches reais têm ao menos um
alvo com caractere não ASCII.

[OBSERVADO] Controle positivo. O mesmo ensaio em clone temporário, com alvo ASCII
`knowledge/IA/RAG e Contexto Longo.md`, passou audit, projeção, diff declarado,
`merge --ff-only`, deixou a árvore limpa e emitiu a sequência esperada de eventos.

[OBSERVADO] Falha pós-fast-forward. Injeção de `RuntimeError` ao emitir
`corpus_changed` deixou HEAD avançado e conteúdo presente, mas emitiu
`promotion_completed: refused`. `promotion.json` só é escrito depois de `promote()`
retornar em `tools/promote.py:104-111`.

[OBSERVADO] Crash duro. Um subprocesso que executou `os._exit(86)` no mesmo ponto saiu
86, deixou HEAD avançado, nenhum `promotion.json`, worktree registrada e diretório
`/tmp/vault-promotion-*`. O ensaio ocorreu apenas em clone temporário; seus artefatos
foram removidos e o diff canônico permaneceu idêntico.

[OBSERVADO] Identidade. Três votos em memória de
`groq/openai/gpt-oss-120b`, `nvidia/openai/gpt-oss-120b` e
`groq/qwen/qwen3.6-27b` produziram `promote`, 3 votos, 2 providers, 2 families. A chave de
membro é `provider/endpoint`; `infer_family` é descrita como visual em
`providers/base.py:264`, mas `MIN_FAMILIES` governa decisão e planejamento.

[OBSERVADO] Race SSE. Append entre as duas leituras de `snapshot()` produziu:

```text
snapshot 2 runtime-00000000000000000001 [1]
replay_after_runtime_cursor []
present_after_frame_id [2]
```

[OBSERVADO] Watcher inválido. Em corpus temporário, transformar um link válido em
quebrado produziu revisão 2, `broken=1`, `edges=0` e `last_error=None`; a última projeção
válida não foi preservada.

[OBSERVADO] Crash real de worker. A tarefa `aut-8349e507b41388463a4e` abriu o painel
`e626137bd0cb`, completou Google e dois Groq, iniciou NVIDIA e não gravou
`call_completed`. Após restart abriu `9999849aff4b` e repetiu os quatro endpoints. O
painel antigo ficou com dois votos/sem decisão. `queue.finish` grava painel/endpoints só
depois da chamada; recovery reabre `running`; ledger persiste no `finally` do runner.

## 8. Lacuna do auditor epistemológico

[MEDIDO] O corpus contém 267 claims. Distribuição de status: `established` 164,
`supported` 27, `refuted` 33, `open` 16, `model-dependent` 12, `hypothesis` 6,
`speculative` 5, `operational` 3 e `out-of-scope` 1.

[MEDIDO] Busca lexical encontrou 96 ocorrências de DOI, 76 de arXiv e 44 de ISBN (216
ocorrências, não identificadores únicos). Oitenta notas têm `verified_at`; nenhuma tem
`review_after`.

[OBSERVADO] Em cópia temporária, remover `title:` do frontmatter, trocar um status por
`invented-status` e substituir um DOI por `10.0000/audit-fake` ainda terminou com código
0 e `APROVADO`. O audit verifica delimitadores de frontmatter, links/relações, orfandade,
MOC vazio e IDs duplicados; não valida campos obrigatórios, status ou resolução de
identificadores.

[INFERIDO] O gate é estrutural e parcial, como sua documentação declara; chamá-lo de
garantia epistemológica seria incorreto.

## 9. API e Atlas ao vivo

[OBSERVADO] Um app FastAPI isolado recebeu Settings explícitas com `_env_file=None`,
runtime copiado em `/tmp`, corpus canônico somente para leitura e nenhuma chave. Respostas:
`/health` 0.1.0; `/corpus/notes` 84; `/proposals` 0; snapshot com os quatro provedores
`ausente` e `key_configured=false`.

[MEDIDO] `/corpus/projection` retornou contrato 1.1.0, origem `corpus`, origem operacional
`quorum`, fingerprint `e48f…a2b3`, 12 domínios, 84 nós epistêmicos, 358 operacionais,
555 arestas canônicas, 52 agregadas, 672 wikilinks e 267 claims. Cinco leituras após
aquecimento: 0,163783; 0,097686; 0,082078; 0,079690; 0,078389 s; mediana 0,082078 s.

[MEDIDO] A cena viva compôs 442 nós, 1.122 arestas e revisão runtime 1.166. Após o corte
de 160 eventos, a camada viva tinha 175 nós. Capturas novas estão em
`ANE_AUDIT_PACKAGE/screenshots/`.

[OBSERVADO] Instrumento: Chrome/ANGLE Vulkan SwiftShader, 1920×993, mock FastAPI GET/SSE
read-only e Vite com cache/perfil em `/tmp`. O mock recusou PUT de layout com 503. Todos
os processos e listeners 8000/5173/9222 foram encerrados ao final.

[MEDIDO] Com todas as camadas: 361 draw calls, 17.143 triângulos, 1.314 entradas de
inspeção, 697 com world box e 694 visíveis. `renderOnce().objects=15` conta apenas filhos
de topo e não é total da cena.

[MEDIDO] rAF aproximado no software renderer: 1,1 FPS com runtime, 3,2 sem runtime e 5,3
apenas corpus. Heap variou 43–120 MB entre recargas/amostras sem GC controlado.

[NÃO VERIFICADO] FPS em GPU física, memória GPU e estabilidade de heap em sessão longa
não foram medidos por instrumento válido; os números SwiftShader não são estimativa de
hardware.

[OBSERVADO] A captura inicial ocorre após o único `fitToGraph`, mas SSE adiciona runtime
depois (`main.ts:367,392`; `atlas.ts:2172-2179`) sem reenquadrar. O topo de Modelos/
Provedores ficou cortado; pressionar G trouxe o conjunto ao quadro.

[OBSERVADO] `atlas.ts:1615-1627` trata WASD/G globalmente sem ignorar inputs. O dock tem
input de segredo (`dock.ts:234-245`); essas letras são interceptadas enquanto se digita.

[OBSERVADO] `runtimeLayer.update` limpa e recria tudo, inclusive `selecionado`
(`runtimeLayer.ts:527-544`), enquanto `mutable.runtimeSelected` permanece sem reaplicar
`setSelected`. Enter/Esc consultam apenas seleção corpus (`atlas.ts:1629-1637`).

[OBSERVADO] `aplicarEnfase` (`atlas.ts:754-772`) e o novo `acenderOutraPonta`
(`atlas.ts:1444-1457`) escrevem todos os slots; hover ou novo snapshot volta a executar o
primeiro e apaga o segundo.

[OBSERVADO] O pool tem 640 slots, mas cada slot cria dois objetos Text — corpo e título
(`panelTextRenderer.ts:249-280`) — e `dispose` libera só o corpo (`547-553`). A métrica
`criados=slots.length` e o harness de “64 Text” não observam o título.

[OBSERVADO] `CONTROLS` contém somente G (`controls3d.ts:36-38`), mas a mensagem inicial
anuncia L/F/M/G (`main.ts:428`). L/F/M não têm efeito. O dock oculto fez 146 GETs com
intervalos próximos de 2,5 s porque a cadência não considera `dock--oculto`.

## 10. Credenciais e segurança

[OBSERVADO] Reprodução 422 com `CredentialBody.key` sintética de 513 caracteres:

```text
oversize_status 422
candidate_full_in_response True
input_length 513
```

[OBSERVADO] A validação Pydantic ocorre antes da rota e o handler FastAPI serializa
`exc.errors()`, que inclui `input`. Nenhum valor candidato é reproduzido neste pacote.

[OBSERVADO] Reprodução com adaptador falso que ecoa candidata sintética:

```text
adapter_status 200 invalido
candidate_prefix_in_detail True
detail_length 300
```

[OBSERVADO] `_probe` sanitiza com o Settings original (`routes.py:153-178`); esse objeto
não conhece a candidata. A regex genérica (`config.py:25-27`) só cobre três formatos e
não uma chave Ollama arbitrária.

[OBSERVADO] Os ensaios positivos de `tests/test_control.py` passaram: substituição
atômica, arquivo `0600`, preservação de outras variáveis, máscara abaixo/acima de 12 e
redação de chaves conhecidas. Em diretório preexistente `0755`, `write_atomic` deixou o
diretório `0755`, embora o arquivo fosse `0600`.

[MEDIDO] Varredura atual avaliou 1.122 arquivos e achou três ocorrências dos prefixos
buscados, todas sintéticas em testes. O histórico alcançável avaliou 779 blobs e sete
ocorrências, correspondentes às mesmas duas credenciais sintéticas. Nenhum `.env`, token
ou credential file real está rastreado.

[NÃO VERIFICADO] Regex não prova ausência de segredo sem formato, ofuscado ou dentro de
imagem. Os 32 PNGs antigos não contêm chunks EXIF/textuais; revisão visual de privacidade
e direitos permanece necessária antes de publicação.

## 11. História, higiene e dependências

[MEDIDO] Commits por dia: 9 em 30/07, 15 em 02/08, 5 em 03/08, 27 em 04/08, 17 em
05/08, 11 em 06/08, 2 em 07/08 e 8 em 08/08. Hotspots por commits: `atlas.ts` 32,
`panels.ts` 14, `panelTextRenderer.ts` 12, `main.ts` 12, `composeLayout.ts` 11,
`contract.ts` 10.

[OBSERVADO] `8a3f894` introduziu voo livre e `6b64792` o reverteu. `d141ba7` removeu o
controle de camada, tornou `todas` padrão e religou famílias; `b6fe0e8` removeu
gaiolas/wireframes previstos no ADR-002. `controlBar.ts` ficou sem consumidor.

[MEDIDO] `knip` apontou `controlBar.ts`, `createControlIsland`, `describePanels`,
`parallax` e `metricasDeRelacao` sem uso. `vulture --min-confidence 80` não apontou
candidato Python. `jscpd` mediu 167 linhas duplicadas, 0,51%.

[MEDIDO] O repositório tem 324 arquivos rastreados e 16,11 MiB. A auditoria antiga ocupa
13,72 MiB; 32 PNGs somam 13,60 MiB, 84,4% do total rastreado.

[OBSERVADO] Há 22 referências a `/home/ziul` em nove documentos. O e-mail autoral está
nos 94 commits e 67 commits têm trailer de coautoria. Isso é identidade pública, não
segredo, e exige decisão consciente do mantenedor.

[OBSERVADO] Não existem `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md` nem
`CODE_OF_CONDUCT`. `.env.example` existe sem valores. `.gitignore` cobre runtime,
ambientes, dependências, caches, build, projeção gerada, VS Code e pacotes; nenhuma
dessas categorias aparece em `git ls-files`.

[OBSERVADO] Auditoria do ambiente do projeto encontrou `cryptography 49.0.0` afetado por
`PYSEC-2026-3552`/`CVE-2026-69247`, corrigido em 50.0.0. O caminho vulnerável de
descriptografia PKCS#7 não foi encontrado na aplicação, reduzindo a aplicabilidade
observada, não a presença da dependência afetada.

[OBSERVADO] `pnpm audit --json` encontrou duas vulnerabilidades altas no toolchain de
desenvolvimento: `brace-expansion 5.0.8` (correção `>=5.0.9`) e `nanoid 3.3.16`
(correção `>=3.3.17`).

[MEDIDO] Dezoito pacotes Python e seis npm estavam desatualizados. Dependências diretas
inspecionadas declaram licenças permissivas; `orjson` também declara MPL-2.0. Nenhum
conflito jurídico foi observado. A proveniência de `tools/atlas.svg` e capturas não está
documentada.

## 12. Limitações e hipóteses abertas

[NÃO VERIFICADO] `make setup`, `make corpus-graph` e o launcher canônico `make dev` não
foram executados: os dois primeiros escreveriam dependências/artefato ignorado
preexistentes e o app padrão carregaria `secrets.env`, explicitamente proibido. Lockfiles
foram verificados em dry-run; projeção/API/SSE/cena foram exercitados por app isolado com
`_env_file=None` e transporte GET-only.

[NÃO VERIFICADO] Não houve chamada externa, teste de cota sob carga, confirmação nos
logs dos provedores nem teste real de 401/403. Artefatos persistidos provam execução
local do caminho, não faturamento ou resposta remota de cada chamada.

[NÃO VERIFICADO] Escalabilidade com 800 notas não foi exercitada. O watcher foi testado
com corpus temporário pequeno e rajadas não foram perfiladas sob concorrência real.

[NÃO VERIFICADO] F-01 antigo (zoom máximo), F-02/F-03 visuais, corte de texto F-10 e
memória GPU não foram revalidados por gesto/instrumento válido nesta passagem. Onde o
código/teste indica correção, a tabela de regressão distingue isso de validação viva.

[INFERIDO] Hipótese a testar depois da correção dos bloqueadores: uma sessão WebGL longa
com GC controlado e contadores reais de objetos deve decidir se o churn por SSE causa
crescimento sustentado além do vazamento estático do título do pool.
