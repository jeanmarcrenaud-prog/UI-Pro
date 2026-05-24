# llm/router.py - Intelligent Multi-Model Router
"""
Role: Intelligent routing of tasks to best model based on keywords
Used by: orchestrator, code_review, streaming service
"""

import asyncio
import logging
import queue
import threading
from collections.abc import AsyncGenerator, Iterator
from dataclasses import dataclass

from models.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """LLM Backend Configuration"""

    url: str = ""
    model: str = ""
    timeout: int = 120
    backend: str = "ollama"


class OllamaClient:
    """Unified client supporting multiple backends (Ollama, LM Studio, etc.)"""

    def __init__(self, config: ModelConfig | None = None):
        self.config = config or ModelConfig()

    def generate(
        self,
        prompt: str,
        model: str | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
    ) -> str:
        """Synchronous generation."""
        import requests

        model = model or self.config.model
        backend = self.config.backend or "ollama"

        # Determine URL and payload format based on backend
        if backend in ("lmstudio", "lemonade"):
            url = self.config.url or f"{settings.ollama_url}/v1/chat/completions"
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "temperature": temperature,
            }
        else:
            # Ollama format
            url = self.config.url or f"{settings.ollama_url}/api/generate"
            payload = {
                "model": model,
                "prompt": prompt,
                "system": system_prompt or "",
                "stream": False,
                "options": {"temperature": temperature},
            }

        try:
            resp = requests.post(url, json=payload, timeout=self.config.timeout)
            resp.raise_for_status()
            data = resp.json()

            # Parse response based on backend format
            if backend in ("lmstudio", "lemonade"):
                return (
                    data.get("choices", [{}])[0].get("message", {}).get("content", "")
                )
            else:
                return data.get("response", "")
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            error_msg = str(e).lower()
            if "subscription" in error_msg or "upgrade" in error_msg:
                return "[Error: Ce modèle nécessite un abonnement. Utilisez un modèle local.]"
            elif "404" in error_msg:
                return "[Error: Modèle non trouvé. Vérifiez 'ollama list']"
            elif "connection" in error_msg:
                return "[Error: Impossible de se connecter à Ollama/LMStudio.]"
            return f"[Error: {e}]"

    def stream(
        self,
        prompt: str,
        model: str | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        """Streaming response."""
        import json

        import requests

        model = model or self.config.model
        backend = self.config.backend or "ollama"

        # Determine URL and payload format based on backend
        if backend in ("lmstudio", "lemonade"):
            url = self.config.url or f"{settings.ollama_url}/v1/chat/completions"
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            payload = {
                "model": model,
                "messages": messages,
                "stream": True,
                "temperature": temperature,
            }
        else:
            # Ollama format
            url = self.config.url or f"{settings.ollama_url}/api/generate"
            payload = {
                "model": model,
                "prompt": prompt,
                "system": system_prompt or "",
                "stream": True,
                "options": {"temperature": temperature},
            }

        try:
            with requests.post(
                url, json=payload, stream=True, timeout=self.config.timeout
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        text = line.decode().strip()
                        if not text:
                            continue
                        # Handle SSE format
                        if text.startswith("data: "):
                            text = text[6:]
                        if text == "[DONE]":
                            logger.debug(
                                f"[stream] received [DONE] marker for {backend}"
                            )
                            break
                        try:
                            data = json.loads(text)
                            # Parse based on backend format
                            if backend in ("lmstudio", "lemonade", "llamacpp"):
                                content = (
                                    data.get("choices", [{}])[0]
                                    .get("delta", {})
                                    .get("content", "")
                                )
                                finish_reason = data.get("choices", [{}])[0].get(
                                    "finish_reason"
                                )
                                if finish_reason:
                                    logger.debug(
                                        f"[stream] {backend} finish_reason={finish_reason}"
                                    )
                            else:
                                # Ollama format
                                content = data.get("response", "") or data.get(
                                    "thinking", ""
                                )
                                finish_reason = data.get("done", False)
                            if content:
                                yield content
                            if data.get("done", False):
                                logger.debug(
                                    f"[stream] received done=true for {backend}"
                                )
                                break
                            choices = data.get("choices", [])
                            if choices and choices[0].get("finish_reason"):
                                logger.debug(
                                    f"[stream] {backend} finish_reason received, breaking"
                                )
                                break
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse stream line: {text[:50]}")
        except requests.RequestException as e:
            logger.error(f"[OllamaClient.stream] Request error: {e}")
            error_msg = str(e)
            if "subscription" in error_msg.lower() or "upgrade" in error_msg.lower():
                yield "[Error: Ce modèle nécessite un abonnement Ollama. Veuillez sélectionner un modèle local (qwen3.6, gemma4, lfm2, nemotron-cascade-2, qwen3.5:9b)]"
            elif "404" in error_msg:
                yield "[Error: Modèle non trouvé. Vérifiez que le modèle est bien installé localement avec 'ollama list']"
            elif "connection" in error_msg.lower():
                yield "[Error: Impossible de se connecter à Ollama. Vérifiez que le service est démarré.]"
            else:
                yield f"[Error: {e}]"

    async def astream(
        self,
        prompt: str,
        model: str | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """
        True async token streaming using a queue.
        Runs the sync stream in a thread and yields tokens as they arrive.
        """
        q: queue.Queue = queue.Queue()
        loop = asyncio.get_running_loop()

        def _sync_producer():
            """Run sync stream in thread, push tokens to queue."""
            try:
                for token in self.stream(prompt, model, system_prompt, temperature):
                    q.put_nowait((False, token))
                    logger.debug(
                        f"[astream] token sent to queue: {token[:20] if token else '(empty)'}..."
                    )
            except Exception as e:
                logger.error(
                    f"[OllamaClient.astream] sync stream failed: {e}", exc_info=True
                )
                q.put_nowait((True, f"[Streaming Error: {e}]"))
            finally:
                logger.debug("[astream] stream ended, sending sentinel")
                q.put_nowait((True, None))  # Sentinel: done=True, token=None

        t = threading.Thread(
            target=_sync_producer, daemon=False
        )  # Non-daemon to ensure cleanup
        t.start()

        timeout_counter = 0
        max_idle_iterations = 100
        # Use settings for timeout, fallback to 60s
        try:
            from models.settings import settings

            token_timeout = max(
                30, settings.llm_timeout // 2
            )  # Half of LLM timeout, min 30s
        except ImportError:
            token_timeout = 60  # Default 60s

        try:
            while True:
                try:
                    done, token = await asyncio.wait_for(
                        loop.run_in_executor(None, q.get),
                        timeout=token_timeout,  # Configurable timeout per token
                    )
                    timeout_counter = 0
                    if done and token is None:
                        logger.debug("[astream] received sentinel, stream complete")
                        break
                    if token:
                        yield token
                except asyncio.TimeoutError:
                    timeout_counter += 1
                    logger.warning(
                        f"[astream] queue.get timeout, iteration {timeout_counter}"
                    )
                    # Allow more retries for slow models (5 instead of 3)
                    if timeout_counter > 5:
                        logger.error("[astream] too many timeouts, breaking stream")
                        break
        finally:
            t.join(timeout=5)  # Wait up to 5s for thread to finish


# ==================== CONFIG ====================


@dataclass
class ModelsConfig:
    """Configuration multi-modèles"""

    fast: str = ""
    reasoning: str = ""
    code: str = ""
    reasoner: str = ""
    ollama_url: str = ""
    timeout: int = 120

    @classmethod
    def from_settings(cls) -> "ModelsConfig":
        from models.settings import settings

        return cls(
            fast=settings.model_fast,
            reasoning=settings.model_reasoning,
            code=settings.model_code,
            reasoner=settings.model_reasoning,
            ollama_url=f"{settings.ollama_url}/api/generate",
            timeout=120,
        )


# Singleton settings
_settings = ModelsConfig.from_settings()


# ==================== ROUTER ====================


class LLMRouter:
    """Intelligent model router with weighted scoring."""

    def __init__(self, config: ModelsConfig | None = None):
        self.config = config or _settings

    def get_model_for_task(self, task: str) -> str:
        """Score-based model selection."""
        task_lower = task.lower().strip()

        scores = {"code": 0, "reasoner": 0, "fast": 0}

        # Weighted keywords
        keywords = {
            "code": {
                "code": 2,
                "implement": 2,
                "function": 1,
                "def ": 2,
                "class ": 2,
                "bug": 2,
                "fix": 2,
                "refactor": 2,
            },
            "reasoner": {
                "debug": 3,
                "architecture": 3,
                "plan": 2,
                "analyze": 2,
                "design": 2,
                "strategy": 2,
                "complex": 2,
                "optimize": 2,
            },
            "fast": {
                "explain": 2,
                "describe": 2,
                "what": 1,
                "who": 1,
                "simple": 2,
                "summarize": 2,
            },
        }

        for category, kw_dict in keywords.items():
            for kw, weight in kw_dict.items():
                if kw in task_lower:
                    scores[category] += weight

        # Select highest scoring category
        if scores["code"] >= max(scores["reasoner"], scores["fast"]):
            return self.config.code
        elif scores["reasoner"] >= scores["fast"]:
            return self.config.reasoner
        else:
            return self.config.fast

    def _create_model_config(self, model_name: str) -> ModelConfig:
        return ModelConfig(
            url=self.config.ollama_url,
            model=model_name,
            timeout=self.config.timeout,
        )

    def get_for_task(self, task: str) -> OllamaClient:
        model_name = self.get_model_for_task(task)
        logger.debug(f"Routing task → {model_name}")
        return OllamaClient(self._create_model_config(model_name))

    def get_for_mode(self, mode: str) -> OllamaClient:
        """Get client by explicit mode."""
        mode_map = {
            "fast": self.config.fast,
            "code": self.config.code,
            "reasoning": self.config.reasoning,
            "reasoner": self.config.reasoner,
        }
        model_name = mode_map.get(mode.lower(), self.config.fast)
        return OllamaClient(self._create_model_config(model_name))

    def generate(self, prompt: str, mode: str = "fast") -> str:
        """Convenience method."""
        client = self.get_for_mode(mode)
        return client.generate(prompt)


# ====================== Singleton ======================

_router: LLMRouter | None = None


def get_llm_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router


__all__ = ["LLMRouter", "ModelConfig", "OllamaClient", "get_llm_router"]
