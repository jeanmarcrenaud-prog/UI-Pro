#!/usr/bin/env python3
"""
UI-Pro Setup Script

Sets up the full development environment:
- Creates Python virtual environment
- Installs Python dependencies
- Installs Node.js dependencies for frontend
- Creates .env file from template
- Checks for required services (Ollama, LM Studio, Lemonade)
- Offers to install Ollama if no backend detected
"""

import os
import sys
import subprocess
import shutil
import socket
import platform
from pathlib import Path
from typing import Optional

# ====================== Colors ======================

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_step(msg: str):
    print(f"\n{Colors.BLUE}{Colors.BOLD}>> {msg}{Colors.END}")


def print_success(msg: str):
    print(f"{Colors.GREEN}[OK] {msg}{Colors.END}")


def print_warning(msg: str):
    print(f"{Colors.YELLOW}[!] {msg}{Colors.END}")


def print_error(msg: str):
    print(f"{Colors.RED}[X] {msg}{Colors.END}")


# ====================== Helpers ======================

def run_command(cmd: list[str], cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run shell command with error handling."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            check=check,
            capture_output=True,
            text=True,
            timeout=120
        )
        return result
    except subprocess.CalledProcessError as e:
        if check:
            print_error(f"Command failed: {' '.join(cmd)}")
            if e.stderr:
                print(e.stderr)
            sys.exit(1)
        return e
    except FileNotFoundError:
        print_error(f"Command not found: {cmd[0]}")
        sys.exit(1)


def check_port(host: str, port: int, name: str) -> bool:
    """Check if a port is open."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex((host, port))
        if result == 0:
            print_success(f"{name} running on {host}:{port}")
            return True
        print_warning(f"{name} not running on {host}:{port}")
        return False
    except Exception:
        print_warning(f"{name} not reachable")
        return False
    finally:
        sock.close()


# ====================== Checks ======================

def check_python_version() -> bool:
    """Check Python version is 3.10+."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print_error(f"Python 3.10+ required. Found {version.major}.{version.minor}")
        return False
    print_success(f"Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_node() -> bool:
    """Check Node.js and npm availability."""
    node_path = shutil.which('node')
    npm_path = shutil.which('npm')
    
    if not node_path:
        print_error("Node.js not found. Please install from https://nodejs.org")
        return False
    
    try:
        result = subprocess.run([node_path, '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print_success(f"Node.js {result.stdout.strip()}")
    except Exception:
        print_error("Node.js not found")
        return False
    
    if not npm_path:
        print_warning("npm not found - skipping frontend setup")
        return False
    
    try:
        result = subprocess.run([npm_path, '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print_success(f"npm {result.stdout.strip()}")
            return True
    except Exception:
        pass
    
    print_warning("npm not found - skipping frontend setup")
    return False


def check_services(skip_prompts: bool = False) -> bool:
    """Check if LLM backends are running."""
    print_step("Checking LLM backends...")

    ollama = check_port('localhost', 11434, 'Ollama')
    lmstudio = check_port('localhost', 1234, 'LM Studio')
    lemonade = check_port('localhost', 8080, 'Lemonade')

    if not ollama and not lmstudio and not lemonade:
        print_warning("No LLM backend detected!")
        
        if not skip_prompts:
            print(f"""
{Colors.BOLD}Would you like to install Ollama with qwen3.5:0.8B?{Colors.END}
This is a lightweight model (~500MB) perfect for getting started.
""")
            response = input("Install Ollama? [Y/n]: ").strip().lower()
            if response in ('', 'y', 'yes'):
                install_ollama()
        else:
            print("Skipping Ollama installation (CI mode)")
            print("To install manually: https://ollama.com")

    return True


# ====================== Setup ======================

def setup_venv(project_root: Path) -> bool:
    """Create and populate Python virtual environment."""
    venv_path = project_root / '.venv'
    print_step(f"Setting up virtual environment at {venv_path.name}...")

    if venv_path.exists():
        # Check if valid
        pip_path = venv_path / 'Scripts' / 'pip.exe' if os.name == 'nt' else venv_path / 'bin' / 'pip'
        if pip_path.exists():
            print_success("Virtual environment already exists")
            return True
        # Corrupted - recreate
        print_warning("Corrupted venv detected, recreating...")
        shutil.rmtree(venv_path)

    # Create venv
    run_command([sys.executable, '-m', 'venv', str(venv_path)])

    # Determine pip
    pip_path = venv_path / 'Scripts' / 'pip.exe' if os.name == 'nt' else venv_path / 'bin' / 'pip'

    # Upgrade pip
    run_command([str(pip_path), 'install', '--upgrade', 'pip'])

    # Install requirements
    req_file = project_root / 'requirements.txt'
    if req_file.exists():
        print_step("Installing Python dependencies...")
        result = run_command([str(pip_path), 'install', '-r', str(req_file)], check=False)
        if result.returncode != 0:
            print_warning("Some packages failed to install (continuing)")
        else:
            print_success("Python dependencies installed")
    else:
        print_warning("requirements.txt not found")

    return True


def setup_frontend(project_root: Path) -> bool:
    """Install frontend dependencies."""
    ui_path = project_root / 'ui-pro-ui'
    if not ui_path.exists():
        print_warning(f"Frontend directory not found - skipping")
        return True

    npm_path = shutil.which('npm')
    if not npm_path:
        print_warning("npm not found - skipping frontend setup")
        return True

    print_step("Installing frontend dependencies...")
    if not (ui_path / 'node_modules').exists():
        result = run_command([npm_path, 'install'], cwd=ui_path, check=False)
        if result.returncode != 0:
            print_warning("Failed to install npm packages (continuing)")
        else:
            print_success("Frontend dependencies installed")
    else:
        print_success("node_modules already exists")

    return True


def setup_env_file(project_root: Path) -> bool:
    """Create .env file from template."""
    env_file = project_root / '.env'
    env_example = project_root / '.env.example'

    if env_file.exists():
        print_success(".env already exists")
        return True

    if env_example.exists():
        shutil.copy(env_example, env_file)
        print_success("Created .env from template")
        print_warning("Please edit .env with your settings")
    else:
        print_warning(".env.example not found")

    return True


# ====================== Ollama Install ======================

def install_ollama() -> bool:
    """Install Ollama and pull qwen3.5:0.8B model."""
    print_step("Installing Ollama...")

    system = platform.system()

    try:
        if system == 'Windows':
            print("Installing via PowerShell...")
            result = subprocess.run(
                ['powershell', '-Command', 'irm https://ollama.com/install.ps1 | iex'],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                print_warning("PowerShell install failed")
                print("Please download from: https://ollama.com/download")
                return False
            print_success("Ollama installed")

        elif system == 'Darwin':
            print("Installing via curl...")
            subprocess.run(
                ['curl', '-fsSL', 'https://ollama.com/install.sh', '|', 'sh'],
                shell=True,
                capture_output=True,
                timeout=120
            )
            print_success("Ollama installed")

        elif system == 'Linux':
            print("Installing via curl...")
            result = subprocess.run(
                ['curl', '-fsSL', 'https://ollama.com/install.sh', '|', 'sh'],
                shell=True,
                capture_output=True,
                timeout=120
            )
            if result.returncode != 0:
                print_warning("Install script failed")
                return False
            print_success("Ollama installed")

        else:
            print_warning(f"Unsupported system: {system}")
            print("Please install manually from https://ollama.com")
            return False

    except Exception as e:
        print_warning(f"Failed to install Ollama: {e}")
        print("Please install manually from https://ollama.com")
        return False

    # Pull model
    print_step("Pulling qwen3.5:0.8B model (may take a few minutes)...")

    try:
        # Start serve in background
        subprocess.Popen(
            ['ollama', 'serve'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        import time
        time.sleep(2)

        # Pull model
        result = subprocess.run(
            ['ollama', 'pull', 'qwen3.5:0.8b'],
            capture_output=True,
            text=True,
            timeout=600
        )

        if result.returncode == 0:
            print_success("qwen3.5:0.8B model downloaded!")
        else:
            print_warning("Failed to pull model")
            print("Pull later with: ollama pull qwen3.5:0.8b")

    except Exception as e:
        print_warning(f"Failed to pull model: {e}")
        print("Pull later with: ollama pull qwen3.5:0.8b")

    return True


# ====================== Main ======================

def main():
    """Main setup routine."""
    skip_prompts = '--yes' in sys.argv or '-y' in sys.argv

    print(f"""
{Colors.BOLD}============================================================
                    UI-PRO ENVIRONMENT SETUP
============================================================{Colors.END}
""")

    project_root = Path(__file__).parent.resolve()
    os.chdir(project_root)
    print(f"Project root: {project_root}")

    # Checks
    print_step("Checking prerequisites...")
    if not check_python_version():
        sys.exit(1)
    if not check_node():
        print_warning("Continuing without Node.js...")

    # Setup
    setup_venv(project_root)
    setup_frontend(project_root)
    setup_env_file(project_root)
    check_services(skip_prompts)

    # Done
    print(f"""
{Colors.BOLD}============================================================
                      SETUP COMPLETE!
============================================================{Colors.END}

{Colors.BOLD}Next steps:{Colors.END}

  1. Start LLM backend:
     - Ollama:   ollama serve
     - LM Studio: Run the app

  2. Run the application:
     python run.py --all

  3. Open browser: http://localhost:3000

{Colors.BOLD}Useful commands:{Colors.END}
  python run.py --status    # Check services
  python run.py --check     # Verify deps
  python run.py --api       # FastAPI only
  python run.py --ui        # Next.js only
""")


if __name__ == '__main__':
    main()