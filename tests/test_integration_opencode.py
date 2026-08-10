"""
test_integration_opencode.py - Integration test for the OpenCode connector.

Covers the current task-runner contract: ``get_client`` lazy init,
``run_task`` round-trip through a live WebSocket mock, and graceful
fallback when the backend is unavailable.
"""

import asyncio
import json
import logging
import unittest

import websockets

from backend.infrastructure.opencode_connector.manager import OpenCodeConnectorManager

logger = logging.getLogger("integration_test")

MOCK_HOST = "127.0.0.1"
MOCK_PORT = 8766  # keep clear of the real API (8000) and other mocks (8765)
MOCK_URI = f"ws://{MOCK_HOST}:{MOCK_PORT}"


async def mock_opencode_server():
    """Simulates an OpenCode server that replies to run_task requests."""

    async def handler(websocket):
        try:
            message = await websocket.recv()
            data = json.loads(message)
            reply = {
                "type": "step_finish",
                "content": f"processed: {data.get('prompt', '')}",
                "metadata": {"model": data.get("model")},
            }
            await websocket.send(json.dumps(reply))
        except websockets.exceptions.ConnectionClosed:
            pass

    async with websockets.serve(handler, MOCK_HOST, MOCK_PORT):
        # Serve until the task is cancelled.
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass


class TestOpenCodeIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        server_task = getattr(self, "server_task", None)
        if server_task is not None:
            server_task.cancel()
            try:
                await server_task
            except (asyncio.CancelledError, Exception):
                pass

    async def test_run_task_round_trip(self):
        """run_task reaches the WebSocket server and surfaces its response."""
        self.server_task = asyncio.create_task(mock_opencode_server())
        await asyncio.sleep(1)

        manager = OpenCodeConnectorManager(
            ws_url=MOCK_URI, api_key="test-key", model_id="test-model"
        )
        try:
            result = await manager.run_task("hello")
        finally:
            await manager.shutdown()

        self.assertEqual(result, "SUCCESS: processed: hello")

    async def test_run_task_falls_back_when_unreachable(self):
        """An unreachable backend degrades to an ERROR string, not an exception."""
        manager = OpenCodeConnectorManager(
            ws_url="ws://127.0.0.1:1", api_key="k", model_id="m"
        )
        result = await manager.run_task("hello")
        self.assertTrue(result.startswith("ERROR:"))


if __name__ == "__main__":
    unittest.main()
