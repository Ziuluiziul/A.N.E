---
title: Features de Fourier e Mitigação do Viés Espectral
aliases: [Fourier features, NTK estacionário, mitigação de spectral bias]
domain: ia
kind: nota
status: active
epistemic_status: mixed
updated: 2026-07-27
verified_at: 2026-07-27
---

# Features de Fourier e mitigação do viés espectral

## Função desta nota

[[Viés Espectral e Redes Informadas por Física]] <!-- relation:extends --> estabelece
que redes ajustam baixa frequência antes de alta. Esta nota trata do outro lado:
o que se sabe sobre **contornar** esse viés, e o que ainda não se sabe.

A distinção importa porque viés espectral costuma ser lido como impossibilidade.
Não é: é ordem de aprendizado com custo associado, e existe intervenção com
mecanismo identificado.

## 1. O mecanismo

Tancik et al. mostram que passar as entradas por um mapeamento de features de
Fourier antes do MLP permite aprender funções de alta frequência em domínios de
baixa dimensão. A explicação é via NTK: o kernel tangente neural de um MLP
padrão decai rapidamente com a frequência, e o mapeamento **transforma o NTK
efetivo num kernel estacionário de largura de banda ajustável**.

O ganho não vem de mais capacidade nem de mais treino. Vem de mudar a geometria
do kernel — o que a rede considera "próximo" no espaço de entrada.

## 2. O que isso não resolve

A largura de banda é um hiperparâmetro. Escolhê-la exige saber, antes, qual
faixa de frequência importa no problema — informação que em PDEs nem sempre está
disponível a priori. Banda estreita demais reintroduz o viés; larga demais
degrada a generalização.

E o resultado é sobre **domínios de baixa dimensão**, com regressão de sinais e
representação de cenas 3D como aplicações demonstradas. Transportá-lo para o
resíduo de uma PDE é plausível e não é o que a fonte demonstra.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-IA-FOURIER-001` | Um mapeamento de features de Fourier na entrada permite que um MLP aprenda funções de alta frequência em domínios de baixa dimensão. | established | Tancik, Srinivasan, Mildenhall et al. 2020, “Fourier Features Let Networks Learn High Frequency Functions in Low Dimensional Domains”, arXiv:2006.10739. Escopo: baixa dimensão, tarefas de regressão e representação de cena. |
| `CLM-IA-FOURIER-002` | O mecanismo é a conversão do NTK efetivo em kernel estacionário de largura de banda ajustável, não aumento de capacidade. | established | Mesma fonte, “Fourier Features Let Networks Learn High Frequency Functions in Low Dimensional Domains”, arXiv:2006.10739, na análise por NTK. |
| `CLM-IA-FOURIER-003` | A escolha da largura de banda exige conhecimento prévio da faixa de frequência relevante; erro para menos reintroduz o viés e para mais degrada generalização. | supported | Decorre de a banda ser hiperparâmetro no enunciado da fonte. Não localizei regra de seleção automática validada para PDEs. |
| `CLM-IA-FOURIER-004` | Aplicar features de Fourier ao resíduo de PINNs mitiga a lacuna espectral descrita em `CLM-IA-VIESESP-004`. | hypothesis | Inferência por analogia de mecanismo, não demonstração. A fonte é sobre domínios de baixa dimensão em visão e gráficos; PINNs têm perda composta e amostragem por colocação. Tratar como hipótese a testar, nunca como resultado. |

## Limites e contraexemplos

- Nada aqui contradiz o F-Principle: features de Fourier não eliminam o viés,
  deslocam a banda em que ele opera.
- Ganho demonstrado em regressão de baixa dimensão não transfere automaticamente
  para operadores diferenciais de ordem alta.
- Banda ajustável é liberdade e é risco: introduz um hiperparâmetro cuja escolha
  errada é indistinguível, no treino, de falha de capacidade.

## Discriminante

O que decidiria `CLM-IA-FOURIER-004`: treinar a mesma PDE com e sem mapeamento
de Fourier, mantendo tudo o mais fixo, e comparar a densidade espectral de
potência do resíduo **ao longo das épocas** — o diagnóstico proposto na thread
com `vina`, que isola dinâmica de otimização da limitação de amostragem porque o
conjunto de colocação permanece constante durante o treino.

## Relações

- [[Viés Espectral e Redes Informadas por Física]] <!-- relation:extends --> — o fenômeno que esta nota tenta contornar.
- [[Fundamentos de Aprendizado de Máquina e Modelos de Linguagem]] <!-- relation:prerequisite --> — capacidade, otimização e generalização.
- [[Álgebra Linear]] <!-- relation:prerequisite --> — kernels, espectro e produto interno.

## Fontes

- Tancik, Srinivasan, Mildenhall, Fridovich-Keil, Raghavan, Singhal, Ramamoorthi, Barron & Ng (2020). “Fourier Features Let Networks Learn High Frequency Functions in Low Dimensional Domains”. arXiv:2006.10739

## Condição de revisão

Revisar quando houver fonte primária que aplique features de Fourier ao resíduo
de PINNs com medição espectral, o que moveria `CLM-IA-FOURIER-004` de
`hypothesis` para `established` ou `refuted`.
