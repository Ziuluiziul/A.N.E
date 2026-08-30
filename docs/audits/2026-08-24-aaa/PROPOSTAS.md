# Programa AAA — propostas, na ordem que destrava

Cada incremento entrega capacidade utilizável. Nenhum existe só para preparar o
próximo. Corpus continua fechado à escrita direta: restauração e expansão passam
pelo Promoter ou por commit humano explícito nos quatro casos do regime.

---

## Ciclo 0 — parar o sangramento (hoje, um commit de código)

Sem isto, o resto é teatro: o Promoter queima toda aprovação enquanto a árvore
tiver o diff de `generator.py`.

1. **Stash ou commit o WIP do gerador antes de qualquer promote.** Não misturar
   com o resto. Se o patch do gerador for entrar, cortar `_note_extension` e
   `_undeclared_moc_growth` até haver lacuna declarada — ou o gerador fabrica
   demanda contra a regra 4.
2. **Árvore suja não é terminal.** O Promoter já aplica em worktree isolada.
   Inspecionar o checkout do operador é o defeito. Tratar dirty-tree como
   `failed` (reaplicável) ou, melhor, **não exigir working tree limpa** quando o
   lock do `git-common-dir` e a worktree temporária já isolam o commit.
   `rejected` reserva-se a recusa epistêmica/estrutural do patch.
3. **Assimilação falha ≠ `promote`.** `worker.py:855` devolve o outcome real
   (`failed` / `rejected` / `stale`). Teste que quebra se a exceção virar sucesso.
4. **`admit_patch` recusa ata de runtime no corpo.** Heurística barata: heading
   `Painel` / `Decisão do painel` / IDs hex de 12 chars como seção. Recusa
   `replace` que quebra `$...$` / `$$...$$` (tokens LaTeX desbalanceados ou
   `\operatorname` seguido de lixo). Recusa remoção de DOI/arXiv/ISBN sem
   `allows_reduction`.

Aceite: com a árvore suja de propósito, um patch de fixture ainda promove; uma
exceção no Promoter não marca a tarefa `completed`; um patch que insere
`## Decisão do painel` é recusado antes do quórum gastar avaliadores.

---

## Ciclo 1 — restaurar o corpus (quatro patches mínimos, um quórum cada)

A origem `corpus_defect` (e a `policy_review` quando a Política omite o regime)
já enfileira ata, LaTeX mutilado, título de Klein corrompido e a emenda do
regime. ISBN ausente continua painel dirigido: só entra depois de resolver na
fonte. `make quorum` aceita `--alvo` e anexa o Markdown canônico.

Não é expansão. É desfazer dano medido. Cada patch é um `replace` de poucas
linhas, com `updated` tocado e sem mexer em claim status.

| ordem | alvo | restauração |
|---|---|---|
| 1 | MQ e Sistemas Abertos L60 | `\operatorname{Tr}_E\!\big[` |
| 2 | Cordas L82 | `fünfdimensionale` (como em `Referências Verificadas de Física.md:41`) |
| 3 | Filosofia da Ciência L68 | repor ISBN `978-0-226-61865-4` depois de resolver no Crossref |
| 4 | CNS + Complexidade | apagar as seções de ata; o julgamento fica no painel, não na nota |

Em paralelo, **emendar a Política** (nota operacional, não ciência): registrar o
regime de 2026-08-03 — quórum promove, humano só nos quatro casos, Promoter é o
único escritor, `updated` muda a cada edição. Enquanto a Política disser
"revisão humana", o AGENTS está formalmente errado ou as promoções são ilegítimas.

Aceite: as quatro linhas voltam ao texto pré-dano; Política e AGENTS deixam de
se contradizer; `make audit` continua 0.

---

## Ciclo 2 — o gate passar a ver identificador

A regra 1 sem máquina é teatro honesto. AAA exige o nível 1 da própria Política.

1. `tools/resolve_sources.py` — stdlib + HTTP: DOI via Crossref, arXiv via
   export, ISBN via Open Library. Cache em `runtime/state/sources/` (não é
   conhecimento).
2. Matching como a Política já descreve: só normalização de caixa / Unicode /
   pontuação. Mismatch = defeito. Sem rede = `SKIP` explícito, nunca aprovação.
3. `make audit` ganha um alvo opcional `make audit-fontes`. O gate estrutural
   **não** passa a depender de rede no CI (o runner não deve mentir "aprovado"
   sem resolver). CI ganha job separado `fontes` com cache, `continue-on-error`
   até a primeira baseline humana aceitar os mismatches reais.
4. Toda promoção futura recusa linha cuja evidência cite DOI/arXiv/ISBN que o
   resolvedor marque `mismatch`.

Aceite: as 91+71+34 ocorrências têm um manifesto `ok|mismatch|unresolved`;
zero mismatch silencioso entra depois da data de corte.

---

## Ciclo 3 — fechar ADRs aceitas ou desligá-las

Não deixar decisão "aceita" sem caminho quente.

**ADR-007.** Ou o teto 24 governa o fechamento (e `SWITCH` tem ramo), ou
`policy.json` declara `inert: true` e `make outcomes` para de contar no-ops
como política. Meio-termo atual — 1304 linhas `decision: null` com
`max_calls≈91k` — é o pior dos dois.

**ADR-005.** Uma autoridade só: `runtimeLayer` é dona de QUÓRUM / MODELOS /
PROVEDORES / TRABALHADORES. Projeção deixa de receber `with_runtime_quorum`.
Watcher de corpus reassenta âncoras sem `location.reload()`. Aceite da própria
ADR: acrescentar 32 painéis não move MOC; fingerprint nova não recarrega a
página.

**ADR-006.** Primeira tarefa de código **depois** do ciclo 0: um arquivo fora
da denylist, diff < 40 linhas, `validate_code` no caminho `promote()`. Sem
gerador autônomo ainda — uma `make quorum` dirigida. Se os três gates na
worktree passarem, o commit local acontece. `git push` continua humano.

**M0.** Ou o ledger canônico volta a ser escrito no ciclo quente, ou
`make outcomes` lê só as fontes vivas (`tasks.json`, painéis, diário) e o
`outcomes.jsonl` de 17/08 vira arquivo. Duas verdades é pior que uma velha.

**M3.** Não começar. Sem resolução de fonte (ciclo 2) e sem sobrevivência do
patch (L4) não há desfecho independente. Calibrar revisor agora produz número
com aparência estatística.

---

## Ciclo 4 — Atlas no nível do contrato que já tem

O contrato visual é o pedaço mais "produto" do frontend. Falta fechá-lo.

1. Partir `atlas.ts` sem mudar comportamento: câmera, seleção, texto, overlay
   operacional. Cada fatia nasce com o teste que hoje só existe em
   `visual.test.ts` / `layout.test.ts`.
2. Modo texto carrega o corpo da nota (o mesmo Markdown que o painel 3D já
   renderiza). Sem isso, `?texto=1` não é acessível — é um índice.
3. Uma captura determinística por viewport (`1280×720`, `1440×1000`) no
   harness, comparada a baseline em `frontend/fixtures/`. Sem GPU no CI:
   SwiftShader como na auditoria de 09/08, ou o job `visual` fica `manual`.
4. `prefers-reduced-motion` e `#live` já existem; falta axe no modo texto e
   um roteiro de teclado (Tab / Esc / / / G) com asserção de foco.

Aceite: regressão de overlap das placas quebra o job visual; leitor de tela
lê o texto da nota selecionada; `atlas.ts` < 1200 linhas.

---

## Ciclo 5 — crescimento do corpus sob a emenda de 2026-07-28

Só depois dos ciclos 0–2. Expandir agora replica o padrão das 18 promoções.

Ordem de lacuna **já declarada** nos MOCs, uma nota completa por vez:

1. **Camada 3 oca:** modelo relacional **ou** preservação/FAIR (Dados hoje é
   1 nota, 2 claims).
2. **Python:** typing **ou** testes — o MOC já pede; o Vault é a linguagem de
   trabalho.
3. **Método:** a Ética/sociologia fica de fora até haver fonte primária e
   função. Não criar pasta.
4. **Domínios no limiar** (Vida, Segurança, Cognição): não abrir assunto novo
   sem consumidor. Preferir aprofundar nota existente a nascer MOC.

Toda nota nova: Finalidade, Escopo com negativo, Pré-requisitos, Conceitos,
tabela de claims, Limites, Fontes com identificador **já resolvido**, Condição
de revisão. Física/IA existentes ganham esse esqueleto só quando um painel
tocar a nota por outra razão — não há ciclo de "normalizar template".

Amostragem humana das 164 `established` e das 33 `refuted`: 10+10 notas, nível
2 da Política. O auditor não substitui isso. Sem essa amostra, AAA epistêmico
é declaração.

---

## O que deliberadamente não fazer

- Morphogenic Runtime / M5 tecido pleno. ADR-003 continua certa: emergência
  sobre sinal podre produz adaptação ao ruído. O sinal hoje inclui promote
  falso e ledger morto.
- Gerador inventando nota porque a fila esvaziou.
- Score único de revisor. Diversidade continua piso, aptidão só reordena.
- Resolver DOI no `make audit` do CI sem cache e sem job separado.
- Reescrever `orchestrator.py` / `operational.py` "para ficar limpo".
- Quarentena em massa de claims `established`. Ausência de releitura ≠
  `refuted`.

---

## Sequência e dono

| ciclo | dono | confirmação humana? |
|---|---|---|
| 0 código (dirty-tree, outcome, admit_patch) | agente, gates verdes, commit | não |
| 0 stash do gerador | quem dono do diff | não, se for stash; commit se for o patch |
| 1 restauração do corpus | quórum + Promoter | não, salvo se o Promoter recusar |
| 1 emenda da Política | quórum (nota operacional) ou mantenedor | não |
| 2 resolvedor de fontes | agente + job CI `fontes` | primeira baseline de mismatches |
| 3 ADR-005 / 006 / 007 | agente | `git push` continua humano |
| 4 Atlas | agente; visual job pode ser manual | não |
| 5 notas novas | quórum; identificador pré-resolvido | se a rede/orçamento estourar |
| amostra nível 2 | humano ou modelo com PDF na mesa | **sim** — é leitura |

O único ciclo que o operador precisa disparar agora: **ciclo 0.1 — tirar o
diff da frente do Promoter.** Sem isso, AAA é documento.
