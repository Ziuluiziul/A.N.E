---
title: Reprodutibilidade e Replicação
domain: metodologia
kind: registro
status: active
epistemic_status: established
updated: 2026-07-18
verified_at: 2026-07-18
---

# Reprodutibilidade e replicação

## Finalidade

Responder: **o que significa "o resultado se sustenta"?** Distinguir recomputar dos mesmos dados (reprodutibilidade) e reobter o fenômeno com novos dados (replicação) — a distinção que o Vault usa para pesar evidência.

## Escopo

Definições institucionais; condições para reprodutibilidade computacional (dados + código + ambiente + etapas); replicação como novo estudo da mesma pergunta; graus de replicação (direta, conceitual); práticas TOP (pré-registro, dados abertos, materiais). **Escopo negativo:** estatística da "crise de replicação" por área, meta-análise, e a auditoria de integridade de arquivos do Vault (runbook próprio — recomputação de hash não é replicação científica).

## Pré-requisitos

- [[Inferência e Incerteza]] <!-- relation:prerequisite --> — sem entender poder e p-valores, "falha de replicação" não tem leitura correta.

## Conceitos nucleares

- **Reprodutibilidade** (sentido National Academies): mesmos dados + mesmo código ⇒ mesmos resultados; é condição *mínima*, não validação.
- **Replicação**: novos dados voltados à mesma pergunta científica; é o teste real do fenômeno.
- **Falha de replicação** não implica fraude nem refutação automática: poder, heterogeneidade e desvios de protocolo são explicações concorrentes a serem examinadas.
- **Pré-registro** separa confirmatório de exploratório; ambos são legítimos quando rotulados.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-METODO-REPRO-001` | Reprodutibilidade computacional requer dados, código, etapas e condições suficientes para obter resultados consistentes; estudo sem componente computacional é o contraexemplo de escopo. | established | National Academies (2019), “Reproducibility and Replicability in Science” — identificador nas Fontes; título conferido via Crossref em 2026-07-18. |
| `CLM-METODO-REPL-001` | Replicação envolve novo estudo com novos dados voltados à mesma pergunta científica; recomputação do mesmo conjunto não constitui replicação. | established | National Academies (2019), mesma fonte; a distinção é definicional e normativa. |

## Limites e contraexemplos

- Bit-a-bit idêntico com **erro de projeto idêntico**: reprodutível e errado — reprodutibilidade não valida a ciência.
- Replicação conceitual divergente pode refletir moderadores reais, não falsidade do original.
- Áreas com eventos únicos (astronomia transiente, paleontologia) exigem noções adaptadas — a régua não é uniforme.

## Relações

- [[Desenho Experimental e Causalidade]] <!-- relation:prerequisite -->
- [[Avaliação e Proveniência de Sistemas de IA]] <!-- relation:operational --> — reprodutibilidade de avaliações de modelos.
- [[Política Epistêmica e de Linkagem]] <!-- relation:operational --> — os status de claim implementam esta régua.

## Fontes

- National Academies of Sciences, Engineering, and Medicine. “Reproducibility and Replicability in Science”. The National Academies Press, 2019. DOI `10.17226/25303`.
- Brian A. Nosek et al. “Promoting an open research culture” (TOP Guidelines). *Science* 348(6242), 1422–1425 (2015). DOI `10.1126/science.aab2374`.

## Condição de revisão

Revisar quando o Vault instituir pré-registro interno para experimentos dos próprios agentes (previsto na fase de orquestração).
