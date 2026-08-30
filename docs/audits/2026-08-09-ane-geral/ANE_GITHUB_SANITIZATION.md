# Sanitização obrigatória antes de publicar o A.N.E.

## Classificação

**NOT READY**.

[OBSERVADO] O repositório não tem remote; nenhum dado foi publicado por este Git. A
lista é preventiva e deve ser concluída antes do primeiro `git push` público.

## Bloqueadores, em ordem

1. [OBSERVADO] **Fechar os dois vazamentos de credencial candidata (F-01).** Remover
   `input` de erros 422, redigir com a candidata além dos secrets já configurados e
   testar respostas, logs e tracebacks nos quatro provedores. Não usar uma chave real no
   teste.
2. [OBSERVADO] **Escolher e registrar licenças separadas.** Não existe `LICENSE`.
   Decidir licença do software, do corpus autoral e das evidências/capturas; adicionar
   avisos de terceiros e proveniência de `tools/atlas.svg`. Sem licença, o copyright
   padrão não concede permissão geral de reutilização/distribuição.
3. [OBSERVADO] **Atualizar dependências afetadas.** `cryptography 49.0.0` → versão
   corrigida compatível (`>=50.0.0` para o advisory observado), `brace-expansion 5.0.8`
   → `>=5.0.9`, `nanoid 3.3.16` → `>=3.3.17`; repetir audit/test/lint e scanners.
4. [OBSERVADO] **Reconciliar a governança pública.** Política, AGENTS, README,
   `ProposalStore`, `/proposals`, worker e Promoter descrevem caminhos diferentes.
   Publicar só depois de existir uma regra única e demonstrada de promoção.

## Privacidade e histórico

5. [MEDIDO] Substituir/revisar as 22 ocorrências de `/home/ziul` em nove documentos,
   removendo em especial caminhos de backup pessoal. Um username local não é segredo,
   mas é dado pessoal desnecessário.
6. [OBSERVADO] Decidir conscientemente se o e-mail autoral dos 94 commits e os trailers
   de coautoria em 67 podem ficar públicos. Se não, a única correção completa exige
   reescrita em clone descartável antes do primeiro push; isso não foi autorizado nem
   executado nesta auditoria.
7. [OBSERVADO] Excluir do produto público os cinco handoffs e cinco prompts antigos,
   além do prompt mestre não rastreado de 09/08. Preservar externamente apenas se houver
   finalidade e sanitização.
8. [MEDIDO] Retirar a auditoria antiga do histórico principal ou mantê-la como artefato
   externo: 32 PNGs somam 13,60 MiB e o diretório ocupa 13,72 MiB, 84,4% dos bytes
   rastreados. Revisar visualmente privacidade e direitos; ausência de EXIF não basta.
9. [OBSERVADO] Não incluir `.git`, o ZIP ignorado, `runtime/`, `.venv`, `node_modules`,
   caches, builds, `frontend/public/projection.json`, `.vscode` nem arquivos de segredo.

## Documentação mínima pública

10. [OBSERVADO] Reescrever README com números atuais (84/672/267), arquitetura real,
    estado Alpha honesto, requisitos Python/uv/Node/pnpm, origem configurável do backend,
    modo offline e comandos verificados.
11. [OBSERVADO] Atualizar/superseder ADR-002 e remover referências a L/F/M, famílias
    agregadas, ausência de HUD e outros estados que não correspondem ao frontend atual.
12. [OBSERVADO] Adicionar `SECURITY.md` com canal de reporte, `CONTRIBUTING.md` com gate
    e fronteira do corpus, e opcionalmente `CODE_OF_CONDUCT`. `.env.example` já existe e
    não contém valores.
13. [OBSERVADO] Declarar versões suportadas, política de dados locais/telemetria e que o
    worker é processo separado. Não apresentar snapshot de worker como processo vivo.

## Varredura de segurança a repetir imediatamente antes do push

```bash
git ls-files -z | xargs -0 grep -lnE 'AIza|gsk_|nvapi-|sk-[A-Za-z0-9]|ya29\.|-----BEGIN' 2>/dev/null
git log --all -p -S'AIza' --oneline
git log --all --diff-filter=A --name-only | grep -iE '\.env|secret|credential|token'
git ls-files | grep -E 'node_modules|\.venv|__pycache__|dist/|runtime/'
UV_CACHE_DIR=/tmp/ane-publish-cache uv run --with pip-audit pip-audit
(cd frontend && pnpm audit)
make audit && make test && make lint
```

[OBSERVADO] Os matches atuais de formatos de chave são usos legítimos ou valores
sintéticos em testes; nenhum valor real foi identificado. [NÃO VERIFICADO] As regexes
não detectam secrets sem formato/ofuscados, portanto a revisão humana de diff, imagens e
artefatos continua obrigatória.

## Critério de saída

[INFERIDO] Reclassificar como `READY AFTER SANITIZATION` só quando os quatro bloqueadores
iniciais tiverem evidência de fechamento e existir um conjunto público exato. Usar
`PUBLIC READY` somente depois de gerar esse conjunto em clone limpo, repetir as buscas e
gates, revisar a lista de arquivos e obter decisão explícita sobre licenças e identidade
Git.

## Decisão desta auditoria sobre os pacotes

[OBSERVADO] `ANE_AUDIT_PACKAGE.tar.gz` e `ANE_REVIEW_SNAPSHOT.tar.gz` não incluem
`knowledge/` em texto, `.git`, runtime bruto, credenciais, dependências, caches, build,
documentos pessoais históricos ou o ZIP antigo. Incluem apenas estrutura/hash/contagens
do corpus, código e evidência técnica sanitizada. Caminhos absolutos são substituídos por
`$REPO` dentro das cópias compartilháveis quando aplicável.
