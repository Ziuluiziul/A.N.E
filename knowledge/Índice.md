---
title: Índice do Vault
aliases: [Índice]
domain: vault
kind: moc
status: active
epistemic_status: mixed
updated: 2026-07-30
---

# Índice do Vault

## Missão

Base única de conhecimento técnico e científico, organizada por dependências reais
e não por associação verbal. Conteúdo ativo precisa ser relevante, verificável ou
explicitamente classificado quanto ao status epistêmico.

O critério editorial está em [[Política Epistêmica e de Linkagem]] <!-- relation:prerequisite -->.

## Como este Vault está organizado

A pasta é só localização. **A estrutura intelectual vive aqui e nos MOCs** — todo
wikilink resolve por nome, nenhum depende de caminho, e mover uma nota entre pastas
não quebra nada.

As camadas abaixo são de **dependência**: cada uma usa a anterior. Não é
classificação por assunto, é ordem de pré-requisito.

### Camada 1 — Formalismo

A árvore formal comum. Nada acima disso se sustenta sem ela.

- [[MOC — Matemática]] <!-- relation:navigation --> — lógica e provas, álgebra linear, cálculo multivariável.
- [[MOC — Estatística e Inferência]] <!-- relation:navigation --> — probabilidade, inferência, calibração e incerteza.

### Camada 2 — Método

Como se decide que uma afirmação vale.

- [[MOC — Metodologia Científica]] <!-- relation:navigation --> — causalidade e desenho experimental, metrologia, reprodutibilidade.

### Camada 3 — Computação e dados

O aparato que executa e o que se faz com registro.

- [[MOC — Ciência da Computação]] <!-- relation:navigation --> — algoritmos, custos, sistemas operacionais.
- [[MOC — Python]] <!-- relation:navigation --> — sub-MOC de CS; o modelo de dados da linguagem de trabalho.
- [[MOC — Dados e Informação]] <!-- relation:navigation --> — recuperação de informação e proveniência.

### Camada 4 — Domínios

Onde o conhecimento substantivo está concentrado.

- [[MOC — Física Teórica]] <!-- relation:navigation --> — fundamentos, teorias de fronteira, hipóteses e o monitor de evidências.
- [[MOC — Inteligência Artificial]] <!-- relation:navigation --> — aprendizado e modelos de linguagem, RAG, multimodalidade, avaliação e segurança.
- [[MOC — Ciências da Vida]] <!-- relation:navigation --> — bioenergética, mecanismo molecular e evolução, com as pontes para Física declaradas uma a uma.
- [[MOC — Cognição]] <!-- relation:navigation --> — percepção, julgamento e decisão como fenômenos mensuráveis, com o estado replicativo declarado.
- [[MOC — Segurança]] <!-- relation:navigation --> — propriedades, princípios de projeto e modelo de adversário; a ponte com Cognição que tem fonte.

### Camada transversal — Pontes

As camadas acima organizam o conhecimento por dependência dentro de cada domínio.
**42% das arestas deste corpus cruzam domínio**, e até 2026-08-04 não havia onde ler
essas travessias juntas — cada uma existia isolada dentro da nota que a declarava.

As pontes não são um domínio novo nem introduzem conteúdo: cada uma reúne arestas
**já declaradas** entre notas existentes e lhes dá ordem de leitura. Uma ponte que
precisasse inventar relação para se sustentar estaria violando a regra de 2026-07-28
e não deveria existir.

- [[Ponte — Formalismo Matemático da Física]] <!-- relation:navigation --> — a mais densa
  do corpus (22 arestas): qual estrutura matemática cada formalismo físico exige.
- [[Ponte — Inferência e Desenho Experimental]] <!-- relation:navigation --> — a única
  que corre nos dois sentidos: o dado que a inferência autoriza depende de como foi gerado.
- [[Ponte — Fundamento Estatístico dos Sistemas de IA]] <!-- relation:navigation --> —
  avaliar um modelo é fazer inferência, com todos os riscos de um estudo observacional.

## Leitura por status

| Status | Interpretação |
|---|---|
| `active` | participa do corpus e do grafo. |
| `archived` | registro histórico; não prova estado atual. |
| `quarantine` | fora do corpus ativo; não usar como evidência. |

O `epistemic_status` de cada nota distingue `established`, `supported`,
`model-dependent`, `hypothesis`, `speculative`, `mixed` e `operational`. Notas
marcadas `operational` são snapshots datados: valem como registro do que foi
medido, nunca como estado corrente.

## Regras do grafo

- todo wikilink ativo informa tipo de relação;
- analogia e metáfora não criam aresta;
- DOI/arXiv identifica a fonte, não comprova sua tese;
- teoria matematicamente consistente pode continuar sem suporte observacional;
- snapshots voláteis expiram e devem ser reconsultados.

Política completa: [[Política Epistêmica e de Linkagem]] <!-- relation:prerequisite -->.

## Regra de crescimento

Uma pasta de domínio nasce quando existem **três** notas do assunto. Antes disso, a
nota vive no domínio mais próximo. Nas camadas de fundamento o limiar é outro — ver
a emenda de 2026-07-30, adiante.

Esta regra existe por um motivo concreto: a versão anterior deste Vault tinha sete
pastas contendo apenas um MOC vazio cada, criadas a partir de uma matriz teórica
antes de haver qualquer conteúdo. Estrutura declarada acima do conteúdo existente
produz manutenção sem beneficiário.

### Emenda de 2026-07-28 — fundamentos crescem à frente da demanda

As camadas 1–3 (formalismo, método, computação) passam a seguir regra distinta das
camadas de domínio. Uma nota de fundamento **pode** ser criada sem consumidor no
Vault, porque a base existe para que o conteúdo avançado tenha onde se apoiar — e
uma base dimensionada apenas pelo que já se usa limita o que pode ser construído
depois.

A regra que substitui "não criar sem função", nas camadas 1–3:

> Nota de fundamento entra sem consumidor, desde que entre **completa**: com
> escopo e escopo negativo, conceitos, tabela de claims com status, limites e
> contraexemplos, e fontes com identificador verificado.
>
> O que continua proibido é o **placeholder** — MOC sem notas, nota-esboço,
> diretório criado à espera de conteúdo. A falha de 2026-07 não foi criar cedo
> demais; foi criar **vazio**.

Nas camadas de domínio, a regra original permanece: entram quando há função.

### Emenda de 2026-07-30 — o limiar de pasta acompanha o limiar de nota

A emenda anterior tratou de **quando uma nota pode nascer** e ficou silenciosa sobre
**quando uma pasta pode nascer**. O silêncio deixou `Dados/` — um MOC funcional mais
`Recuperação de Informação`, ambos completos — dependendo de interpretação. Isto
resolve a lacuna sem afrouxar nada:

> Nas camadas 1–3, uma pasta existe legitimamente com um **MOC funcional e ao menos
> uma nota substantiva completa**. Nas camadas de domínio, permanece o limiar de
> **três** notas antes de a pasta nascer.
>
> Em todas as camadas, sem exceção, seguem proibidos o MOC sem notas, a nota-esboço
> e o diretório criado à espera de conteúdo.

O critério não é a contagem, é a completude: o que a regra das três notas impede é
estrutura declarada acima do conteúdo existente. Uma pasta de fundamento com duas
notas completas não comete essa falha; sete pastas com um MOC vazio cada, sim — foi
exatamente o que aconteceu em 2026-07.

## Procedência

Este Vault é a migração enxuta do corpus mantido até 2026-07-28 na máquina LMDE 7.
Atravessaram **46 notas** de conhecimento e o critério editorial.

Ficaram para trás, por decisão explícita: a documentação da automação
(broker, decisões de governança do pipeline, revisões e auditorias — 28 notas),
os snapshots da máquina antiga, os sete MOCs sem conteúdo, e toda a camada de
staging gerada por modelo (2,7 MB), cujas versões divergentes eram, sem exceção,
mais antigas e mais inchadas que as canônicas.

### Estado do histórico Git (verificado em 2026-07-30)

A redação anterior desta seção afirmava que o histórico Git completo do corpus
original estava "preservado em bundle separado". A verificação pós-migração de
2026-07-30 **não localizou esse bundle** nesta máquina. A afirmação não se sustenta
como estava e fica corrigida assim:

- a preservação do bundle histórico **não está comprovada** neste momento;
- isso **não** equivale a declará-lo perdido: mídia externa e armazenamento offline
  não foram descartados, apenas não foram verificados;
- a história Git **verificável** desta instalação começa no commit `e738214`
  (`e7382143ac3c744484f415d6b5731a0277117888`), criado em 2026-07-30;
- nesse commit, as **80 notas Markdown do corpus são byte a byte idênticas** às 80
  do pacote auditado `Vault.zip`, SHA-256
  `f5578b083caa99c4393c1472d04d2bbf56a6e003a32945675129e3134c468aca`;
- a identidade acima cobre **apenas o corpus**. Os arquivos operacionais do Obsidian
  não são idênticos entre o pacote e o commit — `graph.json` diverge e
  `workspace.json` não foi versionado — e ficam fora dessa afirmação.

Enquanto o bundle não for localizado ou definitivamente descartado, o histórico
anterior a 2026-07-28 é uma **lacuna declarada**, não um fato estabelecido em
nenhuma das duas direções.

## Expansão de 2026-07-28

A partir da base migrada, o corpus foi ampliado sob uma regra única e sem exceção:
**nenhum identificador entra sem ter sido resolvido na fonte**. Onde a verificação
não foi possível na hora, a afirmação foi omitida — não estimada, não aproximada,
não citada "de memória".

Consequência visível dessa regra: claims que a literatura não fecha aparecem com
status `open`, não `established`. `P ≠ NP` é o exemplo mais claro — está registrada
como conjectura, com a evidência circunstancial e as barreiras conhecidas listadas,
e com a observação de que nenhuma delas é demonstração.

A regra de aresta interdisciplinar foi aplicada com o mesmo rigor. Vocabulário
compartilhado não criou ligação: "informação" em genética e em Shannon estão
ligadas por `contrasts`, não por `extends`; "replicação" em sistemas distribuídos e
em metodologia científica têm a homonímia registrada para impedir aresta indevida.
A única ponte Física↔Biologia admitida como `prerequisite` é a bioenergética, porque
ali existe fonte primária tratando explicitamente dos dois domínios.
