#!/usr/bin/env python3
"""
UI-Pro Setup Script

Sets up the development environment for UI-Pro:
- Creates Python virtual environment
- Installs Python dependencies
- Installs Node.js dependencies for frontend
- Creates .env file from template
- Checks for required services
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# Colors for output
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

def run_command(cmd: list, cwd: str = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            check=check,
            capture_output=True,
            text=True
        )
    except subprocess.CalledProcessError as e:
        if check:
            print_error(f"Command failed: {' '.join(cmd)}")
            print(e.stderr)
            sys.exit(1)
        return e

def check_python_version() -> bool:
    """Check if Python version is 3.10+."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print_error(f"Python 3.10+ required, found {version.major}.{version.minor}")
        return False
    print_success(f"Python {version.major}.{version.minor}.{version.micro}")
    return True

def check_node_version() -> bool:
    """Check if Node.js is available."""
    try:
        result = run_command(['node', '--version'], check=False)
        if result.returncode == 0:
            print_success(f"Node.js {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    print_error("Node.js not found. Please install Node.js 18+ from https://nodejs.org")
    return False

def check_npm_version() -> bool:
    """Check if npm is available."""
    # Try to find npm using shutil.which
    npm_path = shutil.which('npm')
    if npm_path:
        try:
            result = subprocess.run([npm_path, '--version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print_success(f"npm {result.stdout.strip()}")
                return True
        except Exception:
            pass
    print_warning("npm not found - will skip Node.js setup")
    return False

def setup_python_venv(venv_path: Path) -> bool:
    """Create and populate Python virtual environment."""
    print_step("Setting up Python virtual environment...")
    
    if venv_path.exists():
        print_success(f"Virtual environment already exists at {venv_path}")
        # Check if pip exists in the venv
        if sys.platform == 'win32':
            pip_path = venv_path / 'Scripts' / 'pip.exe'
        else:
            pip_path = venv_path / 'bin' / 'pip'
        
        if pip_path.exists():
            print_success("Using existing venv")
            return True
        else:
            # Corrupted venv, recreate
            print_warning("Corrupted venv detected, recreating...")
            shutil.rmtree(venv_path)
    
    # Create venv
    run_command([sys.executable, '-m', 'venv', str(venv_path)])
    
    # Determine pip path
    if sys.platform == 'win32':
        pip_path = venv_path / 'Scripts' / 'pip.exe'
    else:
        pip_path = venv_path / 'bin' / 'pip'
    
    # Upgrade pip
    print_step("Upgrading pip...")
    run_command([str(pip_path), 'install', '--upgrade', 'pip'])
    
    # Install requirements
    print_step("Installing Python dependencies...")
    requirements = Path(__file__).parent / 'requirements.txt'
    result = run_command([str(pip_path), 'install', '-r', str(requirements)], check=False)
    
    if result.returncode != 0:
        print_error("Failed to install some packages (continuing anyway)")
        print(result.stderr)
    else:
        print_success("Python dependencies installed")
    
    return True

def setup_node_modules(ui_path: Path) -> bool:
    """Install Node.js dependencies."""
    # Check if npm is available
    npm_path = shutil.which('npm')
    if not npm_path:
        print_warning("npm not available, skipping Node.js setup")
        return True
    
    print_step("Installing Node.js dependencies...")
    
    if not (ui_path / 'node_modules').exists():
        result = run_command([npm_path, 'install'], cwd=str(ui_path), check=False)
        if result.returncode != 0:
            print_warning("Failed to install npm packages (continuing)")
            print(result.stderr)
        else:
            print_success("Node.js dependencies installed")
    else:
        print_success("node_modules already exists")
    
    return True

def setup_env_file() -> bool:
    """Create .env file from template if it doesn't exist."""
    print_step("Setting up environment variables...")
    
    env_file = Path('.env')
    env_example = Path('.env.example')
    
    if env_file.exists():
        print_success(".env already exists")
        return True
    
    if env_example.exists():
        shutil.copy(env_example, env_file)
        print_success("Created .env from .env.example")
        print_warning("Please edit .env and add your HF_TOKEN if needed")
    else:
        print_warning(".env.example not found, skipping env setup")
    
    return True

def check_services() -> bool:
    """Check if required services are running."""
    print_step("Checking required services...")
    
    import socket
    
    def check_port(host: str, port: int, name: str) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            result = sock.connect_ex((host, port))
            if result == 0:
                print_success(f"{name} is running on {host}:{port}")
                return True
            else:
                print_warning(f"{name} not running on {host}:{port}")
                return False
        except Exception:
            print_warning(f"{name} not reachable")
            return False
        finally:
            sock.close()
    
    ollama = check_port('localhost', 11434, 'Ollama')
    lmstudio = check_port('localhost', 1234, 'LM Studio')
    
    if not ollama and not lmstudio:
        print_warning("No LLM backend running. Start Ollama or LM Studio to use the app.")
    
    return True

def print_next_steps():
    """Print instructions for next steps."""
    print(f"""
{Colors.BOLD}============================================================
                      SETUP COMPLETE!
============================================================{Colors.END}

{Colors.BOLD}Next steps:{Colors.END}

  1. {Colors.BLUE}Start Ollama (optional but recommended):{Colors.END}
     $ ollama serve

  2. {Colors.BLUE}Run the application:{Colors.END}
     $ python run.py --all

  3. {Colors.BLUE}Open in browser:{Colors.END}
     http://localhost:3000

{Colors.BOLD}Configuration:{Colors.END}
  - Edit .env to configure models and settings
  - Default models: qwen2.5-coder:32b (fast), qwen-opus (reasoning)
  - Backend URLs: Ollama (11434), LM Studio (1234)

{Colors.BOLD}Useful commands:{Colors.END}
  $ python run.py --status    # Check service status
  $ python run.py --check     # Verify dependencies
  $ python run.py --api       # FastAPI only
  $ python run.py --ui        # Next.js UI only
""")

def main():
    """Main setup function."""
    print(f"""
{Colors.BOLD}============================================================
                    UI-PRO ENVIRONMENT SETUP
============================================================{Colors.END}
""")
    
    # Get project root
    project_root = Path(__file__).parent.resolve()
    os.chdir(project_root)
    
    print(f"Project root: {project_root}")
    
    # Check prerequisites
    print_step("Checking prerequisites...")
    if not check_python_version():
        sys.exit(1)
    if not check_node_version():
        sys.exit(1)
    if not check_npm_version():
        sys.exit(1)
    
    # Setup Python venv
    venv_path = project_root / '.venv'
    if not setup_python_venv(venv_path):
        print_error("Python setup failed")
        sys.exit(1)
    
    # Setup Node modules
    ui_path = project_root / 'ui-pro-ui'
    if not setup_node_modules(ui_path):
        print_error("Node.js setup failed")
        sys.exit(1)
    
    # Setup .env
    setup_env_file()
    
    # Check services
    check_services()
    
    # Print next steps
    print_next_steps()

if __name__ == '__main__':
    main()