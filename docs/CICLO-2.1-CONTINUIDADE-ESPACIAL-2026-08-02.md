# Ciclo 2.1 — Continuidade espacial através do reinício — 2026-08-02

Escopo fechado por decisão de Luiz: corrigir a continuidade da memória espacial depois
que o backend reinicia, e nada além disso. Writer Gateway e sondas dirigidas de Google
e NVIDIA ficaram deliberadamente fora deste diff.

**Resultado: PASS.**

## 1. O defeito

O Ciclo 2 entregou a reconciliação espacial correta para uma sessão viva: a transição
vai de uma impressão de origem **declarada** para uma de destino, e nunca escolhe o
snapshot mais recente por data — o que preserva a barreira entre corpora distintos.

O relatório, porém, não demonstrava como a origem é recuperada depois de um reinício,
e o handoff apresentava o watcher como concluído sem registrar a limitação. Não era
demonstrável porque não acontecia:

```python
old_fingerprint = self._fingerprint          # None no primeiro refresh do processo
if old_fingerprint is not None:
    carry_forward(old_fingerprint, new_fingerprint, known_ids=...)
```

No primeiro cálculo após o restart a impressão em memória é `None`, então a transição
simplesmente não ocorria. Consequência: **editar uma nota com o backend desligado
apagava todas as posições**, em silêncio. Era um defeito, não preferência de
arquitetura — e atingia justamente a garantia que o Ciclo 1.1 existiu para criar.

## 2. A correção

### 2.1. Ponteiro da última impressão conhecida

`LayoutStore.remember_fingerprint` e `LayoutStore.last_fingerprint`, gravando em
`runtime/state/layout/last-fingerprint.json`:

```json
{ "schemaVersion": 1, "corpusFingerprint": "<64 hexadecimais>", "updatedAt": "…" }
```

| Requisito | Como foi atendido |
| --- | --- |
| Fora de `knowledge/` | vive em `runtime/state/layout/`, junto dos snapshots, e `runtime/` é ignorado pelo Git |
| Escrita atômica | a mesma rotina do `save`, extraída para `_write_atomic`: temporário no diretório e `os.replace`, com `fsync` antes |
| Schema versionado | `POINTER_SCHEMA_VERSION`; versão diferente é tratada como ausência |
| Validação estrita de SHA-256 | 64 hexadecimais na gravação **e** na leitura; gravar qualquer outra coisa levanta `LayoutStoreError` |
| Recuperação silenciosa | JSON inválido, truncado, vazio, schema estranho, impressão fora do formato ou de tipo errado devolvem `None` |

O nome do arquivo está fora do formato de impressão de propósito: `_path` recusa
qualquer nome que não sejam 64 hexadecimais, então **nenhum `save` consegue
sobrescrever o ponteiro**.

### 2.2. Uso na primeira projeção após o restart

```python
old_fingerprint = self._fingerprint
if old_fingerprint is None:
    old_fingerprint = await asyncio.to_thread(self.layout_store.last_fingerprint)
```

O resto do fluxo já estava certo e não mudou: impressão igual reutiliza o snapshot
existente; impressão diferente chama `carry_forward(origem, destino)`, que preserva as
entidades conhecidas, deixa as novas sem posição — para o layout do frontend as
colocar localmente — e poda as removidas por `known_ids`. A origem continua declarada;
data de modificação nunca entra na decisão.

Toda publicação bem-sucedida reanota o ponteiro. Falha ao anotar vira erro visível no
SSE, mas **não** decide qual versão do corpus a API serve: o ponteiro é cache
derivado, como o próprio layout.

### 2.3. Lock em `refresh()`

`asyncio.Lock`, com o corpo movido para `_refresh_locked`. Não havia corrida
comprovada — `refresh` só é chamado de `start()` e do laço de `awatch`, em sequência.
O lock existe para que a sequencialidade seja invariante do método em vez de
consequência de quem por acaso o chama. O método atravessa três `await` e escreve
`_projection`, `_fingerprint`, `_revision` e `_last_error`; um endpoint de recarga
manual, acrescentado no futuro sem esse cuidado, intercalaria essas escritas.

## 3. Testes

`tests/test_restart_continuity.py`, 22 testes. Cada um **reinicia de verdade**:
constrói watcher e store novos sobre o mesmo diretório de runtime. Reaproveitar o
objeto anterior testaria a memória do processo, que nunca esteve em dúvida.

| Teste mínimo pedido | Situação |
| --- | --- |
| Reinício sem alteração preserva todas as coordenadas | coberto |
| Corpus alterado offline preserva entidades anteriores | coberto, com igualdade exata do mapa |
| Nota nova offline recebe somente colocação local | coberto; ela não aparece no snapshot |
| Nota removida offline desaparece após reinício | coberto |
| Último fingerprint ausente inicia corretamente | coberto |
| Último fingerprint corrompido não impede a projeção | coberto, em seis formas de corrupção |
| Fingerprint persistido sem layout correspondente não inventa posições | coberto |
| Dois `refresh()` concorrentes não intercalam | coberto, em dois cenários |
| Falha no store não bloqueia a verdade do corpus | coberto |
| `knowledge/` byte a byte intacto | coberto, no corpus sintético e no real |

Um teste extra prende a regra que o Ciclo 2 já declarava e ninguém verificava: com um
snapshot alheio gravado **depois** — portanto o mais recente por data —, a origem
continua sendo a anotada, e não a mais nova.

O teste de concorrência é o que dá sentido ao lock: sem ele, dois `refresh()`
simultâneos num watcher recém-criado veriam ambos `fingerprint is None` e publicariam
revisões próprias. Com ele, `revision == 1`.

## 4. Prova de ponta a ponta

Fora da suíte, num diretório temporário:

```text
sessão 1  impressão: 6ee8b784891e | Entropia em (42, 24, 3)
          [backend encerrado; nota nova escrita no corpus]
sessão 2  impressão: d94b9a21764b | mudou: True
          Entropia preservada: Position(x=42.0, y=24.0, z=3.0, pinned=False)
          Pressão sem posição (colocação local): True
```

Antes desta correção, a segunda sessão devolveria um mapa vazio.

## 5. Verificação

| Verificação | Resultado |
| --- | --- |
| `python3 tools/audit.py` | APROVADO — 81 / 627 / 267, manifesto `4f5b1d00…` |
| `uv run pytest` | **185 passaram** (eram 163) |
| `uv run ruff check .` | limpo |
| `uv run mypy` | limpo, 44 arquivos |
| `pnpm run typecheck` | limpo |
| `pnpm run lint` | limpo |
| `pnpm run test` | 59 passaram, inalterados |
| `pnpm run build` | íntegro |

`knowledge/` não aparece no diff. Nenhuma chamada externa foi feita: `discover-models`,
`smoke-providers` e `workspace-oauth` continuam com exatamente uma execução, a do
Ciclo 2. Nenhum servidor foi iniciado.

## 6. Classificação preservada

```text
Ciclo 2 funcional ................ PASS
Disponibilidade dos provedores ... PARTIAL
Estado agregado do Ciclo 2 ....... PARTIAL
Ciclo 2.1 ........................ PASS
```

O Ciclo 2 **não** é reclassificado. A causa do `PARTIAL` dele — Google 503 e NVIDIA
404 — não foi tocada, e nada neste ciclo a toca.

## 7. Pendências

1. **Sondas dirigidas de Google e NVIDIA** (Ciclo 2.2), mediante autorização expressa.
   A hipótese de que os resultados vieram da escolha alfabética do endpoint — um
   `preview` no Google, uma família antiga na NVIDIA — continua sendo hipótese: o que
   está provado é apenas que aqueles dois endpoints responderam 503 e 404.
2. **Writer Gateway** (Ciclo 3), com especificação aprovada antes do código, incluindo
   os dois refinamentos pedidos: separar falha antes da aplicação de falha após
   promoção, e tornar os gates de bibliografia e claims configuráveis por tipo de
   patch em vez de universais.
3. **Custo de leitura do watcher**: cada tentativa de projeção estável faz duas
   varreduras de impressão além do `build_projection`, que relê o corpus por conta
   própria. Imperceptível em 81 notas; com o corpus uma ordem de grandeza maior, vale
   reaproveitar a impressão que o `build_projection` já calcula.

## 8. Reproduzir

```bash
make audit && make test && make lint
```

```bash
uv run pytest -q tests/test_restart_continuity.py
```
