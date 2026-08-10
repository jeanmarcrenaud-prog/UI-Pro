"""
test_send_action.py - Tests for sending tasks through the OpenCode connector.

The legacy ``send_action`` / ``start`` / ``stop`` API was replaced by the
task-runner API (``run_task``). These tests verify the current contract.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from backend.infrastructure.opencode_connector.manager import (
    OpenCodeConnectorManager,
    OpenCodeClient,
    OpenCodeResponse,
)


class TestSendActionFlow(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager = OpenCodeConnectorManager(
            ws_url="ws://localhost:8765", api_key="key", model_id="model"
        )
        self.fake_client = MagicMock(spec=OpenCodeClient)
        self.fake_client.is_running = True
        self.fake_client.send_request = AsyncMock(
            return_value=OpenCodeResponse(type="text", content="ack")
        )
        self.manager.client = self.fake_client

    async def test_send_simple_action(self):
        """run_task forwards the prompt to the client and returns its content."""
        result = await self.manager.run_task("insert print('Hello from Hermes!')")
        self.assertEqual(result, "ack")
        self.fake_client.send_request.assert_awaited_once()

    async def test_run_task_with_step_finish_prefixes_success(self):
        """step_finish responses are surfaced as SUCCESS: <content>."""
        self.fake_client.send_request = AsyncMock(
            return_value=OpenCodeResponse(type="step_finish", content="Done")
        )
        result = await self.manager.run_task("do something")
        self.assertEqual(result, "SUCCESS: Done")

    async def test_shutdown_closes_client(self):
        """shutdown closes the underlying client."""
        await self.manager.shutdown()
        self.fake_client.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
