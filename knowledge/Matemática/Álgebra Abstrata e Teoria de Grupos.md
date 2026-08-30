---
title: Álgebra Abstrata e Teoria de Grupos
aliases: [Grupos, Anéis e Corpos, Teoria de Grupos]
domain: matemática
kind: nota
status: active
epistemic_status: established
updated: 2026-07-28
verified_at: 2026-07-28
---

# Álgebra abstrata e teoria de grupos

## Finalidade

Responder: **o que é uma simetria, formalmente?** Grupo é a estrutura que captura transformação reversível e composição; é o vocabulário em que conservação, degenerescência espectral e classificação de partículas são enunciadas — e é o que torna "simetria" um objeto matemático em vez de uma intuição visual.

## Escopo

Grupos, subgrupos, homomorfismos, quocientes; teoremas de isomorfismo; ações de grupo e órbita–estabilizador; grupos simétricos e teorema de Cayley; teoremas de Sylow; grupos abelianos finitamente gerados; anéis, ideais, domínios; corpos e extensões; teoria de Galois em nível de enunciado; representações lineares em nível de enunciado; grupos de Lie e álgebras de Lie em nível de enunciado. **Escopo negativo:** classificação dos grupos simples finitos, teoria de representações em profundidade, álgebra homológica, e as aplicações físicas específicas (domínio de Física).

## Pré-requisitos

- [[Lógica, Provas e Argumentação]] <!-- relation:prerequisite --> — relações de equivalência e quocientes são o aparato recorrente.
- [[Álgebra Linear]] <!-- relation:prerequisite --> — representação é homomorfismo em `GL(V)`; sem espaço vetorial não há representação.

## Conceitos nucleares

- **Grupo**: conjunto com operação associativa, elemento neutro e inversos. Comutatividade **não** faz parte da definição — é o caso particular abeliano.
- **Homomorfismo e núcleo**: `ker φ` é subgrupo normal; todo subgrupo normal é núcleo de algum homomorfismo. Essa correspondência é o primeiro teorema de isomorfismo.
- **Ação de grupo**: `G × X → X` compatível com a operação. Órbita–estabilizador: `|orbita(x)| = [G : Est(x)]`.
- **Sylow**: para `|G| = p^a·m` com `p ∤ m`, existem subgrupos de ordem `p^a`, todos conjugados, em número `≡ 1 mod p`. É a principal ferramenta estrutural para grupos finitos.
- **Anel, ideal, corpo**: anel quociente por ideal maximal é corpo — o mecanismo que constrói `F_p` e extensões algébricas.
- **Grupo de Lie**: grupo que é também variedade suave, com operações suaves. Sua álgebra de Lie é o espaço tangente na identidade, com o colchete.
- **Representação**: homomorfismo `G → GL(V)`. Irredutível quando não há subespaço invariante próprio não trivial.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-MAT-ALG-001` | Todo grupo é isomorfo a um subgrupo de um grupo de permutações (teorema de Cayley). | established | Dummit & Foote, §4.2. **Limite de utilidade:** o mergulho existe, mas o grupo simétrico resultante é em geral grande demais para ser informativo; o teorema é estrutural, não computacional. |
| `CLM-MAT-ALG-002` | Subgrupos normais são exatamente os núcleos de homomorfismos, e a correspondência entre eles e os quocientes é biunívoca. | established | Dummit & Foote, §3.1–3.3 (teoremas de isomorfismo). |
| `CLM-MAT-ALG-003` | A conexão entre simetria contínua e lei de conservação é um teorema de mecânica analítica (Noether), não uma consequência da teoria de grupos isolada. | established | O aparato de grupos de Lie é pré-requisito, não causa. **Escopo:** a demonstração exige formulação lagrangiana com ação diferenciável e simetria contínua da ação; a demonstração e as hipóteses estão em [[Cálculo Variacional]] <!-- relation:evidence -->, `CLM-MAT-VARIAC-002`, e a instância física em [[Fundamentos de Mecânica Analítica e Campos Clássicos]] <!-- relation:evidence -->. Registrar a atribuição aqui evita a leitura, comum e incorreta, de que "grupos implicam conservação". |

## Limites e contraexemplos

- **Ordem não determina o grupo**: existem grupos não isomorfos de mesma ordem — `Z/4Z` e `Z/2Z × Z/2Z` na ordem 4. Contar elementos não classifica.
- **A recíproca de Lagrange é falsa**: `d | |G|` não garante subgrupo de ordem `d`. O grupo alternado `A₄` tem ordem 12 e nenhum subgrupo de ordem 6. Sylow recupera o caso de potência de primo, e só ele.
- **Nem todo grupo tem representação fiel de dimensão baixa**; a existência de representação não diz nada sobre seu tamanho útil.
- Simetria de uma equação não é simetria de suas soluções: soluções podem quebrar a simetria do sistema que as gera — fenômeno físico central e frequentemente confundido com contradição.

## Relações

- [[Álgebra Linear]] <!-- relation:prerequisite -->
- [[Lógica, Provas e Argumentação]] <!-- relation:prerequisite -->
- [[Variedades Diferenciáveis e Geometria]] <!-- relation:extends --> — grupos de Lie são variedades; a estrutura suave vem de lá.
- [[Fundamentos de Mecânica Analítica e Campos Clássicos]] <!-- relation:evidence --> — onde a relação simetria–conservação é demonstrada.
- [[Fundamentos de Teoria Quântica de Campos e Teorias Efetivas]] <!-- relation:extends --> — grupos de gauge instanciam esta estrutura.
- [[MOC — Matemática]] <!-- relation:navigation -->

## Fontes

- David S. Dummit e Richard M. Foote. *Abstract Algebra*. 3ª ed., John Wiley & Sons, 2003. ISBN 978-0-471-43334-7.

## Condição de revisão

Estável. Revisar se o Vault ganhar nota dedicada a teoria de representações ou a grupos de Lie, que absorveriam o material hoje mantido em nível de enunciado.
