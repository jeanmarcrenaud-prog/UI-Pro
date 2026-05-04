#!/usr/bin/env python3
"""
🚀 UI-Pro Launcher

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
import os
import socket
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

# Port constants
API_PORT = 8000
UI_PORT = 3000

# Fix Windows encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import argparse


# Couleurs pour le terminal
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print header with colors."""
    print(f"\n{Colors.BOLD}{'=' * 50}{Colors.RESET}")
    print(f"{Colors.BOLD}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 50}{Colors.RESET}\n")


def print_hint(text: str):
    """Print hint/suggestion."""
    print(f"{Colors.CYAN}💡 {text}{Colors.RESET}")


def print_success(text: str):
    print(f"{Colors.GREEN}✓{Colors.RESET} {text}")


def print_error(text: str):
    print(f"{Colors.RED}✗{Colors.RESET} {text}")


def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {text}")


def print_info(text: str):
    print(f"{Colors.CYAN}ℹ{Colors.RESET} {text}")


def check_port(port: int) -> bool:
    """Check if a port is in use."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect(("localhost", port))
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def check_npm_available() -> bool:
    """Check if npm is available."""
    import shutil
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
    import shutil
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
        from services.model_discovery import ModelDiscovery
        discovery = ModelDiscovery(timeout=2.0)
        all_models = discovery.discover_all()
        
        # Group by backend
        by_backend = {}
        for model in all_models:
            if model.backend not in by_backend:
                by_backend[model.backend] = []
            by_backend[model.backend].append(model.name)
        
        return {
            "status": "running",
            "models": len(all_models),
            "by_backend": by_backend,
        }
    except Exception as e:
        return {"status": "not_running", "models": 0, "by_backend": {}}


def check_services():
    """Check status of all services."""
    print_header("Status des services")
    
    # FastAPI
    if check_port(8000):
        print_success("FastAPI (8000) - En cours d'exécution")
    else:
        print_warning("FastAPI (8000) - Non lancé")
    
    # Next.js
    if check_port(3000):
        print_success("Next.js UI (3000) - En cours d'exécution")
    else:
        print_warning("Next.js UI (3000) - Non lancé")
    
    # LLM Backends (Ollama, LM Studio, Lemonade)
    backends = check_backends()
    if backends["status"] == "running":
        for backend, models in backends["by_backend"].items():
            print_success(f"{backend.capitalize()} - {len(models)} modèles: {', '.join(models[:3])}{'...' if len(models) > 3 else ''}")
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


def check_python_version() -> bool:
    """Check Python version."""
    version = sys.version_info
    min_version = (3, 10)
    if version >= min_version:
        print_success(f"Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print_error(f"Python {version.major}.{version.minor} - Version minimum requise: {'.'.join(map(str, min_version))}")
        return False


def check_ollama_installed() -> bool:
    """Check if Ollama is installed."""
    import shutil
    ollama_path = shutil.which("ollama")
    if ollama_path:
        try:
            result = subprocess.run(
                [ollama_path, "--version"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                print_success("Ollama installé")
                return True
        except:
            pass
    print_warning("Ollama non installé (optionnel)")
    return False


def check_lmstudio_installed() -> bool:
    """Check if LM Studio is installed."""
    import shutil
    # Check common LM Studio paths
    lmstudio_paths = [
        shutil.which("lm-studio"),
        shutil.which("LM Studio"),
        Path(os.getenv("LOCALAPPDATA", "") + "/Programs/LM Studio/lm-studio.exe") if os.getenv("LOCALAPPDATA") else None,
        Path(os.getenv("PROGRAMFILES", "") + "/LM Studio/lm-studio.exe") if os.getenv("PROGRAMFILES") else None,
    ]
    
    for path in lmstudio_paths:
        if path and (isinstance(path, Path) and path.exists() or shutil.which(str(path))):
            print_success("LM Studio installé")
            return True
    
    print_warning("LM Studio non installé (optionnel)")
    return False


def check_lemonade_installed() -> bool:
    """Check if Lemonade is installed."""
    import shutil
    lemonade_path = shutil.which("lemonade")
    if lemonade_path:
        print_success("Lemonade installé")
        return True
    print_warning("Lemonade non installé (optionnel)")
    return False


def check_dependencies() -> bool:
    """Vérifie les dépendances Python."""
    print_header("Vérification des dépendances Python")
    
    required = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("faiss", "FAISS"),
        ("sentence_transformers", "SentenceTransformers"),
        ("requests", "requests"),
        ("pydantic", "Pydantic"),
        ("python-dotenv", "python-dotenv"),
    ]
    
    all_ok = True
    for module, name in required:
        try:
            __import__(module)
            print_success(f"{name}")
        except ImportError:
            print_error(f"{name} manquant")
            all_ok = False
    
    if not all_ok:
        print_hint("Run: pip install -r requirements.txt")
    
    return all_ok


def check_prerequisites() -> dict:
    """
    Vérifie tous les prérequis pour faire fonctionner UI-Pro.
    
    Returns:
        dict avec les résultats de chaque vérification
    """
    print_header("Vérification des prérequis")
    
    results = {
        "python": False,
        "node": False,
        "npm": False,
        "ollama": False,
        "lmstudio": False,
        "lemonade": False,
        "dependencies": False,
    }
    
    print(f"\n{Colors.BOLD}🔍 Système{Colors.RESET}")
    results["python"] = check_python_version()
    
    print(f"\n{Colors.BOLD}🔧 Node.js{Colors.RESET}")
    if check_node_available():
        import shutil
        node_path = shutil.which("node")
        result = subprocess.run([node_path, "--version"], capture_output=True, timeout=5)
        print_success(f"Node.js {result.stdout.decode().strip()}")
        results["node"] = True
    else:
        print_error("Node.js non installé")
    
    print(f"\n{Colors.BOLD}📦 npm{Colors.RESET}")
    if check_npm_available():
        import shutil
        npm_path = shutil.which("npm")
        result = subprocess.run([npm_path, "--version"], capture_output=True, timeout=5)
        print_success(f"npm {result.stdout.decode().strip()}")
        results["npm"] = True
    else:
        print_error("npm non installé")
    
    print(f"\n{Colors.BOLD}🤖 Backends IA{Colors.RESET}")
    results["ollama"] = check_ollama_installed()
    results["lmstudio"] = check_lmstudio_installed()
    results["lemonade"] = check_lemonade_installed()
    
    print(f"\n{Colors.BOLD}📚 Dépendances Python{Colors.RESET}")
    results["dependencies"] = check_dependencies()
    
    # Résumé
    print_header("Résumé")
    
    required_ok = results["python"] and results["node"] and results["npm"] and results["dependencies"]
    optional_ok = results["ollama"] or results["lmstudio"] or results["lemonade"]
    
    if required_ok:
        print_success("Prérequis obligatoires ✓")
    else:
        print_error("Prérequis obligatoires manquants ✗")
    
    if optional_ok:
        print_success(f"Backends IA détectés ({sum([results['ollama'], results['lmstudio'], results['lemonade']])}/3)")
    else:
        print_warning("Aucun backend IA détecté (optionnel)")
    
    # Vérifier les ports
    print(f"\n{Colors.BOLD}🔌 Ports{Colors.RESET}")
    if check_port(8000):
        print_warning("Port 8000 déjà utilisé (FastAPI?)")
    else:
        print_success("Port 8000 disponible")
    
    if check_port(3000):
        print_warning("Port 3000 déjà utilisé (Next.js?)")
    else:
        print_success("Port 3000 disponible")
    
    return results


def start_api(block: bool = True):
    """Lance FastAPI."""
    if check_port(8000):
        print_warning("FastAPI already running on port 8000")
        return
    
    print_header("Lancement FastAPI")
    print(f"{Colors.GREEN}→ http://localhost:{API_PORT}{Colors.RESET}")
    print(f"{Colors.GREEN}→ http://localhost:{API_PORT}/docs{Colors.RESET}")
    
    # Launch via uvicorn using venv Python
    import sys
    venv_python = sys.executable
    subprocess.run([
        venv_python, "-m", "uvicorn", "api.main:app", 
        "--host", "0.0.0.0", 
        "--port", str(API_PORT)
    ])


def start_ui():
    """Lance Next.js UI."""
    if check_port(UI_PORT):
        print_warning(f"Next.js UI already running on port {UI_PORT}")
        return
    
    if not check_npm_available():
        print_error("npm not found. Install Node.js to run UI.")
        return
    
    print_header("Lancement Next.js UI")
    print(f"{Colors.GREEN}→ http://localhost:{UI_PORT}{Colors.RESET}")
    
    project_root = Path(__file__).parent.parent
    ui_dir = project_root / "ui-pro-ui"
    
    if not ui_dir.exists():
        print_error("ui-pro-ui directory not found")
        return
    
    # Start npm dev - use full path from shutil.which
    import shutil
    npm_path = shutil.which("npm")
    if not npm_path:
        print_error("npm not found. Install Node.js to run UI.")
        return
    
    # Start npm dev in background (non-blocking)
    subprocess.Popen([npm_path, "run", "dev"], cwd=str(ui_dir))


def start_all(auto_open: bool = True):
    """Lance tous les services."""
    print_header("Lancement de tous les services")
    
    # Check all LLM backends
    backends = check_backends()
    if backends["status"] == "running":
        for backend, models in backends["by_backend"].items():
            print_success(f"{backend.capitalize()}: {len(models)} modèles")
    else:
        print_warning("Aucun backend LLM détecté - Lancez Ollama/LM Studio/Lemonade si nécessaire")
    
    # Start FastAPI in a thread
    print_info("Démarrage FastAPI...")
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()
    time.sleep(2)
    
    # Start Next.js UI
    print_info("Démarrage Next.js UI...")
    ui_thread = threading.Thread(target=start_ui, daemon=True)
    ui_thread.start()
    time.sleep(2)
    
    # Summary
    print_header("Services démarrés")
    print(f"{Colors.GREEN}FastAPI:  http://localhost:8000{Colors.RESET}")
    print(f"{Colors.GREEN}API Docs: http://localhost:8000/docs{Colors.RESET}")
    print(f"{Colors.GREEN}Next.js:  http://localhost:3000{Colors.RESET}")
    
    if auto_open:
        print("\nOuvrir http://localhost:3000 dans le navigateur...")
        time.sleep(1)
        webbrowser.open("http://localhost:3000")


def run_tests():
    """Lance les tests."""
    print_header("Lancement des tests")
    
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        cwd=Path(__file__).parent.parent
    )
    
    sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(
        description="UI-Pro Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python run.py             Lance tous les services
  python run.py --api         FastAPI uniquement
  python run.py --ui          Next.js UI uniquement
  python run.py --status      Vér status
  python run.py --check        Vérifie dépendances
  python run.py --prereq      Vérifie tous les prérequis
  python run.py --test       Lance les tests
        """
    )
    
    parser.add_argument("--api", action="store_true", help="Lance FastAPI")
    parser.add_argument("--ui", action="store_true", help="Lance Next.js UI")
    parser.add_argument("--all", action="store_true", help="Lance tous les services")
    parser.add_argument("--status", action="store_true", help="Vér status")
    parser.add_argument("--check", action="store_true", help="Vérifie dépendances")
    parser.add_argument("--prereq", action="store_true", help="Vérifie tous les prérequis")
    parser.add_argument("--test", action="store_true", help="Lance les tests")
    parser.add_argument("--no-open", action="store_true", help="Pas d'auto-open browser")
    
    args = parser.parse_args()
    
    # Default: show status
    if not any([args.api, args.ui, args.all, args.status, args.check, args.prereq, args.test]):
        args.all = True
    
    if args.status:
        check_services()
        
    elif args.check:
        check_dependencies()
        
    elif args.prereq:
        check_prerequisites()
        
    elif args.test:
        if check_dependencies():
            run_tests()
        
    elif args.ui:
        start_ui()
        
    elif args.all:
        start_all(auto_open=not args.no_open)
        
    elif args.api:
        start_api()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Arrêt...{Colors.RESET}")
        sys.exit(0)
