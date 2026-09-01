# ADR-003 — Instrumentação e homeostase antes de morfogênese

**Data:** 2026-08-14 · **Estado:** aceito · **HEAD na decisão:** `d8b5f5a`
**Decidido por:** troca multimodelo entre Claude Opus 5 (medição e relatório) e ChatGPT
(proposta e revisão), com o mantenedor arbitrando.
**Origem:** crítica de Anirban Bandyopadhyay ao Graph Engineering
(https://x.com/anirbanbandyo/status/2088425573102317600).
**Evidência:** frente morfogênica de 2026-08-14 (arquivo interno, fora da
superfície do produto) e o pacote que a acompanha.

## Contexto

A proposta inicial era acrescentar ao A.N.E. uma camada `Morphogenic Runtime` entre o
substrato de modelos e a camada epistêmica: topologia adaptativa, diferenciação
funcional, apoptose, mitose, gradientes, quimiotaxia, homeostase e cicatrização, com o
Atlas virando morfoscópio e as coordenadas `(x,y,z)` passando de fundamento a
consequência.

A medição do repositório em 2026-08-14 mostrou que o diagnóstico acerta a classe dos
defeitos — os quatro commits daquele dia são, em retrospecto, quatro funções
morfogênicas escritas à mão —, mas que o substrato de sinais não existe:

- 296 tentativas de `corpus_review` produziram **uma** decisão;
- dos seis sinais que a proposta nomeia, o sistema mede dois (latência e
  confiabilidade), nenhum por domínio;
- os votos de 156 painéis estão gravados em disco e **nunca são lidos de volta**;
- 27 dos 44 últimos fracassos foram rate limit ou orçamento — congestionamento de
  substrato, não excesso de rigor epistêmico;
- o único painel que concluiu aprovou, por 2 votos de 3 **do mesmo provedor**, um patch
  que substituiria uma nota de 73 linhas por um stub de dez.

## Decisão

**O próximo incremento não é um `Morphogenic Runtime`. É instrumentação e um plano de
controle homeostático.** A morfogênese permanece direção arquitetural válida; fazê-la
emergir agora produziria comportamento adaptativo sobre sinal quase inexistente.

A sequência aceita:

```
M0  Outcome/Telemetry Ledger        eventos primários legíveis de volta
M1  Quorum Capacity Estimator       quantos painéis válidos cabem na capacidade de agora
M2  Homeostatic Admission Controller regula nascimento, admissão e espera das tarefas
M3  Reviewer/Endpoint Calibration   competência só depois de haver desfecho
M4  Adaptive Assignment             histórico afeta seleção, com piso rígido de diversidade
M5  Morphogenic Tissue no Atlas     tecido móvel sobre cartografia estável
```

### O que se persiste (M0)

Evento primário por chamada e por voto, não inteligência derivada:

```
timestamp · task_id · panel_id · task_kind · domain · role
provider · endpoint · family · eligible_at_start
estimated_tokens · actual_tokens · latency · outcome_class · schema_valid
vote_decision · confidence · patch_digest
validation_outcome · promotion_outcome
```

Quatro superfícies derivam disso: **capacidade** por endpoint e provedor; **aptidão
operacional** por `endpoint × role × domain` — probabilidade de entregar resposta
utilizável, que não é competência epistêmica; **calibração do revisor**, que só existe
quando houver desfecho independente; e **custo de fechamento** por painel que concluiu.

Ficam de fora por ora: contribuição marginal, afinidade semântica, score global e
reputação única — a amostra é pequena demais e produziriam número com aparência
estatística e conteúdo quase nulo. A única métrica marginal barata e admitida é
recalcular a decisão retirando um voto por vez e marcar o revisor como `pivotal`,
`redundant` ou `non_decisive` — isso mede influência sobre a decisão, não qualidade.

### Como a alça de calibração fecha antes da primeira promoção (M3)

Promoção não precisa ser o primeiro desfecho. `ProposalPromoter.validate()` já roda as
guardas reais em worktree temporária sem tocar no corpus: os 18 patches em disco podem
gerar imediatamente a primeira população de desfechos, com
`structural_validation`, `preservation_validation`, `projection_validation`,
`promotion_eligible` e a guarda que recusou.

A calibração é **por camada**, nunca colapsada num score único:

```
L0  envelope/schema
L1  integridade estrutural e preservação
L2  consistência e projeção
L3  evidência factual verificável
L4  sobrevivência posterior do patch
```

O `revisor-estrutural` se calibra contra L1 e L2, que são determinísticos. O
`verificador-factual` **não** se calibra contra `audit.py` passar — precisa de desfecho
factual independente. O `critico-epistemologico` se calibra contra mudança posterior de
status de claim. Um consenso pode estar certo em L1 e errado em L3, e foi exatamente
isso que o painel do stub demonstrou.

Consequência: **consenso e dissenso não provocam morfologia diretamente.** Passam antes
pela calibração. Desacordo entre dois revisores calibrados é sinal de outra natureza que
desacordo entre dois endpoints que mal devolvem envelope válido.

### Regulação vai na demanda, não no rigor (M2)

Não se mexe agora em 3 votos válidos, 2 provedores e 3 famílias para `corpus_review`. Os
números apontam congestionamento de substrato, e o único painel concluído é advertência
contra afrouxar o quórum.

A arquitetura hoje inicia trabalho e descobre depois que não há capacidade para fechá-lo:
o proponente é gasto antes de o painel de revisores ser planejado. A precedência se
inverte — *preflight* de capacidade antes de nascer a tarefa:

```
quorum_capacity(t) = número máximo de conjuntos disjuntos de revisores que satisfazem
                     votos ≥ 3 · provedores ≥ 2 · famílias ≥ 3 · quota disponível
```

Com `quorum_capacity == 0`, nenhuma `corpus_review` nova nasce naquele instante.
"Reservar" é contabilizar contra o ledger de planejamento, como `plan_batch()` já faz com
sua cópia do `QuotaLedger` — não exige locking pesado.

E **tarefa impedida por quota vai para `retry_wait` com `next_eligible_at`, não morre em
`blocked`**. O mecanismo já existe no `QueueStore`; não é preciso outra máquina de estados.

O tamanho e a diversidade do painel só voltam à mesa quando houver dado mostrando que
dois revisores calibrados mais uma guarda independente rendem tanto quanto três
revisores. Hoje não há.

### Onde a regra determinística deixa de bastar

"Depende de grandeza não medida" — a hipótese do relatório — **não** é o critério. É bom
detector de falta de instrumentação: se a decisão depende de grandeza não medida, a
primeira resposta é medi-la, e depois disso a regra pode continuar trivial
(`if capacity_remaining < quorum_cost: defer()`).

O limiar para controle adaptativo é a conjunção de: estado que varia continuamente;
grandezas em conflito; melhor ação dependente do histórico e não só do estado
instantâneo; ação que altera o estado observado depois; feedback recorrente que permita
calibrar; e regras fixas exigindo retuning frequente, exceções proliferando ou oscilação
mensurável. Capacidade já se aproxima disso.

Correção conceitual que a decisão adota: **morfogênese não é o oposto de regra
determinística.** A morfogênese biológica também emerge de regras locais simples; o
distintivo é que elas, sobre estado local e realimentação, produzem organização global
não desenhada posição por posição. Os quatro commits de 2026-08-14 são, nessa leitura,
leis locais primitivas:

```
d32ea67 → não migre para recurso metabolicamente morto
30eedfc → morte exige sinal legítimo
1328e36 → dano de envelope é reparável
ddf465e → proliferação exige função
```

O erro seria tomar essa analogia retrospectiva como licença para construir um motor
genérico antes de haver sinal.

### O Atlas: o mapa permanece, o clima muda (M5)

A afirmação de que `(x,y,z)` deve virar consequência é retirada. Ela colide com a memória
espacial, propriedade que este projeto mediu e preservou deliberadamente — a auditoria de
2026-08-05 pôs a separação do espaço operacional antes da estética porque os nós de
quórum empurravam cada MOC de 87 para 148 unidades.

A separação aceita:

```
displayPose(t) = anchorPose + morphOffset(t)
```

E só o que for **tecido** recebe `morphOffset`:

| âncora (cartografia estável) | tecido (livre para reorganizar) |
|---|---|
| MOCs, nós principais do corpus, referências de navegação | painéis de quórum, tarefas, workers, atividade de endpoint, conflitos, fluxos de votação, relações operacionais transitórias |

Para atividade interdomínio, mover **a morfologia das relações** — espessura, densidade,
direção, agrupamento, halo, fluxo — antes de mover nós. Segunda vista só se a sobreposição
demonstrar empiricamente conflito cognitivo, com LOD e filtros já aplicados.

## Restrição que atravessa todos os incrementos

**Nenhum score aprendido ou adaptativo tem autoridade para remover guarda
determinística.** O sistema adaptativo escolhe onde, quando e com quem trabalhar; as
guardas determinísticas continuam dizendo o que não pode ser promovido.

## Consequências

- Graph Engineering não é substituído: é o esqueleto e parte do sistema nervoso. A frente
  morfogênica começa como **metabolismo**.
- As 296 tentativas deixam de ser só fracasso de fila e passam a ser 296 observações —
  hoje desperdiçadas. A primeira conquista morfogênica é o sistema lembrar
  operacionalmente do que acabou de acontecer e mudar sua pressão de trabalho por causa
  disso.
- Diferenciação, poda, bifurcação e topologia emergente ficam explicitamente adiadas até
  M3 existir.

## O que esta decisão não decide

Não fixa esquema de tabela, formato de arquivo nem API para o ledger de M0; não decide
janela temporal das médias; não decide se a calibração de L3 virá de resolução de fontes,
de contradição posterior ou de amostragem humana. Cada incremento decide o seu, na
implementação, conforme o regime de execução deste repositório.
