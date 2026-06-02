"""Port probing utilities."""
import socket
import time
import urllib.error
import urllib.request


def check_port(port: int) -> bool:
    """Check if a port is in use."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect(("localhost", port))
            return True
    except (TimeoutError, ConnectionRefusedError, OSError):
        return False


def wait_for_port(port: int, host: str = "localhost", timeout: int = 30, interval: float = 0.5) -> bool:
    """Wait for a port to be ready, including HTTP health check.

    Two-phase approach:
    Phase 1 — Quick socket poll until TCP port is open (server listening).
    Phase 2 — Try /health with a generous timeout — first request may be
              slow due to lazy initialization (vector memory, backends).

    Returns True if ready within timeout, False otherwise.
    """
    start = time.time()

    # Phase 1: Wait for TCP port to open
    port_open = False
    while time.time() - start < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                s.connect((host, port))
            port_open = True
            break
        except (TimeoutError, ConnectionRefusedError, OSError):
            time.sleep(interval)

    if not port_open:
        return False

    # Phase 2: Port is open — wait for a successful HTTP response.
    # First request may be slow (lazy init, model discovery, etc.).
    # Use a generous timeout for the first attempt, then shorter ones.
    http_deadline = start + timeout
    attempt = 0

    while time.time() < http_deadline:
        attempt += 1
        remaining = max(http_deadline - time.time(), 1)

        # First attempt gets extra time (15s), subsequent get remaining
        read_timeout = min(15 if attempt == 1 else remaining, 15)

        try:
            req = urllib.request.Request(f"http://{host}:{port}/health", method="GET")
            resp = urllib.request.urlopen(req, timeout=read_timeout)
            if resp.status == 200:
                return True
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
            pass

        if time.time() < http_deadline:
            time.sleep(interval)

    return False
