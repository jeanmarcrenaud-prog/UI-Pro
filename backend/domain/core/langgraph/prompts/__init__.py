"""Prompts centralisés du pipeline LangGraph.

Re-exporte les constantes depuis le package ``ui_pro_prompts`` (standalone,
publié sur PyPI).  Les sections dynamiques (exemples de syntaxe, qualité
par langage, contexte de correction) sont ajoutées au moment de la
construction du prompt dans le nœud lui-même.
"""

from ui_pro_prompts import CODING_SYSTEM_PROMPT

__all__ = [
    "CODING_SYSTEM_PROMPT",
]
