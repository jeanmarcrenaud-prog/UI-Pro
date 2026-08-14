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


def _step_start(state: AgentState, name: str) -> dict[str, Any]:
    """Return state updates marking a pipeline step as running.

    Pure helper: does NOT mutate ``state``. Nodes must merge the
    returned ``current_step`` / ``steps_history`` into their own updates
    dict and return them so LangGraph's reducers apply them.
    """
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
    return {"current_step": name, "steps_history": history}


def _step_done(
    name: str,
    history: list[StepInfo],
    status: Literal["done", "error"] = "done",
) -> dict[str, Any]:
    """Mark the most recent running step for *name* as finished.

    Pure helper: does NOT mutate the incoming state. ``history`` is the
    list returned by ``_step_start`` (already containing the running
    step); the matching entry is marked with the final token count.
    Nodes merge the returned updates into their own.

    Usage::

        updates = _step_start(state, "analyzing")
        ...
        return _step_done("analyzing", updates["steps_history"]) | {
            "task_type": task_json,
        }
    """
    for step in reversed(history):
        if step.get("name") == name and step.get("status") == "running":
            step["status"] = status
            step["tokens"] = _node_token_counts.get(name, 0)
            break
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


def _error_guard(node_name: str):
    """Decorator that converts an unhandled node exception into a recorded
    error + error-status step, so the pipeline continues instead of crashing.

    Pairs with ``@_timed_node`` — apply it BELOW (inside) it::

        @_timed_node("coding")
        @_error_guard("coding")
        async def coding_node(state): ...

    On exception the wrapper records the error via ``_record_error``, marks
    the step as ``error`` in ``steps_history``, sets ``error``, and returns
    the partial updates so the graph can continue (e.g. the no-code
    short-circuit or the fix loop). ``BaseException`` (e.g.
    ``asyncio.CancelledError``) is NOT caught — cancellation must propagate.
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(state, *args, **kwargs):
            try:
                return await func(state, *args, **kwargs)
            except Exception as exc:
                logger.exception("[%s_node] Unhandled exception", node_name)
                msg = (
                    f"{type(exc).__name__}: {exc}"
                    if str(exc)
                    else f"{type(exc).__name__} (no message)"
                )
                updates = _record_error(state, node_name, msg)
                # The node may have crashed before _step_start, so its
                # running step (if any) lives in the lost local updates.
                # Append a synthetic running step and mark it error.
                history = list(state.get("steps_history", []))
                history.append({
                    "name": node_name,
                    "status": "running",
                    "model_used": (state.get("metadata") or {}).get("model") or None,
                    "tokens": 0,
                    "duration_ms": 0,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                })
                updates.update(_step_done(node_name, history, status="error"))
                updates["error"] = msg
                return updates

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


def _clean_plan(plan: PlanData | None) -> dict[str, Any]:
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


def _reset_llm_router() -> None:
    """Reset the cached LLMRouter singleton.

    Called by ``settings._invalidate_provider_singletons`` when runtime
    changes (model, URL, provider) must take effect on the next LLM call.
    Must mutate the module-level cell, not a re-exported copy."""
    global _llm_router_instance
    _llm_router_instance = None


def _record_error(state: AgentState, node_name: str, error: str) -> dict[str, Any]:
    """Return updates appending an error entry to ``error_history``.

    Pure helper: does NOT mutate ``state``. Emits a step event so the
    frontend Debug UI can display the error in real time, then returns
    ``{"error_history": [...]}`` for the caller to merge into its
    updates dict.
    """
    entry = {
        "node": node_name,
        "error": error,
        "attempt": state.get("attempt", 0),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    history = list(state.get("error_history", []))
    history.append(entry)
    # Forward to frontend via event bus
    _emit_step(node_name, f"❌ {error}", data={"error": entry})
    return {"error_history": history}


def _emit_step(phase: str, message: str, data: dict | None = None):
    try:
        from backend.domain.core.events import emit_agent_step

        emit_agent_step(phase, message, data=data)
    except Exception:
        pass


# ========================================
# Robust JSON extraction (thinking-model safe)
# ========================================


def _strip_thinking(text: str) -> str:
    """Remove reasoning blocks emitted by thinking-mode models.

    Handles ``<thinking>...</thinking>`` (DeepSeek-R1, Qwen3),
    ``<|thinking|>...</thinking|>`` (Anthropic-style) and Qwen3's
    self-closing ``<|thinking|>...<|thinking|>`` so reasoning text
    with braces doesn't pollute JSON extraction.
    """
    cleaned = re.sub(
        r"<\|?thinking\|?>[\s\S]*?<\/?\|?thinking\|?>",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Extract the first valid JSON object from raw LLM output.

    Robust against thinking-model preamble/reasoning:
    1. Strips ``<thinking>...</thinking>`` blocks.
    2. Scans for balanced ``{...}`` objects (string-aware, like ``json.loads``).
    3. Tries ``json.loads`` on each candidate, returning the first valid dict.
    4. Repairs common LLM mistakes (single quotes → double, trailing commas).

    Returns ``None`` if no valid JSON object is found.
    """
    cleaned = _strip_thinking(text)

    # 2. Balanced-brace scan (string-aware) — finds every top-level {...}
    candidates: list[str] = []
    depth = 0
    start = -1
    in_string = False
    escape = False
    for i, ch in enumerate(cleaned):
        if escape:
            escape = False
            continue
        if ch == chr(92):  # backslash
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    candidates.append(cleaned[start : i + 1])
                    start = -1

    # 3. Try each candidate as-is
    for cand in candidates:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue

    # 4. Repair pass on the first candidate (single quotes, trailing commas)
    if candidates:
        repaired = candidates[0]
        repaired = re.sub(r"(?<!\\)'", '"', repaired)
        repaired = re.sub(r",\s*]", "]", repaired)
        repaired = re.sub(r",\s*}", "}", repaired)
        try:
            obj = json.loads(repaired)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    return None


# ========================================
# Language detection helpers
# ========================================

_LANG_KEYWORDS: dict[str, set[str]] = {
    "python": {"python"},
    "powershell": {"powershell", "pwsh", "ps1", "posh", "microsoft teams"},
    "bash": {"bash", "shell script", "sh ", ".sh"},
    "batch": {".bat", ".cmd", "batch"},
    "javascript": {"javascript", "js ", ".js", "nodejs", "node.js"},
    "typescript": {"typescript"},   # deliberately narrower: ".ts" alone is too
    "html": {"html", "htm", ".html", "page web", "page html"},
    "css": {"css", ".css", "feuille de style", "stylesheet"},
}

_LANG_CONFIG: dict[str, dict[str, str]] = {
    "python": {"ext": "py", "block": "python", "name": "Python"},
    "powershell": {"ext": "ps1", "block": "powershell", "name": "PowerShell"},
    "bash": {"ext": "sh", "block": "bash", "name": "Bash"},
    "batch": {"ext": "bat", "block": "batch", "name": "Batch"},
    "javascript": {"ext": "js", "block": "javascript", "name": "JavaScript"},
    "typescript": {"ext": "ts", "block": "typescript", "name": "TypeScript"},
    "html": {"ext": "html", "block": "html", "name": "HTML"},
    "css": {"ext": "css", "block": "css", "name": "CSS"},
}

_DEFAULT_LANG = "python"


def _detect_language(user_message: str) -> str:
    """Detect the programming language requested by the user.

    Uses keyword matching on the lowercased user message. Returns
    the language key (e.g. 'python', 'powershell', 'bash') or
    the default 'python' when no explicit language is mentioned.

    **Preference logic**: when both ``javascript`` and ``typescript``
    keywords match (e.g. a message that contains both "node.js" and
    "typescript"), JavaScript wins — small models frequently default
    to TypeScript when JavaScript was intended, and TypeScript's
    narrower keyword set (just ``"typescript"``) reduces false hits.
    """
    msg_lower = user_message.lower()
    matched: list[str] = []
    for lang, keywords in _LANG_KEYWORDS.items():
        if any(kw in msg_lower for kw in keywords):
            matched.append(lang)

    if not matched:
        return _DEFAULT_LANG

    # When both JS and TS are plausible, prefer JavaScript (the model's
    # default output when it sees "ES6+" is often TypeScript otherwise).
    if "typescript" in matched and "javascript" in matched:
        matched.remove("typescript")

    return matched[0]


def _get_lang_config(language: str) -> dict[str, str]:
    """Get language config (ext, block, name) for a given language key."""
    return _LANG_CONFIG.get(language, _LANG_CONFIG[_DEFAULT_LANG])


def _build_code_quality_section(language: str) -> str:
    """Build language-specific code quality rules for the coding prompt.

    Returns a formatted block that appends after the syntax example in
    the coding prompt.  Every language follows the same heading format
    ``CODE QUALITY — {Language}:`` for consistency.
    """
    cfg = _get_lang_config(language)
    lang_name = cfg["name"]

    base = (
        f"CODE QUALITY \u2014 {lang_name}:\n"
        "- Follow idiomatic {lang} conventions\n"
        "- Set explicit timeouts on ALL network/HTTP calls (or timeout equivalent)\n"
        "- Handle errors with typed exceptions / structured error output \u2014 "
        "never silent failures\n"
        "- Do NOT invent API keys \u2014 free/public APIs (Open-Meteo, wttr.in, "
        "ipapi.co, \u2026) require none\n"
    )

    if language == "python":
        return base.format(lang="Python") + (
            "- Entry-point file MUST use `if __name__ == '__main__':` guard\n"
            "- Wrap HTTP calls in three distinct `except` branches: "
            "`URLError` (network), `HTTPError` (4xx/5xx), "
            "`JSONDecodeError` (parse)\n"
            "- Raise `ValueError` for bad inputs, `RuntimeError` for runtime "
            "failures \u2014 do NOT `print(); sys.exit(1)` (hides errors "
            "from the auto-fix loop)\n"
            "- Match output format EXACTLY (JSON, CSV, table, \u2026) \u2014 "
            "the user's format constraint is stricter than bare `print()`"
        )
    elif language == "powershell":
        return base.format(lang="PowerShell") + (
            "- Begin scripts with `#Requires -Version 5.1` for dependency "
            "declaration\n"
            "- Use `[CmdletBinding()]` + `param()` for ALL advanced functions "
            "\u2014 never `$args` positional magic\n"
            "- Set `$ErrorActionPreference = 'Stop'` top-of-script; "
            "`-ErrorAction SilentlyContinue` only on intentionally ignored "
            "calls\n"
            "- Use `$PSCustomObject @{ ... }` for structured output (pipeline-ready) "
            "over concatenated strings\n"
            "- Check `$LASTEXITCODE` right after native EXE calls\n"
            "- Structure pipeline functions via `begin {}` / `process {}` / `end {}`"
        )
    elif language in ("bash", "shell"):
        return base.format(lang="Bash") + (
            "- Start with `#!/usr/bin/env bash` + `set -euo pipefail`\n"
            "- Use `curl -fsSL` with `--connect-timeout` + `--max-time` for HTTP\n"
            "- Emit errors to stderr: `echo \"...\" >&2; return 1`\n"
            "- Quote ALL variable expansions: `\"$var\"` never `$var`\n"
            "- Parse JSON with `jq` when the output path expects structured data"
        )
    else:
        return base.format(lang=lang_name) + (
            "- Include a proper entry-point / main function\n"
            "- Use try/catch (or the language's error-handling idiom)"
        )


def _build_syntax_example(language: str) -> str:
    """Build a language-appropriate syntax example for the coding prompt.

    Each example demonstrates ~8-12 lines of correct, idiomatic code for
    the target language — balanced parens/braces/brackets, closed strings,
    proper indentation, and a realistic error-handling pattern.
    """
    if language in ("javascript", "typescript", "jsx", "tsx"):
        return (
            "async function fetchData(url, timeout = 10) {\n"
            "  const controller = new AbortController();\n"
            "  const id = setTimeout(() => controller.abort(), timeout * 1000);\n"
            "  try {\n"
            "    const resp = await fetch(url, { signal: controller.signal });\n"
            "    if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);\n"
            "    return await resp.json();\n"
            "  } finally {\n"
            "    clearTimeout(id);\n"
            "  }\n"
            "}\n"
        )
    elif language == "powershell":
        return (
            "function Get-Data {\n"
            "    [CmdletBinding()]\n"
            "    param(\n"
            "        [Parameter(Mandatory)]\n"
            "        [string]$Url,\n"
            "        [int]$TimeoutSec = 30\n"
            "    )\n"
            "    try {\n"
            "        $resp = Invoke-RestMethod -Uri $Url -TimeoutSec $TimeoutSec -ErrorAction Stop\n"
            "        return [PSCustomObject]@{ status = 'ok'; data = $resp }\n"
            "    } catch {\n"
            "        Write-Error $_.Exception.Message\n"
            "        throw\n"
            "    }\n"
            "}\n"
        )
    elif language in ("bash", "shell"):
        return (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "\n"
            "fetch_data() {\n"
            "  local url=\"$1\"\n"
            "  local timeout=\"${2:-10}\"\n"
            "  curl -fsSL --connect-timeout \"$timeout\" --max-time \"$((timeout * 2))\" \"$url\" || {\n"
            "    echo \"Error: fetch failed\" >&2\n"
            "    return 1\n"
            "  }\n"
            "}\n"
        )
    elif language == "html":
        return (
            "<!DOCTYPE html>\n"
            "<html lang=\"fr\">\n"
            "<head>\n"
            "  <meta charset=\"UTF-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
            "  <title>Page exemple</title>\n"
            "  <link rel=\"stylesheet\" href=\"style.css\">\n"
            "</head>\n"
            "<body>\n"
            "  <h1>Bienvenue</h1>\n"
            "  <p>Ceci est un paragraphe d\u2019exemple avec du texte.</p>\n"
            "  <script src=\"app.js\"></script>\n"
            "</body>\n"
            "</html>\n"
        )
    elif language == "css":
        return (
            "/* Reset de base */\n"
            "*, *::before, *::after {\n"
            "  box-sizing: border-box;\n"
            "  margin: 0;\n"
            "  padding: 0;\n"
            "}\n"
            "\n"
            ".container {\n"
            "  max-width: 1200px;\n"
            "  margin-inline: auto;\n"
            "  padding: 1rem;\n"
            "}\n"
            "\n"
            ".card {\n"
            "  border: 1px solid #ddd;\n"
            "  border-radius: 8px;\n"
            "  padding: 1.5rem;\n"
            "  box-shadow: 0 2px 4px rgba(0,0,0,0.1);\n"
            "}\n"
        )
    # Default Python example
    return (
        "import json\n"
        "import sys\n"
        "import urllib.request\n"
        "\n"
        "def fetch_data(url: str, timeout: int = 10) -> dict:\n"
        "    with urllib.request.urlopen(url, timeout=timeout) as resp:\n"
        "        return json.loads(resp.read().decode('utf-8'))\n"
        "\n"
        "def process(items: list[dict]) -> list[str]:\n"
        "    return [i.get('name', '?') for i in items if i.get('active')]\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    data = fetch_data('https://api.example.com/data')\n"
        "    names = process(data.get('items', []))\n"
        "    print('\\n'.join(names))\n"
    )


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
