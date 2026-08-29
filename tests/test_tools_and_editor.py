"""Tests pure-logique : tools.models + application.editor_manager.

Couvre les dataclasses de définition d'outils (schéma OpenAI, validation des
arguments, exécution async avec timeout) et le bootstrap des singletons
d'éditeur — sans I/O réseau.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import backend.application.editor_manager as editor_manager
from backend.infrastructure.tools.models import Tool, ToolCall, ToolParameter


# ============================================================
# backend/infrastructure/tools/models.py
# ============================================================


class TestToolSchema:
    """to_openai_schema : propriétés + paramètres requis."""

    def test_to_openai_schema_with_required_param(self):
        tool = Tool(
            name="add",
            description="Add two numbers.",
            parameters=[
                ToolParameter(name="a", type="number", description="First operand"),
                ToolParameter(name="b", type="number", description="Second operand", required=True),
            ],
        )
        schema = tool.to_openai_schema()
        assert schema["type"] == "function"
        fn = schema["function"]
        assert fn["name"] == "add"
        props = fn["parameters"]["properties"]
        assert props["a"]["description"] == "First operand"
        assert fn["parameters"]["required"] == ["b"]

    def test_to_openai_schema_no_params(self):
        tool = Tool(name="noop", description="Nothing.", parameters=[])
        schema = tool.to_openai_schema()
        assert schema["function"]["name"] == "noop"
        assert schema["function"]["parameters"]["properties"] == {}
        assert schema["function"]["parameters"]["required"] == []


class TestValidateArguments:
    """validate_arguments : types et paramètres manquants."""

    @pytest.mark.parametrize(
        ("value", "expected_ok"),
        [
            (42, True),          # int accepté pour number
            (3.14, True),        # float accepté pour number
        ],
    )
    def test_number_values_accepted(self, value, expected_ok):
        tool = Tool(
            name="t", description="d", parameters=[ToolParameter(name="n", type="number", description="", required=True)]
        )
        ok, err = tool.validate_arguments({"n": value})
        assert ok is True and err is None

    def test_string_value_rejects_number(self):
        tool = Tool(name="t", description="d", parameters=[ToolParameter(name="s", type="string", description="", required=True)])
        ok, err = tool.validate_arguments({"s": 123})
        assert not ok and isinstance(err, str)
        assert "must be a string" in err

    def test_boolean_value_rejects_int(self):
        tool = Tool(name="t", description="d", parameters=[ToolParameter(name="b", type="boolean", description="", required=True)])
        ok, err = tool.validate_arguments({"b": 1})
        assert not ok and isinstance(err, str)
        assert "must be a boolean" in err

    def test_missing_required_param(self):
        tool = Tool(
            name="t",
            description="d",
            parameters=[ToolParameter(name="req", type="string", description="", required=True)],
        )
        ok, err = tool.validate_arguments({})
        assert not ok and isinstance(err, str)
        assert "Missing required parameter: req" in err

    def test_optional_param_absent_is_ok(self):
        tool = Tool(
            name="t",
            description="d",
            parameters=[ToolParameter(name="opt", type="string", description="", required=False)],
        )
        ok, err = tool.validate_arguments({})
        assert ok is True and err is None


class TestToolExecute:
    """execute : succès, timeout, erreur handler, pas de handler."""

    @pytest.mark.asyncio
    async def test_execute_success(self):
        async def add(args):
            return args["a"] + args["b"]

        tool = Tool(name="add", description="d", parameters=[], handler=add)
        result = await tool.execute({"a": 1, "b": 2})
        assert result == {"status": "success", "result": 3}

    @pytest.mark.asyncio
    async def test_execute_validation_error_short_circuit(self):
        tool = Tool(
            name="t",
            description="d",
            parameters=[ToolParameter(name="req", type="string", description="", required=True)],
        )
        result = await tool.execute({})
        assert result["status"] == "error"
        assert "Missing required parameter" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_no_handler(self):
        tool = Tool(name="t", description="d", parameters=[])  # handler=None par défaut
        result = await tool.execute({})
        assert result == {"status": "error", "error": "No handler defined"}

    @pytest.mark.asyncio
    async def test_execute_timeout(self):
        async def slow(args):
            await asyncio.sleep(2)
            return "done"

        tool = Tool(name="slow", description="d", parameters=[], handler=slow, timeout_seconds=0)
        result = await tool.execute({})
        assert result["status"] == "error"
        assert "timed out" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_handler_exception(self):
        async def boom(args):
            raise RuntimeError("kaboom")

        tool = Tool(name="boom", description="d", parameters=[], handler=boom)
        result = await tool.execute({})
        assert result["status"] == "error"
        assert "kaboom" in result["error"]


class TestToolCall:
    """ToolCall : timestamp par défaut."""

    def test_default_timestamp(self):
        call = ToolCall(id="c1", name="add", arguments={"a": 1})
        assert call.id == "c1"
        assert call.arguments == {"a": 1}
        assert hasattr(call, "timestamp")


# ============================================================
# backend/application/editor_manager.py
# ============================================================


def _reset_editor_globals():
    editor_manager._editor_state_store = None
    editor_manager._editor_service = None
    editor_manager._opencode_manager = None


@pytest.fixture(autouse=True)
def _clean_editor_singletons():
    """Les singletons du module sont des globals : on les remet à zéro."""
    _reset_editor_globals()
    yield
    _reset_editor_globals()


class TestEditorManagerSingletons:
    """get_* sans init -> RuntimeError ; après init -> instance stable."""

    def test_get_editor_service_before_init_raises(self):
        with pytest.raises(RuntimeError, match="init_editor_services"):
            editor_manager.get_editor_service()

    def test_get_opencode_manager_before_init_raises(self):
        with pytest.raises(RuntimeError, match="init_editor_services"):
            editor_manager.get_opencode_manager()

    @pytest.mark.asyncio
    async def test_init_creates_singletons_and_is_idempotent(self):
        # On patche les classes importées dans le namespace du module pour éviter l'I/O.
        with (
            patch.object(editor_manager, "EditorStateStore") as MockStore,
            patch.object(editor_manager, "FilesystemService") as MockFs,
            patch.object(editor_manager, "EditorService") as MockSvc,
            patch.object(editor_manager, "OpenCodeConnectorManager") as MockMgr,
        ):
            # get_client() est appelé dans un asyncio.create_task : il doit
            # retourner une vraie coroutine (AsyncMock) et non un simple Mock.
            MockMgr.return_value.get_client = AsyncMock()

            await editor_manager.init_editor_services()

            store = editor_manager._editor_state_store
            svc = editor_manager.get_editor_service()
            mgr = editor_manager.get_opencode_manager()
            assert store is not None and mgr is not None
            # Les classes mockées ont bien été instanciées avec les bons arguments
            MockStore.assert_called_once_with()
            MockSvc.assert_called_once()
            MockMgr.assert_called_once_with("ws://localhost:8765")

            # Deuxième appel : pas de re-création (idempotence)
            await editor_manager.init_editor_services(ws_uri="ws://x:8765")
            assert editor_manager.get_opencode_manager() is mgr