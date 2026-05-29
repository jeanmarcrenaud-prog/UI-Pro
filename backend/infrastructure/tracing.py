"""
LangSmith Tracing Configuration for LangGraph.

Reads settings from env / Settings, sets LangChain environment variables,
and provides helpers for LangGraph config with thread_id.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


def setup_langsmith_tracing() -> bool:
    """Configure LangSmith tracing for LangGraph.

    Returns True if tracing was enabled, False otherwise.
    """
    from backend.domain.settings import settings

    if not settings.langsmith_tracing:
        logger.info("LangSmith tracing disabled (langsmith_tracing=False)")
        return False

    api_key = settings.langsmith_api_key or os.getenv("LANGSMITH_API_KEY", "")
    if not api_key:
        logger.warning("LangSmith tracing enabled but no API key set. Tracing disabled.")
        return False

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith_endpoint
    os.environ["LANGCHAIN_API_KEY"] = api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project

    logger.info(
        "LangSmith tracing enabled — project: %s, endpoint: %s",
        settings.langsmith_project,
        settings.langsmith_endpoint,
    )
    return True


def get_tracing_config(session_id: str | None = None) -> dict:
    """Return the LangGraph config for tracing with a thread_id."""
    return {
        "configurable": {
            "thread_id": session_id
            or f"thread_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        }
    }
