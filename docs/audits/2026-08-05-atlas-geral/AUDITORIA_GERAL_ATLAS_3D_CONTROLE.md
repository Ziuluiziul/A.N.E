# Auditoria geral — Atlas Neural-Epistêmico e painel de controle

**Data:** 2026-08-05 · **HEAD:** `1457d93` · **Branch:** `main` · **Working tree:** limpa
**Vídeo de referência:** `Gravação de tela de 2026-08-05 17-29-43.mp4` (95,76 s)
**Natureza:** auditoria forense. Nenhum comportamento funcional ou visual foi alterado.

---

## 1. Resumo executivo

Os três gates do repositório passam — `make audit`, `make test` (387 pytest + 217
vitest), `make lint`. O corpus está íntegro. E nenhum dos catorze achados desta auditoria
é capturado por eles, o que é informação sobre a cobertura dos gates.

A conclusão que mais muda o planejamento é esta: **a camada de IA não é fachada.** Há 35
painéis de quórum persistidos, com 105 atribuições de avaliador, 104 votos estruturados e
34 decisões apuradas. A cadeia `provedor → endpoint → modelo → worker → execução →
candidato → avaliação → síntese → arbitragem → decisão` existe e rodou, com proponente
fora do painel, dois provedores e três famílias de modelo. O vídeo não podia mostrar isso
porque nada disso chega à cena.

A segunda conclusão é que **a duplicação de relações não está nos dados.** O corpus tem
555 arestas dirigidas com 555 chaves distintas e zero repetição, e parser e snapshot
preservam a contagem. Toda a duplicação visual nasce em dois pontos precisos do desenho.

A terceira é que **os defeitos caros são de layout, não de estética.** A camada
operacional entra no mesmo espaço de posicionamento do corpus e, ao fazê-lo, empurra o
anel de âncoras de 87 para 148 unidades — o que move todos os MOCs e destrói a memória
espacial que sustenta a arquitetura inteira.

## 2. Veredicto geral

**PARTIAL.**

Funciona de ponta a ponta: corpus, projeção, identidade, LOD, expansão, painel de
controle, catálogo de endpoints, execução de worker, quórum e persistência.

Está defeituoso: renderização de relações, filamentos de ponte, câmera em zoom manual,
relato de falhas.

Está parcial: scheduler (travado), foco (quebra no limite), enquadramento global,
telemetria, observabilidade 3D.

Não existe: painel de deliberação na cena — embora o dado que ele precisaria já esteja
gravado.

## 3. Baseline reproduzida

| Item | Valor |
|---|---|
| Repositório | `/home/ziul/Projetos/vault-autodidata` |
| Branch · HEAD · pai | `main` · `1457d93` · `3a1ad90` |
| `git status --short` | vazio, na abertura e no fechamento |
| Submódulos | nenhum |
| Corpus | 84 notas, 672 wikilinks, 267 claims, 15 MOCs |
| Fingerprint | `e48f47915db6524005241f182cfe98a8bf108c7f6d33d47743061510193da2b3` |
| Backend | `uvicorn vault.app:app --port 8000`, já em execução (pid 14271) |
| Frontend | Vite em `127.0.0.1:5173`, já em execução (pid 11474) |
| Projeção servida | `GET /corpus/projection`, `operationalSource: quorum` |
| Cena medida | 362 nós, 941 arestas, 1600×900 |
| Node · pnpm | v24.18.1 · 11.18.0 |
| Python · uv | 3.13.5 · 0.12.0 |
| Navegador | Chromium 148.0.7778.280 (Electron 42.7.0), DPR 1 |
| WebGL | 2.0 · ANGLE (Mesa, NV137, OpenGL ES 3.2) |
| three · troika-three-text | 0.185.1 · 0.52.5 |
| TypeScript · Vitest | 6.0.3 · 4.1.10 |
| FastAPI · pydantic · networkx | 0.141.1 · 2.13.4 · 3.6.1 |
| Segredos | não lidos; `key_hint` redigido em todo entregável |

Comandos: `make audit`, `make test`, `make lint`, `uv run python tools/endpoints.py`,
`curl /api/control/snapshot`, e um teste de medição temporário em `frontend/src/`,
executado por `vitest` e **removido** ao fim.

## 4. Matriz funcional

Em `FUNCTIONAL_MATRIX.md`, com as 28 capacidades do §4.2 e os invariantes da baseline.
Resumo: **17 `FUNCIONA`, 8 `PARCIAL`, 3 `DEFEITUOSO`** — 28 linhas, todas classificadas.
Todos os invariantes declarados foram **confirmados**, inclusive o pool de 64 objetos
Troika e a ausência de sincronização em quadro parado (556 → 556 após 1,5 s).

> **Correção de 2026-08-05 (adendo).** A primeira versão desta seção dizia "15
> `FUNCIONA` … 2 sem categoria própria". Estava errada nas duas metades: a contagem é 17
> e não existe linha sem categoria. Ver `ADENDO-2026-08-05.md`.

## 5. Achados críticos

Em `FINDINGS.md`, catorze achados com evidência, reprodução, causa e aceite.

**P1:** F-01 câmera em zoom manual · F-02 recíprocas coincidentes · F-03 filamentos
duplicados por direção · F-04 MOCs deslocados pela camada viva · F-07 aba Trabalhadores
desalinhada da execução · F-08 fila travada com mensagem enganosa.

**P2:** F-05 floresta de wireframes · F-06 nuvem de IA sem ontologia espacial · F-09
falhas sem estrutura · F-10 texto recortado · F-11 nuvem operacional domina o
enquadramento · F-12 espinha e famílias coexistem · F-14 deliberação não chega à cena.

**P3:** F-13 camada viva ignora o filtro de relações.

**P0:** nenhum. Não há vazamento de credencial, corrupção de dado, ação destrutiva nem
execução em provedor diferente do declarado.

## 6. Integridade do grafo

| Camada | Contagem |
|---|---|
| Grafo do corpus | 84 nós, 555 arestas dirigidas, 672 wikilinks somados |
| Projeção | 362 nós (84 epistêmicos, 278 operacionais), 941 arestas |
| Canônicas · agregadas · operacionais | 555 · 75 · 311 |
| Chave `source\|primaryRelation\|target` | 555 distintas, **zero repetição** |
| Pares recíprocos no mesmo caminho | 129 — 80 mesma família, **49 famílias diferentes** |
| Agregadas: pares distintos · com dois tubos | 52 · **23**, sendo 10 contraditórias |
| Espinha estrutural | 223 arestas, 40,2% do total |

Não há duplicata byte a byte, semântica ou de snapshot. A recíproca A→B e B→A é legítima
no corpus e o grafo é dirigido de propósito. O defeito é que o renderer trata direção
como geometria distinta quando ela não é: as duas linhas ocupam exatamente o mesmo
caminho. Em 49 pares isso soma duas assinaturas de padrão diferentes no mesmo pixel e
destrói o canal que `edges.ts` existe para carregar.

A agregação inter-MOC é o caso oposto — ali a duplicação **é** visível como paralelismo,
porque cada tubo recebe flecha e espessura proporcionais ao próprio peso direcional.

## 7. Geometria 3D

| Medida | Só corpus | Com camada operacional |
|---|---|---|
| Extensão X · Y · Z | 174 · 156 · 41,7 | 311 · 381 · 64,1 |
| Variância Z / máx(X,Y) | 0,044 | **0,023** |
| PCA λ3/λ1 | 0,042 | **0,022** |
| σ3/σ1 | 0,204 | 0,149 |
| `extentOf` raio · profundidade | 92,3 · 21,6 | 246,8 · 32,5 |
| Nuvens com bounding sphere sobreposta | **0 de 120** | **0 de 136** |
| Extensão Z dos centroides | 34,6 | 60,8 |

Duas leituras, e elas divergem do vídeo.

**A profundidade é real, mas não organiza.** Os centroides ocupam os três eixos e a razão
Z/X entre eles é 0,21 — dentro da faixa de 15% a 25% que o próprio `layout.ts` declara
perseguir. O que denuncia a lâmina não é a extensão: é a **variância**. Apenas 2,3% da
variância total está em profundidade, e o menor eixo principal vale 2,2% do maior. A cena
é geometricamente volumétrica e perceptivamente plana.

**Não há colisão volumétrica entre nuvens no espaço de mundo.** Zero pares de bounding
spheres se tocam, nas duas configurações. Isso descarta a correção que o vídeo sugere —
espalhar as nuvens não resolveria uma colisão que não existe.

Mas **não descarta a sobreposição perceptiva**, que as próprias capturas desta auditoria
confirmam visualmente e que **não foi medida**. Distância em mundo não decide legibilidade:
falta medir interseção das caixas projetadas, taxa de oclusão, separação angular entre
agrupamentos, separação de profundidade relativa à câmera e parallax numa órbita
padronizada. Essas medições entram em 3.5-A.

> **Correção de 2026-08-05 (adendo).** A primeira versão desta seção afirmava que "a
> hipótese de sobreposição de nuvens é falsa". O enunciado excedia a evidência: ele
> generalizava um resultado de espaço de mundo para uma afirmação sobre percepção.

**O anel cresce com dado que não é corpus.** `ringRadius` recebe `projection.nodes.length`
com os 278 nós de quórum incluídos: 87 → 148,5 unidades. Medido, o MOC de Ciências da
Vida vai de `x = 79,9` a `x = 149,0`. É o achado de layout mais grave, porque o argumento
central de `layout.ts` contra a esfera force-directed era justamente que "o mapa inteiro
se reorganizando quando uma única nota mudava" não é navegável.

## 8. Renderer, LOD e materiais

O LOD funciona e é mais capaz do que o vídeo supõe: `showsBody` esconde o corpo abaixo de
4 px, então a política **age** sobre geometria, não só sobre texto. Cinco níveis, com
histerese assimétrica de 0,78, e quadro parado sem sincronização.

O que domina a cena não é a placa distante. É o wireframe: `geometry.ts:41` define
`wireframe: canonicalState === 'temporary'`, e os 278 nós de quórum são todos
`temporary`. A floresta de retângulos de 00:05–00:15 é literalmente isso.

As cascas elipsoidais em volta dos territórios são **outra coisa** —
`createDepthEnvironment` desenha por território uma casca `BackSide` a opacidade 0,055,
uma esfera wireframe a 0,045 e um anel equatorial a 0,09, todas sem raycast, atenuadas
por distância. Confundi-las com o wireframe dos nós provisórios é o erro que esta seção
existe para evitar, e é por isso que elas ficam **fora do escopo de 3.5-A** — mexer nas
duas coisas no mesmo commit tornaria impossível atribuir o efeito.

Isso é razão para não mexer agora, **não** justificativa de permanência. Intenção de
projeto não prova utilidade perceptiva: a manutenção definitiva depende de comparação
A/B posterior entre casca atual, casca reduzida, apenas anel e nenhuma casca, com
critério de ganho de orientação sem aumento relevante de ruído.

> **Correção de 2026-08-05 (adendo).** A primeira versão dizia que as cascas "não devem
> ser removidas", tratando a deliberação de projeto como se fosse evidência de utilidade.

## 9. Câmera

O foco automático está correto e foi medido: `distanciaDeLeitura` põe um MOC expandido a
~120 unidades, ocupando 34% da altura da janela.

O defeito está no zoom manual, e é aritmético. `orbit.minDistance = 12` é constante. Com
`fov = 38°`, a 12 unidades a janela mostra 14,7 × 8,3 unidades de mundo. Um MOC expandido
mede 28,16 × 15,84 — **1,92× maior em cada eixo**. Reproduzido em
`screenshots/audit-03-camera-zoom-maximo.png`: o texto ocupa a tela e é cortado nas
quatro bordas. É defeito funcional de navegação, como o vídeo classifica, e não
refinamento visual.

`near = 0,35` não participa: não há recorte de plano próximo a essa distância. O recorte
observado é de frustum, por excesso de tamanho.

## 10. Nuvens de IA

Os 278 nós operacionais têm `anchorMocId: null` e `domainId: "operacional/quorum"` —
todos. `clusterize` os joga numa chave única e `placeMembers` os espalha numa bola de
raio 46,8 a 200 unidades da origem. As "duas massas amorfas" de 00:64 são o atlas
epistêmico e esta bola.

O dado, porém, **já é diferenciado**: 35 `quorum-panel`, 105 `quorum-member`, 104
`quorum-vote`, 34 `quorum-decision`, todos declarados no contrato. A ontologia existe;
ela só não vira posição. Isso torna 3.5-A um trabalho de usar informação disponível, não
de inventar taxonomia.

## 11. Workers

Configuração e execução **discordam**, e essa é a descoberta desta seção.

O snapshot resolve os 7 workers para `google / gemini-3.5-flash-lite` — todos, por
`usaveis[0]` em `snapshot.py:191`. O painel `0b13e3a58322` persistido registra proponente
`google/gemini-3.5-flash-lite` e avaliadores `groq/qwen3.6-27b`,
`groq/llama-3.3-70b-versatile`, `nvidia/z-ai/glm-5.2`.

Quem lê a aba Trabalhadores conclui que o quórum roda com um provedor e um modelo — o
oposto do que acontece e do que a política do repositório exige. A aba não mente sobre
existir execução; ela mostra a preferência global como se fosse atribuição.

## 12. Quórum

Implementado e verificado nos artefatos: seleção de proponente, painel de três
avaliadores, proponente fora do painel, mínimo de dois provedores e duas famílias, votos
estruturados com validação de schema por voto, apuração, síntese, arbitragem,
persistência, proveniência completa e remoção de bloco de raciocínio.

Invariantes em `_assert_panel_invariants` (`orchestrator.py:1092`) recusam painel com
menos de três endpoints únicos, com o proponente entre os avaliadores, ou sem dois
provedores e duas famílias.

**Três veredictos distintos, que não devem ser confundidos:**

| Dimensão | Veredicto |
|---|---|
| `quorum_engine` — o mecanismo | **FUNCIONA** |
| `autonomous_quorum_availability` — disponibilidade corrente | **BLOQUEADO** |
| `autonomous_loop_readiness` — laço autônomo como serviço | **NÃO PRONTO** |

As 34 decisões persistidas provam que o mecanismo executa. Elas **não** provam saúde
operacional corrente, e não devem ser lidas assim.

E está **travado**. `queued: 21`, `running: 0`, `last_cycle` de sete horas antes, zero
propostas em `runtime/proposals/`. A causa é de cardinalidade: o painel exige 3 endpoints
e o proponente precisa ficar fora deles, logo são necessários 4+ endpoints úteis
simultâneos. Nas execuções registradas havia 3, e todo candidato foi recusado com
"deixaria painel sem diversidade mínima" — mensagem que descreve o teste que falhou e não
a condição do mundo. A diversidade estava correta; faltava cardinalidade.

## 13. Deliberação observável

O contrato pedido em §4.11 **já está quase todo em disco**. Cada painel guarda tarefa e
contexto com questões bloqueantes, membros com provedor/endpoint/família/papel, candidato
com detecção de bloco de raciocínio, votos com decisão, confiança, ação recomendada,
evidências por claim e questões bloqueantes, e decisão com apuração, contagem de
provedores e famílias, votos contados e descartados, falhas estruturais e síntese.

Faltam cinco campos: estado do worker ao longo do tempo, horário de início, duração,
tokens e custo, e resposta às objeções. E falta o caminho até a cena.

Isso reduz materialmente o custo de 3.5-G. Não é preciso desenhar o contrato de
deliberação; é preciso ligá-lo.

## 14. Painel de controle

Servido por dados reais. Quatro provedores com chave configurada e sufixo redigido, 193
endpoints catalogados com recorte por modalidade e sondagem, sete papéis em duas classes
com simultaneidade e ativação.

Crédito devido: `operation.unavailable` **já distingue** indisponível de não coletado, com
motivo em texto para `next_run`, `calls` e `last_audit`. A lacuna é da UI, que mostra "não
informado" sem exibir o motivo que o backend entrega — corrigir a UI antes do contrato.

Falhas, ao contrário, são lista de strings: sem código, severidade, origem, timestamp,
worker, contagem nem janela de ocorrência.

**Ressalva de fidelidade:** o snapshot vivo traz 5 entradas de falha, não as centenas que
a extensão da lista no vídeo sugere. A ausência de agregação é real; o volume observado
no vídeo não foi reproduzido nesta sessão.

## 15. Performance

Visão global: 117 draw calls, 37.840 triângulos, 14 objetos na cena. Em foco: 38 e
25.462. Pool de texto: 64 objetos, `visibleObjects ≤ allocatedSlots ≤ 64` confirmado,
56 alocados ao corpus e 8 à camada viva. Quadro parado não sincroniza.

**Não medido:** FPS e frame time p50/p95/p99. O Browser pane não compõe quadros e
`renderOnce()` mede uma passada sob demanda, não o laço de animação. Registrado como
lacuna em 3.5-I em vez de estimado.

## 16. Segurança

- Chaves nunca aparecem além de sufixo de quatro caracteres — verificado no snapshot.
- Nenhum segredo em log, snapshot ou entregável — varredura por `sk-`, `gsk_`, `AIza`,
  `nvapi`, `api_key`, `secret`, `bearer` sobre todo o diretório: nada.
- `runtime-snapshot.redacted.json` tem `key_hint` substituído por `<redigido>`.
- O arquivo real de segredos **não foi lido** nesta auditoria.
- Nenhuma captura contém credencial.

## 17. Dívidas

- Comentário em `edges.ts:228` cita "as 511 arestas"; são 555. Desatualização inócua,
  mas o número aparece em texto que explica uma decisão de desenho.
- `Z_LAYER` descreve a faixa operacional como "acima da epistêmica"; com a faixa
  epistêmica em ±26 e a dispersão do agrupamento chegando a ±39 antes do `clampZ`, a
  separação prometida não se realiza.
- Nenhum dos catorze achados é detectado pelos gates. Os testes de regressão propostos no
  roadmap são a resposta.

## 18. Plano de correção

Em `REMEDIATION_ROADMAP.md`, com 3.5-A a 3.5-I, escopo, não escopo, arquivos, riscos,
dependências, testes, métricas, aceite e ordem de commit.

A ordem sugerida no prompt foi alterada em dois pontos, com justificativa: a prova de
duplicação já está feita e desceu de posição; o layout da camada operacional subiu para
primeiro, por ser raiz única de três achados e por F-04 destruir a memória espacial que
sustenta todo o resto.

## 19. Riscos

- **Cache de layout.** `runtime/state/layout/` guarda posições por fingerprint. Mudanças
  de layout podem parecer não ter efeito até a invalidação. Vale para 3.5-A.
- **Direção como informação.** Unificar recíprocas não pode apagar a direção; ela precisa
  de codificação explícita, sob pena de trocar um defeito por perda de dado.
- **Cardinalidade de endpoints.** 3.5-F melhora o relato, não o bloqueio. Enquanto
  houver menos de 4 endpoints úteis simultâneos, a fila continua parada — isso é decisão
  de política, não defeito de código, e cabe ao mantenedor.
- **Cascas territoriais.** Há risco real de removê-las junto com o wireframe em 3.5-D.
  O não escopo está explícito por isso.

## 20. Conclusão

O sistema está mais implementado do que o vídeo permite ver e menos legível do que
precisa ser. As três coisas que o vídeo apontou como possivelmente ausentes — execução de
worker, quórum e deliberação — existem, rodaram e estão gravadas em disco com
proveniência completa. As três coisas que ele apontou como estéticas — wireframes,
profundidade e sobreposição — são, respectivamente, um acoplamento de material a estado
canônico, um problema de variância e não de extensão, e uma hipótese falsa.

O caminho mais curto para um produto legível não passa por transparência nem por
espalhar nós. Passa por devolver ao corpus o espaço que a camada operacional tomou dele.

---

### Entregáveis

`AUDITORIA_GERAL_ATLAS_3D_CONTROLE.md` · `FINDINGS.md` · `FUNCTIONAL_MATRIX.md` ·
`DEFECT_ORIGIN_MAP.md` · `REMEDIATION_ROADMAP.md` · `graph-integrity.json` ·
`visual-metrics.json` · `performance-metrics.json` · `operational-ontology.json` ·
`quorum-capabilities.json` · `runtime-snapshot.redacted.json` · `screenshots/` ·
`ADENDO-2026-08-05.md`
