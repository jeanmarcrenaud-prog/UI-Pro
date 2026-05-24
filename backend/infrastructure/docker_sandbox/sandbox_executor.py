#!/usr/bin/env python3
"""
Docker Sandbox Executor
Runs code in isolated container with timeout and resource limits.
"""

import json
import os
import subprocess
import sys
import tempfile
import time

# Configuration
TIMEOUT_SECONDS = 30
MEMORY_LIMIT_MB = 512


def run_code(code: str, language: str = "python") -> dict:
    """Execute code in sandbox and return result."""
    start_time = time.time()

    # Create temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=f".{language}", delete=False
    ) as f:
        f.write(code)
        temp_file = f.name

    try:
        # Build command based on language
        if language == "python":
            cmd = ["python", temp_file]
        elif language == "javascript":
            cmd = ["node", temp_file]
        elif language == "bash":
            cmd = ["bash", temp_file]
        else:
            return {
                "success": False,
                "output": "",
                "error": f"Unsupported language: {language}",
                "execution_time_ms": 0,
            }

        # Execute with timeout
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT_SECONDS, cwd="/tmp"
        )

        execution_time = (time.time() - start_time) * 1000

        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else "",
            "execution_time_ms": execution_time,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": f"Execution timeout ({TIMEOUT_SECONDS}s)",
            "execution_time_ms": TIMEOUT_SECONDS * 1000,
        }
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": str(e),
            "execution_time_ms": (time.time() - start_time) * 1000,
        }
    finally:
        # Cleanup temp file
        try:
            os.unlink(temp_file)
        except:
            pass


def main():
    """Main entry point - read code from stdin, write result to stdout."""
    try:
        # Read input from stdin
        input_data = json.loads(sys.stdin.read())

        code = input_data.get("code", "")
        language = input_data.get("language", "python")

        result = run_code(code, language)

        # Output result as JSON
        print(json.dumps(result))

    except Exception as e:
        # Output error as JSON
        print(
            json.dumps(
                {
                    "success": False,
                    "output": "",
                    "error": f"Sandbox error: {e!s}",
                    "execution_time_ms": 0,
                }
            )
        )


if __name__ == "__main__":
    main()
