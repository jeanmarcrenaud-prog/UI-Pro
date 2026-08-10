"""
test_opencode_mock.py - Integration test for the OpenCode connector using a
mock WebSocket server speaking the current request/response protocol.
"""

import asyncio
import json
import logging

import pytest
import websockets

from backend.infrastructure.opencode_connector.manager import OpenCodeConnectorManager

logger = logging.getLogger(__name__)

MOCK_HOST = "localhost"
MOCK_PORT = 8765
MOCK_URI = f"ws://{MOCK_HOST}:{MOCK_PORT}"


async def mock_opencode_server():
    """Simulates an OpenCode server that responds to a run_task request."""

    async def handler(websocket):
        try:
            message = await websocket.recv()
            data = json.loads(message)
            prompt = data.get("prompt", "")
            logger.info(f"Mock server received prompt: {prompt[:60]}")
            reply = {
                "type": "step_finish",
                "content": f"Mock executed: {prompt}",
                "metadata": None,
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


@pytest.mark.asyncio
async def test_opencode_connector_flow():
    """run_task round-trips through a live WebSocket and returns the response."""
    server_task = asyncio.create_task(mock_opencode_server())
    await asyncio.sleep(1)  # wait for server to start

    manager = OpenCodeConnectorManager(ws_url=MOCK_URI, api_key="test-key", model_id="test-model")

    try:
        result = await manager.run_task("write a test")
        assert result == "SUCCESS: Mock executed: write a test", f"Unexpected result: {result}"
    finally:
        await manager.shutdown()
        server_task.cancel()
        try:
            await server_task
        except (asyncio.CancelledError, Exception):
            pass
