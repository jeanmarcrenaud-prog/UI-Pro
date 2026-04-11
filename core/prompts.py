# prompts.py - Centralized prompts for orchestrator agents

PLANNER_PROMPT = """
You are a senior planner.

Return JSON:
{{
  "goal": "...",
  "steps": ["...", "..."]
}}

Task:
{task}
"""

ARCHITECT_PROMPT = """
You are a software architect.

Plan:
{plan}

Return JSON:
{{
  "files": [
    {{"name": "main.py", "role": "..."}}
  ]
}}
"""

CODER_PROMPT = """
You are a senior Python engineer.

Architecture:
{architecture}

Return JSON:
{{
  "files": {{
    "main.py": "code here"
  }}
}}
"""

REVIEWER_PROMPT = """
Review this code and detect issues.

Code:
{code}

Return JSON:
{{
  "issues": ["..."],
  "fixes": ["..."]
}}
"""

FIX_PROMPT = """Fix this Python code.

Error:
{error}

Current code:
{code_content}

Return ONLY JSON:
{{
  "files": {{
    "main.py": "fixed code here"
  }}
}}

Retry count: {attempt}
Max retries: {max_retry}
"""

MEMORY_CONTEXT_PROMPT = """
Based on past similar tasks, here is relevant context:
{memory}

Use this to inform your response.
"""