"""Service status checks and launchers."""
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from scripts.launcher.console import (
    Colors,
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
)
from scripts.launcher.ports import check_port, find_free_port, wait_for_port
from scripts.launcher.tools import (
    check_backends,
    check_npm_available,
    check_node_available,
)

# Port constants
API_PORT = 8000
UI_PORT = 3000


def check_services():
    """Check status of all services."""
    print_header("Status des services")

    # FastAPI
    if check_port(API_PORT):
        print_success(f"FastAPI ({API_PORT}) - En cours d'exécution")
    else:
        print_warning(f"FastAPI ({API_PORT}) - Non lancé")

    # Next.js
    if check_port(UI_PORT):
        print_success(f"Next.js UI ({UI_PORT}) - En cours d'exécution")
    else:
        print_warning(f"Next.js UI ({UI_PORT}) - Non lancé")

    # LLM Backends (Ollama, LM Studio, Lemonade)
    backends = check_backends()
    if backends["status"] == "running":
        for backend, models in backends["by_backend"].items():
            print_success(
                f"{backend.capitalize()} - {len(models)} modèles: {', '.join(models[:3])}{'...' if len(models) > 3 else ''}"
            )
    else:
        print_warning("Aucun backend LLM détecté")

    # Node/npm
    if check_node_available():
        print_success("Node.js - Installé")
    else:
        print_warning("Node.js - Non installé")

    if check_npm_available():
        print_success("npm - Installé")
    else:
        print_warning("npm - Non installé")


def _resolve_python() -> str:
    """Return the project's .venv Python, falling back to ``sys.executable``.

    The launcher (``run.py``) is often invoked with the **system** Python
    (``#!/usr/bin/env python3``).  Packages installed inside ``.venv/``
    (e.g. ``ui-pro-prompts``) are invisible to the system interpreter, so
    we explicitly resolve the venv path here.
    """
    project_root = Path(__file__).parent.parent.parent
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def start_api(block: bool = True):
    """Lance FastAPI avec auto-détection du port."""
    global API_PORT
    API_PORT = find_free_port(8000)
    original = 8000

    if API_PORT != original:
        print_warning(f"Port {original} déjà utilisé — API sur le port {API_PORT}")

    print_header("Lancement FastAPI")
    print(f"{Colors.GREEN}→ http://localhost:{API_PORT}{Colors.RESET}")
    print(f"{Colors.GREEN}→ http://localhost:{API_PORT}/docs{Colors.RESET}")

    # Launch via uvicorn — use .venv Python (see _resolve_python)
    python_exe = _resolve_python()
    subprocess.run(
        [
            python_exe,
            "-m",
            "uvicorn",
            "backend.transport.views_api:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(API_PORT),
        ]
    )


def start_ui():
    """Lance Next.js UI avec auto-détection du port."""
    global UI_PORT
    UI_PORT = find_free_port(3000)
    original = 3000

    if UI_PORT != original:
        print_warning(f"Port {original} déjà utilisé — UI sur le port {UI_PORT}")

    if not check_npm_available():
        print_error("npm not found. Install Node.js to run UI.")
        return

    print_header("Lancement Next.js UI")
    print(f"{Colors.GREEN}→ http://localhost:{UI_PORT}{Colors.RESET}")

    project_root = Path(__file__).parent.parent.parent
    ui_dir = project_root / "frontend"

    if not ui_dir.exists():
        print_error("frontend directory not found")
        return

    npm_path = shutil.which("npm")
    if not npm_path:
        print_error("npm not found. Install Node.js to run UI.")
        return

    subprocess.Popen(
        [npm_path, "exec", "--", "next", "dev", "-p", str(UI_PORT)],
        cwd=str(ui_dir),
    )

def start_all(auto_open: bool = True):
    """Lance tous les services."""
    global API_PORT, UI_PORT
    print_header("Lancement de tous les services")

    # Auto-détection des ports libres
    API_PORT = find_free_port(8000)
    UI_PORT = find_free_port(3000)
    if API_PORT != 8000:
        print_warning(f"Port 8000 déjà utilisé — API sur le port {API_PORT}")
    if UI_PORT != 3000:
        print_warning(f"Port 3000 déjà utilisé — UI sur le port {UI_PORT}")
    # LangSmith Tracing
    try:
        from backend.infrastructure.tracing import setup_langsmith_tracing

        if setup_langsmith_tracing():
            print_success("LangSmith tracing activé")
        else:
            print_info("LangSmith tracing désactivé")
    except Exception as e:
        print_warning(f"LangSmith init failed: {e}")

    # Check all LLM backends
    backends = check_backends()
    if backends["status"] == "running":
        for backend, models in backends["by_backend"].items():
            print_success(f"{backend.capitalize()}: {len(models)} modèles")
    else:
        print_warning(
            "Aucun backend LLM détecté - Lancez Ollama/LM Studio/Lemonade si nécessaire"
        )

    # Start FastAPI in a non-daemon thread so the process stays alive
    print_info("Démarrage FastAPI...")
    api_thread = threading.Thread(target=start_api, daemon=False)
    api_thread.start()

    # Wait for FastAPI to be ready (with health check)
    # Timeout generous car FAISS + sentence_transformers peuvent prendre
    # ~50s à charger en mémoire (même en arrière-plan).
    print_info("Attente du backend FastAPI (jusqu'à 120s)...")
    if not wait_for_port(API_PORT, timeout=120):
        print_error(f"FastAPI n'a pas démarré sur le port {API_PORT} dans les 120s")
        return
    print_success("FastAPI prêt")

    # Start Next.js UI
    print_info("Démarrage Next.js UI...")
    ui_thread = threading.Thread(target=start_ui, daemon=True)

    # Give UI a moment to announce
    time.sleep(1)

    # Summary
    print_header("Services démarrés")
    print(f"{Colors.GREEN}FastAPI:  http://localhost:{API_PORT}{Colors.RESET}")
    print(f"{Colors.GREEN}API Docs: http://localhost:{API_PORT}/docs{Colors.RESET}")
    print(f"{Colors.GREEN}Next.js:  http://localhost:{UI_PORT}{Colors.RESET}")

    if auto_open:
        print(f"\nOuvrir http://localhost:{UI_PORT} dans le navigateur...")
        time.sleep(1)
        webbrowser.open(f"http://localhost:{UI_PORT}")

    # Keep the main thread alive — join on FastAPI thread.
    # When user presses Ctrl+C, api_thread (blocked on subprocess.run)
    # will get interrupted and the KeyboardInterrupt propagates here.
    print(
        f"\n{Colors.BOLD}{Colors.CYAN}Appuyez sur Ctrl+C pour arrêter tous les services{Colors.RESET}"
    )
    while api_thread.is_alive():
        try:
            api_thread.join(timeout=1)
        except KeyboardInterrupt:
            break


def run_tests():
    """Lance les tests."""
    print_header("Lancement des tests")

    result = subprocess.run(
        [_resolve_python(), "-m", "pytest", "tests/", "-v", "--tb=short"],
        cwd=Path(__file__).parent.parent.parent,
    )

    sys.exit(result.returncode)
