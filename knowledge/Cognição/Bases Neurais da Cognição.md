---
title: Bases Neurais da Cognição
aliases: [Neurociência, Neurônio, Plasticidade Sináptica]
domain: cognição
kind: nota
status: active
epistemic_status: mixed
updated: 2026-07-31
verified_at: 2026-07-31
review_log:
  - {date: '2026-07-31', action: 'reviewed CLM-COG-NEURO-004', note: 'Busca por evidência de papel funcional de efeitos quânticos coerentes na cognição nas fontes auditadas (Kandel et al., 2021) não retornou resultados; claim mantido como open.'}
---

# Bases neurais da cognição

## Finalidade

Responder: **o que se sabe, com que grau de certeza, sobre a implementação física de processos mentais?** É o domínio em que a distância entre o mecanismo bem estabelecido (nível celular) e a explicação pretendida (nível cognitivo) é maior — e onde essa distância é rotineiramente apagada na divulgação.

## Escopo

Neurônio como unidade: potencial de membrana, potencial de ação, condução; sinapse química e elétrica; neurotransmissores e receptores; integração dendrítica; plasticidade sináptica (LTP, LTD) e regras de coincidência temporal; organização em circuitos e mapas; sistemas sensoriais e motores em nível de arquitetura; métodos de medida e seu poder de resolução (eletrofisiologia, fMRI, lesão, optogenética) com seus limites inferenciais. **Escopo negativo:** consciência como problema explicativo, psiquiatria clínica, modelos computacionais de rede neural artificial (domínio de IA), e afirmações sobre efeitos quânticos em neurônios.

## Pré-requisitos

- [[Bioenergética e Termodinâmica dos Sistemas Vivos]] <!-- relation:prerequisite --> — gradientes iônicos são mantidos por bombas que consomem ATP; o potencial de repouso é um estado estacionário fora do equilíbrio, não um equilíbrio.
- [[Biologia Molecular e Fluxo de Informação Genética]] <!-- relation:prerequisite --> — canais e receptores são proteínas com expressão regulada.

## Conceitos nucleares

- **Potencial de repouso**: separação de carga através da membrana, mantida por gradientes iônicos e pela bomba Na⁺/K⁺-ATPase. Custa energia continuamente.
- **Potencial de ação**: evento regenerativo tudo-ou-nada, com limiar, disparado por abertura dependente de voltagem de canais de Na⁺. A informação está na **taxa e no padrão temporal**, não na amplitude.
- **Sinapse**: transmissão química com atraso e ganho ajustável. O ajuste é o substrato da plasticidade.
- **LTP e LTD**: fortalecimento e enfraquecimento duradouros da eficácia sináptica, dependentes de atividade correlacionada e de janela temporal.
- **Circuito e mapa**: organização topográfica em córtices sensoriais; a estrutura espacial preserva relações do estímulo.
- **Métodos e resolução**: eletrofisiologia dá resolução temporal de milissegundos em poucos neurônios; fMRI dá cobertura ampla com resolução temporal de segundos e sinal **indireto** (hemodinâmico). Nenhum método dá as duas coisas.

## Estado epistêmico

| Claim | Afirmação | Status | Evidência/limite |
|---|---|---|---|
| `CLM-COG-NEURO-001` | O potencial de ação é um evento regenerativo tudo-ou-nada, e a informação transmitida está codificada na taxa e no padrão temporal de disparos, não na amplitude. | established | Kandel et al., cap. 8–10. Mecanismo iônico caracterizado desde Hodgkin e Huxley. |
| `CLM-COG-NEURO-002` | A eficácia sináptica é modificável de forma duradoura por padrões de atividade correlacionada (LTP/LTD), e essa plasticidade é candidata a substrato de armazenamento de memória. | supported | Kandel et al., cap. 53–54. **Limite:** a correlação entre bloqueio de LTP e prejuízo de aprendizado é robusta em modelos animais; a demonstração de que uma memória específica *é* um padrão sináptico específico é muito mais limitada. |
| `CLM-COG-NEURO-003` | O sinal de fMRI é hemodinâmico e indireto: mede correlato do consumo metabólico associado à atividade neural, com resolução temporal de segundos. | established | Kandel et al., cap. 6. **Consequência inferencial:** "área X ativa durante a tarefa Y" não estabelece que X implementa Y, nem que X seja necessária. Necessidade exige lesão ou intervenção causal — é o mesmo requisito de identificação de [[Desenho Experimental e Causalidade]] <!-- relation:prerequisite -->. |
| `CLM-COG-NEURO-004` | Não há, no conjunto de fontes auditado aqui, evidência que estabeleça papel funcional de efeitos quânticos coerentes na cognição. | open | Kandel et al. não trata o tema como resultado estabelecido. **Escopo:** este claim registra ausência de evidência no material consultado, e é `open`, não `refuted` — a política do Vault exige contradição efetiva para `refuted`, e ausência de evidência não é isso. As propostas específicas são avaliadas em [[Colapso Objetivo, Decoerência e Biofísica Quântica]] <!-- relation:contrasts -->. |

## Limites e contraexemplos

- **Localização não é explicação**: identificar onde algo acontece não diz como acontece. O mapa não substitui o mecanismo.
- **Inferência reversa é inválida**: da ativação de uma região não se conclui o processo mental, porque regiões participam de muitas funções. É erro de lógica, não de método.
- **Correlato neural ≠ causa suficiente**: a correlação entre estado neural e relato subjetivo não fecha a questão da direção nem exclui causa comum.
- **Modelo animal transfere parcialmente**: mecanismo celular é fortemente conservado; arquitetura cognitiva, muito menos.
- **Neurônio artificial não é neurônio**: a unidade de rede profunda é uma abstração matemática que compartilha nome, não mecanismo. A aresta com IA é de **contraste**, não de evidência.

## Relações

- [[Bioenergética e Termodinâmica dos Sistemas Vivos]] <!-- relation:prerequisite -->
- [[Biologia Molecular e Fluxo de Informação Genética]] <!-- relation:prerequisite -->
- [[Percepção e Psicofísica]] <!-- relation:extends --> — a psicofísica mede o comportamento que estes circuitos implementam.
- [[Memória]] <!-- relation:extends --> — leva `CLM-COG-NEURO-002` até onde a evidência de consolidação, reconsolidação e engrama alcança.
- [[Desenho Experimental e Causalidade]] <!-- relation:prerequisite --> — o requisito de identificação vale para neuroimagem como para qualquer inferência causal.
- [[Fundamentos de Aprendizado de Máquina e Modelos de Linguagem]] <!-- relation:contrasts --> — homonímia de "neurônio" e "aprendizado"; nenhuma transferência de resultado sem fonte que trate ambos.
- [[Colapso Objetivo, Decoerência e Biofísica Quântica]] <!-- relation:contrasts -->
- [[MOC — Cognição]] <!-- relation:navigation -->

## Fontes

- Eric R. Kandel, John D. Koester, Sarah H. Mack e Steven A. Siegelbaum (eds.). *Principles of Neural Science*. 6ª ed., McGraw Hill, 2021. ISBN 978-1-259-64223-4.

## Condição de revisão

Revisar `CLM-COG-NEURO-002` se surgir evidência que identifique a correspondência entre uma memória episódica específica e um padrão sináptico, além de apenas evocar comportamento por manipulação causal.

Desde 2026-07-30 esse limite tem um par em [[Memória]] <!-- relation:extends -->:
`CLM-COG-MEM-008` registra a mesma fronteira como `open`. Os dois claims devem ser
reavaliados em conjunto, mas cada status continua respondendo à formulação e à
evidência da própria linha.
