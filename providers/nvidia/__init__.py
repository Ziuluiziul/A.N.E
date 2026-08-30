"""NVIDIA Build / NIM — endpoints gratuitos.

O SDK da OpenAI aparece aqui apenas como cliente compatível apontado para
integrate.api.nvidia.com. Nenhum modelo da OpenAI é usado, e nenhuma chave da
OpenAI é lida.
"""

from providers.nvidia.adapter import NvidiaAdapter

__all__ = ["NvidiaAdapter"]
