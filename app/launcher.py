#!/usr/bin/env python3
"""
🚀 UI-Pro Launcher
=================

Entry point for UI-Pro application.
Handles:
- FastAPI backend (port 8000)
- Next.js UI (port 3000) - via npm run dev

Usage:
    python run.py --api           # Launch FastAPI backend only
    python run.py --check         # Verify dependencies
    python run.py --test          # Run tests

Note: Next.js UI is now the primary interface.
Run it separately: cd ui-pro-ui && npm run dev
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


def start_api():
    """Lance FastAPI."""
    print_header("Lancement FastAPI")
    print(f"{Colors.GREEN}→ http://localhost:8000{Colors.RESET}")
    print(f"{Colors.GREEN}→ http://localhost:8000/docs{Colors.RESET}")
    print(f"{Colors.YELLOW}→ http://localhost:3000 (Next.js UI){Colors.RESET}")
    print("(Ctrl+C pour arrêter)\n")
    
    # Get project root and add to path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    # Import and run directly
    from views.api import app
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


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
  python run.py --api           Lance FastAPI (Next.js UI separate)
  python run.py --check         Vérifie les dépendances
  python run.py --test          Lance les tests

Note: Next.js UI runs separately:
  cd ui-pro-ui && npm run dev
        """
    )
    
    parser.add_argument(
        "--api",
        action="store_true",
        help="Lance FastAPI backend"
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
    
    # Default to API if no args
    if not any([args.api, args.check, args.test]):
        args.api = True
    
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
        
    elif args.api:
        start_api()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Arrêt...{Colors.RESET}")
        sys.exit(0)