import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from backend.application.intelligence.intelligence_service import IntelligenceService
from backend.domain.core.models import Action, EditorState, HermesAction, DelegateAction, ActiveFile
from backend.infrastructure.opencode_connector.manager import OpenCodeConnectorManager

@pytest.fixture
def mock_planner():
    planner = MagicMock()
    planner.generate_plan = AsyncMock(return_value=[])
    return planner

@pytest.fixture
def mock_executor():
    executor = MagicMock()
    executor.execute_action.return_value = {"status": "success"}
    return executor

@pytest.fixture
def mock_connector():
    manager = MagicMock(spec=OpenCodeConnectorManager)
    manager.run_task = AsyncMock(return_value="SUCCESS: Mocked OpenCode Response")
    manager.get_recent_notifications = AsyncMock(return_value=[])
    return manager

@pytest.fixture
def service(mock_planner, mock_executor, mock_connector):
    return IntelligenceService(
        planner=mock_planner,
        executor=mock_executor,
        connector_manager=mock_connector
    )

@pytest.mark.asyncio
async def test_delegate_to_opencode_success(service):
    # Teste la délégation réussie
    task = "Refactor the authentication logic"
    state = EditorState(active_file=ActiveFile(path="/app/main.py", content="import os"))
    
    actions = await service.delegate_to_opencode(task, state)
    
    assert len(actions) == 1
    assert actions[0].action_type == "opencode_delegate"
    assert actions[0].status == "success"
    assert "SUCCESS" in actions[0].params["response"]

@pytest.mark.asyncio
async def test_delegate_to_opencode_failure(service, mock_connector):
    # Teste la délégation échouée (simulée par un contenu sans "SUCCESS")
    mock_connector.run_task.return_value = "Error: Connection lost"
    
    task = "Refactor the authentication logic"
    state = EditorState(active_file=ActiveFile(path="/app/main.py", content="import os"))
    
    actions = await service.delegate_to_opencode(task, state)
    
    assert len(actions) == 1
    assert actions[0].status == "failed"
    assert "Error" in actions[0].params["response"]

@pytest.mark.asyncio
async def test_process_user_intent_delegation(service, mock_planner):
    # Teste que le planner déclenche bien une DelegateAction
    mock_planner.generate_plan.return_value = [DelegateAction(task="Write docs")]
    state = EditorState(active_file=ActiveFile(path="/app/main.py", content="import os"))
    
    actions = await service.process_user_intent("Write documentation", state)
    
    assert len(actions) == 1
    assert actions[0].action_type == "opencode_delegate"
