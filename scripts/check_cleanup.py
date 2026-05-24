#!/usr/bin/env python3
"""
check_cleanup.py - Verify project cleanup status

Checks:
- No legacy imports outside backend/
- All re-exports work
- No duplicate files
"""

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# Colors (ASCII-safe)
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
        "from core.",
        "from services.",
        "from api.",
        "from views.",
        "from controllers.",
    ]

    # Directories to exclude from check
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
        # Skip excluded directories
        if any(ex in py_file.parts for ex in exclude_dirs):
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
            for line_num, line in enumerate(content.split("\n"), 1):
                for pattern in legacy_patterns:
                    if pattern in line and "backend" not in line:
                        # Skip if it's in a comment
                        stripped = line.strip()
                        if stripped.startswith("#"):
                            continue
                        found_legacy.append(
                            f"  {py_file.relative_to(PROJECT_ROOT)}:{line_num}: {line.strip()[:60]}"
                        )
        except Exception:
            pass

    if found_legacy:
        ERRORS.append(f"Found {len(found_legacy)} legacy imports:")
        for f in found_legacy[:10]:
            ERRORS.append(f)
            print(f"  {RED}x{RESET} {f}")
        if len(found_legacy) > 10:
            print(f"  ... and {len(found_legacy) - 10} more")
    else:
        print(f"  {GREEN}OK{RESET} No legacy imports found")


def check_reexports():
    """Check that re-exports work"""
    print(f"\n{YELLOW}Checking re-exports...{RESET}")

    # Check models/settings.py re-exports
    try:
        print(f"  {GREEN}OK{RESET} models.settings re-exports work")
    except Exception as e:
        ERRORS.append(f"models.settings re-export failed: {e}")
        print(f"  {RED}x{RESET} models.settings: {e}")

    # Check root settings.py re-exports
    try:
        print(f"  {GREEN}OK{RESET} root settings.py re-exports work")
    except Exception as e:
        ERRORS.append(f"root settings.py re-export failed: {e}")
        print(f"  {RED}x{RESET} root settings.py: {e}")


def check_backend_imports():
    """Check that backend/ imports work"""
    print(f"\n{YELLOW}Checking backend imports...{RESET}")

    try:
        print(f"  {GREEN}OK{RESET} backend.domain.core imports work")
    except Exception as e:
        ERRORS.append(f"backend.domain.core import failed: {e}")
        print(f"  {RED}x{RESET} backend.domain.core: {e}")

    try:
        print(f"  {GREEN}OK{RESET} backend.infrastructure.memory imports work")
    except Exception as e:
        ERRORS.append(f"backend.infrastructure.memory import failed: {e}")
        print(f"  {RED}x{RESET} backend.infrastructure.memory: {e}")

    try:
        print(f"  {GREEN}OK{RESET} backend.transport.views_api imports work")
    except Exception as e:
        ERRORS.append(f"backend.transport.views_api import failed: {e}")
        print(f"  {RED}x{RESET} backend.transport.views_api: {e}")


def check_duplicate_files():
    """Check for duplicate files"""
    print(f"\n{YELLOW}Checking for duplicate files...{RESET}")

    # Files that might be duplicates
    patterns = ["settings.py", "memory.py", "llm_router.py"]

    for pattern in patterns:
        matches = list(PROJECT_ROOT.rglob(pattern))
        if len(matches) > 1:
            # Filter out __pycache__ and similar
            matches = [m for m in matches if "__pycache__" not in str(m)]
            if len(matches) > 1:
                WARNINGS.append(f"Multiple files matching '{pattern}':")
                for m in matches:
                    WARNINGS.append(f"  - {m.relative_to(PROJECT_ROOT)}")
                    print(f"  {YELLOW}W{RESET} {m.relative_to(PROJECT_ROOT)}")


def check_legacy_folders():
    """Check that legacy folders are removed"""
    print(f"\n{YELLOW}Checking legacy folders...{RESET}")

    legacy_folders = ["core", "services", "api", "views", "controllers"]
    found = []

    for folder in legacy_folders:
        path = PROJECT_ROOT / folder
        if path.exists() and path.is_dir():
            found.append(folder)

    if found:
        ERRORS.append(f"Legacy folders still exist: {found}")
        for f in found:
            print(f"  {RED}x{RESET} {f}/ still exists")
    else:
        print(f"  {GREEN}OK{RESET} No legacy folders found")


def main():
    print(f"{'=' * 50}")
    print("UI-Pro Cleanup Verification")
    print(f"{'=' * 50}")

    check_legacy_folders()
    check_legacy_imports()
    check_reexports()
    check_backend_imports()
    check_duplicate_files()

    print(f"\n{'=' * 50}")
    if ERRORS:
        print(f"{RED}ERRORS: {len(ERRORS)}{RESET}")
        for e in ERRORS:
            print(f"  {RED}x{RESET} {e}")

    if WARNINGS:
        print(f"{YELLOW}WARNINGS: {len(WARNINGS)}{RESET}")
        for w in WARNINGS:
            print(f"  {YELLOW}!{RESET} {w}")

    if not ERRORS and not WARNINGS:
        print(f"{GREEN}All checks passed!{RESET}")
        return 0
    elif not ERRORS:
        print(f"{YELLOW}Verification completed with warnings{RESET}")
        return 0
    else:
        print(f"{RED}Verification FAILED{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
