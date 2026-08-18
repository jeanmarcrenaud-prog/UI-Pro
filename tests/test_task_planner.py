import asyncio
import unittest
from typing import cast
from unittest.mock import MagicMock
from backend.application.intelligence.task_planner import TaskPlanner
from backend.domain.core.models import Action, DelegateAction, EditorState


class TestTaskPlannerGeneratePlan(unittest.TestCase):
    """Tests the JSON parsing of TaskPlanner.generate_plan against the
    various response shapes LLMs can produce."""

    def setUp(self):
        self.planner = TaskPlanner()
        self.state = EditorState()

    def run_async(self, coro):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def mock_llm_response(self, content: str):
        """Point the planner's OpenAI client at a fake returning `content`."""
        fake_message = MagicMock()
        fake_message.content = content
        fake_choice = MagicMock()
        fake_choice.message = fake_message
        fake_response = MagicMock()
        fake_response.choices = [fake_choice]

        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = fake_response
        self.planner.client = fake_client

    def test_bare_json_array(self):
        """Regression: a bare JSON array (the shape the prompt asks for)
        must parse instead of raising 'list' object has no attribute 'get'."""
        self.mock_llm_response(
            '[{"action_type": "insert_code", "params": {"content": "print(1)"}}]'
        )
        actions = self.run_async(self.planner.generate_plan("test intent", self.state))
        self.assertEqual(len(actions), 1)
        self.assertIsInstance(actions[0], Action)
        self.assertEqual(actions[0].action_type, "insert_code")

    def test_actions_wrapper(self):
        """A model may wrap the list in {"actions": [...]}."""
        self.mock_llm_response(
            '{"actions": [{"action_type": "insert_code", "params": {}}]}'
        )
        actions = self.run_async(self.planner.generate_plan("test intent", self.state))
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].action_type, "insert_code")

    def test_plan_wrapper(self):
        """A model may wrap the list in {"plan": [...]}."""
        self.mock_llm_response(
            '{"plan": [{"action_type": "insert_code", "params": {}}]}'
        )
        actions = self.run_async(self.planner.generate_plan("test intent", self.state))
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].action_type, "insert_code")

    def test_single_object_instead_of_list(self):
        """A model may return a single object instead of a list."""
        self.mock_llm_response(
            '{"action_type": "insert_code", "params": {}}'
        )
        actions = self.run_async(self.planner.generate_plan("test intent", self.state))
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].action_type, "insert_code")

    def test_code_block_wrapping(self):
        """Models often wrap JSON in ```json ... ``` fences."""
        self.mock_llm_response(
            '```json\n[{"action_type": "insert_code", "params": {}}]\n```'
        )
        actions = self.run_async(self.planner.generate_plan("test intent", self.state))
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].action_type, "insert_code")

    def test_delegate_action(self):
        """opencode_delegate actions must map to DelegateAction."""
        self.mock_llm_response(
            '[{"action_type": "opencode_delegate", "task": "Write docs"}]'
        )
        actions = self.run_async(self.planner.generate_plan("test intent", self.state))
        self.assertEqual(len(actions), 1)
        delegate = cast(DelegateAction, actions[0])
        self.assertEqual(delegate.task, "Write docs")

    def test_invalid_json_falls_back_to_empty(self):
        """Invalid JSON must not raise; it falls back to an empty plan."""
        self.mock_llm_response("not json at all")
        actions = self.run_async(self.planner.generate_plan("test intent", self.state))
        self.assertEqual(actions, [])


if __name__ == "__main__":
    unittest.main()