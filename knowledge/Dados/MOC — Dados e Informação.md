---
title: MOC — Dados e Informação
domain: informação
kind: moc
status: active
epistemic_status: mixed
updated: 2026-07-18
verified_at: 2026-07-18
---

# Dados e informação

**Objeto central:** modelagem, busca, proveniência e curadoria de informação — o fundamento que RAG, avaliação de IA e a própria integridade do Vault consomem.

## Árvore de pré-requisitos

1. [[Recuperação de Informação]] <!-- relation:navigation --> — representação, indexação, ranking e avaliação.
2. [[RAG e Contexto Longo]] <!-- relation:extends --> — aplicação gerativa da RI; consome os fundamentos daqui.
3. [[Avaliação e Proveniência de Sistemas de IA]] <!-- relation:extends --> — proveniência aplicada a sistemas de IA.
4. [[Política Epistêmica e de Linkagem]] <!-- relation:operational --> — a política de dados/proveniência do próprio Vault (linhagem de claims e fontes).

## Escopo negativo (critérios de exclusão)

- ML geral e arquiteturas de modelos (domínio IA).
- Grafos semânticos como "ontologias verdadeiras do mundo" (quarentena por política).
- Embeddings como significado pleno (quarentena por política; embeddings entram como representação com limites declarados).

## Lacunas priorizadas

Modelagem relacional e bancos de dados; ontologias/SKOS com escopo declarado; preservação digital (FAIR operacionalizado) — entram com consumidor real (ex.: migração do ledger para consulta estruturada).

## Fonte curricular

Manning-Raghavan-Schütze (RI); W3C PROV-O (proveniência); Wilkinson et al. 2016 (FAIR); Robertson-Zaragoza (BM25).

## Teste de navegação (casos reais)

- "O RAG do Vigia devolveu contexto certo mas resposta errada — onde olhar?" → Recuperação de Informação (`CLM-IA-RAG-001` na nota RAG: recuperar ≠ responder certo) → Avaliação de IA.
- "Hash do manifesto confere; o conteúdo está correto?" → Integridade do Vault + Política Epistêmica: integridade de bytes ≠ veracidade do conteúdo (princípio do dossiê; o claim formal entrará com a futura nota de Segurança).

## Manutenção

Revisão semestral; RI clássica estável, fronteira RAG viva (nota correspondente tem TTL próprio).

Voltar ao [[Índice]] <!-- relation:navigation -->.
