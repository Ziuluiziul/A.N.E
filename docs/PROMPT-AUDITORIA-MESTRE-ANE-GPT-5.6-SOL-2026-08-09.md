# PROMPT MESTRE DE AUDITORIA — A.N.E. (Atlas Neural-Epistêmico)

**Destinatário:** GPT-5.6 Sol, operando no VS Code com acesso de leitura e execução ao
repositório real.
**Emitido em:** 2026-08-09, por Claude Opus 5, construtor de aproximadamente 80% da
implementação recente.
**Natureza:** auditoria forense adversarial, primeira passagem, não destrutiva.

> Tudo abaixo da linha é o prompt. Copie a partir de `## 0.` até o fim.

---

## 0. QUEM VOCÊ É NESTA TAREFA

Você é o auditor independente do **A.N.E. — Atlas Neural-Epistêmico**, um sistema em
`/home/ziul/Projetos/vault-autodidata` que você já auditou uma vez, em 2026-08-05, e que
mudou substancialmente desde então. **Você está defasado em relação ao estado atual.**
Trate seu próprio relatório anterior (`docs/audits/2026-08-05-atlas-geral/`) como
documento histórico, não como descrição do presente: parte dos defeitos que você
registrou foi corrigida, parte foi corrigida de um jeito que criou outros, e o sistema
ganhou subsistemas que não existiam quando você olhou.

Quem escreveu este prompt construiu a maior parte do que você vai auditar. Isso torna as
**Notas do Construtor** (seção 12) úteis como mapa e perigosas como narrativa. Elas são
**pistas de investigação**. Nenhuma delas é conclusão, nenhuma delas é fato até que você
a confirme na evidência, e várias delas podem estar erradas — inclusive as que afirmam
que algo funciona.

A regra que ordena todas as outras: **a evidência do repositório prevalece sobre
qualquer narrativa histórica**, incluindo a deste prompt, a do README, a dos handoffs em
`docs/` e a da sua própria auditoria anterior.

Seu produto não é uma opinião sobre o projeto. É um **pacote probatório** que permita a
um terceiro auditor, sem contexto nenhum, refazer suas verificações e discordar de você
com base nos mesmos dados.

### O que você precisa determinar

1. Qual é o **verdadeiro estado arquitetural e funcional** do A.N.E. hoje.
2. Se ele tem qualidade para ser classificado **Alpha**, ou o que falta exatamente.
3. Se o repositório pode ser **publicado no GitHub**, ou o que precisa ser sanitizado
   antes.

Uma quarta pergunta atravessa as três, e é a mais importante desta auditoria:

> **Onde a interface parece fazer algo que o runtime não faz?**

O A.N.E. é um sistema visual sobre um sistema operacional real. A forma de falha mais
provável — e a mais cara, porque é a que sobrevive a testes verdes — é uma superfície
que representa convincentemente uma capacidade que não está conectada, ou que está
conectada a dados sintéticos. Procure isso ativamente em cada subsistema.

---

## 1. REGRAS DE ENGAJAMENTO

**Esta passagem é de leitura.** Você observa, mede e executa; não conserta.

| Permitido | Proibido |
| --- | --- |
| Ler qualquer arquivo do repositório | Corrigir defeitos encontrados |
| Rodar `make audit`, `make test`, `make lint` | `git commit`, `git push`, `git reset`, `git checkout` que descarte trabalho |
| Subir backend e frontend localmente | Apagar ou mover arquivos |
| Ler o histórico Git | Reescrever histórico |
| Consultar `runtime/` | Escrever em `knowledge/` |
| Criar arquivos **novos** dentro de `ANE_AUDIT_PACKAGE/` e os entregáveis nomeados na seção 11 | Alterar qualquer arquivo pré-existente |
| Alteração temporária isolada, se for a única forma de rodar um teste | Deixar qualquer alteração temporária no lugar |

**Sobre a árvore de trabalho suja.** No momento da emissão deste prompt havia seis
arquivos modificados e não commitados (seção 3). Eles fazem parte do estado a auditar,
não são ruído a limpar. **Não faça stash, não descarte, não commite.** Se a árvore
estiver limpa quando você começar, significa que o mantenedor commitou nesse intervalo —
registre a diferença e siga.

**Sobre alteração temporária.** Se precisar de uma para rodar algo, registre no dossiê:
arquivo, linhas, motivo, e o comando que provou a reversão (`git diff` vazio para aquele
arquivo ao final). Uma alteração temporária não revertida invalida a auditoria inteira,
porque contamina o baseline que o próximo auditor vai usar.

**Sobre consumo externo.** O sistema chama modelos de quatro provedores. Não dispare
execuções de quórum ou de worker contra provedores reais para "ver funcionando" — há
artefatos de execuções passadas em `runtime/quorum/` que servem como evidência primária
sem gastar cota. Se decidir que uma execução real é indispensável, limite a **uma**, use
`VAULT_WORK_MAX_CALLS` baixo, e registre custo e motivo.

**Sobre credenciais.** Não leia, não escreva e não rotacione
`~/.config/vault-autodidata/secrets.env`. Você pode e deve verificar *o mecanismo* que o
manipula; não precisa do arquivo para isso. Se algum passo exigir credencial, pare e
registre como não verificado.

**Sobre destrutivo em dados canônicos.** A seção 9 pede testes de robustez (corpus
corrompido, escrita interrompida, provedor offline). Faça-os em cópia temporária fora do
repositório, apontada por `VAULT_CORPUS_DIR` e `VAULT_RUNTIME_DIR`, nunca contra
`knowledge/` ou `runtime/`.

---

## 2. TAXONOMIA DE EVIDÊNCIA

Toda afirmação do seu relatório carrega **exatamente um** destes rótulos. Afirmação sem
rótulo será tratada pelo revisor seguinte como opinião.

| Rótulo | Significa | Exige |
| --- | --- | --- |
| **OBSERVADO** | Você viu diretamente | Comando + saída, ou arquivo:linha |
| **MEDIDO** | Resultado quantitativo que você produziu | Método, número, unidade, condições |
| **INFERIDO** | Conclusão sustentada por evidência, não vista diretamente | As premissas OBSERVADAS que a sustentam |
| **DECLARADO** | Só documentação, comentário ou nome de função afirma isso | Onde está declarado |
| **NÃO VERIFICADO** | Sem evidência suficiente | Por que não deu, e o que resolveria |

Duas regras de disciplina:

- **DECLARADO nunca vira OBSERVADO por repetição.** Um docstring que descreve um
  invariante é DECLARADO até que você execute o caminho que o exerce.
- **Um teste verde é OBSERVADO sobre o teste, não sobre o sistema.** Que
  `test_quorum_core.py` passe é evidência de que aquelas asserções valem, não de que o
  quórum funciona. Distinga sempre as duas coisas.

Para o Atlas 3D existe uma armadilha específica, documentada pela sua auditoria
anterior: **teste verde não é evidência sobre a cena renderizada.** Vários defeitos
graves do produto só existiram na cena viva, com todas as camadas ligadas, e passaram
por baterias de testes unitários verdes. Onde a afirmação for sobre o que se vê, a
evidência é captura ou medição na cena, não teste.

---

## 3. FASE 0 — BASELINE FORENSE

**Não altere nada antes de terminar esta fase.** Ela produz o registro contra o qual todo
o resto será comparado, e é a primeira seção de `ANE_AUDIT_EVIDENCE.md`.

### 3.1 Estado declarado na emissão deste prompt

Verifique cada linha. Divergência é dado, não erro do prompt.

```
raiz          /home/ziul/Projetos/vault-autodidata
branch        main
HEAD          61f2da448b234bde0318237965ac954c2c591c17
              "Faz o painel do raciocínio se comportar como o do conhecimento"
data do HEAD  2026-08-08 13:55:06 -0300
commits       94 (o primeiro é 2026-07-30, "Baseline pós-migração do Vault")
árvore        suja — 6 arquivos modificados, 0 não rastreados:
                frontend/src/atlas.ts
                frontend/src/composeLayout.ts
                frontend/src/main.ts
                frontend/src/runtime.ts
                frontend/src/runtimeLayer.test.ts
                frontend/src/runtimeLayer.ts
              (+136 −24 linhas no total)
```

### 3.2 Comandos de baseline

Rode e registre a saída integral:

```bash
pwd && git rev-parse --abbrev-ref HEAD && git rev-parse HEAD
git status --porcelain=v1
git diff --stat && git diff
git log --oneline -40
git rev-list --count HEAD
git tag --list
git remote -v
git count-objects -vH
```

Se `git remote -v` estiver vazio, registre: **o repositório nunca teve remoto**, o que
muda a análise de risco da seção 8 (nada foi publicado ainda; a sanitização é preventiva,
não corretiva).

### 3.3 Inventário estrutural

Produza `ANE_REPOSITORY_INVENTORY.txt` com, no mínimo:

- árvore de diretórios até profundidade 3, excluindo `.git`, `node_modules`, `.venv`,
  `__pycache__`, `*_cache`;
- separação explícita entre **rastreado** e **ignorado-mas-presente** (`git ls-files` vs
  `git status --ignored --porcelain`);
- contagem de arquivos e linhas por subsistema;
- os 20 maiores arquivos rastreados, com tamanho;
- os 20 maiores arquivos presentes mas ignorados;
- para cada subsistema, uma linha dizendo o que ele é.

Os subsistemas conhecidos na emissão, para você confirmar ou corrigir:

| Caminho | Papel declarado | Peso na emissão |
| --- | --- | --- |
| `knowledge/` | Corpus acadêmico canônico — o produto | 12 domínios + Índice + Política |
| `backend/src/vault/` | Pacote Python `vault` | 10.459 linhas em 45 módulos |
| `providers/` | Um adaptador por provedor + registro/catálogo/aptidão | 2.127 linhas, 4 provedores |
| `integrations/google_workspace/` | APIs do Google Workspace | — |
| `frontend/src/` | Cena 3D em TypeScript + Three.js | 17.258 linhas em 57 arquivos |
| `tools/` | Scripts curtos chamados pelo `Makefile` | 13 scripts |
| `tests/` | Suíte Python | 25 arquivos |
| `runtime/` | Estado local, ignorado pelo Git | ver 3.4 |
| `docs/` | ADRs, ciclos, handoffs, prompts, auditoria anterior | 19 documentos + `audits/` |

### 3.4 `runtime/` — estado vivo, não versionado

Contagens na emissão, a confirmar:

```
runtime/captures/    113 arquivos     capturas da cena
runtime/modelos/     376 arquivos     inventário por provedor (google, groq, nvidia, ollama)
runtime/quorum/      278 arquivos     39 painéis de quórum, cada um com
                                      decision.json, members.json, task.json,
                                      events.jsonl, votes/
runtime/state/        22 arquivos     layout persistido, fila de autonomia
runtime/logs/          3 arquivos
runtime/events/        2 arquivos
runtime/proposals/     0 arquivos     ← vazio
```

`runtime/proposals/` vazio é um dado importante e você deve interpretá-lo, não
contorná-lo: 39 painéis de quórum existem e nenhuma proposta está pendente. Determine se
isso significa (a) que tudo foi promovido, (b) que nada chegou a virar proposta, (c) que
o caminho proposta→promoção nunca fechou de ponta a ponta, ou (d) outra coisa. A resposta
muda a avaliação do núcleo epistemológico inteiro.

### 3.5 Ambiente

Registre versões: `python3 --version`, `uv --version`, `node --version`,
`pnpm --version`, `git --version`, SO, e se `.venv/` e `frontend/node_modules/` estão
presentes e resolvidos a partir dos lockfiles.

---

## 4. FASE 1 — RECONSTRUÇÃO ARQUITETURAL

Reconstrua o sistema a partir do código, não da documentação. Só depois de ter sua
própria versão, compare com `README.md`, `AGENTS.md` e `docs/` — e trate cada divergência
como achado.

### 4.1 O que reconstruir

- **Finalidade.** O que o A.N.E. se propõe a fazer, deduzido do que ele faz.
- **Camadas.** Quais existem, o que cada uma possui, onde estão as fronteiras.
- **Fluxos de ponta a ponta.** No mínimo estes cinco, cada um do gatilho ao efeito
  persistido, nomeando arquivo e função em cada salto:
  1. `knowledge/*.md` → leitura → projeção → cena 3D;
  2. tarefa → orquestrador → provedor → resposta → evento → trilha viva na cena;
  3. proposta → quórum → votos → decisão → promoção → corpus;
  4. painel de controle → credencial → provedor → runtime;
  5. edição em `knowledge/` → watcher → SSE → atualização da cena sem reload.
- **Contratos.** O contrato projeção↔cena (`frontend/src/contract.ts`, 522 linhas) é o
  mais importante do sistema: é ele que decide o que a cena pode saber. Determine se ele
  é validado em runtime ou só tipado, e o que acontece quando o backend manda algo fora
  do contrato.
- **Modelos de dados.** Pydantic no backend, tipos no frontend. Onde as duas
  representações do mesmo conceito divergem, há bug latente.
- **Estado compartilhado, concorrência, lifecycle.** Quem escreve o quê, quando, e o que
  acontece se dois escreverem junto.

### 4.2 Perguntas de arquitetura a responder com evidência

- Quantos módulos passam de 700 linhas, e algum deles concentra responsabilidades que
  deveriam estar separadas? (Na emissão: `frontend/src/atlas.ts` 2.304,
  `backend/src/vault/work/orchestrator.py` 1.328, `backend/src/vault/operational.py`
  1.115, `frontend/src/panels.ts` 832.)
- O acoplamento é dirigido, ou há ciclos de importação?
- Erros: são tratados, engolidos, ou propagados sem contexto? Há `except` largo em
  caminho crítico?
- Retry/backoff/idempotência: existem onde há rede? São testados?
- Onde há determinismo prometido — quórum, layout, projeção — ele é real? Rode duas vezes
  e compare byte a byte.
- Condições de corrida entre watcher, worker, API e escrita de estado.
- Limites de recurso: há teto de memória, de eventos, de nós em cena? O que acontece
  quando estoura?
- Degradação: com backend fora, com corpus vazio, com provedor indisponível — o sistema
  degrada ou quebra?

---

## 5. FASE 2 — HISTÓRIA E DERIVA

94 commits em dez dias. Isso é ritmo alto, e ritmo alto produz deriva.

```bash
git log --format='%h %ad %s' --date=short
git log --stat --oneline -60
git log --format='%h %s' --name-only | head -400
```

Determine:

- Quais módulos foram reescritos mais vezes. Área que sofreu várias reformulações é a que
  tem maior chance de carregar restos da versão anterior.
- Quais commits reverteram decisões anteriores. Há pelo menos um par explícito no
  histórico (`8a3f894` troca órbita por voo livre; `6b64792` devolve a órbita). Procure
  outros — cada par revela uma decisão que não estabilizou.
- Módulos adicionados, substituídos, abandonados. Procure código morto: exportado e nunca
  importado, função nunca chamada, flag nunca lida.
- Duplicação: dois caminhos para a mesma coisa. `git log` mostra vários commits que
  "unificam" algo (`78ac5df`, `d141ba7`, `7a3bac3`) — verifique se a unificação removeu o
  caminho antigo ou apenas parou de usá-lo.
- Deriva documentação↔implementação. `docs/` tem 19 arquivos, a maioria histórica.
  Classifique cada um conforme a seção 10.
- **Regressões.** Compare o estado atual contra os achados F-01..F-nn da sua auditoria de
  2026-08-05 em `docs/audits/2026-08-05-atlas-geral/FINDINGS.md` e os fechamentos
  `FECHAMENTO-3.5-A..D.md`. Para cada achado anterior: corrigido, corrigido parcialmente,
  não corrigido, ou reintroduzido? Essa tabela é entregável obrigatório dentro do dossiê.

---

## 6. FASE 3 — DOMÍNIOS DE AUDITORIA

Audite cada domínio abaixo. Em cada um, a pergunta central é a mesma: **o que existe de
verdade, o que existe só como interface, e o que existe só como documento?**

Não se limite a estes domínios. Se o código revelar outro subsistema, audite-o e
acrescente uma seção.

### 6.1 Sistema multimodelo e multiprovedor

Arquivos: `providers/` inteiro, `backend/src/vault/work/`,
`backend/src/vault/control/`, `tools/discover_models.py`, `tools/endpoints.py`,
`tools/smoke_providers.py`, `runtime/modelos/`.

Verifique:

- **Identidade modelo × provedor.** O mesmo modelo servido por dois provedores é uma
  entidade ou duas? O quórum exige "pelo menos dois provedores representados" — se a
  identidade estiver errada, o quórum pode contar como independentes dois votos do mesmo
  modelo. Isso é um defeito de integridade, não de estilo. Encontre onde a identidade é
  decidida e prove que ela sustenta a regra.
- **Cotas.** TPM, RPM, RPD, janela de contexto, nível de raciocínio: são declarados,
  medidos ou presumidos? Onde estão? Uma cota declarada que o runtime não consulta é
  interface sem função.
- **`providers/aptitude.py`** (316 linhas) classifica endpoints. Com base em quê? Dado
  medido ou heurística sobre o nome do modelo? Isso determina se o roteamento é informado
  ou decorativo.
- **Do painel ao runtime.** Mexer num controle do painel muda o comportamento de uma
  execução? Trace o caminho `frontend/src/controlApi.ts` →
  `backend/src/vault/control/routes.py` → preferências → orquestrador, e prove que a
  preferência é **lida** na hora de escolher endpoint. Se ela for gravada e nunca lida, é
  o achado mais importante deste domínio.
- **Ausência de credencial.** Sem chave nenhuma, o sistema diz "sem credencial" ou diz
  "zero"? A diferença é entre honestidade e mentira de interface. Teste com ambiente
  limpo.
- **403 ≠ 401.** Um provedor pode aceitar a chave e negar o modelo. Verifique que o
  sistema distingue "chave inválida" de "chave válida sem acesso a este modelo", e que a
  interface não colapsa os dois num só estado.
- **Catálogo vs realidade.** `runtime/modelos/` tem 376 arquivos de inventário. Compare
  o que o catálogo declara disponível com o que o smoke test comprovou responder. A
  distância entre os dois números é uma medida direta de quanto o sistema sabe sobre si.
- Failover, retry, backoff, roteamento: implementados ou nomeados?

### 6.2 Quórum e promoção

Arquivos: `backend/src/vault/quorum/` (7 módulos), `backend/src/vault/promotion/`,
`backend/src/vault/proposals/`, `tools/run_quorum.py`, `tools/promote.py`,
`runtime/quorum/` (39 painéis reais), `tests/test_quorum_core.py`,
`tests/test_quorum_orchestrator.py`, `tests/test_promotion.py`.

O quórum é a regra de governança central do projeto: `AGENTS.md` diz que promoção de
conhecimento se decide por quórum multimodelo, com no mínimo 3 votos válidos, 2
provedores e o proponente fora da contagem (`MIN_VALID_VOTES`, `MIN_PROVIDERS`,
`MIN_FAMILIES` em `quorum/engine.py`).

Verifique:

- Os 39 painéis em `runtime/quorum/` são execuções reais? Abra `decision.json`,
  `members.json`, `votes/`. Quantos alcançaram quórum, quantos falharam, por quê.
- O proponente é de fato excluído da contagem? Prove com um painel real, não só com o
  teste.
- `MIN_FAMILIES` — o que é uma família, e ela impede que três modelos da mesma casa
  formem quórum?
- Voto malformado: `quorum/parser.py` (274 linhas) decide o que conta. Um voto que não
  parseia vira abstenção, erro, ou some? Voto que some é falha silenciosa e é achado
  grave.
- Confiança nunca vale como voto — o docstring de `engine.py` afirma isso. Prove.
- **Promoção.** `promotion/promoter.py` aplica patch numa árvore Git temporária e só move
  o ponteiro se tudo passar. Esse é o mecanismo que protege o corpus. Audite-o com o
  máximo rigor: o que acontece se o processo morrer no meio, se a árvore temporária tiver
  alteração inesperada, se o patch tocar arquivo fora de `knowledge/`.
- **A pergunta que fecha o domínio:** algum claim que está hoje em `knowledge/` chegou lá
  por este caminho? Se não, o quórum é uma máquina completa que nunca entregou seu
  produto — e isso precisa estar no dossiê com todas as letras, sem eufemismo e sem
  dramatização.

### 6.3 Núcleo epistemológico e corpus

Arquivos: `knowledge/` inteiro, `tools/audit.py`, `backend/src/vault/corpus/`,
`backend/src/vault/projection.py`, `knowledge/Política Epistêmica e de Linkagem.md`,
`knowledge/Índice.md`.

```bash
make audit          # equivale a python3 tools/audit.py; somente leitura
```

Verifique:

- `make audit` sai zero? Registre a saída inteira, linha de defeito por linha de defeito.
- **O que `audit.py` não confere.** `AGENTS.md` admite que ele é estrutural e parcial:
  não valida verdade científica, não resolve DOI/arXiv/ISBN, não confere se identificador
  bate com título canônico. Meça o tamanho dessa lacuna: quantos claims existem, quantos
  têm identificador, e o gate atual poderia detectar um identificador plausível e errado?
  Não resolva os identificadores você mesmo — dimensione o risco.
- Números do README: "81 notas, 627 wikilinks tipados e 267 claims" e, adiante, "511
  arestas". Meça você mesmo. Se divergirem, determine se é desatualização ou **dois
  denominadores diferentes** — o commit `6ce91a4` ("Dá nomes distintos aos dois
  denominadores") sugere que essa confusão já existiu e pode ter sobrado em algum lugar.
- Integridade referencial: wikilink quebrado, wikilink sem `relation:`, nota órfã, MOC
  vazio, claim com ID duplicado.
- Vocabulário fechado de status e de relação: é imposto por código ou só por convenção?
- **Separe com clareza:** o que é estrutura documental, o que é estrutura semântica, o
  que é lógica operacional, o que é visualização, o que é inferência, o que é automação.
  O A.N.E. tem um grafo bonito; a pergunta é se ele **infere** algo ou se apenas
  **desenha** o que já estava escrito nos arquivos. As duas respostas são legítimas — o
  que não pode é a documentação afirmar uma e o código fazer a outra.

### 6.4 Atlas 3D como sistema operacional

Arquivos: `frontend/src/` inteiro. Núcleo: `atlas.ts` (2.304 linhas), `contract.ts`,
`composeLayout.ts`, `layout.ts`, `panels.ts`, `panelBodies.ts`, `panelTextRenderer.ts`,
`runtimeLayer.ts`, `operationalLayout.ts`, `edges.ts`, `textPool.ts`, `lod.ts`,
`depth.ts`, `dock.ts`, `screenMetrics.ts`.

Audite o Atlas como produto operacional, não como demonstração. Verifique:

- **Corpus → representação.** Cada nó em cena corresponde a uma entidade real? Há nó
  sintético, placeholder ou de demonstração misturado ao real? `VAULT_DEMO_OPERATIONAL`
  liga uma trilha sintética — confirme que ela é `0`/vazia por padrão, que a projeção
  declara `operationalSource: demo` quando ligada, e que **nenhum caminho de falha**
  produz `demo` sem pedido explícito (`projection.py` afirma isso; prove).
- **O que a interface deixa fazer vs o que ela realmente faz.** Para cada controle,
  clique, tecla e painel: ele consulta ou modifica estado canônico, ou só muda pixel?
  Monte a tabela. Esta é a tabela mais valiosa da auditoria.
- **Pooling e ciclo de vida de memória.** `textPool.ts` existe justamente porque texto em
  3D é caro. Meça: navegue por muitas entidades, expanda e recolha painéis, e verifique
  se geometrias, materiais e objetos de texto são liberados. Vazamento aqui é achado P1.
- LOD: os degraus mudam o que se lê, ou só o tamanho? `depth.ts` e `lod.ts`.
- Picking, foco, câmera, expansão: o clique cai onde deveria? O painel focado cabe na
  tela em zoom máximo? (Era o F-01 da sua auditoria anterior; commits posteriores dizem
  ter tratado — confirme, não confie.)
- **Ênfase de destaque.** Verifique quantos pontos do código escrevem o estado de ênfase
  dos corpos (`setEmphasis`) e em que ordem. Dois escritores do mesmo estado visual, em
  ordem dependente de evento, é padrão clássico de bug intermitente.
- Poluição visual e legibilidade em cena cheia, com todas as camadas ligadas.
- Sincronização: o que acontece com a cena quando `knowledge/` muda durante a navegação.
- **Desempenho medido, não estimado.** FPS, contagem de draw calls, contagem de objetos,
  memória de GPU e de heap, em cena global e em cena focada.

**Método obrigatório para este domínio:** a verificação é por **captura da cena viva**,
não por teste. Rode o sistema, capture, meça na captura. Um diff entre duas capturas mede
tudo que mudou entre elas — texto, halo, contraste, segundo grau — então ao comparar
estados, nomeie qual diferença você está atribuindo à causa que afirma. Há 113 capturas
anteriores em `runtime/captures/` e 33 na auditoria passada em
`docs/audits/2026-08-05-atlas-geral/screenshots/`: use-as como termo de comparação
histórica, mas produza capturas novas — as antigas descrevem um sistema que mudou.

**Cuidado com o instrumento.** Se você inspecionar a cena por um navegador embutido ou
headless, verifique se ele compõe quadros de fato: um painel que não anima pode ser
limitação do instrumento, não defeito do produto. Prove qual dos dois antes de registrar.

### 6.5 Runtime, autonomia e observabilidade

Arquivos: `backend/src/vault/autonomy/` (worker 506 linhas, generator 398, queue 293),
`backend/src/vault/events/`, `backend/src/vault/app.py`, `tools/run_worker.py`,
`tools/atlas.sh`, `runtime/logs/`, `runtime/events/`.

Verifique:

- O worker autônomo é acionado por `make worker`, **fora da API** — o próprio
  `control/snapshot.py` declara isso. Consequência: o painel pode mostrar estado de
  worker que ninguém está executando. Determine o que o painel afirma nesse caso e se a
  afirmação é honesta.
- Fila de autonomia: persiste? Sobrevive a reinício? `tests/test_restart_continuity.py`
  existe — leia o que ele realmente garante.
- Eventos: `events/store.py` menciona cauda parcial após queda de energia. Teste o
  cenário em ambiente isolado.
- SSE: `/corpus/events` e `/runtime/events`. Cliente desconectado, backend reiniciado,
  revisão retrocedida — o que acontece?
- **Observabilidade.** Uma falha em produção seria diagnosticável? Há níveis de log,
  contexto, identificadores correlacionáveis entre backend, worker e cena? Erros
  silenciosos (`except` que engole, `catch` vazio, `?? 0` que transforma ausência em
  zero) são achados desta seção.
- Telemetria involuntária: alguma chamada sai da máquina sem o usuário ter pedido?

### 6.6 Segurança do mecanismo de credenciais

Arquivos: `backend/src/vault/control/credentials.py`, `control/atomic.py`,
`config.py` (função `redact`), `control/routes.py`, `tests/test_control.py`.

O módulo declara quatro cuidados: escrita atômica, modo `0600`, preservação de variáveis
de outros provedores, e nunca imprimir o valor. **Verifique os quatro por execução, em
`tmp_path`, não por leitura do docstring.** Em particular:

- A permissão é aplicada **antes** de o conteúdo entrar no arquivo?
- Uma escrita interrompida deixa o arquivo íntegro?
- O valor aparece em algum log, mensagem de erro, resposta HTTP, traceback ou no corpo
  de exceção que sobe pela API?
- A máscara mostra 4 caracteres finais só acima de 12 de comprimento — abaixo disso a
  dica seria fração grande demais do segredo. Confirme.
- `redact` cobre os prefixos reais dos quatro provedores?
- A rota `PUT /providers/{id}/credential` valida formato sem vazar o valor na resposta de
  erro?

---

## 7. FASE 4 — TESTES E EXECUÇÃO REAL

### 7.1 A suíte

```bash
make audit
make test     # uv run pytest -q; depois pnpm typecheck && pnpm test
make lint     # ruff, mypy, eslint
```

Registre saída integral, contagens e tempo de cada um. Na emissão havia **339 funções de
teste Python** em 25 arquivos e cerca de **292 casos TypeScript** em 18 arquivos de teste
— confirme os números.

### 7.2 O que investigar além de "passou"

Passar não é evidência de qualidade. Para as áreas críticas — quórum, promoção,
credenciais, orquestrador, projeção, camada viva — determine:

- **Testes triviais:** asserções que valem para qualquer implementação.
- **Mock excessivo:** o teste exercita o sistema ou exercita o mock? Toda integração
  externa é simulada; determine se a simulação corresponde ao comportamento real
  observado nos artefatos de `runtime/`.
- **Teste de implementação, não de comportamento:** quebra ao refatorar sem que nada
  tenha piorado.
- **Caminhos de erro sem cobertura:** timeout, resposta inválida, quota estourada,
  credencial ausente, arquivo corrompido, escrita interrompida.
- **Corrida sem teste:** watcher + worker + API escrevendo junto.
- **Funcionalidade crítica sem cobertura nenhuma.** Faça a lista explícita. Cruze os
  módulos maiores com os arquivos de teste: `operational.py` tem 1.115 linhas e
  `work/orchestrator.py` tem 1.328 — a cobertura proporcional a eles existe?
- **Assimetria frontend.** `atlas.ts`, o maior arquivo do projeto (2.304 linhas), tem
  arquivo de teste próprio? Se não, o que testa a montagem da cena?

### 7.3 Execução real

Pelas vias oficiais:

```bash
make setup                        # se necessário
make corpus-graph                 # projeta knowledge/ em frontend/public/projection.json
VAULT_AUTONOMOUS_WORKER=0 make dev
```

`VAULT_AUTONOMOUS_WORKER=0` sobe backend e Atlas **sem** chamadas de modelo — é o modo
correto para auditar sem consumir cota. Verifique:

- backend responde em `http://127.0.0.1:8000` (`/health`, `/corpus/notes`,
  `/corpus/projection`, `/proposals`, `/api/control/snapshot`);
- Atlas carrega em `http://127.0.0.1:5173` e mostra o corpus real;
- comunicação backend↔frontend, SSE incluído;
- console do navegador: warnings, exceptions, erros de rede;
- **frontend sem backend** — derrube o backend com o Atlas aberto e registre o
  comportamento (`frontend/src/fallback.ts` existe para isso; confirme se cumpre);
- **backend sem corpus** — aponte `VAULT_CORPUS_DIR` para diretório vazio;
- **corpus inconsistente** — cópia temporária com wikilink quebrado e frontmatter
  inválido;
- shutdown e restart: estado sobrevive? Layout persistido volta?
- comportamento sem nenhuma credencial configurada.

**Nota sobre acoplamento de endereço:** cinco módulos do frontend embutem
`http://127.0.0.1:8000` literalmente (`controlApi.ts:18`, `contract.ts:419-420`,
`layoutStore.ts:14`, `runtime.ts:95`). Determine se existe qualquer forma de apontar o
frontend para outro backend sem editar código, e qual o impacto disso para instalação por
terceiros.

---

## 8. FASE 5 — SEGURANÇA E HIGIENE PARA PUBLICAÇÃO

### 8.1 Varredura de segredos

Árvore de trabalho **e** histórico. **Nunca reproduza um segredo integral no relatório** —
cite arquivo, linha, tipo e os 4 últimos caracteres no máximo.

```bash
git ls-files | xargs grep -lnE 'AIza|gsk_|nvapi-|sk-[A-Za-z0-9]|ya29\.|-----BEGIN' 2>/dev/null
git log --all -p -S'AIza' --oneline | head
git log --all --diff-filter=A --name-only | grep -iE '\.env|secret|credential|token'
```

**Aviso de falso positivo, a confirmar por você:** esses prefixos aparecem hoje em
arquivos que os usam legitimamente — `config.py` (função de redação), `operational.py`,
`work/orchestrator.py`, `tests/test_control.py` e outros testes (chaves **sintéticas**
declaradas como tal), e documentos que explicam o formato das chaves. A conclusão do
construtor é que **não há segredo real** no repositório. **Isso é exatamente o tipo de
afirmação que você não deve aceitar.** Verifique cada ocorrência e classifique: uso
legítimo, valor sintético, ou segredo real.

Verifique também: `.env` real (deve estar ausente e ignorado), `credentials.json`,
`token.json`, `client_secret*.json`, cookies, dumps, logs com conteúdo sensível, URLs
privadas, IPs.

### 8.2 Dados pessoais e caminhos absolutos

**OBSERVADO na emissão, a confirmar e classificar por você:** a string `/home/ziul`
aparece em **9 documentos rastreados** — `docs/BOOTSTRAP-2026-07-30.md` (várias
ocorrências, incluindo caminhos de backup pessoal), `docs/GOOGLE-WORKSPACE.md`,
`docs/CICLO-2-WATCHER-E-PROVEDORES-2026-08-02.md`, quatro handoffs, um prompt e o
relatório da auditoria anterior. O nome de usuário do mantenedor aparece nesses mesmos
arquivos.

Classifique a severidade honestamente: um nome de usuário de Linux num documento interno
não é um vazamento de credencial. Mas é decisão do mantenedor, e caminhos de backup
pessoal revelam estrutura de máquina. Liste tudo, proponha, não decida.

### 8.3 Peso e higiene do repositório

Na emissão: `docs/audits/2026-08-05-atlas-geral/` tem **51 arquivos rastreados**, dos
quais 33 são PNGs de captura, vários acima de 700 KB — os 12 maiores arquivos rastreados
do repositório são todos capturas dessa pasta. Existe também um
`docs/audits/2026-08-05-atlas-geral.zip` de 1,9 MB **não rastreado** (o `.gitignore`
ignora `*.zip`).

Determine: peso total do repositório (`git count-objects -vH`), fração que são capturas,
e se isso é aceitável para um repositório público. Recomende — não execute.

Verifique ainda: `.gitignore` cobre `runtime/`, `.venv/`, `node_modules/`, caches, `dist/`,
`frontend/public/projection.json`, `.vscode/` e artefatos de empacotamento. Confirme que
nada dessas categorias está rastreado por engano
(`git ls-files | grep -E 'node_modules|\.venv|__pycache__|dist/'`).

### 8.4 Documentação de publicação

Diagnostique, **não crie**:

- `README.md` — descreve o sistema atual? As instruções de instalação funcionam para um
  terceiro? Requisitos (uv, Node 24, pnpm) estão declarados?
- `LICENSE` — existe? Se não, o repositório publicado é "todos os direitos reservados"
  por omissão. Registre como achado bloqueador de publicação, com essa justificativa.
- `CONTRIBUTING`, política de segurança, `.env.example` (existe e não contém valores —
  confirme), documentação de configuração.
- `AGENTS.md` / `CLAUDE.md` (link simbólico para `AGENTS.md`) — são normativos e ficariam
  públicos. Contêm algo que não deveria ser público?

### 8.5 Dependências e licenciamento

```bash
uv pip list --outdated 2>/dev/null || uv run pip list --outdated
cd frontend && pnpm outdated; pnpm audit
```

Separe **risco técnico** (versão obsoleta, vulnerabilidade conhecida) de **risco
jurídico** (licença incompatível, código copiado sem atribuição, asset sem
proveniência). Verifique especialmente: `three` e `troika-three-text` no frontend;
`google-genai`, `groq`, `openai` no backend; e a licença de qualquer fonte, ícone
(`tools/atlas.svg`) ou asset embutido. Se as ferramentas locais não permitirem checagem
de vulnerabilidade, diga **NÃO VERIFICADO** com o motivo, em vez de omitir.

---

## 9. FASE 6 — ROBUSTEZ, PERFORMANCE, DÍVIDA E ACHADOS

### 9.1 Robustez

Em ambiente isolado (`VAULT_CORPUS_DIR` e `VAULT_RUNTIME_DIR` apontando para cópias
temporárias), exercite: provedor offline, resposta inválida, timeout, quota estourada,
rate limit, credencial ausente, credencial inválida, processo morto no meio de escrita,
frontend sem backend, backend sem corpus, corpus inconsistente, arquivo corrompido,
reinício, concorrência. Para cada um: o que o sistema faz, o que ele **diz** que está
fazendo, e se as duas coisas coincidem.

### 9.2 Performance

Meça, não estime — e quando estimar, rotule INFERIDO. Cena global e cena focada: FPS,
draw calls, objetos, heap, GPU. Backend: tempo de `GET /corpus/projection`, custo de
reprojeção completa, comportamento do watcher sob rajada de edições. Escalabilidade: o
corpus tem 81 notas hoje; o que acontece com 800? Se der para simular com corpus
sintético em diretório temporário, faça e registre o método.

### 9.3 Inventário de dívida

Quatro níveis, e use os quatro — chamar tudo de crítico destrói a utilidade da
classificação:

- **Bloqueadora** — impede Alpha ou impede publicação.
- **Alta** — não impede Alpha, mas precisa cair logo.
- **Média** — cabe no backlog da Alpha.
- **Baixa** — refino.

### 9.4 Formato de achado

Cada achado, sem exceção:

```
ID:          F-NN
Severidade:  P0 | P1 | P2 | P3
Domínio:     arquitetura | provedores | quórum | corpus | atlas | runtime |
             segurança | testes | docs | dependências | performance | higiene
Rótulo:      OBSERVADO | MEDIDO | INFERIDO | DECLARADO | NÃO VERIFICADO
Descrição:   o defeito em uma frase
Evidência:   comando + saída, ou arquivo:linha, ou captura
Arquivos:    caminho:linha
Reprodução:  passos exatos
Impacto:     o que quebra, para quem
Probabilidade: quando isso acontece
Consequência:  o que acontece quando acontece
Recomendação:  o que fazer
Fechamento:    condição objetiva e verificável que encerra o achado
```

Achado sem evidência não entra. Suspeita sem evidência entra numa seção separada,
**Hipóteses não confirmadas**, com o experimento que a decidiria.

---

## 10. FASE 7 — CLASSIFICAÇÃO DE DOCUMENTOS E GATES

### 10.1 Documentação

Classifique cada arquivo de `docs/`, mais `README.md`, `AGENTS.md`, `.env.example` e os
dois documentos normativos do corpus (`knowledge/Índice.md`,
`knowledge/Política Epistêmica e de Linkagem.md`) como: **atual**, **parcialmente
atual**, **obsoleto**, **contraditório**, **histórico** ou **normativo**. Aponte quais
não deveriam ser publicados.

### 10.2 Alpha readiness

Defina critérios objetivos **antes** de olhar o resultado, escreva-os no dossiê, e só
então preencha. Sugestão de eixos, que você deve criticar e ajustar:

| Eixo | Critério objetivo proposto |
| --- | --- |
| Integridade do corpus | `make audit` zero em todas as linhas de defeito |
| Gates de código | `make test` e `make lint` zero defeito |
| Fluxo de ponta a ponta | Pelo menos um caminho completo corpus→cena→operação→corpus demonstrável |
| Honestidade de interface | Nenhum controle que aparente capacidade não conectada |
| Segurança | Nenhum segredo real no working tree ou no histórico |
| Robustez mínima | Degrada sem quebrar em: sem backend, sem credencial, sem corpus |
| Observabilidade | Uma falha típica é diagnosticável pelos logs |
| Dados sintéticos | Nenhum caminho produz dado de demonstração sem pedido explícito |

Escolha **exatamente uma** classificação, e faça-a decorrer dos achados:

- **PASS — ALPHA**
- **CONDITIONAL PASS** — com a lista pequena, enumerada e fechada de correções
  obrigatórias
- **HOLD**
- **FAIL**

### 10.3 GitHub readiness

Classificação separada e independente da anterior:

- **PUBLIC READY**
- **READY AFTER SANITIZATION** — com a lista exata de ações antes de qualquer `git push`
  público
- **NOT READY**

---

## 11. ENTREGÁVEIS

Todos em `docs/audits/2026-08-09-ane-geral/` ou na raiz, à sua escolha — declare qual no
manifesto. Não sobrescreva nada da auditoria de 2026-08-05.

### A. `ANE_AUDIT_DOSSIER.md`

1. Resumo executivo — o que é o sistema, em que estado está, decisão final, tudo em uma
   página.
2. Baseline (Fase 0).
3. Arquitetura reconstruída (Fase 1), com os cinco fluxos de ponta a ponta.
4. Inventário funcional — a tabela **existe de verdade / só interface / só documento**.
5. Estado do runtime.
6. Testes — o que passou, o que os testes realmente cobrem, o que não cobrem.
7. Segurança.
8. GitHub readiness.
9. Alpha readiness.
10. Achados, ordenados por severidade.
11. Dívida, nos quatro níveis.
12. Riscos.
13. Recomendações, priorizadas.
14. Decisão final.
15. **Tabela de regressão** contra `FINDINGS.md` de 2026-08-05.

### B. `ANE_REPOSITORY_INVENTORY.txt` — seção 3.3.

### C. `ANE_AUDIT_EVIDENCE.md` — comandos, saídas, commits, hashes, contagens, medições.
Reproduzível: quem rodar os mesmos comandos chega aos mesmos números, ou descobre que
algo mudou.

### D. `ANE_GITHUB_SANITIZATION.md` — tudo a remover, alterar, ignorar ou revisar antes da
publicação. Segredo nenhum em texto integral.

### E. `ANE_ALPHA_GATE.md` — tabela `| Critério | Estado | Evidência | Bloqueador? |` e a
decisão.

### F. `ANE_AUDIT_MANIFEST.txt` — data, branch, HEAD, `git status` de abertura **e** de
fechamento, ambiente, ferramentas e versões, lista de entregáveis, checksums (`sha256sum`)
de cada um.

### Pacote

`ANE_AUDIT_PACKAGE/` com **apenas** o que é seguro compartilhar, e
`ANE_AUDIT_PACKAGE.tar.gz` (preferir tar.gz: preserva permissões, e `*.zip` já está no
`.gitignore` por outro motivo). Sem chaves, tokens, `.env` reais, credenciais, dados
pessoais desnecessários, caches, dependências instaladas ou arquivos gigantes.

### Snapshot para segunda auditoria

Se for seguro, `ANE_REVIEW_SNAPSHOT.tar.gz` com estrutura, código-fonte, testes,
documentação relevante, configs não secretas, manifests e lockfiles. Excluir `.git`,
credenciais, `.env`, caches, builds, dependências vendorizadas, dados pessoais, artefatos
pesados. **Se excluir `.git` eliminar evidência necessária**, inclua no dossiê um
relatório Git detalhado no lugar — histórico resumido, autores, datas, arquivos por
commit — em vez de expor a árvore inteira.

**Um cuidado específico:** `knowledge/` é o produto do projeto e é conteúdo autoral do
mantenedor. Antes de incluí-lo em qualquer pacote compartilhável, registre a decisão
explicitamente no manifesto. Na dúvida, inclua a estrutura e a contagem, não o texto.

---

## 12. NOTAS DO CONSTRUTOR PARA O AUDITOR

**Status epistêmico desta seção inteira: DECLARADO.** São pistas de investigação de quem
escreveu o código, escritas com esforço deliberado de não proteger o próprio trabalho.
Verifique cada uma. Onde eu digo "funciona", trate como hipótese a testar. Onde eu digo
"está frágil", pode estar pior ou melhor do que eu penso.

### 12.1 O que eu construí, e quanto disso é recente

Participei de cerca de 80% da implementação recente, depois que a arquitetura fundamental
já existia. O que passou pelas minhas mãos, em ordem aproximada de peso:

- **A frente visual inteira sob o ADR-002 ("o painel é o nó")** — `docs/ADR-002-painel-como-no.md`.
  Foi a mudança conceitual mais profunda do período: as entidades deixaram de ser esferas
  e passaram a ser painéis legíveis. Isso reescreveu `panels.ts`, `panelBodies.ts`,
  `panelShapes.ts`, `panelTextRenderer.ts`, `panelTextLayout.ts`, `panelScale.ts`,
  `textPool.ts` e boa parte de `atlas.ts`. É a área com mais reformulações do projeto.
- **A composição espacial das nuvens** — `composeLayout.ts`. As camadas (corpus, quórum,
  modelos, provedores) foram assentadas numa calota epistêmica, com ordem semântica na
  altura e não no raio. Passou por pelo menos quatro reformulações em uma semana.
- **A camada viva** — `runtimeLayer.ts`, `runtime.ts`, `operationalLayout.ts`. Eventos de
  execução aparecendo na cena, ancorados no que eles tocam.
- **Painel de controle e credenciais** — `control/` inteiro, `controlApi.ts`,
  `controlBar.ts`, `dock.ts`, `dockModel.ts`.
- **Provedores** — `providers/ollama/`, `aptitude.py`, `inventory.py`, e a separação
  provedor↔modelo no acervo.

### 12.2 Estado que você vai encontrar, e que eu deixei assim

**A árvore está suja, e a mudança não commitada é minha.** Seis arquivos do frontend,
+136 −24. Ela faz três coisas:

1. `runtime.ts` ganha um mapa `entityByTask` construído **antes** do corte dos 160 eventos
   visíveis, porque só `task_created` declara a entidade e nos 160 eventos mais recentes
   da trilha real nenhum a declarava — a camada viva ficava sem nenhuma linha para o
   corpus.
2. `composeLayout.ts` ganha `GIRO_DO_QUORUM = -2.2` e `posto` fracionário, girando a
   nuvem do quórum para entre o raciocínio e o conhecimento.
3. `atlas.ts` ganha `acenderOutraPonta()`, que acende no corpus a entidade do outro lado
   da haste de um evento.

**Não rodei a suíte completa depois dessa mudança nesta sessão.** Trate-a como código não
verificado. E há uma suspeita concreta que eu levanto contra o meu próprio código: tanto
`acenderOutraPonta()` quanto o bloco de ênfase que reage ao foco do corpus **escrevem
`corpos.setEmphasis` sobre todos os slots**. São dois escritores do mesmo estado visual,
e qual vence depende da ordem dos eventos. Se houver piscada de destaque, ênfase presa ou
nó que fica escuro sem motivo, comece por aí. Isso é hipótese minha, não medição.

### 12.3 Decisões arquiteturais que eu tomei, e que podem estar erradas

- **Ordem epistêmica na altura, não no raio.** As nuvens sobem numa calota em vez de se
  afastarem. Resolveu o problema de arestas atravessando a cena; pode ter criado um
  sistema de coordenadas que só faz sentido para quem acompanhou a decisão.
- **`z` é faixa estreita que separa camadas, nunca medida.** Se em algum lugar `z` virou
  quantidade, é regressão conceitual.
- **Analogia não cria aresta.** Regra do corpus que a cena precisa honrar: se a cena
  desenha ligação que a Política não autoriza, é a cena que está errada.
- **Estado sem dica ainda é estado útil.** Aplicado às credenciais (máscara só acima de 12
  caracteres) e à interface em geral: ausência deve aparecer como ausência, nunca como
  zero. Procure onde essa regra foi quebrada — `?? 0` em campo que podia ser `null` é a
  assinatura.
- **Órbita em vez de voo livre.** Foi trocado e destrocado (`8a3f894` → `6b64792`). Se a
  navegação ainda incomodar, essa decisão não estabilizou e merece ser reaberta com dados.

### 12.4 Invariantes pretendidos — verifique se valem

1. Nenhum dado de demonstração entra em cena sem `VAULT_DEMO_OPERATIONAL=1` explícito, e
   nenhuma falha de leitura produz `demo`.
2. Credencial nunca aparece em log, resposta, exceção ou traceback.
3. O corpus só muda por promoção validada em árvore Git temporária.
4. O proponente não conta no próprio quórum; 3 votos válidos e 2 provedores no mínimo.
5. `verified_at` só muda quando houve verificação real de fonte.
6. Toda relação desenhada na cena é uma relação declarada com `relation:` no corpus.
7. A cena limita eventos visíveis (160) sem perder o vínculo histórico entre tarefa e
   entidade.
8. Texto em 3D é alocado por pool e devolvido.

### 12.5 O que eu considero maduro, experimental e provisório

**Maduro, na minha avaliação — que é exatamente o que você deve atacar primeiro:**
leitura do corpus e projeção; `tools/audit.py`; mecanismo de escrita de credencial;
motor de quórum (`quorum/engine.py`, determinístico e bem testado); persistência de
layout.

**Experimental:** a camada viva na cena; a nuvem de modelos e o acervo de provedores; a
aptidão (`aptitude.py`) que classifica endpoints; a composição espacial das nuvens, que
mudou quatro vezes em uma semana e cujo estado atual é o menos testado de todos.

**Provisório, sem eufemismo:**

- `http://127.0.0.1:8000` embutido em cinco módulos do frontend. Não há configuração.
- O worker roda fora da API (`make worker`), e o painel de controle mostra estado dele
  mesmo quando ninguém o está executando. O código admite isso em texto
  (`control/snapshot.py`); a interface, verifique se admite.
- `atlas.ts` com 2.304 linhas é um módulo que faz coisas demais. Sei disso e não dividi.
- Vários números do README podem estar desatualizados. Meça em vez de citar.

### 12.6 Divergência conhecida que eu não resolvi

**Há 39 painéis de quórum gravados em `runtime/quorum/` — execuções que aconteceram de
verdade — enquanto a aba Trabalhadores do painel de controle mostra outra coisa.** Nunca
fechei essa discrepância.

O mecanismo, que eu li em `backend/src/vault/control/snapshot.py:177-201` ao escrever
este prompt: sob AUTO, `_resolve_endpoint()` devolve `usaveis[0]` — **o primeiro endpoint
do catálogo, igual para todos os sete papéis**. A aba mostra, portanto, os sete
trabalhadores com o mesmo provedor e o mesmo modelo. Um painel real que eu inspecionei em
agosto tinha montado Groq + Groq + NVIDIA. Ler a aba como plano de execução leva a
conclusão errada.

Pode ser diferença legítima de recorte — a aba descreveria "o que a política escolheria
agora", e os painéis descrevem "o que a execução de fato usou". Pode ser uma interface
que descreve um sistema diferente do que roda. **Eu não sei qual das duas, e é
exatamente por isso que essa é a primeira coisa que eu mandaria você olhar.** Determine o
que a aba afirma ao usuário, se a afirmação é verdadeira, e se o usuário tem como saber
que ela não é um plano.

Some a isso `runtime/proposals/` vazio, com 39 painéis executados. Eu não sei dizer se
alguma promoção jamais chegou ao corpus por esse caminho. Essa é, na minha avaliação, a
pergunta mais consequente da auditoria inteira, porque ela decide se o núcleo de
governança do projeto é um mecanismo comprovado ou uma máquina completa que nunca
entregou.

### 12.7 O que eu não consegui verificar

- Se a mudança não commitada renderiza corretamente na cena viva.
- Se há vazamento de memória na navegação prolongada — nunca medi sessão longa.
- Se o sistema se comporta com corpus grande; 81 notas é pequeno e nunca testei acima
  disso.
- Se as cotas declaradas dos provedores correspondem às reais sob carga.
- Cobertura efetiva de `operational.py` e `work/orchestrator.py`, os dois maiores módulos
  do backend.
- Se algum claim do corpus atual chegou lá por quórum.

### 12.8 Duas armadilhas de instrumento, aprendidas na prática

- **Teste verde não vale para render.** Os três piores defeitos visuais do projeto
  passaram por suítes verdes e só existiram na cena viva, com tudo ligado. Para o Atlas,
  a evidência é captura.
- **Diff de captura mede tudo que mudou.** Ao comparar dois estados, uma diferença de
  pixels pode vir de texto, halo, contraste ou de um segundo elemento que você não estava
  olhando. Nomeie a qual causa você atribui a diferença antes de registrar o achado. Eu
  quase reportei um defeito de cor que era outra coisa.

### 12.9 Arquivos e commits que merecem sua atenção primeiro

| Alvo | Por quê |
| --- | --- |
| `frontend/src/atlas.ts` | 2.304 linhas, concentra montagem, navegação, seleção, ênfase |
| `backend/src/vault/work/orchestrator.py` | 1.328 linhas, decide quem executa o quê |
| `backend/src/vault/operational.py` | 1.115 linhas, ponte entre execução real e representação |
| `frontend/src/composeLayout.ts` | quatro reformulações em uma semana, e mais uma não commitada |
| `frontend/src/contract.ts` | define o que a cena pode saber |
| `backend/src/vault/promotion/promoter.py` | única coisa que protege o corpus de escrita indevida |
| `backend/src/vault/control/snapshot.py` | onde a divergência da 12.6 provavelmente mora |
| `git diff` (não commitado) | código mais novo e menos verificado do projeto |
| `d8264f4`, `78ac5df`, `61f2da4` | os três últimos commits, todos na área menos estável |
| `docs/audits/2026-08-05-atlas-geral/FINDINGS.md` | sua própria auditoria anterior, para medir regressão |

---

## 13. REGRA FINAL

Não economize rigor para proteger trabalho já feito — nem o meu, nem o seu de agosto.
O valor desta etapa está em encontrar problemas **antes** da Alpha e **antes** da
publicação pública, quando consertar ainda é barato.

Três compromissos:

1. **Se as Notas do Construtor estiverem erradas, diga que estão erradas**, com a
   evidência. Elas foram escritas para serem contestadas.
2. **Se o sistema não estiver pronto, diga que não está**, e diga exatamente o que falta,
   em condições de fechamento verificáveis.
3. **Se estiver pronto, diga isso também** — sem inflar a lista de achados para parecer
   rigoroso. Rigor é a distância entre a afirmação e a evidência, não o número de
   problemas encontrados.

Não implemente correções nesta passagem. Não commite. Não faça push. Não apague arquivos.
Não toque no corpus canônico. Entregue o pacote, e preserve o estado original — inclusive
a árvore suja com que você começou.
