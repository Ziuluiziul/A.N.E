# Ciclo 2 — Watcher, reconciliação espacial e provedores — 2026-08-02

**STATUS: PARTIAL.** O watcher, a reconciliação da memória espacial, a descoberta,
o ramo de ausência do OAuth e todos os gates locais passaram. A disponibilidade
externa não passou inteira: uma única sonda foi feita por provedor, sem repetição;
Groq respondeu, Google devolveu 503 e NVIDIA devolveu 404. Declarar PASS com duas das
três rotas indisponíveis esconderia exatamente o resultado que o smoke deveria medir.

## Adendo do Ciclo 2.1 — a origem não sobrevivia ao reinício

Este relatório apresentou o watcher como concluído. Ele não estava: a reconciliação
espacial descrita aqui — de uma impressão de origem declarada para uma de destino,
nunca escolhendo o arquivo mais recente por data — vale enquanto o processo vive, e o
texto não demonstra como a origem é recuperada depois de um reinício.

Não era demonstrável, porque não acontecia. `carry_forward` só era chamado quando o
watcher já tinha uma impressão em memória. No primeiro cálculo após o restart essa
impressão é `None`, então a transição não ocorria: um corpus editado com o backend
desligado nascia sem posição alguma, e o mapa mental morria em silêncio no
encerramento do processo. Era um defeito, não uma preferência de arquitetura.

O Ciclo 2.1 fechou a lacuna anotando a última impressão conhecida em
`runtime/state/layout/last-fingerprint.json`, com schema versionado, escrita atômica e
validação estrita de 64 hexadecimais. Ausência ou corrupção do ponteiro devolvem
"não havia origem" e o Atlas recalcula — perder a memória espacial é aborrecimento,
não abrir seria falha. A origem continua declarada, nunca adivinhada por data.

No mesmo commit funcional entrou o `asyncio.Lock` em `refresh()`. Não havia corrida
comprovada: o método só é chamado de `start()` e do laço de observação, em sequência.
O lock transforma essa sequencialidade em invariante do método, em vez de deixá-la
dependendo de quem por acaso o invoca.

**A classificação deste ciclo não muda.** Google 503 e NVIDIA 404 continuam sem
verificação, e nada aqui os toca:

```text
Ciclo 2 funcional ................ PASS
Disponibilidade dos provedores ... PARTIAL
Estado agregado do Ciclo 2 ....... PARTIAL
```

Detalhes em `docs/CICLO-2.1-CONTINUIDADE-ESPACIAL-2026-08-02.md`.

## 1. Baseline canônica

| Item | Estado inicial |
| --- | --- |
| Repositório | `/home/ziul/Projetos/vault-autodidata` |
| Branch | `main` |
| HEAD | `1731f3e50a24bb6c8556bd35cff39931e60fcf91` |
| Pai | `560f49aa725aad0246075e87df41d2f6d382ed3f` |
| Assunto | `Reconcilia o fechamento antes do Ciclo 2` |
| Working tree | limpa |
| Corpus | 81 notas, 627 wikilinks, 267 claims |
| Manifesto | `4f5b1d009041583c89957f7c22199d8d77836f4441f7e6aa16e741da8b2bf5bb` |

O diff do ciclo não contém `knowledge/`. Nenhum conteúdo do corpus foi enviado aos
provedores; a sonda usou somente `Responda apenas: ok`, com teto de 16 tokens.

## 2. Divergência descoberta antes de consumir cota

O handoff exigia no máximo uma requisição por provedor por execução. O código herdado
não cumpria isso: `make smoke-providers` repetia a listagem antes da sonda, e o pager
Google podia avançar silenciosamente. Um 429 também não interrompia globalmente as
chamadas porque as três rotas eram iniciadas em paralelo.

Os comandos externos só foram executados depois destas correções:

- descoberta faz uma listagem por provedor; Google consome apenas a primeira página,
  solicita o máximo de 1.000 itens e falha se houver token de continuação;
- smoke lê exclusivamente o manifesto e os snapshots da descoberta, portanto faz
  zero listagens e uma única geração por provedor;
- provedores rodam em sequência; o primeiro 429 persiste `retry-after` e impede os
  seguintes;
- Google usa uma tentativa total; Groq e NVIDIA usam `max_retries=0`;
- fallback interno de backoff nunca é serializado como se fosse `retry-after` do
  servidor;
- mensagens, respostas, endpoints, metadados e headers passam por redação recursiva;
- JSON de evidência é substituído atomicamente em arquivo `0600`, sob diretório
  `0700`.

Testes sem rede prendem a contagem das chamadas, a ausência de paginação, a parada em
429, o valor observado de `retry-after`, a redação das três formas de chave e as
permissões dos arquivos.

## 3. Watcher e memória espacial

Um único `CorpusProjectionWatcher` nasce e morre com o lifespan da API. `watchfiles`
é apenas o sinal de que algo pode ter mudado: antes de publicar, o watcher calcula o
fingerprint, constrói a projeção completa e confirma o mesmo fingerprint numa segunda
leitura. Uma projeção inválida ou instável não substitui a última válida.

O frontend abre SSE somente quando a carga inicial veio do backend. A assinatura
acontece depois de montar o modo textual ou, no 3D, depois de carregar, reconciliar e
persistir o layout. Fingerprint igual ou inválido não recarrega; outro SHA-256 válido
recarrega uma vez. Um evento de erro também carrega o fingerprint vivo, então a fila
limitada não pode esconder uma revisão válida ao compactar eventos.

A transição espacial é explícita, `origem -> destino`; nunca procura o arquivo "mais
recente". Posições do destino vencem, posições ausentes são completadas pela origem e
IDs removidos são podados. O `PUT` de layout aceita somente o fingerprint vivo e usa
os IDs do mesmo snapshot já validado — não relê uma edição parcial do filesystem.

Uma falha do cache espacial é relatada, mas não bloqueia a verdade do corpus: a nova
projeção válida é publicada com `changed`, seguida do diagnóstico `error`.

Os testes cobrem:

- `touch` sem mudança de bytes: mesmo fingerprint, revisão, objeto e chave de layout;
- nota nova: posições antigas preservadas e colocação local da nova;
- travessia do degrau de 31 para 32 nós: nenhum MOC antigo se move;
- nota removida: ausente da projeção e do novo snapshot;
- edição inválida: evento de erro e última projeção válida mantida;
- reversão exata da edição inválida: recuperação anunciada sem revisão artificial;
- falha de reconciliação espacial: nova projeção ainda publicada;
- destino preexistente: suas coordenadas prevalecem e IDs obsoletos são podados;
- `PUT` atrasado: fingerprint divergente recebe 409; fingerprint e IDs vêm do mesmo
  snapshot;
- `awatch` real: mudança observada e encerramento limpo pelo evento próprio.

## 4. Descoberta dos provedores

`make discover-models` foi executado **uma vez**, em `2026-08-02T23:27:03Z`. O
manifesto terminou em `complete`.

| Provedor | Endpoints | Candidatos textuais | Famílias observadas |
| --- | ---: | ---: | --- |
| Google | 58 | 42 | antigravity, aqa, deep, gemini, gemma, imagen, lyria, nano, veo |
| Groq | 15 | 13 | allam, compound, gpt, llama, orpheus, qwen3, whisper |
| NVIDIA | 102 | 91 | 45 famílias; distribuição preservada no snapshot |

Os IDs exatos ficam no apêndice deste relatório e nos snapshots locais. `available`
significa que a listagem/capacidade não excluiu o endpoint; não é promessa de que a
conta conseguirá gerar nele — distinção confirmada pelo smoke.

## 5. Smoke observado

`make smoke-providers` foi executado **uma vez** e terminou não-zero. Não houve 429;
por isso as três sondas únicas foram feitas. Nenhuma foi repetida e nenhum endpoint
alternativo foi tentado.

| Provedor | Endpoint sondado | Resultado | Latência | Limites observados |
| --- | --- | --- | ---: | --- |
| Google | `antigravity-preview-05-2026` | `unavailable` — HTTP 503 | 473 ms | nenhum header; fonte `desconhecido` |
| Groq | `allam-2-7b` | `ok` | 448 ms | 7.000 RPD, 6.999 restantes; 6.000 TPM, 5.971 restantes; resets preservados em `raw` |
| NVIDIA | `01-ai/yi-large` | `unavailable` — HTTP 404 | 867 ms | nenhum header; fonte `desconhecido` |

O detalhe privado devolvido pela NVIDIA contém um identificador de conta e foi
deliberadamente omitido deste documento. O orçamento NVIDIA de 40 RPM continua
separado como declaração humana de 2026-07-30, pendente de confirmação pela API.

## 6. Evidências locais e confidencialidade

Os arquivos de runtime são ignorados pelo Git. Diretórios `runtime/state` e
`runtime/logs` estão em `0700`; todos os arquivos abaixo estão em `0600`.

| Evidência | SHA-256 |
| --- | --- |
| `runtime/state/models-discovery.json` | `aedffa16a7473f27a9fabb4e376a59b1cd77ed9f7e7530bbcefec03d7acb374b` |
| snapshot Google | `e8e427759e5c940980e8c5cd97ed0b2abf957155c2659e3640f2c41c2e16ecdb` |
| snapshot Groq | `873271b5b2d7ce6ebc346273473e401b9df0641d7405b9c75e30253a5c308f0a` |
| snapshot NVIDIA | `28de223483d8977cc05103888b493ef66f64a7dbc3e359d26ffe8b0affbb9d18` |
| `runtime/logs/smoke-providers.json` | `89652a999ccdd0b83f864f706ba4461aa97adcf2aa484716b9567cee93ed9bd3` |

Uma varredura binária desses cinco arquivos contra os três valores reais de
credencial encontrou **zero correspondências**. Somente presença, ausência, modos e
caminhos aparecem neste relatório.

## 7. OAuth do Workspace

As três chaves de provedor estavam presentes. `GOOGLE_WORKSPACE_CLIENT_SECRET_FILE`
e `GOOGLE_WORKSPACE_TOKEN_FILE` estavam ausentes; portanto, OAuth ficou **SKIPPED**,
como manda o gate.

`make workspace-oauth` foi exercido uma vez. O script terminou antes de rede,
navegador ou escrita, com duas linhas curtas apontando as variáveis ausentes e
`docs/GOOGLE-WORKSPACE.md`; não houve traceback. O código do script retornou 1 e o
alvo Make retornou não-zero.

## 8. Verificação

| Gate | Resultado |
| --- | --- |
| `make audit` | APROVADO — 81 / 627 / 267; manifesto `4f5b1d00…` |
| `make test` — Python | 163 passaram |
| `make test` — frontend | 59 passaram em 4 arquivos |
| `make lint` — Ruff | limpo |
| `make lint` — mypy | limpo, 43 arquivos |
| `make lint` — ESLint | limpo |
| build do frontend | passou; 709,95 kB, 193,93 kB gzip |
| `git diff --check` | limpo |
| `knowledge/` no diff | vazio |

O build conserva o aviso já conhecido de chunk acima de 500 kB; não é erro do gate.
O smoke externo não é contado como verde: seu resultado parcial é o motivo do
veredito no topo.

## 9. Pendências reais

1. Google e NVIDIA precisam de uma nova execução explicitamente autorizada para
   distinguir indisponibilidade transitória, endpoint inadequado à conta ou catálogo
   mais amplo que a capacidade efetiva. Este ciclo não repete nem tenta outro modelo.
2. O Workspace continua sem `client_secret`; o fluxo interativo só pode começar se o
   arquivo surgir e houver autorização explícita.
3. O Writer Gateway ainda não existe. O watcher observa o corpus, mas não amplia a
   superfície autorizada de escrita.
4. O manifesto privado liga snapshots por nome, não por hash interno. Os hashes estão
   registrados aqui; um endurecimento futuro pode validá-los antes do smoke e fazer
   `fsync` do diretório depois do `replace`.

## 10. Fechamento e reprodução

Descoberta, smoke e OAuth já foram consumidos neste ciclo e **não devem ser
reexecutados como mera reprodução**. Seus comandos de auditoria foram, nesta ordem:

```bash
make discover-models
make smoke-providers
make workspace-oauth
```

Os gates locais podem ser repetidos sem efeito externo:

```bash
make audit
make test
make lint
cd frontend && pnpm run build
```

O commit final, o bundle e o tarball são derivados somente depois da aprovação do
diff. Seus hashes ficam nos `.sha256` e no manifesto externo de backups: embuti-los
neste relatório alteraria o próprio HEAD e recriaria a circularidade já resolvida no
Gate 0.

## Apêndice A — endpoints listados

Inventário exato devolvido pela única descoberta. A ordem é a ordem normalizada dos
snapshots, não uma preferência nem atribuição de papel.

### Google

```text
antigravity-preview-05-2026; aqa; deep-research-max-preview-04-2026;
deep-research-preview-04-2026; deep-research-pro-preview-12-2025; gemini-2.0-flash;
gemini-2.0-flash-001; gemini-2.0-flash-lite; gemini-2.0-flash-lite-001;
gemini-2.5-computer-use-preview-10-2025; gemini-2.5-flash; gemini-2.5-flash-image;
gemini-2.5-flash-lite; gemini-2.5-flash-native-audio-latest;
gemini-2.5-flash-native-audio-preview-09-2025;
gemini-2.5-flash-native-audio-preview-12-2025; gemini-2.5-flash-preview-tts;
gemini-2.5-pro; gemini-2.5-pro-preview-tts; gemini-3-flash-preview;
gemini-3-pro-image; gemini-3-pro-image-preview; gemini-3-pro-preview;
gemini-3.1-flash-image; gemini-3.1-flash-image-preview; gemini-3.1-flash-lite;
gemini-3.1-flash-lite-image; gemini-3.1-flash-lite-preview;
gemini-3.1-flash-live-preview; gemini-3.1-flash-tts-preview; gemini-3.1-pro-preview;
gemini-3.1-pro-preview-customtools; gemini-3.5-flash; gemini-3.5-flash-lite;
gemini-3.5-live-translate-preview; gemini-3.6-flash; gemini-embedding-001;
gemini-embedding-2; gemini-embedding-2-preview; gemini-flash-latest;
gemini-flash-lite-latest; gemini-omni-flash-preview; gemini-pro-latest;
gemini-robotics-er-1.5-preview; gemini-robotics-er-1.6-preview;
gemini-robotics-er-2-preview; gemini-robotics-er-2-streaming-preview;
gemma-4-26b-a4b-it; gemma-4-31b-it; imagen-4.0-fast-generate-001;
imagen-4.0-generate-001; imagen-4.0-ultra-generate-001; lyria-3-clip-preview;
lyria-3-pro-preview; nano-banana-pro-preview; veo-3.1-fast-generate-preview;
veo-3.1-generate-preview; veo-3.1-lite-generate-preview
```

### Groq

```text
allam-2-7b; canopylabs/orpheus-arabic-saudi; canopylabs/orpheus-v1-english;
groq/compound; groq/compound-mini; llama-3.1-8b-instant; llama-3.3-70b-versatile;
meta-llama/llama-prompt-guard-2-22m; meta-llama/llama-prompt-guard-2-86m;
openai/gpt-oss-120b; openai/gpt-oss-20b; openai/gpt-oss-safeguard-20b;
qwen/qwen3.6-27b; whisper-large-v3; whisper-large-v3-turbo
```

### NVIDIA

```text
01-ai/yi-large; adept/fuyu-8b; ai21labs/jamba-1.5-large-instruct;
aisingapore/sea-lion-7b-instruct; baai/bge-m3; bigcode/starcoder2-15b;
databricks/dbrx-instruct; deepseek-ai/deepseek-coder-6.7b-instruct;
deepseek-ai/deepseek-v4-flash; deepseek-ai/deepseek-v4-pro;
google/codegemma-1.1-7b; google/codegemma-7b; google/deplot;
google/diffusiongemma-26b-a4b-it; google/gemma-2b; google/gemma-3-12b-it;
google/gemma-3-4b-it; google/gemma-4-31b-it; google/recurrentgemma-2b;
ibm/granite-3.0-3b-a800m-instruct; ibm/granite-3.0-8b-instruct;
ibm/granite-34b-code-instruct; ibm/granite-8b-code-instruct; meta/codellama-70b;
meta/llama-3.1-70b-instruct; meta/llama-3.1-8b-instruct;
meta/llama-3.2-11b-vision-instruct; meta/llama-3.2-1b-instruct;
meta/llama-3.2-3b-instruct; meta/llama-3.2-90b-vision-instruct;
meta/llama-3.3-70b-instruct; meta/llama-guard-4-12b; meta/llama2-70b;
microsoft/kosmos-2; microsoft/phi-3-vision-128k-instruct;
microsoft/phi-3.5-moe-instruct; minimaxai/minimax-m3;
mistralai/codestral-22b-instruct-v0.1; mistralai/mistral-7b-instruct-v0.3;
mistralai/mistral-large; mistralai/mistral-large-2-instruct;
mistralai/mistral-medium-3.5-128b; mistralai/mistral-nemotron;
mistralai/mixtral-8x22b-v0.1; moonshotai/kimi-k2.6;
nv-mistralai/mistral-nemo-12b-instruct; nvidia/ai-synthetic-video-detector;
nvidia/cosmos-reason2-8b; nvidia/embed-qa-4; nvidia/ising-calibration-1.5-31b;
nvidia/llama-3.1-nemoguard-8b-content-safety;
nvidia/llama-3.1-nemoguard-8b-topic-control;
nvidia/llama-3.1-nemotron-51b-instruct;
nvidia/llama-3.1-nemotron-70b-instruct;
nvidia/llama-3.1-nemotron-nano-8b-v1;
nvidia/llama-3.1-nemotron-nano-vl-8b-v1;
nvidia/llama-3.1-nemotron-safety-guard-8b-v3;
nvidia/llama-3.1-nemotron-ultra-253b-v1;
nvidia/llama-3.2-nemoretriever-1b-vlm-embed-v1;
nvidia/llama-3.2-nv-embedqa-1b-v1;
nvidia/llama-3.3-nemotron-super-49b-v1;
nvidia/llama-3.3-nemotron-super-49b-v1.5;
nvidia/llama-nemotron-embed-1b-v2; nvidia/llama-nemotron-embed-vl-1b-v2;
nvidia/llama3-chatqa-1.5-70b; nvidia/mistral-nemo-minitron-8b-8k-instruct;
nvidia/nemoretriever-parse; nvidia/nemotron-3-embed-1b;
nvidia/nemotron-3-nano-30b-a3b;
nvidia/nemotron-3-nano-omni-30b-a3b-reasoning;
nvidia/nemotron-3-super-120b-a12b; nvidia/nemotron-3-ultra-550b-a55b;
nvidia/nemotron-3.5-content-safety; nvidia/nemotron-4-340b-instruct;
nvidia/nemotron-4-340b-reward; nvidia/nemotron-mini-4b-instruct;
nvidia/nemotron-nano-12b-v2-vl; nvidia/nemotron-nano-3-30b-a3b;
nvidia/nemotron-parse; nvidia/neva-22b; nvidia/nv-embed-v1;
nvidia/nv-embedcode-7b-v1; nvidia/nv-embedqa-e5-v5;
nvidia/nv-embedqa-mistral-7b-v2; nvidia/nvclip;
nvidia/nvidia-nemotron-nano-9b-v2; nvidia/riva-translate-4b-instruct;
nvidia/riva-translate-4b-instruct-v1.1; nvidia/riva-translate-4b-instruct-v2;
nvidia/vila; openai/gpt-oss-120b; openai/gpt-oss-20b; poolside/laguna-xs-2.1;
snowflake/arctic-embed-l; stepfun-ai/step-3.7-flash; thinkingmachines/inkling;
writer/palmyra-creative-122b; writer/palmyra-fin-70b-32k;
writer/palmyra-med-70b; writer/palmyra-med-70b-32k; z-ai/glm-5.2;
zyphra/zamba2-7b-instruct
```
