# ADR-001 — Paleta OKLCH dos domínios

**Data:** 2026-08-02 · **Estado:** aceita · **Ciclo:** 1.1

Esta ADR é a **fonte única de verdade** da paleta. Onde o dossiê e este documento
divergirem, vale este documento, e o motivo da divergência está registrado abaixo.

## Contexto

O dossiê "Vault Cognitivo 3D" propõe doze tokens cromáticos em OKLCH para os
domínios, e no mesmo texto exige que a paleta seja validada:

> A associação dos tokens aos domínios é **não especificada**. Antes da implementação
> definitiva, a sequência deve ser validada com simuladores de deficiências de visão
> cromática e, idealmente, recalculada com métodos de maximização de distância como
> Colorgorical ou Glasbey.

A implementação transformou essa exigência num teste: nenhum par de tokens pode ficar
abaixo de um limiar de distância perceptual em OKLab
(`frontend/src/visual.test.ts`).

## Problema

A tabela original reprova o próprio gate. Dois tokens ficam a 15° de matiz um do
outro:

| Token | OKLCH original | Observação |
| --- | --- | --- |
| D03 | `oklch(78% 0.12 90)` | amarelo-esverdeado |
| D12 | `oklch(79% 0.10 105)` | 15° adiante, croma menor |

Distância medida em OKLab: **0,036**. Todos os demais pares ficam acima de 0,045. Com
luminosidades quase iguais (0,78 e 0,79) e matizes vizinhas, os dois seriam lidos como
o mesmo domínio numa legenda de onze itens.

## Método

Distância euclidiana em OKLab, sobre as coordenadas convertidas de OKLCH:

```text
a = C · cos(H),  b = C · sin(H)
d(x, y) = √( (Lx − Ly)² + (ax − ay)² + (bx − by)² )
```

É uma métrica grosseira — não é CIEDE2000 —, mas é suficiente e apropriada para o
defeito que interessa: dois tokens que a legenda não separa. Está implementada em
`perceptualDistance` (`frontend/src/palette.ts`) e é exercida por teste, de modo que a
paleta não pode regredir em silêncio.

Doze pontos igualmente espaçados num círculo de croma 0,12 ficam a
`2 · 0,12 · sen(15°) = 0,062` uns dos outros. O espaçamento uniforme resolve o
problema com folga sem sair da envoltória de luminosidade e croma que o dossiê
especifica (L 0,72–0,79 · C 0,10–0,14).

## Decisão

Manter a envoltória do dossiê e redistribuir as matizes em passos de 30°. Na prática
D01 e D02 ficam intocados, D03 a D11 andam poucos graus, e **D12 é o token que sai do
lugar**, de 105° para 355°, ocupando o vão que existia entre D11 e D01.

| Token | Original | Adotado | Δ matiz |
| --- | --- | --- | --- |
| D01 | `oklch(73% 0.13 25)` | `oklch(73% 0.13 25)` | — |
| D02 | `oklch(75% 0.12 55)` | `oklch(75% 0.12 55)` | — |
| D03 | `oklch(78% 0.12 90)` | `oklch(78% 0.12 85)` | −5° |
| D04 | `oklch(73% 0.12 130)` | `oklch(73% 0.12 115)` | −15° |
| D05 | `oklch(74% 0.12 165)` | `oklch(74% 0.12 145)` | −20° |
| D06 | `oklch(76% 0.11 195)` | `oklch(76% 0.11 175)` | −20° |
| D07 | `oklch(72% 0.13 225)` | `oklch(72% 0.13 205)` | −20° |
| D08 | `oklch(72% 0.14 260)` | `oklch(72% 0.14 235)` | −25° |
| D09 | `oklch(74% 0.13 295)` | `oklch(74% 0.13 265)` | −30° |
| D10 | `oklch(73% 0.13 325)` | `oklch(73% 0.13 295)` | −30° |
| D11 | `oklch(76% 0.11 350)` | `oklch(76% 0.11 325)` | −25° |
| D12 | `oklch(79% 0.10 105)` | `oklch(79% 0.12 355)` | **+250°** |

Distância mínima entre pares: **0,036 → 0,062**.

Os neutros ficam exatamente como o dossiê os define, e dois deles são verificados por
teste contra o hexadecimal publicado:

| Uso | OKLCH | Hex |
| --- | --- | --- |
| Fundo profundo | `oklch(17% 0.015 255)` | `#0b1016` |
| Fundo secundário | `oklch(22% 0.018 255)` | `#151b23` |
| Superfície embutida | `oklch(27% 0.018 255)` | `#21272f` |
| Aresta inativa | `oklch(58% 0.025 250)` | `#6f7c89` |
| Texto principal | `oklch(96% 0.01 255)` | `#edf2f9` |
| Texto secundário | `oklch(82% 0.02 255)` | `#bcc5d1` |
| Foco | `oklch(88% 0.08 220)` | `#9be4fc` |

## Consequências

**Contraste.** Todos os tokens ficam entre L 0,72 e 0,79 contra um fundo de L 0,17. A
diferença de luminosidade é a mesma de antes — o que mudou foi só a matiz —, então
nenhuma relação de contraste piorou.

**Visão cromática.** O espaçamento uniforme melhora o caso de dicromacia em relação à
tabela original, porque elimina o par vizinho em 15°; mas **não** o resolve. Protanopia
e deuteranopia colapsam parte do eixo vermelho-verde, e nenhuma paleta categórica de
doze matizes sobrevive a isso sozinha. É por isso que a arquitetura não deixa nenhuma
informação depender só de cor: forma distingue tipo de entidade, padrão de linha
distingue relação, posição distingue território, e o modo textual entrega tudo sem
cor nenhuma. Um teste específico prende essa redundância.

**Décimo segundo token.** O corpus tem onze domínios e usa D01–D11. D12 existe como
folga para o próximo domínio, e já entra validado.

**Manutenção.** A tabela canônica vive em `DOMAIN_TOKENS`
(`frontend/src/palette.ts`). Mudança nela que reduza a distância mínima abaixo de
0,045 reprova em `frontend/src/visual.test.ts`. Se um dia a paleta for recalculada com
Colorgorical ou Glasbey, o resultado substitui a tabela e esta ADR ganha uma sucessora.

## Alternativas descartadas

**Manter a tabela do dossiê e baixar o limiar para 0,03.** Faria o teste passar sem
resolver nada: os dois tokens continuariam indistinguíveis na legenda, e o gate
deixaria de ser um gate.

**Remover D12.** Resolveria o par, mas gastaria a folga de crescimento e deixaria o
próximo domínio sem token validado.

**Variar luminosidade para separar D03 e D12.** Criaria hierarquia visual entre
domínios — um pareceria mais importante que o outro —, que é justamente o que a
envoltória de luminosidade estreita existe para evitar.
