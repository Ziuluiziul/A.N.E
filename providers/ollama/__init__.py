"""Ollama Cloud — a própria API da Ollama servida em ollama.com, não um SDK.

Nada aqui fala com uma instalação local: `https://ollama.com/api` é o host remoto
documentado, e a chave vai no header `Authorization: Bearer`. O endpoint local
(`localhost:11434`) usa o mesmo protocolo e dispensa credencial, mas não é o que este
adaptador alcança.
"""

from providers.ollama.adapter import OllamaAdapter

__all__ = ["OllamaAdapter"]
