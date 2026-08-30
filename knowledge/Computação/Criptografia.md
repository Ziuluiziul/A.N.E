---
title: Criptografia
aliases: [Cripto, Segurança Computacional, Cifras]
domain: computação
kind: nota
status: active
epistemic_status: mixed
updated: 2026-07-28
verified_at: 2026-07-28
---

# Criptografia

## Finalidade

Responder: **o que significa "seguro", como afirmação demonstrável?** A criptografia moderna substituiu engenhosidade por definição formal e prova por redução — e o que ela demonstra é sempre condicional a uma hipótese de dificuldade computacional não provada.

## Escopo

Sigilo perfeito e o teorema de Shannon; segurança computacional e indistinguibilidade; modelos de adversário (CPA, CCA); cifras simétricas e modos de operação; funções de hash e resistência a colisão; MAC e autenticação; criptografia assimétrica (RSA, curvas elípticas); troca de chaves (Diffie–Hellman); assinaturas digitais; o modelo do oráculo aleatório; provas por redução. **Escopo negativo:** implementação e ataques de canal lateral, protocolos de rede específicos, criptografia pós-quântica em profundidade, e política de gestão de credenciais (domínio operacional).

## Pré-requisitos

- [[Complexidade Computacional]] <!-- relation:prerequisite --> — "seguro" significa "quebrar é computacionalmente inviável", e isso pressupõe as conjecturas de lá.
- [[Probabilidade]] <!-- relation:prerequisite --> — as definições são de indistinguibilidade entre distribuições.
- [[Álgebra Abstrata e Teoria de Grupos]] <!-- relation:prerequisite --> — grupos cíclicos e aritmética modular são o substrato de Diffie–Hellman e RSA.

## Conceitos nucleares

- **Sigilo perfeito**: o texto cifrado não dá nenhuma informação sobre o texto claro. Atingível (one-time pad) e exige chave tão longa quanto a mensagem — teorema de Shannon.
- **Segurança computacional**: nenhum adversário eficiente distingue com vantagem não desprezível. É o relaxamento que torna a criptografia prática possível.
- **Prova por redução**: "se existe adversário que quebra o esquema, existe algoritmo que resolve o problema difícil `X`". A segurança é sempre **relativa** a `X`.
- **CPA e CCA**: modelos de ataque com acesso a oráculo de cifragem, e também de decifragem. Segurança contra CPA não implica contra CCA.
- **Hash criptográfica**: resistência a pré-imagem, segunda pré-imagem e colisão — três propriedades distintas, com força crescente.
- **Assimétrica**: chaves pública e privada; permite troca de chave sem canal seguro prévio.
- **Oráculo aleatório**: idealização da hash como função verdadeiramente aleatória. Provas nesse modelo são heurísticas, não demonstrações no modelo padrão.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-COMP-CRIPTO-001` | Sigilo perfeito exige chave de comprimento pelo menos igual ao da mensagem (teorema de Shannon). | established | Katz & Lindell, cap. 2. É por isso que toda criptografia prática abandona o sigilo perfeito em favor do computacional. |
| `CLM-COMP-CRIPTO-002` | Nenhum esquema criptográfico prático em uso tem segurança demonstrada incondicionalmente; todas as provas são reduções a hipóteses de dificuldade não demonstradas. | established | Katz & Lindell, cap. 3 e 8. **Consequência:** `P = NP` implicaria a queda de essencialmente toda a criptografia de chave pública. A segurança do sistema é condicional a conjecturas — fato estrutural, não ressalva retórica. |
| `CLM-COMP-CRIPTO-003` | Provas no modelo do oráculo aleatório não são demonstrações de segurança no modelo padrão. | established | Katz & Lindell, §6.5, apresenta o modelo com a ressalva explícita. Existem esquemas provadamente seguros no oráculo aleatório e inseguros sob qualquer instanciação concreta da hash. **Escopo:** isso não invalida a prática, que usa o modelo como evidência heurística; invalida a leitura de que a prova seja incondicional. |
| `CLM-COMP-CRIPTO-004` | Um computador quântico de escala suficiente quebraria RSA e Diffie–Hellman em tempo polinomial (algoritmo de Shor); a criptografia simétrica é afetada apenas quadraticamente (Grover). | established | Resultado teórico consolidado. **Limite declarado:** "de escala suficiente" é a condição não satisfeita — o estado atual do hardware é questão empírica separada, fora do escopo desta nota e sem fonte verificada aqui. O que se afirma é o resultado algorítmico, não uma previsão de calendário. |

## Limites e contraexemplos

- **Segurança demonstrada é sobre o esquema, não sobre o sistema**: implementações caem por canal lateral, geração de aleatoriedade fraca, reuso de nonce e erro de protocolo — nenhum coberto pela prova.
- **Composição não é automática**: dois esquemas seguros isoladamente podem ser inseguros combinados. Segurança composicional é propriedade a ser demonstrada.
- **Criptografia caseira falha por padrão**: a assimetria entre projetar e criptanalisar é tal que ausência de ataque conhecido por parte do autor não é evidência.
- **Hash "quebrada" tem gradação**: colisões em MD5 e SHA-1 são práticas; pré-imagem não. Usar "quebrada" sem qualificar a propriedade confunde risco real.

## Relações

- [[Complexidade Computacional]] <!-- relation:prerequisite -->
- [[Álgebra Abstrata e Teoria de Grupos]] <!-- relation:prerequisite -->
- [[Probabilidade]] <!-- relation:prerequisite -->
- [[Teoria da Informação]] <!-- relation:extends --> — o sigilo perfeito é enunciado em termos de informação mútua nula.
- [[Sistemas Operacionais]] <!-- relation:operational --> — isolamento e gestão de segredos no sistema.
- [[MOC — Ciência da Computação]] <!-- relation:navigation -->

## Fontes

- Jonathan Katz e Yehuda Lindell. *Introduction to Modern Cryptography*. 3ª ed., Chapman & Hall/CRC (Cryptography and Network Security Series), 2020. ISBN 978-0-8153-5436-9.

## Condição de revisão

Revisar `CLM-COMP-CRIPTO-004` quando o Vault ganhar nota de criptografia pós-quântica, que trataria os padrões de substituição com fonte primária própria.
