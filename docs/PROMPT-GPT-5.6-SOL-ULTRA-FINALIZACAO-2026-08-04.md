# Prompt — GPT-5.6 SOL Ultra — finalização

Cole o bloco entre os `---` no VS Code.

**O incremento da sessão interrompida está commitado.** Não há working tree a
preservar: HEAD é `5e65409`, árvore limpa, e os gates foram verificados nesse HEAD —
304 pytest, 85 vitest, audit aprovado com o manifesto do corpus inalterado, ruff,
mypy, tsc, eslint e build limpos, `git diff --check` limpo, nenhuma credencial no
diff.

---

Você assume o Vault Autodidata em `/home/ziul/Projetos/vault-autodidata` e vai
finalizar a missão. Confirme o ponto de partida com `git log --oneline -3`: o HEAD
esperado é `5e65409`, com o assunto "Põe o Vault a trabalhar sozinho e a mostrar o que
faz". Se houver commits posteriores, audite-os antes de agir.

Não refaça o que existe. Já estão implementados, testados e commitados: seleção de
endpoint por aptidão, inventário consultável, orquestrador com cotas por endpoint e
por provedor, quórum multimodelo com voto estruturado, Proposal Promoter com todas as
guardas, barramento de eventos operacionais com replay por revisão, fila persistente
com posse única por trava de arquivo, worker contínuo, gerador de tarefas, proponente
emitindo patch estruturado, painéis operacionais no frontend, supervisor único que
sobe backend, frontend e worker e encerra sem órfãos, e a base da profundidade visual
em `frontend/src/depth.ts` — câmera oblíqua por extensão, `FogExp2`, tone mapping
neutro, luz principal e de recorte, cascas translúcidas nos territórios.

Restam quatro frentes. Faça nesta ordem.

**Primeira: atividade real ponta a ponta.** A única inspeção visual até agora usou
eventos sintéticos em `/tmp`. Isso validou a renderização e não conclui nada sobre o
sistema. Suba o Vault e deixe o worker trabalhar com as cotas configuradas em
`VAULT_WORK_MAX_CALLS`, sem ultrapassar orçamento e sem retry oculto. Confirme que a
cadeia real — tarefa criada, enfileirada, atribuída, chamada iniciada e concluída ou
falha, temporário criado, proposta, quórum iniciado, voto pedido e recebido, quórum
decidido, e então rejeição ou promoção — é persistida, chega ao frontend em tempo
real, aparece nos painéis e na camada 3D, não exige recarregar a página, não altera
o fingerprint do corpus, e sobrevive à reconexão pelo replay. O runtime sintético pode
continuar existindo, mas só como fixture de teste.

**Segunda: verifique e termine o acabamento visual.** A base existe e nunca foi olhada
com dados reais. Abra a aplicação num navegador com WebGL de verdade e julgue com os
olhos: o Atlas precisa ter profundidade perceptiva forte, separação clara entre frente,
meio e fundo, territórios com volume legível, MOCs como âncoras espaciais, relações
atravessando o espaço, neon discreto, brilho seletivo, transparências limpas,
atenuação por distância e camada operacional espacialmente distinta. Ajuste com
inspeção real: posição e elevação da câmera, FOV, amplitude da calota, compressão
vertical dos territórios, escala de MOCs e nós, espessura aparente das relações,
opacidade por profundidade, emissive, luzes, densidade do fog, blending, LOD, colisão
de rótulos, separação em `z` da camada operacional e as transições. Consulte a
documentação oficial da versão de Three.js instalada antes de mexer em recurso de
renderização; não confie em memória de API. Não transforme o Atlas em esfera livre,
não destrua a memória espacial, não reposicione o corpus arbitrariamente e não anime
nada que não corresponda a um evento.

**Terceira: complete os painéis.** Endpoint com provedor, endpoint, família, papel,
estado, tarefa, chamadas iniciadas e concluídas, falhas, latência, limites observados,
restante, próximo momento elegível e participação em quóruns. Tarefa com origem, tipo,
domínio, prioridade, objetivo, estado, proponente, avaliadores, temporários,
evidências, proposta e resultado. Quórum com membros, provedores, famílias, papéis,
votos válidos, abstenções, tally, confiança, ação e decisão. Ancorados às entidades,
dentro da linguagem espacial do Atlas — não um dashboard separado da cena.

**Quarta: promoção real de baixo risco.** O elo está fechado no código e nunca
disparou sobre `knowledge/`. Deixe o ciclo rodar até que uma proposta válida seja
aprovada pelo quórum e promova. Não fabrique aprovação nem force alteração só para
demonstrar o mecanismo. Se o quórum rejeitar, a rejeição real também é resultado
válido: ela deve aparecer no Atlas e o sistema deve seguir produzindo outras tarefas.

Corrija a aderência ao schema de voto na Groq. No último quórum real, os dois votos da
Groq vieram inválidos e contaram como abstenção; só o da NVIDIA foi válido. Sem isso o
quórum degrada para avaliador único e nunca alcança os três votos exigidos.

Produza capturas da própria aplicação com runtime real: visão global, camada
operacional viva, painel de endpoint, painel de tarefa, painel de quórum, atividade
durante chamada, decisão de quórum, e o estado depois de promoção ou rejeição. DOM,
log e teste não substituem prova visual. Corrija os defeitos que a inspeção revelar.

Regras de operação. Commite seu próprio trabalho assim que
`make audit && make test && make lint && pnpm --dir frontend run build && git diff --check`
passarem com zero defeito; mensagem em português, no imperativo, dizendo por que a
mudança entra. Cada commit entrega capacidade executável — nenhum commit puramente
documental. Não descarte alteração para fazer teste passar: corrija o código.
Confirmação humana só em quatro casos — credencial, OAuth interativo, comando
administrativo ou destrutivo, e consumo externo acima do orçamento configurado.

Não pare em `PARTIAL` por falha isolada de endpoint. Um 404, um 529 ou um timeout
rebaixa o endpoint, nunca o provedor; escolha outro apto e siga.

Três regras do corpus que custam caro quando ignoradas: identificador que você não
conseguiu verificar agora faz a afirmação inteira ser omitida; ausência de evidência
nunca é `refuted`; analogia e vocabulário compartilhado não criam aresta. E não
reorganize domínios nem crie notas que ninguém pediu — autonomia de commit é sobre
código, a estrutura do corpus é decisão do mantenedor.

No commit final, deixe um handoff curto com HEAD, commits realizados, capacidades
entregues, comandos de início e encerramento, endpoints usados, chamadas consumidas,
testes, estado do corpus, evidências visuais e limitações externas reais. Não o
transforme em nova especificação.

Comece o relato final por `STATUS: PASS`, e use outro status só diante de impedimento
externo que não possa ser contornado sem violar orçamento, credenciais ou segurança.
Não diga que o código foi escrito: demonstre que o Vault trabalhou.

---
