---
title: Sistemas Distribuídos e Dados
aliases: [Sistemas Distribuídos, Consistência, CAP, Replicação]
domain: computação
kind: nota
status: active
epistemic_status: established
updated: 2026-07-28
verified_at: 2026-07-28
---

# Sistemas distribuídos e dados

## Finalidade

Responder: **o que muda quando o sistema tem mais de uma máquina e a rede pode falhar?** Falha parcial é a diferença qualitativa: em uma máquina, algo funciona ou quebra; distribuído, o normal é não saber. Toda garantia de consistência e durabilidade é enunciada contra esse pano de fundo.

## Escopo

Modelos de falha e falha parcial; relógios, ordenação e relação de precedência causal; replicação (líder único, multi-líder, sem líder); particionamento; transações e ACID; níveis de isolamento e anomalias; consenso e suas equivalências; o teorema CAP e o que ele de fato afirma; consistência eventual e forte; log como estrutura fundamental; processamento em lote e em fluxo. **Escopo negativo:** implementações de bancos específicos, ajuste de desempenho, e protocolos de rede de baixo nível.

## Pré-requisitos

- [[Sistemas Operacionais]] <!-- relation:prerequisite --> — concorrência, escalonamento e durabilidade de escrita em uma máquina.
- [[Algoritmos e Estruturas de Dados]] <!-- relation:prerequisite -->

## Conceitos nucleares

- **Falha parcial**: componentes falham independentemente e o observador não distingue lentidão de falha. É a premissa que gera todo o resto.
- **Relógio não é ordem**: relógios físicos derivam; a ordenação confiável usa contadores lógicos (Lamport) ou vetoriais, que capturam causalidade e não tempo.
- **Replicação**: líder único dá ordenação simples e ponto único de falha; multi-líder e sem líder aceitam escrita concorrente e exigem resolução de conflito.
- **Isolamento de transações**: `read committed`, `snapshot isolation`, `serializable` — cada nível admite anomalias específicas. "Serializável" é o único que preserva o raciocínio sequencial.
- **Consenso**: fazer nós concordarem num valor. É equivalente a eleição de líder, a *lock* distribuído e a registro linearizável — um resolvido, todos resolvidos.
- **Log append-only**: ordenação total durável; base de replicação, de recuperação e de fluxo. É a estrutura mais reutilizada da área.
- **Consistência eventual**: réplicas convergem se as escritas cessarem. Garantia mais fraca do que costuma ser lido.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-COMP-DIST-001` | Em presença de partição de rede, um sistema replicado precisa escolher entre disponibilidade e consistência forte (teorema CAP). | established | Kleppmann, cap. 9, apresenta o resultado **e a crítica à sua leitura popular**. **Escopo estrito:** o teorema trata de linearizabilidade sob partição em um modelo específico; a formulação "escolha 2 de 3" é enganosa, porque a partição não é escolha do projetista, e porque fora de partição não há trade-off imposto pelo teorema. |
| `CLM-COMP-DIST-002` | Consenso é impossível em sistema assíncrono com ao menos uma falha por parada, se exigida terminação determinística (resultado FLP). | established | Resultado de Fischer, Lynch e Paterson; discutido em Kleppmann, cap. 8–9. **Como a prática contorna:** algoritmos reais (Raft, Paxos) usam temporizadores, o que os torna parcialmente síncronos, ou aleatoriedade. Não violam FLP — mudam o modelo. |
| `CLM-COMP-DIST-003` | Níveis de isolamento abaixo de serializável admitem anomalias documentadas, e "snapshot isolation" não previne *write skew*. | established | Kleppmann, cap. 7, com exemplos concretos. É a origem de defeitos que passam em teste e falham sob concorrência real. |
| `CLM-COMP-DIST-004` | Relógios de parede não são fonte confiável de ordenação em sistemas distribuídos. | established | Kleppmann, cap. 8 — deriva, salto por NTP e ausência de garantia de monotonicidade. Ordenação exige relógio lógico ou coordenação explícita. |

## Limites e contraexemplos

- **"Eventualmente consistente" não delimita quanto tempo**: sem cota de convergência, a garantia é fraca demais para muitas aplicações e frequentemente lida como se fosse forte.
- **Retentativa cria duplicata**: sem idempotência, o reenvio após timeout aplica a operação duas vezes. O cliente não distingue "falhou" de "sucedeu e a resposta se perdeu".
- **Exactly-once não existe na rede**: existe entrega ao-menos-uma-vez mais processamento idempotente, que é outra coisa e deve ser projetada.
- **Distribuir por antecipação é custo sem benefício**: a maior parte dos sistemas cabe em uma máquina; adotar o modelo distribuído importa toda a dificuldade acima sem necessidade demonstrada.

## Relações

- [[Sistemas Operacionais]] <!-- relation:prerequisite -->
- [[Algoritmos e Estruturas de Dados]] <!-- relation:prerequisite -->
- [[Recuperação de Informação]] <!-- relation:operational --> — índices distribuídos herdam estes problemas.
- [[Criptografia]] <!-- relation:operational --> — autenticação entre nós e integridade de log.
- [[Reprodutibilidade e Replicação]] <!-- relation:contrasts --> — "replicação" aqui é cópia de estado entre máquinas; lá é repetição independente de um estudo. Homonímia registrada para impedir aresta indevida.
- [[MOC — Ciência da Computação]] <!-- relation:navigation -->

## Fontes

- Martin Kleppmann. *Designing Data-Intensive Applications: The Big Ideas Behind Reliable, Scalable, and Maintainable Systems*. O'Reilly Media, 2017. ISBN 978-1-4493-7332-0.

## Condição de revisão

Revisar quando o Vault ganhar nota de bancos de dados ou de redes, que absorveriam respectivamente o modelo relacional e os protocolos de transporte.
