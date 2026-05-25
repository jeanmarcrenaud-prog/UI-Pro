"""
Progress Tracker unifié pour tous les backends LLM
Support : Ollama, LM Studio, Lemonade, llama.cpp
"""

import time
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class LLMProgressTracker:
    """Tracker générique de progression et vitesse pour tous les backends."""

    def __init__(self, backend: str = "unknown"):
        self.backend = backend
        self.start_time = time.time()
        self.token_count = 0
        self.last_update = time.time()
        self.stats: Dict[str, Any] = {}

    def on_token(self, chunk: Any) -> float | None:
        """Traite un chunk et retourne la vitesse si mise à jour."""
        now = time.time()

        # Extraction intelligente du contenu selon le backend
        content = self._extract_content(chunk)
        if content:
            self.token_count += max(1, len(content.split()))  # estimation tokens

        # Mise à jour toutes les ~800ms
        if now - self.last_update >= 0.8:
            self.last_update = now
            speed = self.tokens_per_second
            return speed
        return None

    def _extract_content(self, chunk: Any) -> str:
        """Extrait le texte selon le format du backend."""
        if isinstance(chunk, str):
            return chunk

        if isinstance(chunk, dict):
            # Ollama format
            if "content" in chunk:
                return chunk.get("content", "")
            # OpenAI / LM Studio / Lemonade format
            if "choices" in chunk:
                delta = chunk["choices"][0].get("delta", {})
                return delta.get("content", "")
            # Usage stats final
            if chunk.get("done") or chunk.get("usage"):
                self._extract_final_stats(chunk)
                return ""

        return str(chunk)

    def _extract_final_stats(self, chunk: dict):
        """Capture les statistiques finales selon le backend."""
        if self.backend == "ollama":
            self.stats = {
                "eval_count": chunk.get("eval_count"),
                "total_duration": chunk.get("total_duration", 0) / 1e9,
                "prompt_tokens": chunk.get("prompt_eval_count"),
                "completion_tokens": chunk.get("eval_count"),
                "tokens_per_second": chunk.get("eval_count", 0) / (chunk.get("eval_duration", 1) / 1e9 or 1),
            }
        else:
            # OpenAI-compatible (LM Studio, Lemonade)
            usage = chunk.get("usage") or {}
            self.stats = {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "total_duration": time.time() - self.start_time,
                "tokens_per_second": self.tokens_per_second,
            }

    @property
    def tokens_per_second(self) -> float:
        elapsed = time.time() - self.start_time
        return self.token_count / elapsed if elapsed > 0 else 0.0

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time

    def get_summary(self) -> str:
        """Résumé lisible pour l'utilisateur."""
        speed = self.tokens_per_second
        duration = self.elapsed_seconds
        return f"{self.token_count} tokens en {duration:.1f}s ({speed:.1f} tok/s)"
