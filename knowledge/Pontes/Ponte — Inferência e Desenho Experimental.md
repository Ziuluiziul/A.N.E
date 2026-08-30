---
title: Ponte — Inferência e Desenho Experimental
aliases: [Ponte Estatística-Metodologia, Inferência e Desenho Experimental]
domain: pontes
kind: moc
status: active
epistemic_status: mixed
updated: 2026-08-04
---

# Ponte — inferência e desenho experimental

**Objeto central:** a dependência mútua entre como o dado é gerado e o que a
inferência sobre ele autoriza. É a única ponte do corpus que corre nos dois sentidos,
e isso não é redundância: é o conteúdo.

Este MOC **não cria relação nova**; reúne arestas já declaradas entre as notas de
Estatística e de Metodologia, na ordem em que a dependência acontece.

## A circularidade que não é vício

O corpus declara `Desenho Experimental e Causalidade` como **pré-requisito** de
`Inferência e Incerteza`, e também declara `Inferência e Incerteza` **estendendo**
`Desenho Experimental e Causalidade`. As duas coisas ao mesmo tempo.

Não é contradição nem aresta duplicada por descuido. Sem desenho, a inferência não
sabe o que está estimando; sem inferência, o desenho não sabe quanto poder precisa
ter. Quem lê só um dos lados aprende a fazer contas que não respondem à pergunta, ou
a planejar coletas cujo resultado não se sustenta. A ponte existe para que os dois
lados sejam lidos como um ciclo, e não como uma escada.

## O ciclo, na ordem em que ele roda

1. [[Desenho Experimental e Causalidade]] <!-- relation:navigation --> — o que a coleta
   permite concluir antes de qualquer conta; identificação, confusão, aleatorização.
2. [[Probabilidade]] <!-- relation:navigation --> — o cálculo que tanto o desenho quanto
   a inferência consomem; o corpus o declara pré-requisito pelos dois lados.
3. [[Inferência e Incerteza]] <!-- relation:navigation --> — estimação, testes e
   calibração sobre o dado que o desenho produziu.
4. [[Metrologia e Validação]] <!-- relation:navigation --> — o instrumento também tem
   erro; medida sem incerteza declarada não é medida.
5. [[Reprodutibilidade e Replicação]] <!-- relation:navigation --> — o teste externo do
   ciclo inteiro, e o lugar onde a falha aparece.

## Onde a estatística entra como evidência, não como método

6. [[Estimação e Testes de Hipótese]] <!-- relation:navigation --> — o corpus o liga a
   Reprodutibilidade como `evidence`: o comportamento dos valores-p sob replicação é
   fato observado sobre o método, não escolha de arcabouço.
7. [[Aprendizado Estatístico]] <!-- relation:navigation --> — ligado a Reprodutibilidade
   pela mesma razão: generalização medida fora da amostra é o teste do que foi ajustado.
8. [[Filosofia da Ciência]] <!-- relation:navigation --> — estende Estimação e Testes:
   o que se pode afirmar de uma hipótese rejeitada é questão anterior à estatística.

## Os dois MOCs que esta ponte liga

- [[MOC — Estatística e Inferência]] <!-- relation:navigation --> — incerteza quantificada.
- [[MOC — Metodologia Científica]] <!-- relation:navigation --> — como se decide que uma
  afirmação vale.

## Escopo negativo

- **"Replicação" de sistemas distribuídos não entra.** É homonímia registrada no corpus
  justamente para impedir esta aresta; replicar um dado em três máquinas nada tem com
  replicar um experimento.
- **Estatística aplicada a um domínio** (biologia, física) pertence ao domínio, não aqui.
- **Ferramenta e software** de análise não são conteúdo desta ponte.

## Teste de navegação (casos reais)

- "O efeito sumiu na replicação — o estudo original estava errado?" → Reprodutibilidade
  → Estimação e Testes (o que a ausência autoriza concluir).
- "Preciso de quantas amostras?" → Desenho Experimental → Inferência e Incerteza.
- "A medida tem erro de instrumento ou de amostra?" → Metrologia e Validação.

## Manutenção

A entrada mais frágil é a circularidade declarada na abertura: ela depende de duas
arestas de tipos diferentes entre as mesmas notas. Se uma delas for retipada, esta
seção precisa ser reescrita ou removida — não mantida por inércia.

Voltar ao [[Índice]] <!-- relation:navigation -->.
