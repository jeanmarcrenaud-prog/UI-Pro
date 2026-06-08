"""LLM wrapper with unified progress tracking."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from backend.domain.settings import settings
from backend.infrastructure.llm.progress import LLMProgressTracker

logger = logging.getLogger(__name__)


def _resolve_provider_for_model(model_name: str) -> str | None:
    """Look up which backend currently hosts `model_name`.

    Returns the backend name (e.g. "ollama", "lmstudio") or None if
    the model_discovery cache is cold or the model is unknown. Wraps
    the import in a try/except so this module stays importable in
    test environments that don't have model_discovery wired up.
    """
    if not model_name:
        return None
    try:
        from backend.infrastructure.model_discovery import (
            get_model_discovery,
        )
    except Exception:  # pragma: no cover - import-time guard
        return None
    try:
        return get_model_discovery().get_backend_for_model(model_name)
    except Exception:
        return None


class LLMWrapper:
    def __init__(
        self,
        router,
        user_model: str = "",
        user_provider: str = "ollama",
        force_model: str = "",
        force_provider: str = "",
    ):
        self.router = router
        self.user_model = user_model
        self.user_provider = user_provider
        # Per-node model override: when set, wins over user_model.
        # Used by the orchestrator to route analyze/plan/code/review to
        # different preset tiers (fast / reasoning / code) regardless of
        # the user-selected chat model. Without this, the user_model
        # picked in the chat UI is sent for *every* node, which means a
        # small model (e.g. lfm2.5-1.2b) is forced to do heavy tasks
        # (code gen, review) it can't handle.
        self.force_model = force_model
        # Per-node provider resolution. Three cases:
        #
        #   1) Caller passed force_provider explicitly -> trust it
        #      (e.g. tests, or future per-node overrides).
        #   2) force_model is set but the caller did NOT pass a
        #      provider -> look up which backend actually hosts the
        #      forced model. If the model lives on a DIFFERENT backend
        #      than the user's selected one (common with cross-backend
        #      presets: user picks an Ollama chat model, but the
        #      "fast" tier forces a LM Studio model), switch
        #      force_provider to the right backend. Otherwise the
        #      router forwards the LM Studio model name to Ollama
        #      and gets a 404.
        #   3) No force_model at all -> keep user_provider (legacy
        #      "all nodes use the chat model" behavior).
        #
        # Fallback: if the cache is cold or the model is unknown,
        # inherit user_provider. A 404 from the router is still a
        # clean error -- much better than silently misrouting.
        if force_provider:
            self.force_provider = force_provider
        elif force_model:
            derived = _resolve_provider_for_model(force_model)
            self.force_provider = derived or user_provider
        else:
            self.force_provider = user_provider

    def _resolved(self) -> tuple[str, str]:
        """Return the (model, provider) that should actually be used.

        force_model wins over user_model. Empty force_model keeps the
        legacy "user_model wins" behavior.
        """
        if self.force_model:
            return self.force_model, self.force_provider
        return self.user_model, self.user_provider

    async def generate(
        self,
        prompt: str,
        model_type: str = "fast",
        temperature: float = 0.7,
        max_retries: int = 1,
    ) -> str:
        """Fallback full generation with retry on timeout.

        Local LLMs (Lemonade/Ollama) sometimes stall on the first request
        after VRAM load. One retry recovers the response in most cases.
        """
        timeout = float(settings.llm_timeout)
        model, provider = self._resolved()

        last_exc: BaseException | None = None
        for attempt in range(max_retries + 1):
            loop = asyncio.get_running_loop()
            try:
                return await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: self.router.generate(
                            prompt,
                            model_type,
                            temperature=temperature,
                            model=model,
                            provider=provider,
                        ),
                    ),
                    timeout=timeout,
                )
            except asyncio.TimeoutError as e:
                last_exc = e
                if attempt < max_retries:
                    logger.warning(
                        "LLM generate timed out after %ss (model_type=%s, attempt %d/%d) — retrying",
                        timeout,
                        model_type,
                        attempt + 1,
                        max_retries + 1,
                    )
                    continue

        msg = f"LLM call timed out after {timeout}s (model_type={model_type})"
        logger.error(msg)
        raise TimeoutError(msg) from last_exc

    async def stream_generate(
        self, prompt: str, model_type: str = "fast", temperature: float = 0.7
    ) -> AsyncIterator[str]:
        """Streaming unifié avec tracking de progression."""
        model, provider = self._resolved()
        tracker = LLMProgressTracker(backend=provider)

        try:
            async for chunk in self.router.astream(
                prompt=prompt,
                model_type=model_type,
                temperature=temperature,
                model=model,
                provider=provider,
            ):
                # Mise à jour du tracker
                speed = tracker.on_token(chunk)

                if speed is not None:
                    try:
                        from backend.domain.core.events import emit_agent_step

                        emit_agent_step(
                            "progress",
                            f"[{provider.upper()}] {speed:.1f} tok/s",
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
            logger.error(f"Streaming error ({provider}): {e}")
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
