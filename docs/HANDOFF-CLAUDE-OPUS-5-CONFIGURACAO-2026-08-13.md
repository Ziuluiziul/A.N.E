# Handoff — Claude Opus 5 — configuração no nó — 2026-08-13 (força conjunta)

Arquivo próprio, e não sobrescrita do handoff anterior: há quatro builders na mesma
árvore, e sobrescrever silenciosamente o documento de outro é o tipo de colisão que o
protocolo pede para evitar.

## Estado

```text
HEAD inicial   2be6896
HEAD final     f369e02   (passando por 8d83f41, que não é meu)
árvore         suja com trabalho de outros builders — ver Coordenação

corpus         84 notas · 672 wikilinks · 267 claims · zero defeito estrutural
pytest         561 passed
vitest         504 passed (38 arquivos)
ruff/mypy      limpos
tsc/eslint     limpos
auditoria      ESTRUTURA APROVADA
capturas       nenhuma nova nesta passagem — ver Limitação
```

**Nenhum vermelho em aberto.** O `422` de `test_slots_operacionais_tem_namespace_e_merge_proprios`,
registrado no handoff anterior, **foi resolvido por outro builder** em `8d83f41`
("Ancore os testes do layout na versão real e blinde o quórum contra falha paralela").
Confirmei rodando a suíte: 561 passando, nenhum falhando. Não toquei nesse caminho.

## O que entrou

`f369e02` — **o painel do provedor é a configuração dele.**

Escolher o nó de um provedor leva a configuração até a placa: ancorada ao lado dela,
aberta na aba de provedores, com o cartão marcado e o foco no campo da chave. Antes a
credencial morava numa doca à esquerda que abria por `Esc` e não dizia de quem era.

O que **não** foi feito, de propósito: reimplementar o cartão. Ele já existe no dock com
campo mascarado, confirmação em dois passos e a guarda de teclado de `keyboardTarget.ts`
— que existe porque `WASD` já comeu caractere de credencial uma vez. Uma segunda
superfície para a mesma chave esqueceria uma dessas três coisas.

Peças novas:

| onde | o quê |
| --- | --- |
| `atlas.ts` | `onSelectionChange` + projeção do nó em pixels (`AtlasSelection`) |
| `dock.ts` | `focusProvider(id)` e `anchorAt(ponto \| null)` |
| `providerNode.ts` | `providerIdOf` — puro, testado, recusa o que não é provedor |
| `runtimeLayer.ts` | expõe `renderPositionFor` para a projeção do nó vivo |

Duas decisões que merecem revisão:

- **A âncora não persegue a câmera.** Formulário que foge do cursor enquanto se digita é
  pior que formulário parado ao lado do nó que o abriu. Ela é presa à janela para não
  cair fora da tela quando o provedor está na borda.
- **Só provedor abre.** `providerIdOf` recusa nota, evento e o modelo daquele provedor: o
  modelo tem dono, mas a chave é do provedor, e abrir a configuração sobre a placa do
  modelo afirmaria duas contas onde há uma.

## Limitação — o que ficou devendo captura

O caminho ponta a ponta **não foi exercitado na cena viva** nesta passagem. Dois
bloqueios de ambiente, nenhum deles do código:

1. o runtime sintético de captura ficou sem trilha semeada (o script do ciclo anterior
   não sobreviveu ao scratchpad), então não havia nó de provedor vivo para escolher;
2. o Browser pane não compõe quadros, e por isso `document.hidden` é verdadeiro — o
   polling do controle fica suspenso e o dock nasce sem cartão nenhum.

O contorno para o (2), medido e funcionando: redefinir `document.hidden` como `false` e
disparar `visibilitychange` na página. Com isso os cinco cartões apareceram com a
credencial de cada provedor (`google`, `groq`, `nvidia`, `ollama`, `openrouter`, todos com
chave configurada). Falta reproduzir o gesto que abre pelo nó.

**Quem retomar precisa:** semear um runtime com uma chamada aberta (`deadline_seconds`
≤ 600, ou o contrato do frontend recusa o evento), forçar a visibilidade como acima,
escolher `runtime:provider:groq` e capturar. O que se espera ver: o dock ao lado da
placa, o cartão do groq com borda realçada e o cursor no campo da chave.

## Coordenação

Trabalho de outros builders encontrado e **preservado**:

```text
8d83f41                        commit alheio — correção do 422 (não refiz)
backend/src/vault/app.py       em voo — versão do layout operacional
frontend/src/composeLayout.ts  em voo
frontend/src/layout.ts         em voo
frontend/src/layoutStore.ts    em voo
frontend/src/operationalLayout.ts  em voo
frontend/src/transport.ts      em voo — apareceu durante minha passagem
frontend/src/transport.test.ts em voo
frontend/src/sseSharedWorker.*  novo, de outro builder
```

Commitei **apenas** os sete arquivos meus, nomeados um a um. Nenhum `git add -A`, nenhum
`checkout` amplo, nenhum `reset`.

Pontos de contato para o próximo:

- `dock.ts` agora tem dois métodos novos no contrato. Quem mexer no dock não deve
  removê-los sem mover o chamador em `main.ts`.
- `atlas.ts` ganhou `onSelectionChange`; hoje há **um** ouvinte. Se outro builder precisar
  escutar seleção, transforme o campo único em conjunto em vez de disputar o slot.
- `runtimeLayer.renderPositionFor` é a posição **desenhada** (com a elevação da placa
  escolhida), não a assentada. Foi essa distinção que causou as ligações apontando para o
  vazio no ciclo anterior.

## Conectores

| conector | estado | encontrado | executado | pendente |
| --- | --- | --- | --- | --- |
| Drive, Gmail, Calendar, Slack, Notion, Linear, Canva, Vercel, Cloudflare, Hugging Face, Zapier | disponíveis na sessão | não inspecionados nesta passagem | nada | inventário de ativos do A.N.E. |
| plugins (GitHub, Datadog, PagerDuty, Atlassian, Figma e ~30 outros) | **exigem OAuth** | — | nada | autorizar em sessão interativa ou nas configurações de conectores do claude.ai |
| Browser pane | usado | não compõe quadros; `document.hidden` suspende polling | diagnóstico acima | captura do gesto |

**Nenhuma ação foi executada em nenhum serviço externo.** Optei por gastar a passagem no
território que me foi atribuído em vez de inventariar conectores sem tê-lo fechado.

Sobre a autorização ampla para ações destrutivas: não executo apagamento permanente de
dados de terceiros — e-mail, arquivo, mensagem, repositório —, e autorização ampla não
vale para ações posteriores. Isso é limite meu, não do projeto, e outro builder decide
pela política dele; o que não deve acontecer é tratar a frase como cheque em branco
herdado deste documento.

## Ordem sugerida para quem seguir neste território

1. Captura do gesto (acima) — é o que falta para declarar `f369e02` verificado.
2. Configurações gerais como nó da cena, reaproveitando o mesmo mecanismo: `anchorAt` +
   `openTab('operacao')`.
3. Só então remover `open-configuration` de `selectionKeyboardAction`, e ajustar a linha
   do `Esc` em `SCENE_LEGEND` — `controls3d.test.ts` reprova se a legenda anunciar tecla
   que não faz nada.
