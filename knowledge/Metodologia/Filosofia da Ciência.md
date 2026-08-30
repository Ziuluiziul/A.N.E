---
title: Filosofia da Ciência
aliases: [Demarcação, Falsificacionismo, Subdeterminação, Realismo Científico]
domain: metodologia
kind: nota
status: active
epistemic_status: mixed
updated: 2026-07-28
verified_at: 2026-07-28
---

# Filosofia da ciência

## Finalidade

Responder: **o que justifica tratar uma afirmação como estabelecida, apoiada ou especulativa?** Esta nota existe por uma dívida específica: o Vault classifica 240 claims usando um vocabulário epistêmico — `established`, `supported`, `model-dependent`, `hypothesis`, `speculative`, `open` — que a [[Política Epistêmica e de Linkagem]] <!-- relation:operational --> **define operacionalmente e não fundamenta**. Sem esta nota, a taxonomia que governa todo o corpus opera sem justificativa registrada.

## Escopo

Problema da demarcação; indução e o problema de Hume; falsificacionismo popperiano e suas dificuldades; tese Duhem–Quine e subdeterminação; carga teórica da observação; paradigmas, ciência normal e incomensurabilidade em Kuhn; programas de pesquisa em Lakatos; inferência à melhor explicação; realismo científico, instrumentalismo e a indução pessimista; papel de modelos e idealizações; valores em ciência. **Escopo negativo:** epistemologia geral, metafísica, história da ciência como disciplina, e sociologia da ciência.

## Pré-requisitos

- [[Lógica, Provas e Argumentação]] <!-- relation:prerequisite --> — a assimetria entre verificação e refutação é lógica antes de ser metodológica.
- [[Estimação e Testes de Hipótese]] <!-- relation:prerequisite --> — a prática estatística de teste é a instância operacional dos problemas discutidos aqui.

## Conceitos nucleares

- **Problema da indução (Hume)**: nenhuma quantidade finita de observações confirmadoras implica dedutivamente a generalização. Não há solução aceita; há respostas concorrentes.
- **Falsificacionismo**: uma teoria é científica se proíbe algo observável. A assimetria é real — um contraexemplo refuta o que nenhuma confirmação prova.
- **Tese Duhem–Quine**: hipóteses não são testadas isoladamente, mas junto com hipóteses auxiliares, condições iniciais e teoria do instrumento. Um resultado negativo indica que *algo* no conjunto falhou, sem apontar o quê.
- **Carga teórica da observação**: o que conta como dado depende de teoria prévia. Não há observação neutra que arbitre entre teorias distantes.
- **Paradigma e ciência normal (Kuhn)**: a maior parte da atividade científica resolve quebra-cabeças dentro de um arcabouço não questionado; crises antecedem mudança.
- **Programa de pesquisa (Lakatos)**: núcleo duro protegido por cinturão de hipóteses auxiliares. O critério de avaliação é *progressivo × degenerativo* — se as modificações preveem fatos novos ou apenas absorvem anomalias.
- **Inferência à melhor explicação**: aceitar a hipótese que melhor explicaria a evidência. Depende de um critério de "melhor" que é contestado.
- **Realismo × instrumentalismo**: teorias bem-sucedidas descrevem entidades inobserváveis reais, ou são instrumentos preditivos eficazes? A indução pessimista observa que teorias passadas bem-sucedidas foram abandonadas.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-MET-FILO-001` | Hipóteses não são testáveis isoladamente: um teste confronta a hipótese junto com hipóteses auxiliares e a teoria do instrumento, e um resultado negativo não localiza sozinho a falha (tese Duhem–Quine). | established | Godfrey-Smith, cap. 3 e 10. **Consequência direta para este Vault:** é por isso que a política exige que cada claim declare escopo, hipóteses e limites — o registro das auxiliares é o que torna a refutação localizável depois. |
| `CLM-MET-FILO-002` | O falsificacionismo estrito é insuficiente como critério de demarcação, porque o holismo do teste permite salvar qualquer teoria por ajuste de auxiliares. | established | Godfrey-Smith, cap. 4 e 5. **Escopo:** a insuficiência é como *critério de demarcação*; a assimetria lógica entre confirmação e refutação continua válida e continua sendo boa heurística de projeto experimental. Descartar as duas coisas juntas é erro comum. |
| `CLM-MET-FILO-003` | Não existe consenso filosófico sobre o critério de demarcação entre ciência e não ciência. | open | Godfrey-Smith, cap. 4–5 e 14, apresenta as propostas concorrentes sem resolução. **Status deliberado:** marcar `established` seria contradizer a própria literatura consultada. É um dos poucos claims do Vault em que `open` descreve o estado de uma discussão filosófica em curso, não uma lacuna empírica nem uma falha de busca. **Por que manter `open`:** o `open` aqui é diagnóstico, não residual — afirma exatamente que a discussão está aberta; baixá-lo para `established` encerraria o que a fonte registra como em curso, e elevá-lo para algo mais forte não é sustentado pelo mesmo registro. **Não confundi-lo com:** (a) a inexistência de casos decidíveis (há, ver §Limites); (b) a tese kuhniana forte de que qualquer paradigma vale quanto outro (não é o que o claim diz nem o que a fonte sustenta). **Condição para revisar:** mudança para `established` exigiria fonte que registre convergência filosófica atual sobre um critério — não basta enumeração de propostas. |
| `CLM-MET-FILO-004` | O vocabulário epistêmico deste Vault não é uma taxonomia filosoficamente neutra: ele adota uma posição falibilista e gradualista, em que o suporte é matéria de grau e revisável, e rejeita tanto a certeza indutiva quanto o ceticismo global. | established | Posição identificável em Godfrey-Smith, cap. 14 (e a discussão de Bayesianismo, cap. 14). **Por que registrar isto:** a distinção operacional entre `established`, `supported` e `model-dependent` pressupõe que o grau de suporte é significativo e comparável. Quem rejeitar essa premissa rejeita a taxonomia inteira, e o Vault deve dizer isso em vez de apresentar a classificação como natural. |
| `CLM-MET-FILO-005` | Modelos científicos são idealizações deliberadas: sua utilidade não depende de serem descrições literalmente verdadeiras do sistema modelado. | established | Godfrey-Smith, cap. 12. **Ligação com o corpus:** é a justificativa do status `model-dependent`, que o Vault usa em Física e em Ciências da Vida para consequências válidas sob hipóteses declaradas, sem alegação de observação direta. |

## Limites e contraexemplos

- **Kuhn não é relativismo**: incomensurabilidade é dificuldade de tradução e de comparação por padrão neutro, não a tese de que qualquer teoria vale tanto quanto outra. A leitura relativista é comum e não é sustentada pelo texto.
- **"Não falsificável" não é sinônimo de "sem valor"**: matemática, e boa parte da teoria física em desenvolvimento, não é falsificável no sentido popperiano e não é pseudociência. O Vault trata esses casos com `model-dependent` ou `speculative`, não com exclusão.
- **A demarcação não decide casos individuais**: mesmo sem critério geral aceito, casos específicos são frequentemente decidíveis por evidência. A ausência de teoria não paralisa a prática.
- **Esta nota não fornece critério novo**: descreve o estado de uma discussão e explicita a posição que o Vault já adota. Confundir descrição com fundamentação seria repetir o erro que ela existe para corrigir.

## Relações

- [[Política Epistêmica e de Linkagem]] <!-- relation:operational --> — a taxonomia operacional que esta nota fundamenta.
- [[Lógica, Provas e Argumentação]] <!-- relation:prerequisite -->
- [[Estimação e Testes de Hipótese]] <!-- relation:extends --> — o problema de Duhem–Quine reaparece como especificação do modelo.
- [[Desenho Experimental e Causalidade]] <!-- relation:extends -->
- [[Reprodutibilidade e Replicação]] <!-- relation:evidence --> — a crise de replicação é o teste empírico das teses desta nota.
- [[Metrologia e Validação]] <!-- relation:extends --> — carga teórica da observação instanciada em medição.
- [[Fronteiras da Física — Monitor de Evidências]] <!-- relation:operational --> — o monitor separa status editorial de delta de evidência, distinção que só faz sentido sob esta nota.
- [[MOC — Metodologia Científica]] <!-- relation:navigation -->

## Fontes

- Peter Godfrey-Smith. *Theory and Reality: An Introduction to the Philosophy of Science*. 2ª ed., University of Chicago Press, 2021.

## Condição de revisão

Estável quanto ao mapa da discussão. Revisar `CLM-MET-FILO-003` apenas se surgir fonte que registre convergência filosófica atual sobre um critério de demarcação; revisar `CLM-MET-FILO-004` se a política epistêmica do Vault mudar de taxonomia — o claim documenta uma escolha, e a escolha pode ser revista.
