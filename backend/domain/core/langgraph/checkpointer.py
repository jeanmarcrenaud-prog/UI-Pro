"""Checkpoint management with async SQLite."""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_checkpointer = None
_checkpointer_agen = None
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
            global _checkpointer, _checkpointer_agen, _checkpointer_ready
            if _checkpointer is None:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    # from_conn_string() is an async generator whose
                    # 'async with aiosqlite.connect(...)' owns the connection;
                    # keep the generator so close_checkpointer() can finalize
                    # it (closing the connection) via __aexit__.
                    agen = AsyncSqliteSaver.from_conn_string(str(db_path))
                    saver = loop.run_until_complete(agen.__aenter__())
                    _checkpointer = saver
                    _checkpointer_agen = agen
                    logger.info(f"Async SQLite checkpointing: {db_path}")
                except Exception as e:
                    logger.warning(f"Async SQLite checkpointing failed: {e}")
                    if loop is not None:
                        loop.close()

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


async def close_checkpointer() -> None:
    """Close the SQLite checkpointer connection, if one is open.

    The checkpointer is created through AsyncSqliteSaver.from_conn_string(),
    an async generator whose 'async with aiosqlite.connect(...)' owns the
    connection. Finalizing that generator with __aexit__ closes the
    connection and avoids a 'Task was destroyed' warning from the discarded
    generator. The connection is bound to the background thread's loop, so
    it is re-pointed at the current loop first (aiosqlite only uses it to
    schedule work on its own executor). The idle background loop is then
    closed. Resets the module state so a later _get_checkpointer() call
    creates a fresh saver. Best-effort: failures are logged, never raised.
    """
    global _checkpointer, _checkpointer_agen

    saver = _checkpointer
    agen = _checkpointer_agen
    _checkpointer = None
    _checkpointer_agen = None

    if saver is None and agen is None:
        return

    # The aiosqlite connection is bound to the loop it was created on (the
    # background thread's loop). aiosqlite uses conn._loop only to schedule
    # work on its own executor, so re-pointing it at the current loop lets
    # the close run here without a cross-loop error.
    conn = getattr(saver, "conn", None) if saver is not None else None
    if conn is not None:
        current_loop = asyncio.get_running_loop()
        if getattr(conn, "_loop", None) is not current_loop:
            conn._loop = current_loop

    try:
        if agen is not None:
            # Finalize the generator from from_conn_string(); its internal
            # 'async with aiosqlite.connect(...)' closes the connection.
            await agen.__aexit__(None, None, None)
        elif conn is not None:
            await conn.close()
    except Exception as e:
        logger.warning(f"Failed to close checkpointer: {e}")

    # The background thread that created the saver has exited, leaving an
    # idle loop behind. Close it to avoid an 'unclosed event loop' warning.
    owner_loop = getattr(saver, "loop", None) if saver is not None else None
    if owner_loop is not None:
        try:
            if not owner_loop.is_closed():
                owner_loop.close()
        except Exception:
            pass
