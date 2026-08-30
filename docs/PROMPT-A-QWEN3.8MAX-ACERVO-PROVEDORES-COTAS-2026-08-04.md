# Prompt A — Qwen3.8max — Frente do acervo, provedores e cotas

> Cole o texto abaixo da linha junto com o anexo `vault-autodidata-estado-2026-08-04.zip`.
> Esta é uma de três frentes paralelas; as outras duas atacam conformidade de saída
> estruturada (Frente B) e o painel de trabalhadores (Frente C). Não invada as outras.

---

Você é o pesquisador da **Frente A** de um projeto real em produção local, o Vault
Autodidata: um corpus acadêmico interdisciplinar em português mantido por um coletivo de
modelos, onde nenhuma saída de modelo entra no corpus sem passar por quórum multimodelo.

O anexo `vault-autodidata-estado-2026-08-04.zip` é o projeto completo — código, corpus,
testes, e o `runtime/` inteiro com a evidência operacional bruta. **Comece por
`ESTADO-2026-08-04.md`, na raiz do pacote.** Ele diz o que foi medido hoje, com número e
caminho de arquivo para cada afirmação. Depois leia `AGENTS.md`, `providers/`,
`backend/src/vault/work/quotas.py` e os snapshots em `runtime/state/`.

## O problema que é seu

O inventário conhece **175 endpoints**, dos quais **105 são aptos a texto** e apenas
**5 estão provados usáveis**. Os outros 100 nunca foram sondados, e o inventário se
recusa — corretamente — a oferecer ao worker aquilo que não comprovou.

A consequência é aritmética: o quórum exige 3 votos válidos, 2 provedores e 2 famílias
distintas. Com 5 endpoints usáveis, o painel é sempre o mesmo trio, e a falha de um
único endpoint torna a decisão impossível. Foi exatamente o que aconteceu hoje às
15:09 UTC: painel fechado com 0 votos válidos de 3.

Queremos liberar os 100+ endpoints aptos. Sem queimar cota no processo, e sem promover a
"usável" o que não comprovou que é.

Sobre cotas, o que sabemos de verdade é pouco e está registrado no pacote: a Groq devolve
por header 14400 req/dia e 6000 tokens/min; a API Gemini não devolve header de limite
nenhum; da NVIDIA não há uma única resposta com limite observada — só um orçamento que o
mantenedor informou sem verificação. Uma chamada de voto consome ~3,9k tokens de prompt,
o que faz da janela de 6000 TPM da Groq o freio real do sistema hoje.

## O que você deve produzir

**1. Tabela de limites reais, por provedor e por endpoint.** Free tier e tier pago de
Google Gemini API, Groq e NVIDIA NIM: RPM, RPD, TPM, TPD, limites de concorrência, e se o
teto é por endpoint, por projeto ou por conta — a distinção importa porque nosso ledger
contabiliza em escopos diferentes por provedor e errar o escopo faz um modelo gastar a
cota do outro. Cada linha com **fonte citável e data**. Onde não houver fonte confiável,
escreva "não verificado" — inventar um número aqui é pior que deixar a lacuna, porque o
código passaria a confiar nele.

**2. Semântica exata dos headers de rate limit** de cada uma das três APIs: nomes dos
campos, unidade, comportamento do reset, o que aparece no corpo e nos headers de um 429,
e se há endpoint de cota consultável sem gastar chamada. Nosso `quotas.py` lê o que a API
revelou; queremos que ele leia tudo que a API revela.

**3. Política de sondagem para os 100 não sondados.** Esta é a entrega mais importante.
Precisamos de um procedimento que descubra capacidade real gastando o mínimo:
- qual é a menor sonda que ainda prova o que precisamos provar (o modelo responde? em
  texto? obedecendo a um JSON Schema? sem vazar bloco de raciocínio?);
- em que ordem sondar 100 endpoints para maximizar diversidade de família e provedor cedo;
- lotes, espaçamento e backoff que não disparem 429 nem consumam a janela de trabalho;
- o critério de promoção para `usável`, o de `quarentena` e o de descarte — e por quanto
  tempo cada veredito vale antes de precisar ser reconfirmado;
- como detectar, **na sondagem e não numa tarefa real**, que um endpoint devolve só
  raciocínio ou ignora `maxLength` do schema. Hoje descobrimos isso queimando um painel
  inteiro de 4 chamadas.

**4. Mapa de aptidão declarada contra os sete papéis.** O projeto define `proponente`,
`verificador-factual`, `critico-epistemologico`, `revisor-estrutural`,
`revisor-interdisciplinar`, `sintetizador` e `arbitro` (ver `backend/src/vault/work/roles.py`;
os três últimos nunca foram acionados). Para as famílias presentes nos catálogos do pacote,
diga quais servem a quais papéis, com base em capacidade declarada pelo fabricante: janela
de contexto, suporte real a JSON Schema, controle de raciocínio, throughput, custo por
token. Um verificador factual e um revisor estrutural não pedem o mesmo modelo.

**5. Riscos do catálogo.** Deprecações anunciadas, aliases instáveis que mudam de modelo
sob o mesmo nome, endpoints que somem entre listagens, e o que fazer com um endpoint que
foi `ok` e sumiu — nosso histórico por endpoint em `runtime/modelos/` sobrevive ao
endpoint sair do catálogo, e queremos usar isso bem.

## Como responder

Português. Cada afirmação sobre limite ou capacidade externa vem com fonte e data, ou vem
marcada como não verificada — não há terceira opção. Cite caminhos de arquivo do pacote
quando propuser mudança. Onde propuser código, proponha o mínimo que resolve, no estilo do
que já está lá. Prefira a recomendação única e defendida ao catálogo de alternativas.

Regras do projeto que valem para você: identificador (DOI/arXiv/ISBN/URL) que você não
tenha certeza de estar correto é omitido, não estimado. Ausência de evidência nunca é
refutação. Se não sabe, escreva que não sabe — é resposta aceita e esperada.

## Encerramento obrigatório

Termine sua resposta com **exatamente três perguntas de confirmação** dirigidas ao agente
Claude Code que mantém o repositório, sob o título `## Três perguntas de confirmação`.

Cada pergunta deve ser aquela cuja resposta muda o que você recomendaria — decisão de
escopo, de política ou de risco que só quem tem o repositório na mão pode resolver. Não
pergunte o que está respondido no pacote. Numere de A1 a A3.
