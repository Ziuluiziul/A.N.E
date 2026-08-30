---
title: Viés Espectral e Redes Informadas por Física
aliases: [F-Principle, Spectral Bias, PINNs e viés espectral, DCGD]
domain: ia
kind: nota
status: active
epistemic_status: mixed
updated: 2026-07-27
verified_at: 2026-07-27
---

# Viés espectral e redes informadas por física

## Função desta nota

Separar três coisas que a discussão pública costuma fundir: (i) o que redes neurais
demonstravelmente fazem com o espectro de frequências do alvo, (ii) o que métodos de
geometria de gradiente para PINNs provam, e (iii) o que nenhum dos dois resolve.
Estende [[Fundamentos de Aprendizado de Máquina e Modelos de Linguagem]] <!-- relation:extends --> no ponto
específico de otimização e capacidade de representação.

## 1. Viés espectral (F-Principle)

Redes neurais profundas tendem a ajustar componentes de **baixa frequência** do alvo
antes das de alta frequência ao longo do treino. O fenômeno foi descoberto de forma
independente e simultânea por dois grupos em 2019: Xu et al., por análise de Fourier
da dinâmica de treino, e Rahaman et al., por estimativa dos coeficientes de Fourier de
redes com ativação ReLU.

O mecanismo apontado por Xu et al. é que, com parâmetros pequenos, o gradiente da
perda em baixa frequência domina exponencialmente o de alta frequência — consequência
da suavidade da função de ativação.

## 2. PINNs: a decomposição do erro

Para `u*` resolvendo `N[u]=f` em `Ω` com `B[u]=g` em `∂Ω`, e classe de hipótese
neural `U_Θ={u_θ}`, um orçamento de erro honesto separa ao menos:

`erro total = aproximação + otimização + amostragem/discretização + estabilidade/generalização`

Os quatro termos são independentes. Nenhum método que atue sobre um deles limita os
outros. Em particular, se `inf_{θ∈Θ} ‖u_θ − u*‖ > 0`, nenhuma geometria de gradiente
remove o erro de aproximação.

## 3. O que o DCGD prova, e o que não prova

Dual Cone Gradient Descent trata o caso em que `∇L_r` e `∇L_b` têm produto interno
negativo — minimizar um termo piora o outro. O método escolhe a atualização no cone
dual de `{∇L_r, ∇L_b}`, garantindo produto interno não-negativo com ambos.

O teorema de convergência é para **ponto Pareto-estacionário** em cenário não convexo.
Isso não é convergência para a solução da PDE, e o próprio enunciado não fala sobre
conteúdo espectral do resíduo.

## 4. A lacuna espectral

Estabilidade de otimização e fidelidade espectral são propriedades distintas. Um
otimizador pode satisfazer as condições de contorno e atingir estacionariedade de
Pareto enquanto ajusta apenas uma versão passa-baixa da física — o resíduo fica pequeno
na norma amostrada e continua grande no conteúdo de alta frequência.

Uma verificação direta é a transformada de Fourier do resíduo sobre o domínio,
comparando o espectro ajustado com o esperado.

**Atenção ao status:** os itens 1–3 são resultados publicados. O item 4, como
enunciado, é **inferência** a partir deles — decorre de 002 e 003 serem sobre objetos
diferentes —, não um teorema que eu tenha localizado numa fonte primária. Tratar como
hipótese bem sustentada, não como resultado citável.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-IA-VIESESP-001` | Redes neurais profundas ajustam componentes de baixa frequência do alvo antes das de alta durante o treino (F-Principle / viés espectral). | established | Xu et al. 2019, “Frequency Principle: Fourier Analysis Sheds Light on Deep Neural Networks”, arXiv:1901.06523; e Rahaman et al. 2019 (ICML), descobertas independentes. Escopo: redes totalmente conectadas nos regimes medidos; ativação afeta o mecanismo. |
| `CLM-IA-VIESESP-002` | PINNs totalmente conectadas sofrem viés espectral e, adicionalmente, discrepância de taxa de convergência entre os termos da função de perda. | established | Wang, Yu & Perdikaris 2022, “When and why PINNs fail to train: A neural tangent kernel perspective”, arXiv:2007.14527, via análise do Neural Tangent Kernel no limite de largura infinita. Limite: o resultado é assintótico em largura. |
| `CLM-IA-VIESESP-003` | DCGD seleciona atualização no cone dual de `{∇L_r,∇L_b}`, garantindo produto interno não-negativo com ambos, e converge para ponto Pareto-estacionário em cenário não convexo. | established | Hwang & Lim 2024, “Dual Cone Gradient Descent for Training Physics-Informed Neural Networks”, arXiv:2409.18426. Limite explícito: Pareto-estacionariedade **não** é convergência para a solução da PDE. |
| `CLM-IA-VIESESP-004` | Estacionariedade de Pareto não controla o conteúdo espectral do resíduo; estabilidade de otimização e fidelidade espectral são propriedades independentes. | supported | Inferência a partir de `CLM-IA-VIESESP-002` e `CLM-IA-VIESESP-003`, que tratam de objetos distintos. Não localizei fonte primária que enuncie isto como teorema. Não citar como resultado estabelecido. |

## Limites e contraexemplos

- Viés espectral **não** é impossibilidade: é ordem de aprendizado. Redes alcançam alta
  frequência com treino suficiente, arquitetura adequada ou features de Fourier — o
  ponto é o custo, não a barreira.
- O resultado NTK de `CLM-IA-VIESESP-002` vale no limite de largura infinita sob
  parametrização NTK. Redes finitas estreitas são regime declaradamente fora do escopo.
- DCGD não é criticado por falhar no que não promete. A crítica válida é sobre o que
  se conclui dele, não sobre o teorema.
- Resíduo pequeno na norma amostrada não identifica a solução física sem PDE bem-posta
  e norma em que o resíduo controle o erro.

## Relações

- [[Fundamentos de Aprendizado de Máquina e Modelos de Linguagem]] <!-- relation:extends --> — otimização, capacidade e generalização.
- [[Álgebra Linear]] <!-- relation:prerequisite --> — análise espectral e produto interno.
- [[Fundamentos Matemáticos e Métodos da Física Teórica]] <!-- relation:prerequisite --> — análise de Fourier e PDEs bem-postas.
- [[Probabilidade]] <!-- relation:prerequisite --> — amostragem e risco.

## Fontes

- Xu, Zhang, Luo, Xiao & Ma (2019). “Frequency Principle: Fourier Analysis Sheds Light on Deep Neural Networks”. [arXiv:1901.06523](https://arxiv.org/abs/1901.06523)
- Rahaman, Baratin, Arpit, Draxler, Lin, Hamprecht, Bengio & Courville (2019). *On the Spectral Bias of Neural Networks*. ICML 2019.
- Wang, Yu & Perdikaris (2022). “When and why PINNs fail to train: A neural tangent kernel perspective”. J. Comput. Phys. 449:110768. [arXiv:2007.14527](https://arxiv.org/abs/2007.14527)
- Hwang & Lim (2024). “Dual Cone Gradient Descent for Training Physics-Informed Neural Networks”. NeurIPS 2024. [arXiv:2409.18426](https://arxiv.org/abs/2409.18426)
