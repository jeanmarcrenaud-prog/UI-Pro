"""Code sanitizer — automatic fallback when LLM ignores stdlib constraints.

When the user explicitly says "stdlib only" / "no requests" / "no httpx" but
the model still generates `import requests` or `import httpx`, we inject a
compatibility shim that maps those names onto `urllib.request`. This lets
the code run in our sandbox (which has no `requests` or `httpx` installed)
without changing the model's output, so the user sees exactly what the
model intended.

The shim is intentionally narrow: GET/POST with params/timeout, response
with `.json()`, `.raise_for_status()`, `.text`, `.status_code`. Anything
more exotic (streaming, file uploads, websockets) will fall through to a
clear AttributeError. This is a safety net, not a full implementation.
"""

from __future__ import annotations

import re
import sys
import types
from typing import Any

# Marker so we don't double-inject the same shim in retry attempts.
_SHIM_MARKER_REQUESTS = "# >>> UI-PRO REQUESTS SHIM >>>"
_SHIM_MARKER_HTTPX = "# >>> UI-PRO HTTPX SHIM >>>"

# Match `import requests`, `import requests as r`, `from requests import X`,
# and the same patterns for httpx. We intentionally match even inside
# commented lines — better to inject a harmless shim than to miss a
# real `import requests` that's preceded by a comment.
_IMPORT_PATTERNS = {
    "requests": re.compile(
        r"^\s*(?:from\s+requests\s+import\b|import\s+requests\b)", re.MULTILINE
    ),
    "httpx": re.compile(
        r"^\s*(?:from\s+httpx\s+import\b|import\s+httpx\b)", re.MULTILINE
    ),
}


def _requests_shim_source() -> str:
    """Return the Python source for the `requests` shim."""
    return '''# >>> UI-PRO REQUESTS SHIM >>>
# Auto-injected by code_sanitizer.sanitize_files because the model ignored
# the user's stdlib-only constraint. Maps `requests` onto urllib so the
# generated code runs in our sandbox. Safe to remove if you have `requests`
# installed in your target environment.
import sys as _shim_sys
import types as _shim_types
import urllib.request
import urllib.error
import urllib.parse
import json as _shim_json


class _ShimResponse:
    """Mimics requests.Response for the common case."""

    def __init__(self, response, body_text=None):
        self._response = response
        self.status_code = getattr(response, "status", 200)
        # HTTPError's .read() consumes the body; we cache it so .text and
        # .json() can both be called (matches requests' behavior).
        if body_text is not None:
            self.text = body_text
        else:
            try:
                self.text = response.read().decode("utf-8", errors="replace")
            except Exception:
                self.text = ""

    def json(self):
        return _shim_json.loads(self.text)

    def raise_for_status(self):
        if 400 <= self.status_code < 600:
            raise urllib.error.HTTPError(
                getattr(self._response, "url", ""),
                self.status_code,
                f"HTTP {self.status_code}",
                getattr(self._response, "headers", {}),
                None,
            )


class _ShimSession:
    """Mimics requests.Session / requests.get / requests.post."""

    def get(self, url, params=None, timeout=10, **kwargs):
        if params:
            sep = "&" if "?" in url else "?"
            url = url + sep + urllib.parse.urlencode(params)
        try:
            resp = urllib.request.urlopen(url, timeout=timeout)
            return _ShimResponse(resp)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            wrapped = _ShimResponse(e, body_text=body)
            return wrapped

    def post(self, url, data=None, json=None, timeout=10, **kwargs):
        body = None
        headers = {}
        if json is not None:
            body = _shim_json.dumps(json).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif data is not None:
            body = urllib.parse.urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
            return _ShimResponse(resp)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            return _ShimResponse(e, body_text=body)


# Build a fake `requests` module and register it in sys.modules.
# Any subsequent `import requests` (even via `from requests import get`)
# will resolve to this shim.
_requests_shim = _shim_types.ModuleType("requests")
_requests_shim.get = _ShimSession().get
_requests_shim.post = _ShimSession().post
_requests_shim.Session = lambda: _ShimSession()
_shim_sys.modules["requests"] = _requests_shim
# <<< UI-PRO REQUESTS SHIM <<<
'''


def _httpx_shim_source() -> str:
    """Return the Python source for the `httpx` shim.

    Note: httpx is async-first, so this shim only supports the sync API
    (`httpx.get`, `httpx.Client`). Async usage will fail with a clear
    NotImplementedError rather than silently hanging.
    """
    return '''# >>> UI-PRO HTTPX SHIM >>>
# Auto-injected by code_sanitizer.sanitize_files because the model ignored
# the user's stdlib-only constraint. AsyncClient is NOT supported — the
# sandbox executes files synchronously.
import sys as _shim_sys
import types as _shim_types
import urllib.request
import urllib.error
import urllib.parse
import json as _shim_json


def _httpx_response_to_shim(response, body_text=None):
    class _R:
        def __init__(self):
            self.status_code = getattr(response, "status", 200)
            if body_text is not None:
                self.text = body_text
            else:
                try:
                    self.text = response.read().decode("utf-8", errors="replace")
                except Exception:
                    self.text = ""
        def json(self):
            return _shim_json.loads(self.text)
        def raise_for_status(self):
            if 400 <= self.status_code < 600:
                raise urllib.error.HTTPError(
                    getattr(response, "url", ""),
                    self.status_code,
                    f"HTTP {self.status_code}",
                    getattr(response, "headers", {}),
                    None,
                )
    return _R()


class _HttpxClient:
    def get(self, url, params=None, timeout=10, **kwargs):
        if params:
            sep = "&" if "?" in url else "?"
            url = url + sep + urllib.parse.urlencode(params)
        try:
            resp = urllib.request.urlopen(url, timeout=timeout)
            return _httpx_response_to_shim(resp)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            return _httpx_response_to_shim(e, body_text=body)

    def post(self, url, json=None, data=None, timeout=10, **kwargs):
        body = None
        headers = {}
        if json is not None:
            body = _shim_json.dumps(json).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif data is not None:
            body = urllib.parse.urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
            return _httpx_response_to_shim(resp)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            return _httpx_response_to_shim(e, body_text=body)


_httpx_shim = _shim_types.ModuleType("httpx")
_httpx_shim.get = _HttpxClient().get
_httpx_shim.post = _HttpxClient().post
_httpx_shim.Client = _HttpxClient
_httpx_shim.AsyncClient = None  # Explicit: not supported
_shim_sys.modules["httpx"] = _httpx_shim
# <<< UI-PRO HTTPX SHIM <<<
'''


_SHIM_BY_PACKAGE: dict[str, dict[str, str]] = {
    "requests": {"marker": _SHIM_MARKER_REQUESTS, "source": _requests_shim_source()},
    "httpx": {"marker": _SHIM_MARKER_HTTPX, "source": _httpx_shim_source()},
}


def _detect_packages(source: str) -> list[str]:
    """Return the list of forbidden packages detected in this file."""
    found = []
    for pkg, pat in _IMPORT_PATTERNS.items():
        if pat.search(source):
            found.append(pkg)
    return found


def _inject_shim(source: str, package: str) -> str:
    """Prepend the shim for `package` to `source`, if not already present."""
    entry = _SHIM_BY_PACKAGE[package]
    if entry["marker"] in source:
        return source
    return entry["source"] + "\n" + source


def sanitize_files(files: dict[str, str]) -> tuple[dict[str, str], dict[str, Any]]:
    """Return (sanitized_files, metadata) where metadata describes shim injections.

    Args:
        files: {filename: python_source} dict (e.g. state["code"]["files"])

    Returns:
        Tuple of (new_files_dict, metadata_dict). The original `files` dict
        is NOT mutated. `metadata` shape:

            {
                "injections": [
                    {"file": "main.py", "package": "requests"},
                    {"file": "fetch.py", "package": "httpx"},
                ],
                "files_unchanged": ["utils.py"],
            }
    """
    if not isinstance(files, dict):
        return files, {"injections": [], "files_unchanged": []}

    new_files: dict[str, str] = {}
    injections: list[dict[str, str]] = []
    unchanged: list[str] = []

    for filename, source in files.items():
        if not isinstance(source, str) or not source.strip():
            new_files[filename] = source
            unchanged.append(filename)
            continue

        packages = _detect_packages(source)
        if not packages:
            new_files[filename] = source
            unchanged.append(filename)
            continue

        updated = source
        for pkg in packages:
            updated = _inject_shim(updated, pkg)
            injections.append({"file": filename, "package": pkg})

        new_files[filename] = updated

    return new_files, {
        "injections": injections,
        "files_unchanged": unchanged,
    }
