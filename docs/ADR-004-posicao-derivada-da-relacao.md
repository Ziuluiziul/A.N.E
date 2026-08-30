# ADR-004 — Posição derivada da relação, não da pasta

**Data:** 2026-08-15 · **Estado:** aberta — decisão do mantenedor
**HEAD na abertura:** `10fb3bd`
**Antecedentes:** [ADR-002](ADR-002-painel-como-no.md) (painel como nó),
[ADR-003](ADR-003-instrumentacao-antes-de-morfogenese.md) (`displayPose = anchorPose +
morphOffset`), auditoria de [2026-08-14](audits/2026-08-14-ane-completa/AUDITORIA.md).

## A questão

O mantenedor observou que a cena tem espaço demais e ligações longas demais, e propôs
que **todos os painéis fossem livres** em vez de fixos. Esta ADR existe porque a proposta
colide com uma invariante decidida por evidência, e a colisão merece ser decidida, não
contornada.

## O que foi medido antes de qualquer mudança

Sobre o corpus real — 84 notas, 607 arestas:

| | arestas | mediana | p90 | máx |
|---|---:|---:|---:|---:|
| dentro do domínio | 328 | 56 | 83 | 117 |
| **entre** domínios | 279 | **158** | 253 | 334 |

Ocupação do mundo: **9,4%**. Ocupação interna dos territórios: física 15,6%, matemática
15,4%, **computação 6,4%**.

Quase metade das ligações cruzava domínio, e essas eram 2,8× mais longas.

## O que já foi feito, e o que sobrou

Duas causas eram reparáveis sem tocar em invariante nenhuma, e foram (`b8f113e`, `782c6af`):

1. **A ordem dos domínios no anel era `localeCompare` do id.** Alfabética. Dois domínios
   muito ligados caíam em azimutes opostos por causa da inicial. Agora a ordem sai da
   afinidade medida entre eles: travessia mediana 158 → 129, máxima 334 → 294.
2. **A folga da âncora era somada a toda camada da espiral**, não só à primeira, o que
   transladava o território inteiro para fora e abria um buraco no miolo. Somada em
   quadratura: aresta interna mediana 58 → 42, p90 101 → 64, física de raio 59 e 15,6%
   para raio 33 e **49,1%** de ocupação, zero colisão entre placas.

**O que sobrou é a pergunta desta ADR.** Mesmo com as duas correções, as 279 travessias
continuam com mediana 129 — três vezes as internas —, e a ocupação global segue perto de
10%, porque o que a governa é o anel, e o anel existe para dar território a cada domínio.

## A tensão, dos dois lados

**A favor de derivar a posição da relação.** A Política Epistêmica é explícita: a pasta é
só localização, e wikilinks resolvem por nome. O que estrutura o corpus é a relação
declarada. Hoje a posição de uma nota é decidida pelo **diretório** em que ela está — que
a própria Política diz não ser estrutura. Uma nota de Física que só se liga a Matemática
fica em Física, longe de tudo que a justifica, e a distância que se vê na tela não
corresponde a distância nenhuma do conhecimento.

**Contra soltar os painéis.** A esfera livre já existiu e saiu, com motivo registrado no
cabeçalho de `layout.ts`: oclusão sem remédio, nenhum ponto de referência para reencontrar
uma nota, e o mapa inteiro se reorganizando quando uma única nota mudava. Depois disso,
`b0c52c7` teve de **devolver** a memória espacial ao corpus, e a auditoria de 2026-08-05
pôs isso acima da estética porque nós de quórum empurravam cada MOC de 87 para 148
unidades. A ADR-003, de ontem, fixou âncora estável e só tecido móvel.

## A síntese proposta

As duas coisas só são incompatíveis se "livre" significar **recalculado a cada abertura**.
Não é o que a redução de arestas exige.

```
anchorPose := f(relações declaradas)     — derivada uma vez, não da pasta
             persistida                  — a memória vem de gravar, não de prender ao anel
displayPose(t) = anchorPose + morphOffset(t)   — contrato da ADR-003, intacto
```

Uma nota se assenta onde suas relações a puxam, o resultado é congelado no
`layoutStore`, e a partir daí ela não se move mais — nem quando o quórum cresce, nem
quando o corpus ganha vizinhas. A estabilidade deixa de vir do anel e passa a vir da
persistência, que é onde ela já mora hoje: as 84 posições voltam idênticas depois de
recarregar, e é isso que a torna memória.

O território não desaparece: ele deixa de ser um recorte de pasta e passa a ser o que a
seriação por afinidade já mostra — domínios muito ligados **são** vizinhos, agora por
medição e não por inicial.

## O que precisa ser decidido

1. **A pasta continua decidindo a posição?** Se sim, esta ADR se fecha como recusada e o
   espaço vazio é preço aceito. Se não, `placeAnchors` e `clusterize` são reescritos.
2. **O que ancora o mapa mental**, uma vez que a posição não venha mais do diretório? A
   candidata natural é o próprio MOC, que continua sendo o nó mais ligado do seu grupo —
   mas isso é hipótese, não medição.
3. **O que acontece com a nota que se liga a dois domínios em igual medida?** Hoje a pasta
   desempata. Sem ela, é preciso um critério — e a Política já recusa desempate arbitrário
   em outro lugar (o backend se recusa a escolher âncora a esmo).
4. **Migração.** Toda posição gravada seria invalidada uma vez, na virada. É o mesmo custo
   de uma subida de `LAYOUT_ALGORITHM_VERSION`, e já aconteceu três vezes esta semana.

## Recomendação

Abrir como incremento próprio, **depois** de M3 — a calibração precisa de desfecho, e
mexer no layout não a aproxima. As duas correções já entregues capturaram o que era
reparável sem decisão de princípio; o resto exige que o mantenedor diga se a pasta
governa a posição ou não.

Enquanto isso não se decide, nada aqui bloqueia: o Atlas está mais denso e as travessias
mais curtas do que estavam ontem, e a memória espacial continua verificada em 84 de 84
posições.
