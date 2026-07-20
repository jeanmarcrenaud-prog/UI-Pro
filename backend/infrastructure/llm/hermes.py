"""Hermes Agent-specific backend client.

Connects through the Open Design daemon for chat streaming (same
SSE protocol as OpenDesignBackend) but always routes to the
Hermes agent.  Health checks include a Hermes-specific probe
via the daemon's agent list.

Future: when Hermes exposes a direct ACP TCP server
(``hermes acp``), this backend can be extended with a direct
transport that bypasses the daemon.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.infrastructure.llm.base import LLMBackend
from backend.infrastructure.llm.opendesign import OpenDesignBackend

logger = logging.getLogger(__name__)


class HermesBackend(OpenDesignBackend):
    """Client for Hermes Agent channelled through the Open Design daemon.

    Uses the same ``/api/chat`` SSE endpoint as :class:`OpenDesignBackend`
    but hard-codes the ``agentId`` to ``"hermes"`` so the user does not
    have to select an agent.  Model discovery returns the Hermes agent
    entry together with any models it exposes.

    .. rubric:: Inheritance notes

    * ``generate``, ``stream``, ``astream`` – inherited unchanged from
      :class:`OpenDesignBackend`.
    * ``_dispatch_sse`` – inherited unchanged.
    * ``_chat_payload`` – overridden to set ``agentId="hermes"``.
    * ``list_models`` – overridden to return Hermes-specific model metadata.
    * ``health_check`` – overridden to include Hermes-specific diagnostics.
    """

    backend_name = "hermes"

    # ── Payload builders ──────────────────────────────────────────

    def _chat_payload(self, prompt: str, **kwargs: object) -> dict[str, Any]:
        return {
            "agentId": "hermes",
            "message": prompt,
            "systemPrompt": kwargs.get("system_prompt", ""),
        }

    # ── Discovery & health ────────────────────────────────────────

    def list_models(self) -> list[dict[str, Any]]:
        """List Hermes-specific models from the Open Design daemon.

        GET /api/agents → locate the ``hermes`` agent entry and return
        its ``models`` list, falling back to a single ``"hermes"`` entry
        when the daemon does not supply a model list.
        """
        url = f"{self._base_url()}/api/agents"
        try:
            resp = self._request("GET", url)
            data = resp.json()
            agents: list[dict[str, Any]] = data.get("agents", [])
            hermes_agent = next(
                (a for a in agents if a.get("id") == "hermes"), None
            )
            if hermes_agent:
                models = hermes_agent.get("models", [])
                if models:
                    # Models can be strings or dicts with an "id" key
                    return [
                        {"name": m} if isinstance(m, str) else {"name": m.get("id", "")}
                        for m in models
                    ]
            # Fallback: daemon knows about Hermes but no model list
            if hermes_agent:
                return [{"name": "hermes", "available": hermes_agent.get("available", False)}]
        except Exception as e:
            logger.debug("Hermes model listing failed: %s", e)
        return [{"name": "hermes"}]

    def health_check(self) -> dict[str, Any]:
        """Probe the Open Design daemon and include Hermes agent status."""
        url = f"{self._base_url()}/api/agents"
        result = self._measure("GET", url, timeout=min(self.config.timeout, 5))
        result["model"] = self.config.model

        if result["status"] == "ok":
            try:
                models = self.list_models()
                result["available_models"] = [m["name"] for m in models[:5]]
            except Exception:
                pass
        return result


__all__ = ["HermesBackend"]
