# Handoff — GPT-5.6 SOL no VS Code — 2026-08-03

Continuação depois das Implementações 1 a 4 da diretriz consolidada. O SHA deste
commit não aparece aqui: um documento não pode conter o identificador do commit que o
contém sem que a gravação mude o identificador.

## Como reconhecer o HEAD correto

O commit esperado é filho direto de
`c28492b`, com o assunto:

```text
Decide propostas por quórum sem expor raciocínio interno
```

Confirme com `git rev-parse HEAD^` e `git log --oneline -1`. Se houver commits
posteriores, trate este handoff como histórico e audite o que veio depois antes de
agir.

## Estado entregue

```text
repositório     /home/ziul/Projetos/vault-autodidata
branch          main
corpus          81 notas · 627 wikilinks · 267 claims · 12 MOCs · 11 domínios
manifesto       4f5b1d009041583c89957f7c22199d8d77836f4441f7e6aa16e741da8b2bf5bb
testes          258 pytest · 69 vitest
gates           audit, ruff, mypy, tsc, eslint limpos
árvore          limpa
```

O corpus não foi tocado em nenhuma das quatro implementações. O manifesto é o mesmo
desde a baseline, e tem que continuar sendo até que uma promoção por quórum o mude.

## O prompt

Cole o texto abaixo. Ele é a instrução, e o resto deste arquivo é o material de
consulta que ela referencia.

---

Você assume o Vault Autodidata, em `/home/ziul/Projetos/vault-autodidata`, a partir do
commit `Decide propostas por quórum sem expor raciocínio interno`.

O projeto é um sistema local onde várias IAs pesquisam, criticam o trabalho umas das
outras, formam quórum e ampliam um corpus acadêmico interdisciplinar navegável num
Atlas 3D. Ele está em regime de implementação permanente desde 2026-08-03: você
commita seu próprio trabalho de código assim que `make audit && make test && make lint`
passarem com zero defeito, sem pedir aprovação. Mensagem em português, no imperativo,
dizendo **por que** a mudança entra. Confirmação humana continua obrigatória em quatro
casos e só neles: mexer em credencial, OAuth interativo, comando administrativo ou
destrutivo (`git push`, reescrita de histórico, remoção de dados), e consumo externo
acima do orçamento configurado. Leia `AGENTS.md` antes de começar — ele é a norma, e
tem precedência sobre este prompt.

Quatro coisas já funcionam e você não precisa refazer. A sonda escolhe endpoint por
aptidão em vez de ordem alfabética, e guarda o que observou em
`runtime/state/endpoints.json`. O inventário dos 175 endpoints é consultável por
provedor, propósito, família e estado. O orquestrador distribui tarefas entre
endpoints comprovados, respeitando cota por endpoint, por provedor e por execução, sem
retry escondido. E o quórum decide propostas com voto estruturado, exigindo 3 votos
válidos, 2 provedores e 2 famílias, descartando raciocínio interno antes de contar
qualquer coisa.

Sua próxima entrega é a **Implementação 5, o Proposal Promoter**: o componente que pega
uma proposta aprovada pelo quórum, confirma a base Git, aplica o patch numa árvore
temporária, roda os controles mínimos, cria o commit, publica o corpus novo e registra
quem propôs e quem avaliou. Ele é o primeiro componente do projeto autorizado a
escrever em `knowledge/`, e por isso é o mais perigoso: nenhum agente escreve lá
diretamente, o caminho é sempre `runtime/proposals/` e o Promoter. Não construa o
Writer Gateway de 1.572 linhas que foi proposto e recusado — ele foi aposentado como
estudo arquitetural superado e a cópia está em
`~/.local/share/vault-autodidata/backups/`, com SHA-256 registrado. O Promoter é
mínimo: patch explícito, diff restrito aos alvos declarados, auditoria estrutural
antes do commit, rollback por `git revert`, procedência registrada.

Depois dele vêm a Implementação 6, que é fazer a camada operacional do Atlas mostrar
eventos reais — agente iniciado, proposta criada, voto recebido, quórum alcançado,
commit publicado — e a Implementação 7, que é geração automática de tarefas a partir
das lacunas do próprio corpus.

Três regras do corpus que custam caro quando ignoradas. Identificador só entra
resolvido na fonte: DOI, arXiv ou ISBN que você não conseguiu verificar agora fazem a
afirmação inteira ser omitida, porque identificador plausível e errado é pior que
lacuna. Ausência de evidência nunca é `refuted` — pode ser `open`, `hypothesis` ou
`speculative`, e escolher entre os três é julgamento editorial. E todo wikilink ativo
declara a relação na mesma linha, com o vocabulário fechado; analogia e vocabulário
compartilhado não criam aresta.

Não reorganize domínios, não mova notas entre pastas e não crie notas que não foram
pedidas. Autonomia de commit é sobre código; a estrutura do corpus continua sendo
decisão do mantenedor.

Comece rodando `make audit`, `make endpoints` e `uv run pytest -q` para confirmar que
o estado bate com o descrito, e leia a seção de pendências deste handoff antes de
escolher por onde atacar.

---

## O que já existe, e onde

```text
providers/aptitude.py    classifica endpoint por modalidade, propósito, estabilidade
providers/registry.py    o que a sonda observou, por (provedor, endpoint)
providers/catalog.py     leitura dos retratos da descoberta
providers/inventory.py   junção consultável das três fontes acima
vault/work/              orquestrador: papéis, tarefas, cotas, execução, histórico
vault/quorum/            voto estruturado, parser, motor de decisão, síntese
tools/endpoints.py       `make endpoints` — inventário, sem tocar na rede
tools/smoke_providers.py `make smoke-providers` — uma sonda dirigida por provedor
tools/run_work.py        `make work TAREFA="..."`
tools/run_quorum.py      `make quorum TAREFA="..."`
tools/atlas.sh           `make icon` instala o lançador; o script sobe tudo e abre
```

## Endpoints, hoje

```text
groq     qwen/qwen3.6-27b            ok        recebe trabalho
groq     llama-3.3-70b-versatile     ok        recebe trabalho
nvidia   z-ai/glm-5.2                ok        recebe trabalho
google   gemini-3.6-flash            reachable alcançado, não comprovado
google   gemini-3.5-flash            reachable alcançado, não comprovado
nvidia   deepseek-ai/deepseek-v4-flash  unavailable  529 na execução observada
```

`reachable` e `ok` não são sinônimos e a distinção é deliberada: `reachable` é 200 com
credencial aceita e nenhum texto de volta. Só `ok` autoriza trabalho.

## Pendências conhecidas

**Google ainda não comprovou saída textual útil.** Com os 16 tokens de saída da sonda,
os modelos com raciocínio interno gastam o orçamento inteiro pensando e devolvem 200
vazio. O caminho e a credencial estão provados; a utilidade não. Comprovar exige uma
sonda com orçamento maior — decisão de cota do mantenedor, não ajuste de código. Sem
isso, o quórum opera com dois provedores, que é o mínimo, e não com três.

**`make dev` deixa órfão.** O alvo põe backend e frontend em sessões próprias com
`setsid`, mas guarda o PID do `setsid` em vez do líder do grupo criado, então o `kill`
do trap erra o alvo e o uvicorn sobrevive segurando a porta 8000. Foi observado ao
construir o lançador, que por isso não usa `make dev` — ele sobe os dois como filhos
diretos, com job control, e encerra por PGID com escalação para KILL. O defeito no
`make dev` continua lá.

**`run_work.py` guarda a resposta crua.** O `strip_reasoning` do quórum remove
raciocínio interno antes de contar voto, mas o histórico em `runtime/modelos/` grava o
texto como veio, `<think>` incluído. Para auditoria isso é até desejável; para
alimentar o Atlas com o que o modelo *concluiu*, não é.

**`runtime/quorum/` e `runtime/proposals/` estão vazios.** Nenhuma proposta real
percorreu o caminho inteiro ainda. O primeiro teste de ponta a ponta do Promoter será
também o primeiro do quórum sobre conteúdo de verdade.

## O ícone

`make icon` instala o lançador no menu do GNOME como **Vault Autodidata**. Ele abre um
terminal visível — o ponto é acompanhar —, imprime quais endpoints estão comprovados,
projeta o corpus, sobe backend e frontend e abre o Atlas em
`http://127.0.0.1:5173` assim que o Vite responder. Ctrl-C ou fechar a janela encerra
os dois; se o desligamento limpo não terminar em 5 segundos, o script força, porque
servidor sobrevivente impediria a próxima abertura.
