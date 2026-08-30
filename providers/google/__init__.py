"""Google — API Gemini em free tier, via SDK google-genai.

Distinto de `integrations/google_workspace/`: aqui é chave de API do AI Studio; lá é
projeto no Google Cloud com consentimento OAuth do usuário. Não confundir os dois.
"""

from providers.google.adapter import GoogleAdapter

__all__ = ["GoogleAdapter"]
