# Fechamento de 3.5-B — layout volumétrico e redução de oclusão

**Base:** `b69244e` (3.5-A aprovado) · **Escopo:** as cinco precondições do parecer, e
depois o layout volumétrico dos 84 nós epistêmicos.

---

## 1. As cinco precondições

### 1.1 Dois protocolos de medição

`frontend/src/screenMetrics.ts`, módulo versionado e não descartável:

- **câmera fixa** — `POSE_FIXA`, constante declarada, idêntica entre cenários. A única
  variável que muda são as posições, então o que ela mede é causalmente o layout.
- **autoenquadramento** — a pose de `cameraPoseForExtent` para a extensão de cada
  cenário. Mede o que o usuário recebe.

Ambos contam **apenas caixas de painel**; aresta, casca e ambiente ficam fora.

### 1.2 Correção da afirmação anterior

O parecer está certo e a imprecisão foi minha. As métricas de 3.5-A usaram a mesma
**viewport** e poses **diferentes**. O JSON daquele incremento dizia isso no campo
`metodo`, mas eu afirmei "na mesma câmera" ao relatar, e o `FECHAMENTO-3.5-A.md`
deixava a leitura ambígua. Consequência aceita: o ganho de ocupação de 3.5-A é
atribuível ao autoenquadramento, e o de paralaxe não podia ser atribuído ao layout.

### 1.3 Estabilidade da espiral operacional

O ordinal de cada execução passa a ser **atribuído uma vez e gravado**
(`operational-slots-v2`). Quem tem ordinal mantém o seu; quem chega ocupa o menor livre,
na ordem cronológica — o caso comum produz a mesma espiral de antes.

Cinco formas de quebrar a ordenação por data, todas testadas e todas com deslocamento
zero: inserção retroativa, timestamps iguais, correção de data, relógio fora de ordem,
data ausente e reimportação completa em ordem invertida.

Sem backend não há ordinal gravado e o assentamento deriva da ordem de chegada —
determinístico, e declarado.

### 1.4 `scene` deixou de ser exposta

Substituída por `inspect(): SceneObjectInfo[]`, que devolve uma **cópia** — nome, tipo,
visibilidade efetiva na cadeia até a raiz, contagem de instâncias e caixa em coordenadas
de mundo. Nenhum objeto Three.js sai do módulo.

Ressalva de fidelidade: para `InstancedMesh` a inspeção descreve a **malha**, não cada
instância. Uma malha cujas instâncias estão todas recolhidas aparece como visível — foi
o caso de `panels:temporary:operational` na visão de corpus. A conferência de isolamento
usa a caixa de mundo dos objetos com geometria própria, que é onde o vazamento apareceria.

### 1.5 A camada SSE ganhou camada própria

`SceneLayer` passa a ter três populações: `corpus`, `operacional` (execuções concluídas,
frame próprio) e `vivo` (os 167 eventos SSE, amarrados por haste às entidades do corpus).

- não participa do layout nem do `extentOf` epistêmico;
- alternável pelo controle `C`, que agora cicla corpus → observatório → vivo → todas;
- **fora por padrão**;
- métricas próprias em `textMetrics()`: `corpusNodes`, `observatoryNodes`, `liveNodes`.

Isolamento conferido por `inspect()`, com as caixas em `x`:

| Camada | Objetos com geometria própria |
|---|---|
| corpus | epistêmicos `[-104..93]`, agregadas `[-78..80]` |
| vivo | os acima, mais SSE `[-59..32]` e arestas SSE `[-56..29]` |
| operacional | observatório `[214..540]` e arestas `[214..540]` |
| todas | todos |

## 2. O layout volumétrico

Três defeitos de layout, em ordem de impacto.

**O relaxamento separava por um quarto do necessário.** `footprint()` derivava de
`BASE_RADIUS`, o raio dos corpos primitivos que a ADR-002 tirou de cena. Para uma nota
vale 2,0 unidades — e a placa que a nota desenha tem 9,2 de diagonal. A sobreposição
existia **por construção**: nenhuma quantidade de iterações resolve uma distância mínima
4,6× pequena demais. Agora a separação usa a meia-diagonal da placa real, que é a medida
certa porque a placa é orientada à câmera e o que precisa caber é o círculo que ela varre.

**A âncora nunca entrava na colisão.** `clusterize` deixa os MOCs de fora, então o
primeiro membro nascia no centro do território — o MOC de Física a **1,6 unidades** de um
membro, cobrindo a placa dele por inteiro. A âncora passa a ser obstáculo **imóvel**:
empurra e não é empurrada, porque o azimute dos MOCs é a identidade do domínio.

**Oclusão total não é proximidade, é alinhamento.** As duas que sobravam estavam a 32,7 e
66,6 unidades, em agrupamentos diferentes. Uma passagem final desalinha, em ângulo, os
pares em que a placa da frente cobre por inteiro a de trás, empurrando perpendicular ao
raio — a profundidade, que carrega a estrutura, fica intacta, e MOCs não se movem.

Honestidade sobre o alcance: essa passagem garante zero oclusão total **na direção
canônica**, que é a que o produto abre. Orbitando, o usuário encontra outros
alinhamentos. Nenhum layout de placas orientadas à câmera evita isso em todas as
direções, e prometer o contrário seria falso.

## 3. Resultados

Em `metrics-3.5-B.json`.

### Autoenquadrado — contra a baseline do parecer

| Métrica | Baseline | Agora | Critério | |
|---|---:|---:|---|---|
| Pares que se intersectam | 118 | **29** | ≤ 90 | ✅ |
| Intersecção `/ ocupação` | 0,4451 | **0,0726** | ≤ 0,33 | ✅ |
| Totalmente ocluídas | 1 | **0** | 0 | ✅ |
| Recortadas | 0 | **0** | 0 | ✅ |
| Ocupação do viewport | 0,0601 | **0,0602** | 0,045–0,085 | ✅ |

A baseline foi **reproduzida exatamente** (0,4451) antes de medir o depois, o que valida
a cadeia de medição.

### Câmera fixa — o protocolo causal

| Métrica | Antes | Depois | |
|---|---:|---:|---|
| Intersecção `/ área de caixas` | 0,3376 | **0,0639** | **−81,1%** (exigido ≥ 25%) ✅ |
| Pares | 124 | **26** | −79,0% |
| Totalmente ocluídas | 0 | 0 | mantido |
| Separação angular mediana | 14,82° | 14,77° | **−0,05°** |
| Paralaxe relativa mediana | 3,33 px | **4,07 px** | +22% |

### Dispersão espacial

| Medida | Antes | Depois |
|---|---:|---:|
| Variância em `z` | 146,4 | **317,2** |
| σ3/σ1 | 0,2043 | **0,2996** |
| λ3/λ1 | 0,0417 | 0,0900 |

Reportadas as três, e não só λ3/λ1: um único quociente de autovalores pode subir sem que
a leitura melhore, e σ3/σ1 — que está em unidades de comprimento — descreve melhor o que
se vê.

### Separação angular: um trade-off, não uma preservação

> **Correção de 2026-08-05.** A primeira versão desta seção dizia "sem regressão". Está
> errado: a separação angular caiu nos quatro números, e o parecer de aceitação apanhou
> isso.

| Protocolo | Mediana | Mínima |
|---|---|---|
| câmera fixa | 14,82° → **14,77°** (−0,05°) | 3,07° → **2,86°** (−0,21°) |
| autoenquadrado | 19,13° → **17,39°** (−1,74°) | 4,27° → **3,34°** (−0,93°) |

A queda é real e tem causa direta: espalhar os territórios até a escala das placas
aproxima os centroides em ângulo visto da câmera. É um **trade-off controlado** — troca-se
até 1,74° de separação angular mediana por uma redução de 81% na intersecção projetada e
pela eliminação da oclusão total. Nenhuma tolerância havia sido declarada antes da
medição, e declarar uma depois de ver o resultado seria justificar em vez de medir; o
número entra como está, com o custo à vista.

### Nota de método sobre o denominador

Os dois denominadores são legítimos, medem coisas diferentes e **passaram a ter nomes
diferentes** — reutilizar `interseccaoRelativa` para ambos era ambiguidade métrica, e o
parecer apanhou isso também:

- `intersectionOverBoxArea` — divide pela soma das áreas das caixas, que conta a área
  sobreposta duas vezes. Responde "que fração do desenho é redundante". Foi por ele que
  o JSON calculou a redução de 79,1% no autoenquadramento (0,3262 → 0,0683).
- `intersectionOverViewportOccupancy` — divide pela área efetivamente ocupada, contando
  cada pixel uma vez. Responde "quanto do que se vê está disputado". É o denominador dos
  critérios de aceite, e por ele a redução autoenquadrada é de **83,7%**
  (0,4451 → 0,0726).

A tabela autoenquadrada acima usa o segundo. As duas reduções estão no JSON, separadas e
rotuladas.

## 4. Escopo respeitado

Não foram tocados: arestas, transparência, materiais finais, zoom manual, cascas
territoriais e conteúdo dos painéis de deliberação.

Uma mudança de comportamento fora do layout, declarada: o controle `C` passou a ciclar
por quatro estados em vez de três, consequência direta da precondição 1.5.

## 5. Testes

`frontend/src/volumetric.test.ts`, 15 testes novos: as seis formas de bagunça temporal,
zero oclusão nos dois protocolos, a âncora sem invadir membro, profundidade estrutural,
separação angular, determinismo sob permutação, uma nota nova reacomodando só o próprio
domínio, e o cache reaberto devolvendo o gravado.

Suíte: **248 testes** (eram 233).

## 6. Gates e higiene

| Item | Resultado |
|---|---|
| `make audit` | APROVADO, manifesto `e48f4791…` inalterado |
| `make test` | 387 pytest + 248 vitest |
| `make lint` | ruff, mypy, eslint — limpos |
| `knowledge/` | intocado |
| Working tree | limpa |
| Segredos | nenhum lido, nenhum exposto |

## 7. Fica para depois

- **A oclusão é garantida numa direção**, não em todas — §2. Um orçamento de oclusão
  medido ao longo de uma órbita completa seria o fechamento honesto disso, e não cabia
  aqui.
- **Os 167 nós SSE continuam em wireframe** quando a camada `vivo` é ligada. Agora são
  uma camada declarada, contada e desligável; o material é 3.5-D.
- **`inspect()` descreve malha, não instância** — §1.4.
- **A codificação do ordinal em `x`** acomoda o formato do armazenamento de layout
  existente. Trocar por armazenamento próprio é barato e não urgente.
