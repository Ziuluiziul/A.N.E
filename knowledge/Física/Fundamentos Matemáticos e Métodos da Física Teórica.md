---
title: Fundamentos Matemáticos e Métodos da Física Teórica
aliases: [Métodos Matemáticos da Física, Fundamentos Matemáticos]
domain: física
kind: nota
status: active
epistemic_status: established
updated: 2026-07-16
verified_at: 2026-07-16
---

# Fundamentos matemáticos e métodos da física teórica

## Função desta nota

Esta nota é a camada transversal entre cálculo/álgebra elementares e as teorias do Vault. Ela não substitui cursos completos; fixa estruturas, hipóteses e erros de categoria que precisam ser reconhecidos antes de usar mecânica quântica, campos, gravitação, termodinâmica, cordas ou cosmologia.

## 1. Espaços lineares, produtos internos e operadores

Um espaço vetorial complexo `V` fornece soma e multiplicação escalar. Um produto interno `⟨u,v⟩` introduz norma e ortogonalidade. Em dimensão infinita, completar o espaço na norma produz um espaço de Hilbert. Resultados sobre matrizes finitas não migram automaticamente para operadores ilimitados: domínio, densidade do domínio, fechamento, adjunto e extensão autoadjunta importam.

Pontos mínimos:

- autovetores de operador autoadjunto associados a autovalores distintos são ortogonais;
- o teorema espectral substitui “diagonalização” em Hilbert, possivelmente por uma medida espectral contínua;
- hermiticidade formal de uma expressão diferencial não basta para autoadjunticidade;
- comutadores codificam simultaneamente álgebra de simetrias e limites de mensuração, mas só dentro de domínios compatíveis.

Aplicações: [[Fundamentos de Mecânica Quântica e Sistemas Abertos]] <!-- relation:extends --> e [[Fundamentos de Teoria Quântica de Campos e Teorias Efetivas]] <!-- relation:extends -->.

## 2. Análise, distribuições e equações diferenciais

EDOs definem fluxos locais sob condições de existência e unicidade. EDPs exigem classificar o operador, dados iniciais/de contorno e noção de solução. Para um operador linear `L`, uma função de Green satisfaz, em sentido distribucional,

`L G(x,x') = δ(x-x')`.

A solução depende da condição de contorno: Green retardada, avançada, euclidiana e de Feynman não são o mesmo objeto. Distribuições tornam rigorosas derivadas de funções não suaves e fontes puntiformes; não são funções ordinárias avaliáveis ponto a ponto.

Transformadas de Fourier convertem derivadas em multiplicação no espaço de momento e expõem espectro/propagação. Convergência pontual, em norma e distribucional são noções distintas. Regularização controla expressões intermediárias; renormalização define como parâmetros dependem de escala e prescrição física.

## 3. Variedades, tensores e formas diferenciais

Uma variedade suave é localmente modelada por `R^n`, com mapas de transição suaves. Um tensor é um objeto multilinear geométrico; seus componentes dependem da base. Uma métrica pseudo-riemanniana define intervalos, conexão de Levi-Civita e curvatura, mas uma conexão geral pode ter torsão e/ou não metricidade.

Formas diferenciais organizam integração e topologia:

- `d²=0` implica que toda forma exata é fechada;
- o inverso é localmente verdadeiro pelo lema de Poincaré, mas globalmente obstruído pela cohomologia;
- Stokes unifica teoremas do gradiente, Green, Gauss e Stokes clássico;
- fibrados separam o espaço-base dos graus internos; conexões de fibrado descrevem transporte paralelo e campos gauge.

Aplicações: [[Fundamentos de Gravitação e Cosmologia]] <!-- relation:extends -->, [[Gravidade com Torsão e Cosmologias de Bounce]] <!-- relation:extends --> e [[Cordas, Dimensões Extras e Holografia]] <!-- relation:extends -->.

## 4. Grupos de Lie, álgebras e representações

Simetrias contínuas formam grupos de Lie; a expansão infinitesimal define uma álgebra de Lie com

`[T_a,T_b]=i f_{ab}^{\ \ c}T_c`.

Representações dizem como estados e campos transformam. Representação do grupo, da álgebra, projetiva e do grupo de recobrimento não devem ser confundidas. Para rotações, `SU(2)` recobre `SO(3)` e permite spin semi-inteiro. Em teorias gauge, a álgebra fixa acoplamentos cinemáticos, mas conteúdo de matéria, dinâmica, anomalias e quebra de simetria exigem dados adicionais.

## 5. Probabilidade, medida e processos estocásticos

Uma probabilidade é uma medida normalizada. Variáveis aleatórias são funções mensuráveis; densidade não é probabilidade pontual. Esperança, variância e correlação não determinam uma distribuição arbitrária. Independência implica correlação nula quando os momentos existem; o inverso é falso em geral.

Elementos essenciais:

- Bayes atualiza probabilidades condicionais sob um modelo e prior declarados;
- leis dos grandes números e teoremas centrais do limite têm hipóteses específicas;
- cadeias de Markov, processos de Wiener e equações de Langevin/Fokker–Planck modelam ruído em regimes definidos;
- ergodicidade é propriedade dinâmica adicional, não consequência automática de “tempo longo”.

Aplicações: [[Fundamentos de Termodinâmica e Mecânica Estatística]] <!-- relation:extends --> e [[Termodinâmica Fora do Equilíbrio]] <!-- relation:extends -->.

## 6. Topologia, homologia e geometria complexa

Topologia registra propriedades invariantes por deformações contínuas; homotopia classifica mapas, enquanto homologia/cohomologia detectam ciclos e obstruções algébricas. Em teorias gauge e defeitos topológicos, grupos de homotopia classificam setores sob hipóteses de contorno. Índices topológicos são robustos a deformações que não atravessam singularidades ou fechamentos de gap.

Variedades complexas exigem mapas de transição holomorfos. Estruturas complexa, simplética e Kähler são relacionadas, mas não equivalentes em geral. Em Calabi–Yau compacta Kähler, a anulação adequada da primeira classe de Chern permite aplicar o teorema de Yau; isso não seleciona um vácuo físico.

## 7. Métodos variacionais, perturbação e aproximações

Uma expansão perturbativa requer parâmetro pequeno e regime de controle. Série assintótica pode produzir ótima aproximação em ordem finita sem convergir. Aproximações adiabática, semiclassica, mean-field, saddle-point e effective-field-theory descartam graus de liberdade de modos distintos e possuem erros diferentes.

Para qualquer aproximação registrar:

1. quantidade adimensional de controle;
2. escala de corte e domínio;
3. ordem truncada;
4. estimativa de erro;
5. observáveis preservados;
6. singularidades, secularidade ou transições onde o método falha.

## 8. Computação científica e inferência numérica

Resultado numérico não é sinônimo de solução física. Verificar:

- consistência, estabilidade e convergência do esquema;
- independência de malha, timestep, cutoff e seed;
- conservação de invariantes esperados;
- condicionamento e propagação de erro;
- comparação com limites analíticos e benchmarks;
- distinção entre erro de discretização, incerteza paramétrica e inadequação do modelo.

Aritmética de ponto flutuante não é associativa. Ajuste visual não substitui likelihood, posterior ou teste predefinido; múltiplas comparações e tuning no conjunto de teste invalidam interpretação ingênua de significância.

## Estado epistêmico

| ID | Afirmação | Status | Escopo/evidência |
|---|---|---|---|
| `CLM-FIS-MATH-001` | Hermiticidade formal garante autoadjunticidade de qualquer operador diferencial. | `refuted` | Domínio e condições de contorno são parte do operador; ver `HALL-LIE-2015` para estrutura e literatura funcional especializada. |
| `CLM-FIS-MATH-002` | `d²=0` e Stokes organizam leis integrais e identidades locais de formas diferenciais. | `established` | Resultado matemático em variedades suaves; `NAKAHARA-2003`, capítulos 5–7. |
| `CLM-FIS-MATH-003` | Uma conexão geométrica precisa ser sempre a conexão de Levi-Civita. | `refuted` | Levi-Civita é a conexão única apenas sob torsão nula e compatibilidade métrica. |
| `CLM-FIS-MATH-004` | Aproximação perturbativa exige parâmetro/regime de controle e erro rastreável. | `established` | Regra metodológica; validade é local ao problema e à ordem. |
| `CLM-FIS-MATH-005` | Correlação nula implica independência para distribuições arbitrárias. | `refuted` | Vale sob famílias especiais, como Gaussianas conjuntas; falso em geral. |
| `CLM-FIS-MATH-006` | Convergência numérica do algoritmo prova adequação empírica do modelo. | `refuted` | Verificação numérica e validação física são problemas distintos. |

## Relações

- [[MOC — Física Teórica]] <!-- relation:navigation -->
- [[Política Epistêmica e de Linkagem]] <!-- relation:operational -->

## Referências

- Mikio Nakahara, “Geometry, Topology and Physics”, 2ª ed., CRC Press (2003), ISBN `978-0750306065`.
- Lawrence C. Evans, “Partial Differential Equations”, 2ª ed., American Mathematical Society (2010), ISBN `978-0821849743`.
- Brian C. Hall, “Lie Groups, Lie Algebras, and Representations”, 2ª ed., Springer (2015), ISBN `978-3319134666`.
