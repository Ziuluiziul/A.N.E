# Roadmap de correção — 3.5-A a 3.5-I

A ordem proposta no prompt (§5.7) foi **confirmada em parte e alterada em dois pontos**,
com justificativa. Cada incremento entrega capacidade utilizável e cabe num commit.

## O que muda em relação à ordem sugerida

1. **3.5-A não é mais "provar e corrigir duplicação".** A prova está feita: não há
   duplicação no corpus, no parser nem no snapshot (`graph-integrity.json`). O que
   sobrou é correção de renderer e de agregação — trabalho pequeno, que desceu de
   posição.
2. **O layout da camada operacional sobe para primeiro.** Ele é a raiz única de F-04,
   F-06 e F-11, e F-04 destrói a memória espacial, que é o alicerce de todo o resto.
   Enquadrar, despoluir ou dar transparência antes de corrigi-lo é maquiar sobre um mapa
   que se move sozinho.
3. **A deliberação observável (3.5-G) barateia muito.** O contrato já existe em disco
   (F-14); o incremento passa a ser de leitura e não de desenho.

---

## 3.5-A — Separar o espaço da camada operacional

**Resolve:** F-04, F-06, F-11.

- **Escopo:** dimensionar o anel só por entidades epistêmicas; dar ao quórum um espaço
  próprio, com cada `quorum-panel` ancorando seus membros, votos e decisão; enquadrar por
  camada ativa.
- **Não escopo:** aparência dos nós operacionais, transparência, arestas.
- **Arquivos prováveis:** `frontend/src/layout.ts`, `frontend/src/atlas.ts`,
  `frontend/src/depth.ts`.
- **Riscos:** o cache de layout em `runtime/state/layout/` guarda posições por
  fingerprint; posições antigas podem mascarar a mudança. Invalidar ao alterar o layout.
- **Dependências:** nenhuma.
- **Testes:** posições dos MOCs idênticas com e sem camada operacional; posições estáveis
  sob permutação da ordem de entrada; acrescentar execução não move execuções anteriores;
  cada membro, voto e decisão pertence a exatamente um painel; zero órfão silencioso;
  `extentOf` da camada ativa não inclui a inativa.
- **Métricas — estabilidade:** deslocamento máximo de MOC = 0; de nota epistêmica = 0,
  para 1, 32, 100 e 1.000 nós operacionais.
- **Métricas — espaço de tela**, medidas antes e depois com a **mesma câmera e viewport**:
  pares de caixas projetadas que se intersectam; área projetada total de interseção;
  entidades totalmente ocluídas; distância angular entre centroides de agrupamento;
  separação de profundidade relativa à câmera; variação de parallax numa órbita
  padronizada; ocupação do viewport **contando só caixas de nós**, excluindo arestas e
  ambiente.
- **Métrica descartada:** "fração de pixels com conteúdo ≥ 0,40" constava da primeira
  versão e foi removida. Ela é frágil: linha longa, casca ou ruído aumentam a fração sem
  melhorar leitura alguma — e o valor de partida (0,217) foi medido justamente por
  contagem de pixels não-fundo, que as arestas dominam.
- **Aceite:** acrescentar 32 painéis de quórum não move nenhum MOC, e as métricas de tela
  melhoram sem apoio em distância de mundo.
- **Estimativa:** média. **Ordem de commit:** 1.

---

## 3.5-B — Câmera: distância mínima derivada do alvo

**Resolve:** F-01.

- **Escopo:** `orbit.minDistance` calculada a partir do bounding volume do alvo e do FOV,
  recalculada em `select()` e ao expandir ou recolher.
- **Não escopo:** ângulo de visada, transições, `fitToGraph`.
- **Arquivos prováveis:** `frontend/src/atlas.ts`.
- **Riscos:** mínima grande demais impede aproximar de nota pequena; manter piso absoluto.
- **Dependências:** nenhuma. Pode entrar em paralelo com 3.5-A.
- **Testes:** para cada `kind`, expandir e levar a órbita ao limite; asserir projeção
  dentro de `[-1, 1]` NDC nos dois eixos, com o dock aberto e fechado.
- **Métricas:** zero painéis projetando fora do viewport útil em zoom máximo.
- **Aceite:** o defeito de 00:76 não se reproduz pelo roteiro de F-01.
- **Estimativa:** pequena. **Ordem de commit:** 2.

---

## 3.5-C — Identidade das relações: recíproca e agregação

**Resolve:** F-02, F-03, F-12, F-13.

- **Escopo:** agrupar por par não ordenado antes de gerar vértices; chavear a agregação
  inter-MOC por par não ordenado somando as duas direções; tornar espinha e famílias
  mutuamente exclusivas; estender o filtro `F` à camada viva.
- **Não escopo:** edge bundling, orçamento global de arestas, opacidade por distância.
- **Arquivos prováveis:** `frontend/src/edges.ts`, `frontend/src/atlas.ts`,
  `frontend/src/runtimeLayer.ts`, `backend/src/vault/projection.py`.
- **Riscos:** a direção é informação legítima e não pode ser perdida na unificação;
  precisa de codificação explícita (marcador bidirecional ou deslocamento declarado).
- **Dependências:** nenhuma.
- **Testes:** zero segmentos sobre caminho já ocupado; uma agregada por par de âncoras;
  nenhuma aresta desenhada por dois grupos ao mesmo tempo.
- **Métricas:** 129 → 0 pares coincidentes; 75 → 52 agregadas.
- **Aceite:** as sete assinaturas de relação são distinguíveis em qualquer par.
- **Estimativa:** média. **Ordem de commit:** 3.

---

## 3.5-D — Materiais: desacoplar provisório de wireframe

**Resolve:** F-05.

- **Escopo:** estado canônico provisório codificado por opacidade e cabeçalho, não por
  wireframe; auditar `depthWrite`, `depthTest`, `renderOrder` e blending em conjunto.
- **Não escopo:** as cascas territoriais de `createDepthEnvironment`, que são deliberadas,
  de baixa opacidade e comunicam fronteira — **não remover**.
- **Arquivos prováveis:** `frontend/src/geometry.ts`.
- **Riscos:** perder a distinção em escala de cinza; validar por captura.
- **Dependências:** 3.5-A, para julgar a aparência já com a nuvem no lugar certo.
- **Testes:** provisório distinguível de canônico sem cor.
- **Métricas:** arestas de desenho da camada operacional; draw calls.
- **Aceite:** captura lado a lado mostrando a distinção preservada sem floresta.
- **Estimativa:** pequena. **Ordem de commit:** 4.

---

## 3.5-E — Transparência controlada e hierarquia visual

**Resolve:** a direção pedida em §4.6, mais F-10.

- **Escopo:** painel normal moderadamente transparente, focado ou expandido mais opaco,
  arestas atrás do painel atenuadas; resolver o recorte de texto.
- **Não escopo:** mudar a gramática da placa.
- **Arquivos prováveis:** `frontend/src/geometry.ts`, `frontend/src/panelTextRenderer.ts`,
  `frontend/src/panelTextLayout.ts`.
- **Dependências:** 3.5-D.
- **Testes:** nenhuma palavra cortada; estouro sempre por elipse ou remoção declarada.
- **Aceite:** capturas comparadas justificando os valores finais, conforme §4.6.
- **Estimativa:** média. **Ordem de commit:** 5.
- **Nota:** F-10 tem causa em hipótese. Executar antes o experimento descrito no achado.

---

## 3.5-F — Verdade operacional no painel de controle

**Resolve:** F-07, F-08.

- **Escopo:** a aba Trabalhadores mostra a atribuição que o orquestrador planeja, ou
  declara explicitamente que é preferência; a recusa de proponente nomeia a grandeza que
  faltou e o número (endpoints úteis contra necessários).
- **Não escopo:** mudar a regra de diversidade.
- **Arquivos prováveis:** `backend/src/vault/control/snapshot.py`,
  `backend/src/vault/work/orchestrator.py`.
- **Riscos:** planejar para exibir custa cota; usar planejamento seco, sem consumir
  ledger, como `_plan_distinct` já faz.
- **Dependências:** nenhuma.
- **Testes:** provedor e modelo exibidos coincidem com o painel montado; a mensagem de
  recusa contém a cardinalidade.
- **Aceite:** um operador lendo a aba prevê corretamente o painel que será montado.
- **Estimativa:** média. **Ordem de commit:** 6.

---

## 3.5-G — Deliberação observável

**Resolve:** F-14.

- **Escopo:** ligar `runtime/quorum/` à cena — identidade do worker, provedor e modelo,
  papel e tarefa, estado, resumo da abordagem, evidências, artefato parcial, confiança,
  objeções, votos, divergências, síntese e decisão, em painel 3D próprio. Acrescentar ao
  dado os cinco campos ausentes: estado ao longo do tempo, início, duração, tokens e
  custo, resposta às objeções.
- **Não escopo:** cadeia privada de pensamento token a token, prompts sensíveis,
  credenciais, conteúdo de ferramenta redigido.
- **Arquivos prováveis:** `backend/src/vault/operational.py`,
  `backend/src/vault/quorum/store.py`, `frontend/src/runtimeLayer.ts`,
  `frontend/src/panelBodies.ts`.
- **Dependências:** 3.5-A, que dá o espaço onde esses painéis vivem.
- **Testes:** um painel de quórum persistido rende uma trilha legível sem campo inventado.
- **Aceite:** acompanhar uma execução do início à decisão sem abrir arquivo.
- **Estimativa:** grande, mas menor do que o prompt supõe — o contrato já existe.
- **Ordem de commit:** 7.

---

## 3.5-H — Falhas estruturadas e telemetria

**Resolve:** F-09, e as lacunas de §4.13.

- **Escopo:** falha vira registro tipado — código, severidade, origem, timestamp,
  execução, worker, provedor, mensagem, contagem, primeira e última ocorrência, estado de
  resolução — agregada por `(código, worker, endpoint)`; persistir consumo por execução.
- **Não escopo:** novos provedores.
- **Arquivos prováveis:** `backend/src/vault/control/models.py`,
  `backend/src/vault/control/snapshot.py`, `frontend/src/dock.ts`.
- **Nota de crédito:** o snapshot **já** distingue indisponível de não coletado, no campo
  `operation.unavailable`, com motivo em texto para `next_run`, `calls` e `last_audit`.
  A lacuna é a UI, que renderiza "não informado" sem mostrar o motivo que o backend
  entrega. Corrigir a UI antes de mexer no contrato.
- **Aceite:** nenhuma mensagem idêntica repetida sem contador; todo "não informado" traz
  o motivo.
- **Estimativa:** média. **Ordem de commit:** 8.

---

## 3.5-I — Desempenho, regressão e fechamento

- **Escopo:** medir FPS e frame time p50/p95/p99 no laço real de animação — esta auditoria
  não conseguiu (ver ressalva em `performance-metrics.json`); confirmar que nenhum
  incremento anterior regrediu draw calls, triângulos ou o pool de 64; documentar.
- **Dependências:** todos os anteriores.
- **Métricas:** linha de base desta auditoria — 117 draw calls e 37.840 triângulos na
  visão global, 38 e 25.462 em foco.
- **Aceite:** gates zerados, medições registradas, nenhuma regressão material não
  quantificada.
- **Ordem de commit:** 9.

---

## Critérios mínimos do §7 — situação

| Critério | Situação |
|---|---|
| Baseline reproduzível | atendido — HEAD, gates, comandos e portas registrados |
| Mapa de entidades real | atendido — 362 nós, 941 arestas, 4 `kind` operacionais |
| Contagens de relações em todas as camadas | atendido — `graph-integrity.json` |
| Causa das duplicações | **confirmada** — F-02 e F-03, com ponto exato no código |
| Métricas de geometria | atendido — `visual-metrics.json` |
| Reprodução da colisão de câmera | atendido — roteiro em F-01 e captura |
| Inventário das grades e nuvens | atendido — F-05, com distinção entre casca e wireframe |
| Distinção entre configuração e execução dos workers | atendido — F-07, com os dois lados medidos |
| Estado real do quórum | atendido — `quorum-capabilities.json` |
| Contrato proposto para deliberação observável | atendido — F-14, o contrato já existe em disco |
| Ordem de dependências | atendido — este documento |
| Testes de regressão definidos | atendido — por incremento, acima |

Os doze critérios estão atendidos. A auditoria **recomenda iniciar a correção por
3.5-A**, sem nova rodada de descoberta.
