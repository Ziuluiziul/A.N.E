# ADR-002 — O painel é o nó

**Data:** 2026-08-04
**Estado:** aceito; implementação em incrementos
**Decisão do mantenedor.** Registrada aqui porque muda o núcleo da cena e invalida
parte da ADR-001 em forma, não em critério.

## Contexto

O Atlas nasceu com três camadas visuais para representar uma coisa só:

1. um corpo geométrico por tipo de entidade (esfera=nota, cilindro=MOC, toro=proposta…),
   em `InstancedMesh` — `frontend/src/geometry.ts`;
2. um rótulo de texto colado ao corpo — `labels.ts`;
3. placas operacionais **ligadas por haste** ao corpo que as originou —
   `operationalPanels.ts`.

Isso põe a ontologia na forma, o texto como acessório e a informação numa camada
sobreposta. A aresta liga centros de primitivas, isto é, liga objetos, não conteúdo.

## Decisão

Cada entidade do atlas passa a ser **um painel 2D semântico situado no espaço**. Não
há corpo geométrico, não há haste, não há placa auxiliar. A aresta liga painel a
painel, porque quem se relaciona é o conteúdo.

## 1. Gramática visual

A ontologia migra da primitiva para quatro atributos do painel, e **nunca depende só
de cor** — a exigência da ADR-001 continua valendo integralmente:

| atributo | o que carrega |
|---|---|
| **proporção** | classe da entidade: largo e estável, compacto, horizontal de travessia |
| **faixa de cabeçalho** | categoria escrita por extenso (`MOC`, `NOTA`, `PONTE`, `QUÓRUM`, `TAREFA`, `ENDPOINT`) |
| **organização interna** | quantos blocos o painel tem e o que cada um comporta |
| **tipografia** | peso do título, presença de subtítulo, corpo em uma ou duas colunas |

Cor continua marcando **domínio** (token OKLCH da ADR-001) e nada mais. Estado
epistêmico e operacional se dizem por **texto e ícone**, jamais por matiz sozinho.

O painel é sempre orientado à câmera (billboard) e sempre ocupa posição 3D real. Ele
não é HUD: ele tem lugar no espaço, profundidade e oclusão.

## 2. Taxonomia

| tipo | proporção | cabeçalho | blocos internos | comportamento |
|---|---|---|---|---|
| **MOC** | largo, 16:9 | `MOC · <domínio>` | escopo, rotas de leitura, contagem organizada | âncora territorial; posição estável entre execuções |
| **Nota** | compacto, 4:3 | `NOTA · <domínio>` | descrição, claims, relações, estado epistêmico | numeroso e denso |
| **Ponte** | horizontal, 21:9 | `PONTE · <A> ↔ <B>` | o que liga, por qual mecanismo, **o que não afirma** | primeira classe; declara os dois lados na silhueta |
| **Quórum** | vertical, 3:4 | `QUÓRUM · <estado>` | hipótese, evidências, objeções, votos, confiança, próxima ação | painel deliberativo legível |
| **Tarefa** | pequeno, 1:1 | `TAREFA · <estado>` | objetivo, estado, próximo passo | transitório; some quando encerra |
| **Endpoint** | pequeno, 3:2 | `ENDPOINT · <provedor>` | família, estado, latência, elegibilidade | camada operacional discreta |

O painel de **ponte** é o único cuja silhueta anuncia a função: largura maior que
qualquer outro tipo, cabeçalho com os dois domínios, e um bloco fixo de escopo
negativo. Ele deve poder ser lido como *"liga X e Y, por isto, não por aquilo"*.

O invariante de governança continua: **centralidade não vira grandeza**. O MOC de
raiz tem o mesmo tamanho e o mesmo tratamento de todos os MOCs.

## 3. LOD — densidade, não troca de objeto

Os cinco níveis de `lod.ts` (`distant`, `structural`, `identifiable`, `legible`,
`expanded`), medidos em **pixels projetados** e com histerese, permanecem intactos.
O que muda é o que cada nível mostra. O objeto é sempre o mesmo painel.

| nível | o que aparece |
|---|---|
| `distant` | silhueta e cor de domínio; nenhuma letra |
| `structural` | faixa de cabeçalho com a categoria |
| `identifiable` | título curto |
| `legible` | subtítulo, uma a duas linhas de descrição, métricas-chave |
| `expanded` | painel completo: descrição, claims, relações, evidências, objeções, incerteza, próxima ação, origem e data |

A `ReadingPage` de `labels.ts` deixa de ser um objeto separado: ela **é** o nível
`expanded` do próprio painel. Aproximar aumenta densidade de leitura; nunca troca o
que está sendo olhado.

## 4. Ancoragem das arestas

A aresta deixa de ligar centros e passa a ligar **pontos de ancoragem semânticos na
borda**. A borda de saída é função da família da relação:

| família | sai por | entra por |
|---|---|---|
| `prerequisite` | topo | rodapé |
| `extends` | rodapé | topo |
| `navigation` | rodapé | topo |
| `contrasts` | lateral | lateral oposta |
| `evidence` | lateral direita | lateral esquerda |
| `operational` | lateral | lateral |
| `historical` | lateral | lateral |

Consequência de leitura: dependência corre na vertical, contraste e evidência correm
na horizontal. A relação passa a **costurar** painéis em vez de furar bolhas.

As sete assinaturas de traço de `edges.ts` (`EDGE_STYLES`, com padrão de traço e
marcador por família) continuam válidas e continuam **distinguíveis sem cor** — o
teste que prende isso não muda. O que muda é o peso: opacidade e espessura caem onde
a linha cruza a área de texto de um painel, para a aresta nunca competir com a leitura.

## 5. A grade sai; a referência espacial fica

`depth.ts` hoje materializa três coisas distintas, e só uma delas é grade:

- **cascas territoriais** por domínio (esfera `BackSide`, opacidade 0,055) — **fica**;
  é exatamente o "halo territorial suave" que a direção pede;
- **equadores em wireframe** — **sai**; é a muleta de papel milimetrado;
- **plano atmosférico de referência** — **sai**;
- **névoa exponencial** escalada à malha — **fica**; é o que dá profundidade sem desenho.

Resultado: o espaço continua organizado por profundidade, halo e densidade, sem
parecer editor técnico.

## 6. Corpus e operacional

Uma única gramática, duas escalas de protagonismo:

- painéis de corpus ocupam a faixa de tamanho maior e a camada `z` do epistêmico;
- painéis operacionais ficam **um degrau abaixo** em tamanho e opacidade de fundo, na
  camada `z` operacional já definida em `sizing.ts`;
- a camada operacional some por inteiro no filtro global, e o corpus nunca some.

Transparência deliberativa é forte, mas **estruturada**: o painel de quórum mostra
hipótese, evidências, objeções, votos com procedência, confiança, incerteza e próxima
ação. O que ele não faz é despejar cadeia de raciocínio crua — isso continua fora do
contrato de projeção, como já está em `runtime.ts`, e é também o que o commit
`c28492b` decidiu.

## 7. Linguagem natural

Regra formal: **todo texto de painel é frase, não campo**.

| em vez de | escreve-se |
|---|---|
| `ok · 4552 ms · n=17` | Respondeu em 4,5 s na última sonda, com histórico de 17 medições. |
| `approve 1 · reject 0` | Recebeu um voto favorável e nenhum contrário. |
| `schema_valid: false` | A resposta não contou porque falhou na estrutura exigida. |
| `2 valid votes; min 3` | Faltou um avaliador legível para o painel poder decidir. |

Acessível sem empobrecer: nenhum conceito é trocado por versão vaga.

## 8. Plano de implementação

Cinco incrementos, cada um verde nos três gates e utilizável ao fim:

1. **`panels.ts` — descritor único.** Generalizar `describeOperationalPanels` para
   todo nó do contrato, devolvendo `PanelDescriptor` puro (categoria, título,
   subtítulo, linhas por nível de LOD, âncoras, token). Sem tocar na cena: só função
   pura e teste. É o que torna o resto verificável sem GPU.
2. **Placas instanciadas.** Uma `InstancedMesh` de quads substitui as malhas por tipo.
   `geometry.ts` some como corpo; `sizing.ts` passa a devolver largura e altura em vez
   de raio. Picking migra para os quads.
3. **Texto por orçamento.** Pool fixo de objetos `Text` do troika, atribuídos aos
   painéis mais próximos por LOD. Fora do orçamento, o painel fica silhueta.
4. **Arestas por borda.** Ancoragem semântica e atenuação sobre área de texto.
5. **Subtração da grade.** Remoção de equadores e plano; ajuste da névoa.

## 9. Riscos de performance

| risco | por quê | mitigação |
|---|---|---|
| explosão de draw calls | um `Text` do troika é um objeto próprio; 84 painéis × 6 linhas seriam centenas | pool fixo por orçamento de LOD; só `legible` e `expanded` recebem texto |
| custo de atualização de billboard | orientar 84 painéis por quadro | orientar só os visíveis, e reaproveitar a quaternion da câmera |
| retipagem de texto | trocar string em `Text` reconstrói geometria | trocar apenas na mudança de nível, com histerese que já existe |
| sobreposição de painéis | placa ocupa muito mais área que esfera | `footprint()` cresce para a diagonal do painel; o layout já usa footprint para separar |
| transparência e ordenação | painel com fundo translúcido sobre casca territorial | `depthWrite: false` nas cascas e `renderOrder` explícito, como já se faz |

## 10. Reaproveitar, descartar, preservar

**Reaproveita integralmente:** `lod.ts` (níveis, limiares, histerese), `palette.ts` e
a ADR-001, `layout.ts` e `layoutStore.ts` (posição estável entre execuções),
`edges.ts` (assinaturas por família, `dashSegment`), `contract.ts` (fronteira
sanitizada), `depth.ts` na parte de cascas e névoa, o padrão de **descritor puro** de
`operationalPanels.ts`.

> **Nota de 2026-08-12.** Dois nomes desta seção não existem mais, e a decisão que os
> citava continua valendo. `dashSegment` virou `dashPath`, sobre polilinha, quando a
> aresta passou a curvar-se em torno das placas que atravessaria (`edgePath.ts`).
> `footprint()` saiu: ele derivava do raio das esferas que esta própria ADR aposentou, e
> a separação passou a medir a diagonal da placa (`panelSweepRadius`). As cascas de
> `depth.ts` também saíram — o que ficou lá é o campo de grãos que corre conforme o
> trabalho declarado.

**Descarta:** `geometry.ts` como corpo de nó; a haste e o conceito de placa auxiliar;
os equadores e o plano de referência de `depth.ts`; `createLabel` como objeto
separado; `createReadingPage` como objeto separado.

**Preserva como invariante, com teste:**

1. centralidade não vira grandeza — o MOC de raiz tem o mesmo tamanho e o mesmo
   tratamento emissivo de todos os MOCs;
2. domínios permanecem perceptivelmente distintos e com luminosidade próxima;
3. nenhuma informação depende só de cor;
4. degraus de tamanho discretos, e MOC não é maior "por muito";
5. camadas em `z` sem inverter a hierarquia;
6. proposta não ganha falsa solidez;
7. LOD medido em pixels projetados, com histerese;
8. cada família de relação tem assinatura própria sem usar cor;
9. nenhum raciocínio bruto atravessa a fronteira de projeção;
10. movimento só quando significa algo — nada de respiração, órbita ou partícula.

## Consequência sobre a ADR-001

A ADR-001 continua íntegra no que decide: paleta OKLCH, distância perceptual mínima,
proibição de informação por cor sozinha. O que muda é onde a cor se aplica — antes em
corpos geométricos, agora em faixa de cabeçalho e borda de painel. Nenhum token muda.
