# Handoff — GPT-5.6 SOL Ultra — finalização — 2026-08-04

Estado real depois da passagem do Claude Opus 5 UltraCode. O SHA deste commit não
aparece aqui: um documento não pode conter o identificador do commit que o contém.

## HEAD

Filho direto de `106cf29`, com o assunto:

```text
Fecha o laço até o corpus e prova o quórum com três provedores
```

Confirme com `git log --oneline -3`. Se houver commits posteriores, audite-os antes
de agir.

## Estado verificado nesta passagem

```text
corpus       81 notas · 627 wikilinks · 267 claims · manifesto 4f5b1d00… (intocado)
testes       274 pytest · 69 vitest
gates        audit, ruff, mypy, tsc, eslint limpos
árvore       limpa
```

## Endpoints — medidos, não presumidos

```text
google   gemini-3.5-flash-lite         ok            produtivo
groq     qwen/qwen3.6-27b              ok            produtivo
groq     llama-3.3-70b-versatile       ok            produtivo
groq     llama-3.1-8b-instant          ok            produtivo
nvidia   z-ai/glm-5.2                  ok            produtivo
google   gemini-3.6-flash              reachable     200 sem texto sob teto antigo
google   gemini-3.5-flash              reachable     200 sem texto sob teto antigo
nvidia   deepseek-ai/deepseek-v4-flash unavailable   529 sobrecarga
nvidia   deepseek-ai/deepseek-v4-pro   unavailable   timeout em 30s
```

**Três provedores produtivos.** O Google saiu de `reachable` para `ok` porque o
orçamento da sonda subiu de 16 para 512 tokens de saída: com 16, modelo de raciocínio
interno gastava o teto pensando e devolvia 200 vazio, e a sonda media o próprio limite
em vez do endpoint. Os dois `reachable` antigos não foram re-sondados — a seleção
prioriza endpoint nunca testado, por incerteza decrescente. Re-sondá-los sob o teto
novo provavelmente os converte.

## Execução real ponta a ponta

Um quórum multimodelo rodou com chamadas reais e formou painel completo:

```text
painel        c3ace8dbfb20
proponente    google/gemini-3.5-flash-lite
avaliadores   groq/qwen3.6-27b [qwen3, verificador-factual]
              groq/llama-3.3-70b-versatile [llama, critico-epistemologico]
              nvidia/z-ai/glm-5.2 [glm, revisor-estrutural]
decisão       reject — falha estrutural objetiva
```

O revisor estrutural pegou violações **reais** da política do corpus: claims sem ID no
formato `CLM-DOMINIO-TOPICO-NNN`, status fora do vocabulário fechado, e uma relação
inventada (`is_distinct_from`) fora do vocabulário permitido. A máquina recusou o que
deveria recusar. Evidências em `runtime/quorum/c3ace8dbfb20/`.

**Achado operacional:** os dois votos da Groq vieram com schema inválido e contaram
como abstenção. Só o voto da NVIDIA foi válido. A taxa de aderência ao schema de voto
por endpoint é a primeira coisa a medir e corrigir — sem ela o quórum degrada para
avaliador único e nunca alcança os 3 votos válidos exigidos.

## Implementado nesta passagem

**Proposal Promoter** (`backend/src/vault/promotion/`) — o único componente autorizado
a escrever em `knowledge/`. Guardas, cada uma com teste que a faz morder:

- recomputa o quórum a partir dos votos, não lê `decision.json`;
- recusa patch cujo digest divirja do registrado no painel;
- recusa proponente entre avaliadores, mesmo em painel montado por outro processo;
- exige 3 votos válidos, 2 provedores, 2 famílias;
- recusa base divergente do HEAD;
- aplica em worktree temporária, roda `tools/audit.py` e a projeção sobre o
  **resultado**, confere que o diff bate exatamente com os alvos declarados;
- só então avança o corpus vivo por `merge --ff-only` — nunca fica meio escrito;
- reverte por commit compensatório.

O patch é conteúdo integral, não hunks: diff depende do estado do arquivo na hora da
aplicação, e é aí que mora a diferença entre o que foi votado e o que entra.

**Supervisor único** (`tools/atlas.sh`) — `make dev` e o ícone do GNOME agora
compartilham o mesmo mecanismo, com `VAULT_ATLAS_OPEN=0` como única diferença. O
defeito conhecido do `make dev` está fechado: ele punha os serviços em sessões
próprias com `setsid` e guardava o PID errado, deixando uvicorn órfão na porta 8000.
Verificado com SIGINT e SIGHUP: zero listeners, zero processos.

**`make promote PAINEL=<id>`** — lista painéis, `--dry-run` roda todas as guardas sem
commitar.

## Arquivos principais

```text
backend/src/vault/promotion/patch.py     patch com digest, alvos e aplicação atômica
backend/src/vault/promotion/promoter.py  guardas, worktree, auditoria, commit, revert
backend/src/vault/quorum/                voto estruturado, parser, motor, síntese
backend/src/vault/work/                  orquestrador, papéis, cotas, histórico
providers/aptitude.py                    classificação e ordem de preferência
providers/inventory.py                   junção consultável das três fontes
tools/atlas.sh                           supervisor único (dev e ícone)
tools/promote.py                         CLI da promoção
```

## Pendências concretas — o que falta para o aceite visual

Nada do que segue foi implementado nesta passagem. É o trabalho restante, em ordem de
dependência:

1. **Event bus operacional em tempo real.** Hoje existe `corpusRevision` via SSE em
   `/corpus/events`, alimentado por `CorpusProjectionWatcher`. Falta o
   `runtimeRevision` independente e os eventos do §8 (`task_created` … `corpus_changed`).
   A camada operacional em `backend/src/vault/operational.py` já projeta painéis de
   quórum lendo `runtime/quorum/` — ela é o ponto de enxerto, não um começo do zero.
2. **Gerador contínuo de tarefas.** Não existe. Deve nascer de lacunas do corpus,
   claims frágeis, notas isoladas, divergências entre modelos e falhas de endpoint.
3. **Worker autônomo.** Não existe. O orquestrador executa lotes sob demanda
   (`make work`, `make quorum`), respeitando cota por endpoint, por provedor e por
   execução. Falta o laço contínuo que sobrevive a reinício e distribui ao longo das
   janelas.
4. **Painéis 3D vivos e profundidade visual.** O Atlas segue como estava: tecnicamente
   correto, visualmente contido. Nenhum dos 20 itens do §5 foi tocado.
5. **Proposta com patch vinda de modelo.** O Promoter está pronto e testado, mas nada
   ainda **produz** um `CorpusPatch` a partir de uma proposta de modelo. `QuorumStore`
   já tem `save_patch`/`load_patch`; falta o proponente emitir patch estruturado.
6. **Aderência ao schema de voto na Groq.** Ver achado acima.

## Critérios de aceite ainda não cumpridos

Dos 19 itens do §15, estão cumpridos: quórum se formando (13), proposta sendo
rejeitada (14), fechamento sem órfãos (19). Os demais dependem das pendências 1 a 4.

Promoção criando commit (15), corpus mudando (16) e Atlas incorporando (17) estão
**implementados e testados**, mas nunca dispararam sobre `knowledge/` porque nenhuma
proposta chegou aprovada com patch.

## Fontes oficiais que determinaram decisões

- `git worktree` — modelo de árvore vinculada usado para validar o patch fora do
  corpus vivo, e `merge --ff-only` para publicar sem estado intermediário.
- Especificação Desktop Entry do freedesktop.org — uma única categoria principal, para
  o app não aparecer repetido no menu; validado com `desktop-file-validate`.
- Semântica POSIX de grupo de processos e `set -m` do Bash — cada serviço em segundo
  plano vira líder do próprio grupo, o que torna `kill -- -PGID` correto. É o que
  corrige o órfão do `make dev`.
