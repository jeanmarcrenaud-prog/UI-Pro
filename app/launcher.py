#!/usr/bin/env python3
"""
🚀 UI-Pro Launcher
==================

Entry point for UI-Pro application.
Handles:
- Dashboard Gradio (port 7860)
- FastAPI (port 8000)
- Dependency verification

Usage:
    python run.py                    # Launch dashboard
    python run.py --api              # Launch FastAPI
    python run.py --all              # Launch both
    python run.py --check            # Verify dependencies
"""

import sys
import os

# Fix Windows encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import argparse
import subprocess
import time
import threading
from pathlib import Path


# Couleurs pour le terminal
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 50}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(50)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 50}{Colors.RESET}\n")


def print_success(text: str):
    print(f"{Colors.GREEN}✓{Colors.RESET} {text}")


def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {text}")


def print_error(text: str):
    print(f"{Colors.RED}✗{Colors.RESET} {text}")


def check_dependencies() -> bool:
    """Vérifie que toutes les dépendances sont installées."""
    print_header("Vérification des dépendances")
    
    required = [
        ("gradio", "Gradio (UI)"),
        ("fastapi", "FastAPI (Web)"),
        ("faiss", "FAISS (Memory)"),
        ("sentence_transformers", "SentenceTransformers"),
        ("uvicorn", "Uvicorn (Server)"),
    ]
    
    all_ok = True
    for module, name in required:
        try:
            __import__(module)
            print_success(f"{name} installé")
        except ImportError:
            print_error(f"{name} manquant - pip install {module}")
            all_ok = False
    
    return all_ok


def check_ollama() -> bool:
    """Vérifie qu'Ollama est disponible."""
    print_header("Vérification Ollama")
    
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code == 200:
            print_success("Ollama est actif")
            models = r.json().get("models", [])
            print(f"  Modèles disponibles: {len(models)}")
            for m in models[:3]:
                print(f"    - {m.get('name', 'unknown')}")
            return True
        print_warning(f"Ollama status: {r.status_code}")
    except Exception as e:
        print_warning(f"Ollama non détecté: {e}")
        print("  → Lancez 'ollama serve' si nécessaire")
    
    return False


def check_environment() -> bool:
    """Vérifie la configuration .env."""
    print_header("Vérification configuration")
    
    env_file = Path(".env")
    if not env_file.exists():
        env_example = Path(".env.example")
        if env_example.exists():
            print_warning(".env absent - copie depuis .env.example")
            import shutil
            shutil.copy(env_example, env_file)
            print_success(".env créé depuis .env.example")
        else:
            print_error(".env.example manquant")
            return False
    
    # Vérifier les variables essentielles
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = ["OLLAMA_URL"]
    missing = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        print_warning(f"Variables manquantes: {missing}")
        print("  → Editez .env pour configurer")
        return False
    
    print_success("Configuration OK")
    return True


def start_dashboard(block: bool = True):
    """Lance le dashboard Gradio."""
    print_header("Lancement Dashboard Gradio")
    print(f"{Colors.GREEN}→ http://localhost:7860{Colors.RESET}")
    print("(Ctrl+C pour arrêter)\n")
    
    # Get project root and add to path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    # Import and run directly
    from views.dashboard import run
    run()


def start_api(block: bool = True):
    """Lance FastAPI."""
    print_header("Lancement FastAPI")
    print(f"{Colors.GREEN}→ http://localhost:8000{Colors.RESET}")
    print(f"{Colors.GREEN}→ http://localhost:8000/docs{Colors.RESET}")
    print("(Ctrl+C pour arrêter)\n")
    
    # Get project root and add to path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    # Import and run directly
    from views.api import app
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


def start_all():
    """Lance dashboard et API en parallèle."""
    print_header("Lancement de tous les services")
    
    # Démarrer l'API dans un thread
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()
    
    # Attendre un peu que l'API démarre
    time.sleep(2)
    
    # Démarrer le dashboard (bloquant)
    print(f"\n{Colors.GREEN}API démarrée sur port 8000{Colors.RESET}")
    start_dashboard()


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
        description="UI-Pro Launcher - Supervise le lancement des modules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python run.py                  Lance le dashboard
  python run.py --api            Lance FastAPI uniquement
  python run.py --all           Lance dashboard + API
  python run.py --check         Vérifie les dépendances
  python run.py --test          Lance les tests
        """
    )
    
    parser.add_argument(
        "--dashboard", 
        action="store_true",
        help="Lance le dashboard Gradio (défaut)"
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="Lance FastAPI"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Lance tous les services"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Vérifie les dépendances et configuration"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Lance les tests"
    )
    
    args = parser.parse_args()
    
    # Si aucun argument, lancer le dashboard par défaut
    if not any([args.dashboard, args.api, args.all, args.check, args.test]):
        args.dashboard = True
    
    # Vérification des dépendances (toujours sauf si --test)
    if not args.test:
        if not check_dependencies():
            print_error("Dépendances manquantes - installation requise")
            sys.exit(1)
        
        check_ollama()
        check_environment()
    
    # Exécution
    if args.check:
        print_success("Vérification terminée")
        
    elif args.test:
        run_tests()
        
    elif args.all:
        start_all()
        
    elif args.api:
        start_api()
        
    elif args.dashboard:
        start_dashboard()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Arrêt...{Colors.RESET}")
        sys.exit(0)