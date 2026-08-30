"""Canal efêmero do raciocínio do provedor. Não é a trilha operacional.

A trilha canônica recusa texto de modelo — `strip_reasoning` e a lista branca de
eventos existem para o corpus e o quórum não herdarem scratchpad. Este pacote é o
outro tubo: o que o endpoint emite **durante** a chamada, para a cena acompanhar,
sem gravar em `knowledge/`, em proposta nem em `runtime/modelos`.
"""

from vault.cognition.bus import CognitionBus
from vault.cognition.models import COGNITION_KINDS, CognitionFrame
from vault.cognition.recorder import CognitionRecorder
from vault.cognition.store import CognitionStore, CognitionStoreError

__all__ = [
    "COGNITION_KINDS",
    "CognitionBus",
    "CognitionFrame",
    "CognitionRecorder",
    "CognitionStore",
    "CognitionStoreError",
]
