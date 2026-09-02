# Source resolver — contrato de identificadores

Contrato do que o produto consulta quando um identificador precisa de
resolução externa. Código: `tools/resolve_sources.py`, alvo
`make audit-fontes`. O gate estrutural (`make audit`) continua offline
e não chama este resolvedor. Sem rede o identificador sai `skip`, nunca
`ok`. Não inventa path (`/v2/isbn` e afins). Endpoints abaixo foram
copiados da página oficial, não de memória.

O caso ouro ISBN foi exercitado em 2026-08-30 (HEAD `27d4bdd`): resolução
Open Library da edição papel, zero ocorrências no dump de `knowledge/` na
mesma data. O relatório dessa passagem não faz parte da superfície do produto.

| Identificador | Resolver | Endpoint canônico (copiado da página) | Doc oficial |
| --- | --- | --- | --- |
| DOI | Crossref REST | `GET https://api.crossref.org/works/{doi}` | https://www.crossref.org/documentation/retrieve-metadata/rest-api/ (também https://api.crossref.org/) |
| arXiv | export | `GET http://export.arxiv.org/api/query` (method `query`; params `id_list` / `search_query`) | https://info.arxiv.org/help/api/user-manual.html |
| ISBN | Open Library + catálogo da editora | `GET https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data` ; página de edição `https://openlibrary.org/isbn/{isbn}` (docs: https://openlibrary.org/dev/docs/api/books) | catálogo = página da editora, não um host genérico inventado |

## Regras

**paper ≠ eISBN.** São ISBNs distintos. O caso ouro Godfrey-Smith usou
`978-0-226-61865-4` / `9780226618654`, `isbn_10` `022661865X` — edição
2021 papel / Open Library. Não tratar como ebook. Não citar eISBN.

**Godfrey-Smith = caso ouro.** Três âncoras, nenhuma no corpus: o teste
de promoção (`tests/test_promotion.py:382-387`, recusa se o
identificador some), a resolução Open Library de 2026-08-30, e a cota
de 0 ocorrências no dump `knowledge/` na mesma data.

**Sem rede = skip, nunca approve.** Resolução que falha, estoura o
tempo ou não tem rede **não promove**. Skip não é aprovação por
omissão.

**Crossref polite pool.** A página de acesso pede identificação via
`mailto` —
https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/
— cite essa página; não invente o nome do header.

**Não invente path.** Não há `/v2/isbn` neste contrato. ISBN resolve
pela Open Library (tabela) e, em paralelo, pela página da editora do
item — não por um host genérico de catálogo.

## O que isto não é

Não é ADR. Não copia corpo de nota. O índice de docs permanece o
[README](README.md).
