"""Extract valid Python code dict from LLM response."""

from __future__ import annotations

import json
import re
import textwrap


def extract_code_dict(response: str) -> dict[str, Any]:
    """Multi-strategy extraction of {"files": {"name.py": "code"}} from raw LLM output.

    Strategies:
    1. Direct JSON parse
    2. Find JSON object with "files" key (regex + validate syntax)
    3. Extract python code blocks
    4. Direct Python detection
    5. Fallback: return raw response as main.py
    """
    response_clean = response.strip()
    response_clean = re.sub(r"^```(?:json|python)?\s*", "", response_clean, flags=re.MULTILINE)
    response_clean = re.sub(r"\s*```$", "", response_clean)
    response_clean = response_clean.strip()

    code_dict = None

    # Strategy 1: Direct JSON parse
    if code_dict is None:
        try:
            candidate = json.loads(response_clean)
            if isinstance(candidate, dict) and "files" in candidate:
                for fname, fcontent in candidate["files"].items():
                    if not isinstance(fcontent, str):
                        raise ValueError(f"File {fname} content is not a string")
                code_dict = candidate
        except (json.JSONDecodeError, ValueError, TypeError, KeyError):
            pass

    # Strategy 2: Find JSON object with "files" key
    if code_dict is None:
        json_matches = re.findall(r"\{[\s\S]*?\}", response_clean)
        for match in json_matches:
            try:
                candidate = json.loads(match)
                if isinstance(candidate, dict) and "files" in candidate:
                    files = candidate["files"]
                    if isinstance(files, dict) and all(isinstance(v, str) for v in files.values()):
                        valid_files = {}
                        for fname, fcontent in files.items():
                            try:
                                compile(fcontent, fname, "exec")
                                valid_files[fname] = fcontent
                            except SyntaxError:
                                try:
                                    fixed = textwrap.dedent(fcontent).strip()
                                    compile(fixed, fname, "exec")
                                    valid_files[fname] = fixed + "\n"
                                except SyntaxError:
                                    pass
                        if valid_files:
                            code_dict = {"files": valid_files}
                            break
            except (json.JSONDecodeError, TypeError, KeyError):
                continue

    # Strategy 3: Extract python code blocks
    if code_dict is None:
        py_blocks = re.findall(r"```python\s*([\s\S]*?)```", response_clean)
        if py_blocks:
            files = {}
            for i, block in enumerate(py_blocks):
                block = block.strip()
                if not block:
                    continue
                lines = block.expandtabs(4).split("\n")
                non_empty = [l for l in lines if l.strip()]
                if not non_empty:
                    continue
                min_indent = min(len(l) - len(l.lstrip()) for l in non_empty)
                fixed_lines = []
                for line in lines:
                    if line.strip():
                        fixed_lines.append(line[min_indent:])
                    else:
                        fixed_lines.append("")
                normalized = "\n".join(fixed_lines).strip()
                try:
                    compile(normalized, f"file_{i+1}.py", "exec")
                except SyntaxError:
                    normalized = textwrap.dedent(normalized).strip()
                if normalized.strip():
                    files[f"file_{i+1}.py"] = normalized + "\n"
            if files:
                code_dict = {"files": files}

    # Strategy 4: Direct Python code detection
    if code_dict is None:
        py_start = re.search(
            r"^def\s+\w+|^\s*def\s+\w+|^class\s+\w+|^import\s+|^from\s+",
            response_clean, re.MULTILINE,
        )
        if py_start:
            code_dict = {"files": {"main.py": response_clean.strip()}}

    # Fallback
    if code_dict is None:
        code_dict = {"files": {"main.py": response_clean}}

    return code_dict