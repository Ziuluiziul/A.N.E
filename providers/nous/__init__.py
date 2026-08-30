"""Nous Research — a API de inferência oficial em inference-api.nousresearch.com.

Documentação: https://portal.nousresearch.com/api-docs. O catálogo é público e
a chave é por conta (créditos ou assinatura no portal). Só variantes ``:free``
entram, pelo mesmo contrato do OpenRouter.
"""

from providers.nous.adapter import NousAdapter

__all__ = ["NousAdapter"]
