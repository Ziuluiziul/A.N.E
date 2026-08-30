# Bootstrap do vault-autodidata — 2026-07-30

Relatório da primeira fase: preservar, limpar, reorganizar, instalar, provar que o
corpus pode ser lido e visualizado, parar.

**Resultado: PASS.** O ambiente local está concluído. A descoberta e os smoke tests
dos três provedores, assim como o consentimento OAuth do Google Workspace, ficaram
corretamente sem execução porque as credenciais ainda não foram fornecidas.

## Preservação

O estado de partida conferiu com o declarado:

- repositório em `/home/ziul/Área de trabalho/Vault`;
- `HEAD` em `cbe4c3c32b6339c1a1c8d484740908145905d29f`;
- working tree limpo;
- 81 notas, 627 wikilinks e 267 claims com IDs únicos;
- zero defeitos estruturais.

O bundle histórico foi verificado e não foi alterado:

```text
/home/ziul/Documentos/Backups/Vault/2026-07-30/Vault-pos-migracao.bundle
SHA-256 5a48a14c7db4aaa8e5eaa91c80dfe79730998ff58104baaf16bd220b90378b60
```

A tag `baseline-pos-migracao-2026-07-30` continua em
`7aa5db153dc3cf185f5046fa93203673e6809adc`.

Antes da limpeza foi criado um segundo bundle, sem substituir o histórico:

```text
/home/ziul/Documentos/Backups/Vault/2026-07-30/Vault-pre-rearquitetura-cbe4c3c.bundle
SHA-256 e1da0de5a549ffede652572fe02c33902b29373cd652a8576c1504b7b0697cfd
```

`git bundle verify` aprovou. Um clone temporário reproduziu o `HEAD` `cbe4c3c` e o
manifesto acadêmico `4f5b1d009041583c89957f7c22199d8d77836f4441f7e6aa16e741da8b2bf5bb`;
o clone foi apagado em seguida.

## Limpeza do ambiente antigo

O inventário encontrou como componente antigo somente o pacote Debian `obsidian`
1.12.7 e os três metadados versionados em `.obsidian/`:

- `app.json`;
- `appearance.json`;
- `core-plugins.json`.

Não havia processo do Obsidian, instalação Flatpak, Snap ou AppImage, configuração ou
cache próprio do aplicativo no usuário, plugins da comunidade, unidades ou timers
systemd de usuário, cron ligado ao projeto, `vault-broker`, `~/.config/vault-ia`,
Hermes, automação Moltbook ou scripts inequívocos do pipeline antigo.

O pacote foi purgado pelo gerenciador Debian com autorização administrativa.
Conferências posteriores:

- pacote `obsidian` ausente do `dpkg`;
- `/opt/Obsidian` ausente;
- comando `obsidian` ausente;
- `.obsidian/` ausente do repositório.

Nenhum Markdown acadêmico, bundle, histórico Git ou configuração genérica do VS Code
ou navegador foi removido.

## Novo endereço canônico

```text
/home/ziul/Projetos/vault-autodidata
```

O repositório foi movido, não copiado. A árvore antiga
`/home/ziul/Área de trabalho/Vault` não existe mais. `.git`, commits, tag, permissões
e corpus foram preservados.

As 81 notas foram relocadas com `git mv` para `knowledge/`; duas ficam na raiz
(`Índice.md` e `Política Epistêmica e de Linkagem.md`) e as demais nos dez domínios.
O auditor foi para `tools/audit.py` e passou a ler `knowledge/` sem mudar as regras
epistêmicas.

## Estrutura final

```text
vault-autodidata/
├── knowledge/                 corpus canônico
├── backend/src/vault/         FastAPI, configuração, leitor e propostas
├── frontend/src/              TypeScript e cena Three.js
├── providers/                 google/, groq/, nvidia/ e interface comum
├── integrations/              Google Workspace OAuth e catálogo read-only
├── tools/                     auditor e comandos curtos do Makefile
├── tests/                     6 módulos de teste + conftest.py
├── docs/                      relatório e instruções do Workspace
├── runtime/                   proposals/, logs/, state/; ignorado pelo Git
├── AGENTS.md
├── CLAUDE.md -> AGENTS.md
├── .env.example
├── .gitignore
├── Makefile
├── README.md
├── pyproject.toml
├── uv.lock
└── frontend/pnpm-lock.yaml
```

## Ambiente instalado

Todos os pacotes Debian pedidos estão presentes: `git`, `curl`, `ca-certificates`,
`build-essential`, `pkg-config`, `jq`, `ripgrep`, `fd-find`, `unzip`, `zip`,
`sqlite3`, `libsqlite3-dev`, `python3`, `python3-venv` e `python3-dev`.

Versões conferidas:

| Componente | Versão |
| --- | --- |
| Python do Debian | 3.13.5 |
| GCC | 14.2.0 |
| Git | 2.47.3 |
| SQLite | 3.46.1 |
| ripgrep / fd-find | 14.1.1 / 10.2.0 |
| uv | 0.12.0 |
| Node.js | 24.18.1 |
| npm / Corepack / pnpm | 11.16.0 / 0.35.0 / 11.18.0 |

O Python do Debian não foi substituído. O ambiente do projeto vive em `.venv`, e
Node, Corepack, pnpm e uv ficam no espaço de usuário.

`make setup` foi reexecutado com `uv sync --frozen --all-groups` e
`pnpm install --frozen-lockfile`: os dois lockfiles reproduziram o ambiente sem
alteração. `uv pip check` confirmou 70 pacotes compatíveis.

Principais versões resolvidas no Python:

| | | | |
| --- | --- | --- | --- |
| FastAPI 0.141.1 | Uvicorn 0.52.0 | Pydantic 2.13.4 | HTTPX 0.28.1 |
| aiosqlite 0.22.1 | NetworkX 3.6.1 | PyYAML 6.0.3 | orjson 3.11.9 |
| google-genai 2.16.0 | groq 1.6.0 | openai 2.50.0 | google-api-python-client 2.198.0 |
| pytest 9.1.1 | Ruff 0.16.0 | mypy 2.3.0 | |

Frontend: Three.js 0.185.1, Vite 8.2.0, Vitest 4.1.10, ESLint 10.8.0 e TypeScript
6.0.3.

## Corpus e runtime mínimo

Foram implementadas as três interfaces pedidas, mais a API mínima:

- `ProviderAdapter`;
- `CorpusReader`;
- `ProposalStore`;
- API FastAPI para saúde, leitura do corpus, grafo e listagem de propostas.

O leitor preserva pipes Markdown em claims, normaliza o status fechado e registra a
linha física do arquivo. A área de propostas nunca escreve em `knowledge/`: usa IDs
únicos, trava entre processos, escrita atômica, modos privados e exige validação
humana registrada para decidir uma proposta.

Não foram criados adjudicação automática, quórum, agente contínuo, cron, systemd,
seleção complexa de tarefas ou escrita autônoma no corpus.

## Provedores e limites

Google Gemini, Groq e NVIDIA NIM têm adaptadores separados com:

- descoberta do catálogo realmente devolvido à conta;
- identidade por provedor e ID exato do endpoint;
- capacidades somente quando declaradas pela API;
- sonda textual mínima, sem enviar conteúdo do corpus;
- timeout explícito e zero retries escondidos nos SDKs;
- classificação de autenticação, indisponibilidade e rate limit;
- `retry-after` e headers observados preservados;
- backoff adaptativo sem multiplicar as duas chamadas explícitas do smoke.

Na Groq, os headers `x-ratelimit-limit-requests` e
`x-ratelimit-limit-tokens` são interpretados como RPD e TPM, respectivamente,
conforme a [documentação oficial](https://console.groq.com/docs/rate-limits). Para
outros provedores, uma janela não declarada permanece em `raw`, sem conversão
inventada. Os 40 RPM agregados da NVIDIA ficam num campo declarado por Luiz, separado
de qualquer observação da API.

Estado externo em 2026-07-30:

| Integração | Estado |
| --- | --- |
| Google Gemini | preparada; chave ausente; descoberta/smoke não executados |
| Groq | preparada; chave ausente; descoberta/smoke não executados |
| NVIDIA NIM | preparada; chave ausente; descoberta/smoke não executados |
| Google Workspace | catálogo e OAuth local preparados; `client_secret` ausente; OAuth não executado |

`make discover-models`, `make smoke-providers` e `make workspace-oauth` encerram com
mensagem curta e sem traceback enquanto as credenciais estão ausentes.

## Google Workspace

Gemini e Workspace usam credenciais distintas. O fluxo do Workspace:

- pede por padrão somente `drive.metadata.readonly`;
- mantém um catálogo de Drive, Docs, Sheets, Slides, Gmail, Calendar, Tasks, Forms,
  Apps Script, People/Contacts, Chat, Keep e Meet;
- trata APIs administrativas ou restritas como disponibilidade registrada;
- rejeita `credentials.json` e token dentro do repositório;
- rejeita token antigo sem os escopos realmente concedidos;
- grava o token fora do Git, atomicamente e com modo 600;
- executa somente uma leitura mínima depois do consentimento.

Nenhum fluxo escreve em Gmail, Calendar, Drive ou Docs.

## Segredos

```text
/home/ziul/.config/vault-autodidata/              modo 700
/home/ziul/.config/vault-autodidata/secrets.env   modo 600
```

As cinco variáveis previstas existem e estão vazias. No código, chaves são
`SecretStr` e só viram texto no limite do SDK. `.env.example` contém nomes e
explicações, sem valores.

Conferências no conteúdo atual e em todos os commits alcançáveis:

- zero arquivo sensível rastreado por nome;
- zero padrão de chave Google, Groq, NVIDIA ou OpenAI;
- `.venv`, `node_modules`, `runtime`, caches, builds e o JSON derivado do grafo
  ignorados pelo Git.

## Auditoria

```text
notas markdown ................. 81
documentos na raiz ............. 2
wikilinks ...................... 627
wikilinks quebrados ............ 0
wikilinks sem relation: ........ 0
relation: fora do vocabulário .. 0
notas órfãs .................... 0
MOCs sem links ................. 0
frontmatter ausente/inválido ... 0
linhas definidoras de claims ... 267
IDs de claim únicos ............ 267
IDs de claim duplicados ........ 0

SHA-256 do manifesto ........... 4f5b1d009041583c89957f7c22199d8d77836f4441f7e6aa16e741da8b2bf5bb

APROVADO
```

Sair com código zero continua significando integridade estrutural, não aprovação do
conteúdo.

## Testes e prova visual

| Verificação | Resultado |
| --- | --- |
| `make setup` pelos lockfiles congelados | passou |
| `pytest` | 57 passaram |
| Ruff | passou |
| mypy | passou em 31 arquivos |
| `tsc --noEmit` | passou |
| Vitest | 10 passaram |
| ESLint | passou |
| build Vite | passou |
| `uv pip check` | passou |
| `make audit` | passou |

`make corpus-graph` produziu 81 nós, 627 wikilinks condensados em 511 arestas únicas,
267 claims e 11 domínios. A cena Three.js foi renderizada num navegador real:
WebGL/canvas presentes, nós e arestas visíveis, rotação e zoom ativos e seleção de nó
atualizando título e domínio. Nenhum erro apareceu no console.

`make dev` foi validado ponta a ponta:

- `/health` respondeu HTTP 200, corpus presente e nenhuma credencial exposta;
- o frontend respondeu HTTP 200 em `127.0.0.1:5173`;
- `Ctrl-C` encerrou os dois grupos de processos;
- as portas 8000 e 5173 ficaram livres, sem processos órfãos.

## Commits e pacote

Foram usados cinco commits compreensíveis sobre `cbe4c3c`, sem reescrever os
anteriores:

1. `Remove dependências do Obsidian e reorganiza o corpus`
2. `Prepara ambiente de desenvolvimento sob medida`
3. `Adiciona adapters iniciais e prova de grafo 3D`
4. `Registra o relatório do bootstrap`
5. `Endurece integrações e encerra o bootstrap`

A tag histórica não foi movida. O pacote final é:

```text
/home/ziul/Documentos/Backups/Vault/2026-07-30/vault-autodidata-bootstrap.tar.gz
```

Ele é regenerado a partir do estado final e exclui `.git`, `.venv`, `node_modules`,
`runtime`, segredos, caches, builds e `frontend/public/graph.json`.

## Como iniciar

```bash
cd /home/ziul/Projetos/vault-autodidata
make dev
```

`make dev` atualiza o JSON derivado do corpus e sobe o backend em
`http://127.0.0.1:8000` e a cena em `http://127.0.0.1:5173`.

## Pendências reais

Somente ações que dependem de credenciais do usuário:

1. preencher uma ou mais chaves e rodar `make discover-models` e
   `make smoke-providers`;
2. baixar o `credentials.json` do Google Cloud, preencher os dois caminhos do
   Workspace e rodar `make workspace-oauth`.

Até isso ocorrer, o estado correto é **preparado e não testado externamente**, não
falha. O working tree termina limpo depois do commit final.
