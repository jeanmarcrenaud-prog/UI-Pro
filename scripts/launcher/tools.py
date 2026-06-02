"""External tool availability checks."""
import asyncio
import shutil
import subprocess


def check_npm_available() -> bool:
    """Check if npm is available."""
    # Use shutil.which to find npm in PATH
    npm_path = shutil.which("npm")
    if not npm_path:
        return False
    try:
        result = subprocess.run(
            [npm_path, "--version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_node_available() -> bool:
    """Check if node is available."""
    # Use shutil.which to find node in PATH
    node_path = shutil.which("node")
    if not node_path:
        return False
    try:
        result = subprocess.run(
            [node_path, "--version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_backends() -> dict:
    """Check all LLM backends status using model discovery."""
    try:
        from backend.infrastructure.model_discovery import ModelDiscovery

        async def _discover():
            discovery = ModelDiscovery(timeout=2.0)
            return await discovery.discover_all()

        all_models = asyncio.run(_discover())

        # Group by backend
        by_backend: dict[str, list[str]] = {}
        for model in all_models:
            if model.backend not in by_backend:
                by_backend[model.backend] = []
            by_backend[model.backend].append(model.name)

        return {
            "status": "running",
            "models": len(all_models),
            "by_backend": by_backend,
        }
    except Exception:
        return {"status": "not_running", "models": 0, "by_backend": {}}
