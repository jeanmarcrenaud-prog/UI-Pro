# services/memory_service.py - Unified Memory Service
#
# Role: Source of truth for rich metadata
# - FAISS vector search (delegated to MemoryManager)
# - Rich metadata with UUID-based entries (_entries)
# - Context building with token budget
# - Session management
#
# IMPORTANT: MemoryManager is now a pure vector store (no metadata).
# MemoryService manages _entries as the source of truth.

import asyncio
import hashlib
import logging
import pickle
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from models.settings import settings

from .base import BaseService, ServiceMetrics

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """Memory entry with stable identity."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: str | None = None
    task_type: str | None = None
    importance: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "task_type": self.task_type,
            "importance": self.importance,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryEntry":
        data = data.copy()
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class ContextBuilder:
    """Token-aware context assembler."""

    def __init__(self, max_tokens: int = 4096):
        self.max_tokens = max_tokens

    @staticmethod
    def estimate_tokens(text: str) -> int:
        return len(text) // 4

    def fit(self, texts: list[str], max_tokens: int | None = None) -> list[str]:
        max_t = max_tokens or self.max_tokens
        result = []
        total = 0

        for text in texts:
            tokens = self.estimate_tokens(text)
            if total + tokens > max_t:
                break
            result.append(text)
            total += tokens

        return result


class MemoryService(BaseService):
    """Source of truth for rich metadata.

    MemoryManager is a pure vector store (no metadata persistence).
    This class manages _entries as the source of truth.
    """

    def __init__(
        self,
        persist_path: str | None = None,
        max_tokens: int = 4096,
    ):
        super().__init__("MemoryService")

        self.persist_path = persist_path or str(settings.workspace_path / "memory")
        self.max_tokens = max_tokens

        self._lock = threading.RLock()

        # Core storage - SOURCE OF TRUTH
        self._vector_store = None
        self._entries: dict[str, MemoryEntry] = {}  # Rich metadata source of truth
        self._text_to_id: dict[str, str] = {}  # text hash -> entry id
        self._session_index: dict[str, list[str]] = defaultdict(list)

        # Vector ID tracking (for sync with MemoryManager)
        self._entry_to_vector_id: dict[str, int] = {}  # entry id -> vector id

        self.context_builder = ContextBuilder(max_tokens=max_tokens)
        self._service_metrics = ServiceMetrics()

        self._entries_path = Path(self.persist_path) / "memory_entries.pkl"

    # ====================== LIFECYCLE ======================

    async def initialize(self) -> None:
        """Initialize vector store and load persisted data."""
        try:
            # Lazy import to avoid circular dependencies
            from backend.infrastructure.memory import MemoryManager

            self._vector_store = MemoryManager(
                persist_path=str(Path(self.persist_path) / "faiss_index"),
                max_memories=2000,
            )

            await self._load_entries()

            # Sync vector store with entries if needed
            await self._sync_vector_store()

            logger.info(f"MemoryService initialized — {len(self._entries)} entries")

        except Exception as e:
            logger.error(f"MemoryService initialization failed: {e}")
            self._set_error(str(e))
            raise

    async def _load_entries(self) -> None:
        """Load persisted entries."""
        if not self._entries_path.exists():
            return

        try:
            with open(self._entries_path, "rb") as f:
                data = pickle.load(f)

            self._entries = {k: MemoryEntry.from_dict(v) for k, v in data.items()}

            # Rebuild indexes
            self._text_to_id.clear()
            self._session_index.clear()

            for entry in self._entries.values():
                text_hash = hashlib.sha256(entry.text.encode()).hexdigest()[:16]
                self._text_to_id[text_hash] = entry.id
                if entry.session_id:
                    self._session_index[entry.session_id].append(entry.id)

            logger.info(f"Loaded {len(self._entries)} memory entries from disk")
        except Exception as e:
            logger.warning(f"Failed to load memory entries: {e}")

    def _save_entries(self) -> None:
        """Persist entries to disk."""
        try:
            self._entries_path.parent.mkdir(parents=True, exist_ok=True)
            data = {k: v.to_dict() for k, v in self._entries.items()}

            with open(self._entries_path, "wb") as f:
                pickle.dump(data, f)
        except Exception as e:
            logger.error(f"Failed to save memory entries: {e}")

    async def _sync_vector_store(self) -> None:
        """Sync vector store with entries - rebuild if out of sync."""
        if not self._vector_store:
            return

        vector_count = self._vector_store.get_stats()["total_vectors"]
        entry_count = len(self._entries)

        if vector_count != entry_count:
            logger.warning(
                f"Vector store out of sync: {vector_count} vectors vs {entry_count} entries. Rebuilding..."
            )
            await self._rebuild_vector_store()

    async def _rebuild_vector_store(self) -> None:
        """Rebuild vector store from entries."""
        if not self._entries:
            return

        # Get embeddings for all entries
        from backend.infrastructure.memory import get_memory_manager

        mm = get_memory_manager()

        texts = list(self._entries.values())
        embeddings = mm.embed_many([e.text for e in texts])

        # Build arrays
        vectors = []
        ids = []
        for i, entry in enumerate(texts):
            vectors.append(embeddings[i])
            ids.append(i)

        vectors_arr = np.stack(vectors)
        ids_arr = np.ascontiguousarray(ids, dtype=np.int64)

        # Rebuild
        self._vector_store.rebuild_from_arrays(vectors_arr, ids_arr)

        # Update mapping
        self._entry_to_vector_id = {entry.id: i for i, entry in enumerate(texts)}

        logger.info(f"Rebuilt vector store with {len(self._entries)} vectors")

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        if self._vector_store:
            await asyncio.to_thread(self._vector_store.save)
        self._save_entries()
        logger.info("MemoryService shutdown completed")

    # ====================== CORE API ======================

    async def add(
        self,
        text: str,
        session_id: str | None = None,
        task_type: str | None = None,
        importance: float = 0.5,
        metadata: dict | None = None,
    ) -> str | None:
        """Add a new memory entry."""
        if not text or not text.strip():
            return None

        text = text.strip()

        with self._lock:
            try:
                # Deduplication using hash
                text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
                if text_hash in self._text_to_id:
                    entry_id = self._text_to_id[text_hash]
                    # Update importance if higher
                    if importance > self._entries[entry_id].importance:
                        self._entries[entry_id].importance = importance
                        logger.debug(
                            f"Updated importance of existing memory {entry_id}"
                        )
                    return entry_id

                entry = MemoryEntry(
                    text=text,
                    session_id=session_id,
                    task_type=task_type,
                    importance=importance,
                    metadata=metadata or {},
                )

                # Add to vector store (no metadata - MemoryManager is pure vector store)
                if self._vector_store:
                    vector_id = await asyncio.to_thread(
                        self._vector_store.add_text, text
                    )
                    self._entry_to_vector_id[entry.id] = vector_id

                self._entries[entry.id] = entry
                self._text_to_id[text_hash] = entry.id

                if session_id:
                    self._session_index[session_id].append(entry.id)

                self._service_metrics.record_call(0, success=True)
                return entry.id

            except Exception as e:
                self._service_metrics.record_call(0, success=False)
                logger.error(f"Failed to add memory: {e}")
                return None

    async def search(
        self,
        query: str,
        k: int = 5,
        session_id: str | None = None,
        task_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search with optional filters."""
        if not query or not query.strip() or not self._vector_store:
            return []

        try:
            vector_results = await asyncio.to_thread(
                self._vector_store.search, query, limit=k * 2
            )

            results = []
            for vr in vector_results:
                # Map vector ID back to entry
                vector_id = vr.get("id")
                if vector_id is None:
                    continue

                # Find entry by vector ID (reverse lookup)
                entry_id = None
                for eid, vid in self._entry_to_vector_id.items():
                    if vid == vector_id:
                        entry_id = eid
                        break

                if not entry_id:
                    continue

                entry = self._entries.get(entry_id)
                if not entry:
                    continue

                # Apply filters
                if session_id and entry.session_id != session_id:
                    continue
                if task_type and entry.task_type != task_type:
                    continue

                results.append(
                    {
                        "id": entry.id,
                        "text": entry.text,
                        "score": vr.get("score", 0.0),
                        "similarity": vr.get("similarity", 0.0),
                        "session_id": entry.session_id,
                        "task_type": entry.task_type,
                        "importance": entry.importance,
                        "timestamp": entry.timestamp.isoformat(),
                    }
                )

                if len(results) >= k:
                    break

            self._service_metrics.record_call(0, success=True)
            return results

        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            self._service_metrics.record_call(0, success=False)
            return []

    # ====================== CONTEXT ======================

    async def get_context(
        self,
        query: str,
        k: int = 5,
        session_id: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        results = await self.search(query, k=k, session_id=session_id)
        texts = [r["text"] for r in results]
        fitted = self.context_builder.fit(texts, max_tokens)
        return "\n\n---\n\n".join(fitted)

    async def get_session_context(
        self,
        session_id: str,
        max_tokens: int | None = None,
    ) -> str:
        if not session_id:
            return ""

        entry_ids = self._session_index.get(session_id, [])
        entries = [self._entries[eid] for eid in entry_ids if eid in self._entries]

        sorted_entries = sorted(
            entries, key=lambda e: (e.importance, e.timestamp), reverse=True
        )

        texts = [e.text for e in sorted_entries]
        fitted = self.context_builder.fit(texts, max_tokens)
        return "\n\n---\n\n".join(fitted)

    # ====================== UTILITIES ======================

    def count(self) -> int:
        return len(self._entries)

    def clear(self, session_id: str | None = None) -> None:
        with self._lock:
            if session_id:
                for eid in self._session_index.pop(session_id, []):
                    entry = self._entries.pop(eid, None)
                    if entry:
                        text_hash = hashlib.sha256(entry.text.encode()).hexdigest()[:16]
                        self._text_to_id.pop(text_hash, None)
                        self._entry_to_vector_id.pop(eid, None)
                logger.info(f"Cleared session {session_id}")
            else:
                self._entries.clear()
                self._text_to_id.clear()
                self._session_index.clear()
                self._entry_to_vector_id.clear()
                if self._vector_store:
                    self._vector_store.clear()
                logger.info("All memories cleared")

    def get_stats(self) -> dict[str, Any]:
        vector_stats = {}
        if self._vector_store and hasattr(self._vector_store, "get_stats"):
            try:
                vector_stats = self._vector_store.get_stats()
            except Exception:
                pass
        return {
            "total_entries": self.count(),
            "active_sessions": len(self._session_index),
            "max_tokens": self.max_tokens,
            "vector_store": vector_stats,
        }

    def get_metrics(self) -> dict[str, Any]:
        return {
            "service": "MemoryService",
            **self._service_metrics.to_dict(),
            **self.get_stats(),
        }


# ====================== SINGLETON ======================

_memory_service: MemoryService | None = None


def get_memory_service() -> MemoryService:
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service
