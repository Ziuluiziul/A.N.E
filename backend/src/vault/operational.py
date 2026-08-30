"""Camada operacional: procedência, não conhecimento.

O dossiê pede duas redes coordenadas e **não misturadas**. A epistêmica é persistente
e vem de `knowledge/`; a operacional é temporal e registra o que os agentes fizeram —
`agente → atividade → evidência → proposta → validação → commit ou rejeição`.

Em produção essa rede nasce da persistência estruturada em `runtime/quorum/`. O Atlas
recebe apenas uma lista branca de metadados: identidade operacional, voto, confiança,
contagem e decisão. Respostas livres nunca atravessam esta fronteira. Sob
`VAULT_DEMO_OPERATIONAL=1` continua existindo uma trilha sintética explicitamente
marcada como demonstração; ela nunca é consequência de falha de leitura.

Duas coisas que esta camada nunca representa: raciocínio interno de modelo, e
qualquer coisa dentro de `knowledge/`.
"""
