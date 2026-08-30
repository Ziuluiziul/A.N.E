---
title: Fatores Humanos em Segurança
aliases: [Usabilidade e Segurança, Engenharia Social, Fator Humano]
domain: segurança
kind: nota
status: active
epistemic_status: established
updated: 2026-07-28
verified_at: 2026-07-28
---

# Fatores humanos em segurança

## Finalidade

Responder: **por que sistemas com criptografia correta falham na prática?** Porque a garantia matemática cobre o mecanismo e não o operador. Esta é a ponte legítima entre [[MOC — Segurança]] <!-- relation:navigation --> e [[MOC — Cognição]] <!-- relation:navigation -->: existe fonte primária tratando explicitamente dos dois domínios, e por isso a aresta é `prerequisite` e não analogia.

## Escopo

Aceitabilidade psicológica desenvolvida; custo de conformidade e comportamento de contorno; engenharia social e os mecanismos cognitivos que ela explora; *phishing* e limites do treinamento; autenticação e o problema de senhas; fadiga de alerta e habituação; efeito de enquadramento em decisões de segurança; incentivos desalinhados entre quem sofre o dano e quem paga a defesa. **Escopo negativo:** psicologia clínica, políticas de RH, e taxonomia de ataques técnicos (nota de modelagem).

## Pré-requisitos

- [[Princípios de Projeto Seguro]] <!-- relation:prerequisite --> — a aceitabilidade psicológica é um dos oito princípios de 1975, e esta nota é o seu desenvolvimento.
- [[Raciocínio, Julgamento e Decisão]] <!-- relation:prerequisite --> — os mecanismos explorados pela engenharia social são os descritos lá.

## Conceitos nucleares

- **Custo de conformidade**: todo controle impõe um custo ao usuário legítimo. Quando o custo excede o percebido benefício, o contorno é a resposta racional — e o contorno cria a vulnerabilidade real.
- **Engenharia social**: manipulação que explora autoridade, urgência, reciprocidade e escassez. Não é falha de inteligência do alvo; é exploração de heurísticas normalmente adaptativas.
- **Fadiga de alerta**: avisos frequentes com baixa taxa de acerto são habituados e ignorados. A taxa de falsos positivos determina a eficácia do canal de alerta.
- **Senhas**: exigências de complexidade e rotação frequente produzem padrões previsíveis e reuso. O requisito ataca o sintoma e agrava a causa.
- **Assimetria de incentivos**: quem decide o nível de segurança frequentemente não é quem sofre a perda. É problema econômico, não técnico, e resiste a solução técnica.
- **Enquadramento**: a mesma decisão de segurança é tomada de forma diferente conforme apresentada como perda ou como ganho.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-SEG-HUM-001` | Controles de segurança cujo custo de conformidade excede o benefício percebido pelo usuário são contornados de forma sistemática e previsível. | established | Anderson, cap. 3. É a formulação operacional do princípio de aceitabilidade psicológica de Saltzer e Schroeder. **Consequência de projeto:** o comportamento de contorno deve ser tratado como resposta previsível ao projeto, não como indisciplina do usuário. |
| `CLM-SEG-HUM-002` | A engenharia social explora heurísticas de julgamento que são normalmente adaptativas, e por isso a suscetibilidade não se corrige apenas por informar o alvo. | established | Anderson, cap. 3, conecta explicitamente ao aparato de heurísticas e vieses. **Aresta legítima:** este é o ponto em que Segurança e Cognição se ligam com fonte que trata dos dois — ver `CLM-COG-JULG-001` em [[Raciocínio, Julgamento e Decisão]] <!-- relation:evidence -->. |
| `CLM-SEG-HUM-003` | Alertas com alta taxa de falsos positivos perdem eficácia por habituação, independentemente de sua correção técnica. | established | Anderson, cap. 3. **Ligação formal:** o problema é o de critério de resposta em [[Percepção e Psicofísica]] <!-- relation:extends --> — a decisão do operador tem sensibilidade e critério separáveis, e inundar o canal desloca o critério. |
| `CLM-SEG-HUM-004` | Boa parte das falhas de segurança em sistemas reais decorre de incentivos desalinhados, e não de deficiência técnica. | established | Anderson, cap. 8 (economia da segurança). **Escopo:** "boa parte" é a formulação sustentável; a proporção exata dependeria de uma taxonomia de incidentes que não foi consultada aqui, e por isso não é afirmada. |

## Limites e contraexemplos

- **Culpar o usuário é diagnóstico incorreto e caro**: quando o contorno é previsível, o defeito está no projeto. "Erro humano" como causa raiz encerra a investigação no lugar errado.
- **Treinamento tem efeito limitado e decadente**: reduz taxa de sucesso de ataques genéricos, e muito menos de ataques direcionados; o efeito decai sem reforço.
- **Estudos de usabilidade em segurança herdam os problemas de replicação** do campo de origem — ver `CLM-COG-JULG-003`. Números específicos de eficácia de intervenção devem ser tratados com o mesmo ceticismo.
- **Autenticação multifator não é uniforme**: SMS, aplicativo e chave de hardware têm resistências muito diferentes a *phishing*; tratar "MFA" como propriedade única apaga a distinção que importa.

## Relações

- [[Princípios de Projeto Seguro]] <!-- relation:prerequisite -->
- [[Raciocínio, Julgamento e Decisão]] <!-- relation:prerequisite -->
- [[Percepção e Psicofísica]] <!-- relation:extends --> — sensibilidade e critério na decisão do operador.
- [[Modelagem de Ameaças]] <!-- relation:extends --> — o operador faz parte do sistema modelado.
- [[Reprodutibilidade e Replicação]] <!-- relation:evidence -->
- [[MOC — Segurança]] <!-- relation:navigation -->

## Fontes

- Ross Anderson. *Security Engineering: A Guide to Building Dependable Distributed Systems*. 3ª ed., John Wiley & Sons, 2020. ISBN 978-1-119-64278-7.
- Jerome H. Saltzer e Michael D. Schroeder. "The Protection of Information in Computer Systems". *Proceedings of the IEEE* 63(9), 1278–1308 (1975). DOI `10.1109/PROC.1975.9939`.

## Condição de revisão

Revisar `CLM-SEG-HUM-004` se uma taxonomia quantitativa de incidentes for consultada — a proporção está deliberadamente não afirmada.
