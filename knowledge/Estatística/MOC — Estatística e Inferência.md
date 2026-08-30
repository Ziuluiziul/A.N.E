---
title: MOC — Estatística e Inferência
domain: estatística
kind: moc
status: active
epistemic_status: mixed
updated: 2026-07-18
verified_at: 2026-07-18
---

# Estatística e inferência

**Objeto central:** incerteza quantificada — de axiomas de probabilidade a conclusões calibradas sob dados finitos.

## Árvore de pré-requisitos

### Base

1. [[Probabilidade]] <!-- relation:navigation --> — o cálculo; pré-requisito de tudo abaixo.
2. [[Teoria da Medida e Integração]] <!-- relation:prerequisite --> — aresta cruzada com Matemática: o rigor por trás de "variável aleatória" e "esperança".
3. [[Inferência e Incerteza]] <!-- relation:navigation --> — o panorama; estimação, testes, calibração.

### Os dois arcabouços

4. [[Estimação e Testes de Hipótese]] <!-- relation:navigation --> — frequentista: o que um valor-p autoriza e o que não autoriza.
5. [[Inferência Bayesiana]] <!-- relation:navigation --> — posterior, prior e o custo explícito de responder `P(θ | dados)`.

### Predição e informação

6. [[Aprendizado Estatístico]] <!-- relation:navigation --> — ajuste contra generalização; viés–variância, regularização, validação.
7. [[Teoria da Informação]] <!-- relation:navigation --> — entropia, KL e os limites de compressão e transmissão.

### Consumidores

8. [[Desenho Experimental e Causalidade]] <!-- relation:navigation --> — aresta cruzada com Metodologia: a validade da inferência depende da geração dos dados.
9. [[Fundamentos de Aprendizado de Máquina e Modelos de Linguagem]] <!-- relation:operational --> — consumidor principal no Vault (perdas esperadas, generalização).
10. [[Avaliação e Proveniência de Sistemas de IA]] <!-- relation:operational --> — avaliações são inferências sob amostras; herda p-valores e calibração daqui.

## Escopo negativo (critérios de exclusão)

- Metodologia geral sem conteúdo estatístico (MOC de Metodologia).
- Algoritmos de ML em si (domínio IA); aqui vive o fundamento inferencial deles.
- Processos estocásticos e teoria assintótica avançada (entram com consumidor).

## Fonte curricular

Sequência canônica probabilidade → inferência (Ross; Casella-Berger; Gelman et al.); advertência normativa da ASA sobre p-valores incorporada na nota de Inferência.

## Teste de navegação (casos reais)

- "O benchmark de um modelo melhorou 2 pontos — é real?" → Inferência e Incerteza (testes, múltiplas comparações) + Avaliação de IA.
- "Posso confiar numa previsão '80%'?" → Inferência → calibração (`CLM-STAT-CALIB-001`).

## Manutenção

Revisão semestral; a nota de Inferência referencia literatura normativa viva (ASA) — reconferir na revisão.

Voltar ao [[Índice]] <!-- relation:navigation -->.
