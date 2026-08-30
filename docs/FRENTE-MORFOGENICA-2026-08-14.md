# A frente morfogênica, confrontada com o que a fila mediu

**Projeto:** A.N.E. / vault-autodidata · **Data:** 2026-08-14 · **HEAD:** `d8b5f5a`
**Origem da frente:** crítica de Anirban Bandyopadhyay ao Graph Engineering
(https://x.com/anirbanbandyo/status/2088425573102317600), e a resposta do ChatGPT
propondo uma camada *Morphogenic Runtime / Morphogenic Control Plane* — reproduzida
íntegra em [`FRENTE-MORFOGENICA-2026-08-14-PROPOSTA.md`](FRENTE-MORFOGENICA-2026-08-14-PROPOSTA.md).

**Desfecho.** Este relatório foi lido e respondido; a decisão que saiu dele está em
[`ADR-003-instrumentacao-antes-de-morfogenese.md`](ADR-003-instrumentacao-antes-de-morfogenese.md).
Em resumo: a camada morfogênica é adiada em favor de instrumentação e controle
homeostático, porque os números abaixo mostram que fazê-la emergir agora seria adaptação
sobre sinal inexistente.

**Para que serve este pacote.** A proposta morfogênica foi escrita sem acesso ao
repositório. Nas últimas vinte e quatro horas a fila autônoma do A.N.E. produziu 296
tentativas de revisão de corpus e exatamente **uma** decisão. Esse material é o teste
empírico mais próximo que a proposta tem, e ele diz coisas que a proposta não previu —
umas a favor dela, outras contra. Este relatório apresenta esse confronto e devolve
cinco perguntas.

Tudo que segue é medido. Os arquivos de `evidencia/` são a fonte; nenhum número aqui
foi estimado.

---

## 1. O estado, em números

| | |
|---|---|
| Corpus | 84 notas · 672 wikilinks · 267 claims · **inalterado desde 2026-08-04** |
| Fila autônoma | 255 tarefas — 80 blocked, 56 queued, 52 completed, 46 rejected, 21 retry_wait |
| `corpus_review` (as únicas que podem tocar o corpus) | 45 — **44 blocked, 1 completed, 0 na fila, 0 rodando** |
| Tentativas gastas nelas | **296**, entre 4 e 9 por tarefa |
| Painéis de quórum | 156 — 98 `escalate`, 49 `reject`, 5 `promote`, 1 `revise` |
| Painéis com patch aplicável | 18 |
| Promoções efetivas ao corpus | **0** |
| Endpoints inventariados | 142 — 50 `ok`, 74 `unavailable`, 14 `auth`, 4 `error` |
| Gates | auditoria aprovada · 607 pytest · 557 vitest · ruff, mypy, ESLint limpos |

Duas leituras dessa tabela importam para a frente.

A primeira: **a taxa de escalonamento é de 64%** (98 de 153 painéis decididos). O painel
não consegue concluir na maioria das vezes.

A segunda: **296 tentativas produziram 1 decisão.** Não é um sistema caro; é um sistema
que quase nunca fecha o circuito.

---

## 2. A nuance central: quatro funções morfogênicas já foram implementadas — à mão

Este é o achado que a proposta não podia antecipar. Os quatro últimos commits do
projeto, todos de 2026-08-14, não foram planejados sob vocabulário morfogênico. Cada um
deles é, em retrospecto, exatamente uma das funções que a proposta pede:

| commit | o que corrigiu | função morfogênica correspondente |
|---|---|---|
| `d32ea67` | crédito esgotado suspende o **provedor inteiro**, não só o endpoint | **quimiotaxia negativa / cicatrização** — parar de seguir um gradiente morto |
| `30eedfc` | `replace` que apaga claims, wikilinks ou metade da nota exige `allows_reduction` | **distinção entre apoptose e necrose** — remoção declarada versus destruição |
| `1328e36` | envelope inválido vira `invalid_envelope` e não aposenta a nota | **regeneração** — falha de forma não mata o órgão |
| `ddf465e` | divergência só nasce de painel de corpus com nota herdada | **controle de proliferação** — crescimento desacoplado de função é tumor, não morfogênese |

O diagnóstico morfogênico, portanto, **acerta a classe dos defeitos**. Antes de `d32ea67`
o sistema gastou 22 tarefas tentando quatro endpoints diferentes da mesma conta Google
sem crédito: quatro derrotas garantidas por uma causa só, que é literalmente seguir um
gradiente morto. Antes de `ddf465e`, 80 das 84 tarefas novas criadas em poucas horas eram
meta-tarefas incapazes, por construção, de tocar o corpus: proliferação sem função.

E aqui está o contra-argumento, que é igualmente medido: **as quatro correções foram
regras determinísticas, baratas, e funcionaram.** Nenhuma exigiu emergência. Se o
argumento morfogênico for "o sistema precisa de mecanismos que se auto-organizem", estes
quatro casos são evidência de que uma regra explícita resolve — e resolve em um commit.

O que salva o argumento morfogênico não é a natureza dos defeitos. É o padrão da
sequência: **cada regra corrigiu a causa dominante daquele momento e revelou a
seguinte.** Google morto → envelope inválido → amplificador de divergência → e agora:

```
causa do último fracasso das 44 corpus_review bloqueadas
  20  rate limit do provedor
   8  votos válidos insuficientes
   7  orçamento do lote esgotado
   4  provedor indisponível
   3  credencial estruturalmente impossível (OpenRouter sem BYOK)
   1  prompt acima do teto
   1  outro
```

Vinte e sete das 44 morreram por **capacidade**, não por epistemologia. A regra seguinte
seria "regule a demanda contra a oferta" — e essa é a primeira da série que não se
escreve como uma condição, porque depende de uma grandeza que o sistema não mede. É aí
que a esteira de regras trava, e é o argumento mais forte a favor de um mecanismo
homeostático. Não porque regras sejam feias: porque a próxima regra não cabe numa
condição.

---

## 3. A segunda nuance: o plano de controle não tem instrumentos

A proposta enumera os sinais que fariam a topologia emergir: *desempenho, afinidade
semântica, divergência útil, latência, confiabilidade e custo*. Fui verificar o que
existe hoje (`evidencia/sinais-disponiveis.json`).

**Existe, e é real:**

- por endpoint — `observed_status`, `latency_ms`, `last_success`, `observed_limits`,
  sondas (142 endpoints inventariados);
- por stream — classe de entrega por endpoint, medida por `make probe-streams`;
- por chamada — ledger de cota com tokens, em **janela deslizante**, não histórico;
- por voto — `decision`, `confidence`, `blocking_issues`, `evidence`, `schema_valid`, e
  os sinalizadores de raciocínio e reparo.

**Não existe, em nenhuma forma:**

- competência de um endpoint **por domínio** — nada mede se o `qwen3.6-27b` é melhor em
  Física do que em Cognição;
- taxa histórica de acordo de um revisor;
- contribuição marginal de um revisor para a decisão;
- custo por decisão útil;
- divergência como grandeza persistida — ela existe como evento, nunca como campo;
- qualidade a posteriori de um patch aceito.

O detalhe que decide: **os votos estão gravados em 156 diretórios de painel e nunca são
lidos de volta.** A matéria-prima da diferenciação existe como evento bruto e nunca foi
agregada em superfície.

Dos seis sinais que a proposta nomeia, o sistema mede hoje **dois** — latência e
confiabilidade — e ambos por endpoint, nenhum por domínio. Diferenciação funcional
alimentada pelos outros quatro seria diferenciação alimentada por ruído.

Isso não é objeção à proposta. É uma ordem de precedência: **a camada morfogênica é um
plano de controle, e um plano de controle sem instrumento é malha aberta.** E há um
bônus prático: o mesmo ledger agregado que daria substrato à diferenciação é o
instrumento que resolveria o problema de capacidade da seção anterior. Instrumentar
primeiro não adia a frente morfogênica — paga a conta dela e a da esteira de regras ao
mesmo tempo.

---

## 4. O que o quórum demonstrou sobre si mesmo

Das 45 tarefas de corpus, **uma** chegou a decisão. O painel `59e32f5df5d5` decidiu
`promote` por 2 de 3 votos válidos. O patch aprovado substituiria uma nota de 73 linhas
por dez linhas, com reticências literais no corpo:

> Especificação do conteúdo não solicitada, apenas o patch para CLL-FIS-LQG-004.
> … (resto do conteúdo mantido igual, apenas a seção relevante alterada) …

Métrica da substituição: claims 5 → 1, wikilinks 5 → 0, bytes 4672 → 603
(`evidencia/patch-destrutivo.json`, e a nota real em `evidencia/nota-alvo-original.md`).

A auditoria estrutural do corpus **reprovaria** — mas por um único sinal, frontmatter
ausente. Aplicado a uma cópia, o resultado acusa 1 defeito e passa em tudo o mais: os 4
claims perdidos e os 5 wikilinks perdidos não geram defeito nenhum, porque o auditor
verifica se o que sobrou está bem formado, não se algo foi destruído. Com um frontmatter
plausível copiado no topo, o stub teria sido commitado no corpus com procedência de
quórum. A guarda de delta de `30eedfc` fechou esse caminho no mesmo dia.

**Por que isso importa para a frente morfogênica.** A proposta dá ao quórum papel
morfológico: *"dissenso persistente poderia provocar bifurcação; consenso redundante
poderia provocar poda"*. O único dado empírico disponível é de um consenso **redundante e
errado**. E a composição do voto diz mais que o placar:

```
ollama/minimax-m3        verificador-factual       approve   confiança 0,85
ollama/gemma4:31b        critico-epistemologico    approve   confiança 1,00
groq/groq/compound-mini  revisor-estrutural        revise    confiança 0,90
```

O painel cumpriu a diversidade mínima — 2 provedores, 3 famílias —, mas **a maioria que
aprovou é de um provedor só**. O único revisor fora do `ollama` foi exatamente o que
recusou. Com três votos, a regra de diversidade garante que o painel seja diverso; ela
não garante que a *maioria* seja.

Se a formação de estrutura for governada por acordo, este painel teria podado na direção
errada, com procedência impecável — e teria podado por concordância intraprovedor,
que é a forma de acordo com menos informação. **Acordo não é sinal de qualidade enquanto
não estiver calibrado contra um desfecho** — e o desfecho, no A.N.E., é a promoção, que
aconteceu zero vezes. A alça está aberta nos dois extremos.

---

## 5. Onde a proposta encosta no que já existe

Mapa honesto do que já está construído e do que a camada exigiria:

| a proposta pede | o A.N.E. hoje | distância |
|---|---|---|
| topologia adaptativa por desempenho e custo | seleção por inventário + AUTO, com diversidade mínima imposta (2 provedores, 3 famílias) | falta o histórico agregado; a seleção é por disponibilidade, não por competência |
| diferenciação funcional | 7 papéis fixos em `work/roles.py`, com classe `produtor`/`avaliador` | papel é rótulo dado, nunca adquirido |
| apoptose operacional | `blocked` é terminal e o id é hash determinístico da evidência — a tarefa **não renasce** | há necrose sem regeneração: o oposto de apoptose |
| mitose | `proposal_revision` e `divergence_review` derivam painel de painel | existe, e foi justamente o que precisou de freio |
| gradientes (incerteza, custo, conflito) | nenhum campo persistido; só eventos | ausente |
| homeostase | orçamento fixo por lote (`max_calls: 5`) | é teto, não regulação |
| cicatrização | `d32ea67` suspende provedor com falha de conta | existe como regra global, não como reorganização local |
| `(x,y,z)` como consequência | **layout ancorado com memória espacial deliberada** | **colisão direta — ver abaixo** |

A última linha é a mais séria e merece ser dita com todas as letras.

A proposta afirma: *"as coordenadas (x,y,z) passariam a ser consequência, não
fundamento"*. O A.N.E. decidiu o contrário, e decidiu por evidência. A auditoria de
2026-08-05 pôs a separação do espaço operacional **antes da estética** porque os nós de
quórum entravam no dimensionamento do anel de âncoras e empurravam cada MOC de 87 para
148 unidades: a memória espacial — a capacidade de o mantenedor saber onde uma coisa
está porque ela continua onde estava — era destruída por dado que nem era do corpus. O
commit `4818c87` fixou a regra atual: painéis secundários se movem apenas por mudança
real de topologia, âncoras principais não se movem.

Ou seja: **o Atlas já foi um morfoscópio, e isso foi tratado como defeito.** Não porque
mover seja feio, mas porque um mapa cujas coordenadas mudam sozinhas deixa de ser
navegável para o humano que o usa todo dia.

Isso não mata a ideia do morfoscópio. Sugere que ela precisa de um segundo espaço, ou de
uma separação explícita entre o que é âncora (estável por contrato, para navegação) e o
que é tecido (livre para se reorganizar, para observação) — e essa distinção não está na
proposta.

---

## 6. As cinco perguntas que este pacote devolve

1. **Ordem de construção.** Qual é o conjunto **mínimo** de grandezas persistidas — por
   endpoint, por domínio, por revisor — para que diferenciação funcional e apoptose sejam
   sinal e não ruído? O sistema hoje mede dois dos seis sinais que a proposta nomeia.

2. **Calibração do acordo.** O único painel que concluiu aprovou um stub por 2 votos de
   3 — os dois do mesmo provedor, com o único revisor externo recusando. Se dissenso e
   consenso passam a formar estrutura, que sinal de desfecho fecha a alça — e de onde ele
   vem, se o desfecho canônico é a promoção e houve zero promoções em dez dias?

3. **Homeostase contra capacidade.** 296 tentativas para 1 decisão, sobre quatro free
   tiers. A regulação deve ir na demanda (menos tarefas simultâneas, orçamento adaptativo)
   ou na exigência do painel (hoje: 3 votos válidos, 2 provedores, 3 famílias distintas)?
   A segunda é mais barata e mexe justamente no que define o rigor epistêmico do projeto.

4. **Onde a regra determinística deixa de bastar.** Quatro funções morfogênicas foram
   implementadas hoje como regras de uma linha e funcionaram. Que critério diz que a
   quinta não deve ser mais uma regra? A resposta candidata deste relatório é "quando a
   condição depende de grandeza não medida" — vale?

5. **A colisão do morfoscópio.** Coordenadas como consequência contradizem uma decisão
   tomada por evidência neste projeto. Âncora estável e tecido móvel podem coexistir no
   mesmo espaço, ou o morfoscópio pede uma segunda vista?

---

## 7. Inventário do pacote

O pacote enviado para análise externa tinha **19 arquivos regulares em 4 diretórios** —
23 entradas no ZIP, contando os diretórios. Ele **não é versionado**: `runtime/`, `*.zip`
e `*.tar.gz` estão no `.gitignore`, e a evidência bruta é estado local da máquina. O que
entra no repositório é este relatório, a proposta e a decisão. A evidência é reproduzível
a partir de `runtime/` no mesmo HEAD.

```
RELATORIO.md                        este documento
PROPOSTA-MORFOGENICA.md             a proposta original, íntegra e atribuída
evidencia/
  estado-medido.json                fila, painéis, corpus, revisores mais usados
  corpus-review-falhas.json         as 296 tentativas classificadas por causa
  sinais-disponiveis.json           o que é mensurável hoje, e o que falta
  patch-destrutivo.json             o patch aprovado 2 de 3, com os votos
  nota-alvo-original.md             a nota de 73 linhas que ele substituiria
  commits-do-ciclo.txt              os seis commits do ciclo
  gates.txt                         saída de audit, test e lint
codigo/                             os mecanismos citados, como estão no HEAD
  patch.py  promoter.py  queue.py  generator.py  proposal.py  orchestrator.py  roles.py
capturas/                           o Atlas real, antes e depois do ajuste de hoje
MANIFESTO.txt                       SHA-256 de cada arquivo
```

**Redação e sigilo.** Nada aqui contém credencial, dica de chave ou identificador de
conta. Os nomes de provedor e de endpoint aparecem porque são a substância técnica do
relatório. O corpus é do próprio mantenedor.

**Limite deste relatório.** Ele mede estrutura e operação. Não avalia a verdade
científica de nenhuma nota, e a auditoria citada declara isso na própria saída: nenhuma
resolução de DOI, arXiv ou ISBN foi executada.

---

## 8. Errata da primeira versão

A primeira versão circulou com três erros na seção 4. Ficam registrados aqui em vez de
serem apagados, porque dois deles enfraquecem o argumento que o próprio relatório
defende, e um relatório que corrige a si mesmo em silêncio não serve de evidência.

1. **Confiança dos votos.** Dizia 0,95 e 1,0; os valores registrados são **0,85 e 1,0**.
   O 0,95 veio de outro painel, de 2026-08-04, por confusão minha na leitura.
2. **Independência dos aprovadores.** Dizia "dois revisores independentes, de provedores
   e famílias distintos". É falso: **ambos os `approve` são do `ollama`**, e o único
   revisor de outro provedor foi o que votou `revise`. O erro tornava o consenso mais
   impressionante do que ele foi — e escondia o achado mais interessante, que é a maioria
   ter sido intraprovedor num painel formalmente diverso.
3. **Contagem do pacote.** A mensagem que acompanhou o ZIP dizia "23 arquivos". São
   **19 arquivos regulares e 4 diretórios**, 23 entradas.

Os dois primeiros foram apontados na leitura do ChatGPT; o segundo foi encontrado ao
conferir o primeiro.
