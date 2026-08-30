# Provedores autorizados e o que a página oficial diz hoje

Três conjuntos de fatos, e só esses três. **Página oficial** é o HTML consultado em
2026-08-30 (ou a data `Last updated` que a própria página imprime). **O que o vault
declara hoje** é o que o dump em `/workspace/ane-product` contém. **Header observado**
é o que uma resposta HTTP devolveu nesta sessão — e esta sessão não chamou nenhum
provedor. Números de cota do vault **não** se copiam para a coluna oficial.

`AUTHORIZED_PROVIDERS` em `backend/src/vault/work/ceilings.py:19` é
`frozenset({"google", "groq", "nvidia"})`. Ollama, Nous e OpenRouter existem no
runtime (`providers/__init__.py` constrói o adaptador quando há chave) e **não**
estão em `AUTHORIZED_PROVIDERS`: provedor fora do conjunto some zero no teto
(`ceilings.py:61-62`). Sem spec.

Variáveis de ambiente abaixo são **nomes**. Os valores moram fora do repositório.

## Groq (HOJE)

### O que o vault declara

`providers/groq/limits.py` (consultado no código; o próprio arquivo data a leitura
oficial em 2026-08-17, `ORIGEM` na linha 17). `DECLARED_BY_MODEL` (linhas 22-81)
não é um teto único da conta e **não** vale para todo modelo Groq: só os IDs
listados têm mapa. Os quatro gpt-oss/qwen abaixo compartilham o mesmo bloco
(RPM 30, RPD 1000, TPM 8000, TPD 200000):

| `endpoint_id` | RPM | RPD | TPM | TPD |
| --- | ---: | ---: | ---: | ---: |
| `openai/gpt-oss-120b` | 30 | 1000 | 8000 | 200000 |
| `openai/gpt-oss-20b` | 30 | 1000 | 8000 | 200000 |
| `openai/gpt-oss-safeguard-20b` | 30 | 1000 | 8000 | 200000 |
| `qwen/qwen3.6-27b` | 30 | 1000 | 8000 | 200000 |

Outros IDs no mesmo mapa, tetos **diferentes**: `groq/compound` e
`groq/compound-mini` TPM 70000 (RPD 250, sem TPD no mapa); os dois
`llama-prompt-guard-2-*` TPM 15000; os dois Orpheus TPM 1200 (RPM 10, RPD 100).
ID ausente do mapa: `declared_limits()` devolve dicionário vazio
(`limits.py:103-108`).

`SHUT_DOWN` (`limits.py:85-96`) marca Llama 3.1/3.3 (e outros) desligados para
free/developer desde 2026-08-16. O adaptador (`providers/groq/adapter.py:125-137`)
expõe o ID no inventário com `available=False` quando a chave está nesse mapa.

Headers, segundo o próprio `limits.py:8-9` e `providers/base.py:371-396`:
`x-ratelimit-limit-requests` é RPD; `x-ratelimit-limit-tokens` é TPM. RPM **não**
vem no header. O SDK é `AsyncGroq` (`adapter.py:74-80`) **sem** `base_url` no
repositório — vale o default do SDK. Env: `GROQ_API_KEY` (só o nome).

### Página oficial (consulta 2026-08-30)

https://console.groq.com/docs/rate-limits — a página chama o bloco de *high
level summary* e manda olhar *exact rate limits* na *limits page* da conta. A
tabela servida nesta consulta (aba Free, no HTML obtido) confirma TPM=8K para
os quatro gpt-oss/qwen acima (RPM 30, RPD 1K, TPD 200K). Compound 70K TPM;
prompt-guard 15K; Orpheus 1.2K. A mesma página documenta os headers
(`x-ratelimit-limit-requests` = RPD; `x-ratelimit-limit-tokens` = TPM) e o 429.

Leitura do A.N.E. na mesma URL em 2026-08-30: `qwen/qwen3.6-27b` e a
família `gpt-oss-*` = 30 RPM / 1K RPD / 8K TPM. Header
`x-ratelimit-limit-tokens` = TPM. Não muda a tabela do vault; só confirma
a página.

https://console.groq.com/docs/models — coluna **RATE LIMITS (DEVELOPER PLAN)**
mostra **outras** linhas para os mesmos IDs: `openai/gpt-oss-120b` e
`openai/gpt-oss-20b` e `qwen/qwen3.6-27b` a 250K TPM / 1K RPM;
`openai/gpt-oss-safeguard-20b` (Preview) a 150K TPM / 1K RPM; Compound 200K TPM /
200 RPM. **Linhas oficiais diferentes.** O vault declara 8K alinhado à página de
rate-limits, não à tabela models. 8K **não** é o limite da conta: a página de
rate-limits manda ler *account settings*.

A página de models ainda lista `llama-3.1-8b-instant` e `llama-3.3-70b-versatile`
como Production Models *Enterprise / ContactSales*. A depreciação
https://console.groq.com/docs/deprecations (citada no código em `limits.py:6`)
data o shutdown de free/developer em 16/08/2026 — o mesmo dia que
`SHUT_DOWN`. A página de models **não** é, sozinha, a fonte do desligamento.

A mesma página de rate-limits lista `qwen/qwen3.8-27b` (TPM 8K, TPD 2M nesta
consulta). Esse ID **não** está em `DECLARED_BY_MODEL`.

Base URL oficial: `https://api.groq.com/openai/v1`
(https://console.groq.com/docs/openai, consulta 2026-08-30). Referência REST
https://console.groq.com/docs/api-reference (consulta 2026-08-30), endpoints
copiados:

- `POST https://api.groq.com/openai/v1/chat/completions`
- `POST https://api.groq.com/openai/v1/responses`
- `GET https://api.groq.com/openai/v1/models`

Auth: `Authorization: Bearer $GROQ_API_KEY`. 429:
https://console.groq.com/docs/errors. Compatibilidade OpenAI:
https://console.groq.com/docs/openai. O vault **não** declara `base_url` no
`AsyncGroq`; o host oficial acima é da página, não de uma constante no adapter.

## NVIDIA NIM (HOJE)

### O que o vault declara

Host `https://integrate.api.nvidia.com/v1` em `providers/nvidia/adapter.py:50`
(`BASE_URL`). SDK `openai.AsyncOpenAI` (`adapter.py:65-76`) com esse
`base_url`, timeout 60s, `max_retries=0`. Env: `NVIDIA_API_KEY`. O comentário de
`.env.example:28-30` aponta *NVIDIA Build / NIM (build.nvidia.com)* e o mesmo
host.

40 RPM agregados = `DECLARED_REQUESTS_PER_MINUTE = 40` (`adapter.py:52-58`),
origem *confirmado pelo mantenedor em 2026-08-17*. **Não** é número de página
NIM. Entra como `declared_limits` / `requests_per_minute_aggregate`, nunca como
limite observado (`get_observed_limits` só devolve o que uma resposta mostrou,
mais a nota do orçamento declarado).

Nenhum model ID de produção está hardcoded no adapter. O inventário vem de
`self._client.models.with_raw_response.list()` (`adapter.py:99-135`).

### Página oficial (consulta 2026-08-30)

NIM = microserviços de inferência:
https://docs.nvidia.com/nim/ ;
https://docs.api.nvidia.com/nim/docs/introduction (a página imprime
*Updated 24 days ago* nesta consulta, o que recua a ~2026-08-06).

Dois modos, páginas distintas:

| Modo | Página | Host | Credencial que a página nomeia |
| --- | --- | --- | --- |
| Self-hosted (container) | Quickstart NIM LLM **2.0.11** https://docs.nvidia.com/nim/large-language-models/latest/get-started/quickstart.html | `http://localhost:8000` (`-p 8000:8000`) | `NGC_API_KEY` (pull / artefatos; a própria quickstart diz que em alguns catálogos públicos a chave é opcional) |
| API Catalog hospedado | https://docs.api.nvidia.com/nim/docs/api-quickstart (*Updated 24 days ago*) | `https://integrate.api.nvidia.com/v1` | *NVIDIA Developer API Key* (fluxo *Get API Key* em build.nvidia.com) |

O vault usa o **hospedado**, não o container local: `BASE_URL` aponta para
`integrate.api.nvidia.com`, não para localhost.

Referência de API do NIM LLM **3.0.0** (self-hosted, consulta 2026-08-30):
https://docs.nvidia.com/nim/large-language-models/3.0.0/reference/api-reference.html
— `POST /v1/chat/completions` no container. Endpoint canônico **hosted**, copiado
de uma ficha do catálogo (https://docs.api.nvidia.com/nim/reference/meta-llama-3_3-70b-instruct-infer,
consulta 2026-08-30):

`POST https://integrate.api.nvidia.com/v1/chat/completions`

Não há model ID de produção neste documento: a página do catálogo lista IDs por
ficha; o vault pergunta `list()`. NGC key (pull do container) **não** é a
Developer API Key (hosted). O vault só nomeia `NVIDIA_API_KEY`.

## Google Gemini (HOJE)

### O que o vault declara

SDK `google.genai.Client` (`providers/google/adapter.py:47-56`), env
`GEMINI_API_KEY`. Sem `base_url` no adapter — o host REST oficial abaixo **não**
está no código. Inventário: `self._client.aio.models.list` com
`page_size=1000` (`adapter.py:100-102`); segunda página é erro explícito, não
paginação silenciosa.

Cotas em `providers/google/limits.py`. Origem **painel AI Studio**, captura
2026-08-17 (`ORIGEM` linha 16: `painel Google AI Studio (Documentos/google.md)`).
**Não** header: o próprio adapter (`adapter.py:7-9` e `265-275`) afirma que a
API Gemini não devolve `x-ratelimit-*`. IDs no mapa `_TETO` (linhas 19-34)
incluem `gemini-2.5-flash`, a família 3.x flash (`gemini-3-flash-preview`,
`gemini-3.1-flash-lite`, `gemini-3.5-flash`, `gemini-3.6-flash`,
`gemini-3.7-flash`), `gemma-4-*` e `antigravity-preview-05-2026`. Esses números
são o lado direito de `usado / limite` da captura. **Não** são a página oficial
de rate limits.

Workspace OAuth ≠ Gemini: já documentado em [GOOGLE-WORKSPACE.md](GOOGLE-WORKSPACE.md).
Credenciais distintas, código em árvores distintas.

### Página oficial (consulta 2026-08-30)

https://ai.google.dev/gemini-api/docs/models — *Last updated **2026-08-27 UTC***.
Banner *Gemini 3.7 Flash is now available.* Endpoint na tabela da página:
`gemini-3.7-flash`. Esta página é o catálogo da **Gemini API** (AI Studio /
`generativelanguage.googleapis.com`), não Vertex AI. O vault não menciona Vertex
no adapter.

https://ai.google.dev/gemini-api/docs/rate-limits — *Last updated **2026-08-18 UTC***.
Limites por **projeto**, não por chave; *View your active rate limits in AI
Studio*; *Specified rate limits are not guaranteed*. Tiers Free / 1 / 2 / 3.
RPD reset *midnight Pacific time*. A página **não** reproduz os RPM/TPM/RPD da
captura `limits.py`; por isso este doc **não** copia os números do vault como se
fossem a página.

#### Leitura do painel 2026-08-30 (uso 0)

Tabela do Luiz no Google AI Studio, uso 0 nesta leitura. A página oficial
(https://ai.google.dev/gemini-api/docs/rate-limits, Last updated 2026-08-18
UTC) manda ver o Studio e diz que limites não são garantidos — estes
números são da conta, não da página.

| Nome na tabela | ID no vault (`limits.py`) | RPM | TPM | RPD | Uso nesta leitura |
| --- | --- | ---: | ---: | ---: | ---: |
| Gemini 3.6 Flash | `gemini-3.6-flash` | 5 | 250000 | 20 | 0 |
| Gemma 4 31B | `gemma-4-31b-it` | 30 | 16000 | 14400 | 0 |

Alinhados ao mapa de 2026-08-17. Sem URL de API nova.

https://ai.google.dev/gemini-api/docs/api-key — *Last updated **2026-08-26 UTC***.
Auth por chave; nomes de env `GEMINI_API_KEY` ou `GOOGLE_API_KEY`. Aviso: em
**September 2026** a Gemini API rejeita pedidos de *Standard keys*; migrar para
*auth keys*. (A restrição a *unrestricted standard keys* já vale hoje, segundo
a mesma página.)

https://ai.google.dev/api/generate-content — *Last updated **2026-08-28 UTC***.
O HTML desta consulta mostra o host
`generativelanguage.googleapis.com` e o método `generateContent` no path
`/v1beta/models/<id>:generateContent` (exemplo na página:
`generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent`).
A forma de transcoding `{model=models/*}:generateContent` **não** aparece como
string literal nesse HTML. O vault **não** coloca esse host no adapter: usa o
SDK.

Vertex AI é outro produto (outro host, outro IAM). Não está em
`providers/google/`. Não misturar com o OAuth do Workspace.

## Ollama Cloud (fora de AUTHORIZED_PROVIDERS, leitura 2026-08-30)

Não é provedor do quórum (`ceilings.py` não inclui ollama).

**Página oficial:** https://ollama.com/pricing — Free = *light usage*; cada
plano tem *session limits* (reset 5 horas) e *weekly limits* (reset 7 dias).
A página **não** publica percentual semanal nem contagem de requests por
modelo. Produto Cloud: https://docs.ollama.com/cloud.md . Não há endpoint
de inferência citado aqui (não inventar).

**Observação de sessão 2026-08-30** (A.N.E. / Luiz, plano Free): weekly
24.2% (167 req: `gemma4:31b` 40, `gpt-oss:120b` 32, `gpt-oss:20b` 25,
`nemotron-3-super` 23, e outros). Session 0%. Estas cifras **não** estão na
página de pricing.
