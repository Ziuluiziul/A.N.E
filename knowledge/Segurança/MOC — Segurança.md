---
title: MOC — Segurança
domain: segurança
kind: moc
status: active
epistemic_status: mixed
updated: 2026-07-28
verified_at: 2026-07-28
---

# Segurança

**Objeto central:** o que torna um sistema defensável — propriedades, princípios de projeto e o adversário contra o qual ambos são declarados. Segurança sem modelo de adversário não é afirmação; é adjetivo.

## Árvore de pré-requisitos

### Estrutura

1. [[Princípios de Projeto Seguro]] <!-- relation:navigation --> — os oito princípios de 1975 e por que continuam sendo o vocabulário da área.

### Método

2. [[Modelagem de Ameaças]] <!-- relation:navigation --> — contra quem e contra o quê; suposições declaradas como parte da garantia.

### Operador

3. [[Fatores Humanos em Segurança]] <!-- relation:navigation --> — por que sistemas com criptografia correta falham na prática.

### Mecanismo

4. [[Criptografia]] <!-- relation:prerequisite --> — aresta cruzada com Computação: as primitivas e o que suas provas condicionam.

## A ponte com Cognição

Este domínio contém a **única aresta Segurança↔Cognição admitida como `prerequisite`**, e vale explicar por quê. Anderson dedica um capítulo inteiro à psicologia da segurança e trata explicitamente dos dois domínios — o que satisfaz a exigência da política de "fonte primária que trate explicitamente dos dois". Sem esse capítulo, a ligação seria analogia e estaria proibida.

As três ligações que ela sustenta:

| De | Para | Conteúdo |
|---|---|---|
| Engenharia social | [[Raciocínio, Julgamento e Decisão]] <!-- relation:prerequisite --> | Explora heurísticas normalmente adaptativas; informar o alvo não corrige. |
| Fadiga de alerta | [[Percepção e Psicofísica]] <!-- relation:extends --> | É deslocamento de critério, formalmente separável de sensibilidade. |
| Aceitabilidade psicológica | [[Princípios de Projeto Seguro]] <!-- relation:prerequisite --> | Princípio de 1975 cujo desenvolvimento empírico é o capítulo de Anderson. |

## Como se liga ao resto do Vault

| Ponte | Tipo | Justificativa |
|---|---|---|
| Criptografia ↔ [[Complexidade Computacional]] <!-- relation:prerequisite --> | **legítima** | "Seguro" significa "quebrar é inviável"; a inviabilidade é conjectura de complexidade. |
| Projeto seguro ↔ [[Sistemas Operacionais]] <!-- relation:prerequisite --> | **legítima** | Isolamento e mediação são mecanismos do SO. |
| Modelagem ↔ [[Segurança, Guardrails e Avaliação]] <!-- relation:extends --> | **legítima** | Mesmo método, adversário e propriedades distintos, em sistemas de IA. |
| Risco de segurança ↔ [[Estimação e Testes de Hipótese]] <!-- relation:contrasts --> | **contraste** | Ataque não tem taxa base estável; métodos de confiabilidade transferem mal. |

## Escopo negativo (critérios de exclusão)

- Ferramentas ofensivas, exploração prática e teste de intrusão.
- Resposta a incidente e forense.
- Conformidade regulatória e certificação.
- Atribuição de ataques a atores — inferência com evidência tipicamente insuficiente para o padrão do Vault.

## Lacunas priorizadas (não criar sem função)

Controle de acesso e modelos formais (Bell–LaPadula, Biba); segurança de redes e
protocolos; segurança de cadeia de suprimentos; privacidade e privacidade
diferencial; segurança de hardware e canais laterais. Cada uma entra quando uma
nota consumidora a exigir — vale a regra de crescimento do [[Índice]] <!-- relation:navigation -->.

## Teste de navegação (casos reais)

- "Este sistema é seguro?" → Modelagem → `CLM-SEG-AMEACA-001` → a pergunta é malformada sem modelo de adversário.
- "Por que ninguém segue a política de senhas?" → Fatores Humanos → `CLM-SEG-HUM-001` → o contorno é resposta previsível ao custo de conformidade.
- "Adicionamos mais uma camada, estamos mais seguros?" → Princípios → `CLM-SEG-PRINC-004` → só se os modos de falha forem independentes.
- "Podemos manter o algoritmo em segredo?" → Princípios → `CLM-SEG-PRINC-002` → a segurança não pode depender disso.

## Fonte curricular

Bibliografia declarada por nota, com identificador verificado em 28/07/2026:
Saltzer & Schroeder 1975 como fonte primária dos princípios (DOI resolvido);
Anderson 3ª ed. (engenharia de segurança e fatores humanos); Shostack (modelagem).

Voltar ao [[Índice]] <!-- relation:navigation -->.
