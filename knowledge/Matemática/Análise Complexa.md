---
title: Análise Complexa
aliases: [Funções Holomorfas, Variável Complexa]
domain: matemática
kind: nota
status: active
epistemic_status: established
updated: 2026-07-28
verified_at: 2026-07-28
---

# Análise complexa

## Finalidade

Responder: **por que diferenciabilidade sobre `C` é uma condição tão mais forte que sobre `R`?** Uma derivada complexa implica infinitas; essa rigidez é o que torna a continuação analítica, os métodos de contorno e a estrutura de polos ferramentas de cálculo em vez de curiosidades.

## Escopo

Funções holomorfas e equações de Cauchy–Riemann; integral de contorno; teorema e fórmula de Cauchy; analiticidade e séries de potências; zeros isolados e princípio da identidade; singularidades e séries de Laurent; teorema dos resíduos; princípio do módulo máximo; continuação analítica; aplicações conformes e Riemann; funções meromorfas. **Escopo negativo:** superfícies de Riemann em profundidade, funções de várias variáveis complexas, geometria complexa, e as aplicações específicas em teoria quântica de campos (domínio de Física).

## Pré-requisitos

- [[Análise Real]] <!-- relation:prerequisite --> — convergência de séries e limite uniforme são o aparato operante.
- [[Cálculo Multivariável e Vetorial]] <!-- relation:prerequisite --> — Cauchy–Riemann é condição sobre as derivadas parciais; a integral de contorno é integral de linha.

## Conceitos nucleares

- **Holomorfia**: derivada complexa existe num aberto. Equivale às equações de Cauchy–Riemann com parciais contínuas — é uma condição sobre *duas* funções reais acopladas, não uma derivada a mais.
- **Teorema de Cauchy**: integral de holomorfa sobre curva fechada num domínio simplesmente conexo é nula. A hipótese topológica sobre o domínio é essencial.
- **Fórmula de Cauchy**: o valor num ponto interior é determinado pelos valores na fronteira. É a fonte de toda a rigidez subsequente.
- **Analiticidade**: holomorfa ⇒ representável por série de potências convergente ⇒ infinitamente diferenciável. Em `R` nenhuma dessas implicações vale.
- **Princípio da identidade**: se duas holomorfas coincidem num conjunto com ponto de acumulação no domínio conexo, coincidem em todo ele. É a base da continuação analítica.
- **Resíduo**: coeficiente `a₋₁` da série de Laurent; o teorema dos resíduos converte integrais em soma de resíduos.
- **Módulo máximo**: função holomorfa não constante não atinge máximo de `|f|` no interior.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-MAT-ANCOMP-001` | Diferenciabilidade complexa num aberto implica analiticidade e diferenciabilidade infinita; o análogo real é falso. | established | Stein & Shakarchi, cap. 2. Contraexemplo real: `f(x)=x²·sin(1/x)` (com `f(0)=0`) é diferenciável e não `C¹`; `e^{−1/x²}` é `C^∞` e não analítica em 0. |
| `CLM-MAT-ANCOMP-002` | O teorema dos resíduos permite calcular integrais reais definidas que não têm primitiva elementar. | established | Stein & Shakarchi, cap. 3. **Limite de escopo:** o método exige que se possa fechar o contorno com contribuição controlada no arco; não é procedimento universal. |
| `CLM-MAT-ANCOMP-003` | A continuação analítica de uma função holomorfa, quando existe, é única. | established | Consequência do princípio da identidade; Stein & Shakarchi, cap. 2. **Limite:** a unicidade é local ao longo de um caminho — continuação por caminhos distintos pode dar valores distintos (monodromia), como no logaritmo. A unicidade global exige domínio simplesmente conexo. |

## Limites e contraexemplos

- **Nem toda função tem continuação**: existem funções holomorfas com fronteira natural, além da qual nenhuma continuação existe.
- **Simplesmente conexo é hipótese, não detalhe**: `1/z` é holomorfa em `C∖{0}` e sua integral no círculo unitário é `2πi`, não zero. O teorema de Cauchy falha exatamente por causa da topologia do domínio.
- **Holomorfia é rígida demais para modelagem direta**: funções com suporte compacto não nulas não são holomorfas — não há "bump function" analítica. Onde a análise real dá flexibilidade, a complexa dá estrutura, e a troca é essa.
- Liouville: função inteira e limitada é constante. Consequência imediata: não existe versão holomorfa global de funções limitadas interessantes.

## Relações

- [[Análise Real]] <!-- relation:prerequisite -->
- [[Cálculo Multivariável e Vetorial]] <!-- relation:prerequisite -->
- [[Topologia]] <!-- relation:prerequisite --> — conexidade simples é hipótese explícita dos teoremas centrais.
- [[Fundamentos de Teoria Quântica de Campos e Teorias Efetivas]] <!-- relation:extends --> — estrutura analítica de amplitudes e polos.
- [[MOC — Matemática]] <!-- relation:navigation -->

## Fontes

- Elias M. Stein e Rami Shakarchi. *Complex Analysis*. Princeton University Press (Princeton Lectures in Analysis II), 2003. ISBN 978-0-691-11385-2.

## Condição de revisão

Estável. Revisar se o Vault ganhar nota de superfícies de Riemann.
