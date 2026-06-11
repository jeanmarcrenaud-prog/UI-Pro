# core/prompts.py - Centralized Prompts for Orchestrator Agents
"""
Prompt templates centralisés pour l'orchestrator.
- Format JSON strict
- Helpers de formatting sécurisés
- Registry pour accès facile
"""

import logging
from typing import Any

# ================== SYSTEM INSTRUCTIONS ==================

SYSTEM_PLANNER = "You are an expert technical planner. Break down tasks into clear, actionable steps."
SYSTEM_ARCHITECT = "You are a senior software architect focused on clean, maintainable, and scalable design."
SYSTEM_CODER = "You are a senior software engineer who writes clean, idiomatic, and production-ready code."
SYSTEM_REVIEWER = "You are a strict, detail-oriented code reviewer focused on correctness, security, and best practices."
SYSTEM_FIXER = "You are an expert debugging specialist. Provide minimal, targeted, and correct fixes."

# ================== MAIN PROMPTS ==================

PLANNER_PROMPT = """{system}

Task:
{task}

Return **only** valid JSON using this exact structure:
{{
  "goal": "One clear sentence describing the objective",
  "steps": ["Step 1...", "Step 2..."],
  "complexity": "low|medium|high",
  "estimated_effort": "small|medium|large",
  "potential_risks": ["risk 1", "risk 2"]
}}
"""

ARCHITECT_PROMPT = """{system}

Plan:
{plan}

Design a clean architecture.

Return **only** valid JSON:
{{
  "files": [
    {{"name": "filename.py", "role": "brief role", "key_components": ["main parts"]}}
  ],
  "design_decisions": ["decision 1", "decision 2"],
  "dependencies": ["list of important packages"]
}}
"""

CODER_PROMPT = """{system}

Architecture:
{architecture}

Write high-quality, clean, well-documented {language} code.

Return **only** valid JSON:
{{
    "files": {{
        "filename.{ext}": "complete code here"
    }}
}}
"""

REVIEWER_PROMPT = """{system}

Code to review:
{code}

Return **only** valid JSON:
{{
  "issues": [
    {{"severity": "high|medium|low", "description": "...", "location": "..."}}
  ],
  "overall_score": 8.5,
  "recommendations": ["recommendation 1", "recommendation 2"]
}}
"""

FIX_PROMPT = """{system}

Error:
{error}

Current code:
{current_code}

This is attempt {attempt} of {max_retry}.

Fix the code with minimal, targeted changes.

Return **only** valid JSON:
{{
  "files": {{
    "{main_file}": "fixed complete code"
  }},
  "explanation": "Brief explanation of changes made"
}}
"""

MEMORY_CONTEXT_PROMPT = """Relevant context from past similar tasks:

{memory}

Use this information to improve consistency and quality of your response.
Do not mention this context unless explicitly asked.
"""

# ================== PROMPT REGISTRY ==================

SYSTEMS = {
    "planner": SYSTEM_PLANNER,
    "architect": SYSTEM_ARCHITECT,
    "coder": SYSTEM_CODER,
    "reviewer": SYSTEM_REVIEWER,
    "fix": SYSTEM_FIXER,
}

PROMPTS = {
    "PLANNER_PROMPT": (PLANNER_PROMPT, "planner"),
    "ARCHITECT_PROMPT": (ARCHITECT_PROMPT, "architect"),
    "CODER_PROMPT": (CODER_PROMPT, "coder"),
    "REVIEWER_PROMPT": (REVIEWER_PROMPT, "reviewer"),
    "FIX_PROMPT": (FIX_PROMPT, "fix"),
    "MEMORY_CONTEXT_PROMPT": (MEMORY_CONTEXT_PROMPT, None),
}

# ================== UTILITY FUNCTIONS ==================


def format_with_fallback(template: str, **kwargs: Any) -> str:
    """
    Format template with missing key handling.

    Auto-injects system prompt if not provided.
    """
    # Auto-inject system prompt if not provided
    if "system" not in kwargs:
        # Try to find matching system based on template
        prompt_info = PROMPTS.get("PLANNER_PROMPT")  # default
        for name, (tmpl, sys_key) in PROMPTS.items():
            if tmpl == template:
                if sys_key:
                    kwargs["system"] = SYSTEMS.get(sys_key, "")
                break

    safe_kwargs = {k: v for k, v in kwargs.items()}

    try:
        return template.format(**safe_kwargs)
    except KeyError as e:
        logging.warning(f"Missing placeholder in prompt: {e}")
        # Replace missing keys with empty
        result = template
        for key in kwargs:
            result = result.replace("{" + key + "}", "")
        return result


def get_prompt(name: str, **kwargs: Any) -> str:
    """
    Get and format prompt by name.

    Usage:
        get_prompt("planner", task="Build API")
        get_prompt("architect", plan="...")
    """
    # Normalize name
    upper_name = name.upper() if name.islower() else name
    if not upper_name.endswith("_PROMPT"):
        upper_name = upper_name + "_PROMPT"

    prompt_tuple = PROMPTS.get(upper_name)
    if not prompt_tuple:
        logging.error(f"Unknown prompt: {name}")
        raise ValueError(f"Unknown prompt template: {name}")

    template, sys_key = prompt_tuple

    # Auto-inject system
    if "system" not in kwargs and sys_key:
        kwargs["system"] = SYSTEMS.get(sys_key, "")

    return format_with_fallback(template, **kwargs)


# Aliases for convenience
def planner_prompt(task: str, **kwargs: Any) -> str:
    """Convenience wrapper for planner prompt"""
    kwargs["task"] = task
    return get_prompt("planner", **kwargs)


def architect_prompt(plan: str, **kwargs: Any) -> str:
    """Convenience wrapper for architect prompt"""
    kwargs["plan"] = plan
    return get_prompt("architect", **kwargs)


def coder_prompt(architecture: str, language: str = "python", **kwargs: Any) -> str:
    """Convenience wrapper for coder prompt"""
    kwargs["architecture"] = architecture
    kwargs.setdefault("language", language)
    ext = kwargs.pop("ext", _lang_to_ext(language))
    kwargs.setdefault("ext", ext)
    return get_prompt("coder", **kwargs)


def reviewer_prompt(code: str, **kwargs: Any) -> str:
    """Convenience wrapper for reviewer prompt"""
    kwargs["code"] = code
    return get_prompt("reviewer", **kwargs)


def fix_prompt(
    error: str, current_code: str, attempt: int = 1, max_retry: int = 3, **kwargs: Any
) -> str:
    """Convenience wrapper for fix prompt"""
    kwargs["error"] = error
    kwargs["current_code"] = current_code
    kwargs["attempt"] = attempt
    kwargs["max_retry"] = max_retry
    return get_prompt("fix", **kwargs)


# ================== LANGUAGE HELPERS ==================

_LANG_EXT_MAP: dict[str, str] = {
    "python": "py",
    "powershell": "ps1",
    "bash": "sh",
    "shell": "sh",
    "batch": "bat",
    "cmd": "bat",
    "javascript": "js",
    "typescript": "ts",
}


def _lang_to_ext(language: str) -> str:
    """Map a language name to its file extension (without dot)."""
    return _LANG_EXT_MAP.get(language.lower(), "py")


# ================== EXPORTS ==================

__all__ = [
    # System instructions
    "SYSTEM_PLANNER",
    "SYSTEM_ARCHITECT",
    "SYSTEM_CODER",
    "SYSTEM_REVIEWER",
    "SYSTEM_FIXER",
    # Main prompts
    "PLANNER_PROMPT",
    "ARCHITECT_PROMPT",
    "CODER_PROMPT",
    "REVIEWER_PROMPT",
    "FIX_PROMPT",
    "MEMORY_CONTEXT_PROMPT",
    # Utilities
    "PROMPTS",
    "SYSTEMS",
    "format_with_fallback",
    "get_prompt",
    # Convenient wrappers
    "planner_prompt",
    "architect_prompt",
    "coder_prompt",
    "reviewer_prompt",
    "fix_prompt",
]
