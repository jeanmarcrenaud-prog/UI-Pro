"""Base helpers for LangGraph pipeline nodes — timing, LLM setup, token tracking.

Extracted from the monolithic ``nodes.py`` to keep the node functions focused
on business logic rather than infrastructure boilerplate.
"""

from __future__ import annotations

import functools
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Literal

from backend.domain.settings import settings

from ..state import AgentState, CodeData, PlanData, ReviewData, StepInfo

logger = logging.getLogger(__name__)


# ── Per-node token counting for Agent Canvas ─────────────────────────────

_node_token_counts: dict[str, int] = {}
"""Module-level dict tracking approximate token counts per node.

Each node function stores ``len(response)`` (character-based token
approximation) after its LLM call.  ``@_timed_node`` reads and clears
the entry in its ``finally`` block so the count is included in the
completion event sent to the frontend Agent Canvas.
"""


# ── Step-tracking helpers for Agent Canvas state ─────────────────────────


def _step_start(state: AgentState, name: str) -> None:
    """Mark a pipeline step as ``running`` in ``steps_history`` and set
    ``current_step``.  Call this at the top of each node function."""
    model = (state.get("metadata") or {}).get("model", "")
    step: StepInfo = {
        "name": name,
        "status": "running",
        "model_used": model or None,
        "tokens": 0,
        "duration_ms": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    history = list(state.get("steps_history", []))
    history.append(step)
    state["current_step"] = name
    state["steps_history"] = history


def _step_done(
    state: AgentState,
    name: str,
    status: Literal["done", "error"] = "done",
) -> dict[str, Any]:
    """Update the most recent ``steps_history`` entry for *name* with
    final token count and duration, then return a dict with the updated
    ``current_step`` and ``steps_history`` for the node to merge into
    its return value.

    Usage::

        return _step_done(state, "analyzing") | {
            "task_type": task_json,
        }
    """
    history = list(state.get("steps_history", []))
    for step in reversed(history):
        if step.get("name") == name and step.get("status") == "running":
            step["status"] = status
            step["tokens"] = _node_token_counts.get(name, 0)
            break
    state["steps_history"] = history
    return {"current_step": name, "steps_history": history}


# ── Timing decorator for node execution metrics ──────────────────────────


def _timed_node(name: str):
    """Decorator that records node execution duration as a Prometheus histogram
    and emits a step-completion event with the measured duration and token
    count so the frontend Agent Canvas can display live per-node metrics.

    Usage::

        @_timed_node("analyzing")
        async def analyzing_node(state: AgentState) -> AgentState: ...
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(state, *args, **kwargs):
            # Reset token counter before the node runs (the node function
            # will update it via _node_token_counts[name] = ...)
            _node_token_counts[name] = 0
            start = time.monotonic()
            try:
                return await func(state, *args, **kwargs)
            finally:
                duration = time.monotonic() - start
                token_count = _node_token_counts.pop(name, 0)
                try:
                    from backend.infrastructure.monitoring.pipeline_metrics import (
                        observe_node_duration,
                    )

                    observe_node_duration(name, duration)
                except Exception:
                    pass
                # Push to in-memory rolling store for the REST metrics endpoint
                try:
                    from backend.infrastructure.monitoring.pipeline_metrics_store import (
                        observe_node,
                    )

                    observe_node(name, duration, token_count)
                except Exception:
                    pass
                # Emit step completion with duration + token count for
                # the Agent Canvas
                _emit_step(
                    name,
                    "completed",
                    data={"duration": duration, "tokens": token_count},
                )

        return wrapper

    return decorator


# ========================================
# Helpers
# ========================================


def _get_user_message(state: AgentState) -> str:
    messages = state.get("messages", [])
    msg = messages[0] if messages else None
    return msg.get("content", "") if msg else ""


def _get_model_info(state: AgentState) -> tuple[str, str]:
    metadata = state.get("metadata", {})
    return (metadata or {}).get("model", ""), (metadata or {}).get("provider", "ollama")


def _clean_plan(plan: PlanData | None) -> dict[str, object]:
    if plan is None:
        return {}
    return {k: v for k, v in plan.items() if k not in ("raw", "thinking", "analysis")}


_llm_router_instance = None


def _get_llm_router():
    global _llm_router_instance
    if _llm_router_instance is None:
        from backend.infrastructure.llm_router import LLMRouter

        _llm_router_instance = LLMRouter()
    return _llm_router_instance


def _record_error(state: AgentState, node_name: str, error: str) -> None:
    """Append an error entry to ``error_history`` in the state, then emit a
    step event so the frontend Debug UI can display it in real time."""
    entry = {
        "node": node_name,
        "error": error,
        "attempt": state.get("attempt", 0),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    history = list(state.get("error_history", []))
    history.append(entry)
    state["error_history"] = history
    # Forward to frontend via event bus
    _emit_step(node_name, f"❌ {error}", data={"error": entry})


def _emit_step(phase: str, message: str, data: dict | None = None):
    try:
        from backend.domain.core.events import emit_agent_step

        emit_agent_step(phase, message, data=data)
    except Exception:
        pass


# ========================================
# Language detection helpers
# ========================================

_LANG_KEYWORDS: dict[str, set[str]] = {
    "powershell": {"powershell", "pwsh", "ps1", "posh", "microsoft teams"},
    "bash": {"bash", "shell script", "sh ", ".sh"},
    "batch": {".bat", ".cmd", "batch"},
    "javascript": {"javascript", "js ", ".js", "nodejs", "node.js"},
    "typescript": {"typescript", "ts ", ".ts"},
}

_LANG_CONFIG: dict[str, dict[str, str]] = {
    "python": {"ext": "py", "block": "python", "name": "Python"},
    "powershell": {"ext": "ps1", "block": "powershell", "name": "PowerShell"},
    "bash": {"ext": "sh", "block": "bash", "name": "Bash"},
    "batch": {"ext": "bat", "block": "batch", "name": "Batch"},
    "javascript": {"ext": "js", "block": "javascript", "name": "JavaScript"},
    "typescript": {"ext": "ts", "block": "typescript", "name": "TypeScript"},
}

_DEFAULT_LANG = "python"


def _detect_language(user_message: str) -> str:
    """Detect the programming language requested by the user.

    Uses keyword matching on the lowercased user message. Returns
    the language key (e.g. 'python', 'powershell', 'bash') or
    the default 'python' when no explicit language is mentioned.
    """
    msg_lower = user_message.lower()
    for lang, keywords in _LANG_KEYWORDS.items():
        if any(kw in msg_lower for kw in keywords):
            return lang
    return _DEFAULT_LANG


def _get_lang_config(language: str) -> dict[str, str]:
    """Get language config (ext, block, name) for a given language key."""
    return _LANG_CONFIG.get(language, _LANG_CONFIG[_DEFAULT_LANG])


def _build_code_quality_section(language: str) -> str:
    """Build language-specific code quality rules for the coding prompt."""
    cfg = _get_lang_config(language)
    lang_name = cfg["name"]

    if language == "python":
        return (
            "CODE QUALITY (apply unless the user explicitly opts out):\n"
            "- Entry-point file MUST use `if __name__ == '__main__':` guard so it can be safely imported without side effects\n"
            "- All HTTP calls MUST have an explicit `timeout` argument (e.g. `timeout=10`). Never call `urlopen()` without a timeout\n"
            "- Wrap network, HTTP-status, and parse failures in a single `try/except` with three distinct branches:\n"
            "    except urllib.error.URLError as e:   # network / DNS / connection refused\n"
            "    except urllib.error.HTTPError as e:  # server returned 4xx / 5xx\n"
            "    except json.JSONDecodeError:         # response was not valid JSON\n"
            "  Each branch MUST print a different, human-readable message so the failure mode is obvious\n"
            "- Use `with urllib.request.urlopen(...) as resp:` for auto-cleanup of the HTTP connection\n"
            "- Do NOT invent API keys. Free public APIs (Open-Meteo, wttr.in, ipapi.co, CoinGecko, etc.) require no key. If you receive 401/403, the URL or parameter is wrong, not the key\n"
            "- When the user specifies an output format (table, list, JSON, CSV, \u2026), follow it EXACTLY \u2014 don't downgrade to bare `print()` calls\n"
            "- Raise `ValueError` for bad inputs, `RuntimeError` for runtime failures. Do NOT `print('error:', e); sys.exit(1)` \u2014 callers and the auto-fix loop need to see the exception"
        )
    elif language == "powershell":
        return (
            f"{lang_name} CODE QUALITY:\n"
            "- Begin EVERY script with `#Requires -Version 5.1` (or `#Requires -Modules ...`) for explicit dependency declaration\n"
            "- Use `[CmdletBinding()]` + `param()` block for ALL advanced functions and scripts — never rely on `$args` positional magic\n"
            "- Prefer `Write-Output` for data (goes to pipeline), `Write-Host` ONLY for host UI (cannot be captured), "
            "`Write-Verbose`/`Write-Debug` for diagnostics, `Write-Error` or `throw` for errors\n"
            "- Use `try { } catch { } finally { }` generously — never leave a fallible operation unprotected\n"
            "- Set `$ErrorActionPreference = 'Stop'` at the script start so errors are terminating by default; "
            "use `-ErrorAction SilentlyContinue` ONLY on intentionally ignored failures\n"
            "- When calling external APIs with `Invoke-RestMethod`, ALWAYS set `-TimeoutSec` (e.g. `30`) and wrap in `try/catch` for network, HTTP status, and JSON parse failures\n"
            "- Check `$LASTEXITCODE` immediately after calling native EXEs (e.g. `if ($LASTEXITCODE -ne 0) { throw \"...\" }`)\n"
            "- Use splatting (`@Params`) for cmdlets with 3+ arguments — keeps lines under 120 chars and improves readability\n"
            "- Structure advanced functions with `begin { }` / `process { }` / `end { }` blocks for correct pipeline behavior\n"
            "- Emit structured data via `[PSCustomObject]@{ ... }` instead of concatenated strings — enables further pipeline processing\n"
            "- Do NOT invent API keys \u2014 use free/public APIs where possible\n"
            "- For modular code, prefer `.psm1` modules with a `.psd1` manifest over monolithic `.ps1` scripts"
        )
    elif language in ("bash", "shell"):
        return (
            "CODE QUALITY:\n"
            "- Start with `#!/usr/bin/env bash` shebang\n"
            "- Use `set -euo pipefail` for strict error handling\n"
            "- Check exit codes and handle errors gracefully\n"
            "- Use `curl -fsSL` with `--connect-timeout` and `--max-time` for HTTP calls\n"
            "- Add meaningful error messages: `echo \"Error: ...\" >&2; exit 1`\n"
            "- Quote all variable expansions: `\"$var\"` instead of `$var`\n"
            "- Do NOT invent API keys \u2014 use free/public APIs where possible"
        )
    else:
        return (
            f"CODE QUALITY \u2014 {lang_name}:\n"
            "- Follow idiomatic {lang_name} conventions\n"
            "- Handle errors gracefully with try/catch or equivalent\n"
            "- Set explicit timeouts on all network calls\n"
            "- Do NOT invent API keys\n"
            "- Include a proper entry-point / main function"
        ).format(lang_name=lang_name)


# Heuristics used by the reviewing_node to surface severity and a
# coarse quality score from a free-text review. Both run in
# microseconds and never block on the LLM — the LLM is asked for a
# score in the prompt (so we prefer it when present) but the
# classifier and the score fallback are deterministic and
# non-LLM-dependent. The keyword lists are intentionally short and
# high-precision: false positives would just clutter format_fix_prompt
# and waste retry context.
_HIGH_SEVERITY_KEYWORDS = (
    "error", "undefined", "nameerror", "typeerror", "syntax",
    "import", "missing", "crash", "exception", "injection",
    "security", "vulnerability", "xss", "csrf", "rce", "ssrf",
    "race", "deadlock", "leak", "secret", "credential",
)
_MEDIUM_SEVERITY_KEYWORDS = (
    "warning", "deprecated", "unused", "no entry-point",
    "no type", "no timeout", "no error", "no try", "no except",
    "no if __name__", "stdlib only", "should", "consider",
)


def _classify_issue_severity(text: str) -> str:
    """Map a free-text review issue to "high" / "medium" / "low"."""
    if not isinstance(text, str) or not text:
        return "low"
    t = text.lower()
    for kw in _HIGH_SEVERITY_KEYWORDS:
        if kw in t:
            return "high"
    for kw in _MEDIUM_SEVERITY_KEYWORDS:
        if kw in t:
            return "medium"
    return "low"


def _heuristic_review_score(issues: list[str], suggestions: list[str]) -> float:
    """Coarse 0.0-1.0 quality score from issue / suggestion counts."""
    if not isinstance(issues, list):
        issues = []
    if not isinstance(suggestions, list):
        suggestions = []
    score = 1.0 - 0.10 * len(issues) - 0.05 * len(suggestions)
    return max(0.0, min(1.0, score))


# ========================================
# Per-node model routing
# ========================================


def _force_model_for(tier: str) -> str:
    """Resolve the preset tier to a model name, honoring the routing toggle.

    Returns the preset's model for the given tier when per-node routing
    is enabled (the default) AND that model is actually discovered on
    a running backend.  Returns ``""`` (empty) when:

      - the user has disabled routing (legacy "all nodes use the chat
        model" path);
      - the preset model is not in the model_discovery cache (e.g.
        model_fast points to a LM Studio model but LM Studio is off).

    In the second case the LLMWrapper takes the legacy user_model path
    on the user's selected backend, which is safe and predictable.
    """
    if not settings.get_node_routing_enabled():
        return ""
    candidate = settings.get_model_for_task(tier)
    if not candidate:
        return ""

    try:
        from backend.infrastructure.model_discovery import (
            get_model_discovery,
        )
    except Exception:
        return candidate

    try:
        discovered_backend = (
            get_model_discovery().get_backend_for_model(candidate)
        )
    except Exception:
        return candidate

    if discovered_backend is None:
        logger.warning(
            "[routing] Preset tier '%s' points to model '%s', which is "
            "not discovered on any running backend. Falling back to "
            "the user's chat model.",
            tier,
            candidate,
        )
        return ""
    return candidate


# ========================================
# LLM helpers (eliminate boilerplate in node functions)
# ========================================


def _build_llm(state: AgentState, tier: str):
    """Create an ``LLMWrapper`` configured for the given preset tier.

    Handles model resolution, routing logging, and provider lookup —
    all the boilerplate that was repeated in every node function.
    """
    user_model, user_provider = _get_model_info(state)
    force_model = _force_model_for(tier)
    routing_state = "on" if force_model else "off (user model)"
    logger.info(
        "[llm] user_model=%s → force_model=%s (tier=%s, routing=%s)",
        user_model,
        force_model or user_model,
        tier,
        routing_state,
    )
    from ..llm_wrapper import LLMWrapper  # late import — breaks circular dep

    return LLMWrapper(
        _get_llm_router(), user_model, user_provider, force_model=force_model,
    )


async def _llm_generate(llm, prompt: str, node_name: str, **kwargs) -> str:
    """Call ``llm.generate()`` and track the token count in ``_node_token_counts``.

    Returns the full response string.
    """
    response = await llm.generate(prompt, **kwargs)
    _node_token_counts[node_name] = len(response)
    return response


async def _llm_run_node(llm, prompt: str, node_name: str, **kwargs) -> str:
    """Call ``llm.run_node()`` and track the token count in ``_node_token_counts``.

    Returns the full response string.
    """
    response = await llm.run_node(prompt, **kwargs)
    _node_token_counts[node_name] = len(response)
    return response
