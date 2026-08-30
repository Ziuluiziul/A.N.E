# ADR-006 — O A.N.E. editando o próprio código

**Data:** 2026-08-15 · **Estado:** aceita em direção, condicionada em execução
**HEAD na decisão:** `8a88c8b`
**Decidida por:** mantenedor.
**Relacionadas:** [ADR-003](ADR-003-instrumentacao-antes-de-morfogenese.md) (instrumentação
antes de emergência), [ADR-005](ADR-005-propriedade-do-estado-operacional.md) (uma
autoridade por estado), auditoria de [2026-08-14](audits/2026-08-14-ane-completa/AUDITORIA.md).

## A decisão

O sistema passa a poder propor alteração no **próprio código**, pelo mesmo quórum
multimodelo que hoje governa o corpus, e sem builder humano no ciclo.

## A inversão que torna isso viável

A intuição diz que editar código é mais perigoso que editar prosa. A evidência desta
casa diz o contrário, e vale enunciar:

| | corpus (`knowledge/`) | código |
|---|---|---|
| sinal de correção | julgamento epistêmico | `make audit && make test && make lint` |
| quem decide | quórum de modelos | máquina |
| falso positivo | passa e fica | não compila, ou o teste reprova |
| raio de dano | uma nota | contido pelo commit, reversível por `git` |

O quórum foi medido nesta casa: **296 tentativas produziram uma decisão**, e essa decisão
aprovou, por 2 votos de 3 do mesmo provedor, um patch que substituiria uma nota de 73
linhas por um stub de dez. Ele não está pronto para julgar verdade.

Mas ele não precisa julgar verdade para editar código. Precisa produzir uma alteração que
**passe nos três gates** — e os gates são determinísticos, já existem, e já rodam a cada
commit desta casa há semanas. O sinal de correção que falta ao corpus sobra ao código.

Por isso a ordem natural se inverte: o sistema pode se tornar capaz de editar o próprio
código **antes** de ser capaz de editar o próprio corpus com segurança.

## A invariante que não se negocia

> **O sistema não pode alterar aquilo que o julga.**

É a mesma regra que a ADR-003 fixou um nível abaixo — nenhum score aprendido remove guarda
determinística —, elevada ao caso em que o autor da mudança é o próprio sistema. Um patch
que enfraquece o gate e depois passa no gate enfraquecido não foi verificado por nada.

Ficam **fora** do alcance de qualquer patch gerado pelo próprio sistema:

```
tools/audit.py                     o gate estrutural do corpus
backend/src/vault/promotion/       a guarda que decide o que entra
backend/src/vault/quorum/engine.py a regra de decisão do painel
tests/                             o que prova que o resto funciona
Makefile                           a definição dos próprios gates
.github/, CI                       se existir
docs/ADR-*.md                      as decisões que o governam
~/.config/…/secrets.env            fora do repositório, e já inalcançável
```

A lista é de negação explícita, não de permissão implícita: o alcance começa fechado, e
cada abertura é uma decisão registrada.

## O que muda no mecanismo

`CorpusPatch` recusa hoje qualquer alvo que não termine em `.md`
([patch.py:56](../backend/src/vault/promotion/patch.py)). Um patch de código é **outro
tipo**, e não uma flexibilização deste — misturar os dois faria a guarda de redução do
corpus, que conta claims e wikilinks, opinar sobre Python.

O que o patch de código exige, e que o de corpus não tem:

1. **Gate mecânico como condição de promoção.** `audit`, `test` e `lint` rodam na
   worktree temporária, exatamente como a auditoria do corpus já roda, e reprovar é
   recusar. Sem exceção e sem `--force`.
2. **Escopo declarado por arquivo**, como `corpus_patch_allowed_targets` já faz.
3. **Diff limitado.** Um patch que toca trinta arquivos não é uma alteração, é uma
   reescrita, e ninguém — humano ou modelo — a revisa de verdade.
4. **Nada de `git push`.** Continua sendo confirmação humana obrigatória, como o regime
   deste repositório já determina. O sistema commita local; publicar é do mantenedor.
5. **Reversibilidade provada antes do mérito.** O commit é atômico e o `HEAD` anterior
   fica registrado no evento de promoção, para desfazer ser um comando e não uma
   arqueologia.

## O que precisa ser verdade antes

Nada disto é opinião: são medições desta casa, e cada uma tem um número hoje.

| condição | estado em 2026-08-15 |
|---|---|
| o quórum fecha painel | **65% escalonam** (103 de 159 decididos) |
| há custo por fechamento medido | sim — 9,6 chamadas (M0) |
| a admissão evita gasto inútil | sim — M1/M2 entregues |
| existe desfecho para calibrar revisor | **não** — zero promoções |
| a guarda recusa patch destrutivo | sim — provado contra o stub |
| há capacidade de provedor sustentada | **não** — free tier, 27 de 44 falhas por cota |

As duas linhas em negrito são as que faltam. A primeira é epistêmica e a segunda é
econômica, e **nenhuma das duas bloqueia o caso do código** — porque o gate mecânico
substitui o julgamento que falta, e porque um patch de código que reprova nos testes custa
uma execução, não uma nota corrompida.

## Sequência

1. `CodePatch` como tipo próprio, com escopo declarado e a lista de negação acima.
2. O promotor ganha o caminho de código: aplica na worktree, roda os três gates, e recusa
   sem eles. O caminho do corpus não muda.
3. Uma primeira tarefa autônoma de código deliberadamente pequena e verificável — o tipo
   de coisa que a auditoria já enumerou: `atlas.sh:63` quebrando no encerramento, o
   endpoint que nunca funcionou e segue elegível, o rótulo de nuvem que se sobrepõe.
4. Só então tarefas geradas pelo próprio sistema a partir da telemetria dele.

## O que esta ADR não decide

Não decide que o sistema deva editar código **em vez** de corpus — o corpus continua sendo
o produto, e ele segue congelado desde 2026-08-04. Não decide que a autonomia se estenda a
`git push`, a segredo ou a configuração de máquina. E não decide que o quórum atual seja
suficiente: ele é o mecanismo disponível, com 65% de escalonamento medido, e melhorá-lo
continua sendo trabalho aberto.

A aposta desta ADR é estreita e verificável: **onde a correção é mecânica, a autonomia é
segura antes de o julgamento amadurecer.**
