"""
test_streaming_verification.py - Tests for the OpenCode connector streaming flow.

The connector was rewritten from an editor-state-sync WebSocket protocol
to a task-runner API (``run_task`` / ``get_recent_notifications``). These
tests verify that flow and its graceful fallback when the backend is down.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.infrastructure.opencode_connector.manager import (
    OpenCodeConnectorManager,
    OpenCodeClient,
    OpenCodeResponse,
)


class TestStreamingVerification(unittest.IsolatedAsyncioTestCase):
    async def test_run_task_returns_success_when_client_responds(self):
        """run_task returns SUCCESS: payload for a step_finish response."""
        manager = OpenCodeConnectorManager(
            ws_url="ws://localhost:8080", api_key="key", model_id="model"
        )
        fake_client = MagicMock(spec=OpenCodeClient)
        fake_client.is_running = True
        fake_client.send_request = AsyncMock(
            return_value=OpenCodeResponse(type="step_finish", content="Done!")
        )
        manager.client = fake_client

        result = await manager.run_task("write tests")

        self.assertEqual(result, "SUCCESS: Done!")
        fake_client.send_request.assert_awaited_once_with("write tests")

    async def test_run_task_falls_back_when_client_not_running(self):
        """A disconnected client must not raise — it degrades to an ERROR string."""
        manager = OpenCodeConnectorManager(
            ws_url="ws://localhost:8080", api_key="key", model_id="model"
        )
        fake_client = MagicMock(spec=OpenCodeClient)
        fake_client.is_running = False
        manager.client = fake_client

        result = await manager.run_task("write tests")

        self.assertTrue(result.startswith("ERROR:"), f"Unexpected result: {result}")

    async def test_get_client_is_lazy_and_falls_back_on_connect_error(self):
        """get_client should not raise when the WebSocket cannot be reached."""
        manager = OpenCodeConnectorManager(
            ws_url="ws://localhost:1", api_key="key", model_id="model"
        )
        with patch.object(
            OpenCodeClient, "connect", new=AsyncMock(side_effect=ConnectionError("down"))
        ):
            client = await manager.get_client()
        self.assertIsNotNone(client)

    def test_get_recent_notifications_returns_list(self):
        """The notifications feed returns a structured list."""
        manager = OpenCodeConnectorManager()
        notifications = manager.get_recent_notifications(limit=10)
        self.assertIsInstance(notifications, list)
        for n in notifications:
            self.assertIn("type", n)
            self.assertIn("content", n)


if __name__ == "__main__":
    unittest.main()
