"""LLM wrapper with unified progress tracking."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from models.settings import settings
from backend.infrastructure.llm.progress import LLMProgressTracker

logger = logging.getLogger(__name__)


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
        """Streaming unifié avec tracking de progression."""
        tracker = LLMProgressTracker(backend=self.user_provider)

        try:
            async for chunk in self.router.astream(
                prompt=prompt,
                model_type=model_type,
                temperature=temperature,
                model=self.user_model,
                provider=self.user_provider,
            ):
                # Mise à jour du tracker
                speed = tracker.on_token(chunk)

                if speed is not None:
                    try:
                        from backend.domain.core.events import emit_agent_step

                        emit_agent_step(
                            "progress",
                            f"[{self.user_provider.upper()}] {speed:.1f} tok/s",
                        )
                    except Exception:
                        pass

                # Yield seulement le contenu (pas les stats)
                if isinstance(chunk, dict):
                    if chunk.get("done") or chunk.get("usage"):
                        # Stats finales
                        try:
                            from backend.domain.core.events import emit_agent_step

                            emit_agent_step(
                                "generation_stats",
                                tracker.get_summary(),
                                data=tracker.stats,
                            )
                        except Exception:
                            pass
                        continue  # Ne pas envoyer les stats comme token
                    if "content" in chunk:
                        yield chunk["content"]
                else:
                    yield str(chunk)

        except Exception as e:
            logger.error(f"Streaming error ({self.user_provider}): {e}")
            full = await self.generate(prompt, model_type, temperature)
            yield full

    async def run_node(
        self,
        prompt: str,
        model_type: str = "fast",
        temperature: float = 0.3,
        strip_markdown: bool = False,
        max_retries: int = 1,
    ) -> str:
        """Helper: collect full response from streaming with timeout.

        Retries once on TimeoutError before failing — local models
        (Lemonade/Ollama) sometimes stall on the first request after
        VRAM load, and a single retry often recovers the response.
        """
        timeout = float(settings.llm_timeout)

        last_exc: BaseException | None = None
        for attempt in range(max_retries + 1):
            async def _collect() -> str:
                result = ""
                async for token in self.stream_generate(prompt, model_type, temperature):
                    result += token
                return result

            try:
                full_response = await asyncio.wait_for(_collect(), timeout=timeout)
                last_exc = None
                break
            except asyncio.TimeoutError as e:
                last_exc = e
                if attempt < max_retries:
                    logger.warning(
                        "LLM call timed out after %ss (model_type=%s, attempt %d/%d) — retrying",
                        timeout,
                        model_type,
                        attempt + 1,
                        max_retries + 1,
                    )
                    continue

        if last_exc is not None:
            msg = f"LLM call timed out after {timeout}s (model_type={model_type})"
            logger.error(msg)
            raise TimeoutError(msg) from None

        if strip_markdown:
            cleaned = full_response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:] if lines[0].startswith("```") else lines)
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            return cleaned.strip()
        return full_response
