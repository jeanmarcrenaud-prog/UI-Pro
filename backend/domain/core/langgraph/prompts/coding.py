"""Re-export de ``CODING_SYSTEM_PROMPT`` depuis ``ui_pro_prompts``.

Conservé pour compatibilité ascendante — les imports via ``..prompts``
fonctionnent toujours.  La source de vérité est
``packages/prompts/src/ui_pro_prompts/coding.py``.
"""

from ui_pro_prompts import CODING_SYSTEM_PROMPT

__all__ = [
    "CODING_SYSTEM_PROMPT",
]
