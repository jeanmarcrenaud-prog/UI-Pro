import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from core.old_orchestrator import run_team, save_file

class TestSaveFile:
    """Unit tests for save_file function."""
    
    def test_save_file_creates_file(self, tmp_path, monkeypatch):
        """Save file creates file in workspace."""
        workspace = tmp_path
        monkeypatch.setattr("orchestrator.WORKSPACE", str(workspace))
        
        save_file("test.py", "content")
        
        assert (tmp_path / "test.py").exists()
        
    def test_save_file_writes_content(self, tmp_path, monkeypatch):
        """Save file writes exact content."""
        workspace = tmp_path
        monkeypatch.setattr("orchestrator.WORKSPACE", str(workspace))
        
        test_content = "print('Hello Python')"
        save_file("app.py", test_content)
        
        assert (tmp_path / "app.py").read_text() == test_content
    
    def test_save_file_creates_directory(self, tmp_path, monkeypatch):
        """Save file creates directory if needed."""
        workspace = tmp_path
        monkeypatch.setattr("orchestrator.WORKSPACE", str(workspace))
        
        test_content = "test"
        save_file("app.py", test_content)
        
        workspace_path = Path(workspace)
        child = list(workspace_path.iterdir())[0]
        assert child.is_file()
        assert child.name == "app.py"

@pytest.fixture
def mock_workspace(tmp_path, monkeypatch):
    """Setup a temporary workspace directory."""
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    monkeypatch.setattr("orchestrator.WORKSPACE", str(workspace_dir))
    return workspace_dir

@pytest.fixture
def mock_all_agents():
    """Mock all specialized agents for orchestrator testing."""
    with patch('orchestrator.planner') as mock_planner, \
         patch('orchestrator.architect') as mock_architect, \
         patch('orchestrator.coder') as mock_coder, \
         patch('orchestrator.reviewer') as mock_reviewer, \
         patch('orchestrator.tester') as mock_tester, \
         patch('orchestrator.debugger') as mock_debugger, \
         patch('orchestrator.devops') as mock_devops:
        
        # Set up default mock behaviors
        mock_planner.return_value = "Plan: Build FastAPI app"
        mock_architect.return_value = "Architecture: FastAPI with endpoints"
        mock_coder.return_value = "app.py code content"
        mock_reviewer.return_value = "Reviewed app.py"
        mock_tester.return_value = "# Test code here"
        mock_debugger.return_value = "Debugged app.py"
        mock_devops.return_value = "# Dockerfile content"
        
        yield {
            'planner': mock_planner,
            'architect': mock_architect,
            'coder': mock_coder,
            'reviewer': mock_reviewer,
            'tester': mock_tester,
            'debugger': mock_debugger,
            'devops': mock_devops
        }

@pytest.fixture
def mock_memory(monkeypatch):
    """Mock memory functions for testing."""
    with patch('orchestrator.search_memory') as mock_search, \
         patch('orchestrator.add_memory') as mock_add:
        mock_search.return_value = []
        mock_add.return_value = None
        yield {'search': mock_search, 'add': mock_add}

class TestRunTeam:
    """Integration tests for run_team function covering all execution paths."""
    
    def test_run_team_success_path(self, mock_workspace, mock_all_agents, mock_memory, mocker):
        """Test successful orchestration with no errors requiring debug."""
        agents = mock_all_agents
        memory = mock_memory
        
        # Mock executor.run to succeed immediately (no error)
        mock_run = mocker.patch('orchestrator.run')
        mock_run.return_value = ("Execution successful", "")
        
        # Execute the team
        run_team("Create a FastAPI app that returns [1, 2, 3]")
        
        # Verify planner was called
        assert agents['planner'].assert_called_once()
        
        # Verify architect was called
        assert agents['architect'].assert_called_once()
        
        # Verify coder was called
        assert agents['coder'].assert_called_once()
        
        # Verify searcher didn't fail
        assert memory['search'].assert_called_once()
        
        # Verify file creation
        assert (mock_workspace / "app.py").exists()
        
        # Verify debugger NEVER called (no errors occurred)
        assert not agents['debugger'].called
    
    def test_run_team_with_debug_cycle(self, mock_workspace, mock_all_agents, mocker):
        """Test execution with errors requiring debugger intervention."""
        agents = mock_all_agents
        
        # Mock memory search to return empty context
        with patch('orchestrator.search_memory') as mock_search:
            mock_search.return_value = []
            
            with patch('orchestrator.add_memory') as mock_add:
                # Mock executor.run to fail twice then succeed
                mock_run = mocker.patch('orchestrator.run')
                mock_run.side_effect = [
                    ("", "AttributeError: Something went wrong"),
                    ("", "TypeError: Invalid operation"),
                    ("Success!", "")  # Third attempt: success
                ]
                
                # Execute
                run_team("Build a calculator application")
                
                # Debugger should have been called twice (for two errors)
                assert agents['debugger'].call_count >= 1
                
                # Should have created app.py file
                assert (mock_workspace / "app.py").exists()
                
                # Add_memory should have been called to store errors
                assert mock_add.call_count >= 1
    
    def test_run_team_exception_handling(self, mocker):
        """Test exception handling when critical component fails."""
        
        with patch('orchestrator.planner') as mock_planner:
            mock_planner.side_effect = Exception("Planner failed")
            
            with patch('orchestrator.search_memory') as mock_search:
                mock_search.return_value = []
                
                # Should raise exception
                try:
                    run_team("Create something")
                    pytest.fail("Expected exception to be raised")
                except Exception as e:
                    assert str(e) == "Planner failed"
    
    def test_run_team_multiple_iterations(self, mock_workspace, mock_all_agents, mocker):
        """Test run_team completes within max 5 iterations."""
        agents = mock_all_agents
        
        with patch('orchestrator.search_memory') as mock_search:
            mock_search.return_value = []
            
            with patch('orchestrator.add_memory') as mock_add:
                # Mock run to succeed on 3rd iteration
                mock_run = mocker.patch('orchestrator.run')
                mock_run.side_effect = [
                    ("", "Error 1"),
                    ("", "Error 2"),
                    ("Success on 3rd try", "")  # Success
                ]
                
                run_team("Test iteration limit")
                
                # Should complete within 5 iterations
                assert mock_run.call_count <= 5
                
                # Files should exist
                assert (mock_workspace / "app.py").exists()
                assert (mock_workspace / "test_app.py").exists()
                assert (mock_workspace / "Dockerfile").exists()

@pytest.mark.integration
def test_run_team_complete_workflow(mocker, tmp_path, monkeypatch):
    """Integration test verifying complete end-to-end workflow."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr("orchestrator.WORKSPACE", str(workspace))
    
    with patch('orchestrator.planner') as mock_planner:
        mock_planner.return_value = "Plan: Create API"
        
        with patch('orchestrator.search_memory') as mock_search:
            mock_search.return_value = []
            
            with patch('orchestrator.add_memory') as mock_add:
                with patch('orchestrator.architect') as mock_arch:
                    mock_arch.return_value = "FastAPI architecture with REST endpoints"
                    
                    with patch('orchestrator.coder') as mock_coder:
                        mock_coder.return_value = """
from fastapi import FastAPI
app = FastAPI()
@app.get("/")
def root():
    return {"status": "ok"}
"""
                        with patch('orchestrator.debugger'):
                            with patch('orchestrator.reviewer') as mock_review:
                                with patch('orchestrator.tester') as mock_test:
                                    with patch('orchestrator.devops') as mock_devops:
                                        mock_run = mocker.patch('orchestrator.run')
                                        mock_run.return_value = ("200 OK", "")
                                        
                                        run_team("Build REST API")
                                        
                                        # Verify all components engaged
                                        assert mock_planner.called
                                        assert mock_arch.called
                                        assert mock_coder.called
                                        assert mock_review.called
                                        assert mock_test.called
                                        assert mock_devops.called
                                        
                                        # Verify workspace files
                                        assert (workspace / "app.py").exists()
                                        assert (workspace / "test_app.py").exists()
                                        assert (workspace / "Dockerfile").exists()


# Run tests with: pytest tests/test_orchestrator.py -v
   
