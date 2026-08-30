"""Model Work Orchestrator: distribui tarefas entre endpoints comprovados.

Quatro peças, cada uma com uma responsabilidade que não vaza para as outras:
`roles` define quem faz o quê, `quotas` diz quando uma chamada pode acontecer,
`orchestrator` escolhe e executa, e `store` guarda entrada e saída onde elas possam
ser auditadas depois.

Nada aqui promove conhecimento. O orquestrador também conduz as chamadas do quórum,
mas schema, decisão e persistência do painel pertencem a ``vault.quorum``; promoção
continua sendo uma camada posterior.
"""
