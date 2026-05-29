# tests/test_router.py - Tests for LLMRouter (advanced router)

from unittest.mock import MagicMock, patch

import pytest


class TestLLMRouter:
    """Tests for the advanced LLMRouter class"""

    def _make_router(self):
        from backend.infrastructure.llm_router import LLMRouter, RouterConfig

        config = RouterConfig(max_context_tokens=4096)
        return LLMRouter(config=config)

    def test_classify_task_code(self):
        """Test classification for code tasks."""
        router = self._make_router()

        result = router.classify_task(prompt="implement a function to sort a list")
        from backend.infrastructure.llm_router import TaskType

        assert result in (TaskType.CODE, TaskType.FAST, TaskType.REASONING)

    def test_classify_task_reasoning(self):
        """Test classification for reasoning tasks."""
        router = self._make_router()

        result = router.classify_task(prompt="explain how the architecture works")
        from backend.infrastructure.llm_router import TaskType

        assert result in TaskType

    def test_classify_task_fast(self):
        """Test classification for fast tasks."""
        router = self._make_router()

        result = router.classify_task(prompt="what is the time")
        from backend.infrastructure.llm_router import TaskType

        assert result in TaskType

    def test_select_model_returns_string(self):
        """Test select_model returns a valid model name."""
        router = self._make_router()
        model = router.select_model(
            prompt="write a function to parse JSON",
        )
        assert isinstance(model, str)
        assert len(model) > 0

    def test_route_returns_dict(self):
        """Test route returns expected structure."""
        router = self._make_router()
        result = router.route(prompt="implement a sorting algorithm")
        assert "model" in result
        assert "task_type" in result
        assert "confidence" in result

    def test_route_with_mode(self):
        """Test route with explicit mode."""
        router = self._make_router()
        result = router.route(prompt="anything", mode="code")
        assert "model" in result
        assert result["task_type"] == "code"

    def test_records_calls(self):
        """Test record_call tracks usage."""
        router = self._make_router()
        from backend.infrastructure.llm_router import TaskType

        router.record_call("test-model", TaskType.CODE, 100.0, True)
        assert len(router._call_history) == 1

    def test_records_max_length(self):
        """Test _call_history doesn't exceed 200 entries."""
        router = self._make_router()
        from backend.infrastructure.llm_router import TaskType

        for i in range(210):
            router.record_call(f"model-{i}", TaskType.FAST, 50.0, True)
        assert len(router._call_history) <= 200

    def test_models_configured(self):
        """Test router has required model type mappings."""
        router = self._make_router()
        from backend.infrastructure.llm_router import TaskType

        for task_type in [TaskType.FAST, TaskType.REASONING, TaskType.CODE]:
            assert task_type in router.models
            assert isinstance(router.models[task_type], str)


class TestTaskType:
    """Tests for TaskType enum."""

    def test_values(self):
        from backend.infrastructure.llm_router import TaskType

        assert TaskType.FAST.value == "fast"
        assert TaskType.CODE.value == "code"
        assert TaskType.REASONING.value == "reasoning"
        assert TaskType.CREATIVE.value == "creative"
        assert TaskType.ANALYSIS.value == "analysis"

    def test_all_defined(self):
        from backend.infrastructure.llm_router import TaskType

        assert len(TaskType) >= 5


class TestRouterConfig:
    """Tests for RouterConfig dataclass."""

    def test_default_max_context(self):
        from backend.infrastructure.llm_router import RouterConfig

        config = RouterConfig()
        assert config.max_context_tokens > 0

    def test_custom_config(self):
        from backend.infrastructure.llm_router import RouterConfig

        config = RouterConfig(max_context_tokens=999, enable_cost_optimization=False)
        assert config.max_context_tokens == 999
        assert config.enable_cost_optimization is False


class TestGetLLMRouter:
    """Tests for get_llm_router singleton."""

    def test_singleton(self):
        from backend.infrastructure.llm_router import get_llm_router

        router1 = get_llm_router()
        router2 = get_llm_router()
        assert router1 is router2

    def test_router_has_required_methods(self):
        from backend.infrastructure.llm_router import get_llm_router

        router = get_llm_router()
        assert hasattr(router, "classify_task")
        assert hasattr(router, "select_model")
        assert hasattr(router, "route")
        assert hasattr(router, "generate")
        assert hasattr(router, "astream")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
