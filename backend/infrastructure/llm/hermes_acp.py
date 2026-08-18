"""Hermes ACP backend — direct stdio transport to ``hermes acp`` + optional pool.

Bypasses the Open Design daemon entirely by speaking the Agent Client
Protocol (ACP) JSON-RPC 2.0 over the stdio streams of the ``hermes acp``
subprocess.

Two execution paths:

* **Oneshot** (sync ``generate``/``stream``, invoked via ``asyncio.run``
  from an executor thread): spawn → initialize → new_session → prompt →
  close_session → teardown.  No shared event loop, no pool.
* **Pooled** (async ``astream``, invoked from the main event loop — the
  LangGraph bridge path): the subprocess + initialize are reused across
  prompts.  Each prompt still gets a fresh ACP session
  (new_session → prompt → close_session).  Connections are keyed by
  ``(command, cwd)``, bounded by ``hermes_acp_pool_size``, evicted after
  ``hermes_acp_pool_idle_ttl`` seconds, and discarded on error.

The ``agent-client-protocol`` package (>=0.12.0) is an optional dependency.
If it is not installed the backend is simply not registered by the factory.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from collections.abc import AsyncGenerator, Iterator
from dataclasses import dataclass, field
from typing import Any, Callable

from backend.infrastructure.llm.base import LLMBackend
from backend.infrastructure.llm.errors import (
    LLMBackendError,
    LLMConnectionError,
)
from backend.infrastructure.llm.models import ModelConfig

logger = logging.getLogger(__name__)

# The acp package is an optional dependency — import lazily so the rest of
# the backend module remains importable when acp is not installed.
try:
    from acp import (
        PROTOCOL_VERSION,
        RequestError,
        connect_to_agent,
        spawn_stdio_transport,
        text_block,
    )
    from acp.schema import (
        AgentMessageChunk,
        AllowedOutcome,
        ClientCapabilities,
        DeniedOutcome,
        Implementation,
        InitializeResponse,
        NewSessionResponse,
        RequestPermissionResponse,
        TextContentBlock,
    )
    from acp.core import ClientSideConnection

    _ACP_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when acp is absent
    _ACP_AVAILABLE = False


class _HermesACPClient:
    """Minimal ``acp.Client`` implementation for UI-Pro.

    The client receives streaming updates (text deltas) from the agent via
    ``session_update`` and pushes them onto an ``asyncio.Queue`` that the
    backend's ``astream`` coroutine drains.  Permission requests are
    auto-approved (first option) so the agent can proceed without a human
    in the loop.  File-system and terminal operations are not supported in
    this transport and raise ``RequestError`` so the agent can report the
    failure gracefully.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._session_id: str | None = None

    def reset_queue(self) -> None:
        """Drop leftover deltas between pooled uses."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    # ── Streaming ────────────────────────────────────────────────────

    async def session_update(
        self,
        session_id: str,
        update: Any,
        **kwargs: Any,
    ) -> None:
        """Receive session updates from the agent.

        Only ``AgentMessageChunk`` instances carrying a ``TextContentBlock``
        produce text deltas — everything else (tool calls, thoughts, usage)
        is silently ignored for now.
        """
        if not isinstance(update, AgentMessageChunk):
            return
        content = update.content
        if isinstance(content, TextContentBlock) and content.text:
            await self._queue.put(content.text)

    # ── Permissions ──────────────────────────────────────────────────

    async def request_permission(
        self,
        options: list[Any],
        session_id: str,
        tool_call: Any,
        **kwargs: Any,
    ) -> RequestPermissionResponse:
        """Auto-approve the first permission option (no human in the loop)."""
        if options:
            return RequestPermissionResponse(
                outcome=AllowedOutcome(
                    option_id=options[0].option_id, outcome="selected"
                )
            )
        # No options offered — deny gracefully.
        return RequestPermissionResponse(
            outcome=DeniedOutcome(outcome="cancelled")
        )

    # ── Unsupported client methods ───────────────────────────────────

    async def write_text_file(
        self, content: str, path: str, session_id: str, **kwargs: Any
    ) -> Any:
        raise RequestError(
            -32601, "write_text_file not supported by UI-Pro ACP client"
        )

    async def read_text_file(
        self, path: str, session_id: str,
        limit: int | None = None, line: int | None = None, **kwargs: Any,
    ) -> Any:
        raise RequestError(
            -32601, "read_text_file not supported by UI-Pro ACP client"
        )

    async def create_terminal(
        self, command: str, session_id: str,
        args: list[str] | None = None, cwd: str | None = None,
        env: list[Any] | None = None,
        output_byte_limit: int | None = None, **kwargs: Any,
    ) -> Any:
        raise RequestError(
            -32601, "create_terminal not supported by UI-Pro ACP client"
        )

    async def terminal_output(
        self, session_id: str, terminal_id: str, **kwargs: Any
    ) -> Any:
        raise RequestError(
            -32601, "terminal_output not supported by UI-Pro ACP client"
        )

    async def release_terminal(
        self, session_id: str, terminal_id: str, **kwargs: Any
    ) -> Any:
        raise RequestError(
            -32601, "release_terminal not supported by UI-Pro ACP client"
        )

    async def wait_for_terminal_exit(
        self, session_id: str, terminal_id: str, **kwargs: Any
    ) -> Any:
        raise RequestError(
            -32601, "wait_for_terminal_exit not supported by UI-Pro ACP client"
        )

    async def kill_terminal(
        self, session_id: str, terminal_id: str, **kwargs: Any
    ) -> Any:
        raise RequestError(
            -32601, "kill_terminal not supported by UI-Pro ACP client"
        )

    async def ext_method(
        self, method: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        raise RequestError(
            -32601, f"ext_method '{method}' not supported by UI-Pro ACP client"
        )

    async def ext_notification(
        self, method: str, params: dict[str, Any]
    ) -> None:
        raise RequestError(
            -32601, f"ext_notification '{method}' not supported by UI-Pro ACP client"
        )

    def on_connect(self, conn: Any) -> None:
        """Called when the connection is established — no-op."""
        pass


# ── Pooled connection ────────────────────────────────────────────────


@dataclass
class _PooledConnection:
    """One live ``hermes acp`` subprocess + ACP connection.

    ``transport_cm`` is the async context manager from
    ``spawn_stdio_transport``; it is entered once at spawn time and only
    exited (which terminates the subprocess) when the connection is
    destroyed.  ``release`` without ``discard`` keeps it alive for reuse.
    """

    command: str
    cwd: str
    client: _HermesACPClient
    conn: Any  # ClientSideConnection
    transport_cm: Any
    process: Any
    created_at: float = field(default_factory=time.monotonic)
    last_used: float = field(default_factory=time.monotonic)
    in_use: bool = False
    prompt_count: int = 0
    healthy: bool = True

    def touch(self) -> None:
        self.last_used = time.monotonic()

    def idle_for(self) -> float:
        return time.monotonic() - self.last_used


class HermesACPConnectionPool:
    """Process-level pool: keep ``hermes acp`` alive across prompts.

    Keyed by ``(command, cwd)``.  Designed for a single asyncio event loop
    (the app's main loop); the sync ``asyncio.run`` paths never touch it.
    """

    def __init__(
        self,
        *,
        max_size: int = 2,
        idle_ttl: float = 120.0,
        settings_provider: Callable[[], Any] | None = None,
    ) -> None:
        self._max_size = max(1, max_size)
        self._idle_ttl = max(1.0, idle_ttl)
        self._settings_provider = settings_provider
        self._lock = asyncio.Lock()
        self._closed = False
        # key -> list of connections
        self._buckets: dict[tuple[str, str], list[_PooledConnection]] = {}
        # Metrics: hit/miss/discard counters + latency averages.
        self._hits = 0
        self._misses = 0
        self._discards = 0
        self._spawn_ms_total = 0.0
        self._spawn_count = 0
        self._acquire_ms_total = 0.0
        self._acquire_count = 0

    def _current_max_size(self) -> int:
        """Live pool size from settings (falls back to the static value)."""
        if self._settings_provider is not None:
            try:
                s = self._settings_provider()
                return max(1, int(getattr(s, "hermes_acp_pool_size", self._max_size)))
            except Exception:
                pass
        return self._max_size

    def _current_idle_ttl(self) -> float:
        """Live idle TTL from settings (falls back to the static value)."""
        if self._settings_provider is not None:
            try:
                s = self._settings_provider()
                return max(
                    1.0, float(getattr(s, "hermes_acp_pool_idle_ttl", self._idle_ttl))
                )
            except Exception:
                pass
        return self._idle_ttl

    def _current_handshake_timeout(self) -> float:
        """Live handshake timeout from settings (falls back to 30s)."""
        if self._settings_provider is not None:
            try:
                s = self._settings_provider()
                return max(
                    1.0,
                    float(getattr(s, "hermes_acp_handshake_timeout", 30.0)),
                )
            except Exception:
                pass
        return 30.0

    def _record_acquire(self, start: float) -> None:
        """Accumulate acquire latency (hit or miss) for the stats average."""
        self._acquire_ms_total += (time.monotonic() - start) * 1000.0
        self._acquire_count += 1
    def stats(self) -> dict[str, Any]:
        total = busy = idle = 0
        for conns in self._buckets.values():
            for c in conns:
                total += 1
                if c.in_use:
                    busy += 1
                else:
                    idle += 1
        return {
            "connections": total,
            "busy": busy,
            "idle": idle,
            "buckets": len(self._buckets),
            "max_size": self._current_max_size(),
            "idle_ttl": self._current_idle_ttl(),
            "hits": self._hits,
            "misses": self._misses,
            "discards": self._discards,
            "spawn_ms_avg": (
                round(self._spawn_ms_total / self._spawn_count, 1)
                if self._spawn_count
                else 0.0
            ),
            "acquire_wait_ms_avg": (
                round(self._acquire_ms_total / self._acquire_count, 1)
                if self._acquire_count
                else 0.0
            ),
        }

    async def acquire(self, command: str, cwd: str) -> _PooledConnection:
        key = (command, cwd)
        start = time.monotonic()
        async with self._lock:
            await self._evict_locked(key)
            bucket = self._buckets.setdefault(key, [])

            # Drop connections whose subprocess already exited (dead process).
            dead = [
                c
                for c in bucket
                if not c.in_use
                and getattr(c.process, "returncode", None) is not None
            ]
            for c in dead:
                bucket.remove(c)
                await self._destroy(c)

            for conn in bucket:
                if not conn.in_use and conn.healthy:
                    conn.in_use = True
                    conn.client.reset_queue()
                    conn.touch()
                    self._hits += 1
                    self._record_acquire(start)
                    logger.debug(
                        "ACP pool hit command=%s cwd=%s prompts=%s",
                        command, cwd, conn.prompt_count,
                    )
                    return conn

            if len(bucket) >= self._current_max_size():
                # At capacity: evict the oldest idle connection to make room.
                # If everything is busy we still spawn (no queueing) so
                # concurrency is never blocked — the bucket may temporarily
                # exceed max_size under peak load.
                idle = [c for c in bucket if not c.in_use]
                if idle:
                    victim = min(idle, key=lambda c: c.last_used)
                    bucket.remove(victim)
                    await self._destroy(victim)

        # Spawn outside the lock: subprocess start + initialize round-trip
        # can take hundreds of ms and must not block other acquires.
        conn = await self._spawn(command, cwd)

        async with self._lock:
            if self._closed:
                await self._destroy(conn)
                raise LLMBackendError("ACP pool is closed")
            conn.in_use = True
            self._buckets.setdefault(key, []).append(conn)
            self._misses += 1
            self._record_acquire(start)
            logger.debug("ACP pool miss — spawned command=%s cwd=%s", command, cwd)
            return conn

    async def release(self, conn: _PooledConnection, *, discard: bool = False) -> None:
        async with self._lock:
            conn.in_use = False
            conn.touch()
            if discard or not conn.healthy:
                key = (conn.command, conn.cwd)
                bucket = self._buckets.get(key, [])
                if conn in bucket:
                    bucket.remove(conn)
                await self._destroy(conn)
                self._discards += 1
                return
            conn.client.reset_queue()

    async def close_all(self) -> None:
        async with self._lock:
            self._closed = True
            for bucket in list(self._buckets.values()):
                for conn in list(bucket):
                    await self._destroy(conn)
            self._buckets.clear()

    async def _evict_locked(self, key: tuple[str, str]) -> None:
        bucket = self._buckets.get(key, [])
        keep: list[_PooledConnection] = []
        for conn in bucket:
            if (
                not conn.in_use
                and (conn.idle_for() > self._current_idle_ttl() or not conn.healthy)
            ):
                await self._destroy(conn)
            else:
                keep.append(conn)
        self._buckets[key] = keep

    async def _spawn(self, command: str, cwd: str) -> _PooledConnection:
        if not _ACP_AVAILABLE:
            raise LLMBackendError("agent-client-protocol is not installed")

        start = time.monotonic()
        handshake = self._current_handshake_timeout()
        client = _HermesACPClient()
        cm = spawn_stdio_transport(
            command,
            "acp",
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        try:
            async with asyncio.timeout(handshake):
                try:
                    reader, writer, process = await cm.__aenter__()
                except TimeoutError:
                    raise
                except Exception as e:
                    raise LLMConnectionError(
                        f"hermes acp spawn failed: {e}"
                    ) from e
                conn = connect_to_agent(client, writer, reader)
                try:
                    await conn.initialize(
                        PROTOCOL_VERSION,
                        ClientCapabilities(),
                        Implementation(
                            name="ui-pro", title="UI-Pro", version="1.0.0"
                        ),
                    )
                except TimeoutError:
                    raise
                except Exception as e:
                    raise LLMConnectionError(
                        f"hermes acp initialize failed: {e}"
                    ) from e
        except TimeoutError as e:
            try:
                await cm.__aexit__(None, None, None)
            except Exception:
                pass
            raise LLMConnectionError(
                f"hermes acp handshake timed out after {handshake}s"
            ) from e
        except Exception:
            # Non-timeout failure: tear down the transport before propagating.
            try:
                await cm.__aexit__(None, None, None)
            except Exception:
                pass
            raise

        self._spawn_ms_total += (time.monotonic() - start) * 1000.0
        self._spawn_count += 1
        return _PooledConnection(
            command=command,
            cwd=cwd,
            client=client,
            conn=conn,
            transport_cm=cm,
            process=process,
        )

    async def _destroy(self, conn: _PooledConnection) -> None:
        conn.healthy = False
        try:
            await conn.transport_cm.__aexit__(None, None, None)
        except Exception:
            logger.debug("ACP transport teardown failed", exc_info=True)
        logger.debug(
            "ACP connection destroyed command=%s prompts=%s",
            conn.command, conn.prompt_count,
        )


# Module-level pool (one per process; safe for the app's single event loop).
_pool: HermesACPConnectionPool | None = None


def get_acp_pool() -> HermesACPConnectionPool:
    """Get the process-wide pool, creating it from settings on first use."""
    global _pool
    if _pool is None:
        try:
            from backend.domain.settings import settings

            _pool = HermesACPConnectionPool(
                max_size=int(getattr(settings, "hermes_acp_pool_size", 2)),
                idle_ttl=float(getattr(settings, "hermes_acp_pool_idle_ttl", 120.0)),
                settings_provider=lambda: settings,
            )
        except Exception:
            _pool = HermesACPConnectionPool()
    return _pool


def reset_acp_pool_for_tests() -> None:
    """Drop the singleton (tests only)."""
    global _pool
    _pool = None


async def close_acp_pool() -> None:
    """Close the pool if it was ever created (app shutdown hook)."""
    global _pool
    if _pool is not None:
        await _pool.close_all()
        _pool = None


# ── Backend ──────────────────────────────────────────────────────────


class HermesACPBackend(LLMBackend):
    """Direct ACP transport to the Hermes agent via ``hermes acp`` (stdio).

    Unlike :class:`HermesBackend` (which routes through the Open Design
    daemon's SSE endpoint), this backend spawns ``hermes acp`` as a
    subprocess and speaks ACP JSON-RPC 2.0 directly over its stdin/stdout.
    """

    backend_name = "hermes_acp"

    def __init__(self, config: ModelConfig) -> None:
        super().__init__(config)
        if not _ACP_AVAILABLE:
            raise LLMBackendError(
                "agent-client-protocol package is not installed. "
                "Run: pip install agent-client-protocol>=0.12.0"
            )
        self._command = self._resolve_command()
        self._last_client: _HermesACPClient | None = None

    # ── Configuration ────────────────────────────────────────────────

    def _resolve_command(self) -> str:
        """Resolve the ``hermes acp`` executable path.

        Priority:
        1. ``config.url`` (if set to a non-empty path)
        2. ``settings.hermes_acp_command`` (env ``HERMES_ACP_COMMAND``)
        3. ``"hermes"`` (on PATH)
        """
        if self.config.url:
            return self.config.url
        try:
            from backend.domain.settings import settings

            return settings.hermes_acp_command
        except Exception:
            return "hermes"

    def _pool_enabled(self) -> bool:
        """Whether the async path should use the connection pool."""
        try:
            from backend.domain.settings import settings

            return bool(getattr(settings, "hermes_acp_pool_enabled", True))
        except Exception:
            return True

    def _prompt_timeout(self) -> float:
        """Operation deadline for a full ACP turn.

        Priority: explicit ``hermes_acp_prompt_timeout`` (>0) →
        ``config.timeout`` → ``settings.llm_timeout``.
        """
        try:
            from backend.domain.settings import settings

            explicit = float(getattr(settings, "hermes_acp_prompt_timeout", 0.0))
            if explicit > 0:
                return explicit
        except Exception:
            pass
        if self.config.timeout and self.config.timeout > 0:
            return float(self.config.timeout)
        try:
            from backend.domain.settings import settings

            return float(settings.llm_timeout)
        except Exception:
            return 900.0

    def _handshake_timeout(self) -> float:
        """Handshake deadline for spawn+initialize (settings, default 30s)."""
        try:
            from backend.domain.settings import settings

            return float(getattr(settings, "hermes_acp_handshake_timeout", 30.0))
        except Exception:
            return 30.0

    # ── Async core (oneshot) ─────────────────────────────────────────

    async def _run_acp_oneshot(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Spawn ``hermes acp``, send *prompt*, yield text deltas.

        Lifecycle: spawn → initialize → new_session → prompt → close_session.
        The connection is torn down automatically by the ``async with`` on
        ``spawn_stdio_transport``.  The whole turn is bounded by the
        operation timeout (config.timeout / llm_timeout).
        """
        client = _HermesACPClient()
        self._last_client = client  # exposed for testing
        cwd = kwargs.get("cwd") or os.getcwd()
        timeout = self._prompt_timeout()

        try:
            async with asyncio.timeout(timeout):
                async with spawn_stdio_transport(
                    self._command,
                    "acp",
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                ) as (reader, writer, process):
                    # connect_to_agent: input_stream = writer (agent stdin),
                    # output_stream = reader (agent stdout).
                    conn: ClientSideConnection = connect_to_agent(
                        client, writer, reader
                    )

                    try:
                        await conn.initialize(
                            PROTOCOL_VERSION,
                            ClientCapabilities(),
                            Implementation(
                                name="ui-pro", title="UI-Pro", version="1.0.0"
                            ),
                        )
                    except RequestError as e:
                        raise LLMConnectionError(
                            f"hermes acp initialize failed: {e}"
                        ) from e

                    try:
                        resp: NewSessionResponse = await conn.new_session(cwd=cwd)
                    except RequestError as e:
                        raise LLMConnectionError(
                            f"hermes acp new_session failed: {e}"
                        ) from e

                    session_id = resp.session_id
                    client._session_id = session_id
                    message_id = str(uuid.uuid4())

                    prompt_task = asyncio.create_task(
                        conn.prompt([text_block(prompt)], session_id, message_id)  # type: ignore[arg-type]
                    )

                    # Drain the queue as text deltas arrive, racing against the
                    # prompt task which completes when the agent finishes its turn.
                    try:
                        while True:
                            get_task = asyncio.create_task(client._queue.get())
                            done, _ = await asyncio.wait(
                                {prompt_task, get_task},
                                return_when=asyncio.FIRST_COMPLETED,
                            )
                            if get_task in done:
                                text = get_task.result()
                                if text:
                                    yield text
                            else:
                                get_task.cancel()
                                await asyncio.gather(get_task, return_exceptions=True)
                            if prompt_task in done:
                                # Drain any remaining queued text before exiting.
                                while not client._queue.empty():
                                    text = client._queue.get_nowait()
                                    if text:
                                        yield text
                                break
                        # Propagate any exception raised by the agent.
                        await prompt_task
                    finally:
                        try:
                            await asyncio.wait_for(
                                conn.close_session(session_id), timeout=5.0
                            )
                        except Exception:
                            logger.debug(
                                "close_session failed during cleanup",
                                exc_info=True,
                            )
        except TimeoutError as e:
            logger.warning("ACP oneshot prompt timed out after %ss", timeout)
            raise LLMConnectionError(
                f"hermes acp prompt timed out after {timeout}s"
            ) from e

    # ── Async core (pooled) ──────────────────────────────────────────

    async def _prompt_on_connection(
        self,
        pooled: _PooledConnection,
        prompt: str,
    ) -> AsyncGenerator[str, None]:
        """new_session → prompt → drain queue → close_session on a live conn."""
        client = pooled.client
        conn = pooled.conn
        self._last_client = client
        client.reset_queue()

        try:
            resp: NewSessionResponse = await conn.new_session(cwd=pooled.cwd)
        except Exception as e:
            pooled.healthy = False
            raise LLMConnectionError(f"hermes acp new_session failed: {e}") from e

        session_id = resp.session_id
        client._session_id = session_id
        message_id = str(uuid.uuid4())
        pooled.prompt_count += 1

        prompt_task = asyncio.create_task(
            conn.prompt([text_block(prompt)], session_id, message_id)  # type: ignore[arg-type]
        )

        try:
            while True:
                get_task = asyncio.create_task(client._queue.get())
                done, _ = await asyncio.wait(
                    {prompt_task, get_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if get_task in done:
                    text = get_task.result()
                    if text:
                        yield text
                else:
                    get_task.cancel()
                    await asyncio.gather(get_task, return_exceptions=True)
                if prompt_task in done:
                    while not client._queue.empty():
                        text = client._queue.get_nowait()
                        if text:
                            yield text
                    break
            await prompt_task
        except Exception:
            pooled.healthy = False
            raise
        finally:
            try:
                await asyncio.wait_for(
                    conn.close_session(session_id), timeout=5.0
                )
            except Exception:
                logger.debug("close_session failed during cleanup", exc_info=True)

    async def _run_acp_pooled(
        self, prompt: str, cwd: str
    ) -> AsyncGenerator[str, None]:
        pool = get_acp_pool()
        pooled = await pool.acquire(self._command, cwd)
        ok = False
        try:
            timeout = self._prompt_timeout()
            async with asyncio.timeout(timeout):
                async for chunk in self._prompt_on_connection(pooled, prompt):
                    yield chunk
            ok = True
        except TimeoutError as e:
            pooled.healthy = False
            logger.warning(
                "ACP prompt timed out after %ss (discarding conn)", timeout
            )
            raise LLMConnectionError(
                f"hermes acp prompt timed out after {timeout}s"
            ) from e
        finally:
            await pool.release(pooled, discard=not ok)

    async def _generate_async(
        self, prompt: str, **kwargs: Any
    ) -> str:
        """Collect the full response from the oneshot path (sync context)."""
        chunks: list[str] = []
        async for chunk in self._run_acp_oneshot(prompt, **kwargs):
            chunks.append(chunk)
        return "".join(chunks)

    # ── Public API (LLMBackend interface) ────────────────────────────

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Synchronous generation — full response as a single string.

        Uses ``asyncio.run`` because this method is invoked via
        ``run_in_executor`` (a thread with no running event loop).
        Always uses the oneshot path — no pooled connection.
        """
        try:
            return asyncio.run(self._generate_async(prompt, **kwargs))
        except LLMBackendError:
            raise
        except Exception as e:
            raise LLMConnectionError(
                f"hermes acp generate failed: {e}"
            ) from e

    def stream(self, prompt: str, **kwargs: Any) -> Iterator[str]:
        """Synchronous streaming — yields text tokens.

        Collects the async stream via ``asyncio.run`` and yields chunks
        synchronously.  Always uses the oneshot path — no pooled connection.
        """
        try:
            async def _collect() -> list[str]:
                chunks: list[str] = []
                async for chunk in self._run_acp_oneshot(prompt, **kwargs):
                    chunks.append(chunk)
                return chunks

            chunks = asyncio.run(_collect())
            for chunk in chunks:
                yield chunk
        except LLMBackendError:
            raise
        except Exception as e:
            raise LLMConnectionError(
                f"hermes acp stream failed: {e}"
            ) from e

    async def astream(
        self, prompt: str, **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Asynchronous streaming — yields text tokens as they arrive.

        Uses the connection pool (if enabled) so the ``hermes acp``
        subprocess survives across prompts.  Falls back to the oneshot
        path when pooling is disabled.
        """
        if self._pool_enabled():
            cwd = kwargs.get("cwd") or os.getcwd()
            async for chunk in self._run_acp_pooled(prompt, cwd):
                yield chunk
        else:
            async for chunk in self._run_acp_oneshot(prompt, **kwargs):
                yield chunk

    def health_check(self) -> dict[str, Any]:
        """Probe the ``hermes acp`` subprocess via a full initialize round-trip.

        Always oneshot — never consumes or pollutes a pooled connection.
        """
        start = time.monotonic()
        try:
            async def _probe() -> InitializeResponse:
                async with spawn_stdio_transport(
                    self._command,
                    "acp",
                    stderr=asyncio.subprocess.PIPE,
                    cwd=os.getcwd(),
                ) as (reader, writer, process):
                    conn = connect_to_agent(
                        _HermesACPClient(), writer, reader
                    )
                    try:
                        return await conn.initialize(
                            PROTOCOL_VERSION,
                            ClientCapabilities(),
                            Implementation(
                                name="ui-pro",
                                title="UI-Pro",
                                version="1.0.0",
                            ),
                        )
                    finally:
                        await conn.close()

            resp = asyncio.run(
                asyncio.wait_for(
                    _probe(),
                    timeout=min(10.0, self._handshake_timeout()),
                )
            )
            ms = round((time.monotonic() - start) * 1000, 1)
            agent_info = resp.agent_info
            result: dict[str, Any] = {
                "status": "ok",
                "latency_ms": ms,
                "model": self.config.model or "hermes",
                "agent_name": agent_info.name if agent_info else "hermes",
                "agent_version": (
                    agent_info.version if agent_info else None
                ),
                "error": None,
            }
            if self._pool_enabled():
                result["pool"] = get_acp_pool().stats()
            return result
        except Exception as e:
            ms = round((time.monotonic() - start) * 1000, 1)
            return {
                "status": "error",
                "latency_ms": ms,
                "model": self.config.model or "hermes",
                "agent_name": None,
                "agent_version": None,
                "error": str(e),
            }

    def list_models(self) -> list[dict[str, Any]]:
        """Return the Hermes agent as a single model entry.

        The actual model is selected inside the Hermes agent itself, so
        from UI-Pro's perspective there is one "model": ``hermes``.
        """
        return [{"name": "hermes", "available": True}]


__all__ = [
    "HermesACPBackend",
    "HermesACPConnectionPool",
    "close_acp_pool",
    "get_acp_pool",
    "reset_acp_pool_for_tests",
]
