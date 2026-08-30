# A.N.E.

**Atlas Neural-Epistêmico.** Ambiente autodidata interdisciplinar em torno de um
corpus acadêmico. O corpus é o produto; o resto é código de apoio a ele.

O corpus vive em `knowledge/`. As contagens vivas — notas, wikilinks, claims — são
sempre as que `make audit` imprime; não fixe números aqui. O histórico Git inclui a
tag `baseline-pos-migracao-2026-07-30`. O identificador técnico do repositório e do
pacote Python continua `vault-autodidata` / `vault`; o nome do sistema é A.N.E.

## Começar

```bash
make setup
```

Instala as dependências Python em `.venv` a partir de `uv.lock` e as do frontend a
partir de `pnpm-lock.yaml`. Requer `uv`, Node 24 e `pnpm` no PATH.

```bash
make audit
```

Auditoria estrutural do corpus, somente leitura, e agora também a guarda de redução:
cada nota é comparada com `HEAD`, e perder claims, wikilinks ou mais da metade dos
bytes sem declaração reprova. Zero em todas as linhas de defeito, ou a alteração não
está pronta — ver `AGENTS.md`. Para medir a redução contra outra referência,
`make audit-reducao REF=<ref>`.

## O Atlas Neural-Epistêmico

```bash
make dev
```

O comando projeta `knowledge/` em `frontend/public/projection.json`, sobe o backend em
`http://127.0.0.1:8000`, o Atlas em `http://127.0.0.1:5173` e o worker autônomo. Use
`VAULT_AUTONOMOUS_WORKER=0 make dev` quando quiser apenas observar, sem chamadas de
modelo.

O navegador fala com a API por caminhos da mesma origem. No desenvolvimento e em
`pnpm --dir frontend preview`, o Vite encaminha `/api`, `/corpus`, `/runtime`,
`/layout` e `/operational-layout` para `VAULT_VITE_PROXY_TARGET` (por padrão,
`http://127.0.0.1:8000`). Um build estático precisa do mesmo reverse proxy no servidor
que o publicar; não há origem cross-site escondida no bundle.

O Atlas é volumétrico e ancorado: os MOCs ocupam posições persistentes num anel, cada
nota orbita a sua âncora, e `z` é uma faixa estreita que separa camadas — nunca uma
medida. A forma distingue o tipo de entidade, a matiz distingue o domínio, e o padrão
da linha distingue a relação, de modo que nenhuma informação dependa só de cor.
Volumes recebem luz e sombra coerentes, relações têm espessura e oclusão próprias, e
as superfícies operacionais ficam conectadas às entidades por tethers espaciais.

A exploração é progressiva. A visão global mostra territórios e os filamentos
agregados entre MOCs; as relações individuais aparecem ao selecionar uma entidade ou
aproximar um território. Exibir todas as arestas de uma vez produziria um emaranhado
em que nenhuma pergunta se responde.

Não há barra nem painel lateral permanente: a navegação usa gestos e teclado, e a
leitura acontece numa superfície tridimensional ao lado da entidade. `Esc` abre a
configuração quando nada está selecionado. Uma placa mínima no rodapé declara se
corpus e runtime estão vivos, reconectando ou em modo offline.

| Ação | Como |
| --- | --- |
| Girar / aproximar | arrastar / rolar |
| Andar | `W` `A` `S` `D` |
| Selecionar | clique parado sobre a entidade |
| Recentrar a câmera | duplo clique, ou `Enter` com algo selecionado |
| Buscar uma entidade | `Ctrl+K` (ou `/`) abre a busca; `Esc` fecha |
| Voltar à visão global | `G` |
| Limpar a seleção | `Esc` |

As posições são lembradas entre sessões, em `runtime/state/layout/`, indexadas pela
impressão digital do corpus. Uma nota nova é assentada sem mover o que já estava no
lugar — e nenhuma dessas coordenadas é conhecimento: não medem verdade, importância
nem confiança.

## Sem WebGL, ou sem enxergar

```text
http://127.0.0.1:5173/?texto=1
```

O modo textual substitui a cena — não é um painel ao lado dela — e é ativado
automaticamente quando o WebGL não inicializa. Tem busca sem acento e sem caixa,
detalhe estruturado por entidade e a lista de ligações. Somente leitura, como o resto.

## Camada operacional

O Atlas desenha procedência sem misturá-la ao corpus. O fluxo `/runtime/events` tem
`runtimeRevision` próprio e atualiza, sem recarregar o corpus, painéis 3D de endpoint,
tarefa e quórum. Painéis persistidos em `runtime/quorum/` mostram membros, votos
estruturados e decisão; texto livre de modelo, prompts e blocos `<think>` não
atravessam essa fronteira. Na ausência de execuções, a camada continua vazia.

```bash
make quorum TAREFA="Proponha uma correção pequena para ..."
```

O comando escolhe um proponente, exige dele um `CorpusPatch` fechado, monta três
avaliadores em endpoints diversos, calcula a decisão e guarda exatamente o artefato
votado. Empate usa um árbitro independente quando há endpoint e cota; caso contrário
termina explicitamente em `escalate`. Para avaliar texto sem produzir patch, use
`ARGS=--texto-livre`.

O worker deriva tarefas de claims fracos, notas isoladas, domínios pouco cobertos,
divergências, rejeições, falhas de endpoint e capacidade ociosa:

```bash
make worker ARGS=--dry-run   # mostra a fila derivada, sem persistir nem chamar
make worker ARGS=--once      # executa no máximo uma tarefa dentro da cota
make worker                  # mantém geração e execução contínuas
```

A fila fica em `runtime/state/autonomy/`, sobrevive a reinício e admite um único
worker por vez. Não há retry escondido: uma falha fecha a tentativa e a próxima usa
outros endpoints. `VAULT_WORK_MAX_CALLS` limita as chamadas do processo; quando nada
cabe, as tarefas permanecem na fila sem fabricar tentativas.

`VAULT_WORKER_CONCURRENCY` limita quantas tarefas podem avançar juntas e
`VAULT_PROVIDER_CONCURRENCY` põe o teto em voo de cada provedor como um objeto JSON.
O worker sobe esses números até o RPM/RPD que a documentação autoriza (Google e Groq
por modelo; NVIDIA 40 RPM agregados). Zero no mapa continua sendo pausa explícita.
Sem número na fonte (Ollama Cloud, Nous, OpenRouter) o valor configurado permanece.
A cota por endpoint é que corta — o semáforo deixa o mesmo modelo ter dezenas em voo
para a morfologia (ADR-003) ter chamada aberta de verdade.

Uma decisão `promote` com patch válido pode percorrer o caminho completo:

```bash
make promote PAINEL=<id>
```

O Promoter recompõe o quórum, confere digest e base Git, aplica em worktree temporária,
audita, projeta, commita e só então avança o corpus por fast-forward.

Para ver a gramática visual dessa camada antes de haver dados reais:

```bash
VAULT_DEMO_OPERATIONAL=1 make dev
```

A projeção passa a declarar `operationalSource: demo`; com painéis reais e demo ao
mesmo tempo, declara `mixed`.

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

## Estrutura

```
knowledge/     corpus canônico e sua política — nunca recebe código
backend/src/   pacote Python `vault`: configuração, leitura do corpus, API
providers/     um adaptador por provedor: google, groq, nvidia, ollama, nous, openrouter
integrations/  Google Workspace (OAuth do usuário, distinto da API Gemini)
frontend/      Atlas 3D em TypeScript e Three.js
tools/         scripts curtos que o Makefile chama, incluindo o auditor
tests/         testes Python
docs/          documentação técnica
runtime/       estado local: propostas, logs, banco — ignorado pelo Git
```

## Credenciais

As chaves ficam em `~/.config/vault-autodidata/secrets.env`, com permissão 600, fora do
repositório. `.env.example` explica cada variável sem conter valor nenhum. Sem
credencial, os adaptadores simplesmente não são construídos e o resto do sistema
funciona igual — o corpus e a cena 3D não dependem de nenhum provedor.

Provedores desta fase: Google (API Gemini, free tier), Groq (conta gratuita), NVIDIA
(NIM Free Endpoints), Ollama Cloud (`https://ollama.com/api`, a própria API da Ollama
servida como host remoto), Nous Research (`https://inference-api.nousresearch.com/v1`,
variantes `:free` com preço zero) e OpenRouter. Nenhum papel permanente é atribuído a
modelo, e `get_observed_limits()` distingue o que a API respondeu do que foi declarado.

No OpenRouter, a descoberta é dinâmica e deliberadamente estreita: entram somente
variantes publicadas cujo ID exato termina em `:free`, cuja saída inclui texto e cujo
preço de entrada e saída é zero. O adapter recusa qualquer outro ID também na hora da
geração, impedindo que uma preferência manual acione um modelo pago. `openrouter/free`
fica de fora porque é um roteador aleatório; ele não oferece a identidade estável que
o histórico e o quórum exigem. Variantes compostas são recusadas, a busca web é
desabilitada explicitamente e o roteador recebe teto zero para token, pedido e imagem.
Para cobranças do OpenRouter e de BYOK, o modo padrão exige uma chave dedicada com
spending limit USD 0 e `Include BYOK usage in limit` ativo; as duas condições são
revalidadas antes de cada inferência e qualquer outra chave é recusada. Contas que
`/key` marque exatamente como free-tier, sem teto e com BYOK fora do limite, só podem
ser usadas com o opt-in explícito
`OPENROUTER_ALLOW_UNCAPPED_FREE_TIER=1`. O painel sinaliza esse modo no detalhe do
provedor. Ele preserva todas as guardas de endpoint e preço, mas não consegue impedir
que uma chave BYOK vinculada à conta consuma créditos do provedor externo; desligado é
o padrão seguro. Há ainda uma precondição externa que a API `/key` não expõe: antes de
ativar, confirme que o plugin Web da conta/workspace não está travado com
`Prevent overrides` e Firecrawl, que usa créditos próprios fora desse teto. A franquia
gratuita é agregada à conta, então todos os modelos OpenRouter compartilham o mesmo teto
no planejador. O upstream realmente selecionado é preservado como metadado de uso.
Enquanto essa proveniência não integrar a identidade do painel, o OpenRouter pode
executar trabalho comum e propor, mas não avaliar nem sintetizar um quórum: o rótulo do
gateway não prova um segundo provedor.

O Ollama Cloud, a Nous e o OpenRouter têm catálogos públicos. Por isso a validação de
chave do painel não passa por listar modelos — cada adaptador diz em `verify_credential()`
qual chamada prova a sua chave. No Ollama ela é um `POST /api/chat` com o
modelo-sentinela e nenhuma mensagem; no OpenRouter é `GET /api/v1/key`; na Nous é um
`POST /chat/completions` com `max_tokens=1` no modelo-sentinela `:free`. As três
verificações autenticam sem gerar conteúdo.

O Ollama Cloud é ainda o único cuja descoberta custa `1 + N` chamadas: `/api/tags`
devolve só nomes, e janela, arquitetura e capacidades vêm de `/api/show`, um pedido
por modelo. As duas rotas são públicas e não gastam cota de inferência, e os pedidos
correm em paralelo. Os dezoito modelos da nuvem foram inventariados em 0,9 s. O custo
é aceito porque sem
a janela declarada `preference_key` põe todo endpoint da Ollama atrás de qualquer
modelo que declare a sua, e o AUTO nunca escolheria nenhum.

## Limites deliberados

Modelo e worker nunca escrevem diretamente em `knowledge/`: só o Proposal Promoter
altera o corpus, e apenas para um patch aprovado, amarrado ao artefato votado e ao
HEAD avaliado. Não há cron ou serviço de sistema instalado, nem escrita em Gmail,
Calendar, Drive ou Docs. Credenciais, OAuth interativo, comandos administrativos e
consumo acima do orçamento continuam fora da autonomia silenciosa.
