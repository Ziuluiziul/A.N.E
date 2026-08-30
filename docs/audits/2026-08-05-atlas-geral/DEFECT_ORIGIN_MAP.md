# Mapa de origem dos defeitos — 2026-08-05

Cada achado atribuído à camada onde a correção precisa entrar, não onde o sintoma
aparece. A distinção importa: seis dos catorze achados aparecem no renderer e só dois
nascem nele.

| Achado | Camada de origem | Arquivo e ponto | Camada onde o sintoma aparece |
|---|---|---|---|
| F-01 câmera penetra o painel | **câmera** | `frontend/src/atlas.ts:219` | renderer |
| F-02 recíprocas coincidentes | **renderer** | `frontend/src/edges.ts:149-217` | renderer |
| F-03 filamentos duplicados por direção | **contrato/backend** | `backend/src/vault/projection.py:401` | renderer |
| F-04 MOCs deslocados pela camada viva | **layout** | `frontend/src/layout.ts:278` | layout |
| F-05 floresta de wireframes | **material** | `frontend/src/geometry.ts:41` | renderer |
| F-06 nuvem de IA sem ontologia espacial | **layout** | `frontend/src/layout.ts:88-99` | layout |
| F-07 aba Trabalhadores desalinhada da execução | **snapshot** | `backend/src/vault/control/snapshot.py:191` | UI |
| F-08 fila travada, mensagem enganosa | **quórum/scheduler** | `backend/src/vault/work/orchestrator.py:783,1084` | observabilidade |
| F-09 falhas sem estrutura | **contrato** | `backend/src/vault/control/models.py` (campo `failures`) | UI |
| F-10 texto recortado | **renderer** (hipótese) | `frontend/src/panelTextRenderer.ts` | renderer |
| F-11 nuvem operacional domina o enquadramento | **layout** | `frontend/src/layout.ts` + `atlas.ts:190` | câmera |
| F-12 espinha e famílias coexistem | **renderer** | `frontend/src/atlas.ts:737,859` | renderer |
| F-13 camada viva ignora o filtro | **renderer** | `frontend/src/runtimeLayer.ts:361` | renderer |
| F-14 deliberação não chega à cena | **integração** | `operational.py` → `projection.py` → cena | observabilidade |

## Contagem por origem

| Origem | Achados |
|---|---|
| renderer | F-02, F-10, F-12, F-13 |
| layout | F-04, F-06, F-11 |
| câmera | F-01 |
| material | F-05 |
| contrato/backend | F-03, F-09 |
| snapshot | F-07 |
| quórum/scheduler | F-08 |
| integração | F-14 |

## Camadas sem defeito atribuído

Registradas porque a auditoria as examinou e as achou íntegras:

- **corpus** — 84 notas, 672 wikilinks, zero quebrados, zero órfãs, zero relações fora do
  vocabulário, 267 claims com ID único. Nenhum defeito visual tem origem no corpus.
- **parser** — 555 arestas dirigidas, wikilink ambíguo reprova em vez de desempatar.
- **store** — `runtime/quorum/` preserva a proveniência completa de 35 execuções.

## Leitura

A concentração no renderer é enganosa se lida como "o problema é a cena". Dos quatro
achados que nascem no renderer, dois (F-12, F-13) são coordenação de visibilidade entre
grupos e um (F-02) é uma escolha de chave — nenhum é dívida estrutural profunda.

Os defeitos caros são os de **layout**: F-04, F-06 e F-11 têm a mesma raiz única — a
camada operacional entra no mesmo espaço de posicionamento que o corpus, sem âncora,
sem subdivisão por `kind` e contando para o dimensionamento do anel. Corrigir esse ponto
resolve três achados de uma vez, e é por isso que ele encabeça o roadmap.
