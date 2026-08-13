"""Python and LLM backend dependency checks."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.launcher.console import (
    Colors,
    print_error,
    print_header,
    print_hint,
    print_success,
    print_warning,
)
from scripts.launcher.ports import check_port
from scripts.launcher.tools import check_npm_available, check_node_available


def check_python_version() -> bool:
    """Check Python version."""
    version = sys.version_info
    min_version = (3, 10)
    if version >= min_version:
        print_success(f"Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print_error(
            f"Python {version.major}.{version.minor} - Version minimum requise: {'.'.join(map(str, min_version))}"
        )
        return False


def check_ollama_installed() -> bool:
    """Check if Ollama is installed."""
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
        except Exception:
            pass
    print_warning("Ollama non installé (optionnel)")
    return False


def check_lmstudio_installed() -> bool:
    """Check if LM Studio is installed."""
    # Check common LM Studio paths
    lmstudio_paths = [
        shutil.which("lm-studio"),
        shutil.which("LM Studio"),
        Path(os.getenv("LOCALAPPDATA", "") + "/Programs/LM Studio/lm-studio.exe")
        if os.getenv("LOCALAPPDATA")
        else None,
        Path(os.getenv("PROGRAMFILES", "") + "/LM Studio/lm-studio.exe")
        if os.getenv("PROGRAMFILES")
        else None,
    ]

    for path in lmstudio_paths:
        if path is None:
            continue
        if isinstance(path, Path):
            # Absolute path — check existence directly
            if path.exists():
                print_success("LM Studio installé")
                return True
        else:
            # Command name — search PATH
            if shutil.which(path):
                print_success("LM Studio installé")
                return True

    print_warning("LM Studio non installé (optionnel)")
    return False


def check_lemonade_installed() -> bool:
    """Check if Lemonade is installed."""
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
        ("openai", "OpenAI"),
        ("pydantic", "Pydantic"),
        ("dotenv", "python-dotenv"),
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


def _parse_node_version(version_str: str) -> tuple[int, int, int] | None:
    """Parse 'v18.17.1' into (18, 17, 1)."""
    v = version_str.lstrip("v")
    parts = v.split(".")
    if len(parts) >= 2:
        try:
            return (int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
        except ValueError:
            pass
    return None

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
        node_path = shutil.which("node")
        if node_path is None:
            print_error("Node.js non installé")
        else:
            try:
                result = subprocess.run(
                    [node_path, "--version"], capture_output=True, timeout=5
                )
                if result.returncode == 0:
                    version_str = result.stdout.decode().strip()
                    print_success(f"Node.js {version_str}")
                    # Verify minimum version 18.17
                    parsed = _parse_node_version(version_str)
                    if parsed is None:
                        print_warning("Could not parse Node.js version")
                    elif parsed < (18, 17, 0):
                        print_error(f"Node.js 18.17+ required. Found {version_str}")
                        results["node"] = False
                    else:
                        results["node"] = True
                else:
                    print_error(f"Node.js check failed (exit {result.returncode})")
            except subprocess.TimeoutExpired:
                print_error("Node.js version check timed out")
            except Exception as e:
                print_error(f"Node.js check failed: {e}")
    else:
        print_error("Node.js non installé")

    print(f"\n{Colors.BOLD}📦 npm{Colors.RESET}")
    if check_npm_available():
        npm_path = shutil.which("npm")
        if npm_path is None:
            print_error("npm non installé")
        else:
            try:
                result = subprocess.run([npm_path, "--version"], capture_output=True, timeout=5)
                if result.returncode == 0:
                    print_success(f"npm {result.stdout.decode().strip()}")
                    results["npm"] = True
                else:
                    print_error(f"npm check failed (exit {result.returncode})")
            except subprocess.TimeoutExpired:
                print_error("npm version check timed out")
            except Exception as e:
                print_error(f"npm check failed: {e}")
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

    required_ok = (
        results["python"]
        and results["node"]
        and results["npm"]
        and results["dependencies"]
    )
    optional_ok = results["ollama"] or results["lmstudio"] or results["lemonade"]

    if required_ok:
        print_success("Prérequis obligatoires ✓")
    else:
        print_error("Prérequis obligatoires manquants ✗")

    if optional_ok:
        print_success(
            f"Backends IA détectés ({sum([results['ollama'], results['lmstudio'], results['lemonade']])}/3)"
        )
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
