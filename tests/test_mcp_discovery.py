import requests
import pytest


def test_mcp_discovery():
    """Discover MCP tools exposed by the standalone Hermes MCP server (port 8001)."""
    BASE_URL = "http://localhost:8001"
    TOOLS_ENDPOINT = f"{BASE_URL}/mcp/tools"

    try:
        response = requests.get(TOOLS_ENDPOINT, timeout=5)
    except requests.exceptions.ConnectionError:
        pytest.skip("Hermes MCP server not running on port 8001 (start: python run.py --hermes)")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    tools = response.json()
    assert isinstance(tools, list), f"Expected a list of tools, got {type(tools)}"
    assert len(tools) > 0, "MCP server exposed no tools"

    # Verification of critical tools
    tool_names = [tool["name"] for tool in tools]
    critical_tools = ["execute_intent", "get_opencode_status", "read_file", "write_file", "chat"]
    missing = [t for t in critical_tools if t not in tool_names]
    assert not missing, f"Missing critical tools: {missing}"

if __name__ == "__main__":
    test_mcp_discovery()
