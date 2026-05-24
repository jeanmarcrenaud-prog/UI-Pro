# backend/infrastructure/checkpointer.py
from __future__ import annotations

import logging
from pathlib import Path

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages LangGraph checkpoint lifecycle.

    Handles connection to the SQLite checkpoint store and periodic
    cleanup of old checkpoints to prevent disk bloat.
    """

    def __init__(self, settings, max_checkpoints_per_thread: int = 50):
        self.db_path = Path(settings.data_dir) / "checkpoints.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.saver: AsyncSqliteSaver | None = None
        self._max_per_thread = max_checkpoints_per_thread

    async def get_saver(self) -> AsyncSqliteSaver:
        """Get or create the async SQLite checkpoint saver."""
        if not self.saver:
            self.saver = AsyncSqliteSaver.from_conn_string(
                f"sqlite+aiosqlite:///{self.db_path}"
            )
        return self.saver

    async def cleanup_old_checkpoints(
        self, keep_per_thread: int | None = None
    ) -> int:
        """Remove old checkpoints beyond the retention limit per thread.

        Keeps the latest `keep_per_thread` checkpoints for each thread_id
        and deletes older ones along with their associated writes.

        Args:
            keep_per_thread: Number of latest checkpoints to keep.
                             Defaults to self._max_per_thread (50).

        Returns:
            Number of checkpoint rows deleted.
        """
        import aiosqlite

        keep = keep_per_thread or self._max_per_thread
        total_deleted = 0

        try:
            async with aiosqlite.connect(str(self.db_path)) as db:
                # Enable WAL mode for concurrent readers
                await db.execute("PRAGMA journal_mode=WAL")

                # Get all thread_ids
                cursor = await db.execute(
                    "SELECT DISTINCT thread_id FROM checkpoints"
                )
                threads = [row[0] for row in await cursor.fetchall()]

                for thread_id in threads:
                    # Find checkpoint_ids beyond the keep limit
                    cursor = await db.execute(
                        """
                        SELECT checkpoint_id FROM checkpoints
                        WHERE thread_id = ?
                        ORDER BY checkpoint_id DESC
                        LIMIT -1 OFFSET ?
                        """,
                        (thread_id, keep),
                    )
                    stale = [row[0] for row in await cursor.fetchall()]

                    if not stale:
                        continue

                    placeholders = ",".join("?" for _ in stale)
                    params = (thread_id, *stale)

                    # Delete associated writes first
                    await db.execute(
                        f"""
                        DELETE FROM writes
                        WHERE thread_id = ? AND checkpoint_id IN ({placeholders})
                        """,
                        params,
                    )

                    # Delete stale checkpoints
                    await db.execute(
                        f"""
                        DELETE FROM checkpoints
                        WHERE thread_id = ? AND checkpoint_id IN ({placeholders})
                        """,
                        params,
                    )

                    total_deleted += len(stale)

                await db.commit()

            if total_deleted:
                logger.info(
                    "[Checkpointer] Cleaned %d old checkpoints (%d per thread)",
                    total_deleted,
                    keep,
                )
        except Exception as e:
            logger.warning("[Checkpointer] Cleanup failed: %s", e)

        return total_deleted

    async def get_stats(self) -> dict:
        """Get checkpoint store statistics."""
        import aiosqlite

        try:
            async with aiosqlite.connect(str(self.db_path)) as db:
                cursor = await db.execute("SELECT COUNT(*) FROM checkpoints")
                total = (await cursor.fetchone())[0]

                cursor = await db.execute(
                    "SELECT COUNT(DISTINCT thread_id) FROM checkpoints"
                )
                threads = (await cursor.fetchone())[0]

                db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

                return {
                    "total_checkpoints": total,
                    "total_threads": threads,
                    "db_size_bytes": db_size,
                    "db_size_mb": round(db_size / (1024 * 1024), 2),
                }
        except Exception as e:
            logger.warning("[Checkpointer] Stats failed: %s", e)
            return {"total_checkpoints": 0, "total_threads": 0, "db_size_bytes": 0}
