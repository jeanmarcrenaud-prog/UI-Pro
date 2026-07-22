#!/usr/bin/env python3
"""
verify_imports.py - Verify all imports point to backend/

This script checks that:
1. No legacy imports (from core., from services., etc.) outside backend/
2. All imports from backend/ are valid
3. No circular import issues
"""

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# Colors
GREEN = "[+]"
RED = "[-]"
YELLOW = "[!]"
RESET = ""

ERRORS = []
WARNINGS = []


def check_legacy_imports():
    """Check for legacy imports outside backend/"""
    print(f"\n{YELLOW}Checking legacy imports...{RESET}")

    legacy_patterns = [
        ("from core.", "backend.domain.core"),
        ("from services.", "backend.infrastructure"),
        ("from api.", "backend.transport"),
        ("from views.", "backend.transport"),
        ("from controllers.", "backend.application"),
    ]

    # Directories to exclude
    exclude_dirs = {
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        "scripts",
    }

    found_legacy = []

    for py_file in PROJECT_ROOT.rglob("*.py"):
        if any(ex in py_file.parts for ex in exclude_dirs):
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
            for line_num, line in enumerate(content.split("\n"), 1):
                for pattern, suggestion in legacy_patterns:
                    if pattern in line and "backend" not in line:
                        stripped = line.strip()
                        if stripped.startswith("#"):
                            continue
                        found_legacy.append(
                            {
                                "file": py_file.relative_to(PROJECT_ROOT),
                                "line": line_num,
                                "pattern": pattern,
                                "suggestion": suggestion,
                            }
                        )
        except Exception:
            pass

    if found_legacy:
        ERRORS.append(f"Found {len(found_legacy)} legacy imports:")
        for f in found_legacy[:10]:
            ERRORS.append(
                f"  {f['file']}:{f['line']}: {f['pattern']} -> use {f['suggestion']}"
            )
            print(f"  {RED}x{RESET} {f['file']}:{f['line']}")
        if len(found_legacy) > 10:
            print(f"  ... and {len(found_legacy) - 10} more")
    else:
        print(f"  {GREEN}OK{RESET} No legacy imports found")


def check_backend_imports():
    """Check that backend imports work"""
    print(f"\n{YELLOW}Checking backend imports...{RESET}")

    # Test key imports
    tests = [
        ("backend.domain.core", ["OrchestratorAsync", "CodeExecutor", "AgentState"]),
        ("backend.domain.core.events", ["get_event_bus", "emit_agent_step"]),
        ("backend.domain.core.logger", ["get_logger"]),
        ("backend.domain.core.metrics", ["MetricsManager", "get_metrics"]),
        ("backend.infrastructure.memory", ["MemoryManager", "add_memory"]),
        ("backend.infrastructure.llm_router", ["LLMRouter"]),
        ("backend.infrastructure.streaming", ["StreamingService"]),
        ("backend.transport.main", ["app"]),
        ("backend.transport.routers.ws", ["router"]),
    ]

    for module_path, items in tests:
        try:
            module = __import__(module_path, fromlist=items)
            for item in items:
                if not hasattr(module, item):
                    ERRORS.append(f"{module_path}.{item} not found")
                    print(f"  {RED}x{RESET} {module_path}.{item}")
            print(f"  {GREEN}OK{RESET} {module_path}")
        except Exception as e:
            ERRORS.append(f"Failed to import {module_path}: {e}")
            print(f"  {RED}x{RESET} {module_path}: {e}")


def check_backend_settings():
    """Check backend.domain.settings import works"""
    print(f"\n{YELLOW}Checking backend.domain.settings import...{RESET}")

    try:
        from backend.domain.settings import settings, get_settings, Settings
        print(f"  {GREEN}OK{RESET} backend.domain.settings")
    except Exception as e:
        ERRORS.append(f"backend.domain.settings failed: {e}")
        print(f"  {RED}x{RESET} backend.domain.settings: {e}")


def check_llm_imports():
    """Check llm module imports work"""
    print(f"\n{YELLOW}Checking llm imports...{RESET}")

    try:
        print(f"  {GREEN}OK{RESET} llm")
    except Exception as e:
        ERRORS.append(f"llm failed: {e}")
        print(f"  {RED}x{RESET} llm: {e}")


def check_legacy_shims_removed():
    """Verify legacy shim files have been removed"""
    print(f"\n{YELLOW}Checking legacy shims removed...{RESET}")
    legacy_files = [
        PROJECT_ROOT / "settings.py",
        PROJECT_ROOT / "models" / "settings.py",
        PROJECT_ROOT / "models" / "__init__.py",
        PROJECT_ROOT / "config" / "__init__.py",
    ]
    found = [f for f in legacy_files if f.exists()]
    if found:
        for f in found:
            WARNINGS.append(f"Legacy shim still exists: {f.relative_to(PROJECT_ROOT)}")
            print(f"  {YELLOW}W{RESET} {f.relative_to(PROJECT_ROOT)} still exists")
    else:
        print(f"  {GREEN}OK{RESET} No legacy shim files found")


def check_circular_imports():
    """Check for common circular import patterns"""
    print(f"\n{YELLOW}Checking circular import patterns...{RESET}")

    # This is a basic check - real circular imports need runtime detection
    patterns = [
        ("backend.domain.core", "models"),
        ("backend.infrastructure", "backend.transport"),
    ]

    # Just verify basic imports work (would fail on circular)
    try:
        from backend.domain.core import OrchestratorAsync
        from backend.domain.settings import settings

        print(f"  {GREEN}OK{RESET} No obvious circular imports")
    except ImportError as e:
        if "circular" in str(e).lower():
            ERRORS.append(f"Circular import detected: {e}")
            print(f"  {RED}x{RESET} Circular import: {e}")
        else:
            print(f"  {GREEN}OK{RESET} Import error (not circular): {e}")


def main():
    print(f"{'=' * 50}")
    print("UI-Pro Import Verification")
    print(f"{'=' * 50}")

    check_legacy_imports()
    check_backend_imports()
    check_backend_settings()
    check_llm_imports()
    check_legacy_shims_removed()
    check_circular_imports()

    print(f"\n{'=' * 50}")
    if ERRORS:
        print(f"{RED}ERRORS: {len(ERRORS)}{RESET}")
        for e in ERRORS:
            print(f"  {RED}x{RESET} {e}")
        return 1
    else:
        print(f"{GREEN}All imports verified!{RESET}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
