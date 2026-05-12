# core/prompts.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.domain.core.prompts instead

from backend.domain.core.prompts import (
    SYSTEM_PLANNER,
    SYSTEM_ARCHITECT,
    SYSTEM_CODER,
    SYSTEM_REVIEWER,
    SYSTEM_FIXER,
    PLANNER_PROMPT,
    ARCHITECT_PROMPT,
    CODER_PROMPT,
    REVIEWER_PROMPT,
    FIX_PROMPT,
    MEMORY_CONTEXT_PROMPT,
    PROMPTS,
    SYSTEMS,
    format_with_fallback,
    get_prompt,
    planner_prompt,
    architect_prompt,
    coder_prompt,
    reviewer_prompt,
    fix_prompt,
)

__all__ = [
    "SYSTEM_PLANNER",
    "SYSTEM_ARCHITECT",
    "SYSTEM_CODER",
    "SYSTEM_REVIEWER",
    "SYSTEM_FIXER",
    "PLANNER_PROMPT",
    "ARCHITECT_PROMPT",
    "CODER_PROMPT",
    "REVIEWER_PROMPT",
    "FIX_PROMPT",
    "MEMORY_CONTEXT_PROMPT",
    "PROMPTS",
    "SYSTEMS",
    "format_with_fallback",
    "get_prompt",
    "planner_prompt",
    "architect_prompt",
    "coder_prompt",
    "reviewer_prompt",
    "fix_prompt",
]