"""
code_extractor/__init__.py — Extraction multi-stratégie de code depuis les réponses LLM.

Ce package transforme la sortie brute d'un LLM en dictionnaires ``{files: {name: code}}``
validés, en passant par plusieurs stratégies de parsing (blocs ```python, JSON,
détection directe) et une chaîne de réparation progressive (indentation, syntaxe).

Modules
-------
- extractor : 7 stratégies de parsing séquentielles + finalisation
- models    : Modèles Pydantic avec validation compilation Python et vérifications sécurité
- repair    : Utilitaires de réparation pour les erreurs courantes des LLM
"""

from .extractor import extract_code_dict

__all__ = ["extract_code_dict"]
