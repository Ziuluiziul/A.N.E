# Handoff — Claude Opus 5, modo UltraCode — 2026-08-02

Estado factual e prompt de continuidade depois do Ciclo 2. Este arquivo pertence ao
mesmo commit funcional que introduz o watcher, endurece os comandos de provedor e
registra os resultados externos. O SHA do próprio commit não aparece aqui para não
criar circularidade.

## Como reconhecer o HEAD correto

O commit esperado é o filho direto de
`1731f3e50a24bb6c8556bd35cff39931e60fcf91`, com o assunto:

```text
Torne o corpus vivo e meça provedores sem ocultar falhas
```

Descubra o SHA real com `git rev-parse HEAD` e confira o pai com `git rev-parse
HEAD^`. Se HEAD tiver avançado, trate este handoff como histórico e audite os commits
posteriores antes de agir.

## Estado entregue

```text
repositório     /home/ziul/Projetos/vault-autodidata
branch          main
baseline pai    1731f3e50a24bb6c8556bd35cff39931e60fcf91
tag baseline    baseline-pos-migracao-2026-07-30 -> 7aa5db153dc3cf185f5046fa93203673e6809adc
corpus          81 notas · 627 wikilinks · 267 claims
manifesto       4f5b1d009041583c89957f7c22199d8d77836f4441f7e6aa16e741da8b2bf5bb
testes          163 pytest · 59 vitest
gates           audit, ruff, mypy, tsc, eslint e build limpos
status ciclo    PARTIAL somente pela disponibilidade externa
```

O relatório canônico é
`docs/CICLO-2-WATCHER-E-PROVEDORES-2026-08-02.md`. Ele contém a lista exata dos 175
endpoints, decisões de implementação, resultados, hashes, permissões, pendências e
comandos executados.

## O que foi concluído

- watcher único no lifespan da API, com leitura estável antes/depois, última projeção
  válida e SSE `current`, `changed`, `error` e `recovered`;
- `touch` sem mudança de bytes não cria revisão;
- transição espacial explícita preserva posições, completa apenas ausentes e poda
  removidos; falha do cache não bloqueia uma projeção válida;
- frontend persiste o layout antes de assinar SSE e só recarrega diante de outro
  SHA-256 válido;
- `PUT` de layout aceita apenas o fingerprint vivo e deriva fingerprint e IDs do
  mesmo snapshot validado;
- descoberta e smoke separados: uma requisição por provedor por comando, zero retry,
  primeira página Google limitada a 1.000 e parada global em 429;
- evidências externas sanitizadas, atômicas, em arquivo `0600` e diretório `0700`;
- `knowledge/` permaneceu intocado.

## Chamadas externas já consumidas — não repetir

`make discover-models`, `make smoke-providers` e `make workspace-oauth` já foram
executados uma vez neste ciclo. Não os use como comandos de verificação.

| Provedor | Descoberta | Sonda única |
| --- | ---: | --- |
| Google | 58 endpoints | `antigravity-preview-05-2026`: HTTP 503, 473 ms |
| Groq | 15 endpoints | `allam-2-7b`: `ok`, 448 ms |
| NVIDIA | 102 endpoints | `01-ai/yi-large`: HTTP 404, 867 ms |

Não houve 429 nem retry. O detalhe privado da NVIDIA contém identificador de conta e
não deve ser copiado para resposta, issue ou documento. As três chaves estavam
presentes, mas nenhum valor foi exposto. O Workspace continua sem `client_secret` e
o OAuth terminou pelo ramo curto, antes de rede ou navegador.

Evidências locais ignoradas pelo Git:

```text
runtime/state/models-discovery.json
runtime/state/models-google-2026-08-02T232703Z.json
runtime/state/models-groq-2026-08-02T232703Z.json
runtime/state/models-nvidia-2026-08-02T232703Z.json
runtime/logs/smoke-providers.json
```

Se esses arquivos ainda existirem, leia-os localmente e nunca publique conteúdo
sensível. Os hashes estão no relatório do Ciclo 2.

## Corrigido depois deste ciclo — leia antes de confiar na lista acima

Este handoff apresentou o watcher como concluído e **omitiu uma limitação real**: a
reconciliação espacial não sobrevivia ao encerramento do processo. `carry_forward` só
rodava com uma impressão de origem em memória, e no primeiro cálculo após o restart
ela é `None` — um corpus editado com o backend desligado perdia todas as posições.

O Ciclo 2.1 fechou isso persistindo a última impressão conhecida em
`runtime/state/layout/last-fingerprint.json` e acrescentou `asyncio.Lock` a
`refresh()`. Ver `docs/CICLO-2.1-CONTINUIDADE-ESPACIAL-2026-08-02.md`. A classificação
do Ciclo 2 permanece PARTIAL, porque a causa dela — Google 503 e NVIDIA 404 — não foi
tocada.

## Pendências que continuam reais

1. Google 503 e NVIDIA 404 impedem declarar os três provedores operacionais. Nova
   sonda, outro endpoint ou investigação de conta exigem autorização explícita e um
   novo orçamento de chamadas; não trate este handoff como autorização.
2. Workspace não pode avançar sem `client_secret` e consentimento interativo.
3. O Writer Gateway ainda não existe. Nenhum componente ganhou permissão de escrita
   em `knowledge/`. Decisão de Luiz: fica para o Ciclo 3, com especificação aprovada
   antes do código, e dois refinamentos já pedidos — `failed` precisa separar falha
   antes da aplicação de falha após promoção, e os gates de bibliografia e claims
   devem ser configuráveis por tipo de patch, não universais.
4. O manifesto privado de descoberta referencia snapshots pelo nome; validar hashes
   internamente antes do smoke e fazer `fsync` do diretório são endurecimentos
   possíveis, não bloqueadores deste ciclo.

## Artefatos finais

O bundle e o tarball deste commit são gerados somente depois do commit. Seus nomes
levam o SHA abreviado; hashes ficam nos `.sha256` adjacentes e em um manifesto externo
sob `~/Documentos/Backups/Vault/2026-08-02/`. Confira esse manifesto em vez de esperar
hashes dentro do Git.

## Prompt pronto para colar

```text
Você é Claude Opus 5 em modo UltraCode e tem acesso local ao repositório
/home/ziul/Projetos/vault-autodidata.

Comece por orientação somente leitura. Confira `git rev-parse HEAD`, branch, pai,
assunto e working tree. O HEAD esperado é filho direto de
1731f3e50a24bb6c8556bd35cff39931e60fcf91 e tem o assunto
"Torne o corpus vivo e meça provedores sem ocultar falhas". O SHA do próprio commit
não está hardcoded no handoff. Se houver commits posteriores, descubra-os antes de
usar este estado como presente.

Leia integralmente:
- AGENTS.md
- docs/CICLO-2-WATCHER-E-PROVEDORES-2026-08-02.md
- docs/HANDOFF-CLAUDE-OPUS-5-ULTRACODE-2026-08-02.md
- docs/CICLO-1.1-FECHAMENTO-ATLAS-2026-08-02.md
- docs/ADR-001-paleta-oklch.md

Rode somente os gates locais `make audit`, `make test`, `make lint` e o build do
frontend. Confirme 81 notas, 627 wikilinks, 267 claims, manifesto 4f5b1d00…, 163
pytest e 59 vitest. Confirme também que knowledge/ não mudou, a tag baseline não se
moveu e os artefatos externos do HEAD passam nas verificações descritas no manifesto
de backup.

NÃO execute `make discover-models`, `make smoke-providers` nem
`make workspace-oauth`: os três já foram consumidos neste ciclo. Não faça outra
chamada de provedor, não abra OAuth, não copie valores de credencial e não publique o
identificador de conta presente no erro NVIDIA.

Depois da orientação, entregue uma revisão curta com:
1. qualquer inconsistência factual entre HEAD, relatório, handoff e artefatos;
2. riscos residuais do watcher e da reconciliação espacial, separados de preferência;
3. um plano de uma única chamada por provedor para investigar Google 503 e NVIDIA
   404, mas sem executá-lo;
4. a menor especificação útil para o Writer Gateway: fronteira de autorização,
   estados, evento de procedência, validação de patch e rollback;
5. a decisão que Luiz precisa tomar para abrir o próximo ciclo.

Regras inegociáveis: knowledge/ é somente leitura; saída de modelo nunca entra direto
no corpus; nenhum framework esconde o fluxo; nenhum commit antes de apresentar diff
e obter aprovação; nada de reset, clean, rebase ou movimentar a tag baseline.

Comece a resposta por STATUS: PASS, STATUS: PARTIAL ou STATUS: BLOCKED. Não altere
arquivos nesta primeira passagem. Se o estado estiver coerente, pare após a revisão e
aguarde Luiz escolher o próximo escopo.
```
