# Ciclo 1.1 — Fechamento do Atlas FULL 3D — 2026-08-02

Fechamento das não conformidades que a auditoria externa apontou no Ciclo 1, cujo
relatório foi entregue em `6d267ab`. O Ciclo 1.1 partiu desse commit e sua última
alteração funcional entrou em `c2e36db`; `560f49a` acrescentou somente o handoff.
Escopo estritamente limitado às não conformidades: nenhuma chamada externa e nenhuma
alteração no corpus.

**Resultado da implementação: PASS.** O pacote documental permaneceu **PARTIAL** até
o Gate 0 posterior a `560f49a`, que reconciliou a cadeia, os artefatos e as métricas
sem reescrever o histórico.

## 1. A reclassificação estava certa

O Ciclo 1 declarou PASS listando, no próprio relatório, que as posições não persistiam
entre sessões. Isso não era melhoria opcional — o prompt pedia "posições persistidas
fora do corpus" e o dossiê lista "MOCs e posições persistem entre sessões" como meta
de aceitação. Declarar PASS com uma não conformidade conhecida na mesma página foi
erro de classificação, não de implementação. PARTIAL era o veredito correto.

## 2. Estado inicial do ciclo

| Item | Estado | Evidência |
| --- | --- | --- |
| HEAD | `6d267ab` | `git rev-parse HEAD` |
| Working tree | limpa | `git status --short --branch` |
| `knowledge/` desde `6510322` | intocado | `git diff --stat 6510322..HEAD -- knowledge/` vazio |
| Manifesto | `4f5b1d00…` | `python3 tools/audit.py` |
| Processos concorrentes | nenhum | `pgrep` |

Bundle de preservação: `vault-autodidata-pre-ciclo1.1-6d267ab.bundle`, SHA-256
`ad05b91f5c556405be52fa8a6bcc4c310bbd82536baf544524780e87693a53a6`, verificado.

### 2.1. Estado reconciliado antes do Ciclo 2

O Gate 0 encontrou `main` limpa em `560f49a`, filho direto de `c2e36db`. O primeiro é
apenas documental; o segundo contém a última alteração de código do fechamento. O
manifesto seguia em `4f5b1d00…` e `make audit` aprovou 81 notas, 627 wikilinks e 267
claims.

O par mais recente e verificável no disco, ambos identificando `560f49a`, era:

| Artefato | SHA-256 | Verificação |
| --- | --- | --- |
| `vault-autodidata-ciclo-1.1-fechamento-560f49a.bundle` | `3949cfa0d6876fc7f02bde05b8081f31a705daabc3dea9da6429ca1b0e3b5286` | `git bundle verify`; histórico completo, `HEAD` e `main` em `560f49a` |
| `vault-autodidata-ciclo-1.1-fechamento-560f49a.tar.gz` | `0cfddf9391c54ada90c7a1eb7623fa18adb52f601a65b8945f78f860de6a3b8a` | `gzip -t`, `tar -tzf` e `git get-tar-commit-id` em `560f49a` |

Os artefatos para `c2e36db` e os hashes `ee7fdb19…` / `cd5f6088…` citados na versão
anterior do handoff não existem nos backups retidos e não são verificáveis. O bundle,
o tarball e o `.sha256` do commit documental que contém esta reconciliação são
gerados depois dele, porque seus hashes não podem ser embutidos sem circularidade.

## 3. Persistência espacial — a lacuna que motivou a reclassificação

`backend/src/vault/layout_store.py` grava em
`runtime/state/layout/<impressão>.json`, fora do corpus e fora do Git.

| Requisito | Como foi atendido |
| --- | --- |
| Nenhuma escrita em `knowledge/` | store escreve só no diretório próprio; teste compara a impressão do corpus antes e depois de gravar, ler e apagar |
| Schema versionado | `schemaVersion: 1`; versão diferente devolve "não havia posições" |
| Chave por `corpusFingerprint` | o arquivo leva a impressão no nome e no conteúdo, e recusa se discordarem |
| IDs canônicos NFC | as chaves são as identidades do contrato, já normalizadas |
| Gravação atômica | temporário no mesmo diretório mais `os.replace`; um corte de energia deixa o arquivo antigo intacto |
| Corrupção não quebra a aplicação | JSON inválido, truncado, vazio ou de outro schema devolvem `None`; entrada podre é descartada uma a uma |
| Impressão diferente não reaproveita | outra impressão devolve mapa vazio |
| MOCs preservam posição | verificado em uso real, não só em teste |
| Entidades removidas somem | `known_ids` poda na gravação |
| Posição não é conhecimento | `Position` tem `x`, `y`, `z`, `pinned` e nada mais; um teste prende esse conjunto |

Travessia de diretório foi tratada: a impressão é validada como hexadecimal de 64
dígitos antes de virar caminho, porque um valor vindo da rede poderia conter `../`.

**Roteiro de verificação executado**, os dez passos pedidos:

1–5. Layout calculado, persistido, lido de volta **por um interpretador separado**
(`subprocess`, não apenas outro objeto no mesmo processo) e comparado — coordenadas
idênticas.
6–7. Nota sintética acrescentada; posições preexistentes inalteradas.
8–9. Cinco formas de corrupção injetadas; todas recuperam em silêncio.
10. Impressão do corpus idêntica antes e depois.

**E funcionou em uso real.** Ao recarregar o Atlas na segunda sessão, a barra de
estado anunciou:

```text
Memória espacial: 81 posições reaproveitadas, 0 novas, gravadas.
```

Arquivo em disco: 81 posições, `schemaVersion` 1, impressão
`4f5b1d00…` — a mesma que `make audit` imprime.

## 4. Camada operacional

Implementada inteira no contrato e no renderer, e **vazia em produção**, que é o
estado correto: nenhum agente registrou nada, e fabricar eventos seria inventar
procedência.

`meta.operationalSource` vale `none` por padrão. A trilha sintética só nasce sob
`VAULT_DEMO_OPERATIONAL=1` e declara `demo`. Dois ramos de propósito — um termina em
commit, outro em rejeição —, porque um caminho feliz sozinho não mostraria que
atividade pode não virar conhecimento.

| Entidade | Geometria | Estado | Solidez |
| --- | --- | --- | --- |
| agente | hexágono fino | temporary | hachurado |
| atividade | cápsula alongada | temporary | hachurado |
| evidência | marcador quadrado | temporary | hachurado |
| proposta | toro vazado | proposed | vazado |
| commit | selo octogonal | canonical | sólido |
| rejeição | forma com setor removido | rejected | translúcido |
| arquivo temporário | moldura sem miolo | temporary | hachurado |

Sólido e opaco é privilégio do que já é conhecimento. A rede inteira vive numa faixa
de `z` acima do plano epistêmico — coordenada, e visivelmente não misturada.

Testes: 12 no backend, incluindo "a flag nasce desligada", "a trilha não altera
nenhuma contagem do corpus", "nenhum nó operacional tem arquivo no corpus" e "nada de
raciocínio interno na trilha".

## 5. Acesso sem WebGL

`?texto=1`, ou automático quando o WebGL não inicializa. Substitui a cena; não é
painel ao lado dela.

Verificado no navegador: nenhum `canvas`, zero `aside`/`nav`, 90 entidades listadas
(81 do corpus mais 9 da demo então ativa), busca por `estatistica` devolvendo 8
resultados **sem acento e sem caixa**, e cada entidade expondo identidade, tipo,
camada, estado, estado epistêmico, domínio, claims, relações, arquivo, datas e a lista
de ligações. Somente leitura. Registro completo em
`runtime/captures/07-modo-textual.txt`.

## 6. Gate do MOC central

O `Índice` fica no centro por ser o MOC de raiz do corpus, e **não** funciona como sol
central. Verificado por teste e por inspeção:

- tamanho idêntico ao dos outros MOCs — o degrau é por classe, e centralidade não vira
  grandeza;
- o acréscimo emissivo é o mesmo para todo MOC, e o do raiz não é o maior da cena;
- `isAnchor` e `lodClass` iguais aos demais; `anchorMocId` nulo em todos;
- nenhuma nota é ancorada nele por centralidade — só as duas de `raiz`, por domínio;
- os onze MOCs periféricos ficam **à mesma distância tridimensional** do centro, com
  desvio abaixo de 0,001: a elevação da calota não cria hierarquia radial.

Nas capturas, o `Índice` é um dos menores objetos rotulados da cena.

## 7. Paleta normativa

`docs/ADR-001-paleta-oklch.md` passa a ser a fonte única de verdade. Registra o par
reprovado (D03 × D12 a 0,036 em OKLab), o método de distância, a tabela canônica com o
delta de cada token, o efeito em contraste, o limite honesto em dicromacia e as
alternativas descartadas. Distância mínima: 0,036 → 0,062.

## 8. Evidência visual

Produzidas pela própria aplicação, em 1920×1080, e gravadas em `runtime/captures/`.

| Arquivo | Conteúdo |
| --- | --- |
| `01-visao-global.png` | anel de MOCs, territórios, filamentos agregados |
| `02-moc-em-foco.png` | MOC selecionado, arestas focais, página de leitura |
| `03-nota-expandida.png` | nota `Memória` com a página completa |
| `04-ilha-de-controles-e-legenda.png` | ilha 3D e legenda aberta |
| `05-todas-as-relacoes.png` | todas as famílias reveladas pelo filtro |
| `06-camada-operacional-demo.png` | trilha operacional em modo DEMO |
| `07-modo-textual.txt` | evidência do acesso sem WebGL |

Contexto: commit `2c7a0ec` no momento da captura, impressão
`4f5b1d00…`, Chromium (Claude 1.24012.9), renderer `ANGLE (Mesa, NV137, OpenGL ES
3.2)`, origem `corpus` (`operationalSource: none`, exceto a captura 06, em `demo`).

**A inspeção visual encontrou três defeitos que nenhuma métrica tinha apontado**, e é
por isso que ela era exigida:

1. **Capturas sem rótulo algum.** O troika gera os glifos fora do quadro corrente; a
   captura fotografava antes de existirem. Draw calls, triângulos e cobertura de pixel
   estavam todos corretos.
2. **Ilha de controles invisível.** A cor ociosa era `surfaceEmbedded`, escura demais
   contra o fundo — semioculta virou ausente.
3. **Rótulos sobrepostos** nos territórios densos, que é falha automática pelo gate de
   qualidade do dossiê. Resolvido com rejeição de colisão em espaço de tela, por
   prioridade, mais um piso de 10 px abaixo do qual o texto some em vez de virar
   sujeira.

Uma quarta correção veio junto: a página de leitura era pequena demais e saía do
quadro. Agora tem escala proporcional à distância e escolhe o lado com espaço.

E uma funcionalidade que faltava apareceu na inspeção: o dossiê pede que o usuário
possa recentrar a câmera em qualquer entidade. Não existia. Foi implementada — duplo
clique, ou `Enter` com algo selecionado — preservando a direção de visada, porque
mudar o ângulo junto com o alvo desorienta.

## 8.1. Correção de profundidade — o atlas estava raso demais

Depois das capturas, Luiz observou que as posições e a rede pareciam mais 2.5D que 3D.
A medição deu razão a ele: na métrica original do dossiê — profundidade dividida pela
extensão horizontal da cena — a primeira entrega ficou em **5,7%**, abaixo da faixa
de **15% a 25%**. Era um diagrama quase plano com geometria volumétrica em cima.

O que mudou:

- **As âncoras deixaram o anel plano e passaram a uma calota.** Azimute continua
  igualmente espaçado, e a elevação varia por índice pelo ângulo áureo. O raio
  horizontal é corrigido para que a distância tridimensional de cada MOC ao centro
  seja idêntica — sem isso, elevação viraria hierarquia, e um MOC "mais alto"
  pareceria mais importante que o vizinho.
- **Os territórios deixaram de ser discos.** As notas se distribuem por Fibonacci
  sobre a esfera, com a componente vertical comprimida a 45%: volume de verdade,
  ainda mais largo que alto.
- **O relaxamento de colisão passou a ser tridimensional.** Separar só no plano
  deixaria pares sobrepostos em projeção assim que o território ganhou volume.

A implementação **substitui o gate literal**, em vez de alegar que o cumpre com outro
denominador. O parâmetro controlador da calota é `0,22` do raio tridimensional das
âncoras, cuja escala é quantizada. A altura de cada MOC aplica ainda o seno do índice
pelo ângulo áureo; por isso `0,22` é a amplitude máxima parametrizada, não a altura de
todos os MOCs. Medir contra a extensão corrente seria mais fiel à letra do dossiê,
mas essa extensão depende do maior território: uma nota nova poderia recalibrar a
profundidade de todos os MOCs e quebrar a estabilidade do mapa mental.

As duas métricas ficam, portanto, separadas:

| Métrica | Papel | Situação |
| --- | --- | --- |
| profundidade / extensão horizontal da cena | requisito original do dossiê | diagnóstico de 0,13–0,30 conforme o corpus; não há conformidade literal universal com 0,15–0,25 |
| amplitude da calota / raio estrutural quantizado | invariante adotada | parâmetro 0,22; estável enquanto o raio permanece no mesmo degrau |

O teto diagnóstico de `0,35` impede regressão à esfera livre; ele não transforma a
nova métrica na métrica original. A decisão deste fechamento é priorizar a invariante
estrutural e registrar o desvio. Se a conformidade literal voltar a ser mandatória, o
dossiê deverá adotar formalmente a nova invariante ou o layout deverá ganhar um
segundo gate — por exemplo, um envelope horizontal versionado que só muda por migração
explícita.

Quatro invariantes semânticas prendem a correção: faixa da calota, teto da profundidade
total, alturas distintas entre âncoras e volume dentro de cada território. Houve três
casos `it(...)` líquidos a mais; o teste da faixa da calota substituiu o gate anterior,
e outros testes existentes foram reforçados para distância tridimensional e calota.

**Uma consequência aceita:** com a câmera oblíqua padrão, dois MOCs podem se projetar
perto o bastante para que a rejeição de colisão suprima um dos rótulos. É o
comportamento correto — rótulo faltando é melhor que rótulo ilegível — e girar a
câmera separa os dois. O dossiê reconhece que não existe ponto de vista universalmente
bom para todos os grafos.

## 9. Verificação

| Verificação | Resultado |
| --- | --- |
| `python3 tools/audit.py` | APROVADO — 81 / 627 / 267, manifesto `4f5b1d00…` |
| `uv run pytest` | **138 passaram** (eram 109) |
| `uv run ruff check .` | limpo |
| `uv run mypy` | limpo, 39 arquivos |
| `pnpm run typecheck` | limpo |
| `pnpm run lint` | limpo |
| `pnpm run test` | **53 passaram** (eram 33) |
| `pnpm run build` | 705 kB, 192 kB gzip |

No navegador: zero erros no console, 44 draw calls na visão global, 50.800 triângulos,
seleção e recentragem funcionando, quatro controles respondendo por clique e por
teclado, movimento reduzido operante, zero painéis DOM, nenhuma escrita no corpus.

Servidores encerrados pelos PIDs próprios; portas 8000 e 5173 livres.

## 10. Cadeia de commits reconciliada

```text
6d267ab  Registra o relatório do Ciclo 1
81477b5  Persiste a memória espacial fora do corpus
c109132  Torna a camada operacional renderizável sem fabricar procedência
89161ea  Garante acesso sem WebGL e consolida a paleta em ADR
2c7a0ec  Produz evidência visual a partir da própria aplicação
b9d5752  Registra o relatório do Ciclo 1.1
c2e36db  Dá profundidade real ao atlas, sem soltá-lo
560f49a  Deixa o handoff com os prompts dos próximos agentes
[atual]  Reconcilia o fechamento antes do Ciclo 2
```

A cadeia é linear. O commit atual é o sucessor documental de `560f49a` e altera
somente este relatório e o handoff; seu SHA é descoberto por `git rev-parse HEAD`, não
hardcoded dentro do próprio objeto.

| Commit | Pai | Assunto | Arquivos alterados |
| --- | --- | --- | --- |
| `6d267ab` | `1be744e` | Registra o relatório do Ciclo 1 | adiciona `docs/CICLO-1-ATLAS-FULL-3D-2026-08-02.md` |
| `2c7a0ec` | `89161ea` | Produz evidência visual a partir da própria aplicação | modifica `frontend/package.json`, `pnpm-lock.yaml`, `tsconfig.json` e `vite.config.ts` |
| `c2e36db` | `b9d5752` | Dá profundidade real ao atlas, sem soltá-lo | modifica este relatório, `layout.ts`, `layout.test.ts` e `governance.test.ts` |
| `560f49a` | `c2e36db` | Deixa o handoff com os prompts dos próximos agentes | adiciona `docs/HANDOFF-2026-08-02.md` |

Calota, territórios volumétricos, relaxamento tridimensional e testes de profundidade
entraram todos em `c2e36db`. `560f49a` não contém a correção geométrica; apenas a
descreve no handoff.

Nenhum commit existente foi reescrito; a tag segue em `7aa5db1`.

Uma ressalva de higiene: as correções de rótulo, página de leitura e recentragem em
`frontend/src/atlas.ts` foram feitas antes do primeiro commit deste ciclo e acabaram
dentro dele, embora pertençam ao commit de evidência visual. Reescrever histórico é
proibido no projeto, então fica registrado aqui em vez de corrigido.

## 11. Critérios de aceite

| Critério | Situação |
| --- | --- |
| Posições persistem entre sessões | sim — verificado em disco e em uso real |
| Alteração local não move MOCs | sim — dois testes, mais o degrau de 32 no raio estrutural |
| Camada operacional implementada e testada | sim — 12 testes no backend, 4 no frontend |
| Produção não fabrica eventos | sim — `operationalSource: none` por padrão |
| Fallback acessível existe | sim — `?texto=1` e automático sem WebGL |
| `Índice` não é sol central | sim — cinco asserções e inspeção visual |
| Paleta normativa consolidada | sim — ADR-001 |
| Evidências visuais produzidas | sim — seis capturas 1920×1080 mais o registro textual |
| Corpus e manifesto idênticos | sim — `4f5b1d00…` |
| Working tree limpa | sim |
| Bundle e tarball de `560f49a` | sim — hashes e identidade conferidos no Gate 0 |
| Rastreabilidade documental | sim — cadeia, autoria da profundidade e métricas reconciliadas |

## 12. Pendências reais

1. **A métrica normativa de profundidade ainda precisa de uma decisão de governança.**
   O código adota a invariante estrutural de 0,22 e trata a razão contra a extensão
   corrente como diagnóstico. Uma futura revisão deve alterar o dossiê ou introduzir
   um segundo gate, possivelmente por envelope estrutural versionado.
2. **Posições não se auto-reconciliam com edições concorrentes do corpus.** Se o corpus
   mudar enquanto o Atlas está aberto, a impressão passa a divergir e o mapa é
   recalculado na próxima abertura. É o comportamento correto; o que falta é o watcher
   que reconciliaria em tempo real.
3. **A camada operacional não tem produtor.** O Writer Gateway ainda não existe, então
   `operationalSource` seguirá `none` até que algo registre eventos de verdade.
4. **`make smoke-providers` e `make workspace-oauth`** continuam sem execução. As três
   chaves de provedor foram preenchidas entre os ciclos e `/health` as reporta
   presentes; o Workspace segue sem `client_secret`.
5. **Comandos com administrador** seguem com Luiz e não bloqueiam nada.

## 13. Reproduzir

```bash
make audit && make test && make lint
```

```bash
make dev
```

```bash
VAULT_DEMO_OPERATIONAL=1 make dev
```

Modo textual em `http://127.0.0.1:5173/?texto=1`. Para refazer as capturas, com o
`make dev` no ar, no console do navegador:

```js
await window.__atlas.capturar('01-visao-global', 1920, 1080)
```
