---
title: Biologia Molecular e Fluxo de Informação Genética
aliases: [Dogma Central, DNA, Transcrição e Tradução]
domain: ciências da vida
kind: nota
status: active
epistemic_status: established
updated: 2026-07-28
verified_at: 2026-07-28
---

# Biologia molecular e fluxo de informação genética

## Finalidade

Responder: **como uma sequência química armazena, copia e expressa instruções?** É o mecanismo que torna "informação" um conceito com referente físico em biologia — e o ponto onde é preciso mais cuidado, porque a mesma palavra é usada aqui e em [[Teoria da Informação]] <!-- relation:contrasts --> com sentidos que não coincidem.

## Escopo

Estrutura do DNA e pareamento de bases; replicação semiconservativa; transcrição e processamento de RNA; código genético e tradução; regulação da expressão gênica; mutação e reparo; estrutura da cromatina e regulação epigenética; o dogma central e suas exceções documentadas. **Escopo negativo:** técnicas de laboratório e protocolos, genômica computacional, biologia do desenvolvimento, e as afirmações sobre efeitos quânticos em biomoléculas (tratadas em Física, sob quarentena epistêmica).

## Pré-requisitos

- [[Bioenergética e Termodinâmica dos Sistemas Vivos]] <!-- relation:prerequisite --> — replicação e tradução são processos que consomem energia livre; nenhum ocorre espontaneamente.

## Conceitos nucleares

- **Estrutura em dupla hélice**: duas fitas antiparalelas com pareamento complementar `A–T` e `G–C`. A complementaridade é o que torna a cópia mecanicamente possível — foi a observação central de 1953.
- **Replicação semiconservativa**: cada fita serve de molde; a molécula-filha retém uma fita parental. Demonstrada por Meselson e Stahl.
- **Transcrição**: DNA → RNA por RNA polimerase. Em eucariotos, o transcrito primário sofre processamento (*splicing*, capeamento, poliadenilação).
- **Código genético**: trincas de nucleotídeos (códons) especificam aminoácidos. É **degenerado** (vários códons por aminoácido) e quase universal, com exceções conhecidas em mitocôndrias e alguns organismos.
- **Tradução**: ribossomo lê o mRNA e sintetiza a cadeia polipeptídica, com tRNA como adaptador.
- **Regulação**: a informação de *quando* e *quanto* expressar está em elementos regulatórios, não na sequência codificante. É o que permite que células com o mesmo genoma sejam diferentes.
- **Mutação e reparo**: erros ocorrem e são majoritariamente corrigidos; a taxa residual é o substrato da variação hereditária.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-BIO-MOL-001` | O DNA é uma dupla hélice com pareamento específico de bases, e essa complementaridade sugere diretamente um mecanismo de cópia. | established | Watson & Crick, *Nature* 171:737–738 (1953), DOI `10.1038/171737a0` — verificado na fonte em 28/07/2026. O artigo enuncia explicitamente que o pareamento postulado sugere um mecanismo de cópia; a demonstração experimental da replicação semiconservativa veio depois. |
| `CLM-BIO-MOL-002` | O código genético é degenerado e quase universal, com exceções documentadas. | established | Alberts et al., cap. 6. "Quase" é parte da afirmação: códigos alternativos existem em mitocôndrias e em alguns ciliados. Tratar a universalidade como absoluta é erro corrente. |
| `CLM-BIO-MOL-003` | O fluxo de informação sequencial de ácido nucleico para proteína não se reverte: não há mecanismo conhecido de transferência de sequência da proteína de volta para o ácido nucleico. | established | Alberts et al., cap. 6. **Escopo crítico:** o "dogma central" é frequentemente enunciado como "DNA → RNA → proteína", e nessa forma **é falso** — transcrição reversa (RNA → DNA) existe e é bem caracterizada. A formulação correta, devida a Crick, é sobre a irreversibilidade a partir da proteína, não sobre a ordem das setas. |
| `CLM-BIO-MOL-004` | Modificações epigenéticas regulam a expressão gênica e podem ser herdadas por divisões celulares. | established | Alberts et al., cap. 4 e 7. **Limite de escopo:** herança epigenética *transgeracional* em mamíferos — através da linhagem germinativa, por múltiplas gerações — é questão distinta e muito menos estabelecida. Este claim cobre apenas a herança mitótica. |

## Limites e contraexemplos

- **"Gene para X" é quase sempre formulação incorreta**: a maioria dos traços é poligênica e dependente de ambiente. A afirmação exige, no mínimo, tamanho de efeito e população de referência — é o mesmo requisito de escopo que a política do Vault impõe a qualquer claim.
- **Correlação genótipo–fenótipo não é mecanismo**: estudos de associação identificam regiões, não vias causais. A ponte para causalidade exige o aparato de [[Desenho Experimental e Causalidade]] <!-- relation:prerequisite -->.
- **Sequência não determina estrutura de forma resolvida**: predição de enovelamento avançou muito, mas prever estrutura não é prever função, e nenhum dos dois é prever comportamento celular.
- **"Informação genética" não é informação de Shannon**: a analogia é sugestiva e não é identidade. Nenhum resultado de teoria da informação transfere para genética sem fonte que trate explicitamente dos dois domínios.

## Relações

- [[Bioenergética e Termodinâmica dos Sistemas Vivos]] <!-- relation:prerequisite -->
- [[Evolução e Seleção Natural]] <!-- relation:extends --> — mutação e recombinação são a origem da variação sobre a qual a seleção age.
- [[Desenho Experimental e Causalidade]] <!-- relation:prerequisite --> — atribuir causa a variantes genéticas exige identificação.
- [[Teoria da Informação]] <!-- relation:contrasts --> — homonímia de "informação"; nenhuma transferência de resultados sem fonte que trate ambos.
- [[MOC — Ciências da Vida]] <!-- relation:navigation -->

## Fontes

- Bruce Alberts, Rebecca Heald, Alexander Johnson, David Morgan, Martin Raff et al. *Molecular Biology of the Cell*. 7ª ed., W. W. Norton & Company, 2022. ISBN 978-0-393-88482-1.
- J. D. Watson e F. H. C. Crick. "Molecular Structure of Nucleic Acids: A Structure for Deoxyribose Nucleic Acid". *Nature* 171, 737–738 (1953). DOI `10.1038/171737a0`.

## Condição de revisão

Revisar `CLM-BIO-MOL-004` se o Vault ganhar nota dedicada a epigenética, que trataria a herança transgeracional com fonte primária própria — hoje deliberadamente fora de escopo.
