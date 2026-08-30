# Fechamento de 3.5-D — simplificação e deliberação viva

**Base:** `7a3bac3` · **Commits:** `b6fe0e8`, `7923e32`, `36fe753`, `2a4bf70`

---

## 1. O que saiu de cena (D1)

| Elemento | Situação |
|---|---|
| Cascas territoriais elipsoidais | removidas, com `territoryVolumes` e o teste que as prendia |
| Esferas wireframe por domínio | removidas |
| Anéis equatoriais | removidos |
| Piso circular | removido |
| Wireframe por estado `temporary` | removido — eram 278 painéis de quórum e 167 eventos ao vivo |
| Barra de modos `L/F/M/G/C` | fora da experiência |
| Painel lateral permanente | vira sobreposição mínima, fora da tela até `Esc` sem seleção |

Cada casca era discreta — opacidade 0,055 na esfera, 0,045 no wireframe, 0,09 no anel.
Três objetos por domínio, sempre ligados, e o conjunto passou a dizer que este produto
desenha grades em volta de coisas. Ficaram a névoa, que dá profundidade sem geometria, e
o painel.

**Cena global: 116 chamadas de desenho → 66; 30.904 triângulos → 21.476.**

## 2. Navegação (D2)

`WASD` desloca **câmera e alvo juntos**: a distância entre eles não muda, então voar
nunca colapsa a órbita nem atravessa o que se está olhando. Aproximar é a roda; `WASD` é
atravessar o espaço. A velocidade é proporcional à distância do alvo — passo fixo
obrigaria o usuário a gerenciar a própria velocidade, que é a complexidade que esta
navegação existe para não pedir. Tecla presa não sobrevive à perda de foco da janela.

Medido: 30 quadros com cada tecla deslocam câmera e alvo por 184,67 unidades, com
variação de distância **0,0000**.

**E cai o P1 mais agressivo da auditoria.** `orbit.minDistance` era a constante 12; com
`fov` de 38° isso mostra 14,7 × 8,3 unidades enquanto um MOC expandido mede 28,2 × 15,8.
O limite passa a sair do tamanho do alvo:

| | valor |
|---|---|
| Foco num MOC | 120,3 |
| Zoom máximo permitido | 47,0 |
| Janela visível a 47,0 | 57,6 × 32,4 |
| Painel expandido | 28,2 × 15,8 |

## 3. Deliberação em linguagem natural (D3, D4)

O dado estava em disco desde sempre — tarefa, proposta, avaliação por claim, questão
bloqueante, motivo, síntese. À cena chegava `panelId`, e por isso 278 painéis apareciam
como caixas vazias.

**A lista branca mudou de natureza, e isso é declarado.** Ela existia para impedir
resposta bruta de modelo, e cumpria isso recusando texto livre inteiro. A direção pede o
oposto: processo observável em linguagem natural. O que protege deixou de ser "nada de
texto" e passou a ser o sanitizador — `_resumo` recusa bloco de raciocínio e qualquer
coisa com forma de segredo, e corta o resto na fronteira de frase em vez de descartar por
comprimento. Chave fora da lista continua reprovando; `raw_response` continua sem caminho
por onde entrar. O afrouxamento tem teste próprio
(`test_texto_com_raciocinio_ou_segredo_nao_vira_frase_de_painel`).

**122 dos 278 nós operacionais** passam a ter deliberação legível.

Uma correção que só a cena mostrou: o esquema guarda `claim` com a afirmação e
`assessment` com o veredicto, muitas vezes uma palavra. Projetar o veredicto sozinho dava
"Examinou: supported" — pior que não dizer nada.

## 4. Execução real, de ponta a ponta

Rodada nesta sessão, não reaproveitada do histórico:

```
painel:      bd8c7ee51ffb
proponente:  google/gemini-3.5-flash-lite
avaliadores: google/gemini-3.1-flash-lite   [gemini; verificador-factual]
             ollama/minimax-m3              [minimax-m3; critico-epistemologico]
             ollama/gemma4:31b              [gemma4; revisor-estrutural]
decisão:     reject — falha estrutural objetiva registrada
```

O que a cena mostra, em `screenshots/d4-04-execucao-real-painel.png`:

- **Tarefa** — "Explique em duas frases por que ausência de evidência não implica refutação."
- **Proposta** — "A ausência de evidência indica apenas que um dado fenômeno ainda não foi observado ou documentado sob as condições atuais de investigação."
- **Voto favorável (google)** — "Examinou: … — Epistemologicamente correto; a ausência de evidência em um contexto específico não constitui prova de ausência. Este avaliador foi favorável, com 100% de confiança declarada."
- **Voto contrário (ollama)** — "Dificuldade: Cada claim deve possuir ID único no formato CLM-DOMINIO-TOPICO-NNN (ausente na proposta). Este avaliador foi contrário, com 100% de confiança declarada."
- **Decisão** — "A decisão computou 2 votos, representando 2 provedores e 2 famílias de modelo. Motivo: falha estrutural objetiva registrada. Próxima ação: recusar a proposta."

Nenhuma cadeia privada de pensamento aparece.

### O defeito que a execução revelou

O quórum não rodava. `gemma4:31b` é como a Ollama nomeia modelo e tag; o identificador
vira caminho de diretório de trabalho, e a validação recusava `:`. A execução morria
antes da primeira chamada, com uma mensagem que parecia de segurança e não era —
**nenhum endpoint da Ollama conseguia entrar em painel nenhum**. É provável que isso
explique parte da fila parada registrada como F-08.

O `:` não ajuda a escapar da raiz: quem escapa é `..` e a barra inicial, e ambos
continuam recusados, com a checagem de contenção intacta. A objeção que derrubou a
proposta veio justamente de um avaliador da Ollama.

## 5. Gates

| Item | Resultado |
|---|---|
| `make audit` | APROVADO, manifesto inalterado |
| `make test` | 390 pytest + 260 vitest |
| `make lint` | ruff, mypy, eslint limpos |
| `knowledge/` | intocado |
| Working tree | limpa |
| Segredos e raciocínio bruto | nenhum exposto |

## 6. O que não foi entregue

**O vídeo contínuo de 60–120 segundos não foi produzido.** Não é escolha: o ambiente não
tem `ffmpeg`, e a aba que audita não compõe quadros — é por isso que toda captura desta
série passa pelo endpoint que lê o canvas da própria aplicação. Um vídeo exigiria ou um
codificador instalado ou uma sessão de navegador que componha. As capturas cobrem os
mesmos oito momentos pedidos, quadro a quadro.

**A deliberação é observável depois da execução, não durante.** Os painéis são projetados
a partir dos artefatos persistidos, que o backend grava ao fim de cada etapa. Um painel
que se preenche progressivamente **enquanto** a IA trabalha exige o fluxo SSE carregando
os mesmos campos — o contrato de eventos existe (`runtimeLayer`), mas os campos de
linguagem natural ainda não viajam por ele. É o próximo passo natural, e não foi feito.

**Os estados de worker não são distinguidos visualmente.** `aguardando`, `trabalhando`,
`criticando`, `votando`, `concluído` e `falhou` existem no dado; a cena ainda os desenha
com a mesma aparência.

**A camada SSE continua sem representação própria** quando ligada — agora sem wireframe,
mas ainda uma massa de painéis sem hierarquia.
