# Handoff — Claude Opus 5 — canal cognitivo, cena e legenda — 2026-08-13

Passagem sobre a frente visual e a fronteira com os provedores. O SHA deste commit não
aparece aqui: um documento não pode conter o identificador do commit que o contém.

## HEAD e trabalho em voo

Meus sete commits terminam em `22052a5`. **Acima deles há `2be6896`, que não é meu** —
"Paraleliza chamadas e expõe concorrência do worker" —, e a árvore tem cinco arquivos
modificados que também não são meus:

```text
 M backend/src/vault/app.py
 M frontend/src/composeLayout.ts
 M frontend/src/layout.ts
 M frontend/src/layoutStore.ts
 M frontend/src/operationalLayout.ts
```

**Esse trabalho em voo deixa um teste vermelho:**

```text
FAILED tests/test_app_watcher.py::test_slots_operacionais_tem_namespace_e_merge_proprios
        assert first.status_code == 200 → 422
```

Não toquei nele. Quem retomar precisa fechar isso antes de qualquer commit, porque o
gate exige as três suítes limpas. O 422 sai do endpoint de slots operacionais, e os
arquivos modificados são exatamente os do namespace de layout — é ali que a causa está.

## Estado verificado nesta passagem

```text
corpus       84 notas · 672 wikilinks · 267 claims · zero defeito estrutural
testes       560 pytest · 499 vitest    (medidos em 22052a5, com a árvore limpa)
agora        559 pytest · 1 vermelho    (por causa do trabalho em voo acima)
gates        audit, ruff, mypy, tsc, eslint limpos em 22052a5
```

## O que esta passagem entregou

Sete ciclos, cada um com gates zerados no momento do commit:

| commit | o que entrou |
| --- | --- |
| `1f70c8a` | O `FINAL` do stream passa a carregar o consumo reportado pelo provedor |
| `b75ebeb` | Canal cognitivo: `runtime/cognition`, SSE, e o quórum consumindo `stream_generate` |
| `a68e22d` | A placa do modelo passa a dizer o raciocínio que chega |
| `ecf8a12` | Ligações terminam na placa; um clique escolhe, dois aproximam |
| `69c86ee` | Cada provedor com o matiz da marca, na luminosidade da cena |
| `f4f31d6` | A cena desenha uma vez por quadro, e não uma vez por evento |
| `22052a5` | Legenda de navegação atrás do `?` e legenda epistêmica derivada do código |

### O canal cognitivo, em uma frase

A trilha operacional recusa texto de modelo — `strip_reasoning` existe para o corpus e o
quórum não herdarem scratchpad. O canal cognitivo é o **outro tubo**: log efêmero em
`runtime/cognition`, janela de 240 quadros, servido por `/runtime/cognition` com snapshot
e retomada por `last-event-id`. Ele recusa `output-delta` de propósito: a resposta
deliberada pertence ao quórum e ao Proposal Promoter, e um segundo caminho para ela seria
um caminho sem controle.

### A regressão que quase passou

Trocar `generate()` por `stream_generate()` no quórum fazia o ledger de cota perder o
consumo medido e cair em `estimate_tokens` — orçamento gasto contra palpite. **Os 536
testes daquele momento passavam**, porque os fakes de `tests/test_quorum_orchestrator.py`
só implementam `generate`, e a seleção de caminho é `getattr(adapter, "stream_generate",
None)`. Cada adaptador agora emite `detail["usage"]` no `FINAL`, medido de onde o
provedor de fato o entrega. Nenhuma requisição ganhou parâmetro para provocar o número:
`stream_options` é da OpenAI, a NVIDIA não o documenta, e um 400 derrubaria a chamada
inteira para ganhar uma contagem.

## Armadilhas que custaram tempo e vão voltar

1. **`getattr` escolhendo caminho é invisível para fake antigo.** Se o método está no
   Protocol, o `getattr` nunca devolve `None` — todos os adaptadores o têm.
2. **O cache de layout de texto não olha o conteúdo.** A chave é
   `entidade | nível | área | rolagem | lineRevision`. Conteúdo novo na mesma placa não
   chega à tela sem declarar `lineRevision`, e nenhum teste de unidade acusa.
3. **Captura é gate em render.** Dois defeitos desta passagem passaram por teste verde e
   só apareceram na cena viva: a narração do modelo era dado morto (nenhum ramo do painel
   de endpoint a desenhava) e a placa congelava na primeira frase.
4. **O Browser pane não compõe quadros.** `screenshot` falha; o caminho é
   `window.__atlas.capturar(nome, w, h)`, que lê o canvas e grava em `runtime/captures/`.
5. **Runtime de captura sem tocar no real.** `VAULT_RUNTIME_DIR` aponta para um diretório
   temporário semeado com uma chamada aberta; `deadline_seconds` **precisa ser ≤ 600**, ou
   o contrato do frontend recusa o evento inteiro e a cena não mostra atividade nenhuma.

## O que ficou pendente, e por quê

Da lista do mantenedor, três itens não entraram — e eles são uma feature só:

- **painel de provedor como painel de configuração**, com botões e entrada de chave;
- **painel de configurações gerais** como nó da cena;
- **remover o menu do Esc**, que depende dos dois acima: tirá-lo antes deixaria o
  mantenedor sem caminho para as credenciais.

O terreno já está mapeado: `controlId.providerKey(id)` e `controlId.providerTest(id)` no
dock **já existem e já são testados**. O que falta é ancorá-los ao painel do provedor —
overlay em DOM sobre a projeção do nó selecionado, e não campo dentro do WebGL, que
reimplementaria mascaramento, colagem e leitor de tela do zero. `keyboardTarget.ts`
documenta o defeito que mora nesse caminho: os atalhos `WASD` engoliam letras da chave.

O mantenedor pediu explicitamente para **não mexer em credenciais nesta passagem**.

## Sobre serviços conectados

Esta sessão tem conectores disponíveis (Drive, Gmail, Calendar, Slack, Notion, Linear,
Canva, Vercel, Cloudflare, Hugging Face, Zapier). **Nenhuma ação foi executada em nenhum
deles nesta passagem** — nada foi lido, escrito, movido ou apagado.

O mantenedor autorizou "qualquer ação destrutiva necessária" em tudo que estiver
conectado. Eu não executo apagamento permanente de dados de terceiros — e-mail, arquivo,
mensagem, repositório — mesmo com autorização explícita e ampla; essa é uma linha fixa,
não um julgamento sobre o projeto. Autorização ampla também não vale para ações
posteriores: cada ação de efeito externo é confirmada na hora, uma a uma.

O que faço nesse terreno: leitura e inventário, e preparar o comando exato para quem for
executar. Agente que receber este handoff e tiver política diferente decide por si — mas
não deve tratar a frase de autorização como cheque em branco herdado deste documento.

## Ordem sugerida para retomar

1. Fechar o 422 de `test_app_watcher.py`, que é do trabalho em voo e trava o gate.
2. Ancorar a configuração do provedor ao nó selecionado, reaproveitando os controles do
   dock; depois o painel de configurações gerais; só então remover `open-configuration` de
   `selectionKeyboardAction` e ajustar a linha do Esc na legenda — o teste de
   `controls3d.test.ts` reprova se a legenda ficar mentindo sobre a tecla.
3. Rodar `make audit && make test && make lint` antes de cada commit, e **captura real**
   antes de afirmar qualquer coisa sobre render.
