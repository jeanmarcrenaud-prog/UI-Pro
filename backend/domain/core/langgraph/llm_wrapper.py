"""LLM wrapper with streaming support, stats capture, and progress tracking."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator

from models.settings import settings

logger = logging.getLogger(__name__)


class OllamaProgressTracker:
    """Real-time tokens/second tracker for streaming."""

    def __init__(self):
        self.start_time = time.time()
        self.token_count = 0
        self.last_update = time.time()

    def on_token(self, token: str):
        """Record a token, emit progress every ~800ms."""
        self.token_count += len(token.split()) or 1
        now = time.time()

        if now - self.last_update >= 0.8:
            self.last_update = now
            speed = self.tokens_per_second
            logger.debug("Streaming speed: %.1f tok/s", speed)
            try:
                from backend.domain.core.events import emit_agent_step

                emit_agent_step("progress", f"Generation speed: {speed:.1f} tok/s")
            except Exception:
                pass

    @property
    def tokens_per_second(self) -> float:
        elapsed = time.time() - self.start_time
        return self.token_count / elapsed if elapsed > 0 else 0.0

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time


class LLMWrapper:
    def __init__(self, router, user_model: str = "", user_provider: str = "ollama"):
        self.router = router
        self.user_model = user_model
        self.user_provider = user_provider

    async def generate(
        self, prompt: str, model_type: str = "fast", temperature: float = 0.7
    ) -> str:
        """Fallback full generation."""
        loop = asyncio.get_running_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: self.router.generate(
                    prompt,
                    model_type,
                    temperature=temperature,
                    model=self.user_model,
                    provider=self.user_provider,
                ),
            ),
            timeout=float(settings.llm_timeout),
        )

    async def stream_generate(
        self, prompt: str, model_type: str = "fast", temperature: float = 0.7
    ) -> AsyncIterator[str]:
        """Real token streaming with stats capture and progress tracking."""
        stats: dict | None = None
        tracker = OllamaProgressTracker()

        try:
            if hasattr(self.router, "astream"):
                async for chunk in self.router.astream(
                    prompt=prompt,
                    model_type=model_type,
                    temperature=temperature,
                    model=self.user_model,
                    provider=self.user_provider,
                ):
                    if isinstance(chunk, dict):
                        # Stats dict from Ollama backend (final done line)
                        if chunk.get("done"):
                            stats = {
                                "eval_count": chunk.get("eval_count", 0),
                                "total_duration": chunk.get("total_duration", 0) / 1e9,
                                "prompt_eval_count": chunk.get("prompt_eval_count", 0),
                                "tokens_per_second": chunk.get("eval_count", 0)
                                / (chunk.get("eval_duration", 1) / 1e9),
                            }
                            logger.info(
                                "Generation stats — tokens: %d, time: %.2fs, speed: %.1f tok/s",
                                stats["eval_count"],
                                stats["total_duration"],
                                stats["tokens_per_second"],
                            )
                            try:
                                from backend.domain.core.events import emit_agent_step
                                msg = f"✅ Terminé - {stats['eval_count']} tokens en {stats['total_duration']:.1f}s"
                                emit_agent_step("generation_stats", msg, data=stats)
                            except Exception:
                                pass
                        continue  # Don't yield stats dict as a token

                    # String token
                    token_str = str(chunk) if not isinstance(chunk, str) else chunk
                    tracker.on_token(token_str)
                    yield token_str
            else:
                full = await self.generate(prompt, model_type, temperature)
                for i in range(0, len(full), 8):
                    yield full[i : i + 8]
                    await asyncio.sleep(0.015)
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            full = await self.generate(prompt, model_type, temperature)
            yield full

        # Log final speed if no Ollama stats were provided
        if stats is None and tracker.token_count > 0:
            logger.info(
                "Streaming complete — tokens: %d, time: %.2fs, speed: %.1f tok/s (client-side)",
                tracker.token_count,
                tracker.elapsed_seconds,
                tracker.tokens_per_second,
            )

    async def run_node(
        self,
        prompt: str,
        model_type: str = "fast",
        temperature: float = 0.3,
        strip_markdown: bool = False,
    ) -> str:
        """Helper: collect full response from streaming."""
        full_response = ""
        async for token in self.stream_generate(prompt, model_type, temperature):
            full_response += token

        if strip_markdown:
            cleaned = full_response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:] if lines[0].startswith("```") else lines)
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            return cleaned.strip()
        return full_response
