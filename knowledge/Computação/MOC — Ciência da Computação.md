---
title: MOC — Ciência da Computação
domain: computação
kind: moc
status: active
epistemic_status: mixed
updated: 2026-07-30
verified_at: 2026-07-18
---

# Ciência da computação

**Objeto central:** fundamentos teóricos e sistêmicos da computação — custo, correção e abstrações de máquina — independentes de linguagem.

## Árvore de pré-requisitos

1. [[Algoritmos e Estruturas de Dados]] <!-- relation:navigation --> — custo e correção; a porta de entrada.
2. [[Sistemas Operacionais]] <!-- relation:navigation --> — processos, memória, arquivos, concorrência.
3. [[MOC — Python]] <!-- relation:navigation --> — sub-MOC autônomo da linguagem de trabalho do Vault.
4. [[Recuperação de Informação]] <!-- relation:navigation --> — aresta cruzada com Dados: índices e ranking instanciam estruturas daqui.
5. [[Fundamentos de Aprendizado de Máquina e Modelos de Linguagem]] <!-- relation:extends --> — consumidor: ML é computação sobre as estruturas e custos daqui.

6. [[Teoria da Computação]] <!-- relation:navigation --> — o que pode ser computado; decidibilidade, parada, Rice.
7. [[Complexidade Computacional]] <!-- relation:navigation --> — entre os decidíveis, quais são viáveis; P, NP, e a conjectura aberta.
8. [[Criptografia]] <!-- relation:navigation --> — o que "seguro" significa como afirmação demonstrável, e sob que hipótese.
9. [[Sistemas Distribuídos e Dados]] <!-- relation:navigation --> — o que muda quando a rede pode falhar; consistência, consenso, replicação.

## Escopo negativo (critérios de exclusão)

- Detalhes exclusivos de Python (sub-MOC próprio).
- Operação específica do broker da máquina anterior: a documentação do pipeline não atravessou a migração de 2026-07-28 e não tem MOC neste Vault.
- Redes/distribuídos e teoria da computação formal (decidibilidade, NP) — entram como sub-notas quando um consumidor exigir.

## Fonte curricular

ACM/IEEE-CS/AAAI *Computer Science Curricula 2023*; bibliografia canônica por nota (CLRS; Tanenbaum-Bos; OSTEP).

## Teste de navegação (casos reais)

- "Por que o manifesto do Vault usa hash e o ledger usa append+fsync?" → Algoritmos (hash, custo) + Sistemas Operacionais (durabilidade, journaling).
- "Threads no broker seriam seguras?" → Sistemas Operacionais (corridas, deadlock) + Modelo de Dados do Python (GIL, `version_scope`).

## Manutenção

Revisão semestral do MOC; teoria estável, sistemas com fronteira volátil declarada nas notas.

Voltar ao [[Índice]] <!-- relation:navigation -->.
