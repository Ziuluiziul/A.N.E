# Handoff — GPT-5.6 SOL, modo ultra — 2026-08-02

Estado depois do Ciclo 2.1 e prompt de continuidade. O SHA deste commit não aparece
aqui: um documento não pode conter o identificador do commit que o contém sem que a
gravação mude o identificador.

## Como reconhecer o HEAD correto

O commit esperado é filho direto de
`cdc407c3df041ebefd1c99b310c85603940ae676`, com o assunto:

```text
Faz a memória espacial sobreviver ao reinício do backend
```

Descubra o SHA real com `git rev-parse HEAD` e confira o pai com `git rev-parse HEAD^`.
Se houver commits posteriores, trate este handoff como histórico e audite o que veio
depois antes de agir.

## Estado entregue

```text
repositório     /home/ziul/Projetos/vault-autodidata
branch          main
pai             cdc407c3df041ebefd1c99b310c85603940ae676
tag baseline    baseline-pos-migracao-2026-07-30 -> 7aa5db153dc3cf185f5046fa93203673e6809adc
corpus          81 notas · 627 wikilinks · 267 claims · 12 MOCs · 11 domínios
manifesto       4f5b1d009041583c89957f7c22199d8d77836f4441f7e6aa16e741da8b2bf5bb
testes          185 pytest · 59 vitest
gates           audit, ruff, mypy, tsc, eslint e build limpos
```

Classificação vigente, que **não** muda por causa deste ciclo:

```text
Ciclo 2 funcional ................ PASS
Disponibilidade dos provedores ... PARTIAL
Estado agregado do Ciclo 2 ....... PARTIAL
Ciclo 2.1 ........................ PASS
```

## O que o Ciclo 2.1 fechou

A reconciliação espacial não sobrevivia ao encerramento do processo: `carry_forward`
só rodava com uma impressão de origem em memória, e no primeiro cálculo após o restart
ela é `None`. Editar uma nota com o backend desligado apagava todas as posições, em
silêncio.

- ponteiro da última impressão em `runtime/state/layout/last-fingerprint.json`, com
  schema versionado, escrita atômica e validação estrita de 64 hexadecimais;
- ausência ou corrupção do ponteiro devolvem "não havia origem" e o Atlas recalcula;
- a origem continua **declarada**, nunca escolhida por data de modificação;
- `asyncio.Lock` em `refresh()`, tornando a sequencialidade invariante do método;
- 22 testes que reiniciam de verdade, com watcher e store novos sobre o mesmo disco.

Detalhes em `docs/CICLO-2.1-CONTINUIDADE-ESPACIAL-2026-08-02.md`.

## Chamadas externas — não repetir

`make discover-models`, `make smoke-providers` e `make workspace-oauth` foram
executados **uma vez**, no Ciclo 2, e não foram reexecutados no Ciclo 2.1. Não os use
como comando de verificação.

| Provedor | Descoberta | Sonda única |
| --- | ---: | --- |
| Google | 58 endpoints | `antigravity-preview-05-2026`: HTTP 503 |
| Groq | 15 endpoints | `allam-2-7b`: `ok` |
| NVIDIA | 102 endpoints | `01-ai/yi-large`: HTTP 404 |

O detalhe privado devolvido pela NVIDIA contém identificador de conta e não pode ser
copiado para resposta, documento ou issue.

## Ordem decidida por Luiz

```text
Ciclo 2.1 — Continuidade espacial através de restart   CONCLUÍDO
Ciclo 2.2 — Sondas dirigidas de Google e NVIDIA        exige autorização expressa
Ciclo 3   — Writer Gateway                             exige especificação aprovada
```

**Este handoff não é autorização para nada disso.** O Ciclo 2.2 depende de Luiz
liberar um orçamento novo de chamadas; o Ciclo 3 depende de uma especificação aprovada
antes de existir código.

## O que Luiz já exigiu da especificação do Writer Gateway

Duas correções sobre o esboço anterior, que precisam estar na proposta:

1. `failed` não pode ser um estado terminal indistinto. Falha **antes** da aplicação e
   falha **após** a promoção são situações diferentes, com consequências diferentes, e
   precisam de estados separados.
2. Bibliografia resolvida e claims válidos devem ser gates **configuráveis por tipo de
   patch**, não condições universais para qualquer alteração editorial ou estrutural.
   Corrigir uma vírgula não pode exigir os mesmos gates que introduzir um claim novo.

## Prompt pronto para colar

```text
Você é o GPT-5.6 SOL em modo ultra, com acesso local ao repositório
/home/ziul/Projetos/vault-autodidata.

ORIENTAÇÃO, ANTES DE QUALQUER COISA

Confira `git rev-parse HEAD`, o pai, o assunto, o branch e a working tree. O HEAD
esperado é filho direto de cdc407c3df041ebefd1c99b310c85603940ae676 e tem o assunto
"Faz a memória espacial sobreviver ao reinício do backend". O SHA não está gravado
dentro do próprio commit. Se houver commits posteriores, descubra o que mudou antes de
tratar este estado como presente.

Leia integralmente:
- AGENTS.md
- docs/CICLO-2.1-CONTINUIDADE-ESPACIAL-2026-08-02.md
- docs/CICLO-2-WATCHER-E-PROVEDORES-2026-08-02.md
- docs/HANDOFF-GPT-5.6-SOL-2026-08-02.md
- docs/CICLO-1.1-FECHAMENTO-ATLAS-2026-08-02.md
- docs/ADR-001-paleta-oklch.md

Rode somente os gates locais: `make audit`, `make test`, `make lint` e o build do
frontend. Confirme 81 notas, 627 wikilinks, 267 claims, manifesto 4f5b1d00…, 185
pytest e 59 vitest, que knowledge/ não mudou e que a tag baseline não se moveu.

NÃO execute `make discover-models`, `make smoke-providers` nem `make workspace-oauth`.
Não faça nenhuma chamada de provedor, não abra OAuth, não copie valor de credencial e
não reproduza o identificador de conta presente no erro da NVIDIA.

TAREFA DESTE CICLO — ESPECIFICAÇÃO DO WRITER GATEWAY, SEM CÓDIGO

Produza `docs/SPEC-WRITER-GATEWAY-<data>.md`. É documento, não implementação: nenhum
módulo novo, nenhuma dependência, nenhuma alteração em código existente. O Writer
Gateway só ganha código depois que Luiz aprovar a especificação.

A especificação precisa fechar, com precisão suficiente para virar código sem
reinterpretação:

1. FRONTEIRA DE AUTORIZAÇÃO. Quem pode escrever em knowledge/, por qual caminho, e
   como o restante do sistema fica estruturalmente impedido de escrever — não por
   convenção, por construção. Diga o que acontece se alguém tentar contornar.

2. MÁQUINA DE ESTADOS. Estados, transições permitidas e quais são terminais. Falha
   antes da aplicação e falha após a promoção são estados distintos: nomeie os dois,
   diga o que cada um permite fazer em seguida, e o que fica preservado em cada caso.

3. EVENTO DE PROCEDÊNCIA. Esquema completo e versionado, campo a campo, com tipos.
   Onde é gravado, em que formato, com que garantias de atomicidade e ordenação. O que
   nunca entra nele — em particular, raciocínio interno de modelo.

4. VALIDAÇÃO DE PATCH POR TIPO. Defina os tipos de patch que existem (no mínimo:
   correção editorial, alteração estrutural, claim novo, referência nova) e monte a
   matriz de gates por tipo. Bibliografia resolvida e unicidade de claim não podem ser
   universais. Justifique cada gate que for opcional: quem o dispensa, e sob qual
   critério.

5. ROLLBACK. Como se desfaz cada classe de falha, incluindo a que ocorre depois da
   promoção. Nada de `git reset` nem `git clean`; a tag baseline nunca se move.

6. INVARIANTES VERIFICÁVEIS. Liste os testes que a implementação futura terá de
   passar, em linguagem de asserção, não de intenção. Inclua pelo menos um que prove
   que um agente sem passar pelo gateway não consegue escrever.

7. O QUE FICA DE FORA. Diga explicitamente o que a especificação não cobre e por quê.

REGRAS INEGOCIÁVEIS

- knowledge/ é somente leitura neste ciclo. Nem para exemplo, nem para teste.
- Saída de modelo nunca entra direto no corpus.
- Nada de LangChain, CrewAI, AutoGen, Docker, banco externo ou framework que esconda
  o fluxo.
- Proibidos git reset --hard, git clean, git checkout -- ., rebase de commits
  existentes e mover a tag baseline.
- Nenhum commit antes de apresentar o diff e obter aprovação de Luiz.
- Encerre pelos PIDs próprios qualquer processo que você inicie; nunca pkill genérico.

ENTREGA

Comece a resposta por STATUS: PASS, STATUS: PARTIAL ou STATUS: BLOCKED. Não declare
PASS por aproximação — se um dos sete pontos ficou incompleto, é PARTIAL, e diga qual.
Depois da especificação, pare e aguarde Luiz aprovar antes de escrever qualquer código.
```

## Artefatos

Bundle e tarball deste commit são gerados **depois** dele. Os nomes levam o SHA
abreviado, os SHA-256 ficam nos `.sha256` adjacentes, e há um manifesto externo em
`~/Documentos/Backups/Vault/2026-08-02/`. Confira esse manifesto em vez de esperar
hashes dentro do Git.
