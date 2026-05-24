"""LLM wrapper with streaming support."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from models.settings import settings

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
        """Real token streaming."""
        try:
            if hasattr(self.router, "astream"):
                async for chunk in self.router.astream(
                    prompt=prompt,
                    model_type=model_type,
                    temperature=temperature,
                    model=self.user_model,
                    provider=self.user_provider,
                ):
                    if isinstance(chunk, str):
                        yield chunk
                    elif hasattr(chunk, "content") and chunk.content:
                        yield chunk.content
                    elif isinstance(chunk, dict) and chunk.get("content"):
                        yield chunk["content"]
            else:
                full = await self.generate(prompt, model_type, temperature)
                for i in range(0, len(full), 8):
                    yield full[i : i + 8]
                    await asyncio.sleep(0.015)
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            full = await self.generate(prompt, model_type, temperature)
            yield full

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
