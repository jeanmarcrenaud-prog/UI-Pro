"""Code repair utilities for common LLM output mistakes."""

from __future__ import annotations

import textwrap


def fix_syntax_errors(code: str) -> str:
    """Attempt basic syntax repair for common LLM mistakes.

    Tries to:
    1. Remove extra closing brackets (parens, brackets, braces)
    2. Append missing closing brackets at the end

    Returns the best-effort fixed code, or the original if no fix is needed.
    """
    stripped = code.strip()
    if not stripped:
        return code

    # Try compiling as-is first
    try:
        compile(stripped, "<string>", "exec")
        return code
    except SyntaxError:
        pass

    pairs = {"(": ")", "[": "]", "{": "}"}
    closing = set(pairs.values())

    # Strategy 1: Scan and remove extra closing brackets
    for _ in range(3):  # Try up to 3 iterations
        stack = []
        cleaned: list[str] = []
        for ch in stripped:
            if ch in pairs:
                stack.append(ch)
                cleaned.append(ch)
            elif ch in closing:
                if stack and pairs.get(stack[-1]) == ch:
                    stack.pop()
                    cleaned.append(ch)
                # else: extra closing bracket - remove it (don't append)
            else:
                cleaned.append(ch)
        candidate = "".join(cleaned)
        if candidate == stripped and stack:
            # No brackets were removed but there are unmatched opening brackets
            # Append missing closing brackets
            extra_closers = "".join(pairs[opener] for opener in reversed(stack))
            candidate = stripped + extra_closers

        try:
            compile(candidate, "<string>", "exec")
            return candidate
        except SyntaxError:
            stripped = candidate
            continue

    return code  # All repair attempts failed


def fix_indentation(code: str) -> str:
    """Normalize inconsistent indentation.

    Strategy: bump outlier lines to the minimum non-zero indent,
    then dedent everything to column 0.

    Example:
        import requests       <- outlier (indent 0, should be 4)
        import json           <- ok (indent 4)
        from datetime import... <- ok (indent 4)
        url = "..."           <- ok (indent 4)
        params = {            <- ok (indent 4)
            "key": "val"      <- deeper indent (8) - preserved after dedent
    """
    lines = code.split("\n")
    non_empty = [l for l in lines if l.strip()]
    if len(non_empty) < 2:
        return code

    indents = [len(l) - len(l.lstrip()) for l in non_empty]
    nonzero = [i for i in indents if i > 0]
    if not nonzero:
        return code

    base_indent = min(nonzero)
    min_indent = min(indents)

    candidates: list[str] = []

    # Strategy 1: bump lines below base_indent up, dedent all to 0
    if min_indent < base_indent:
        fixed: list[str] = []
        for line in lines:
            if line.strip():
                diff = len(line) - len(line.lstrip())
                if diff < base_indent:
                    fixed.append(" " * base_indent + line.lstrip())
                else:
                    fixed.append(line)
            else:
                fixed.append(line)
        uniform = "\n".join(fixed)
        dedented = textwrap.dedent(uniform)
        if dedented != uniform:
            candidates.append(dedented)
        candidates.append(uniform)

    # Strategy 2: simple textwrap.dedent
    dedented_full = textwrap.dedent(code)
    if dedented_full != code:
        candidates.append(dedented_full)

    # Try each candidate, return first that compiles
    for candidate in candidates:
        try:
            compile(candidate, "<string>", "exec")
            return candidate
        except SyntaxError:
            continue

    return code
