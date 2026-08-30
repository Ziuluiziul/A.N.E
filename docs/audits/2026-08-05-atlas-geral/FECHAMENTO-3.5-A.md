# Fechamento de 3.5-A — separação do espaço operacional

**Base:** `1457d93` (auditoria `f15adc0`, adendo `713df2a`)
**Escopo:** separar o frame de coordenadas do corpus do frame do observatório de execuções.
**Resolve:** F-04, F-06, F-11 do `FINDINGS.md`.

---

## 1. O que mudou

O atlas epistêmico e o observatório operacional passam a ser **dois frames de
coordenadas independentes**, calculados sem se conhecerem e compostos num lugar só
(`composeLayout.ts`), com dependência de mão única: o observatório consulta o raio do
corpus para se afastar dele, e o corpus não consulta nada da camada viva.

Dentro do observatório, cada execução vira um **sistema local**: o painel na base, os
avaliadores em leque acima dele, o voto de cada avaliador adiante do próprio avaliador,
e a decisão sozinha no topo do eixo. `z` deixa de ser só volume e passa a medir a
progressão do processo — ler a coluna de baixo para cima é ler a execução na ordem em
que ela aconteceu. As 35 execuções se assentam numa espiral de Fermat ordenada por data:
antigas no miolo, novas para fora.

## 2. Prova de deslocamento zero

O defeito que motivou o incremento, medido diretamente:

```
estado anterior (include:'all'): deslocamento máximo de MOC = 69,12 unidades
depois de 3.5-A:                deslocamento máximo de MOC =  0,00 unidades
```

Na projeção viva, com 278 nós de quórum:

| Medida | Valor |
|---|---|
| Deslocamento máximo de MOC | **0** |
| Deslocamento máximo de nota epistêmica | **0** |
| Testado com 1, 32, 100 e 1.000 nós operacionais | **0 em todos** |
| Posições sob permutação da ordem de entrada | idênticas |
| Execuções anteriores ao acrescentar uma nova | inalteradas |

## 3. Métricas de tela

Em `metrics-3.5-A.json`, medidas na mesma viewport (1600×900), contando **só caixas de
nós** — arestas, cascas e ambiente ficam de fora, conforme a ressalva do parecer sobre a
métrica de pixels não-fundo.

| Métrica | Antes | Depois |
|---|---|---|
| `extentOf` da visão de corpus | 246,82 | **92,31** |
| Ocupação do viewport por caixas de nós | 0,87% | **6,01%** (6,9×) |
| Paralaxe mediana numa órbita padronizada | 1,23 px | **2,19 px** (+78%) |
| Entidades recortadas pela borda | 0 | 0 |
| Entidades totalmente ocluídas | 1 | 1 |

**O que não melhorou, dito sem rodeio.** A área absoluta de intersecção entre caixas
cresce de 4.853 px² para 38.522 px². Normalizada pela área de nós — que é a comparação
justa, já que o corpus está 6,9× maior na tela — a sobreposição vai de **0,387 a 0,445**:
piora levemente. 3.5-A separou frames e **não** tratou oclusão dentro do corpus. Isso é
3.5-B (layout volumétrico) e 3.5-C (orçamento de arestas), e fica registrado como não
resolvido em vez de apresentado como ganho.

## 4. Integridade das execuções

| Critério | Resultado |
|---|---|
| 35 painéis → 35 agrupamentos locais | ✅ |
| Cada avaliador pertence a exatamente um painel | ✅ |
| Cada voto pertence ao painel e ao avaliador corretos | ✅ |
| Cada decisão pertence a exatamente um painel | ✅ |
| Mistura entre identificadores de execução | 0 |
| Órfãos silenciosos | 0 — e um órfão sintético é **reportado e não assentado** |
| Votos sem avaliador | 0 — e um voto sem aresta é contado e assentado em anel próprio |

## 5. Isolamento por camada, verificado por inventário de cena

Não por captura: por varredura dos objetos efetivamente visíveis, com as caixas em
coordenadas de mundo.

| Camada | Objetos nomeados visíveis | Faixa em `x` |
|---|---|---|
| corpus | `panels:*`, `edges:operational`, `edges:aggregated` | −78 a 80 |
| operacional | `panels:*`, `edges:operational` | **202 a 529** |
| ambas | os dois conjuntos | −78 a 529 |

Na visão operacional **nenhum objeto do corpus é desenhado** — nem placa, nem texto, nem
casca territorial, nem filamento inter-MOC.

## 6. Três defeitos encontrados durante a implementação

Registrados porque nenhum deles aparecia na auditoria e os três eram invisíveis em teste.

1. **`domainFallbackCenter` ainda recebia `projection.nodes.length`.** O filtro por
   camada foi aplicado ao anel principal, mas o centro de agrupamento sem âncora
   continuava contando a projeção inteira. Pego pelo teste de raio do corpus, não por
   inspeção.
2. **A camada de eventos ao vivo recebia a extensão composta.** `createRuntimeLayer`
   dimensiona o próprio anel pelo que recebe; com o mundo composto, esse anel passava a
   medir 529 unidades e os eventos se espalhavam por cima do atlas inteiro. Agora ela
   recebe só as posições do corpus, que é o que ela anota.
3. **Família de relação não é camada de cena.** `operational` é ao mesmo tempo o nome de
   uma camada e o de uma família de relação que o corpus declara em wikilink. Agrupar as
   arestas pelo nome da família fazia as arestas *epistêmicas* marcadas
   `relation:operational` acompanharem o observatório e reaparecerem sobre o corpus
   escondido. As arestas passam a ser agrupadas por **camada**.

## 7. Cache de layout

A chave de gravação passa a ser `<fingerprint>-layout1-op1`. A impressão digital
identifica o corpus, não a geometria; sem a versão do algoritmo, a cena reabriria com as
posições da versão anterior e a correção pareceria não ter surtido efeito — era o risco
registrado no roadmap. Nada é apagado: o que muda é a chave que se lê.

A camada viva **não é mais persistida**: a chave é a impressão do corpus, que não muda
quando um painel de quórum entra, e gravar posição de execução sob ela faria uma execução
nova reaparecer no lugar de uma antiga.

## 8. Interface

Novo controle `C`, quinto da barra: alterna **corpus → observatório → ambos**. A cena
abre em `corpus`, e não em `ambos`: o produto é um atlas de conhecimento, e o
observatório é uma segunda leitura, pedida explicitamente.

A névoa passa a ser escalada à camada ativa. `FogExp2` dissolve pela distância ao
quadrado, e a densidade vinha da extensão do corpus; com os dois frames em cena a câmera
recua além de mil unidades e a mesma densidade apagava tudo — a visão composta saía
uniformemente escura. Reescalar não move nada; muda o alcance do horizonte, que a troca
de camada já mudou.

## 9. Testes

`frontend/src/operationalLayout.test.ts`, 16 testes novos. Os de estabilidade
**reprovavam no estado anterior**, o que foi verificado executando o layout com
`include: 'all'` — o comportamento de antes — e medindo os 69,12 unidades da seção 2.

Suíte: 233 testes (eram 217).

## 10. Gates e higiene

| Item | Resultado |
|---|---|
| `make audit` | APROVADO, manifesto `e48f4791…` inalterado |
| `make test` | 387 pytest + 233 vitest |
| `make lint` | ruff, mypy (99 arquivos), eslint — limpos |
| `knowledge/` | **intocado** |
| Working tree | limpa |
| Segredos | nenhum lido, nenhum exposto |

## 11. Escopo respeitado

Não foram tocados: materiais e transparência, wireframe de estados provisórios, desenho
das relações recíprocas, agregação inter-MOC, câmera de aproximação manual, contrato de
falhas, conteúdo dos painéis de deliberação, cascas territoriais.

Duas mudanças fora da separação estrita, ambas necessárias para que a separação fosse
observável, e ambas declaradas: a névoa por camada (§8) e a exposição de `scene` no
`AtlasHandle`, somente para inspeção — sem ela, provar isolamento dependeria de adivinhar
qual objeto ainda desenha, já que a aba de auditoria não compõe quadros.

## 12. Fica para depois

- **A camada de eventos ao vivo (SSE) ainda é um terceiro conjunto espacial**, com 160
  nós amarrados ao corpus e materiais em wireframe. Ela aparece como massa densa no alto
  da captura `ac-01-corpus-isolado.png`. Não entra em 3.5-A: seu material é 3.5-D e sua
  leitura é 3.5-G.
- **Sobreposição perceptiva dentro do corpus** — §3, não resolvida, endereço em 3.5-B/C.
- **Enquadramento do observatório** deixa uma faixa vazia embaixo, por a espiral ser
  achatada sob visada oblíqua. Cosmético; entra com 3.5-B.
