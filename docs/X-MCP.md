# X MCP (plugin Cursor / Grok Bot)

Camada **Grok Bot / plugin Cursor**. **Não** é contrato do vault-autodidata:
não há adapter X em `providers/`; a API do produto não chama `api.x.com`.
[ADR-003](ADR-003-instrumentacao-antes-de-morfogenese.md) só menciona um tweet
como origem da crítica (https://x.com/anirbanbandyo/status/2088425573102317600).
Isso não torna X parte do produto.

Esta missão **não** chamou X. Endpoints abaixo são os que o skill e as URLs
oficiais nomeiam; nada além.

## Skill (o que dizer ao usuário num 403)

Path:
`/home/box/agent-data/plugins/cache/cursor-public/x/68836ddaf5697224520f1847d90cdb90ca8babaa/skills/x-api-mcp-guide/SKILL.md`

No 403 de enrollment (`client-forbidden`, `user-not-enrolled`,
`client-not-enrolled`) o skill manda **uma** linha e parar — sem retry, sem
mencionar app/projeto/pay-per-use:

> This X account isn't set up yet. Go to https://console.x.com, register and
> onboard with this same X account, then come back and I'll retry.

Leitura que o skill lista na mensagem de capacidades: profile, home timeline,
posts, mentions, search, bookmarks (e news/trends). Escrita MCP que o skill
nomeia para bookmarks: listar, adicionar, remover, pastas. O proxy MCP está em
`https://api.x.com/mcp` (`mcp.json` do plugin; `README.md` do plugin; **não**
chamado nesta missão).

## Página oficial (consulta 2026-08-30)

URLs:

- https://docs.x.com/x-api/fundamentals/response-codes-and-errors
- https://docs.x.com/x-api/getting-started/pricing
- https://docs.x.com/llms.txt
- https://developer.x.com/
- https://console.x.com

O provedor de fetch desta sessão recebeu **HTTP 403** ao pedir `docs.x.com`
(WebFetch e o fetch de `llms.txt`). Isso **não** prova que a página não existe;
prova que o HTML não foi relido aqui. O que segue, sobre o texto dessas
páginas, é o que o briefing desta missão atribui a elas — marcado como tal,
não como leitura desta sessão:

- HTTP 403 = autenticação válida sem permissão.
- tipo `client-forbidden` = *app not enrolled*.
- pricing: pay-per-use; a página **não** lista subscriptions Essential / Free /
  Basic / Pro.

Três camadas distintas, e só a primeira é frase ao usuário:

| Camada | Onde | O que é |
| --- | --- | --- |
| Frase ao usuário | skill, bloco *Not onboarded (403)* | ir a https://console.x.com com a mesma conta; não retry |
| Texto interno de docs.x.com | briefing → página de response codes (HTML **não** relido nesta sessão) | `client-forbidden` = app not enrolled |
| Evidência de sessão | Auditor, **não** produto | MCP `user-X` `get_users_me` forbidden, `required_enrollment: Pay-per-use` |

Pay-per-use **não** é a frase a dizer ao usuário sobre 403. É rótulo que o
Auditor viu no payload de uma sessão, e (segundo o briefing) o modelo de
cobrança da página de pricing. O vault-autodidata não interpreta nenhum dos
três.

Não há lista de endpoints REST X neste documento além do proxy MCP acima e das
URLs oficiais. Inventar path de timeline ou search aqui seria spec falsa.
