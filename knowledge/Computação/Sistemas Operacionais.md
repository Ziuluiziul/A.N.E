---
title: Sistemas Operacionais
domain: computação
kind: nota
status: active
epistemic_status: established
updated: 2026-07-18
verified_at: 2026-07-18
---

# Sistemas operacionais

## Finalidade

Responder: **que abstrações transformam hardware compartilhado em processos isolados e arquivos confiáveis?** É a teoria por trás das notas operacionais de Linux do Vault — princípios estáveis, não snapshots da máquina.

## Escopo

Processos e threads; escalonamento; memória virtual (paginação, proteção); concorrência (condições de corrida, exclusão mútua, deadlock); sistemas de arquivos (nomes, inodes, journaling como conceito); IPC; fronteira kernel/usuário e chamadas de sistema. **Escopo negativo:** administração de distribuições específicas, configuração da máquina local (ver a nota operacional Ambiente Computacional) e redes (sub-MOC futuro).

## Pré-requisitos

- [[Algoritmos e Estruturas de Dados]] <!-- relation:prerequisite --> — escalonadores, caches e alocadores são algoritmos com estruturas próprias.

## Conceitos nucleares

- **Processo**: programa em execução com espaço de endereçamento próprio; a **memória virtual** dá a cada um a ilusão de memória privada contígua e impõe proteção por hardware (MMU).
- **Thread**: fluxo de execução dentro do processo; compartilha memória — e por isso compartilha corridas.
- **Corrida de dados**: resultado depende da intercalação; exclusão mútua (locks) serializa seções críticas ao custo de possível **deadlock** (condições de Coffman).
- **Chamada de sistema**: única porta legítima do usuário ao kernel; a fronteira de privilégio que todo modelo de segurança pressupõe.
- **Journaling**: escrever a intenção antes do dado torna a recuperação após falha um replay — o mesmo princípio do ledger deste Vault (`fsync`, append, replay).

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-CS-SO-001` | Memória virtual com proteção por hardware isola espaços de endereçamento de processos: um processo de usuário não lê nem escreve memória de outro sem mediação do kernel. | established | Arquitetura MMU/paginação padrão; canais laterais microarquiteturais (ex.: classe Spectre) são a exceção declarada — vazam por inferência, não por acesso direto. |
| `CLM-CS-SO-002` | Deadlock exige simultaneamente exclusão mútua, posse-e-espera, não-preempção e espera circular; negar qualquer uma das condições o previne. | established | Condições de Coffman; prevenir tem custo (ordenação global de locks, preempção) — a engenharia escolhe o trade-off. |

## Limites e contraexemplos

- Isolamento de memória **não** é isolamento de informação: canais laterais e side effects de timing existem — a base do ceticismo da DEC-0001 (Governança de Privilégios) sobre "isolamento" nominal.
- `fsync` garante durabilidade só até onde o dispositivo honra flush — firmware mentiroso quebra a pilha inteira.
- Threads sem disciplina de lock podem ser mais lentas que um único fluxo (contenção, coerência de cache).

## Relações

- [[Algoritmos e Estruturas de Dados]] <!-- relation:prerequisite -->

## Fontes

- Andrew S. Tanenbaum e Herbert Bos. *Modern Operating Systems*. 5ª ed., Pearson, 2022.
- Remzi H. Arpaci-Dusseau e Andrea C. Arpaci-Dusseau. *Operating Systems: Three Easy Pieces* (OSTEP). Arpaci-Dusseau Books, versão 1.10, 2023.

## Condição de revisão

Estável; revisar quando Redes/Distribuídos ganharem sub-MOC (herdariam IPC remoto e consistência).
