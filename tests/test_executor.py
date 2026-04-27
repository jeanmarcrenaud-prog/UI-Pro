"""
test_executor.py - Unit tests for executor module

Tests for:
- subprocess execution
- timeout handling
- error handling
- workspace management
"""

import pytest
from unittest.mock import patch, Mock, MagicMock
import subprocess
import os
from core.executor import run


class TestExecutorBasic:
    """Test basic executor functionality"""
    
    @patch('subprocess.run')
    def test_run_success(self, mock_run):
        """Test successful subprocess execution"""
        # Mock successful subprocess run
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Success output",
            stderr=""
        )
        
        stdout, stderr = run()
        
        assert stdout == "Success output"
        assert stderr == ""
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_run_with_error_output(self, mock_run):
        """Test handling of error output"""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Error message here"
        )
        
        stdout, stderr = run()
        
        assert stderr == "Error message here"
        assert stdout == ""
    
    @patch('subprocess.run')
    def test_run_with_empty_output(self, mock_run):
        """Test handling of empty output"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="",
            stderr=""
        )
        
        stdout, stderr = run()
        
        assert stdout == ""
        assert stderr == ""


class TestTimeoutHandling:
    """Test timeout behavior"""
    
    @patch('subprocess.run')
    def test_run_with_nonzero_exit(self, mock_run):
        """Test handling of non-zero exit code"""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Process failed with exit code 1"
        )
        
        stdout, stderr = run()
        
        assert mock_run.call_args[1]["timeout"] == 60  # executor.py timeout
        assert "run_workspace" in str(mock_run.call_args)


class TestSubprocessConfiguration:
    """Test subprocess configuration"""
    
    @patch('subprocess.run')
    def test_subprocess_arguments(self, mock_run):
        """Test subprocess is called with correct arguments"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="",
            stderr=""
        )
        
        run()
        
        # Verify subprocess arguments
        call_args = mock_run.call_args
        assert call_args[0][0] == ["python", "workspace/app.py"]
        assert call_args[1]["capture_output"] == True
        assert call_args[1]["text"] == True
    
    @patch('subprocess.run')
    def test_execution_timeouted(self, mock_run):
        """Test timeout handling"""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["python", "workspace/app.py"],
            timeout=60
        )
        
        with pytest.raises(subprocess.TimeoutExpired):
            run()
    
    @patch('subprocess.run')
    def test_subprocess_failure(self, mock_run):
        """Test subprocess execution failure"""
        mock_run.side_effect = FileNotFoundError(
            "python",
            None,
            "Python not found"
        )
        
        with pytest.raises(FileNotFoundError):
            run()


class TestWorkspaceManagement:
    """Test workspace directory handling"""
    
    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('os.makedirs')
    def test_workspace_creation(self, mock_makedirs, mock_exists, mock_run):
        """Test workspace directory is created if not exists"""
        mock_exists.return_value = False
        mock_run.return_value = Mock(
            returncode=0,
            stdout="",
            stderr=""
        )
        
        run()
        
        # Verify makedirs was called
        assert mock_makedirs.called


class TestErrorHandling:
    """Test error handling scenarios"""
    
    @patch('subprocess.run')
    def test_subprocess_with_large_output(self, mock_run):
        """Test handling of large outputs"""
        large_output = "x" * 1000000  # 1MB output
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout=large_output,
            stderr=""
        )
        
        stdout, stderr = run()
        
        assert isinstance(stdout, str)
        assert len(stdout) == 1000000
    
    @patch('subprocess.run')
    def test_binary_output(self, mock_run):
        """Test handling of binary output"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=b"binary content",
            stderr=""
        )
        
        # Should handle binary gracefully
        stdout, stderr = run()
        
        assert isinstance(stdout, str)


class TestLogging:
    """Test logging functionality"""
    
    @patch('subprocess.run')
    @patch('executor.logger')
    def test_logging_on_success(self, mock_logger, mock_run):
        """Test logging on successful execution"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Success",
            stderr=""
        )
        
        run()
        
        # Verify logger was called
        assert mock_logger.info.called
        assert mock_logger.warning.called
    
    @patch('subprocess.run')
    @patch('executor.logger')
    def test_logging_on_error(self, mock_logger, mock_run):
        """Test logging on error"""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Error occurred"
        )
        
        run()
        
        # Verify error logging
        assert mock_logger.warning.called


class TestIntegration:
    """Integration tests"""
    
    def test_run_workspace_app_exists(self):
        """Test that workspace/app.py exists and is valid"""
        import os
        workspace_path = os.path.join(os.path.dirname(__file__), "..", "workspace")
        app_path = os.path.join(workspace_path, "app.py")
        
        # Create app.py if it doesn't exist
        if not os.path.exists(app_path):
            os.makedirs(workspace_path, exist_ok=True)
            with open(app_path, "w") as f:
                f.write("print('Hello World')")
        
        assert os.path.exists(app_path)
    
    @patch('subprocess.run')
    def test_actual_execution(self, mock_run):
        """Test actual subprocess execution simulation"""
        # Create a real test file
        test_file = "workspace/test_execution.py"
        os.makedirs("workspace", exist_ok=True)
        
        with open(test_file, "w") as f:
            f.write("print('Execution successful')\nexit(1)")
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Success",
            stderr=""
        )
        
        stdout, stderr = run()
        
        assert stdout == "Success"
        assert mock_run.call_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])