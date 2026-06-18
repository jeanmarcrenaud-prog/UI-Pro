"""``ui_pro_prompts`` — standalone prompt constants from the UI-Pro pipeline.

Exports:

- ``CODING_SYSTEM_PROMPT`` — French-language system prompt for the
  ``coding_node`` code generation task.
"""

from .coding import CODING_SYSTEM_PROMPT

__all__ = [
    "CODING_SYSTEM_PROMPT",
]
