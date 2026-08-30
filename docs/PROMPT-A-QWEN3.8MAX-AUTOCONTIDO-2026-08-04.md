# Prompt A (autocontido) — Qwen3.8max — Frente do acervo, provedores e cotas

> Substitui `PROMPT-A-QWEN3.8MAX-ACERVO-PROVEDORES-COTAS-2026-08-04.md` quando não é
> possível anexar o ZIP. Todo o dado necessário está embutido abaixo. Cole a partir da
> linha horizontal.

---

Você é o pesquisador da **Frente A** de um projeto real em produção local, o Vault
Autodidata. Esta é uma de três frentes paralelas; as outras atacam conformidade de saída
estruturada e aritmética do quórum (Frente B) e o desenho de um painel de configuração
(Frente C). Não invada as outras — sua frente é **acervo de endpoints, provedores e cotas**.

Você não vai receber anexo. Tudo que você precisa saber sobre o sistema está neste texto,
e foi medido em 2026-08-04, não estimado.

## 1. O sistema, em um parágrafo

Um corpus acadêmico interdisciplinar em português (81 notas, 267 claims, 11 domínios) é
mantido por um coletivo de modelos. Nenhuma saída de modelo entra no corpus direto: ela
vira proposta e só é promovida por **quórum multimodelo**, que exige 3 votos válidos, de
pelo menos 2 provedores e 2 famílias distintas, com o proponente fora da própria contagem.
Um worker autônomo deriva tarefas do corpus (claims fracos, endpoints que falharam),
monta painéis, distribui papéis entre endpoints e registra tudo. O stack é Python/FastAPI
no backend, Three.js num atlas 3D, e um adaptador por provedor: Google Gemini API, Groq e
NVIDIA NIM.

## 2. O problema que é seu

O inventário conhece **175 endpoints**, dos quais **105 são aptos a texto**, e apenas
**5 estão provados usáveis**. Os outros 100 nunca foram sondados, e o inventário se recusa
— corretamente — a oferecer ao worker aquilo que não comprovou.

A consequência é aritmética. Com 5 endpoints usáveis e a exigência de 3 votos válidos de
2 provedores e 2 famílias, o painel é sempre o mesmo trio, e a falha de um único endpoint
torna a decisão impossível. Foi o que aconteceu em 2026-08-04T15:09Z: painel fechado com
**0 votos válidos de 3**, porque um endpoint devolveu só bloco de raciocínio, outro
estourou um `maxLength` do schema, e o terceiro deu timeout.

Queremos liberar os 100+ endpoints aptos. **Sem queimar cota no processo**, e sem promover
a "usável" o que não comprovou que é.

## 3. O que já sabemos de cota — e é pouco

| provedor | fonte | o que se observou |
|---|---|---|
| groq | headers HTTP | 14400 requisições/dia e 6000 tokens/minuto; numa medição os restantes eram 14399 req e 5447 tokens |
| google | — | a API Gemini **não devolve header de limite algum**; os tetos do free tier variam por modelo e só se conhecem por 429 observado ou pela documentação da conta |
| nvidia | — | **nenhuma** resposta com limite foi observada; existe apenas um orçamento que o mantenedor informou em 2026-07-30, sem verificação |

Detalhe que importa para o desenho: na Groq os tetos são **por endpoint** — dois modelos
da mesma conta reportaram 7000 e 1000 requisições por dia. No NIM da NVIDIA o orçamento
informado é **agregado por provedor**. Nosso contador respeita escopos diferentes por
provedor justamente por isso; contabilizar tudo num escopo só faria um endpoint gastar a
cota do outro, e o erro só apareceria como 429.

Três tetos coexistem no código e nenhum substitui o outro: o que a API revelou por header,
o que o mantenedor declarou sem verificação, e o orçamento configurado para a execução.
O contador nega **antes** da chamada e nunca dorme esperando janela abrir.

Escala de consumo: uma chamada de voto consome **~3,9k tokens de prompt**. Com 6000
tokens/minuto, a Groq comporta ~1,5 chamadas por minuto. Esse é o freio real do sistema
hoje. O timeout dos adaptadores é de 30s (5s para conectar).

## 4. O acervo completo — os 105 endpoints aptos a texto

Listagem de 2026-08-02T23:27Z, com o status observado até 2026-08-04. Vocabulário de
status: `ok` = respondeu com texto utilizável; `reachable` = respondeu 200 mas sem texto
sob 16 tokens de saída; `unavailable` = erro ou timeout; `não sondado` = nunca chamado.

### google — 22 aptos a texto

| endpoint | família | ctx | max_out | status |
|---|---|---|---|---|
| `gemini-2.0-flash` | gemini | 1048576 | 8192 | não sondado |
| `gemini-2.0-flash-001` | gemini | 1048576 | 8192 | não sondado |
| `gemini-2.0-flash-lite` | gemini | 1048576 | 8192 | não sondado |
| `gemini-2.0-flash-lite-001` | gemini | 1048576 | 8192 | não sondado |
| `gemini-2.5-flash` | gemini | 1048576 | 65536 | não sondado |
| `gemini-2.5-flash-lite` | gemini | 1048576 | 65536 | não sondado |
| `gemini-2.5-pro` | gemini | 1048576 | 65536 | não sondado |
| `gemini-3-flash-preview` | gemini | 1048576 | 65536 | não sondado |
| `gemini-3-pro-preview` | gemini | 1048576 | 65536 | não sondado |
| `gemini-3.1-flash-lite` | gemini | 1048576 | 65536 | não sondado |
| `gemini-3.1-flash-lite-preview` | gemini | 1048576 | 65536 | não sondado |
| `gemini-3.1-pro-preview` | gemini | 1048576 | 65536 | não sondado |
| `gemini-3.1-pro-preview-customtools` | gemini | 1048576 | 65536 | não sondado |
| `gemini-3.5-flash` | gemini | 1048576 | 65536 | **reachable** |
| `gemini-3.5-flash-lite` | gemini | 1048576 | 65536 | **ok** |
| `gemini-3.6-flash` | gemini | 1048576 | 65536 | **reachable** |
| `gemini-flash-latest` | gemini | 1048576 | 65536 | não sondado |
| `gemini-flash-lite-latest` | gemini | 1048576 | 65536 | não sondado |
| `gemini-omni-flash-preview` | gemini | 131072 | 65536 | não sondado |
| `gemini-pro-latest` | gemini | 1048576 | 65536 | não sondado |
| `gemma-4-26b-a4b-it` | gemma | 262144 | 32768 | não sondado |
| `gemma-4-31b-it` | gemma | 262144 | 32768 | não sondado |

Descartados por especialização declarada no nome: image 10, audio 8, research-agent 4,
video 3, embedding 3, robotics 3, live 3, retrieval 1, computer-use 1.

### groq — 8 aptos a texto

| endpoint | família | ctx | max_out | status |
|---|---|---|---|---|
| `allam-2-7b` | allam | 4096 | 4096 | não sondado |
| `groq/compound` | compound | 131072 | 8192 | não sondado |
| `groq/compound-mini` | compound | 131072 | 8192 | não sondado |
| `llama-3.1-8b-instant` | llama | 131072 | 131072 | **ok** |
| `llama-3.3-70b-versatile` | llama | 131072 | 32768 | **ok** |
| `openai/gpt-oss-120b` | gpt | 131072 | 65536 | não sondado |
| `openai/gpt-oss-20b` | gpt | 131072 | 65536 | não sondado |
| `qwen/qwen3.6-27b` | qwen3 | 131072 | 16384 | **ok** |

Descartados: safety 3, audio 2, transcription 2.

### nvidia — 75 aptos a texto

A listagem do NIM **não devolve janela de contexto nem teto de saída** para nenhum
endpoint. Isso é, por si, um dado que queremos entender.

| endpoint | família | status |
|---|---|---|
| `01-ai/yi-large` | yi | não sondado |
| `adept/fuyu-8b` | fuyu | não sondado |
| `ai21labs/jamba-1.5-large-instruct` | jamba | não sondado |
| `aisingapore/sea-lion-7b-instruct` | sea | não sondado |
| `bigcode/starcoder2-15b` | starcoder2 | não sondado |
| `databricks/dbrx-instruct` | dbrx | não sondado |
| `deepseek-ai/deepseek-coder-6.7b-instruct` | deepseek | não sondado |
| `deepseek-ai/deepseek-v4-flash` | deepseek | **unavailable** (529, serviço sobrecarregado) |
| `deepseek-ai/deepseek-v4-pro` | deepseek | **unavailable** (timeout) |
| `google/codegemma-1.1-7b` | codegemma | não sondado |
| `google/codegemma-7b` | codegemma | não sondado |
| `google/gemma-2b` | gemma | não sondado |
| `google/gemma-3-12b-it` | gemma | não sondado |
| `google/gemma-3-4b-it` | gemma | não sondado |
| `google/gemma-4-31b-it` | gemma | não sondado |
| `google/recurrentgemma-2b` | recurrentgemma | não sondado |
| `ibm/granite-3.0-3b-a800m-instruct` | granite | não sondado |
| `ibm/granite-3.0-8b-instruct` | granite | não sondado |
| `ibm/granite-34b-code-instruct` | granite | não sondado |
| `ibm/granite-8b-code-instruct` | granite | não sondado |
| `meta/codellama-70b` | codellama | não sondado |
| `meta/llama-3.1-70b-instruct` | llama | não sondado |
| `meta/llama-3.1-8b-instruct` | llama | não sondado |
| `meta/llama-3.2-11b-vision-instruct` | llama | não sondado |
| `meta/llama-3.2-1b-instruct` | llama | não sondado |
| `meta/llama-3.2-3b-instruct` | llama | não sondado |
| `meta/llama-3.2-90b-vision-instruct` | llama | não sondado |
| `meta/llama-3.3-70b-instruct` | llama | não sondado |
| `meta/llama2-70b` | llama2 | não sondado |
| `microsoft/kosmos-2` | kosmos | não sondado |
| `microsoft/phi-3-vision-128k-instruct` | phi | não sondado |
| `microsoft/phi-3.5-moe-instruct` | phi | não sondado |
| `minimaxai/minimax-m3` | minimax | não sondado |
| `mistralai/codestral-22b-instruct-v0.1` | codestral | não sondado |
| `mistralai/mistral-7b-instruct-v0.3` | mistral | não sondado |
| `mistralai/mistral-large` | mistral | não sondado |
| `mistralai/mistral-large-2-instruct` | mistral | não sondado |
| `mistralai/mistral-medium-3.5-128b` | mistral | não sondado |
| `mistralai/mistral-nemotron` | mistral | não sondado |
| `mistralai/mixtral-8x22b-v0.1` | mixtral | não sondado |
| `moonshotai/kimi-k2.6` | kimi | não sondado |
| `nv-mistralai/mistral-nemo-12b-instruct` | mistral | não sondado |
| `nvidia/cosmos-reason2-8b` | cosmos | não sondado |
| `nvidia/ising-calibration-1.5-31b` | ising | não sondado |
| `nvidia/llama-3.1-nemotron-51b-instruct` | llama | não sondado |
| `nvidia/llama-3.1-nemotron-70b-instruct` | llama | não sondado |
| `nvidia/llama-3.1-nemotron-nano-8b-v1` | llama | não sondado |
| `nvidia/llama-3.1-nemotron-nano-vl-8b-v1` | llama | não sondado |
| `nvidia/llama-3.1-nemotron-ultra-253b-v1` | llama | não sondado |
| `nvidia/llama-3.3-nemotron-super-49b-v1` | llama | não sondado |
| `nvidia/llama-3.3-nemotron-super-49b-v1.5` | llama | não sondado |
| `nvidia/llama3-chatqa-1.5-70b` | llama3 | não sondado |
| `nvidia/mistral-nemo-minitron-8b-8k-instruct` | mistral | não sondado |
| `nvidia/nemotron-3-nano-30b-a3b` | nemotron | não sondado |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` | nemotron | não sondado |
| `nvidia/nemotron-3-super-120b-a12b` | nemotron | não sondado |
| `nvidia/nemotron-3-ultra-550b-a55b` | nemotron | não sondado |
| `nvidia/nemotron-4-340b-instruct` | nemotron | não sondado |
| `nvidia/nemotron-mini-4b-instruct` | nemotron | não sondado |
| `nvidia/nemotron-nano-12b-v2-vl` | nemotron | não sondado |
| `nvidia/nemotron-nano-3-30b-a3b` | nemotron | não sondado |
| `nvidia/neva-22b` | neva | não sondado |
| `nvidia/nvidia-nemotron-nano-9b-v2` | nvidia | não sondado |
| `nvidia/vila` | vila | não sondado |
| `openai/gpt-oss-120b` | gpt | não sondado |
| `openai/gpt-oss-20b` | gpt | não sondado |
| `poolside/laguna-xs-2.1` | laguna | não sondado |
| `stepfun-ai/step-3.7-flash` | step | não sondado |
| `thinkingmachines/inkling` | inkling | não sondado |
| `writer/palmyra-creative-122b` | palmyra | não sondado |
| `writer/palmyra-fin-70b-32k` | palmyra | não sondado |
| `writer/palmyra-med-70b` | palmyra | não sondado |
| `writer/palmyra-med-70b-32k` | palmyra | não sondado |
| `z-ai/glm-5.2` | glm | **ok** (latências de 25,2s / 25,8s / timeout aos 30,8s) |
| `zyphra/zamba2-7b-instruct` | zamba2 | não sondado |

Descartados: embedding 12, safety 6, translation 3, image 2, parsing 2, ranking 1,
retrieval 1.

## 5. Os sete papéis que precisam ser preenchidos

O trabalho é dividido em papéis com instrução própria. Hoje só os quatro primeiros são
acionados; os três últimos existem no código e nunca foram usados por falta de gente.

| papel | o que faz | avalia proposta alheia? |
|---|---|---|
| `proponente` | produz a alteração | não |
| `verificador-factual` | procura erro objetivo: número, atribuição, data, identificador | sim |
| `critico-epistemologico` | julga se o status declarado corresponde ao apoio apresentado | sim |
| `revisor-estrutural` | confere forma: vocabulário de relação, formato de ID, ausência de placeholder | sim |
| `revisor-interdisciplinar` | julga se a conexão entre disciplinas é real ou apenas verbal | sim |
| `sintetizador` | descreve onde as avaliações divergem, sem votar | sim |
| `arbitro` | decide empate; adiar por falta de evidência é decisão válida | sim |

O voto de um avaliador tem que sair num JSON de schema fechado, com campos obrigatórios
`decision` (`approve`/`reject`/`revise`/`abstain`), `confidence` (0–1) e
`recommended_action`, mais listas opcionais de problemas e de avaliações de evidência —
e nessas últimas cada `assessment` tem **limite duro de 120 caracteres**. O schema
completo vai no prompt. Um voto que não valida vira abstenção, e abstenção nunca conta
para o quórum. Foi assim que um voto correto de 213 caracteres foi jogado fora.

## 6. O que você deve produzir

**1. Tabela de limites reais, por provedor e por endpoint.** Free tier e tier pago da
Google Gemini API, da Groq e do NVIDIA NIM: RPM, RPD, TPM, TPD, limite de concorrência, e
se cada teto é por endpoint, por projeto ou por conta. Cada linha com **fonte citável e
data**. Onde não houver fonte confiável, escreva "não verificado" — inventar um número
aqui é pior que deixar a lacuna, porque o código passaria a confiar nele.

**2. Semântica exata dos headers de rate limit** das três APIs: nomes dos campos, unidade,
comportamento do reset, o que aparece no corpo e nos headers de um 429, e se existe
endpoint de cota consultável sem gastar chamada. Nosso contador lê o que a API revela;
queremos que ele leia tudo que ela revela. Interessa em especial o que a Gemini API
oferece, já que hoje não lemos nada dela.

**3. Política de sondagem para os 100 não sondados.** É a entrega mais importante.
Precisamos de um procedimento que descubra capacidade real gastando o mínimo:
- qual é a menor sonda que ainda prova o que precisa ser provado — o modelo responde? em
  texto? obedecendo a um JSON Schema com `maxLength`? sem vazar bloco de raciocínio?;
- em que ordem sondar 100 endpoints para maximizar diversidade de família e de provedor
  cedo, já que o quórum precisa de 2 famílias distintas antes de precisar de volume;
- lotes, espaçamento e backoff que não disparem 429 nem consumam a janela de trabalho —
  lembre dos 6000 tokens/minuto da Groq;
- o critério de promoção para `usável`, o de `quarentena` e o de descarte, e por quanto
  tempo cada veredito vale antes de precisar ser reconfirmado;
- como distinguir, na sondagem, `reachable` de `ok`: hoje três endpoints Gemini devolvem
  200 sem texto sob 16 tokens de saída, e não sabemos se é falta de orçamento de saída,
  bloco de raciocínio consumindo o teto, ou outra coisa. Diga o que é.

**4. Mapa de aptidão declarada contra os sete papéis.** Para as famílias listadas na seção
4, diga quais servem a quais papéis, com base em capacidade declarada pelo fabricante:
janela de contexto, suporte real a JSON Schema, controle de raciocínio, throughput, custo.
Um verificador factual e um revisor estrutural não pedem o mesmo modelo. Sinalize os
endpoints da lista que **não deveriam estar lá** — código, visão, especializações médicas
ou financeiras que passaram pelo nosso filtro de nome e não servem para avaliar corpus.

**5. Riscos do catálogo.** Deprecações anunciadas nas três plataformas, aliases instáveis
que trocam de modelo sob o mesmo nome (`gemini-flash-latest`, `gemini-pro-latest`,
`groq/compound` são candidatos óbvios), endpoints `preview` que somem, e o que fazer com
um endpoint que foi `ok` e desapareceu do catálogo.

## 7. Como responder

Português. Cada afirmação sobre limite ou capacidade externa vem com fonte e data, ou vem
marcada como não verificada — não há terceira opção. Prefira a recomendação única e
defendida ao catálogo de alternativas.

Regras deste projeto que valem para você: identificador ou número que você não tenha
certeza de estar correto é omitido, não estimado. Ausência de evidência nunca é refutação.
Se não sabe, escreva que não sabe — é resposta aceita e esperada.

## 8. Encerramento obrigatório

Termine com **exatamente três perguntas de confirmação** dirigidas ao agente Claude Code
que mantém o repositório, sob o título `## Três perguntas de confirmação`.

Cada pergunta deve ser aquela cuja resposta muda o que você recomendaria — decisão de
escopo, de política ou de risco que só quem tem o repositório na mão pode resolver. Não
pergunte o que já está respondido acima. Numere de A1 a A3.
