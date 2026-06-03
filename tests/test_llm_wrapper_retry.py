"""Tests for LLMWrapper.run_node retry behavior.

Covers the asyncio.TimeoutError retry added to handle local LLM
stalls (Lemonade/Ollama) that recover on the second attempt.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator
from unittest.mock import MagicMock, patch

import pytest


class _StubRouter:
    """Stub router whose astream yields tokens or raises after a delay."""

    def __init__(self, behaviors: list) -> None:
        self._behaviors = list(behaviors)
        self.calls = 0

    async def astream(self, **_kwargs: object) -> AsyncIterator[str]:
        self.calls += 1
        behavior = self._behaviors.pop(0)
        if isinstance(behavior, Exception):
            raise behavior
        for token in behavior:
            yield token

    def generate(self, *args, **kwargs) -> str:  # noqa: ARG002
        return ""  # used by stream_generate fallback


@pytest.mark.asyncio
async def test_run_node_succeeds_first_try():
    from backend.domain.core.langgraph.llm_wrapper import LLMWrapper

    router = _StubRouter([["hello", " world"]])
    wrapper = LLMWrapper(router, user_model="m", user_provider="ollama")

    with patch("backend.domain.core.langgraph.llm_wrapper.settings") as mock_settings:
        mock_settings.llm_timeout = 5
        result = await wrapper.run_node("hi", model_type="fast")

    assert result == "hello world"
    assert router.calls == 1


@pytest.mark.asyncio
async def test_run_node_retries_on_timeout_and_succeeds():
    """First attempt: stream_generate hangs. Second attempt: returns content."""
    from backend.domain.core.langgraph.llm_wrapper import LLMWrapper

    router = _StubRouter([["recovered", " response"]])
    wrapper = LLMWrapper(router, user_model="m", user_provider="ollama")

    sg_calls = {"n": 0}
    real_sg = wrapper.stream_generate

    async def flaky_sg(*args, **kwargs):  # type: ignore[no-untyped-def]
        sg_calls["n"] += 1
        if sg_calls["n"] == 1:
            # Simulate hang by sleeping beyond the wrapper timeout
            await asyncio.sleep(10)
            return
            yield  # make this an async generator  # noqa: F401
        async for tok in real_sg(*args, **kwargs):
            yield tok

    with patch.object(wrapper, "stream_generate", side_effect=flaky_sg):
        with patch("backend.domain.core.langgraph.llm_wrapper.settings") as mock_settings:
            mock_settings.llm_timeout = 1  # tight timeout
            result = await wrapper.run_node("hi", model_type="fast", max_retries=1)

    assert "recovered" in result
    assert sg_calls["n"] == 2  # one hang + one successful retry


@pytest.mark.asyncio
async def test_run_node_raises_after_exhausted_retries():
    from backend.domain.core.langgraph.llm_wrapper import LLMWrapper

    router = _StubRouter(
        [RuntimeError("fail 1"), RuntimeError("fail 2")]
    )
    wrapper = LLMWrapper(router, user_model="m", user_provider="ollama")

    wait_for_calls = {"n": 0}
    real_wait_for = asyncio.wait_for

    async def always_timeout(awaitable, timeout=None):  # type: ignore[no-untyped-def]
        wait_for_calls["n"] += 1
        raise asyncio.TimeoutError()

    with patch(
        "backend.domain.core.langgraph.llm_wrapper.asyncio.wait_for",
        side_effect=always_timeout,
    ):
        with patch("backend.domain.core.langgraph.llm_wrapper.settings") as mock_settings:
            mock_settings.llm_timeout = 5
            with pytest.raises(TimeoutError, match="timed out after 5"):
                await wrapper.run_node("hi", model_type="fast", max_retries=1)

    assert wait_for_calls["n"] == 2  # initial + 1 retry


@pytest.mark.asyncio
async def test_run_node_strip_markdown_fences():
    from backend.domain.core.langgraph.llm_wrapper import LLMWrapper

    router = _StubRouter([["```python\nprint('hi')\n```"]])
    wrapper = LLMWrapper(router, user_model="m", user_provider="ollama")

    with patch("backend.domain.core.langgraph.llm_wrapper.settings") as mock_settings:
        mock_settings.llm_timeout = 5
        result = await wrapper.run_node(
            "hi", model_type="fast", strip_markdown=True
        )

    assert "print('hi')" in result
    assert "```" not in result
