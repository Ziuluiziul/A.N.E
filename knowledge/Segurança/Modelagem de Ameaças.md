---
title: Modelagem de Ameaças
aliases: [Threat Modeling, Modelo de Adversário, STRIDE]
domain: segurança
kind: nota
status: active
epistemic_status: established
updated: 2026-07-28
verified_at: 2026-07-28
---

# Modelagem de ameaças

## Finalidade

Responder: **contra quem, e contra o quê, exatamente?** Sem modelo de adversário explícito, "seguro" é palavra vazia — nenhuma afirmação de segurança é verificável ou falsificável sem declarar capacidade, motivação e acesso do atacante suposto.

## Escopo

Modelo de adversário: capacidade, acesso, motivação e recursos; propriedades de segurança (confidencialidade, integridade, disponibilidade, autenticidade, não repúdio); as quatro perguntas estruturantes do processo; STRIDE como taxonomia de ameaça; diagramas de fluxo de dados e limites de confiança; árvores de ataque; priorização e aceitação de risco residual; suposições e o que acontece quando elas quebram. **Escopo negativo:** teste de intrusão e ferramentas ofensivas, resposta a incidente, e a avaliação de sistemas de IA especificamente (tratada em IA).

## Pré-requisitos

- [[Princípios de Projeto Seguro]] <!-- relation:prerequisite --> — os princípios dizem como construir; a modelagem diz contra o que.
- [[Criptografia]] <!-- relation:prerequisite --> — os modelos de adversário formais (CPA, CCA) são instância do que aqui se faz informalmente.

## Conceitos nucleares

- **Modelo de adversário**: declaração explícita do que o atacante pode fazer, observar e computar. É a premissa da qual toda garantia depende.
- **As quatro perguntas** (Shostack): *No que estamos trabalhando? O que pode dar errado? O que vamos fazer a respeito? Fizemos um bom trabalho?* A ordem importa — modelar antes de saber o que se está construindo produz teatro.
- **STRIDE**: *Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, Elevation of privilege*. Taxonomia mnemônica; cada categoria é a negação de uma propriedade desejada.
- **Limite de confiança**: fronteira onde o nível de privilégio ou a origem dos dados muda. É onde as ameaças se concentram, e é o que um diagrama de fluxo de dados existe para tornar visível.
- **Árvore de ataque**: decomposição de um objetivo do adversário em sub-objetivos, com custo e viabilidade por caminho.
- **Risco residual**: o que resta após as mitigações. Aceitá-lo é decisão legítima; não declará-lo é a falha.
- **Suposição**: toda garantia tem premissas. A modelagem só é útil se as suposições ficarem escritas — porque o ataque real costuma vir da suposição, não do mecanismo.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-SEG-AMEACA-001` | Uma afirmação de segurança sem modelo de adversário declarado não é verificável nem falsificável. | established | Shostack, cap. 1–2; Anderson, cap. 1. É a mesma exigência de escopo que a política deste Vault impõe a qualquer claim: sem condições de validade declaradas, o enunciado não é auditável. |
| `CLM-SEG-AMEACA-002` | A modelagem de ameaças é mais eficaz aplicada durante o projeto do que após a implementação, porque as mitigações estruturais deixam de estar disponíveis depois. | established | Shostack, cap. 1 e 12. **Escopo:** a afirmação é sobre disponibilidade de opções de mitigação, não sobre inutilidade da modelagem tardia — modelar tarde é melhor que não modelar. |
| `CLM-SEG-AMEACA-003` | Os ataques bem-sucedidos em sistemas reais frequentemente exploram a violação de uma suposição do modelo, e não a quebra do mecanismo modelado. | established | Anderson, cap. 1 e 27, com casos documentados. **Consequência prática:** a lista de suposições é a parte mais valiosa e mais frequentemente omitida do documento de modelagem. |
| `CLM-SEG-AMEACA-004` | STRIDE é uma taxonomia mnemônica para gerar hipóteses de ameaça, e não uma prova de cobertura completa. | established | Shostack, cap. 3, apresenta-a explicitamente como auxílio de geração. Tratar a checagem das seis categorias como demonstração de que nada ficou de fora é erro de leitura da própria ferramenta. |

## Limites e contraexemplos

- **Modelo errado dá falsa garantia**: subestimar a capacidade do adversário produz um sistema demonstravelmente seguro contra um atacante que não existe.
- **Adversário adaptativo invalida análise estática**: o atacante escolhe o caminho depois de ver as defesas; árvores de ataque descrevem um instante, não um jogo.
- **Ameaça interna quebra o pressuposto de fronteira**: a maior parte dos modelos assume que o perigo vem de fora do limite de confiança.
- **Probabilidade em risco de segurança é frágil**: ao contrário de falha aleatória de componente, ataque não tem taxa base estável. Métodos quantitativos de risco importados de confiabilidade transferem mal, e isso conecta ao problema de [[Estimação e Testes de Hipótese]] <!-- relation:contrasts --> — não há amostragem de um processo estacionário.

## Relações

- [[Princípios de Projeto Seguro]] <!-- relation:prerequisite -->
- [[Criptografia]] <!-- relation:prerequisite -->
- [[Fatores Humanos em Segurança]] <!-- relation:extends -->
- [[Segurança, Guardrails e Avaliação]] <!-- relation:extends --> — a instância do problema em sistemas de IA, onde o adversário e as propriedades diferem.
- [[Sistemas Distribuídos e Dados]] <!-- relation:operational -->
- [[MOC — Segurança]] <!-- relation:navigation -->

## Fontes

- Adam Shostack. *Threat Modeling: Designing for Security*. John Wiley & Sons, 2014. ISBN 978-1-118-80999-0.
- Ross Anderson. *Security Engineering: A Guide to Building Dependable Distributed Systems*. 3ª ed., John Wiley & Sons, 2020. ISBN 978-1-119-64278-7.

## Condição de revisão

Estável quanto ao método. Revisar se o Vault ganhar nota de segurança de cadeia de suprimentos, que traria um modelo de adversário estruturalmente distinto.
