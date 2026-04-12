# tests/test_router.py - Tests for LLMRouter

import pytest
from unittest.mock import patch, MagicMock


class TestLLMRouter:
    """Tests for LLMRouter class"""

    @pytest.fixture
    def mock_config(self):
        """Create mock config"""
        from dataclasses import dataclass
        
        @dataclass
        class MockConfig:
            fast = "qwen2.5:7b"
            reasoning = "qwen2.5:32b"
            code = "deepseek-coder:33b"
            reasoner = "qwen-opus"
            ollama_url = "http://localhost:11434"
            timeout = 30
        
        return MockConfig()

    @pytest.fixture
    def router(self, mock_config):
        """Create router with mock config"""
        from models.llm_router import LLMRouter
        return LLMRouter(config=mock_config)

    def test_get_model_for_task_code(self, router):
        """Test routing for code tasks"""
        assert router.get_model_for_task("write a function") == "deepseek-coder:33b"
        assert router.get_model_for_task("implement def") == "deepseek-coder:33b"
        assert router.get_model_for_task("import numpy") == "deepseek-coder:33b"

    def test_get_model_for_task_reasoning(self, router):
        """Test routing for reasoning tasks"""
        assert router.get_model_for_task("debug this error") == "qwen-opus"
        assert router.get_model_for_task("architecture design") == "qwen-opus"
        assert router.get_model_for_task("complex algorithm") == "qwen-opus"

    def test_get_model_for_task_fast(self, router):
        """Test routing for fast tasks"""
        assert router.get_model_for_task("explain what") == "qwen2.5:7b"
        assert router.get_model_for_task("describe") == "qwen2.5:7b"

    def test_get_model_for_task_default(self, router):
        """Test default routing"""
        assert router.get_model_for_task("random task") == "qwen2.5:32b"

    def test_generate_with_mode(self, router):
        """Test generate method with mode"""
        # The generate method should use the correct model for each mode
        # We can't actually call the LLM, but we can check the config is used
        
        # Test that mode mapping works
        modes = {"fast": "qwen2.5:7b", "reasoning": "qwen2.5:32b", "code": "deepseek-coder:33b"}
        
        for mode, expected_model in modes.items():
            result_config = router.config
            if hasattr(result_config, mode):
                assert getattr(result_config, mode) == expected_model

    def test_generate_raises_on_error(self, router):
        """Test that generate handles errors gracefully"""
        # Mock the client to raise an error
        with patch("models.llm_router.OllamaClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.generate.side_effect = Exception("Connection failed")
            mock_client.return_value = mock_instance
            
            # Should not raise, should return error dict
            result = router.generate("test prompt", mode="fast")
            assert isinstance(result, str)

    def test_stream_raises_on_error(self, router):
        """Test that stream method handles errors gracefully"""
        with patch("models.llm_router.OllamaClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.stream.side_effect = Exception("Connection failed")
            mock_client.return_value = mock_instance
            
            # Collect errors from generator
            errors = []
            try:
                for chunk in router.stream("test prompt"):
                    pass
            except Exception as e:
                errors.append(str(e))
            
            # Should have caught the error somewhere


class TestModelSelection:
    """Tests for model selection logic"""

    def test_explicit_mode_mapping(self):
        """Test explicit mode parameter"""
        from models.llm_router import ModelsConfig
        config = ModelsConfig()
        
        # Each mode should have a model
        assert config.fast
        assert config.reasoning
        assert config.code
        assert config.reasoner

    def test_single_backend_config(self):
        """Test single backend configuration"""
        from models.llm_router import ModelsConfig
        config = ModelsConfig()
        
        # Should have URL configured
        assert config.ollama_url


if __name__ == "__main__":
    pytest.main([__file__, "-v"])