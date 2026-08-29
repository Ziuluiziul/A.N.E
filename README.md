# A.N.E.

**Atlas Neural-Epistêmico.** Corpus acadêmico interdisciplinar vivo e o sistema
que o projeta num Atlas 3D, delibera por quórum multimodelo e promove o que
passou nas guardas. O corpus é o produto; o resto é o mecanismo que o sustenta.

O corpus vive em `knowledge/` e **nunca recebe código**. As contagens vivas —
notas, wikilinks, claims — são as que `make audit` imprime; não as fixe aqui.

## Começar

```bash
make setup
```

Instala as dependências Python em `.venv` a partir de `uv.lock` e as do frontend a
partir de `pnpm-lock.yaml`. Requer `uv`, Node 24 e `pnpm` no PATH.

```bash
make audit
```

Auditoria estrutural do corpus, somente leitura, com a guarda de redução: cada
nota é comparada com `HEAD`, e perder claims, wikilinks ou mais da metade dos
bytes sem declaração reprova. Zero em todas as linhas de defeito, ou a alteração
não está pronta — ver `AGENTS.md`. Para medir a redução contra outra referência,
`make audit-reducao REF=<ref>`.

## O Atlas

```bash
make dev
```

Projeta `knowledge/` em `frontend/public/projection.json`, sobe o backend em
`http://127.0.0.1:8000`, o Atlas em `http://127.0.0.1:5173` e o worker autônomo.
Use `VAULT_AUTONOMOUS_WORKER=0 make dev` quando quiser apenas observar, sem
chamadas de modelo.

O navegador fala com a API por caminhos da mesma origem. No desenvolvimento e em
`pnpm --dir frontend preview`, o Vite encaminha `/api`, `/corpus`, `/runtime`,
`/layout` e `/operational-layout` para `VAULT_VITE_PROXY_TARGET` (por padrão,
`http://127.0.0.1:8000`). Um build estático precisa do mesmo reverse proxy no
servidor que o publicar.

O Atlas é volumétrico e ancorado: os MOCs ocupam posições persistentes num anel,
cada nota orbita a sua âncora, e `z` é uma faixa estreita que separa camadas —
nunca uma medida. A forma distingue o tipo de entidade, a matiz distingue o
domínio, e o padrão da linha distingue a relação. Nenhuma informação depende só
de cor.

A exploração é progressiva. A visão global mostra territórios e os filamentos
agregados entre MOCs; as relações individuais aparecem ao selecionar uma entidade
ou aproximar um território. Não há barra nem painel lateral permanente: a leitura
acontece numa superfície tridimensional ao lado da entidade. `Esc` abre a
configuração quando nada está selecionado.

| Ação | Como |
| --- | --- |
| Girar / aproximar | arrastar / rolar |
| Andar | `W` `A` `S` `D` |
| Selecionar | clique parado sobre a entidade |
| Recentrar a câmera | duplo clique, ou `Enter` com algo selecionado |
| Buscar uma entidade | `Ctrl+K` (ou `/`) abre a busca; `Esc` fecha |
| Voltar à visão global | `G` |
| Limpar a seleção | `Esc` |

As posições são lembradas entre sessões, em `runtime/state/layout/`, indexadas
pela impressão digital do corpus. Uma nota nova é assentada sem mover o que já
estava no lugar — e nenhuma dessas coordenadas é conhecimento.

## Sem WebGL, ou sem enxergar

```text
http://127.0.0.1:5173/?texto=1
```

O modo textual substitui a cena — não é um painel ao lado dela — e é ativado
automaticamente quando o WebGL não inicializa. Tem busca sem acento e sem caixa,
detalhe estruturado por entidade e a lista de ligações. Somente leitura.

## Camada operacional

O Atlas desenha procedência sem misturá-la ao corpus. Eventos em `/runtime/events`
atualizam painéis de endpoint, tarefa e quórum sem recarregar o corpus. Texto
livre de modelo, prompts e blocos `<think>` não atravessam essa fronteira.

```bash
make quorum TAREFA="Proponha uma correção pequena para ..."
make worker ARGS=--dry-run   # fila derivada, sem persistir nem chamar
make worker ARGS=--once      # no máximo uma tarefa dentro da cota
make worker                  # geração e execução contínuas
make promote PAINEL=<id>     # aplica um patch aprovado até o commit
```

O quórum escolhe um proponente, exige um `CorpusPatch` fechado, monta avaliadores
em endpoints diversos e guarda o artefato votado. Empate usa árbitro independente
quando há endpoint e cota; caso contrário termina em `escalate`. O worker deriva
tarefas de claims fracos, notas isoladas e falhas observadas; a fila vive em
`runtime/state/autonomy/` e admite um único processo por vez.

Uma decisão `promote` com patch válido só entra no corpus pelo Promoter: ele
recompõe o quórum, confere digest e base Git, aplica em worktree temporária,
audita, projeta, commita e só então avança por fast-forward.

`VAULT_WORK_MAX_CALLS` limita as chamadas do processo; `VAULT_WORKER_CONCURRENCY`
e `VAULT_PROVIDER_CONCURRENCY` limitam tarefas e provedores. Para ver a gramática
visual da camada antes de haver dados reais: `VAULT_DEMO_OPERATIONAL=1 make dev`.

## Comandos

| Comando | O que faz |
| --- | --- |
| `make setup` | Instala dependências Python e Node pelos lockfiles |
| `make audit` | Auditoria estrutural + guarda de redução contra `HEAD` |
| `make test` | pytest, `tsc --noEmit` e Vitest |
| `make lint` | Ruff, mypy e ESLint |
| `make dev` | Backend, frontend e worker sob um supervisor único |
| `make backend` | Só a API, com reload |
| `make frontend` | Só a cena 3D |
| `make corpus-graph` | Projeta o corpus em `frontend/public/projection.json` |
| `make discover-models` | Inventaria os endpoints disponíveis em cada provedor |
| `make endpoints` | Consulta o inventário descoberto sem tocar na rede |
| `make smoke-providers` | Uma chamada mínima por provedor |
| `make work TAREFA="..."` | Distribui trabalho entre endpoints produtivos |
| `make quorum TAREFA="..."` | Produz proposta, coleta votos e decide o painel |
| `make worker ARGS="..."` | Deriva e executa a fila autônoma persistente |
| `make promote PAINEL=<id>` | Promove um patch aprovado até o commit |
| `make workspace-oauth` | Consentimento OAuth do Workspace e uma leitura mínima |
| `make icon` | Instala o lançador GNOME do A.N.E. |

## Estrutura

```
knowledge/     corpus canônico e sua política — nunca recebe código
backend/src/   pacote Python interno `vault`: configuração, leitura do corpus, API
providers/     um adaptador por provedor: google, groq, nvidia, ollama, nous, openrouter
integrations/  Google Workspace (OAuth do usuário, distinto da API Gemini)
frontend/      Atlas 3D em TypeScript e Three.js
tools/         scripts curtos que o Makefile chama, incluindo o auditor
tests/         testes Python
docs/          ADRs e o guia do Workspace
runtime/       estado local: propostas, logs, banco — ignorado pelo Git
```

## Credenciais

As chaves ficam em `~/.config/ane/secrets.env` (canônico), com permissão 600, fora
do repositório. Se esse arquivo não existir, o caminho legado
`~/.config/vault-autodidata/secrets.env` continua aceito. `.env.example` explica
cada variável sem conter valor nenhum. Sem credencial, os adaptadores simplesmente
não são construídos: o corpus e a cena 3D não dependem de nenhum provedor.

Provedores desta fase: Google (API Gemini, free tier), Groq, NVIDIA NIM Free,
Ollama Cloud, Nous Research (`:free`) e OpenRouter (somente variantes `:free` com
preço zero). Nenhum papel permanente é atribuído a modelo. No OpenRouter o
adaptador recusa qualquer ID que não termine em `:free`; o gateway pode executar
trabalho comum e propor, mas não avaliar nem sintetizar um quórum enquanto a
proveniência do upstream não integrar a identidade do painel.

A validação de chave do painel não passa por listar modelos nos provedores de
catálogo público: cada adaptador diz em `verify_credential()` qual chamada prova
a sua chave, sem gerar conteúdo.

## Limites deliberados

Modelo e worker nunca escrevem diretamente em `knowledge/`: só o Proposal Promoter
altera o corpus, e apenas para um patch aprovado, amarrado ao artefato votado e ao
HEAD avaliado. Não há cron ou serviço de sistema instalado, nem escrita em Gmail,
Calendar, Drive ou Docs. Credenciais, OAuth interativo, comandos administrativos e
consumo acima do orçamento continuam fora da autonomia silenciosa.
