---
title: Política Epistêmica e de Linkagem
domain: vault
kind: registro
status: active
epistemic_status: operational
updated: 2026-08-30
verified_at: 2026-07-17
---

# Política epistêmica e de linkagem

## Finalidade

Esta política define o que pode integrar o corpus ativo do Vault e o que pode formar uma aresta no seu grafo. O objetivo é preservar utilidade sem converter semelhança verbal, autoridade bibliográfica ou novidade em evidência.

## Regra de admissão

Uma nota ativa precisa satisfazer simultaneamente:

1. **Relevância:** responde a uma pergunta real do Vault ou fornece pré-requisito necessário.
2. **Proveniência:** afirmações externas materialmente importantes apontam para fonte primária, review reconhecida ou observação local reproduzível.
3. **Status explícito:** o texto distingue resultado estabelecido, suporte empírico, consequência dependente de modelo, hipótese e especulação.
4. **Escopo:** a conclusão não excede população, regime, benchmark ou hipóteses da fonte.
5. **Testabilidade editorial:** DOI/arXiv e metadados podem ser revalidados por código.

Conteúdo que falha em qualquer item vai para quarentena. Ser rotulado como “metáfora” não torna conteúdo irrelevante admissível.

## Vocabulário epistêmico

> A justificativa desta taxonomia — e a posição filosófica que ela pressupõe — está em
> [[Filosofia da Ciência]] <!-- relation:prerequisite -->. Esta seção define o uso; ela
> não o fundamenta.


| Valor | Uso permitido |
|---|---|
| `established` | Resultado teórico ou empírico amplamente consolidado no regime declarado. |
| `supported` | Evidência positiva reproduzida, ainda com incertezas ou domínio limitado. |
| `model-dependent` | Consequência válida sob hipóteses/modelo identificados; não é observação direta. |
| `hypothesis` | Proposta científica sem confirmação suficiente. |
| `speculative` | Programa ou interpretação com conexão empírica fraca/indireta. |
| `mixed` | Nota de síntese que separa explicitamente classes diferentes. |
| `operational` | Estado de máquina, configuração, decisão ou procedimento verificável. |
| `quarantine` | Item irresolúvel, irrelevante ou em conflito; fora do corpus ativo. |

## Unidade mínima de afirmação

Notas científicas ativas usam uma tabela de claims na seção `Estado epistêmico`. Cada linha deve conter:

1. ID estável e globalmente único no formato `CLM-DOMINIO-TOPICO-NNN`;
2. uma afirmação falsificável ou circunscrita;
3. um status do vocabulário fechado de claims;
4. evidência, hipótese ou limite de escopo suficiente para auditar a linha.

Status de claim permitidos: `established`, `supported`, `model-dependent`, `hypothesis`, `speculative`, `open`, `refuted`, `operational`, `out-of-scope` e `quarantine`. O status da nota resume o conjunto; não substitui o status linha a linha. `refuted` exige contradição efetiva; ausência de evidência deve ser `open`, `hypothesis` ou `speculative`, conforme o caso.

O gate reprova ID ausente ou duplicado, status fora do vocabulário e linha sem afirmação ou evidência/escopo.

## Fontes e referências

- DOI/arXiv deve resolver e corresponder ao título canônico após apenas normalização de caixa, Unicode, pontuação e espaços.
- Matching fuzzy pode sugerir revisão, mas nunca aprovar promoção automaticamente.
- Se DOI e arXiv da mesma linha retornarem títulos materialmente distintos, a linha falha; os identificadores devem ser separados ou o metadado inconsistente removido.
- Toda linha Markdown com DOI/arXiv em nota ativa é auditada, inclusive tabelas; não apenas bullets bibliográficos.
- Preprint não é chamado de peer-reviewed sem venue confirmado.
- Ano de submissão, revisão e publicação são campos distintos.
- Um DOI que resolve para outro título é **mismatch confirmado**, não “a confirmar”.
- Item sem identificador não recebe BibTeX ativo; permanece como pista em quarentena.
- Publicação de modelo teórico não aumenta suporte empírico por si.
- Review organiza evidência; não cria evidência nova.
- Retratação, correção ou versão nova reabre a revisão.

## Wikilinks tipados

Todo wikilink ativo deve trazer, na mesma linha, um comentário de relação:

```markdown
[[Fundamentos Matemáticos e Métodos da Física Teórica]] <!-- relation:prerequisite -->
```

Tipos permitidos:

| Tipo | Significado |
|---|---|
| `navigation` | MOC, índice ou retorno estrutural; não expressa confirmação. |
| `prerequisite` | O destino fornece conceitos necessários. |
| `extends` | O destino aprofunda o mesmo objeto ou formalismo. |
| `contrasts` | Comparação explícita entre mecanismos distintos. |
| `evidence` | O destino contém fontes ou dados que sustentam o trecho. |
| `operational` | Dependência técnica/configuracional real. |
| `historical` | Relação histórica documentada por fonte. |

São proibidos no grafo ativo: `analogy`, `metaphor`, `inspiration`, `wordplay` e `speculative_association`.

## Links entre domínios

Uma aresta Física↔IA, Física↔filosofia ou ciência↔operação só é permitida quando:

- há dependência operacional real; ou
- uma fonte primária trata explicitamente dos dois domínios; e
- a nota preserva as ressalvas dessa fonte.

Vocabulário compartilhado — “entropia”, “informação”, “emergência”, “aprendizado”, “alinhamento” — não constitui relação.

## Dados voláteis

Notas de APIs, hardware e software exigem `verified_at` e `review_after`. Após o vencimento:

- continuam válidas como snapshot histórico;
- não podem ser tratadas como estado atual;
- exigem reconferência na fonte viva antes de serem reafirmadas.

## Semântica de `verified_at` (definida em 2026-07-18)

`verified_at` registra a data da última **verificação de fontes** da nota, no nível declarado pela própria nota. Há três níveis, e a nota deve deixar claro qual alega:

1. **Resolução bibliográfica**: identificadores (DOI/arXiv/ISBN) resolvem e os títulos conferem com a fonte oficial. É o nível mínimo. **Não alega leitura nem confronto do conteúdo.**
2. **Verificação substantiva**: o conteúdo citado foi confrontado com a fonte (resumo/artigo lido; claim comparado ao que a fonte afirma). É o nível das auditorias de rigor.
3. **Adequação curricular** (notas de fundamentos com fontes canônicas de livro): a citação foi conferida quanto a autor/título/edição e adequação ao escopo da nota — sem releitura integral da obra.

Regras: atualizar `verified_at` **somente** quando uma verificação real ocorreu na data; **nunca** alegar nível 2 quando houve apenas nível 1 (resolução não é leitura); a mera edição do texto atualiza `updated`, não `verified_at`. Quando níveis distintos coexistem numa nota, o corpo declara qual fonte recebeu qual nível e quando (ex.: "títulos conferidos via Crossref em AAAA-MM-DD" = nível 1).

## Promoção e revisão

Promoção de quarentena para ativo exige:

1. Fonte resolvida;
2. Escopo e status revisados;
3. Validação determinística aprovada;
4. Diff pequeno e auditável;
5. Promoção requer quórum multimodel: o proponente não conta; são necessários ao menos dois provedores que aprovem;
6. O **Promoter** é o único escritor do diretório `knowledge/`; intervenções humanas são restritas a credenciais, OAuth interativo, comandos administrativos/destrutivos e consumo acima do orçamento.

## Nota sobre esta política

Estas regras foram escritas quando o Vault era mantido por um pipeline automatizado com gates determinísticos. O pipeline foi descontinuado na migração de 2026-07-28.

O **Promoter** passou a ser o único escritor do diretório `knowledge/`; intervenções humanas limitam‑se a credenciais, OAuth interativo, comandos administrativos/destrutivos e consumo acima do orçamento. O critério editorial permanece o mesmo: a regra de admissão, o vocabulário epistêmico, a tabela de claims, o tratamento de fontes e a tipagem de wikilinks continuam sendo o padrão do corpus — agora aplicados por julgamento humano em vez de gate.
