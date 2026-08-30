# Registro de achados — auditoria geral de 2026-08-05

HEAD auditado `1457d93`, working tree limpa na abertura e no fechamento.
Cena viva medida em 1600×900, projeção servida por `GET /corpus/projection`
com `operationalSource: quorum` (362 nós, 941 arestas).

Severidade conforme a seção 6 do prompt. Causa marcada como **confirmada** só quando
há medição ou leitura de código que a prenda; caso contrário, **hipótese** com o
experimento que a decidiria.

---

## F-01 — `orbit.minDistance` é constante e ignora a extensão do painel

- **Severidade:** P1
- **Categoria:** câmera
- **Status:** confirmado e reproduzido
- **Evidência no vídeo:** 00:76
- **Evidência desta auditoria:** `screenshots/audit-03-camera-zoom-maximo.png`
- **Reprodução:**
  ```js
  const at = window.__atlas.atlas;
  at.focusOn('Matemática/MOC — Matemática');
  const cv = document.querySelector('canvas');
  for (let i = 0; i < 90; i += 1)
    cv.dispatchEvent(new WheelEvent('wheel', { deltaY: -120, bubbles: true, cancelable: true }));
  ```
- **Esperado:** o painel focado cabe no viewport útil em qualquer nível de zoom.
- **Atual:** o texto ocupa a tela inteira e é recortado nas quatro bordas.
- **Impacto:** navegação inutilizável no limite de aproximação; é o defeito visual mais
  agressivo do produto.
- **Causa raiz — confirmada:** `frontend/src/atlas.ts:219` fixa `orbit.minDistance = 12`.
  Com `fov = 38°` (`depth.ts:35`), a 12 unidades a janela mostra 14,7 × 8,3 unidades de
  mundo. Um MOC mede 4,00 × 2,25 semânticos × `PANEL_WORLD_SCALE = 3.2` = 12,8 × 7,2, e
  `EXPANSAO = 2.2` (`panelBodies.ts:51`) leva a **28,16 × 15,84**. O painel é 1,92× mais
  largo e 1,92× mais alto que a janela disponível.
- **Não é a causa:** `near = 0.35` (`depth.ts:53`) não recorta a esta distância, e
  `aproximarDe()` enquadra corretamente — `distanciaDeLeitura` põe o mesmo painel a
  ~120 unidades. O defeito está no zoom manual, não no foco automático.
- **Correção proposta:** derivar a distância mínima do bounding volume do alvo em vez de
  usar constante — `minDistance = max(12, alcanceEfetivo * focal / alturaJanela)`,
  recalculada em `select()` e ao expandir/recolher.
- **Dependências:** nenhuma.
- **Teste de regressão:** para cada `kind`, expandir e levar a órbita ao limite; asserir
  que a projeção do painel cabe em `[-1, 1]` NDC nos dois eixos.
- **Aceite:** nenhum painel expandido projeta fora do viewport útil em zoom máximo.

---

## F-02 — 129 pares de arestas recíprocas desenhados sobre o mesmo caminho

- **Severidade:** P1
- **Categoria:** renderer
- **Status:** confirmado por contagem
- **Evidência no vídeo:** 00:16–00:34, 00:67
- **Reprodução:** `graph-integrity.json`, bloco `duplicacao`.
- **Esperado:** cada relação declarada tem assinatura visual legível.
- **Atual:** 129 dos 555 pares canônicos têm aresta de ida **e** de volta. Como
  `buildRelationLines` (`edges.ts:167`) busca as posições por identidade, A→B e B→A
  produzem exatamente os mesmos dois extremos: as linhas são **coincidentes**, não
  paralelas.
  - 80 pares na mesma família: sobredesenho puro — opacidade dobrada e disputa de
    profundidade.
  - **49 pares em famílias diferentes**: as duas assinaturas se somam no mesmo pixel.
    `contrasts` (linha dupla) sobre `extends` (contínua com seta vazada),
    `operational` (traço-ponto) sobre `prerequisite` (contínua com seta sólida). O
    canal que o módulo existe para carregar — tipo pela forma, não pela cor — fica
    ilegível em 23% das relações.
- **Impacto:** a codificação de relação por padrão é o pilar do desenho de arestas e não
  sobrevive à recíproca.
- **Causa raiz — confirmada:** não há defeito de dado. O corpus tem 555 arestas dirigidas
  com 555 chaves `source|primaryRelation|target` distintas e **zero repetição**; parser e
  snapshot preservam a contagem. O grafo é dirigido e a recíproca é legítima. O defeito é
  que o renderer trata direção como se fosse geometria distinta, e não é.
- **Correção proposta:** agrupar por par não ordenado antes de gerar vértices; um par com
  duas relações vira um traçado com deslocamento perpendicular explícito (como
  `contrasts` já faz) ou um marcador bidirecional, nunca duas linhas sobrepostas.
- **Teste de regressão:** asserir que nenhum par não ordenado gera dois conjuntos de
  vértices colineares coincidentes.
- **Aceite:** zero segmentos desenhados sobre caminho já ocupado.

---

## F-03 — Filamentos agregados duplicados por direção entre 23 pares de MOC

- **Severidade:** P1
- **Categoria:** contrato/backend
- **Status:** confirmado
- **Evidência no vídeo:** 00:90–00:96 — "vários segmentos paralelos de longa extensão".
- **Esperado:** uma ponte por par de territórios.
- **Atual:** 75 arestas agregadas para **52 pares distintos**; 23 pares recebem **dois
  tubos**. Como o arco é `-5 - 4 × (peso / pesoMáximo)` (`edges.ts:334`) e o raio é
  `0.12 + 0.5 × √(peso / pesoMáximo)`, os dois tubos do mesmo par têm flecha e espessura
  diferentes — e aí sim aparecem **visivelmente paralelos**, ao contrário de F-02.
- **Impacto:** a ponte interdisciplinar, que é a leitura mais valiosa da visão global,
  é a que mais mente sobre a própria cardinalidade.
- **Agravante — semântico:** em **10 dos 23 pares** os dois tubos declaram relações
  dominantes contraditórias. Exemplo medido:
  `Computação → Matemática primary=prerequisite (peso 9)` e
  `Matemática → Computação primary=contrasts (peso 5)`. A mesma ponte conta duas
  histórias, e a legenda não tem como desempatar.
- **Causa raiz — confirmada:** `backend/src/vault/projection.py:401` usa
  `chave = (origem, destino)` — tupla **ordenada**. Um par de MOCs com tráfego nos dois
  sentidos gera duas entradas no dicionário `agregados`.
- **Correção proposta:** chavear por par não ordenado (`tuple(sorted(...))`), somar os
  pesos das duas direções e escolher uma única relação dominante sobre o balde unificado.
  Se a direção importar, declará-la em campo próprio — não em duas arestas.
- **Teste de regressão:** `len(agregadas) == len({frozenset((e.source, e.target))})`.
- **Aceite:** uma aresta agregada por par de âncoras, com relação dominante única.

---

## F-04 — A camada operacional desloca todos os MOCs

- **Severidade:** P1
- **Categoria:** layout
- **Status:** confirmado por medição comparada
- **Evidência:** `visual-metrics.json`, campo `anel_de_ancoras`.
- **Esperado:** `layout.ts:105-115` promete explicitamente que "dentro do mesmo balde de
  32 entidades o anel não muda", para que nenhum MOC se mova fora de mudança estrutural.
- **Atual:** `ringRadius` recebe `projection.nodes.length`, que **inclui os 278 nós de
  quórum**. Sem a camada operacional o anel tem raio 87; com ela, 148,5. Medido no mesmo
  corpus: o MOC de Ciências da Vida sai de `x = 79,9` para `x = 149,0`.
- **Impacto:** a memória espacial — justificativa central de toda a arquitetura de
  âncoras — é destruída por dado que não é do corpus. A cada 32 painéis de quórum
  acumulados, o atlas inteiro se reescala.
- **Causa raiz — confirmada:** `layout.ts:278`,
  `placeAnchors(mocs, projection.nodes.length, config)`.
- **Correção proposta:** dimensionar o anel só pelas entidades epistêmicas
  (`nodes.filter(n => n.layer === 'epistemic').length`).
- **Teste de regressão:** posições dos MOCs idênticas com e sem camada operacional.
- **Aceite:** deslocamento zero de MOC ao acrescentar ou remover painéis de quórum.

---

## F-05 — A "floresta de wireframes" são os 278 nós de quórum, por estado canônico

- **Severidade:** P2
- **Categoria:** material
- **Status:** confirmado
- **Evidência no vídeo:** 00:05–00:15, 00:64
- **Evidência desta auditoria:** `screenshots/audit-01-global.png` e
  `audit-04-global-fit.png` — a massa reticulada no alto à direita.
- **Pergunta obrigatória do prompt (3.1), respondida:** não são bounding boxes, não são
  geometria de depuração e não são resíduo de instanciamento. São **as próprias placas**,
  renderizadas em wireframe literal.
- **Causa raiz — confirmada:** `geometry.ts:41` define
  `wireframe: canonicalState === 'temporary'`, e os 278 nós operacionais têm
  `canonicalState: "temporary"` (medido: 278 de 278). Somam-se `transparent: true` e
  `opacity: 0.62`, porque `temporary` está em `NAO_SOLIDOS` (`geometry.ts:18`).
- **Distinção importante:** as cascas elipsoidais visíveis em volta dos territórios
  epistêmicos são **outra coisa** e são deliberadas — `createDepthEnvironment`
  (`depth.ts:152`) desenha por território uma casca `BackSide` a opacidade 0,055, uma
  esfera wireframe a 0,045 e um anel equatorial a 0,09, todas sem raycast. Elas comunicam
  fronteira de território, custam três objetos por domínio e **não** são a poluição
  reclamada. Não devem ser removidas junto.
- **Correção proposta:** desacoplar "provisório" de "wireframe". Wireframe em 278 objetos
  multiplica arestas de desenho e é o que produz a leitura de floresta; a provisoriedade
  já está codificada pela opacidade e pelo cabeçalho escrito.
- **Aceite:** o estado provisório continua distinguível em escala de cinza sem wireframe.

---

## F-06 — A nuvem de IA é um único agrupamento sem ontologia espacial

- **Severidade:** P2
- **Categoria:** layout
- **Status:** confirmado
- **Evidência no vídeo:** 00:64 — "duas massas amorfas quase indistinguíveis".
- **Atual:** os 278 nós operacionais têm `anchorMocId: null` e `domainId:
  "operacional/quorum"` — **todos**. `clusterize` (`layout.ts:88`) os joga numa única
  chave `domínio:operacional/quorum`, e `placeMembers` os espalha numa bola de raio 46,8
  centrada em (−54,7, 192,8, 0,2). As duas massas do vídeo são: o atlas epistêmico e esta
  bola.
- **O dado já é diferenciado; a cena é que não usa:** o contrato declara quatro `kind`
  distintos e a projeção os entrega separados — 35 `quorum-panel`, 105 `quorum-member`,
  104 `quorum-vote`, 34 `quorum-decision`. Nada disso vira posição.
- **Agravante:** `Z_LAYER` (`sizing.ts`) reserva 4,8–5,6 para os kinds de quórum,
  descrito como "faixa própria, acima da epistêmica". A faixa epistêmica vai a ±26 e o
  termo `cosPolar × raio × 0.45` chega a ±39 antes do `clampZ`. A separação de camadas
  prometida por `Z_LAYER` é engolida pela dispersão do próprio agrupamento.
- **Correção proposta:** agrupar por painel, não por domínio: cada `quorum-panel` vira
  âncora local dos seus membros, votos e decisão. Isso dá ao 3D exatamente a ontologia
  que o dado já tem.
- **Aceite:** painel, membro, voto e decisão distinguíveis por posição, sem legenda.

---

## F-07 — A aba Trabalhadores não mostra o que a execução usa

- **Severidade:** P1
- **Categoria:** UI/observabilidade
- **Status:** confirmado
- **Evidência no vídeo:** 00:49–00:52
- **Atual:** os 7 workers do snapshot resolvem **todos** para
  `google / gemini-3.5-flash-lite`, `resolved_by: "auto"`,
  detalhe "resolvido pela política canônica".
- **O que a execução real faz:** o painel `0b13e3a58322` persistido em `runtime/quorum/`
  registra proponente `google/gemini-3.5-flash-lite` e avaliadores
  `groq/qwen3.6-27b`, `groq/llama-3.3-70b-versatile`, `nvidia/z-ai/glm-5.2`.
- **Impacto:** o painel exibe uma resolução de configuração que **não é** o plano de
  execução. Quem lê a aba conclui que o quórum roda com um só provedor e um só modelo —
  o oposto do que o orquestrador faz e do que a política do repositório exige.
- **Causa raiz — confirmada:** `control/snapshot.py:191` devolve `usaveis[0]` para todo
  worker; é o primeiro endpoint da ordem de preferência global, sem passar pela restrição
  de diversidade que `orchestrator._has_panel_diversity` aplica na hora de planejar.
- **Correção proposta:** ou a aba mostra a atribuição planejada pelo orquestrador, ou
  declara explicitamente que é preferência e não atribuição. Hoje ela não faz nem um nem
  outro.
- **Aceite:** provedor e modelo exibidos coincidem com os do painel efetivamente montado.

---

## F-08 — A fila está parada e a mensagem de falha aponta para a causa errada

- **Severidade:** P1
- **Categoria:** scheduler/quórum
- **Status:** confirmado
- **Evidência no vídeo:** 00:37–00:43 — repetição de "deixaria painel sem diversidade
  mínima".
- **Atual (snapshot vivo):** `queued: 21`, `running: 0`, `active_workers: 7`,
  `capacity: 15`, `last_cycle: 2026-08-05T13:13:05Z` — mais de sete horas antes desta
  auditoria. Zero propostas em `runtime/proposals/`.
- **Causa raiz — confirmada:** `_select_proposer` (`orchestrator.py:783`) remove o
  candidato do conjunto e exige que o **restante** ainda forme painel diverso.
  `_has_panel_diversity` (`orchestrator.py:1084`) exige `len(profiles) >= 3` mais dois
  provedores mais duas famílias. Logo o sistema precisa de **4+ endpoints úteis
  simultâneos**: três para o painel e um para o proponente, que não pode avaliar a
  própria proposta. Nas execuções registradas o conjunto útil tinha três
  (`groq/llama-3.3-70b`, `groq/llama-3.1-8b`, `nvidia/z-ai/glm-5.2`), e todo candidato foi
  recusado.
- **Por que a mensagem engana:** "deixaria painel sem diversidade mínima" descreve o teste
  que falhou, não a condição do mundo. A condição é "há 3 endpoints úteis e o desenho
  exige 4". Um operador lendo o painel tenta corrigir diversidade, que já está correta.
- **Correção proposta:** distinguir no relato "pool insuficiente em cardinalidade" de
  "pool insuficiente em diversidade", e informar quantos endpoints úteis existem contra
  quantos são necessários.
- **Aceite:** a falha nomeia a grandeza que faltou e o número que faltou.

---

## F-09 — Falhas entregues como texto puro, sem estrutura

- **Severidade:** P2
- **Categoria:** observabilidade
- **Status:** confirmado
- **Evidência no vídeo:** 00:37–00:43
- **Atual:** `operation.failures` é uma lista de **strings**. Não há código, severidade,
  origem, timestamp, worker, provedor, contagem, primeira nem última ocorrência. Cada
  entrada concatena vários motivos com `;`, e o mesmo motivo se repete três vezes dentro
  de uma entrada e entre entradas.
- **Ressalva de fidelidade:** o snapshot vivo traz **5** entradas, não as centenas que a
  extensão da lista no vídeo sugere. A ausência de agregação é real; o volume observado
  no vídeo não foi reproduzido nesta sessão e pode depender do estado daquele momento.
- **Correção proposta:** falha vira registro tipado, agregado por `(código, worker,
  endpoint)`, com contagem e janela de ocorrência.
- **Aceite:** nenhuma mensagem idêntica repetida sem contador.

---

## F-10 — Texto recortado pela borda da placa

- **Severidade:** P2
- **Categoria:** renderer/LOD
- **Status:** confirmado
- **Evidência desta auditoria:** `screenshots/audit-02-global-nativo.png` — "MAPA DE CO",
  "MOC — Segi", "Organiza o c", "Aponta para" cortados no meio da palavra; blocos
  distintos em `audit-04-global-fit.png`.
- **Atual:** em nível `legible` a caixa de texto extravasa a largura da placa e é cortada
  sem reticências.
- **Causa — hipótese:** `panelTextLayout`/`panelTextRenderer` calculam `maxWidth` a partir
  da extensão semântica, mas o corte observado ocorre em placas não expandidas de MOC,
  cujo título é longo. `syncByReason` registra `overflow-title-ellipsized: 0` e
  `overflow-secondary-removed: 1` — ou seja, a política de estouro **não disparou** para
  os casos recortados.
- **Experimento que decide:** instrumentar `panelTextRenderer` para registrar, por
  entidade, `larguraMedida` contra `larguraDisponível` no quadro da captura, e comparar
  com o `renderOrder` da placa. Se `larguraMedida > larguraDisponível` sem elipse, o
  defeito está no gatilho de estouro; se não, está na projeção da caixa.
- **Aceite:** nenhuma palavra cortada; estouro sempre resolvido por elipse ou remoção
  declarada.

---

## F-11 — A nuvem operacional domina o enquadramento global

- **Severidade:** P2
- **Categoria:** câmera/layout
- **Status:** confirmado
- **Evidência:** `screenshots/audit-04-global-fit.png`, tirada logo após `fitToGraph()`.
- **Atual:** `extentOf` passa de raio 92,3 (só corpus) para **246,8** com a camada
  operacional, porque a bola de quórum fica a ~200 unidades da origem. A câmera recua
  2,7× e o corpus — o objeto de interesse — encolhe proporcionalmente. Medição em pixels
  do quadro enquadrado: apenas **21,7%** dos pixels têm conteúdo, e a caixa ocupada toca
  as quatro bordas porque as arestas longas a esticam, com painéis recortados à direita.
- **Impacto:** a visão global deixou de enquadrar o corpus e passou a enquadrar corpus
  mais anexo operacional, sem que ninguém tenha pedido os dois na mesma escala.
- **Correção proposta:** enquadrar por camada ativa; a camada operacional entra no
  enquadramento só quando é ela a camada em foco.
- **Aceite:** na visão global do corpus, o corpus preenche a moldura útil.

---

## F-12 — Espinha e famílias podem ser desenhadas ao mesmo tempo

- **Severidade:** P2
- **Categoria:** renderer
- **Status:** confirmado por leitura de código
- **Evidência no vídeo:** 00:67 — "feixes densos... a conectividade domina a percepção".
- **Atual:** `espinha.visible = regime === 'intermediaria'` (`atlas.ts:737`) e
  `grupoFamilias.visible` alternado pela tecla `F` (`atlas.ts:859`) são **independentes**.
  Sem seleção, na banda intermediária, com `F` ligado, a cena desenha a espinha (223
  arestas contínuas a opacidade 0,22) **e** as famílias (555 arestas com padrão) — 223
  arestas duas vezes, com assinaturas diferentes.
- **Correção proposta:** tornar os dois regimes mutuamente exclusivos, ou subtrair da
  espinha as arestas que as famílias já desenham.
- **Aceite:** nenhuma aresta desenhada por dois grupos simultaneamente.

---

## F-13 — A camada viva ignora o filtro de relações

- **Severidade:** P3
- **Categoria:** renderer
- **Status:** confirmado por leitura de código
- **Atual:** `runtimeLayer.update` (`runtimeLayer.ts:361`) chama `buildRelationLines` e
  adiciona os resultados ao próprio grupo. A tecla `F` alterna apenas `grupoFamilias`, de
  modo que as relações da camada viva permanecem desenhadas com padrão cheio
  independentemente do filtro.
- **Aceite:** o filtro de relações vale para todas as camadas.

---

## Hipóteses do vídeo que esta auditoria **refuta**

Registradas porque a ordem de correção proposta no prompt depende delas.

- **"Sobreposição maciça de volumes das nuvens" (§4.4).** Refutada **apenas em espaço de
  mundo**: das 136 combinações de nuvens, **zero** têm bounding spheres sobrepostas, antes
  e depois da camada operacional. Isso descarta a correção sugerida — espalhar nuvens não
  resolve colisão inexistente. Não descarta a sobreposição **perceptiva**, visível nas
  capturas e ainda **não medida**: interseção de caixas projetadas, oclusão, separação
  angular, separação de profundidade e parallax entram em 3.5-A. *(Enunciado corrigido no
  adendo de 2026-08-05; a primeira versão dizia "falso" sem essa qualificação.)*
- **"Links duplicados no corpus, no parser ou no snapshot" (§3.2).** Falso nessas três
  camadas: 555 arestas, 555 chaves dirigidas distintas, zero repetição. A duplicação
  visual é inteiramente do renderer (F-02) e da agregação dirigida (F-03).
- **"Workers e quórum podem ser apenas configuração" (§3.4, §4.10).** Falso quanto ao
  **mecanismo**. Há 35 painéis, 34 decisões e 105 atribuições de membro persistidos, com
  proponente fora do painel, dois provedores, três famílias, votos com schema validado,
  apuração e síntese. A cadeia `provedor → endpoint → modelo → worker → execução →
  candidato → avaliação → síntese → arbitragem → decisão` **existe e rodou**.
  Isso **não** significa saúde operacional corrente: `quorum_engine` FUNCIONA,
  `autonomous_quorum_availability` BLOQUEADO, `autonomous_loop_readiness` NÃO PRONTO —
  ver F-08. O que também não existe é a leitura disso na cena (F-14, abaixo).
- **"O LOD trata só o texto" (§3.5).** Impreciso. `showsBody` esconde o corpo abaixo de
  4 px, então o LOD **age** sobre a geometria. O que domina a cena não é a placa em nível
  distante: é o wireframe dos 278 nós provisórios (F-05) somado ao orçamento de arestas.

---

## F-14 — A deliberação existe em disco e não chega à cena

- **Severidade:** P2
- **Categoria:** observabilidade
- **Status:** confirmado
- **Consequência de projeto — a mais importante desta auditoria:** o contrato de
  deliberação observável que o prompt pede em §4.11 **já está quase todo persistido**.
  Cada painel em `runtime/quorum/<id>/` guarda:
  `task.json` (tarefa, prompt, contexto, `blocking_issues`), `members.json` (provedor,
  endpoint, família, papel por avaliador), `proposal` (candidato, com detecção e remoção
  de bloco de raciocínio), `votes/*.json` (decisão, confiança, ação recomendada,
  evidências por claim, questões bloqueantes, `schema_valid`), `decision.json`
  (resultado, apuração, contagem de provedores e famílias, votos contados e descartados,
  falhas estruturais, síntese) e `events.jsonl`.
- **O que falta no dado:** estado do worker ao longo do tempo, horário de início,
  duração, tokens e custo, resumo da abordagem, e resposta às objeções.
- **O que falta no caminho:** os quatro `kind` de quórum chegam à cena como nós sem
  posição diferenciada (F-06) e sem painel de leitura próprio.
- **Efeito no planejamento:** o incremento 3.5-G do prompt é substancialmente mais barato
  do que ele assume. Não é preciso desenhar o contrato de deliberação; é preciso
  **ligar** o que já é gravado a uma leitura na cena, e acrescentar cinco campos.
