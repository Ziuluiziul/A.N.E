---
title: MOC — Python
domain: python
kind: moc
status: active
epistemic_status: mixed
updated: 2026-07-30
verified_at: 2026-07-18
---

# Python

**Objeto central:** a linguagem de trabalho do Vault como domínio próprio — especificação separada de implementação, engenharia separada de sintaxe. Sub-MOC de [[MOC — Ciência da Computação]] <!-- relation:navigation -->.

## Árvore de pré-requisitos

1. [[Modelo de Dados do Python]] <!-- relation:navigation --> — identidade/tipo/valor, protocolos, contrato hash; a fundação de tudo.
2. [[Sistemas Operacionais]] <!-- relation:prerequisite --> — processos, threads e arquivos que o runtime pressupõe.

## Regra do domínio (herdada do dossiê)

**A especificação define identidade, tipo e valor; GIL, contagem de referências, bytecode e layout de objetos são detalhes de implementação por versão.** Toda nota volátil exige `version_scope`, `verified_at` e revisão semestral. Não existe nota estática "O GIL".

## Escopo negativo (critérios de exclusão)

- Teoria geral de linguagens (semântica, tipos) — futura sub-nota de CS.
- Algoritmos independentes de linguagem (nota própria em CS).
- Operação do broker da máquina anterior: a documentação do pipeline não atravessou a migração de 2026-07-28; aqui vive apenas o fundamento de linguagem que ela consumia.

## Lacunas priorizadas

Tipagem gradual (typing); testes e análise estática; packaging/reprodutibilidade (`pyproject.toml` como interface padronizada). O gatilho antigo — "quando o ciclo de automação exigir" — caducou com o pipeline em 2026-07-28. Como Python é camada 3, cada uma pode entrar sem consumidor prévio, desde que entre completa, pela emenda de fundamentos registrada no Índice.

## Fonte curricular

PSF: *The Python Language Reference*, documentação de free-threading e *Python Packaging User Guide*; Ramalho, *Fluent Python* (2ª ed.).

## Teste de navegação (casos reais)

- "Posso usar `is` para comparar strings no broker?" → Modelo de Dados (identidade ≠ igualdade; interning é acidente de CPython).
- "O broker pode paralelizar juízes com threads?" → Modelo de Dados (`CLM-PY-GIL-001`, `version_scope`) + Sistemas Operacionais (corridas).

## Manutenção

Revisão **semestral obrigatória** (domínio volátil por natureza); reconferir free-threading/ABI a cada release do CPython.

Voltar ao [[Índice]] <!-- relation:navigation -->.
