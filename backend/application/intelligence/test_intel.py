import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from unittest.mock import MagicMock

from backend.application.intelligence.intelligence_service import IntelligenceService
from backend.domain.core.editor_service import EditorService
from backend.domain.core.action_executor import ActionExecutor
from backend.domain.core.planner import TaskPlanner
from backend.domain.core.models import EditorState, Cursor
from backend.infrastructure.opencode_connector.manager import OpenCodeConnectorManager


class MockEditorService(EditorService):
    """Mock that skips EditorStateStore dependency and returns a plain dict."""

    def __init__(self):
        pass

    def get_current_state(self) -> dict:
        return {
            "active_file": None,
            "cursor": {"line": 1, "column": 0},
            "selection": None,
            "diagnostics": [],
            "terminal_output": None,
            "git_status": {},
        }


service = MockEditorService()
executor = ActionExecutor(service)
planner = TaskPlanner(service)
connector_manager = MagicMock(spec=OpenCodeConnectorManager)
intel = IntelligenceService(planner, executor, connector_manager)

# Run the async test
import asyncio

state = EditorState(cursor=Cursor(line=1, column=0))

# Test 1: Regular intent -> HermesAction path
print("=== Test 1: Regular intent (local planning) ===")
result = asyncio.run(intel.process_user_intent('Hello', state))
print(result)

# Test 2: Delegate intent -> DelegateAction -> opencode run
print("\n=== Test 2: Delegate intent (opencode) ===")
async def mock_run(task, project_path, model="lmstudio/google/gemma-4-12b-qat"):
    return {"success": True, "response": "Bonjour!", "session_id": "ses_test"}
connector_manager.run = mock_run
result = asyncio.run(intel.process_user_intent('Bonjour', state))
print(result)
print("-> run() called with (Bonjour, workspace)")
