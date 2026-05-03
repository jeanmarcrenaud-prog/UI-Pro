# core/prompts.py - Centralized Prompts for Orchestrator Agents
"""
Centralized prompt templates.
All prompts use consistent JSON output format for reliable parsing.
"""

import logging
from typing import Any

# ================== UTILITY FUNCTIONS ==================

def format_with_fallback(template: str, **kwargs: Any) -> str:
    """
    Format template with missing key handling.
    
    Replaces missing keys with empty string to avoid KeyError.
    """
    # Build a safe mapping
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
    Get prompt by name with safe formatting.
    """
    prompt = PROMPTS.get(name)
    if not prompt:
        raise ValueError(f"Unknown prompt: {name}")
    return format_with_fallback(prompt, **kwargs)


# ================== CORE AGENT PROMPTS ==================

PLANNER_PROMPT = """You are an expert project planner.

Analyze the task and break it down into clear, actionable steps.

Return valid JSON only:
{{
  "goal": "Clear one-sentence goal",
  "steps": ["Step 1 description", "Step 2 description", ...],
  "complexity": "low|medium|high",
  "estimated_effort": "small|medium|large"
}}

Task:
{task}"""

ARCHITECT_PROMPT = """You are a senior software architect.

Given this plan, design a clean, maintainable structure.

Plan:
{plan}

Return valid JSON only:
{{
  "files": [
    {{"name": "filename.py", "role": "brief description", "key_components": ["list", "of", "parts"]}}
  ],
  "design_decisions": ["key decision 1", "key decision 2"]
}}"""

CODER_PROMPT = """You are a senior Python engineer.

Architecture:
{architecture}

Write clean, well-documented, production-ready code.

Return valid JSON only:
{{
  "files": {{
    "filename.py": "full code here"
  }}
}}"""

REVIEWER_PROMPT = """You are a strict code reviewer.

Code to review:
{code}

Return valid JSON only:
{{
  "issues": ["list of issues found"],
  "severity": "low|medium|high",
  "suggestions": ["improvement 1", "improvement 2"],
  "overall_score": 8.5
}}"""

FIX_PROMPT = """Fix the following Python code.

Error:
{error}

Current code:
{current_code}

This is attempt {attempt} of {max_retry}.

Return ONLY valid JSON:
{{
  "files": {{
    "{main_file}": "fixed complete code here"
  }},
  "explanation": "brief explanation of what was fixed"
}}"""

MEMORY_CONTEXT_PROMPT = """Relevant past context from similar tasks:

{memory}

Use this information to provide better, more consistent responses.
Do not mention this context unless necessary."""

SYSTEM_PROMPT = """You are an expert AI coding assistant.

Current system context:
{context}

Provide clear, actionable responses."""


# ================== PROMPT REGISTRY ==================

PROMPTS = {
    "PLANNER_PROMPT": PLANNER_PROMPT,
    "ARCHITECT_PROMPT": ARCHITECT_PROMPT,
    "CODER_PROMPT": CODER_PROMPT,
    "REVIEWER_PROMPT": REVIEWER_PROMPT,
    "FIX_PROMPT": FIX_PROMPT,
    "MEMORY_CONTEXT_PROMPT": MEMORY_CONTEXT_PROMPT,
    "SYSTEM_PROMPT": SYSTEM_PROMPT,
}


# Export for convenience
__all__ = [
    "PLANNER_PROMPT",
    "ARCHITECT_PROMPT", 
    "CODER_PROMPT",
    "REVIEWER_PROMPT",
    "FIX_PROMPT",
    "MEMORY_CONTEXT_PROMPT",
    "SYSTEM_PROMPT",
    "PROMPTS",
    "format_with_fallback",
    "get_prompt",
]