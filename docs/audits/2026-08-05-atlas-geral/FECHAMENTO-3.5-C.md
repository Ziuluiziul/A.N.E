# Fechamento de 3.5-C — semântica e orçamento das relações

**Base:** `6ce91a4` · **Escopo:** reduzir a dominância visual das relações sem perder
nenhuma relação do corpus.

---

## 1. As três camadas

A tentação, diante de 129 pares desenhados duas vezes, era deduplicar. Seria errado: a
recíproca é declarada no corpus, é legítima, e apagá-la perderia conhecimento. O
incremento separa os níveis para que reduzir o que se desenha nunca reduza o que se sabe.

| Camada | Onde vive | Conteúdo |
|---|---|---|
| **registro semântico** | `relationRegistry.ts` → `semantic` | as 555 relações dirigidas, intactas, com `directedKey` e proveniência |
| **registro canônico** | `relationRegistry.ts` → `pairs` | um par não ordenado, com os dois sentidos dentro |
| **primitivas** | `edges.ts`, `atlas.ts` | o que a cena emite, variável com contexto e orçamento |

A regra que amarra os três: de qualquer primitiva se recupera o par, e de qualquer par se
recuperam as relações dirigidas que ele representa. `provenanceOf(pairKey)` é o caminho
de volta, e o teste 14 confere que ele cobre todas as relações.

### Tabela de correspondência

| Relação semântica | Registro canônico | Primitiva |
|---|---|---|
| `A →prerequisite B` | par `A B`, `forward=[…]` | uma linha contínua com seta em B |
| `A →prerequisite B` + `B →prerequisite A` | par `A B`, `reciprocal` | **uma** linha, seta nas duas pontas |
| `A →prerequisite B` + `B →contrasts A` | par `A B`, `familiesDifferByDirection` | **duas faixas** deslocadas, cada uma com a assinatura do próprio sentido |
| três famílias no mesmo par | par com `families` de 3 | uma primitiva com a família dominante; o resto sai na seleção |
| `MOC A ↔ MOC B` | agregado por par **não ordenado** | um tubo, com `weightByDirection` e `relationsByDirection` |
| `A →extends A` | par com `selfLink` | nenhum segmento — e o registro continua tendo a relação |

## 2. Os três defeitos corrigidos

**Recíprocas coincidentes.** `buildRelationLines` desenhava uma linha por aresta
dirigida. Como A→B e B→A têm os mesmos dois extremos, as duas caíam sobre o mesmo
caminho: **136 segmentos exatamente coincidentes**, e em 49 pares as assinaturas de
famílias diferentes se somavam no mesmo pixel. Agora o desenho parte do par: a direção
vira marcador, e famílias diferentes viram duas faixas deslocadas — cada sentido conta a
própria história sem destruir a do outro.

**Agregação inter-MOC por par ordenado.** `projection.py` chaveava por `(origem,
destino)`, e um par de MOCs com tráfego nos dois sentidos produzia **duas** arestas
agregadas: 75 filamentos para 52 pares, 23 pares com dois tubos de flecha e espessura
diferentes. Em 10 deles cada tubo elegia uma relação dominante própria, e a mesma ponte
declarava `prerequisite` num sentido e `contrasts` no outro. A chave passou a ser o par
não ordenado, e a direção virou dado do agregado — `weightByDirection`,
`relationsByDirection`, `reciprocal`.

**Espinha fixa na visão global.** `buildStructuralSpine` desenhava, de uma vez, as 223
relações que tocam alguma âncora — 40% do corpus — sempre que a câmera entrava na banda
intermediária. Ela saiu de `edges.ts`. A espinha agora é reescrita por território, a
partir do registro canônico e sob orçamento de 48 primitivas, e a visão global mostra
apenas as pontes agregadas.

## 3. Estados contextuais

| Estado | Como se entra | O que aparece |
|---|---|---|
| **global** | sem seleção, câmera afastada | só os 52 tubos agregados |
| **domínio** | selecionar um MOC, ou aproximar-se de um território | agregados + até 48 pares internos daquele território |
| **nó** | selecionar qualquer outra entidade | agregados + ego de grau 1 e 2 |

Selecionar um MOC **é** focar o domínio: o MOC é a âncora do território, e a pergunta de
quem o escolhe é "como este território se organiza", não "o que este nó toca". Sem essa
regra o estado de domínio era quase inalcançável — aproximar-se de uma âncora para a
câmera a ~120 unidades, fora da banda de 94.

## 4. Resultados

Em `metrics-3.5-C.json`, medidos na pose fixa.

### Integridade

| Critério | Resultado |
|---|---|
| Relações semânticas preservadas | **555**, zero perda |
| Proveniência recuperável de toda primitiva | sim (teste 14) |
| Segmentos exatamente coincidentes | **136 → 0** |
| Agregadas inter-MOC | **75 → 52**, uma por par não ordenado |
| Agregadas duplicadas por inversão do par | **0** |

### Primitivas visíveis por estado

| Estado | Antes | Depois | |
|---|---:|---:|---|
| global | 298 | **52** | **−82,6%** (exigido ≥60%) ✅ |
| domínio focado | 298 | **≤100** | −66,4% |

O "antes" da visão global é 75 tubos mais a espinha de 223, que era o que a cena
efetivamente emitia ao aproximar-se de qualquer território.

### Desenho com todas as relações ligadas

| Métrica | Antes | Depois | |
|---|---:|---:|---|
| Primitivas | 555 | **426** | −23,2% |
| Segmentos | 7.447 | **5.898** | −20,8% |
| Cruzamentos projetados | 36.983 | **14.214** | **−61,6%** (exigido ≥50%) ✅ |
| Densidade máxima por célula | 98 | **58** | −40,8% |
| Ocupação com sobreposição | 0,1533 | 0,1417 | −7,6% |

A redução de cruzamentos é muito maior que a de segmentos, e isso não é acaso: o que
some são justamente as linhas que ocupavam o mesmo caminho de outra, e cada uma delas
cruzava tudo que a companheira cruzava.

### Estabilidade, medida no navegador

| Verificação | Resultado |
|---|---|
| Objetos na cena, início | 123 |
| Após 40 seleções e desseleções | 123 |
| Após 100 alternâncias de camada | 123 — crescimento **0** |
| Quadro parado | 6.522 → 6.522 sincronizações, 0 objetos criados |
| Volta ao global | 1 objeto de aresta, **zero resíduo** |
| Pool de texto | 64 de 64, invariante mantido |

## 5. Testes

`frontend/src/relationRegistry.test.ts`, 13 testes — os casos 1 a 8, 11, 12, 13, 14 do
parecer, mais a preservação da contagem entre registros.

Os casos **9, 10 e 15** — troca de estados, seleção repetida e 100 alternâncias — exigem
WebGL e ficam na verificação de navegador, registrada em §4 e em `metrics-3.5-C.json`.
É a mesma divisão que `visual.test.ts` já declara: o que precisa de GPU não entra na
suíte headless.

Backend: `tests/test_projection.py` ganhou dois testes — unicidade do agregado por par
não ordenado e preservação da direção que a unificação absorveu. O teste que prendia a
agregação por par ordenado foi corrigido: ele pinava o defeito.

Suítes: **389 pytest** e **261 vitest**.

## 6. Escopo respeitado

Não foram tocados: conteúdo do corpus, posições dos nós, materiais finais, transparência
geral, câmera de zoom manual, cascas territoriais, conteúdo dos painéis de deliberação.

## 7. Fica para depois

- **A visão "todas as camadas" continua diagnóstica**, não cotidiana: o corpus fica
  pequeno e há muito vazio entre os dois frames. Precisa de transição e foco entre
  frames, não de mais orçamento de arestas.
- **A camada SSE segue visualmente inutilizável quando ligada** — massa de wireframes
  sem agrupamento. Tem registro e orçamento próprios desde 3.5-B; falta representação.
- **O orçamento de domínio corta pelo fim de uma lista ordenada por grau.** É escolha
  editorial declarada, e melhor que a alternativa anterior — que era não cortar —, mas
  não é a única possível.
- **Cruzamentos foram medidos na pose fixa.** Uma medida ao longo de uma órbita fecharia
  isso, e é a mesma dívida de oclusão que 3.5-B deixou.
