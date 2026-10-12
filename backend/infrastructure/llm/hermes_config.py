"""Read-only readiness evaluation for the Hermes-agent LLM configuration.

See ``docs/plans/spec-hermes-config-check.md``. This module NEVER mutates
configuration and NEVER triggers a GPU/model load: it only probes the local
LLM backends (LM Studio ``/v1/models``, Ollama ``/api/tags``) with a short
timeout and returns a stable JSON report the frontend can render as a banner.

Local-first by design (spec rule #1): when no explicit ``hermes_llm_base_url``
is set, the default LM Studio / Ollama endpoints are auto-detected so a fresh
install still reports useful readiness instead of a blank state.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from backend.infrastructure.llm.hermes_home import resolve_effective_hermes_llm

logger = logging.getLogger(__name__)

# Short probe deadline (spec: "timeout 3s").
_PROBE_TIMEOUT = 3.0

# A local model above this size is considered "heavy" for a single GPU. When
# one is already present we do NOT recommend adding another big model on GPU
# (spec rule #2) and flag ``gpu_headroom_ok = false``.
_LARGE_MODEL_PARAM_B = 15.0

# Matches the parameter count in common model names ("aura-4b", "qwen3.8-27b",
# "google/gemma-4-12b-qat"). The lookahead avoids matching garbage like "8bit".
_PARAM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*b(?![a-z0-9])", re.IGNORECASE)


def _param_count(model_name: str) -> float | None:
    """Best-effort parameter count (billions) parsed from a model name."""
    match = _PARAM_RE.search(model_name or "")
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:  # pragma: no cover - regex guarantees a float
        return None


def _classify_backend(base_url: str) -> str:
    """Map a base URL to one of: lmstudio | ollama | nvidia | none."""
    value = (base_url or "").lower()
    if not value:
        return "none"
    if "nvidia" in value:
        return "nvidia"
    if ":1234" in value or "lmstudio" in value or "lm-studio" in value:
        return "lmstudio"
    if ":11434" in value or "ollama" in value:
        return "ollama"
    if "/v1" in value:
        # Generic OpenAI-compatible endpoint → treat as LM Studio style.
        return "lmstudio"
    return "none"


def _lm_models_url(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    return f"{base}/models" if base.endswith("/v1") else f"{base}/v1/models"


def _ollama_models_url(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    for suffix in ("/api/generate", "/api/chat", "/api/tags"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return f"{base}/api/tags"


def _extract_models(data: Any) -> list[str]:
    """Read model identifiers from an LM Studio or Ollama payload."""
    if not isinstance(data, dict):
        return []
    raw = data.get("data")
    if raw is None:
        raw = data.get("models")
    models: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                name = item.get("id") or item.get("name") or item.get("model")
                if name:
                    models.append(str(name))
            elif isinstance(item, str):
                models.append(item)
    return models


def _probe_models(url: str) -> tuple[bool, list[str]]:
    """GET ``url`` and return ``(reachable, model_names)``.

    Never raises — any error (connection refused, timeout, bad JSON) yields
    ``(False, [])`` so the report degrades gracefully.
    """
    try:
        import httpx

        with httpx.Client(timeout=_PROBE_TIMEOUT) as client:
            response = client.get(url)
        if response.status_code != 200:
            return False, []
        data = response.json()
    except Exception as exc:  # noqa: BLE001 - report-only, degrade gracefully
        logger.debug("Hermes config probe failed for %s: %s", url, exc)
        return False, []
    return True, _extract_models(data)


def _autodetect(lm_url: str, ollama_url: str) -> tuple[str, bool, list[str]]:
    """Probe the default local backends in order (LM Studio, then Ollama)."""
    lm_ok, lm_models = _probe_models(_lm_models_url(lm_url))
    if lm_ok:
        return "lmstudio", True, lm_models
    ollama_ok, ollama_models = _probe_models(_ollama_models_url(ollama_url))
    if ollama_ok:
        return "ollama", True, ollama_models
    return "none", False, []


def evaluate_hermes_config(settings: Any) -> dict[str, Any]:
    """Return a stable readiness report for the Hermes-agent config.

    Pure/report-only: never writes settings, never loads a GPU model.
    """
    model, raw_base = resolve_effective_hermes_llm(settings)
    configured = bool(raw_base) and bool(model)

    lm_url = (getattr(settings, "lmstudio_url", "") or "http://localhost:1234").rstrip("/")
    ollama_url = (getattr(settings, "ollama_url", "") or "http://localhost:11434").rstrip("/")

    if raw_base:
        backend = _classify_backend(raw_base)
        if backend == "nvidia":
            # Remote API — no local probe, no local install required.
            llm_reachable, available_models = False, []
        elif backend == "ollama":
            llm_reachable, available_models = _probe_models(_ollama_models_url(raw_base))
        else:
            # lmstudio or unrecognized OpenAI-style endpoint.
            llm_reachable, available_models = _probe_models(_lm_models_url(raw_base))
    else:
        backend = "none"
        backend, llm_reachable, available_models = _autodetect(lm_url, ollama_url)

    # Recommended model: lightest available (favoring small FR/EN multi-use
    # models already present) — spec rule #2.
    def _size_key(name: str) -> float:
        count = _param_count(name)
        return count if count is not None else 1e9

    recommended_model = min(available_models, key=_size_key) if available_models else ""

    # VRAM-aware: a heavy model already present means no GPU headroom to add
    # another big model.
    gpu_headroom_ok = not any(
        (count := _param_count(name)) is not None and count > _LARGE_MODEL_PARAM_B
        for name in available_models
    )

    if backend == "none":
        needs_install = True
        message = "Aucun LLM local détecté. Installez LM Studio ou Ollama."
    elif backend in ("lmstudio", "ollama") and not llm_reachable:
        needs_install = True
        message = (
            f"Backend {backend} configuré mais injoignable. "
            "Vérifiez qu'il est bien lancé."
        )
    elif backend in ("lmstudio", "ollama") and not available_models:
        needs_install = True
        message = f"Aucun modèle disponible sur {backend}. Déployez un modèle."
    elif backend == "nvidia":
        needs_install = False
        message = f"Hermes configuré via NVIDIA API · model: {model}"
    elif not gpu_headroom_ok:
        needs_install = False
        message = (
            f"Modèle lourd déjà chargé (>15B). Recommandé : "
            f"{recommended_model} (plus léger)."
        )
    elif not configured:
        needs_install = False
        message = f"Hermes prêt. Modèle recommandé : {recommended_model}."
    else:
        needs_install = False
        message = f"Hermes prêt · model: {model}"

    return {
        "configured": configured,
        "base_url": raw_base or None,
        "model": model,
        "backend": backend,
        "llm_reachable": llm_reachable,
        "available_models": available_models,
        "recommended_model": recommended_model,
        "gpu_headroom_ok": gpu_headroom_ok,
        "needs_install": needs_install,
        "message": message,
    }


__all__ = ["evaluate_hermes_config"]
