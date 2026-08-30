---
title: Princípios de Projeto Seguro
aliases: [Saltzer-Schroeder, Menor Privilégio, Princípios de Segurança]
domain: segurança
kind: nota
status: active
epistemic_status: established
updated: 2026-07-28
verified_at: 2026-07-28
---

# Princípios de projeto seguro

## Finalidade

Responder: **que propriedades estruturais tornam um sistema defensável, antes de qualquer mecanismo específico?** Os princípios enunciados em 1975 continuam sendo o vocabulário de projeto da área — e a maior parte das falhas práticas é a violação de um deles, não a quebra de um algoritmo.

## Escopo

Os oito princípios de Saltzer e Schroeder; base computacional confiável (TCB) e superfície de ataque; separação de privilégios e compartimentalização; defesa em profundidade e sua leitura correta; falha segura; mediação completa; projeto aberto e a crítica à segurança por obscuridade; economia de mecanismo. **Escopo negativo:** primitivas criptográficas (nota própria), modelagem de ameaças como processo (nota própria), conformidade regulatória e gestão de risco corporativo.

## Pré-requisitos

- [[Sistemas Operacionais]] <!-- relation:prerequisite --> — isolamento, anéis de privilégio e mediação são implementados lá.
- [[Criptografia]] <!-- relation:prerequisite --> — os princípios delimitam onde a criptografia ajuda e onde ela é irrelevante.

## Conceitos nucleares

- **Economia de mecanismo**: o projeto deve ser tão simples quanto possível. Simplicidade é condição de auditabilidade, não estética.
- **Falha segura (*fail-safe defaults*)**: a decisão padrão é negar; o acesso é concedido por permissão explícita, não por ausência de proibição.
- **Mediação completa**: toda tentativa de acesso é verificada. Caches de decisão de autorização são a violação mais comum.
- **Projeto aberto**: a segurança não depende do sigilo do projeto, apenas do segredo da chave. É o princípio de Kerckhoffs generalizado.
- **Separação de privilégio**: exigir mais de uma condição para conceder acesso.
- **Menor privilégio**: cada componente opera com o mínimo de autoridade necessária.
- **Mecanismo comum mínimo**: minimizar o que é compartilhado entre usuários, porque compartilhamento é canal.
- **Aceitabilidade psicológica**: a interface deve tornar o uso correto natural. Um controle que atrapalha será contornado — e o contorno é a vulnerabilidade real.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-SEG-PRINC-001` | Os oito princípios de projeto de proteção — economia de mecanismo, falha segura, mediação completa, projeto aberto, separação de privilégio, menor privilégio, mecanismo comum mínimo e aceitabilidade psicológica — foram enunciados em 1975 e permanecem o vocabulário de referência da área. | established | Saltzer e Schroeder, "The Protection of Information in Computer Systems", *Proceedings of the IEEE* 63(9):1278–1308 (1975), DOI `10.1109/PROC.1975.9939` — verificado na fonte em 28/07/2026. Anderson, cap. 1, reafirma a vigência. |
| `CLM-SEG-PRINC-002` | Segurança por obscuridade não é propriedade de segurança: um sistema cuja defesa depende do sigilo do projeto falha quando o projeto vaza, e projetos vazam. | established | Saltzer & Schroeder, princípio de projeto aberto; Anderson, cap. 5. **Escopo:** o princípio **não** afirma que revelar detalhes é sempre benéfico — afirma que a segurança não pode *depender* do sigilo do mecanismo. Confundir as duas leituras é erro corrente nos dois sentidos. |
| `CLM-SEG-PRINC-003` | A aceitabilidade psicológica é um princípio de projeto de igual estatuto aos demais, não uma preocupação secundária de usabilidade. | established | Saltzer & Schroeder listam-no entre os oito; Anderson, cap. 3, documenta o mecanismo de falha. **Consequência:** controles que impõem custo desproporcional ao usuário são contornados de forma previsível, e o contorno costuma ser pior que a ausência do controle. |
| `CLM-SEG-PRINC-004` | "Defesa em profundidade" significa camadas com modos de falha independentes; camadas que falham pela mesma causa não somam proteção. | established | Anderson, cap. 1 e 27. **Erro que o claim delimita:** empilhar controles correlacionados — todos dependentes do mesmo diretório de identidade, por exemplo — produz aparência de profundidade sem ganho, porque uma única falha derruba todas. |

## Limites e contraexemplos

- **Princípio não é receita**: menor privilégio e usabilidade entram em conflito real; o projeto é uma negociação, e declarar o princípio não a resolve.
- **TCB só é útil se for pequena e verificada**: chamar um componente de "confiável" é declaração de dependência, não de qualidade. Confiável significa "cuja falha compromete tudo".
- **Superfície de ataque não é métrica bem definida**: contagens de interfaces expostas variam com a granularidade escolhida; servem para comparar variantes de um mesmo sistema, não para pontuar sistemas distintos.
- **Conformidade não é segurança**: satisfazer um padrão é evidência de processo, e a correlação com resistência real a adversário é fraca.

## Relações

- [[Sistemas Operacionais]] <!-- relation:prerequisite -->
- [[Criptografia]] <!-- relation:prerequisite -->
- [[Modelagem de Ameaças]] <!-- relation:extends --> — o processo que decide contra o que se defende.
- [[Fatores Humanos em Segurança]] <!-- relation:extends --> — a aceitabilidade psicológica desenvolvida.
- [[Sistemas Distribuídos e Dados]] <!-- relation:operational --> — mediação e confiança entre nós.
- [[MOC — Segurança]] <!-- relation:navigation -->

## Fontes

- Jerome H. Saltzer e Michael D. Schroeder. "The Protection of Information in Computer Systems". *Proceedings of the IEEE* 63(9), 1278–1308 (1975). DOI `10.1109/PROC.1975.9939`.
- Ross Anderson. *Security Engineering: A Guide to Building Dependable Distributed Systems*. 3ª ed., John Wiley & Sons, 2020. ISBN 978-1-119-64278-7. Edição eletrônica disponibilizada pelo autor.

## Condição de revisão

Estável. Os princípios têm meio século e sobreviveram a várias gerações de tecnologia; revisar apenas se o Vault ganhar nota de arquitetura de confiança zero.
