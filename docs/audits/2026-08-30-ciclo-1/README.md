# Auditoria de produto — ciclo 1 (2026-08-30)

Auditoria de **produto**, não de corpus. Este arquivo não promove nota,
não lista path em `knowledge/` e não é handoff.

| Campo | Valor |
| --- | --- |
| Data | 2026-08-30 (America/Sao_Paulo) |
| Fonte da missão | A.N.E. (ciclo 1) |
| HEAD reportado | `27d4bdd` |
| Verificação nos remotes | **não verificado** |
| Código de ciclo 2 | ainda não existe neste dump |

## HEAD que o A.N.E. atribuiu, e a lacuna

O A.N.E. atribuiu o SHA `27d4bdd` ao ciclo 1. Essa atribuição **não** foi
conferida nos remotes GitHub `Ziuluiziul/vault-autodidata` e
`Ziuluiziul/A.N.E` (API 422 nesta sessão). O SHA fica documentado como
HEAD que o ciclo 1 reportou, não como HEAD lido de um remote.

O dump em `/workspace/ane-gh`, ramo `complete/product-tree`, está em
`ca070c7`. Não é o mesmo objeto que `27d4bdd`. `vault-autodidata` `main`
em 2026-08-30 17:33 UTC aponta para `c8d7696` — pack de provedores,
já registrado em [PROVEDORES.md](../../PROVEDORES.md); **não** se
duplica aqui.

Sem código de ciclo 2 neste dump: o que segue descreve o que o ciclo 1
observou e o que o dump de produto já contém. Nada daqui é spec de
ciclo 2.

## Promotes de hoje

Nomes como o A.N.E. os deu — não são paths de `knowledge/`:

- Tr_E
- Cordas heading
- Complexidade
- Política

Política de bump nestas promotes: só o campo `updated`. Não houve
`verified_at`. Este registro **não** afirma verificação editorial e
**não** copia o corpo das notas.

## ISBN 978-0-226-61865-4 — confirmado fora do corpus

Cota, não texto de nota. Contagem no dump `knowledge/` em 2026-08-30:
**0 ocorrências** de `978-0-226-61865-4` / `9780226618654`.

Caso ouro nos testes: `tests/test_promotion.py:382-387`
(`test_replace_recusa_isbn_removido`). O fixture monta
«Peter Godfrey-Smith. ISBN 978-0-226-61865-4.» e a guarda recusa o
replace se o identificador some (`PatchRefused`,
`identificadores removidos`). Redução explícita (`reduz=True`) é o
único caminho que passa. O teste **não** coloca o ISBN no corpus; o
corpus, nesta cota, também não o tem.

Resolução Open Library em 2026-08-30 (consulta ao endpoint oficial,
não inventado):

```
GET https://openlibrary.org/api/books?bibkeys=ISBN:9780226618654&format=json&jscmd=data
```

Docs: https://openlibrary.org/dev/docs/api/books

Resposta:

| Campo | Valor |
| --- | --- |
| title | Theory and Reality |
| subtitle | An Introduction to the Philosophy of Science, Second Edition |
| author | Peter Godfrey-Smith |
| publishers | University of Chicago Press |
| publish_date | 2021 |
| isbn_13 | 9780226618654 |
| isbn_10 | 022661865X |
| openlibrary | OL34693585M |
| key | /books/OL34693585M |

Catálogo da editora (página de **autor**, sem slug de livro inventado):
https://press.uchicago.edu/ucp/books/author/G/P/au5266863.html —
lista *Theory and Reality, Second Edition*, July 2021.

**paper ≠ eISBN.** Esta resolução devolveu `isbn_13` / `isbn_10` da
edição 2021 (papel / Open Library). Não se cita eISBN. Sem rede = skip,
nunca approve — contrato em [SOURCE-RESOLVER.md](../../SOURCE-RESOLVER.md).

## 33 cadeiras vazias — observação operacional

O A.N.E., em 2026-08-30, reportou **33 cadeiras vazias** na cena / Atlas.
É observação operacional do ciclo 1. **Não** está como constante `33` no
dump: busca no backend e no frontend deste produto não acha esse
número amarrado a cadeira, seat ou empty.

Duas noções distintas, que este ciclo não funde:

| Noção | O que o dump contém | O que o ciclo 1 observou |
| --- | --- | --- |
| Cadeira de **painel** | `PANEL_ROLES` no orquestrador são **3** papéis (`orchestrator.py:87-91`): `verificador-factual`, `critico-epistemologico`, `revisor-estrutural`. Reposição de cadeira sem voto contado é `_replenish_invalid_votes` (`orchestrator.py:731-732`). | — |
| Cadeira vazia na **cena / Atlas** | Não há constante 33. Os GET SSE do tecido são os três de [ATLAS-SSE.md](../../ATLAS-SSE.md) (`/corpus/events`, `/runtime/events`, `/runtime/cognition`). | 33 cadeiras vazias, reportadas pelo A.N.E. |

Não se inventa endpoint, path SSE nem constante de produto para as 33.
A observação fica aqui, datada, sem promover-se a spec.

## Reposição de voto: um passe

O A.N.E. reportou `VOTE_REPLENISH_ROUNDS=1` para hoje. No dump,
`_replenish_invalid_votes` é **uma** reposição
(`orchestrator.py:731-732`, docstring «Uma reposição»). A string
`VOTE_REPLENISH_ROUNDS` **não** aparece em `.env.example` nem no dump:
não há env com esse nome no código. O `1` alinha-se ao passe único da
função, não a uma variável de ambiente.

## Ver também

- [SOURCE-RESOLVER.md](../../SOURCE-RESOLVER.md) — contrato DOI / arXiv / ISBN; skip sem rede.
- [PROVEDORES.md](../../PROVEDORES.md) — pack `c8d7696`; não duplicado aqui.
- [ATLAS-SSE.md](../../ATLAS-SSE.md) — os três GET; nenhum é cadeira vazia.
