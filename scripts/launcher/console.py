"""Colored console output utilities."""
import io
import sys


class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def setup_windows_encoding() -> None:
    """Force UTF-8 encoding for stdout/stderr on Windows."""
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def print_header(text: str):
    """Print header with colors."""
    print(f"\n{Colors.BOLD}{'=' * 50}{Colors.RESET}")
    print(f"{Colors.BOLD}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 50}{Colors.RESET}\n")


def print_hint(text: str):
    """Print hint/suggestion."""
    print(f"{Colors.CYAN}[IDEA] {text}{Colors.RESET}")


def print_success(text: str):
    print(f"{Colors.GREEN}✓{Colors.RESET} {text}")


def print_error(text: str):
    print(f"{Colors.RED}✗{Colors.RESET} {text}")


def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {text}")


def print_info(text: str):
    print(f"{Colors.CYAN}ℹ{Colors.RESET} {text}")
