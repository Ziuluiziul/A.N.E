# Google Workspace: obter as credenciais

Duas integrações com o Google convivem neste produto e **não** compartilham
credencial:

| | API Gemini | Google Workspace |
| --- | --- | --- |
| Credencial | chave de API do AI Studio | OAuth 2.0 do dono da conta |
| Variável | `GEMINI_API_KEY` | `GOOGLE_WORKSPACE_CLIENT_SECRET_FILE` |
| Exige projeto no Cloud | não | sim |
| Onde vive no código | `providers/google/` | `integrations/google_workspace/` |

Confundir as duas é o erro mais comum aqui. A chave do AI Studio não abre o Drive, e o
token OAuth não fala com o Gemini. Host, cotas e o que a página da Gemini API diz hoje
estão em [PROVEDORES.md](PROVEDORES.md); este guia não mistura OAuth com essa API.

## Passo a passo

1. Abra o [Google Cloud Console](https://console.cloud.google.com/) e crie um projeto
   — ou selecione um existente.
2. Em **APIs e serviços → Biblioteca**, habilite as APIs que pretende usar. Para esta
   fase basta a **Google Drive API**; as demais podem esperar, e habilitar uma de cada
   vez é melhor que habilitar treze de uma vez.
3. Em **APIs e serviços → Tela de permissão OAuth**, configure a tela. Tipo de usuário
   **Externo** serve para conta pessoal. Em **Usuários de teste**, adicione o seu
   próprio e-mail: sem isso o consentimento é recusado enquanto o app não for
   verificado.
4. Em **APIs e serviços → Credenciais → Criar credenciais → ID do cliente OAuth**,
   escolha **App para computador**. Baixe o JSON.
5. Guarde o arquivo fora do repositório e restrinja a permissão:

   ```bash
   mkdir -p ~/.config/ane
   mv ~/Downloads/client_secret_*.json ~/.config/ane/credentials.json
   chmod 600 ~/.config/ane/credentials.json
   ```

6. Aponte as duas variáveis em `~/.config/ane/secrets.env` (ou no caminho legado
   `~/.config/vault-autodidata/secrets.env`, se for o arquivo que o A.N.E. ainda lê):

   ```
   GOOGLE_WORKSPACE_CLIENT_SECRET_FILE=~/.config/ane/credentials.json
   GOOGLE_WORKSPACE_TOKEN_FILE=~/.config/ane/token.json
   ```

   Expanda `~` para o caminho absoluto da sua máquina.

7. Rode o consentimento:

   ```bash
   make workspace-oauth
   ```

   O navegador abre, você autoriza, e o token é gravado com permissão 600 no caminho
   indicado. Em seguida o script faz uma leitura mínima no Drive para confirmar que a
   autorização vale de fato.

## Escopos

Só o metadado do Drive é pedido nesta fase:

```
https://www.googleapis.com/auth/drive.metadata.readonly
```

Pedir os treze escopos de uma vez faz o consentimento falhar inteiro quando uma única
API não está habilitada. Cada serviço a mais é uma decisão explícita, e o catálogo
completo — com escopo, alcance e a leitura mínima de cada serviço — está em
`integrations/google_workspace/client.py`.

## Alcance por serviço

Preparado não é habilitado, e indisponível não é falha. O catálogo registra a
diferença:

| Serviço | Situação |
| --- | --- |
| Drive, Calendar, Tasks, People, Meet | leitura possível sem ID; sondagem implementada |
| Docs, Sheets, Slides, Forms | leem por ID; a descoberta passa pelo Drive |
| Gmail | escopo restrito pelo Google: exige usuário de teste ou app verificado |
| Apps Script | exige a Apps Script API ligada nas configurações do usuário |
| Chat | somente contas Google Workspace, indisponível em conta pessoal |
| Keep | somente Workspace Enterprise, com delegação em todo o domínio |

## Nesta fase não há escrita

Nenhum fluxo automatizado escreve em Gmail, Calendar, Drive ou Docs. Todos os escopos
do catálogo são `readonly`, e um teste em `tests/test_workspace_catalog.py` falha se
algum deixar de ser.
