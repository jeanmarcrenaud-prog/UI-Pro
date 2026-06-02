#!/usr/bin/env python3
"""
[START] UI-Pro Launcher

Entry point for UI-Pro application.
Handles:
- FastAPI backend (API_PORT)
- Next.js UI (UI_PORT)
- Auto-discovery of running services

Usage:
    python run.py                  Launch all services
    python run.py --api          FastAPI only
    python run.py --ui            Next.js UI only
    python run.py --check         Verify dependencies
    python run.py --test         Run tests
    python run.py --status        Check running services
"""
import sys
from pathlib import Path

# Ensure repo root is on sys.path so `scripts.launcher` imports resolve
sys.path.insert(0, str(Path(__file__).parent))

from scripts.launcher.cli import main
from scripts.launcher.console import Colors, setup_windows_encoding

if __name__ == "__main__":
    setup_windows_encoding()
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Arrêt...{Colors.RESET}")
        sys.exit(0)
