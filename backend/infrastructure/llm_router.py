"""
services/llm_router.py - Advanced LLM Router with Real Token Streaming
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from models.settings import OLLAMA_URL, settings

logger = logging.getLogger(__name__)


class TaskType(Enum):
    FAST = "fast"
    CODE = "code"
    REASONING = "reasoning"
    CREATIVE = "creative"
    ANALYSIS = "analysis"
    VISION = "vision"


@dataclass
class RouterConfig:
    max_context_tokens: int = 8192
    enable_cost_optimization: bool = True
    enable_load_balancing: bool = False


class LLMRouter:
    """Production-ready LLM Router with robust streaming support."""

    TASK_KEYWORDS = {
        TaskType.CODE: [
            "code",
            "implement",
            "function",
            "class ",
            "def ",
            "import ",
            "api",
            "endpoint",
            "sql",
            "query",
            "bug",
            "fix",
            "refactor",
        ],
        TaskType.REASONING: [
            "why",
            "how",
            "explain",
            "analyze",
            "architecture",
            "design",
            "plan",
            "strategy",
            "compare",
            "reason",
            "optimize",
        ],
        TaskType.CREATIVE: [
            "create",
            "write",
            "story",
            "generate",
            "draft",
            "poem",
            "script",
            "content",
        ],
        TaskType.ANALYSIS: [
            "analyze",
            "review",
            "evaluate",
            "assess",
            "audit",
            "improve",
        ],
        TaskType.FAST: [
            "what",
            "who",
            "when",
            "where",
            "list",
            "simple",
            "quick",
            "brief",
            "summary",
        ],
    }

    def __init__(self, config: RouterConfig | None = None):
        self.config = config or RouterConfig()
        self._call_history: list[dict] = []

        self.models = {
            TaskType.FAST: settings.model_fast,
            TaskType.REASONING: settings.model_reasoning,
            TaskType.CODE: getattr(settings, "model_code", settings.model_fast),
            TaskType.ANALYSIS: settings.model_reasoning,
            TaskType.CREATIVE: settings.model_reasoning,
        }

    def classify_task(
        self, prompt: str | None = None, messages: list[dict] | None = None
    ) -> TaskType:
        """Classify task based on content."""
        if messages:
            content = " ".join(
                msg.get("content", "") for msg in messages if msg.get("role") == "user"
            ).lower()
        elif prompt:
            content = prompt.lower()
        else:
            return TaskType.FAST

        scores = dict.fromkeys(TaskType, 0)

        for task_type, keywords in self.TASK_KEYWORDS.items():
            scores[task_type] = sum(1 for kw in keywords if kw in content)

        return max(scores.items(), key=lambda x: x[1])[0]

    def select_model(
        self,
        task_type: TaskType | None = None,
        prompt: str | None = None,
        messages: list[dict] | None = None,
        context_length: int | None = None,
    ) -> str:
        """Select best model for the task."""
        if task_type is None:
            task_type = self.classify_task(prompt, messages)

        model = self.models.get(task_type)

        if not model or model.strip() == "":
            fallback_order = [TaskType.REASONING, TaskType.FAST, TaskType.CODE]
            for fallback in fallback_order:
                model = self.models.get(fallback)
                if model and model.strip():
                    break

        return model or settings.model_fast or "qwen3.5:9b"

    def route(
        self,
        prompt: str | None = None,
        messages: list[dict] | None = None,
        mode: str | None = None,
        context_length: int | None = None,
    ) -> dict[str, Any]:
        """Main routing method."""
        if mode:
            mode = mode.lower()
            task_type = {
                "fast": TaskType.FAST,
                "code": TaskType.CODE,
                "reasoning": TaskType.REASONING,
                "creative": TaskType.CREATIVE,
                "analysis": TaskType.ANALYSIS,
            }.get(mode)
        else:
            task_type = self.classify_task(prompt, messages)

        model = self.select_model(task_type, prompt, messages, context_length)

        text = prompt or ""
        if messages:
            text = " ".join(
                msg.get("content", "") for msg in messages if msg.get("content")
            )
        estimated_tokens = len(text) // 4

        return {
            "model": model,
            "task_type": task_type.value if task_type else "unknown",
            "estimated_tokens": estimated_tokens,
            "exceeds_context": estimated_tokens > self.config.max_context_tokens,
            "routing_method": "keyword+config",
            "confidence": 0.85,
        }

    def record_call(
        self, model: str, task_type: TaskType, latency_ms: float, success: bool
    ):
        """Record usage for analytics."""
        self._call_history.append(
            {
                "model": model,
                "task_type": task_type.value if task_type else "unknown",
                "latency_ms": latency_ms,
                "success": success,
                "timestamp": datetime.now().isoformat(),
            }
        )

        if len(self._call_history) > 200:
            self._call_history = self._call_history[-200:]

    def generate(
        self,
        prompt: str,
        mode: str = "fast",
        temperature: float = 0.7,
        model: str = "",
        provider: str = "ollama",
    ) -> str:
        """Synchronous generation (kept for compatibility)."""
        # Use user-selected model if provided, otherwise use routing
        if model:
            actual_model = model
            # Clean model name
            for prefix in ["ollama-", "lmstudio-", "lemonade-", "llamacpp-"]:
                if actual_model.startswith(prefix):
                    actual_model = actual_model[len(prefix) :]
                    break
        else:
            routing = self.route(prompt=prompt, mode=mode)
            actual_model = routing["model"]
            # Clean model name
            for prefix in ["ollama-", "lmstudio-", "lemonade-", "llamacpp-"]:
                if actual_model.startswith(prefix):
                    actual_model = actual_model[len(prefix) :]
                    break

        from backend.infrastructure.legacy_llm_router import ModelConfig, OllamaClient

        # Determine base URL based on provider
        if provider == "ollama" or not provider:
            ollama_base = getattr(settings, "ollama_url", OLLAMA_URL).rstrip("/")
            endpoint = "/api/generate"
        elif provider == "lmstudio":
            ollama_base = getattr(
                settings, "lmstudio_url", "http://localhost:1234"
            ).rstrip("/")
            endpoint = "/v1/chat/completions"
        elif provider == "lemonade":
            ollama_base = getattr(
                settings, "lemonade_url", "http://localhost:13305"
            ).rstrip("/")
            endpoint = "/v1/chat/completions"
        else:
            ollama_base = getattr(settings, "ollama_url", OLLAMA_URL).rstrip("/")
            endpoint = "/api/generate"

        if not ollama_base.startswith("http"):
            ollama_base = "http://localhost:11434"

        config = ModelConfig(
            url=f"{ollama_base}{endpoint}",
            model=actual_model,
            timeout=settings.llm_timeout,
            backend=provider,
        )
        client = OllamaClient(config)
        return client.generate(prompt, temperature=temperature)

    async def astream(
        self,
        prompt: str,
        model_type: str = "fast",
        temperature: float = 0.7,
        model: str = "",
        provider: str = "ollama",
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Robust async token streaming.
        """
        # Use user-selected model if provided, otherwise use routing
        if model:
            actual_model = model
            # Clean model name
            for prefix in ["ollama-", "lmstudio-", "lemonade-", "llamacpp-"]:
                if actual_model.startswith(prefix):
                    actual_model = actual_model[len(prefix) :]
                    break
        else:
            routing = self.route(prompt=prompt, mode=model_type)
            actual_model = routing["model"]
            # Clean model name
            for prefix in ["ollama-", "lmstudio-", "lemonade-", "llamacpp-"]:
                if actual_model.startswith(prefix):
                    actual_model = actual_model[len(prefix) :]
                    break

        try:
            from backend.infrastructure.legacy_llm_router import ModelConfig, OllamaClient

            # Determine base URL based on provider
            if provider == "ollama" or not provider:
                ollama_base = getattr(settings, "ollama_url", OLLAMA_URL).rstrip("/")
                endpoint = "/api/generate"
            elif provider == "lmstudio":
                ollama_base = getattr(
                    settings, "lmstudio_url", "http://localhost:1234"
                ).rstrip("/")
                endpoint = "/v1/chat/completions"
            elif provider == "lemonade":
                ollama_base = getattr(
                    settings, "lemonade_url", "http://localhost:13305"
                ).rstrip("/")
                endpoint = "/v1/chat/completions"
            else:
                ollama_base = getattr(settings, "ollama_url", OLLAMA_URL).rstrip("/")
                endpoint = "/api/generate"

            if not ollama_base.startswith("http"):
                ollama_base = "http://localhost:11434"

            config = ModelConfig(
                url=f"{ollama_base}{endpoint}",
                model=actual_model,
                timeout=settings.llm_timeout,
                backend=provider,
            )
            client = OllamaClient(config)

            # Prefer async streaming if available
            if hasattr(client, "astream"):
                async for chunk in client.astream(prompt, temperature=temperature):  # type: ignore[attr-defined]
                    if isinstance(chunk, str):
                        yield chunk
                    elif hasattr(chunk, "content"):
                        yield chunk.content
                    elif isinstance(chunk, dict) and "response" in chunk:
                        yield chunk["response"]

            else:
                # Reliable fallback: run sync stream in executor
                loop = asyncio.get_running_loop()

                def sync_stream():
                    try:
                        return client.stream(prompt, temperature=temperature)
                    except Exception as e:
                        logger.warning(f"Sync stream failed: {e}")
                        return [self.generate(prompt, model_type, temperature)]

                stream_iter = await loop.run_in_executor(None, sync_stream)

                for chunk in stream_iter:
                    if isinstance(chunk, str):
                        yield chunk
                    elif hasattr(chunk, "get") and chunk.get("response"):
                        yield chunk.get("response")
                    elif isinstance(chunk, dict):
                        yield chunk.get("response", str(chunk))
                    await asyncio.sleep(0)  # Allow event loop breathing

        except Exception as e:
            logger.error(f"astream failed for {model}: {e}", exc_info=True)
            # Ultimate fallback
            full_response = self.generate(
                prompt, model_type, temperature, model=model, provider=provider
            )
            chunk_size = 10
            for i in range(0, len(full_response), chunk_size):
                yield full_response[i : i + chunk_size]
                await asyncio.sleep(0.008)


# ======================== Singleton ========================

_router: LLMRouter | None = None


def get_llm_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router


__all__ = ["LLMRouter", "RouterConfig", "TaskType", "get_llm_router"]
