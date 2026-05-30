# backend/infrastructure/tools/builtins.py
# Role: Built-in tool handlers (calculator, memory search, get_time)

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


async def tool_calculator(arguments: dict) -> Any:
    """Calculator tool - uses safe arithmetic parsing instead of eval()"""
    expression = arguments.get("expression", "")

    try:
        # Safe arithmetic evaluation using ast
        result = _safe_eval(expression)
        return {"expression": expression, "result": result}
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Calculation error: {e!s}"}


def _safe_eval(expr: str) -> float:
    """
    Safe arithmetic evaluation without eval().
    Supports: +, -, *, /, parentheses, and basic math functions.
    """
    expr = expr.strip()
    if not expr:
        raise ValueError("Empty expression")

    # Only allow safe characters
    allowed = set("0123456789+-*/.() ")
    if not all(c in allowed for c in expr):
        raise ValueError("Invalid characters in expression")

    # Simple recursive descent parser for basic arithmetic
    def parse_add_sub(tokens: list) -> float:
        result = parse_mul_div(tokens)
        while tokens and tokens[0] in ("+", "-"):
            op = tokens.pop(0)
            rhs = parse_mul_div(tokens)
            result = result + rhs if op == "+" else result - rhs
        return result

    def parse_mul_div(tokens: list) -> float:
        result = parse_unary(tokens)
        while tokens and tokens[0] in ("*", "/"):
            op = tokens.pop(0)
            rhs = parse_unary(tokens)
            if op == "*":
                result = result * rhs
            else:
                if rhs == 0:
                    raise ValueError("Division by zero")
                result = result / rhs
        return result

    def parse_unary(tokens: list) -> float:
        if tokens and tokens[0] == "-":
            tokens.pop(0)
            return -parse_primary(tokens)
        return parse_primary(tokens)

    def parse_primary(tokens: list) -> float:
        if not tokens:
            raise ValueError("Unexpected end of expression")

        token = tokens.pop(0)

        if token == "(":
            result = parse_add_sub(tokens)
            if tokens and tokens[0] == ")":
                tokens.pop(0)
            return result

        # Try to parse as number
        try:
            return float(token)
        except ValueError:
            raise ValueError(f"Invalid token: {token}")

    # Tokenize
    tokens = []
    current = ""
    for char in expr:
        if char in " \t":
            if current:
                tokens.append(current)
                current = ""
        elif char in "+-*/()":
            if current:
                tokens.append(current)
                current = ""
            tokens.append(char)
        else:
            current += char
    if current:
        tokens.append(current)

    if not tokens:
        raise ValueError("Empty expression")

    return parse_add_sub(tokens)


async def tool_get_time(arguments: dict) -> Any:
    """Get current time tool"""
    return {"datetime": datetime.now().isoformat()}
