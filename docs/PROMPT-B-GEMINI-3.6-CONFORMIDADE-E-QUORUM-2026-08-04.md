# Prompt B — Gemini 3.6 (ou 3.1 Pro) — Frente da conformidade estruturada e do quórum

> Cole o texto abaixo da linha junto com o anexo `vault-autodidata-estado-2026-08-04.zip`.
> Esta é uma de três frentes paralelas; as outras atacam o acervo de provedores e cotas
> (Frente A) e o painel de trabalhadores (Frente C). Não invada as outras.

---

Você é o pesquisador da **Frente B** de um projeto real em produção local, o Vault
Autodidata: um corpus acadêmico interdisciplinar em português mantido por um coletivo de
modelos, onde nenhuma saída de modelo entra no corpus sem passar por quórum multimodelo.

O anexo `vault-autodidata-estado-2026-08-04.zip` é o projeto completo — código, corpus,
testes, e o `runtime/` inteiro com a evidência bruta de cada falha citada aqui. **Comece
por `ESTADO-2026-08-04.md`, na raiz do pacote.** Depois leia `backend/src/vault/quorum/`
(`models.py`, `parser.py`, `engine.py`), `backend/src/vault/work/orchestrator.py` e
`backend/src/vault/work/roles.py`.

## O problema que é seu

O laço de promoção nunca fechou. Zero propostas promovidas desde o início do projeto. Não
por juízo epistêmico — os modelos até produzem avaliação boa — mas porque o sistema não
consegue **ler o voto dos próprios avaliadores**. Hoje, entre 15:09 e 15:20 UTC, 32
chamadas externas produziram 4 tarefas bloqueadas e zero promoções.

São quatro modos de falha independentes, cada um com evidência no pacote:

**(1) Resposta só de raciocínio.** `groq/qwen/qwen3.6-27b` devolve exclusivamente bloco de
raciocínio; removido o bloco, sobra string vazia e o parser abstém.
Ver `runtime/modelos/groq/qwen/qwen3.6-27b/trabalho/8e92eb6dede8.json`.

**(2) Estouro de campo no schema fechado.** `groq/llama-3.3-70b-versatile` devolveu JSON
bem-formado, substantivo e correto — descartado porque `evidence[0].assessment` tinha 213
caracteres contra `max_length=120` (`backend/src/vault/quorum/models.py:54`). O JSON Schema
completo, com o `maxLength` explícito, **vai no prompt**; o modelo ignorou. O único reparo
permitido hoje (`parser.py:133`) é remover vírgula pendente.
Ver `runtime/modelos/groq/llama-3.3-70b-versatile/trabalho/1253e95668df.json`.

**(3) Timeout com pool de um só.** `nvidia/z-ai/glm-5.2` falhou aos 30,8s contra timeout de
30s; suas duas chamadas bem-sucedidas anteriores levaram 25,2s e 25,8s. É o único endpoint
nvidia usável, então sua queda derruba a diversidade de provedor exigida.

**(4) O proponente falha antes do painel.** `google/gemini-3.5-flash-lite` produziu patch
mirando `física/Gravidade com Torsão…` enquanto o alvo autorizado é `Física/…`; a checagem
em `orchestrator.py:483` é diferença de conjunto de strings sem normalizar caixa, e
`domain: física` aparece minúsculo no frontmatter. Outro patch não obedeceu ao `CorpusPatch`.

O quórum exige `MIN_VALID_VOTES=3`, `MIN_PROVIDERS=2`, `MIN_FAMILIES=2`
(`quorum/engine.py:19-21`), e abstenção nunca conta. Com esses quatro modos ativos e um
pool de 5 endpoints usáveis, o resultado prático é a paralisia.

## O que você deve produzir

**1. A correção de cada um dos quatro modos**, na forma: arquivo, o que muda, por quê, e
qual é o custo ou risco de mudar. Queremos a correção mínima que resolve, no estilo do
código existente — não uma reescrita. Diga explicitamente quando a correção certa for
afrouxar uma restrição nossa e quando for endurecer o prompt.

**2. Saída estruturada nativa, provedor por provedor.** Google Gemini API, Groq e NVIDIA
NIM: qual mecanismo cada um oferece para *impor* um JSON Schema (não pedir educadamente),
o que cada um aceita do vocabulário JSON Schema (`maxLength` é respeitado? `enum`? `$defs`?
`additionalProperties: false`?), o que acontece com o que não é suportado, e como o
comportamento muda entre famílias no mesmo provedor. Cada afirmação com fonte e data.
Se a imposição real de `maxLength` não existir em algum provedor, isso decide o desenho do
nosso schema — diga com todas as letras.

**3. Tratamento de raciocínio.** Como desligar, limitar ou isolar o bloco de raciocínio em
cada provedor e família presentes no pacote — e como distinguir raciocínio de resposta de
forma robusta quando não dá para desligar. Nosso `strip_reasoning` já detecta e remove;
o problema é o que sobra depois. Um modelo que só sabe raciocinar deve ser barrado do papel
de avaliador ou acomodado? Defenda a escolha.

**4. Retry disciplinado com devolução do erro do validador.** Hoje não há retry: uma falha
de schema vira abstenção definitiva. Proponha o desenho — quantas tentativas, o que exatamente
devolver ao modelo (a mensagem do validador? o campo ofensor? o schema de novo?), como
limitar custo, e como impedir que vire laço que consome cota. Considere que a Groq nos dá
~1,5 chamadas por minuto na janela de 6000 TPM, com ~3,9k tokens por voto.

**5. A aritmética do quórum sob capacidade heterogênea.** Com pool pequeno e endpoints de
confiabilidade desigual, `3 votos / 2 provedores / 2 famílias` é sustentável? Avalie
alternativas que **não afrouxem a garantia epistêmica**: quórum adaptativo ao tamanho do
pool, peso por confiabilidade observada, abstenção informativa versus abstenção silenciosa,
papel do `sintetizador` e do `arbitro` (definidos em `roles.py` e nunca acionados), e o que
a literatura de deliberação multimodelo, self-consistency e LLM-as-judge estabelece sobre
número mínimo de avaliadores independentes e sobre correlação entre modelos da mesma família.
Traga referências reais e resolvíveis, ou nenhuma.

## Como responder

Português. Cite caminhos de arquivo do pacote. Marque explicitamente o que é verificado e o
que é inferência sua. Prefira a recomendação única e defendida ao catálogo de alternativas.

Regras do projeto que valem para você: identificador (DOI/arXiv/ISBN/URL) que você não tenha
certeza de estar correto é omitido, não estimado — identificador plausível e errado é pior
que lacuna, porque passa por auditado. Ausência de evidência nunca é refutação. Se não sabe,
escreva que não sabe.

## Encerramento obrigatório

Termine sua resposta com **exatamente três perguntas de confirmação** dirigidas ao agente
Claude Code que mantém o repositório, sob o título `## Três perguntas de confirmação`.

Cada pergunta deve ser aquela cuja resposta muda o que você recomendaria — um trade-off
entre rigor e vazão, uma restrição que talvez deva cair, uma decisão de escopo que só quem
tem o repositório na mão pode resolver. Não pergunte o que está respondido no pacote.
Numere de B1 a B3.
