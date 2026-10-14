"""LLM wrapper with unified progress tracking and Prometheus metrics."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor

from backend.domain.settings import settings
from backend.infrastructure.llm.errors import LLMBackendError
from backend.infrastructure.llm.progress import LLMProgressTracker
from backend.infrastructure.monitoring.llm_metrics import (
    inc_llm_error,
    inc_llm_tokens,
    observe_llm_latency,
    set_active_requests,
)



def _exponential_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 32.0) -> float:
    """Calculate exponential backoff delay with jitter cap."""
    delay = min(base_delay * (2 ** attempt), max_delay)
    return delay

logger = logging.getLogger(__name__)


# ── Hermes recentering: health cache for the ACP backend ───────────────────
_hermes_healthy_cache: dict[str, float | bool] = {}
_HERMES_HEALTH_CACHE_TTL = 60.0  # seconds

# ``HermesACPBackend.health_check`` is a *sync* method that internally calls
# ``asyncio.run``.  ``_resolved`` runs on the event-loop thread (async
# ``generate`` / ``stream_generate`` / ``run_node``), so the probe must run in
# a dedicated worker thread — otherwise ``asyncio.run`` raises RuntimeError and
# Hermes would always look unhealthy.
_hermes_probe_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hermes-health")


def _hermes_healthy() -> bool:
    """Probe the Hermes ACP backend (cached ~60 s) and report its health.

    Returns ``True`` when the ``hermes acp`` subprocess is reachable and a
    full ``initialize`` round-trip succeeds, ``False`` otherwise.  The probe
    is cheap to cache because each node of the pipeline re-enters
    ``_resolved()`` many times per single run; without the cache we would
    pay one spawn+initialize (3–5 s) per token.

    When the probe fails (subprocess absent, timed out, or Hermes not
    configured), the caller falls back to Ollama so existing setups keep
    working without reconfiguring."""
    now = time.monotonic()
    ts = _hermes_healthy_cache.get("ts")
    if isinstance(ts, float) and now - ts < _HERMES_HEALTH_CACHE_TTL:
        return bool(_hermes_healthy_cache.get("value", False))

    try:
        from backend.infrastructure.llm.factory import get_backend

        # Build a Hermes ACP backend (uses the user's real config.yaml when
        # settings.hermes_llm_base_url/model are empty, so we don't clobber).
        backend = get_backend("hermes_acp")
        # health_check() calls asyncio.run() internally, which raises
        # RuntimeError when invoked from the event-loop thread (the normal
        # path: _resolved() is called from async generate/stream_generate/
        # run_node).  Probe in a worker thread with a hard deadline instead.
        result = _hermes_probe_pool.submit(backend.health_check).result(timeout=5.0)
    except Exception:  # pragma: no cover — probe must never crash the pipeline
        result = {"status": "error", "error": ""}

    healthy = bool(result.get("status") == "ok")
    _hermes_healthy_cache["ts"] = now
    _hermes_healthy_cache["value"] = healthy
    return healthy


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

        Hermes recentering: when the user selected a Hermes provider and the
        Hermes ACP backend is healthy, route to ``hermes_acp`` (the model is
        chosen by Hermes itself).  Otherwise fall back to the user's provider
        (e.g. Ollama) so existing setups keep working.
        """
        if self.force_model:
            return self.force_model, self.force_provider
        from .hermes_bridge import is_hermes_provider

        if is_hermes_provider(self.user_provider):
            # Hermes recentering: user chose a Hermes provider.  Route to the
            # ACP backend (model chosen by Hermes) only when it is healthy;
            # otherwise fall back to Ollama so existing setups keep working.
            return (self.user_model or ""), "hermes_acp" if _hermes_healthy() else "ollama"
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
        start = time.monotonic()
        set_active_requests(provider, 1)

        last_exc: BaseException | None = None
        for attempt in range(max_retries + 1):
            loop = asyncio.get_running_loop()
            try:
                result = await asyncio.wait_for(
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
                set_active_requests(provider, 0)
                observe_llm_latency(provider, time.monotonic() - start, model_type)
                inc_llm_tokens(provider, len(result))
                return result
            except (asyncio.TimeoutError, LLMBackendError) as e:
                last_exc = e
                inc_llm_error(
                    provider,
                    "timeout" if isinstance(e, asyncio.TimeoutError) else "backend_error",
                )
                if attempt < max_retries:
                    delay = _exponential_backoff(attempt)
                    logger.warning(
                        "LLM generate failed (model_type=%s, attempt %d/%d) — retrying in %.1fs: %s",
                        model_type,
                        attempt + 1,
                        max_retries + 1,
                        delay,
                        e,
                    )
                    await asyncio.sleep(delay)
                    continue

        if isinstance(last_exc, LLMBackendError):
            msg = f"LLM backend error after {max_retries + 1} attempt(s) (model_type={model_type}): {last_exc}"
            logger.error(msg)
            set_active_requests(provider, 0)
            raise LLMBackendError(msg) from last_exc
        msg = f"LLM call timed out after {timeout}s (model_type={model_type})"
        logger.error(msg)
        set_active_requests(provider, 0)
        raise TimeoutError(msg) from last_exc

    async def stream_generate(
        self, prompt: str, model_type: str = "fast", temperature: float = 0.7
    ) -> AsyncIterator[str]:
        """Streaming unifié avec tracking de progression."""
        model, provider = self._resolved()
        tracker = LLMProgressTracker(backend=provider)
        start = time.monotonic()
        token_count = 0
        set_active_requests(provider, 1)

        try:
            async for chunk in self.router.astream(
                prompt=prompt,
                model_type=model_type,
                temperature=temperature,
                model=model,
                provider=provider,
            ):
                # Comptage de tokens pour métriques
                if isinstance(chunk, dict) and "content" in chunk:
                    token_count += 1
                elif isinstance(chunk, str):
                    token_count += 1

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

            # Streaming terminé avec succès — enregistrer les métriques
            set_active_requests(provider, 0)
            observe_llm_latency(provider, time.monotonic() - start, model_type)
            inc_llm_tokens(provider, token_count)

        except Exception as e:
            logger.error(f"Streaming error ({provider}): {e}")
            inc_llm_error(provider, "stream_error")
            set_active_requests(provider, 0)
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

        Retries once on TimeoutError or LLMBackendError before failing —
        local models (Lemonade/Ollama) sometimes stall on the first request
        after VRAM load, and a single retry often recovers the response.
        """
        timeout = float(settings.llm_timeout)
        model, provider = self._resolved()
        start = time.monotonic()
        set_active_requests(provider, 1)

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
            except (asyncio.TimeoutError, LLMBackendError) as e:
                last_exc = e
                inc_llm_error(
                    provider,
                    "timeout" if isinstance(e, asyncio.TimeoutError) else "backend_error",
                )
                if attempt < max_retries:
                    delay = _exponential_backoff(attempt)
                    logger.warning(
                        "LLM call failed (model_type=%s, attempt %d/%d) — retrying in %.1fs: %s",
                        model_type,
                        attempt + 1,
                        max_retries + 1,
                        delay,
                        e,
                    )
                    await asyncio.sleep(delay)
                    continue

        if last_exc is not None:
            if isinstance(last_exc, LLMBackendError):
                msg = f"LLM backend error after {max_retries + 1} attempt(s) (model_type={model_type}): {last_exc}"
                logger.error(msg)
                set_active_requests(provider, 0)
                raise LLMBackendError(msg) from last_exc
            msg = f"LLM call timed out after {timeout}s (model_type={model_type})"
            logger.error(msg)
            set_active_requests(provider, 0)
            raise TimeoutError(msg) from None

        # Overall metrics (complements stream_generate's per-stream metrics)
        set_active_requests(provider, 0)
        observe_llm_latency(provider, time.monotonic() - start, model_type)
        inc_llm_tokens(provider, len(full_response))

        if strip_markdown:
            cleaned = full_response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:] if lines[0].startswith("```") else lines)
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            return cleaned.strip()
        return full_response
