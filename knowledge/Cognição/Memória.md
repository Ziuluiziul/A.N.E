---
title: Memória
aliases: [Consolidação, Reconsolidação, Engrama, Esquecimento]
domain: cognição
kind: nota
status: active
epistemic_status: mixed
updated: 2026-07-30
verified_at: 2026-07-30
---

# Memória

## Finalidade

Responder: **como uma experiência vira um traço durável, o que acontece com esse
traço ao longo do tempo, e o que se sabe sobre onde ele está?** É a nota que fecha o
arco aberto por `CLM-COG-NEURO-002` em [[Bases Neurais da Cognição]] <!-- relation:prerequisite -->,
que trata plasticidade sináptica como **candidata** a substrato de armazenamento.
Fechar o arco aqui não significa promovê-lo: significa mostrar exatamente até onde a
evidence chega e onde ela para.

## Escopo

Sistemas dissociáveis de memória (declarativa e não declarativa) e a evidência de
lesão que os separa; codificação e os fatores que a modulam; consolidação sináptica
e a distinção conceitual da consolidação de sistemas; reconsolidação após
reativação e seus limites de tradução; esquecimento; recuperação como processo
**reconstrutivo**; engrama como rótulo operacional para populações celulares
marcadas e manipuladas; prática distribuída e efeito de teste como intervenções
com efeito medido. **Escopo negativo:** memória de trabalho e controle executivo
(lacuna declarada do domínio, ainda sem nota); psicopatologia da memória e
diagnóstico clínico; mnemotécnicas e literatura de autoajuda cognitiva; "memória"
em sistemas computacionais, que é homônimo e não compartilha mecanismo.

## Pré-requisitos

- [[Bases Neurais da Cognição]] <!-- relation:prerequisite --> — LTP/LTD, sinapse e os limites inferenciais de cada método de medida.
- [[Desenho Experimental e Causalidade]] <!-- relation:prerequisite --> — a diferença entre necessidade e suficiência, que organiza toda a seção de engrama.

## Conceitos nucleares

- **Codificação**: transformação da experiência em traço. Não é gravação — é
  seletiva, dependente de atenção e de estado, e já introduz distorção.
- **Consolidação sináptica**: estabilização local após a aprendizagem. Nesta nota,
  a evidência direta vem da interferência com síntese proteica em um paradigma
  animal específico.
- **Consolidação de sistemas**: mudança da dependência neural de memórias em
escalas mais longas. O mecanismo e o curso temporal permanecem dívida declarada,
sem claim próprio.
- **Recuperação**: tornar um traço acessível para uso. Pode reativá-lo, mas não é
  sinônimo de reconsolidação: esta exige evidência de labilização e nova
  estabilização no regime observado.
- **Reconsolidação**: em certos paradigmas, reativar uma memória consolidada pode
  torná-la lábil e novamente dependente de síntese proteica para se estabilizar. Espécie, região, tarefa e intervalo
  limitam a generalização.
- **Esquecimento**: redução da disponibilidade ou da acessibilidade do traço ao
  longo do tempo. Mecanismos e trajetória temporal não recebem claim nesta nota.
- **Reconstrução**: recuperar é reconstruir a partir de traço parcial mais
  inferência. É por isso que a confiança do relato não indexa sua acurácia.
- **Engrama**: nesta nota, população esparsa de neurônios marcada durante a
  aprendizagem e depois manipulada. É uma definição operacional, não a afirmação
  de que essa população seja a própria memória.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-COG-MEM-001` | Memória não é faculdade única: lesão bilateral do lobo temporal medial prejudica gravemente a memória declarativa preservando aprendizado de habilidade e memória imediata. | supported | Scoville e Milner (1957), o relato primário do caso H.M.; sistematizado por Squire (2004). **Nível de verificação:** identificadores resolvidos e títulos conferidos no Crossref em 2026-07-30; o conteúdo aqui se apoia também em Kandel et al., já fonte curricular do domínio. |
| `CLM-COG-MEM-002` | No condicionamento de medo em ratos, bloquear a síntese proteica na amígdala logo após o treino prejudica a consolidação da memória recém-formada. | established | Nader, Schafe e LeDoux (2000), resumo conferido. No experimento, a infusão de anisomicina nos núcleos lateral e basal da amígdala logo após o treino produziu o prejuízo. **Escopo:** modelo animal e condicionamento de medo; a linha não generaliza o mecanismo para toda forma de memória. |
| `CLM-COG-MEM-003` | No condicionamento de medo em ratos, reativar uma memória consolidada pode torná-la lábil e novamente dependente de síntese proteica para se estabilizar. | supported | Nader, Schafe e LeDoux (2000), resumo conferido. **Escopo:** núcleos lateral e basal da amígdala; efeito com reativação 1 ou 14 dias após o condicionamento; anisomicina **sem** reativação deixa a memória intacta; infusão seis horas após a reativação **não** produz amnésia. Generalizar para "memórias humanas podem ser reescritas" excede espécie, região, paradigma e intervalo da fonte. |
| `CLM-COG-MEM-004` | A extinção pós-recuperação — o uso comportamental da reconsolidação — tem efeito real mas heterogêneo, e não uniforme entre paradigmas. | supported | Kredlow, Unger e Otto (2016), meta-análise de 63 comparações, resumo conferido: `g = 0,40` (pequeno a moderado, significativo) para reduzir retorno do medo em **humanos**; `g = 0,89` (grande) para respostas apetitivas em **animais**; `g = 0,21` **não significativo** para medo em animais, com moderação por densidade de alojamento e intervalo até o teste. **Limite:** a heterogeneidade entre os três é o dado, não ruído a ser mediado. Citar só o `g = 0,89` seria selecionar o braço mais favorável. |
| `CLM-COG-MEM-005` | Em tarefas de recordação verbal, o intervalo entre estudos que maximiza a retenção **cresce** conforme cresce o intervalo de retenção pretendido. | established | Cepeda et al. (2006), meta-análise de 839 avaliações em 317 experimentos de 184 artigos, resumo conferido: "the ISI producing maximal retention increased as retention interval increased". **Consequência prática:** não existe "intervalo ótimo" absoluto de revisão; a pergunta está malformada sem declarar por quanto tempo se quer lembrar. |
| `CLM-COG-MEM-006` | Nos experimentos de Roediger e Karpicke (2006), testar-se superou reestudar na retenção a longo prazo, e a vantagem **se inverteu** no intervalo curto. | supported | Dois experimentos, resumo conferido: com teste final após 5 min, reestudar superou testar; após 2 dias e 1 semana, testar produziu retenção substancialmente maior — apesar de o reestudo aumentar a **confiança** dos estudantes. **Limite:** a linha registra o resultado diretamente inspecionado; generalização além desses experimentos exige convergência adicional. |
| `CLM-COG-MEM-007` | A reativação optogenética de uma população esparsa de neurônios marcada durante o condicionamento é **suficiente** para evocar a resposta de medo. | supported | Liu et al. (2012), resumo conferido. **Escopo:** camundongos; giro denteado do hipocampo; marcação com ChR2; congelamento induzido apenas sob estimulação luminosa, ausente nos controles (não condicionados com ChR2; condicionados com EYFP) e **específico de contexto**. Suficiência para evocar a resposta comportamental não é o mesmo que identidade entre a memória e aquele conjunto celular. |
| `CLM-COG-MEM-008` | Não está estabelecido que uma memória episódica específica **seja** um padrão sináptico específico identificado. | open | O mesmo limite de `CLM-COG-NEURO-002`: a evidência de engrama (`CLM-COG-MEM-007`, Liu et al. 2012; revisão Josselyn e Tonegawa 2020) demonstra **suficiência** de um conjunto celular esparso para evocar a resposta comportamental em um paradigma, não **identidade** entre o conteúdo mnemônico episódico e uma configuração sináptica específica. A distinção entre suficiência operacional e identidade ontológica é exigida pela [[Política Epistêmica e de Linkagem]] <!-- relation:prerequisite -->. **Status `open` (não `refuted`):** questão em aberto, sem contradição efetiva. |
| `CLM-COG-MEM-009` | A recuperação é reconstrutiva: informação introduzida depois do evento altera o relato posterior sobre ele. | supported | Loftus e Palmer (1974), o experimento da "reconstrução de destruição automobilística". **Nível de verificação:** identificador resolvido e título conferido no Crossref em 2026-07-30; o resumo **não** foi auditado, e o tamanho de efeito não é afirmado aqui. O estado replicativo de achados clássicos deste campo é tratado em [[Raciocínio, Julgamento e Decisão]] <!-- relation:evidence -->. |

## Limites e contraexemplos

- **Suficiência não é identidade.** Ativar um conjunto celular e obter a resposta
  comportamental mostra que aquele conjunto basta para disparar o comportamento
  naquele paradigma. Não mostra que a memória *é* aquele conjunto, nem que outro
  conjunto não bastaria.
- **Reconsolidação não é "reescrever memórias".** A leitura popular ignora espécie,
  região, paradigma e o limite temporal observado — seis horas após a reativação,
  a infusão já não produziu amnésia. `CLM-COG-MEM-003` e `CLM-COG-MEM-004`
  separam o achado animal de sua tradução comportamental.
- **Confiança não indexa acurácia.** `CLM-COG-MEM-006` traz a dissociação medida:
  reestudar aumentou a confiança e reduziu a retenção relativa. Sensação de saber é
  um mau instrumento.
- **Não há intervalo ótimo universal.** `CLM-COG-MEM-005` torna a pergunta
  dependente do horizonte de retenção; qualquer recomendação de revisão com número
  fixo omite o parâmetro que determina a resposta.
- **Modelo animal transfere parcialmente.** Vale aqui o mesmo limite de
  [[Bases Neurais da Cognição]] <!-- relation:prerequisite -->: mecanismo celular é
  conservado; arquitetura cognitiva, muito menos.
- **"Memória" em computação é homônimo.** Armazenamento endereçável com leitura
  fiel não compartilha mecanismo com um traço reconstrutivo e lábil. A aresta com IA
  é de **contraste**, nunca de evidência.

## Relações

- [[Bases Neurais da Cognição]] <!-- relation:prerequisite -->
- [[Desenho Experimental e Causalidade]] <!-- relation:prerequisite -->
- [[Raciocínio, Julgamento e Decisão]] <!-- relation:extends --> — julgamento sob incerteza opera sobre o que foi recuperado, com as distorções desta nota.
- [[Percepção e Psicofísica]] <!-- relation:prerequisite --> — o que é codificado começa no que foi percebido e atendido.
- [[Reprodutibilidade e Replicação]] <!-- relation:prerequisite --> — fornece os critérios para interpretar o estado replicativo desigual dos achados clássicos do campo.
- [[Biologia Molecular e Fluxo de Informação Genética]] <!-- relation:prerequisite --> — "síntese proteica" em `CLM-COG-MEM-002` é o mecanismo descrito lá.
- [[Fundamentos de Aprendizado de Máquina e Modelos de Linguagem]] <!-- relation:contrasts --> — homonímia de "memória" e "esquecimento"; nenhuma transferência de resultado sem fonte que trate ambos os domínios.
- [[MOC — Cognição]] <!-- relation:navigation -->

## Fontes

Nível de verificação declarado por item, conforme a [[Política Epistêmica e de Linkagem]] <!-- relation:prerequisite -->.
Todos os identificadores abaixo foram resolvidos no Crossref em 2026-07-30 com o
título canônico conferido (nível 1). Os marcados **[resumo auditado]** tiveram o
resumo lido e confrontado com o claim que sustentam (nível 2). Nenhum texto integral
foi lido.

- William Beecher Scoville e Brenda Milner. "Loss of Recent Memory After Bilateral Hippocampal Lesions". *Journal of Neurology, Neurosurgery & Psychiatry* 20(1), 11–21 (1957). DOI `10.1136/jnnp.20.1.11`.
- Larry R. Squire. "Memory systems of the brain: A brief history and current perspective". *Neurobiology of Learning and Memory* 82(3), 171–177 (2004). DOI `10.1016/j.nlm.2004.06.005`.
- Karim Nader, Glenn E. Schafe e Joseph E. LeDoux. "Fear memories require protein synthesis in the amygdala for reconsolidation after retrieval". *Nature* 406(6797), 722–726 (2000). DOI `10.1038/35021052`. **[resumo auditado]**
- M. Alexandra Kredlow, Leslie D. Unger e Michael W. Otto. "Harnessing reconsolidation to weaken fear and appetitive memories: A meta-analysis of post-retrieval extinction effects". *Psychological Bulletin* 142(3), 314–336 (2016). DOI `10.1037/bul0000034`. **[resumo auditado]**
- Nicholas J. Cepeda, Harold Pashler, Edward Vul, John T. Wixted e Doug Rohrer. "Distributed practice in verbal recall tasks: A review and quantitative synthesis". *Psychological Bulletin* 132(3), 354–380 (2006). DOI `10.1037/0033-2909.132.3.354`. **[resumo auditado]**
- Henry L. Roediger III e Jeffrey D. Karpicke. "Test-Enhanced Learning: Taking Memory Tests Improves Long-Term Retention". *Psychological Science* 17(3), 249–255 (2006). DOI `10.1111/j.1467-9280.2006.01693.x`. **[resumo auditado]**
- Xu Liu, Steve Ramirez, Petti T. Pang, Corey B. Puryear, Arvind Govindarajan, Karl Deisseroth e Susumu Tonegawa. "Optogenetic stimulation of a hippocampal engram activates fear memory recall". *Nature* 484(7394), 381–385 (2012). DOI `10.1038/nature11028`. **[resumo auditado]**
- Sheena A. Josselyn e Susumu Tonegawa. "Memory engrams: Recalling the past and imagining the future". *Science* 367(6473), eaaw4325 (2020). DOI `10.1126/science.aaw4325`.
- Elizabeth F. Loftus e John C. Palmer. "Reconstruction of automobile destruction: An example of the interaction between language and memory". *Journal of Verbal Learning and Verbal Behavior* 13(5), 585–589 (1974). DOI `10.1016/S0022-5371(74)80011-3`.
- Björn Rasch e Jan Born. "About Sleep's Role in Memory". *Physiological Reviews* 93(2), 681–766 (2013). DOI `10.1152/physrev.00032.2012`.
- John T. Wixted. "The Psychology and Neuroscience of Forgetting". *Annual Review of Psychology* 55(1), 235–269 (2004). DOI `10.1146/annurev.psych.55.090902.141555`.

## Lacuna declarada nesta nota

A consolidação de sistemas aparece apenas como distinção conceitual. Seu mecanismo,
o papel do sono e o curso temporal do esquecimento **não** têm claim próprio.
Squire (2004), Rasch e Born (2013) e Wixted (2004) estão listados com identificador
resolvido e título conferido, mas sem resumo ou texto auditado nesta passagem.
Permanecem como fontes identificadas para ciclos posteriores, não como evidência já
contabilizada.

## Condição de revisão

- Revisar `CLM-COG-MEM-001` quando Scoville e Milner (1957) e Squire (2004)
  receberem verificação substantiva; até lá, permanece `supported`.
- Reavaliar `CLM-COG-MEM-008` junto com `CLM-COG-NEURO-002` se surgir evidência que
  identifique a correspondência entre uma memória episódica específica e uma
  configuração sináptica, além de apenas evocar comportamento por manipulação.
- Revisar `CLM-COG-MEM-004` se meta-análise posterior alterar a heterogeneidade
  entre os três braços.
- Revisar `CLM-COG-MEM-009` quando o resumo de Loftus e Palmer for auditado.
