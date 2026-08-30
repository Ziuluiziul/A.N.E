# ADR-005 — Uma autoridade só sobre o estado operacional

**Data:** 2026-08-15 · **Estado:** aceita, não implementada · **Refinada em 2026-08-15**
**HEAD na decisão:** `cf746b0`
**Decidida por:** mantenedor, sobre o achado de que a cena principal é estática por construção.
**Relacionadas:** [ADR-003](ADR-003-instrumentacao-antes-de-morfogenese.md) (`displayPose =
anchorPose + morphOffset`), [ADR-004](ADR-004-posicao-derivada-da-relacao.md) (aberta).

## O achado que a motivou

A pergunta era por que só a nuvem RACIOCÍNIO se move. A resposta está no código, e é
estrutural:

```
app.py:304        with_runtime_quorum(base, quorum_root, state_dir)   ← injeta operação na projeção
main.ts:581       loadProjection()                                    ← uma vez, no arranque
main.ts:695,716   composeLayout(...)                                  ← duas vezes, e nunca mais
main.ts:602       watchProjection(fingerprint, () => location.reload())
main.ts:551       updateRuntime(s) → runtimeLayer.update(s)            ← só a trilha viva
```

QUÓRUM, MODELOS, PROVEDORES e TRABALHADORES chegam **dentro da projeção**, são assentados
uma vez e ficam congelados a sessão inteira. A projeção só muda quando a impressão digital
do corpus muda — o que não acontece há onze dias — e, quando muda, a resposta é recarregar
a página.

Medido na cena viva: recompor custa 48–77 ms para 1242 nós, **e devolve as mesmas
posições**, porque a entrada é a mesma projeção congelada.

Cheguei a implementar o M5 — `setTargets` mais `assentarTecido`, ligando `advanceMotion` a
`PanelBodies.moveTo` — e **reverti antes de commitar**: seria uma porta sem nada para
atravessá-la, que é placeholder pelo critério deste repositório.

## A decisão

**O estado operacional tem uma autoridade só: a `runtimeLayer`.** Não existe segunda cópia
operacional imobilizada dentro da projeção.

```
PROJEÇÃO / ÂNCORAS          RUNTIME / TECIDO
corpus                      quóruns
MOCs                        workers
notas                       provedores operacionais
pontes epistêmicas          modelos/endpoints em atividade
geometria cartográfica      tarefas · raciocínios · votos
                            relações transitórias
```

**Provedor e modelo não se duplicam.** É uma entidade só, com identidade e posição-base
persistentes mais estado e deslocamento de runtime:

```
anchor/base identity  +  runtime state  +  runtime displacement
```

E não "provedor estático + provedor vivo". Posição-base estável **não** implica entidade
estática — é a mesma separação entre âncora e tecido que a ADR-003 fixou.

### A invariante que vale durante a migração inteira

```
para toda entidade operacional visível:
  existe exatamente um dono da identidade,
  um dono do estado,
  e um dono da posição corrente.
```

Ela vale **em todo passo intermediário**, não só no final. É o que impede a migração de
passar por um estado em que duas representações disputam a mesma entidade — que é
exatamente a doença que esta ADR trata. No estado final os três donos convergem para a
mesma abstração de runtime; a projeção pode fornecer a pose-base e nada além disso.

### Três poses, e um mecanismo cego

```
anchorPose    estado cartográfico estável
targetPose    destino operacional atual
currentPose   posição interpolada pelo mecanismo de movimento
```

`advanceMotion` continua completamente ignorante de semântica: ele conduz
`currentPose → targetPose` e nada mais. A política morfogênica decide `targetPose`; a
memória espacial fornece `anchorPose`. Fixar os três nomes no código desde o primeiro
commit é o que impede a ambiguidade de voltar por outro caminho.

## Movimento continua sendo consequência, nunca decoração

`advanceMotion` é mecanismo; a política é o evento operacional medido. Nada de timer,
ruído ou física decorativa:

| evento | efeito no tecido |
|---|---|
| worker assume tarefa | aproxima-se do domínio/âncora correspondente |
| painel nasce | quórum forma tecido em torno do alvo |
| voto chega | relação revisor→quórum aparece ou intensifica |
| painel escala | estrutura diverge, abre |
| painel fecha | tecido contrai |
| endpoint indisponível | perde participação, recua |
| tarefa termina | estrutura operacional desaparece |

`setTargets`/`assentarTecido` continuam conceitualmente corretos. Só estavam recebendo a
fonte errada: o alvo vem do runtime vivo, não de uma recomposição da projeção congelada.

## Sequência

1. `runtimeLayer` passa a possuir criação, atualização, remoção e posição-alvo das
   entidades operacionais, **herdando as âncoras determinísticas de hoje**.
2. Só então a projeção deixa de carregá-las — `with_runtime_quorum` sai de
   `/corpus/projection`.
3. `advanceMotion`/`PanelBodies.moveTo` ligados a esse estado real.
4. Desaparecimento de tarefa ou painel **remove ou retrai** o tecido: nada de cadáver
   visual.
5. `window.location.reload()` do `watchProjection` dá lugar à aplicação incremental da
   projeção, e só para mudança do corpus.
6. Câmera, seleção e foco preservados na transição.

**A ordem 1 antes de 2 é correção deliberada** da sequência original. Invertida, a cena
perde quatro populações entre um passo e outro: a restrição do mantenedor é migrar
*propriedade*, não aparência. Se hoje `google`, `groq` e `nvidia` têm lugares
reconhecíveis, a `runtimeLayer` herda essas âncoras.

O passo 5 absorve a alternativa que foi descartada — trocar o reload por aplicação
incremental —, que resolvia um sintoma real mas preservava a duplicação. Implementá-la
antes criaria duas arquiteturas de movimento, uma para mudança epistêmica e outra para
atividade operacional, e depois exigiria reconciliá-las.

### Uma categoria por vez, e nesta ordem

```
TRABALHADORES  →  QUÓRUM  →  MODELOS/endpoints  →  PROVEDORES
```

Workers e quóruns são inequivocamente runtime — se a propriedade nova estiver errada,
erra onde o custo é menor. Modelos e provedores têm identidade cartográfica mais forte e
só migram depois que o novo dono estiver comprovado.

O tamanho de cada etapa, medido em `/corpus/projection` no HEAD desta ADR:

| categoria | nós na projeção |
|---|---:|
| `operacional/trabalhadores` | **7** |
| `operacional/quorum` | **1083** |
| `operacional/modelos` | **123** |
| `operacional/provedores` | **5** |
| — corpus (`epistemic`) | 84 |

**A projeção do corpus carrega 1218 nós operacionais contra 84 do corpus:** 94% do que o
endpoint chamado `/corpus/projection` devolve não é corpus. Ele responde em **6,8 s** e
pesa **1,99 MB**.

Isso confirma a ordem escolhida por dois lados. TRABALHADORES tem 7 entidades — é a menor
superfície possível para provar o novo dono. E QUÓRUM, com 1083, é onde está o ganho: é
ele que faz a cartografia epistêmica custar segundos para carregar.

### O gate que transforma a migração em substituição 1:1

**Antes de tirar qualquer entidade de `with_runtime_quorum`, provar na cena viva que a
equivalente criada pela `runtimeLayer` ocupa a mesma âncora e mantém a mesma identidade
visual.** Sem esse gate isto vira refatoração big-bang, e big-bang em geometria de cena é
como se perde uma população sem ninguém notar até a captura seguinte.

Quatro testes de contrato, antes da captura:

1. nenhuma entidade operacional aparece simultaneamente em projeção e runtime;
2. atualização de runtime não exige `composeLayout`;
3. desaparecimento no runtime **remove** a entidade — nada de cadáver visual;
4. mudar `targetPose` altera o movimento sem alterar `anchorPose`.

E o gate visual em **1280×720 e 1440×1000**, precisamente porque já houve regressão de
PROVEDORES sobre TRABALHADORES nesta sessão com a suíte inteira verde.

## Raio de alcance

`with_runtime_quorum` é consumido por `app.py:304` e por `tests/test_operational.py`. Do
lado do cliente, `layer === 'operational'` atravessa `contract.ts` (validação, contagens),
`composeLayout` (`layoutOperational`, `layoutModels`), `atlas.ts` (`idsPorCamada`) e os
nomes de nuvem. É refatoração de contrato, não ajuste local.

## O que esta ADR muda além do M5

O ponto arquitetural é maior que o movimento que o motivou:

> A projeção deixa de ser o snapshot total do universo do Atlas. Ela passa a ser a
> **cartografia epistêmica persistente**. O runtime passa a ser o **organismo operacional
> presente**.

É essa separação que dá substrato real à frente morfogênica. Sem ela, a ADR-003 estaria
pedindo para animar uma fotografia — e foi literalmente o que a tentativa de M5 desta
sessão descobriu ao recompor 1242 nós em 48–77 ms e receber de volta as mesmas posições.

## Condição de verificação

Nada aqui se dá por pronto sem captura da cena viva — é a regra da casa, e foi ela que
pegou PROVEDORES sobre TRABALHADORES hoje, com todos os testes verdes. No momento desta
decisão o backend e o dev server estavam fora do ar, e por isso a implementação **não foi
iniciada**: mudar quem é dono da geometria sem poder olhar o resultado é exatamente o
risco que esta casa não corre.

**Atualização:** backend e dev server foram religados ao fim desta sessão
(`.claude/launch.json`, alvos `backend` e `atlas`). A condição que bloqueava a
implementação não vale mais para quem retomar.

## Onde retomar

Em `frontend/src/runtimeLayer.ts`, e só ali. **Não** reabrir `atlas.ts` primeiro, **não**
mexer no `reload()` ainda, e **não** tocar em `with_runtime_quorum` até a primeira
entidade de runtime existir visualmente com paridade de âncora e de identidade.

O primeiro alvo é TRABALHADORES: dar à `runtimeLayer` criação, atualização, remoção e
`targetPose` deles, herdando a âncora que `layoutOperational` produz hoje.

### Mapa da primeira transferência, já levantado

**De onde vem a âncora hoje.** Não é `layoutOperational` — é `layoutModels`, em
[modelsLayout.ts:256](../frontend/src/modelsLayout.ts) : um anel na borda externa da
região de modelos, com `angulo = 2πi/n` e
`raio = max(raioDaCasca × FOLGA_DO_ANEL_DE_TRABALHO, raioParaCaber(n, largura, largura))`.
Depende de três entradas e de nada mais: a **quantidade** de trabalhadores, o **índice**
na ordem por id, e o `raioDaCasca` da região de modelos. Extrair isso como função pura é
o que separa âncora de espelho.

**De onde vem a identidade e o estado.** `/api/control/snapshot` devolve os sete com
`id`, `role`, `class_name`, `status`, `provider`, `model`, `enabled`, `running`,
`concurrency`. É o runtime declarando os próprios trabalhadores.

**A decisão de desenho que a especificação não cobria.** `runtimeLayer.update(snapshot)`
consome a **trilha de eventos**, e retorna cedo quando ela está vazia. O roster dos sete
não está lá: ele está no snapshot de controle, que o `main.ts` já busca por outro canal.
Portanto a `runtimeLayer` precisa de uma **segunda entrada** para possuir trabalhadores.

Fica decidido que a fonte é o **snapshot de controle**, e não uma lista de papéis
declarada no frontend. O motivo é a própria regra desta ADR: identidade e estado têm de
ter o mesmo dono, e é o controle que sabe qual provedor e qual modelo cada papel resolveu
naquele instante. Uma constante no cliente daria identidade sem estado, e o estado voltaria
a ser buscado noutro lugar — a duplicação de novo, com outro nome.

Consequência: `createRuntimeLayer` ganha o `raioDaCasca` como entrada de âncora, e o
contrato de atualização ganha a via do controle. `composeLayout` já calcula esse raio.

**A armadilha nomeada.** A dependência correta é
`identidade do trabalhador → anchorPose → runtimeLayer possui a entidade`. Se em vez disso
a `runtimeLayer` receber as sete posições prontas da projeção operacional, transfere-se o
objeto sem transferir a autoridade, e a duplicação sobrevive sob outro nome. Enquanto a
projeção ainda os contiver, eles são **fonte legada em migração** — nunca a fonte canônica
do objeto novo.

**Estado inicial obrigatório**, para os sete:
`anchorPose == targetPose == currentPose == posição atual de layoutModels`. O primeiro
commit não produz movimento visível nenhum, e é assim que se prova que o dono mudou sem a
aparência mudar.

**Prova numérica antes da captura**, entidade a entidade:

```
worker id · legacy x/y/z · runtime x/y/z · delta        →  delta ≤ epsilon
```

É o que distingue migração correta de imagem que apenas parece igual.

**O corte, e o número que ele produz.** Só depois da paridade: `operacional/trabalhadores`
sai de `with_runtime_quorum`, e a projeção vai de **1302 para 1295 nós**. Sete nós somem da
projeção e **nada some do Atlas** — é a prova material de que a propriedade mudou de mãos.
A contagem entra na mensagem do commit.
