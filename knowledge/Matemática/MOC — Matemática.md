---
title: MOC — Matemática
domain: matemática
kind: moc
status: active
epistemic_status: mixed
updated: 2026-07-18
verified_at: 2026-07-18
---

# Matemática

**Objeto central:** a árvore formal comum a Física, IA e Computação — estruturas, provas e cálculo, organizadas por dependência real.

## Árvore de pré-requisitos

### Raiz

1. [[Lógica, Provas e Argumentação]] <!-- relation:navigation --> — sem ela, nada abaixo se lê com rigor.
2. [[Teoria dos Conjuntos e Fundamentos]] <!-- relation:navigation --> — sobre que base os objetos existem, e o que se paga pelo axioma da escolha.

### Estrutura e cálculo

2. [[Álgebra Linear]] <!-- relation:navigation --> — espaços vetoriais e operadores; pré-requisito de MQ e de ML.
3. [[Cálculo Multivariável e Vetorial]] <!-- relation:navigation --> — variação e acúmulo em `R^n`.
4. [[Análise Real]] <!-- relation:navigation --> — o que autoriza a passagem ao limite; rigor por trás do cálculo.
5. [[Teoria da Medida e Integração]] <!-- relation:navigation --> — medida, integral de Lebesgue e os teoremas de convergência que Riemann não dá.
5b. [[Análise Funcional]] <!-- relation:navigation --> — o que sobrevive da álgebra linear em dimensão infinita; onde mora o teorema espectral da mecânica quântica.

6. [[Análise Complexa]] <!-- relation:navigation --> — por que uma derivada complexa implica infinitas; resíduos e continuação.

### Espaço e forma

7. [[Topologia]] <!-- relation:navigation --> — proximidade sem distância; compacidade, conexidade, continuidade.
8. [[Variedades Diferenciáveis e Geometria]] <!-- relation:navigation --> — cálculo em espaços localmente euclidianos; o formalismo da relatividade.

### Estrutura e simetria

9. [[Álgebra Abstrata e Teoria de Grupos]] <!-- relation:navigation --> — o que é uma simetria, formalmente; grupos, anéis, corpos.
10. [[Combinatória e Teoria dos Grafos]] <!-- relation:navigation --> — contagem e relações discretas; existência sem construção.

### Aplicação

11. [[Equações Diferenciais]] <!-- relation:navigation --> — quando uma lei em forma de taxa determina uma trajetória.
11b. [[Cálculo Variacional]] <!-- relation:navigation --> — otimização sobre funções; onde Noether é demonstrado.
12. [[Otimização]] <!-- relation:navigation --> — quando minimizar tem garantia e quando é heurística.
13. [[Probabilidade]] <!-- relation:navigation --> — formalmente matemática; curada no MOC de Estatística (aresta cruzada declarada, sem duplicação).
14. [[Fundamentos Matemáticos e Métodos da Física Teórica]] <!-- relation:extends --> — a instância física do aparato.

## Escopo negativo (critérios de exclusão)

- Resultados físicos (vivem em Física; aqui só o aparato).
- Métodos numéricos e estabilidade de ponto flutuante (domínio de Computação).
- Fundamentos filosóficos da matemática (não-empírico; fora do corpus ativo).

## Lacunas priorizadas (não criar sem função)

Teoria de representações e grupos de Lie; sistemas dinâmicos e caos; processos
estocásticos; teoria dos números; análise numérica; teoria das categorias. Cada uma entra quando uma nota consumidora a exigir —
vale a regra de crescimento do [[Índice]] <!-- relation:navigation -->.

## Fonte curricular

Núcleo comum de graduações em matemática. Bibliografia canônica declarada por nota,
com identificador verificado: Axler e Strang (álgebra linear); Rudin e Abbott (análise);
Folland (medida); Munkres (topologia); Lee e Nakahara (variedades);
Stein–Shakarchi (análise complexa); Dummit–Foote (álgebra); Evans (EDPs);
Diestel (grafos); Boyd–Vandenberghe e Nocedal–Wright (otimização).

## Teste de navegação (casos reais)

- "Por que operadores autoadjuntos têm espectro real?" → Álgebra Linear → teorema espectral → uso em MQ via relação `extends`.
- "Multiplicadores de Lagrange valem sempre?" → Cálculo Multivariável → limites (condição necessária, regularidade).

## Manutenção

Revisão semestral do MOC (cobertura vs consumidores); notas de teoria são estáveis com `review_after` anual.

Voltar ao [[Índice]] <!-- relation:navigation -->.
