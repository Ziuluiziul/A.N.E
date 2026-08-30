---
title: Modelo de Dados do Python
domain: python
kind: nota
status: active
epistemic_status: mixed
updated: 2026-08-16
verified_at: 2026-07-18
review_after: 2027-01-30
---

# Modelo de dados do Python

## Finalidade

Responder: **o que a linguagem Python garante sobre objetos — e o que é detalhe do CPython?** A distinção especificação/implementação é a regra número um do domínio Python deste Vault. Ela entrou no corpus porque broker, Qtile e a automação da máquina anterior dependiam dela; esses consumidores foram descontinuados na migração de 2026-07-28, e a distinção permanece pelo próprio mérito, não por eles.

## Escopo

Objetos: identidade, tipo e valor; mutabilidade; nomes como vinculações (não caixas); passagem por atribuição de objeto; protocolos e métodos especiais (`__len__`, `__iter__`, `__eq__`/`__hash__`); contrato hash-igualdade; gerenciamento de vida de objetos como *conceito*. **Escopo negativo:** sintaxe, biblioteca padrão, tipagem estática (nota futura), packaging, e detalhes internos do CPython além dos aqui rotulados como voláteis.

## Pré-requisitos

- [[Algoritmos e Estruturas de Dados]] <!-- relation:prerequisite --> — dict/set do Python instanciam tabelas hash com o contrato correspondente.

## Conceitos nucleares

- **Todo objeto tem identidade, tipo e valor**; identidade e tipo são imutáveis durante a vida do objeto; o valor pode mudar se o tipo for mutável.
- **Nomes vinculam objetos**: atribuição nunca copia; `a = b` cria segundo nome para o mesmo objeto — a raiz dos "bugs de alias" com mutáveis.
- **Contrato hash-igualdade**: `x == y` implica `hash(x) == hash(y)`; violá-lo corrompe dicts/sets silenciosamente. Mutáveis não são hasháveis por padrão exatamente por isso.
- **Protocolos**: a semântica emerge de métodos especiais (duck typing); `for` usa `__iter__`/`__next__`, não um tipo "lista".
- **Igualdade ≠ identidade**: `==` compara valor (definível), `is` compara identidade (não definível).

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-PY-DATAMODEL-001` | Todo objeto Python possui identidade, tipo e valor; identidade e tipo não mudam durante a vida do objeto. | established | *Python Language Reference*, cap. Data Model (especificação Python 3); nenhuma implementação conforme pode divergir. |
| `CLM-PY-CPYTHON-001` | Em CPython, `id()` pode corresponder ao endereço de memória do objeto; isso não é garantia da linguagem e não deve ser assumido em código portável. | operational | Documentação oficial do CPython (comportamento de implementação); outras implementações são o contraexemplo. Escopo: CPython 3.13 (`version_scope`). |
| `CLM-PY-GIL-001` | Builds free-threaded do CPython permitem execução sem GIL, sujeita a compatibilidade das extensões; o comportamento depende de versão e build, nunca de "Python" em abstrato. | operational | Documentação oficial de free-threading do CPython; builds padrão e extensões incompatíveis são o contraexemplo. Revisão semestral obrigatória (`review_after`). |

## Limites e contraexemplos

- Interning de inteiros pequenos/strings faz `is` "funcionar" por acidente em CPython — e quebrar em outra implementação ou faixa de valores.
- Objeto default mutável em assinatura de função é compartilhado entre chamadas — consequência direta de "nomes vinculam, não copiam".
- `__eq__` sem `__hash__` coerente torna o objeto inutilizável como chave — falha silenciosa típica.
- Nada nesta nota descreve custo/desempenho: isso é CPython + hardware, volátil por natureza.

## Relações

- [[Algoritmos e Estruturas de Dados]] <!-- relation:prerequisite -->
- [[Sistemas Operacionais]] <!-- relation:prerequisite --> — processos/threads/GIL só fazem sentido sobre o modelo de execução do SO.

## Fontes

- Python Software Foundation. *The Python Language Reference*, cap. 3 “Data Model”, Python 3.13. Documentação oficial.
- Luciano Ramalho. *Fluent Python*. 2ª ed., O'Reilly, 2022.

## Condição de revisão

Semestral (campo volátil `CLM-PY-GIL-001`): reconferir estado do free-threading e compatibilidade de extensões a cada release do CPython; claims de especificação são estáveis por versão da linguagem.
