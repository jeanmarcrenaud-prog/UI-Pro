"""Checkpoint management with async SQLite."""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_checkpointer = None
_checkpointer_ready = threading.Event()


def _get_checkpointer():
    """Persistent checkpointing with async SQLite (properly initialized)."""
    global _checkpointer, _checkpointer_ready

    if _checkpointer is not None:
        return _checkpointer

    db_path = Path("data/checkpoints.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        def _init():
            global _checkpointer, _checkpointer_ready
            if _checkpointer is None:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    saver = loop.run_until_complete(
                        AsyncSqliteSaver.from_conn_string(str(db_path)).__aenter__()
                    )
                    _checkpointer = saver
                    logger.info(f"Async SQLite checkpointing: {db_path}")
                except Exception as e:
                    logger.warning(f"Async SQLite checkpointing failed: {e}")

        t = threading.Thread(target=_init, daemon=True)
        t.start()
        t.join(timeout=5)

        if _checkpointer is not None:
            return _checkpointer

    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: in-memory
    from langgraph.checkpoint.memory import MemorySaver
    _checkpointer = MemorySaver()
    logger.warning("SQLite checkpointing unavailable - using in-memory")
    return _checkpointer