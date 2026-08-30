# Ciclo 1 — Atlas Neural-Epistêmico FULL 3D — 2026-08-02

Consolidação do bootstrap, fechamento dos defeitos P0 da projeção do corpus e
primeira fatia vertical do Atlas.

**Resultado: PASS**, com duas ressalvas declaradas na última seção — nenhuma delas
bloqueia o ciclo seguinte.

## 1. Estado inicial real

O relatório anterior descrevia o checkpoint `52e3f39` com nove arquivos alterados e
não commitados por outro agente. Essa descrição já estava vencida quando este ciclo
começou: o trabalho concorrente foi concluído e commitado.

| Item | Relato anterior | Estado real em 2026-08-02 | Evidência |
| --- | --- | --- | --- |
| HEAD | `52e3f39` | `6510322` | `git rev-parse HEAD` |
| Branch | main | main | `git status --porcelain=v2 --branch` |
| Working tree | suja, 9 arquivos | **limpa** | `git status --porcelain=v1` vazio |
| Commits posteriores | nenhum | 1: `6510322` "Endurece integrações e encerra o bootstrap" | `git log` |
| Worktrees | — | só a principal | `git worktree list` |
| Processos concorrentes | outro agente editando | **nenhum** | `ps`, `lsof +D`, sem `index.lock` |
| Tag histórica | `7aa5db1` | `7aa5db1`, intacta | `git rev-parse baseline-pos-migracao-2026-07-30` |
| Notas / wikilinks / claims | 81 / 627 / 267 | 81 / 627 / 267 | `python3 tools/audit.py` |
| SHA do manifesto | `4f5b1d00…` | `4f5b1d00…` idêntico | idem |
| Testes | 33, depois "38 em voo" | **57** | `uv run pytest -q` |
| Lint / tipos | 2 pendências | limpos | `ruff`, `mypy` (31 arquivos) |
| Pendências de lint citadas | 2 abertas | ambas fechadas em `6510322` | inspeção do commit |
| Documentação | desatualizada | ainda descrevia 33 testes | `docs/BOOTSTRAP-2026-07-30.md` |

O `6510322` entregou mais do que o relatório previa: além de `SecretStr`, backoff e
correção de `extract_claims`, endureceu o `ProposalStore` (escrita atômica, trava
entre processos, IDs sem travessia de diretório), o cliente do Workspace (token
atômico com 600, recusa a escopo não consentido, credencial fora do repositório) e
acrescentou `tests/test_provider_commands.py`.

Nenhuma ambiguidade sobre qual árvore é canônica, e nada a integrar manualmente.

## 2. Preservação

Auditor no estado real, antes de qualquer mutação:

```text
notas 81 · wikilinks 627 · claims 267 · IDs únicos 267 · zero defeitos
SHA-256 do manifesto  4f5b1d009041583c89957f7c22199d8d77836f4441f7e6aa16e741da8b2bf5bb
```

Idêntico ao histórico. Bundle criado e verificado:

```text
~/Documentos/Backups/Vault/2026-08-02/vault-autodidata-pre-ciclo1-6510322.bundle
SHA-256 dc7b67cd173ffed0dd3fe1653fca1a2ed6234867e704905b7d3e09b1806c7b15
```

`git bundle verify` aprovou; um clone temporário reproduziu `6510322` e o mesmo
manifesto; o clone foi removido. Nenhum Markdown canônico foi alterado neste ciclo —
`knowledge/` não aparece em nenhum dos quatro commits.

## 3. Alterações concorrentes: auditoria

Todas verificadas no código e nos testes de `6510322`.

| Item | Veredito | Evidência |
| --- | --- | --- |
| `SecretStr` nas chaves | confere | `repr`, `model_dump_json` e `credential_status` não revelam valor; `_plain_secret` desempacota só na fronteira da SDK |
| `extract_claims` com `\|` | confere | ancora no vocabulário fechado de status; `CLM-EST-INFER-001` preserva `P(dados … \| H₀)` |
| Assimetria das SDKs | confere | Groq `await raw.parse()`; OpenAI/NVIDIA `raw.parse()` síncrono, porque `with_raw_response` devolve a resposta legada |
| `DECLARED_BUDGET` | confere | `DECLARED_REQUESTS_PER_MINUTE = 40` é `int` na origem; não há coerção |
| Retry intrarrun | ausente | `max_retries=0` (Groq, NVIDIA), `HttpRetryOptions(attempts=1)` (Google); nenhum laço de repetição |
| Imports de `test_corpus_reader` | já corrigido | ruff limpo |
| Tipagem do adapter NVIDIA | já corrigido | mypy limpo |

**Um defeito residual encontrado e corrigido neste ciclo.** `AdaptiveBackoff.rate_limited`
honrava `retry-after` sem teto: um servidor respondendo `retry-after: 3600` faria a
próxima chamada dormir uma hora dentro do processo. O valor recomendado continua
íntegro no relatório — cortá-lo seria mentir sobre o que o provedor pediu —, mas o
bloqueio em processo passou a ser limitado a `max_delay_s`. Commit `0526cfe`.

## 4. Correções P0

### 4.1 Escopo de ingestão

`CorpusReader` já validava a raiz e recusava leitura fora dela. Faltava o caminho por
symlink: `rglob` atravessa diretório ligado, e o conteúdo de fora entrava até estourar
mais adiante. Agora um symlink que sai do corpus **reprova a leitura** com o caminho
nomeado. Só `**/*.md` sob a raiz configurada entra; `runtime/`, `README.md` e afins
ficam de fora.

Não existe modo DEMO. Não é uma omissão: não há dataset de demonstração nem caminho de
código que produza um, e `meta.source` é sempre `"corpus"`. Dois testes cobrem a
ausência de fallback — corpus inexistente levanta erro, corpus vazio produz projeção
vazia. Um fallback para dados de exemplo é pior que uma falha, porque parece resultado.

### 4.2 Identidade

A identidade de uma nota passa a ser o **caminho relativo normalizado em NFC, sem
extensão** (`Física/Entropia`), e não o nome do arquivo.

Enquanto fosse o nome, `Física/Entropia.md` e `Dados/Entropia.md` eram o mesmo nó e a
segunda apagava a primeira sem erro. A troca de chave **elimina a classe inteira**, em
vez de detectá-la. NFC cobre o outro caminho: no Linux o mesmo nome acentuado existe
em bytes diferentes conforme quem o escreveu, e duas grafias de `Física` não podem
virar dois domínios. Duas notas que colidam após normalização reprovam o índice.

Colisão de **nome, título ou alias** não reprova por si — duas notas podem ter o mesmo
nome de arquivo em domínios diferentes sem que nada as referencie por nome. Fica
registrada em `meta.diagnostics.collisions` e vira defeito no momento em que um
wikilink precisa escolher.

### 4.3 Resolução de wikilinks

Precedência fixa, documentada em `PRECEDENCE`:

```text
id → caminho relativo à nota de origem → nome de arquivo → título → alias
   → nome/título/alias sem caixa nem acento
```

Um degrau com mais de um candidato **interrompe a busca** em vez de descer para o
próximo: descer esconderia a ambiguidade atrás de um critério mais frouxo. Ambiguidade
reprova a construção do grafo e devolve todos os candidatos; a API responde 409.
Escolher um deles produziria um grafo plausível e errado, que é o pior resultado
possível para um corpus cuja finalidade é ser confiável.

Fragmento (`[[Nota#Seção]]`) é separado do alvo e preservado; `[[#Seção]]` resolve para
a própria nota; o texto de exibição depois do `|` nunca chega ao resolvedor.

**Nenhuma dessas patologias existe no corpus de hoje** — zero nomes repetidos, zero
títulos duplicados, zero aliases colidindo, zero caminhos fora de NFC, zero fragmentos,
zero alvos com barra ou pipe. Os testes usam corpora sintéticos justamente por isso: a
defesa precisa existir antes do defeito.

### 4.4 Fronteira backend/frontend

O contrato `vault.projection`, versionado em `1.0.0`, é a única forma do corpus que sai
do backend. A chave `corpus`, que carregava o caminho absoluto do repositório, saiu; no
lugar está `corpusFingerprint`, que é **o mesmo manifesto SHA-256 que o auditor
calcula, pelo mesmo método** — conferível com uma linha de terminal e utilizável como
chave de cache do layout.

Distingue entidade, tipo, estado canônico, estado epistêmico, domínio, MOC de
ancoragem, relações, métricas de grau e temporalidade, mais um bloco `visual` com token
de paleta, classe de LOD e prioridade de rótulo. Nada de conteúdo de nota, caminho
absoluto ou segredo. Campos derivados são declarados em `meta.computedFields`.

Ontologia desconhecida reprova: um `kind` fora do mapa é deriva ontológica, não caso a
tratar com valor padrão. Ausência é `null` ou `not-specified`; presença desconhecida é
erro. Vale igual para `epistemic_status`.

## 5. Atlas FULL 3D

### 5.1 Ontologia extraída, não inventada

Nada da concept art foi codificado. Os tipos vêm do corpus real:

| `kind` no corpus | Entidade no contrato | Quantidade |
| --- | --- | --- |
| `moc` | `moc` | 12 |
| `nota` | `note` | 65 |
| `referência` | `reference` | 2 |
| `registro` | `register` | 2 |

Os MOCs **já são formalmente tipados** no frontmatter, então não houve necessidade de
regra calculada para reconhecê-los. Os onze domínios são os do corpus (dez temáticos
mais `raiz`), não os nomes discutidos no dossiê. Nenhuma nota, relação, autor ou claim
foi fabricado.

O que é calculado está marcado como tal: `domainId`, `anchorMocId`, `mocIds`, graus,
token de paleta, classe de LOD e os filamentos agregados.

### 5.2 Layout

Anel de MOCs em fatias angulares **iguais**, ordenadas por identidade, com o MOC de
raiz (`Índice`) no centro. Cada nota orbita a própria âncora numa espiral de Vogel,
ordenada por prioridade, e o relaxamento de colisão age **só dentro do território**.

O raio do anel cresce por degraus de 32 entidades. Contínuo seria mais elegante e faria
todos os MOCs se moverem a cada nota nova, violando a métrica de estabilidade do
dossiê. Dois testes prendem a propriedade: nota nova não desloca nenhum MOC, e não
desloca nenhum território vizinho.

`z` fica numa faixa de ±6 contra um raio de ~105 — 5,7% da extensão horizontal, abaixo
da faixa de 15–25% que o dossiê sugere, e muito abaixo do volume esférico que o Atlas
substituiu. Profundidade separa camadas e foco; não mede nada.

Ancoragem se recusa a desempatar: Computação tem dois MOCs, e a nota que nenhum deles
reivindica fica **sem âncora**, posicionada pelo baricentro do domínio.

### 5.3 Gramática visual

| Entidade | Geometria |
| --- | --- |
| MOC | núcleo hexagonal volumétrico + anel estrutural (toro) |
| nota | elipsoide achatado |
| referência | prisma fino com lombada lateral |
| registro | placa hexagonal espessa |

Tamanho é degrau discreto por classe — nunca grau somado a claims. O MOC é 2,5× a nota,
não uma esfera gigante.

| Relação | Padrão | Marcador |
| --- | --- | --- |
| `navigation` | tracejada fina | — |
| `prerequisite` | contínua | seta sólida |
| `extends` | contínua | seta vazada |
| `contrasts` | linha dupla | — |
| `evidence` | contínua | marcador quadrado |
| `operational` | traço-ponto | — |
| `historical` | pontilhada | marcador temporal |
| inter-MOC | tubo espesso semitransparente, arqueado em `z` | agregado |

Matiz das linhas é neutra; as cores ficam com os domínios. O padrão é construído na
geometria porque `LineDashedMaterial` só sabe um par traço/intervalo e não faria
traço-ponto. Um teste verifica que as sete famílias têm assinatura distinta **sem usar
cor**.

Seleção usa contorno (casca em `BackSide`), elevação de 1,4 em `z` e a página de
leitura. O corpo selecionado não muda de cor nem de tamanho: mudar duas propriedades
faz o olho ler duas informações onde existe uma.

### 5.4 Exploração progressiva

Visão global: territórios, MOCs e os 63 filamentos agregados. As 511 arestas canônicas
ficam ocultas. Foco: as relações da entidade selecionada, com o padrão da família.
Filtro (`F`): revela todas as famílias de uma vez, para quem quer a visão média.

### 5.5 Texto e LOD

Texto SDF via `troika-three-text`, preso à geometria. Títulos curtos orientam-se à
câmera; o conteúdo longo abre numa página tridimensional opaca ao lado da entidade —
não sobre ela, e não num painel lateral. O pacote não publica tipos; em vez de
`declare module` com `any`, há uma declaração do subconjunto usado.

LOD por **tamanho projetado em pixels**, não por distância no mundo: o mesmo
afastamento produz glifos diferentes conforme o campo de visão e a altura da janela.
Limiares do dossiê (4 / 10 / 28 / 80 px) e histerese de 0,78 — subir de nível é
imediato, descer exige folga, para o rótulo não piscar na fronteira. No máximo 44
rótulos simultâneos, por prioridade.

### 5.6 Controles e acessibilidade

Quatro objetos 3D presos à câmera, semiocultos quando inativos: legenda (`L`), filtro
de relações (`F`), reduzir movimento (`M`), voltar à global (`G`); `Esc` limpa a
seleção. Não há botão de "fechar aplicação": uma aba não se fecha por vontade da
página, e um controle sem efeito é ruído com aparência de função.

`prefers-reduced-motion` é respeitado na inicialização. A camada DOM sobrevive apenas
como texto acessível (`.sr-only`, `aria-live`) com o resumo do corpus e a lista das 81
entidades — alcançável por leitor de tela e pela busca do navegador, fora da
composição visual.

### 5.7 ADRs

**ADR-1 — Three.js puro, sem R3F nem Drei.** Nenhuma necessidade concreta apareceu:
não há árvore de componentes, estado reativo nem reconciliação. `troika-three-text`
entra direto, que é o que o Drei `<Text>` embrulha. Custo evitado: React, o
reconciliador e a camada de abstração sobre o laço de render.

**ADR-2 — Desvio da paleta do dossiê.** A tabela põe D12 em h=105 e D03 em h=90 —
0,036 em OKLab, que reprova o gate de discriminabilidade que o próprio dossiê exige
("recalculada com métodos de maximização de distância"). Doze matizes igualmente
espaçadas num círculo de croma 0,12 ficam a 0,062. Os neutros seguem exatos
(`#0b1016`, `#edf2f9`), verificados por teste.

**ADR-3 — Corpos instanciados, seleção por casca.** Uma `InstancedMesh` por tipo mantém
o desenho em poucas chamadas. Emissiva por instância exigiria material customizado; a
casca de foco resolve com um objeto reutilizado.

**ADR-4 — Ponto de verificação só em desenvolvimento.** `window.__atlas` existe sob
`import.meta.env.DEV`. Uma aba sem composição não recebe `requestAnimationFrame`, e sem
isso não haveria como conferir chamadas de desenho nem exercer o picking. O build de
produção não o define.

## 6. Segurança e provedores

Nenhuma credencial no Git: nenhum arquivo de segredo rastreado, o único `env`
versionado é `.env.example`, e a varredura por padrões de chave (`AIza…`, `gsk_…`,
`nvapi-…`, `sk-…`, `ya29.…`) em todos os commits alcançáveis não achou nada. Um teste
faz a mesma varredura sobre a projeção serializada e sobre as chaves do JSON.

Retries intrarrun continuam desligados nos três provedores. Nenhum provedor novo,
nenhum modelo novo, nenhum fallback automático. Nenhuma chamada externa foi feita neste
ciclo.

**Mudança de estado desde o ciclo anterior:** `GEMINI_API_KEY`, `GROQ_API_KEY` e
`NVIDIA_API_KEY` agora estão preenchidas — `/health` reporta `true` para as três, sem
expor valor. `make smoke-providers` deixou de estar bloqueado. Não foi executado: o
escopo deste ciclo não o inclui e a chamada gasta cota. O Workspace segue sem
`client_secret`.

## 7. Testes e auditoria

| Verificação | Resultado |
| --- | --- |
| `python3 tools/audit.py` | APROVADO — 81 / 627 / 267, manifesto `4f5b1d00…` |
| `uv run pytest` | **109 passaram** (eram 57) |
| `uv run ruff check .` | limpo |
| `uv run mypy` | limpo, 35 arquivos |
| `pnpm run typecheck` | limpo |
| `pnpm run lint` | limpo |
| `pnpm run test` | **33 passaram** |
| `pnpm run build` | 700 kB, 191 kB gzip |

Testes novos: 26 de identidade e resolução, 25 do contrato de projeção, 1 do teto do
backoff, 33 do frontend (layout, estabilidade, paleta, tamanho, LOD, arestas,
contrato).

Um teste antigo tinha um defeito próprio: procurava a substring `TOKEN` na projeção
serializada, que casa com `visual.paletteToken` — reprovava o inocente e, ao falhar
sobre uma string de 216 KB, travava o pytest montando a explicação. Trocado por busca
de formatos de chave reais e nomes de variável de ambiente.

## 8. Verificação no navegador

Backend e frontend locais, projeção vinda de `http://127.0.0.1:8000/corpus/projection`.

| Item | Medida |
| --- | --- |
| Console | zero erros |
| Contexto | WebGL2, canvas 1280×720 |
| Origem | `corpus`, contrato v1.0.0, impressão `4f5b1d00…` |
| Draw calls — global | **86** |
| Draw calls — foco | 92 |
| Draw calls — todas as famílias | 102 |
| Draw calls — legenda aberta | 94 |
| Triângulos | 52.880 |
| Pixels desenhados | 49.442 (5,4% do quadro) |
| Faixas de matiz distintas | 8 |
| Seleção por clique | acertou entidades de Física, IA e Ciências da Vida |
| Arrastar seleciona? | não |
| `L` / `F` / `M` / `G` / `Esc` | todos respondem e anunciam |
| Painéis DOM (`aside`, `nav`, `header`) | **0** |
| Escrita no corpus | nenhuma; a API só tem verbos GET |

Os alvos de draw call do dossiê (≤ 250 padrão, ≤ 500 sob foco) ficam com folga.

**Não há captura de tela.** O painel do navegador desta sessão permaneceu oculto e não
compõe quadros, o que impede `screenshot`. A verificação acima é programática e
reproduzível: `make dev`, abrir `http://127.0.0.1:5173`, e no console do navegador usar
`window.__atlas.atlas.renderOnce()`, `.select(id)` e `.toggle(id)`.

## 9. Commits

Quatro, sobre `6510322`, nenhum existente reescrito:

```text
4657c4c  Endurece ingestão, identidade e resolução de wikilinks
45c47ff  Introduz contrato de projeção sanitizado entre corpus e navegador
0526cfe  Limita o bloqueio do backoff sem falsear a espera recomendada
1be744e  Substitui a prova de grafo pelo Atlas Neural-Epistêmico FULL 3D
```

A tag `baseline-pos-migracao-2026-07-30` continua em `7aa5db1`.

## 10. Limitações e pendências reais

1. **`docs/BOOTSTRAP-2026-07-30.md` descreve o estado em `6510322`**, com 57 testes.
   Continua correto para aquele commit; este relatório o sucede.
2. **Sem captura de tela**, pelo motivo da seção 8.
3. **Camada operacional ausente.** O contrato prevê procedência (agente, atividade,
   evidência, proposta, validação, commit), mas nenhuma dessas entidades existe no
   corpus ainda, então a cena não as desenha. Nada foi fabricado para preencher.
4. **Posições não persistem entre sessões.** `layoutAtlas` aceita um mapa anterior e o
   respeita, mas nada o grava ainda. O layout é determinístico, então a cena reabre
   idêntica; o que falta é sobreviver a uma nota nova sem recalcular o território.
5. **`make smoke-providers` e `make workspace-oauth`** seguem sem execução (seção 6).
6. **Comandos que exigem administrador** continuam com Luiz, e não bloqueiam nada:
   `sudo apt purge -y obsidian && sudo apt autoremove -y`.

## 11. Comandos para reproduzir

```bash
make audit          # 81 / 627 / 267, manifesto 4f5b1d00…
make test           # 109 pytest + 33 vitest + tsc
make lint           # ruff, mypy, eslint
make corpus-graph   # projeção em frontend/public/projection.json
make dev            # backend :8000 e Atlas :5173
```
