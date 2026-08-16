"""Hermes ACP backend — direct stdio transport to ``hermes acp``.

Bypasses the Open Design daemon entirely by speaking the Agent Client
Protocol (ACP) JSON-RPC 2.0 over the stdio streams of the ``hermes acp``
subprocess.  Each call spawns a fresh process, performs the full
initialize → new_session → prompt → close_session lifecycle, then tears
down the process.  This keeps the implementation simple and robust:
there is no shared event-loop between the synchronous ``generate``/``stream``
methods (invoked via ``run_in_executor``) and the asynchronous ``astream``
method (invoked from the main event loop).

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
from typing import Any

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

    # ── Async core ───────────────────────────────────────────────────

    async def _run_acp(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Spawn ``hermes acp``, send *prompt*, yield text deltas.

        Lifecycle: spawn → initialize → new_session → prompt → close_session.
        The connection is torn down automatically by the ``async with`` on
        ``spawn_stdio_transport``.
        """
        client = _HermesACPClient()
        self._last_client = client  # exposed for testing
        cwd = kwargs.get("cwd") or os.getcwd()

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
                    await conn.close_session(session_id)
                except Exception:
                    logger.debug(
                        "close_session failed during cleanup",
                        exc_info=True,
                    )

    async def _generate_async(
        self, prompt: str, **kwargs: Any
    ) -> str:
        """Collect the full response from ``_run_acp``."""
        chunks: list[str] = []
        async for chunk in self._run_acp(prompt, **kwargs):
            chunks.append(chunk)
        return "".join(chunks)

    # ── Public API (LLMBackend interface) ────────────────────────────

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Synchronous generation — full response as a single string.

        Uses ``asyncio.run`` because this method is invoked via
        ``run_in_executor`` (a thread with no running event loop).
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
        synchronously.  This is acceptable because the sync ``stream``
        path is only used internally by the fallback/opendesign wrappers.
        """
        try:
            async def _collect() -> list[str]:
                chunks: list[str] = []
                async for chunk in self._run_acp(prompt, **kwargs):
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
        """Asynchronous streaming — yields text tokens as they arrive."""
        async for chunk in self._run_acp(prompt, **kwargs):
            yield chunk

    def health_check(self) -> dict[str, Any]:
        """Probe the ``hermes acp`` subprocess via a full initialize round-trip."""
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

            resp = asyncio.run(_probe())
            ms = round((time.monotonic() - start) * 1000, 1)
            agent_info = resp.agent_info
            return {
                "status": "ok",
                "latency_ms": ms,
                "model": self.config.model or "hermes",
                "agent_name": agent_info.name if agent_info else "hermes",
                "agent_version": (
                    agent_info.version if agent_info else None
                ),
                "error": None,
            }
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


__all__ = ["HermesACPBackend"]
