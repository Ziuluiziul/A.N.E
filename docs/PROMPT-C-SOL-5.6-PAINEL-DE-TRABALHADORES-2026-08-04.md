# Prompt C — Sol 5.6 — Frente do painel lateral de trabalhadores ativos

> Cole o texto abaixo da linha junto com o anexo `vault-autodidata-estado-2026-08-04.zip`.
> Esta é uma de três frentes paralelas; as outras atacam o acervo de provedores e cotas
> (Frente A) e a conformidade de saída estruturada (Frente B). Não invada as outras.

---

Você é o pesquisador da **Frente C** de um projeto real em produção local, o Vault
Autodidata: um corpus acadêmico interdisciplinar em português mantido por um coletivo de
modelos, visualizado num atlas 3D em Three.js, onde nenhuma saída de modelo entra no corpus
sem passar por quórum multimodelo.

O anexo `vault-autodidata-estado-2026-08-04.zip` é o projeto completo. **Comece por
`ESTADO-2026-08-04.md`, na raiz do pacote.** Depois leia `frontend/src/` — em especial
`atlas.ts` (784 linhas), `controls3d.ts`, `operationalPanels.ts`, `runtimeLayer.ts` e
`contract.ts` — mais `backend/src/vault/app.py`, `backend/src/vault/work/roles.py`,
`backend/src/vault/work/quotas.py` e `backend/src/vault/autonomy/`.

## O problema que é seu

Hoje a atribuição de modelo a papel é inteiramente automática, por aptidão observada
(`providers/aptitude.py`). O mantenedor não tem como dizer "este modelo neste papel", nem
ajustar raciocínio, nem regular o ritmo — e o orçamento da execução só é lido na partida do
processo, de modo que mudar qualquer coisa exige derrubar a pilha inteira. Foi o que
aconteceu hoje: para trocar um número, o atlas que ele tinha aberto caiu.

Queremos um **painel lateral de trabalhadores ativos** no atlas. O esboço abaixo é a
proposta a ser atacada, não a especificação a ser obedecida — se estiver errada, diga onde.

### Esboço a atacar

- **Por papel, uma linha.** Os sete papéis existem em `roles.py`: `proponente`,
  `verificador-factual`, `critico-epistemologico`, `revisor-estrutural`,
  `revisor-interdisciplinar`, `sintetizador`, `arbitro`. Só os quatro primeiros são usados
  hoje. Cada linha mostra provedor e modelo atribuídos (ou "automático por aptidão"), estado
  do endpoint, latência mediana observada e taxa histórica de voto válido — dados que já
  existem em `runtime/modelos/` e `runtime/state/endpoints.json`.
- **Configurações primárias por atribuição:** temperatura, teto de tokens de saída, controle
  de raciocínio, modo de saída estruturada, timeout.
- **Ritmo:** intervalo entre tarefas, concorrência (hoje fixa em 1) e orçamento da execução.
- **Cota como teto rígido:** cada controle mostra quanto da cota conhecida aquela escolha
  consome, e a interface **impede por construção** salvar configuração que ultrapasse o teto
  — não avisa depois. O ledger em `quotas.py` continua sendo a autoridade final e nega antes
  da chamada; a interface nunca é a única linha de defesa.
- **Efeito sem reinício:** aplicar reconfigura o worker no ciclo seguinte, sem derrubar
  backend, frontend ou atlas.

## O que você deve produzir

**1. Especificação do painel.** O que mostra, o que é editável, o que é somente leitura, e
— principalmente — **o que jamais deve ser editável pela interface**. Justifique cada
exclusão. Considere que este projeto tem quatro casos onde confirmação humana é obrigatória
(credenciais, OAuth interativo, comando administrativo ou destrutivo, consumo externo acima
do orçamento) e que a interface não pode virar um contorno para nenhum deles.

**2. Modelo de estado e contrato de API.** Onde a configuração vive, como é versionada, como
o worker a relê sem reiniciar, e o que acontece quando ela muda no meio de uma tarefa em voo
ou de um painel de quórum já montado. O backend hoje expõe `/health`, `/corpus/*`,
`/proposals`, `/layout/{fingerprint}` e um fluxo SSE em `/runtime/events`; o worker mantém
um lease exclusivo sobre a fila (`runtime/state/autonomy/tasks.json.worker.lock`). Proponha o
contrato mínimo que resolve, coerente com o que já existe.

**3. Cota como restrição de interface.** Como representar três tetos coexistentes — header
observado, declarado sem verificação, orçamento da execução — de modo que o mantenedor
entenda **qual** deles está mordendo. Como impedir configuração inválida por construção. E o
que mostrar quando o ledger nega uma chamada: hoje ele nega antes de chamar e não dorme
esperando janela, e essa negativa precisa aparecer como informação, não como erro.

**4. Integração com o atlas existente.** Painel 2D sobreposto ou objeto 3D na cena? O projeto
já tem uma ilha de controles 3D (`controls3d.ts`) e painéis operacionais na cena
(`operationalPanels.ts`), e uma decisão de paleta registrada em `docs/ADR-001-paleta-oklch.md`.
Densidade de formulário e cena 3D têm exigências opostas; escolha um lado e defenda.
Trate acessibilidade (teclado, leitor de tela, contraste) e o custo de render de um painel
denso sobre uma cena que já roda. Há capturas reais da interface em `runtime/captures/`.

**5. Ritmo e concorrência: o que é seguro expor.** Intervalo entre tarefas e concorrência
mexem diretamente no consumo externo. Diga quais faixas são seguras, quais exigem confirmação
explícita, e como impedir que uma combinação aparentemente inocente esgote a janela de 6000
tokens por minuto da Groq — nosso freio real, com ~3,9k tokens por chamada de voto.

**6. O que pode dar errado.** A interface nunca escreve no corpus. Nunca exibe credencial —
`credential_status()` diz apenas se cada credencial existe, jamais qual é. Duas abas abertas
não podem produzir configurações divergentes. Enumere os modos de falha que o desenho precisa
tornar impossíveis, não apenas improváveis.

## Como responder

Português. Cite caminhos de arquivo do pacote. Marque o que é verificado e o que é inferência
sua. Prefira a recomendação única e defendida ao catálogo de alternativas — se propuser duas
opções, diga qual você escolheria e por quê.

Regras do projeto que valem para você: se não sabe, escreva que não sabe; é resposta aceita e
esperada. Não invente API, campo ou comportamento de biblioteca que você não tenha certeza de
que existe.

## Encerramento obrigatório

Termine sua resposta com **exatamente três perguntas de confirmação** dirigidas ao agente
Claude Code que mantém o repositório, sob o título `## Três perguntas de confirmação`.

Cada pergunta deve ser aquela cuja resposta muda o que você desenharia — um limite de escopo,
uma decisão de produto, um trade-off entre controle e proteção. Não pergunte o que está
respondido no pacote. Numere de C1 a C3.
