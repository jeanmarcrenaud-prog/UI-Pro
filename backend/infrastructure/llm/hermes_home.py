"""Resolve and read the real Hermes agent configuration (``HERMES_HOME``).

ui-pro ships its own optional ``hermes_llm_base_url`` / ``hermes_llm_model``
overrides (exposed in the Settings UI, persisted to ``.env``). When neither is
set, the *real* Hermes agent config — the ``config.yaml`` under ``HERMES_HOME``
— is the source of truth for the model and endpoint.

This module exists so ui-pro can *reflect* the user's Hermes configuration
instead of clobbering it with a stale hardcoded default. It is strictly
read-only: it never writes settings or config files, and it never triggers any
network or GPU activity.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# The value that used to ship as the hardcoded default for
# ``hermes_llm_model``. It is a bogus/legacy value, so any configuration still
# carrying it verbatim is treated as "unset" and falls through to the real
# Hermes config.
LEGACY_DEFAULT_MODEL = "google/gemma-4-12b-qat"


def _candidate_paths() -> list[Path]:
    """Candidate ``config.yaml`` locations for the Hermes agent.

    An explicit ``HERMES_HOME`` is authoritative: when set, only its
    ``config.yaml`` is considered (matching the Hermes CLI, which lets
    ``HERMES_HOME`` replace the default home dir). Otherwise the platform
    default is used (``%LOCALAPPDATA%\\hermes`` on Windows,
    ``$XDG_CONFIG_HOME/hermes`` or ``~/.config/hermes`` / ``~/.hermes``
    elsewhere).
    """
    env_home = os.environ.get("HERMES_HOME")
    if env_home:
        return [Path(env_home) / "config.yaml"]

    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        return [Path(local) / "hermes" / "config.yaml"] if local else []

    candidates: list[Path] = []
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        candidates.append(Path(xdg) / "hermes" / "config.yaml")
    candidates.append(Path.home() / ".config" / "hermes" / "config.yaml")
    candidates.append(Path.home() / ".hermes" / "config.yaml")
    return candidates


def hermes_config_path() -> Path | None:
    """Return the first existing Hermes ``config.yaml``, or ``None``."""
    for candidate in _candidate_paths():
        try:
            if candidate.is_file():
                return candidate
        except OSError:  # pragma: no cover - defensive against odd paths
            continue
    return None


def read_hermes_agent_config() -> dict[str, str]:
    """Read the real Hermes agent model configuration.

    Returns a subset of ``{"model", "base_url", "provider"}`` (only the keys
    that are present and non-empty), or ``{}`` when the file is missing,
    malformed, or does not carry a ``model`` mapping. Never raises.
    """
    path = hermes_config_path()
    if path is None:
        return {}

    try:
        import yaml  # optional-ish: project declares pyyaml>=6
    except ImportError:  # pragma: no cover - pyyaml is a declared dependency
        logger.debug("PyYAML unavailable; cannot read Hermes config %s", path)
        return {}

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - read is best-effort/report-only
        logger.debug("Failed to read Hermes config %s: %s", path, exc)
        return {}

    if not isinstance(raw, dict):
        return {}

    model_cfg = raw.get("model")
    if not isinstance(model_cfg, dict):
        return {}

    result: dict[str, str] = {}
    for source_key, target_key in (
        ("default", "model"),
        ("base_url", "base_url"),
        ("provider", "provider"),
    ):
        value = model_cfg.get(source_key)
        if isinstance(value, str) and value.strip():
            result[target_key] = value.strip()
    return result


def resolve_effective_hermes_llm(settings: Any) -> tuple[str, str]:
    """Resolve the effective ``(model, base_url)`` for the Hermes agent.

    Precedence: an explicit ui-pro override (non-empty) wins; otherwise the
    real Hermes agent ``config.yaml`` is used; otherwise ``("", "")`` — there is
    intentionally no hardcoded fallback model.

    The legacy sentinel ``LEGACY_DEFAULT_MODEL`` is treated as "unset" (only
    when no base URL was also configured) so a stale ``.env`` value does not
    mask the user's real Hermes config.
    """
    ui_model = (getattr(settings, "hermes_llm_model", "") or "").strip()
    ui_base = (getattr(settings, "hermes_llm_base_url", "") or "").strip()

    if ui_model == LEGACY_DEFAULT_MODEL and not ui_base:
        ui_model = ""

    if ui_model or ui_base:
        return ui_model, ui_base

    real = read_hermes_agent_config()
    return real.get("model", ""), real.get("base_url", "")


__all__ = [
    "LEGACY_DEFAULT_MODEL",
    "hermes_config_path",
    "read_hermes_agent_config",
    "resolve_effective_hermes_llm",
]
