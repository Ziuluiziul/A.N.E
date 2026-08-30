# Instruções para agentes neste repositório

Este é o **A.N.E.** — Atlas Neural-Epistêmico. O repositório abriga duas coisas
com pesos diferentes. Em `knowledge/` está um **corpus de conhecimento**, cujo
produto é o texto e a confiabilidade das afirmações; todo o resto é código de
apoio a ele. Vários agentes trabalham aqui
(Claude Code, Codex/ChatGPT no VS Code, ChatGPT no navegador), o que torna as
regras abaixo mais importantes que qualquer preferência de estilo.

O rigor máximo pertence ao conteúdo acadêmico. Código nunca entra em `knowledge/`,
e saída de modelo nunca entra no corpus direto: ela fica em
`runtime/quorum/<painel>/`, que não é versionado, e só é promovida por quórum
multimodelo — ver **Regime de execução**, no fim deste arquivo.

## Leia antes de escrever

1. `knowledge/Índice.md` — o MOC raiz e as camadas de dependência.
2. `knowledge/Política Epistêmica e de Linkagem.md` — o critério editorial completo.

Estes dois documentos têm precedência sobre este arquivo. Se algo aqui contradisser
a Política, a Política vence e este arquivo está errado.

## As cinco regras que não se negociam

1. **Identificador só entra resolvido na fonte.** DOI, arXiv e ISBN precisam
   resolver e bater com o título canônico. Não deu para verificar agora? A
   afirmação é **omitida** — não estimada, não aproximada, não citada de memória.
   Um identificador plausível e errado é pior que uma lacuna, porque passa por
   auditado.
2. **Todo wikilink ativo declara a relação** na mesma linha:
   `[[Nota]] <!-- relation:prerequisite -->`. Vocabulário permitido: `navigation`,
   `prerequisite`, `extends`, `contrasts`, `evidence`, `operational`, `historical`.
   Analogia, metáfora e vocabulário compartilhado **não criam aresta**.
3. **Todo claim tem ID único global** no formato `CLM-DOMINIO-TOPICO-NNN`, com
   status do vocabulário fechado (`established`, `supported`, `model-dependent`,
   `hypothesis`, `speculative`, `open`, `refuted`, `operational`, `out-of-scope`,
   `quarantine`). Antes de criar um ID, confira que ele não existe.

   Sobre ausência de evidência: ela **isoladamente nunca implica `refuted`** —
   `refuted` exige contradição efetiva. Conforme a Política, a proposição pode ser
   `open`, `hypothesis` ou `speculative`; escolher entre os três é julgamento
   editorial, não automatismo, e nenhum deles é o padrão. Pista insuficiente pode
   permanecer em quarentena ou staging — o que ela não pode é ser promovida a
   conhecimento estabelecido no corpus ativo.
4. **Nada de placeholder.** MOC sem notas, nota-esboço e diretório à espera de
   conteúdo são proibidos em todas as camadas. Nota de fundamento pode nascer sem
   consumidor, mas só se nascer completa.
5. **`updated` muda a cada edição; `verified_at` só muda quando houve verificação
   real de fontes naquela data.** Resolver um DOI não é ler a fonte — não alegue o
   nível que não fez.

## Antes de encerrar qualquer alteração

```bash
make audit
```

Equivale a `python3 tools/audit.py --contra=HEAD`, que sem argumento audita
`knowledge/` e com `--contra` mede o que cada nota perdeu desde a referência — o
Makefile passa `HEAD` por padrão, então redução não declarada reprova. O
script é somente-leitura. Ele confere contagens, nomes de nota duplicados,
wikilinks quebrados, wikilinks sem `relation:`, notas órfãs, MOCs vazios, campos e
vocabulários do frontmatter, `review_after` vencido, datas, forma e vocabulário das
claims e unicidade dos seus IDs. Zero em todas as linhas de defeito, ou a alteração
não está pronta.

Este script substitui o gate determinístico do pipeline antigo, descontinuado na
migração de 2026-07-28. Ele é um auditor **estrutural e parcial**: não valida
verdade científica, não resolve fontes e não confere se um identificador
corresponde ao título canônico. Sair com código 0 significa que a estrutura está
íntegra, nunca que o conteúdo está certo. A própria saída declara separadamente
que fontes externas não foram verificadas. Isso continua sendo julgamento humano.

## Onde fica o código

`backend/src/vault/` é o pacote Python (`vault`); `providers/` traz um adaptador por
provedor; `integrations/google_workspace/` cobre as APIs do Workspace; `frontend/` é
a cena 3D em TypeScript e Three.js; `tools/` são os scripts curtos que o `Makefile`
chama; `tests/` os testes; `runtime/` o estado local ignorado pelo Git. Segredos
moram em `~/.config/vault-autodidata/secrets.env` e nunca no repositório.

## Escopo

Não reorganize domínios, não mova notas entre pastas e não crie notas novas sem que
tenham sido pedidas. A estrutura de pastas é só localização — wikilinks resolvem por
nome — mas mudanças estruturais são decisão do mantenedor, não do agente.

## Regime de execução

Desde a diretriz de 2026-08-03, implementação não espera aprovação humana. Trabalho
de código que passe nos gates locais é commitado pelo próprio agente:

```bash
make audit && make test && make lint
```

Zero defeito nas três, ou não commita. Mensagem em português, no imperativo,
explicando **por que** a mudança entra. Cada ciclo entrega capacidade utilizável;
nenhum ciclo se abre só para preparar outro, e documentação registra o que foi
implementado em vez de anteceder indefinidamente a implementação.

Promoção de conhecimento é decidida por quórum multimodelo — nem por pessoa, nem por
agente isolado. A proposta é produzida por um modelo e avaliada por modelos
independentes, com pelo menos dois provedores representados e o proponente fora da
própria contagem. O corpus segue fechado à escrita direta: o caminho é
`runtime/quorum/<painel>/` e o Proposal Promoter, que aplica o patch, roda os
controles mínimos e registra quem propôs e quem avaliou. Defeito de conteúdo já
presente no corpus (ata de painel, LaTeX mutilado, título canônico corrompido,
Política sem o regime de 2026-08-03) entra na fila como origem de restauração e
não espera comando avulso.

Confirmação humana permanece obrigatória em quatro casos, e só neles:

- **credenciais** — ler, escrever ou rotacionar segredo;
- **OAuth interativo**, que exige consentimento numa sessão de navegador;
- **comando administrativo ou destrutivo** — `git push`, reescrita de histórico,
  remoção de dados, alteração de configuração do sistema;
- **consumo externo acima do orçamento** configurado para a execução.

Fora desses quatro, perguntar antes de agir atrasa sem proteger nada. Isso não
afrouxa o **Escopo** acima: autonomia de commit é sobre código, e mudar a estrutura
do corpus continua sendo decisão do mantenedor.
