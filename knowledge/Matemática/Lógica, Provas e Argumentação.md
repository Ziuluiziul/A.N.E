---
title: Lógica, Provas e Argumentação
domain: matemática
kind: nota
status: active
epistemic_status: established
updated: 2026-07-18
verified_at: 2026-07-18
---

# Lógica, provas e argumentação

## Finalidade

Responder: **o que torna um argumento válido, e o que uma prova estabelece (e não estabelece)?** É o pré-requisito de leitura crítica de todo o Vault: separa validade formal, verdade de premissas e evidência empírica.

## Escopo

Proposicional e primeira ordem; técnicas de prova (direta, contraposição, contradição, indução); falácias estruturais. **Escopo negativo:** teoria de modelos avançada, teoria da prova formal, lógicas não clássicas e semântica de linguagens de programação (ver Fundamentos Matemáticos e Métodos da Física Teórica para o uso físico e o futuro domínio de semântica em computação).

## Pré-requisitos

Nenhum interno ao Vault — esta é uma raiz do grafo de fundamentos.

## Conceitos nucleares

- **Validade**: a conclusão segue das premissas em toda interpretação que as satisfaça.
- **Correção (soundness)**: validade + premissas verdadeiras.
- **Prova**: derivação finita a partir de axiomas/hipóteses por regras explícitas; estabelece o teorema *relativo ao sistema* adotado.
- **Indução matemática**: prova sobre naturais (base + passo); não confundir com indução empírica.
- **Quantificadores**: a ordem importa (`∀x∃y` ≠ `∃y∀x`) — fonte clássica de erro em enunciados.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-MAT-LOGICA-001` | Validade dedutiva não equivale a verdade empírica: argumento válido com premissa falsa pode ter conclusão falsa; correção exige validade e premissas verdadeiras. | established | Definição padrão de validade/correção; qualquer texto canônico de lógica. |
| `CLM-MAT-LOGICA-002` | Uma prova matemática estabelece o resultado relativamente ao sistema de axiomas e regras adotado; não é, por si, evidência sobre o mundo físico. | established | Distinção formal/empírico; base da Política Epistêmica e de Linkagem do Vault. |

## Limites e contraexemplos

- "Todos os corvos são verdes; isto é um corvo; logo é verde" é **válido** e empiricamente falso — validade não transmite verdade que as premissas não tenham.
- Indução matemática com passo correto e **base ausente** prova nada (contraexemplo clássico: "todos os cavalos têm a mesma cor").
- Formalizar mal um enunciado (troca de quantificadores) produz "provas" de afirmações distintas da pretendida.

## Relações

- [[Política Epistêmica e de Linkagem]] <!-- relation:operational --> — esta nota fundamenta o vocabulário de validade usado na política.
- [[Fundamentos Matemáticos e Métodos da Física Teórica]] <!-- relation:extends --> — os métodos da física pressupõem estas técnicas de prova.

## Fontes

- Daniel J. Velleman. *How to Prove It: A Structured Approach*. 3ª ed., Cambridge University Press, 2019.
- Herbert B. Enderton. *A Mathematical Introduction to Logic*. 2ª ed., Academic Press, 2001.

## Condição de revisão

Conteúdo estável (matemática consolidada); revisar apenas se o Vault adotar lógicas não clássicas ou formalização mecanizada (proof assistants).
