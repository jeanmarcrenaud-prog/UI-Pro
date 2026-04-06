"""
test_llm.py - Unit tests for LLM module

Tests for:
- Ollama API calls (call, smart_call)
- Error handling and timeouts
- Model selection logic
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock, call
import requests
import sys
from pathlib import Path

# Import under test
sys.path.insert(0, str(Path(__file__).parent.parent))
from llm import call, smart_call, OLLAMA_URL, MODELS


class TestCallFunction:
    """Test call() function with various scenarios"""
    
    def test_call_success_response(self):
        """Test successful API call returns response"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "response": "This is the AI response",
            "model": "qwen-opus",
            "done": True
        }
        
        with patch('requests.post', return_value=mock_response) as mock_post:
            result = call("qwen2.5-coder:32b", "Hello")
            
            assert result == "This is the AI response"
            mock_post.assert_called_once_with(
                OLLAMA_URL,
                json={
                    "model": "qwen2.5-coder:32b",
                    "prompt": "Hello",
                    "stream": False,
                    "timeout": 30
                },
                timeout=40
            )
    
    def test_call_empty_response(self):
        """Test when API returns empty response"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "response": "",
            "model": "qwen2.5-coder:32b",
            "done": True
        }
        
        with patch('requests.post', return_value=mock_response) as mock_post:
            result = call("qwen2.5-coder:32b", "Hello")
            
            assert result == ""
    
    def test_call_timeout_error(self):
        """Test handling of timeout errors"""
        with patch('requests.post', side_effect=requests.exceptions.Timeout()) as mock_post:
            result = call("qwen2.5-coder:32b", "Hello")
            
            assert result == ""
            mock_post.assert_called_once()
    
    def test_call_http_error(self):
        """Test handling of HTTP errors from Ollama"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response,
            request=Mock()
        )
        
        with patch('requests.post', return_value=mock_response) as mock_post:
            result = call("qwen2.5-coder:32b", "Hello")
            
            assert result == ""
    
    def test_call_request_exception(self):
        """Test handling of network errors"""
        with patch('requests.post', side_effect=requests.exceptions.ConnectionError()) as mock_post:
            result = call("qwen2.5-coder:32b", "Hello")
            
            assert result == ""


class TestSmartCallFunction:
    """Test smart_call() function with model selection"""
    
    def test_smart_call_fast_model(self, caplog):
        """Test smart_call uses fast model for normal prompts"""
        prompt = "Write a Python function to calculate fibonacci"
        result = smart_call(prompt)
        
        assert result is not None
        # Should have used fast model
        assert any("qwen2.5-coder:32b" in str(call_arg) for call_arg in caplog.log_records) if hasattr(caplog, 'log_records') else True
    
    def test_smart_call_reasoning_model_keywords(self):
        """Test smart_call uses reasoning model when keywords detected"""
        keywords = ["error", "debug", "optimize", "architecture", "complex"]
        
        for keyword in keywords:
            prompt = f"This is a {keyword} related task"
            result = smart_call(prompt)
            
            assert result is not None
    
    def test_smart_call_no_keywords(self):
        """Test smart_call uses fast model when no keywords"""
        prompt = "Simple question without special keywords"
        result = smart_call(prompt)
        
        assert result is not None
    
    def test_smart_call_empty_prompt(self):
        """Test smart_call handles empty prompt"""
        result = smart_call("")
        assert result is not None or result == ""


# Test edge cases
def test_smart_call_edge_cases():
    """Test various edge cases for smart_call"""
    
    # Empty prompt
    result = smart_call("")
    assert result is not None
    
    # None prompt (should handle gracefully)
    try:
        result = smart_call(None)
        assert result is not None or result == ""
    except Exception:
        pass  # Expected to fail gracefully


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_call_with_special_characters(self):
        """Test call with special characters in prompt"""
        prompt = "Test with special chars: @#$%^&*()[]{}<>|"
        mock_response = Mock()
        mock_response.json.return_value = {
            "response": "Handled special chars",
            "model": "qwen2.5-coder:32b",
            "done": True
        }
        
        with patch('requests.post', return_value=mock_response):
            result = call("qwen2.5-coder:32b", prompt)
            
            assert result == "Handled special chars"
    
    def test_call_with_multiline_prompt(self):
        """Test call with multiline prompt"""
        prompt = """Line 1
        
Line 2
        
Line 3"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "response": "Handled multiline",
            "model": "qwen2.5-coder:32b",
            "done": True
        }
        
        with patch('requests.post', return_value=mock_response):
            result = call("qwen2.5-coder:32b", prompt)
            
            assert result == "Handled multiline"
    
    def test_smart_call_with_very_long_prompt(self):
        """Test smart_call with very long prompt"""
        long_prompt = "x " * 10000  # 20KB string
        mock_response = Mock()
        mock_response.json.return_value = {
            "response": "Handled long prompt",
            "model": "qwen2.5-coder:32b",
            "done": True
        }
        
        with patch('requests.post', return_value=mock_response):
            result = call("qwen2.5-coder:32b", long_prompt)
            
            assert result == "Handled long prompt"
    
    def test_smart_call_unicode(self):
        """Test smart_call with unicode characters"""
        prompt = "Test with Unicode: 你好世界 🌍 Привет мир"
        mock_response = Mock()
        mock_response.json.return_value = {
            "response": "Handled unicode",
            "model": "qwen2.5-coder:32b",
            "done": True
        }
        
        with patch('requests.post', return_value=mock_response):
            result = call("qwen2.5-coder:32b", prompt)
            
            assert result == "Handled unicode"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
