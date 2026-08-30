---
title: Topologia
aliases: [Topologia Geral, Espaços Topológicos]
domain: matemática
kind: nota
status: active
epistemic_status: established
updated: 2026-07-28
verified_at: 2026-07-28
---

# Topologia

## Finalidade

Responder: **o que sobra de "proximidade" quando se remove a distância?** Continuidade, convergência, conexidade e compacidade são definíveis sem métrica; isolar o que depende só de abertos é o que permite falar de espaços de configuração, variedades e espaços de funções sem impor uma métrica arbitrária.

## Escopo

Espaços topológicos e bases; continuidade como pré-imagem de aberto; subespaço, produto e quociente; axiomas de separação (`T₀`–`T₄`, Hausdorff); compacidade e Tychonoff; conexidade e conexidade por caminhos; espaços métricos como caso particular; homotopia e grupo fundamental em nível de enunciado. **Escopo negativo:** homologia e cohomologia, topologia algébrica além do `π₁`, e a estrutura diferenciável (nota de Variedades).

## Pré-requisitos

- [[Análise Real]] <!-- relation:prerequisite --> — as noções métricas de compacidade e continuidade são o caso particular do qual se abstrai.
- [[Lógica, Provas e Argumentação]] <!-- relation:prerequisite -->

## Conceitos nucleares

- **Topologia**: família de abertos fechada sob união arbitrária e interseção finita. A assimetria (arbitrária × finita) é a definição, não um detalhe.
- **Continuidade**: `f` contínua ⇔ pré-imagem de aberto é aberta. Coincide com `ε–δ` em espaços métricos.
- **Hausdorff (`T₂`)**: pontos distintos têm vizinhanças disjuntas. Sem isso, limites podem não ser únicos.
- **Compacidade**: toda cobertura aberta admite subcobertura finita. Definição por cobertura, não por sequência — as duas coincidem em métricos, não em geral.
- **Conexidade**: não admite partição em dois abertos não vazios disjuntos. Conexidade por caminhos implica conexidade; a recíproca é falsa.
- **Quociente**: colar pontos por relação de equivalência; é como se constroem toro, faixa de Möbius e espaços projetivos.
- **Homeomorfismo**: bijeção contínua com inversa contínua. É a noção de "mesma forma" desta teoria.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-MAT-TOPO-001` | Compacidade por cobertura e compacidade sequencial são equivalentes em espaços métricos, e independentes em espaços topológicos gerais. | established | Munkres, cap. 3 e 28. Existem espaços compactos não sequencialmente compactos e vice-versa; a equivalência exige metrizabilidade (ou, no mínimo, primeiro-enumerabilidade para uma das direções). |
| `CLM-MAT-TOPO-002` | O teorema de Tychonoff — produto arbitrário de compactos é compacto — é equivalente ao axioma da escolha em ZF. | established | Munkres, cap. 37, apresenta a prova a partir do lema de Zorn; a equivalência reversa é resultado de Kelley (1950). A independência de AC está em [[Teoria dos Conjuntos e Fundamentos]] <!-- relation:prerequisite -->. **Limite:** para produtos *finitos* ou para produtos de espaços de Hausdorff compactos, versões mais fracas bastam. |
| `CLM-MAT-TOPO-003` | Conexidade por caminhos implica conexidade, e a recíproca é falsa. | established | Munkres, cap. 25. Contraexemplo canônico: a curva do seno do topólogo, conexa e não conexa por caminhos. |

## Limites e contraexemplos

- **Bijeção contínua não é homeomorfismo**: `[0,1) → S¹` por `t ↦ e^{2πit}` é contínua e bijetora, com inversa descontínua. A continuidade da inversa é condição independente.
- **Nem todo espaço é metrizável**: a topologia cofinita em conjunto infinito não é Hausdorff, logo não é metrizável. Metrizabilidade tem critérios próprios (Urysohn).
- **Compacto não implica fechado sem Hausdorff**: em espaços não `T₂`, subconjunto compacto pode não ser fechado.
- Intuição de "buraco" só vira invariante depois de definida homotopia; antes disso é linguagem, não argumento — e a política do Vault não aceita analogia como evidência.

## Relações

- [[Análise Real]] <!-- relation:prerequisite -->
- [[Variedades Diferenciáveis e Geometria]] <!-- relation:extends --> — acrescenta estrutura diferenciável a espaços topológicos localmente euclidianos.
- [[Teoria da Medida e Integração]] <!-- relation:contrasts --> — medida e topologia são estruturas independentes sobre o mesmo conjunto; conjunto de Cantor é o exemplo que separa as duas.
- [[Fundamentos de Gravitação e Cosmologia]] <!-- relation:extends --> — questões de topologia global do espaço-tempo pressupõem estas definições.
- [[MOC — Matemática]] <!-- relation:navigation -->

## Fontes

- James R. Munkres. *Topology*. 2ª ed., Prentice Hall, 2000. ISBN 978-0-13-181629-9.

## Condição de revisão

Estável. Revisar se o Vault ganhar nota de topologia algébrica (homologia), que absorveria os invariantes além do `π₁`.
