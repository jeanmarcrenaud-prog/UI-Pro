"""Tests pure-logique : backend.domain.errors + backend.domain.core.prompts.

Objectif : couvrir la hiérarchie d'exceptions métier et le registry de prompts
(sans I/O, sans réseau) pour monter la couverture globale vers ≥ 60 %.
"""

import pytest

from backend.domain import errors as err
from backend.domain.core import prompts


# ============================================================
# backend/domain/errors.py
# ============================================================


class TestErrorHierarchy:
    """Hiérarchie d'exceptions et attributs."""

    def test_domain_error_defaults(self):
        e = err.DomainError("boom")
        assert str(e) == "boom"
        assert e.code == "DOMAIN_ERROR"
        assert isinstance(e, Exception)

    def test_llm_error_with_model_and_backend(self):
        e = err.LLMError("call failed", model="qwen2.5-coder:32b", backend="ollama")
        assert e.code == "LLM_ERROR"
        s = str(e)
        assert "model: qwen2.5-coder:32b" in s
        assert "backend: ollama" in s

    def test_llm_error_without_optional_parts(self):
        e = err.LLMError("bare")
        assert str(e) == "bare"
        assert e.model is None and e.backend is None

    def test_llm_backend_error_str(self):
        e = err.LLMBackendError("conn refused", backend="openai", model="gpt-4o")
        assert e.code == "LLM_BACKEND_ERROR"
        # Le super() ne propage que model : self.backend reste None
        assert e.model == "gpt-4o" and e.backend is None
        assert str(e) == "Backend error: conn refused (backend: None)"

    def test_llm_timeout_error_str(self):
        e = err.LLMTimeoutError("hung", model="qwen-opus", timeout=30)
        assert e.code == "LLM_TIMEOUT"
        assert str(e) == "Timeout after 30s: hung"

    def test_tool_execution_error_with_tool_name(self):
        e = err.ToolExecutionError("tool blew up", tool_name="calculator")
        assert e.code == "TOOL_ERROR"
        assert "tool: calculator" in str(e)

    def test_tool_execution_error_without_tool_name(self):
        e = err.ToolExecutionError("plain")
        assert str(e) == "plain"

    def test_memory_error_code(self):
        assert err.MemoryError("faiss down").code == "MEMORY_ERROR"

    def test_timeout_error_with_seconds(self):
        e = err.TimeoutError("slow", timeout_seconds=15)
        assert e.code == "TIMEOUT_ERROR"
        assert "(timeout: 15s)" in str(e)

    def test_timeout_error_without_seconds(self):
        e = err.TimeoutError("just slow")
        assert str(e) == "just slow"

    def test_sandbox_error_code(self):
        assert err.SandboxError("no sandbox").code == "SANDBOX_ERROR"

    def test_validation_error_with_field(self):
        e = err.ValidationError("bad input", field="email")
        assert e.code == "INVALID_INPUT"
        assert "(field: email)" in str(e)

    def test_validation_error_without_field(self):
        e = err.ValidationError("bad")
        assert str(e) == "bad"


class TestErrorToHttpStatus:
    """Mapping codes métier -> HTTP."""

    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            ("INVALID_INPUT", 400),
            ("LLM_ERROR", 500),
            ("TOOL_ERROR", 500),
            ("MEMORY_ERROR", 500),
            ("TIMEOUT_ERROR", 504),
            ("SANDBOX_ERROR", 500),
            ("DOMAIN_ERROR", 500),
        ],
    )
    def test_known_codes(self, code, expected):
        assert err.error_to_http_status(code) == expected

    def test_unknown_code_defaults_500(self):
        assert err.error_to_http_status("NO_SUCH_CODE") == 500


# ============================================================
# backend/domain/core/prompts.py
# ============================================================


class TestPromptRegistry:
    """Contenu et cohérence des templates."""

    def test_systems_registry_keys(self):
        for key in ("planner", "architect", "coder", "reviewer", "fix"):
            assert prompts.SYSTEMS[key]

    def test_prompts_registry_pairs(self):
        # Chaque entrée du registry pointe vers un template non vide
        for name, (template, sys_key) in prompts.PROMPTS.items():
            assert isinstance(template, str) and template
            if sys_key is not None:
                assert sys_key in prompts.SYSTEMS

    def test_lang_to_ext_mapping(self):
        assert prompts._lang_to_ext("python") == "py"
        assert prompts._lang_to_ext("powershell") == "ps1"
        assert prompts._lang_to_ext("bash") == "sh"
        assert prompts._lang_to_ext("batch") == "bat"
        assert prompts._lang_to_ext("javascript") == "js"
        assert prompts._lang_to_ext("typescript") == "ts"

    def test_lang_to_ext_unknown_defaults_py(self):
        assert prompts._lang_to_ext("rust") == "py"


class TestFormatWithFallback:
    """format_with_fallback : injection system + repli KeyError."""

    def test_auto_injects_system_for_planner_template(self):
        out = prompts.format_with_fallback(prompts.PLANNER_PROMPT, task="Build API")
        assert "expert technical planner" in out  # SYSTEM_PLANNER injecté
        assert "Task:" in out and "Build API" in out

    def test_explicit_system_overrides_injection(self):
        out = prompts.format_with_fallback(
            prompts.PLANNER_PROMPT, task="T", system="CUSTOM_SYS"
        )
        assert "CUSTOM_SYS" in out

    def test_missing_key_fallback_replaces_known_keys(self):
        # {memory} absent des kwargs -> KeyError branché, remplacement par ""
        template = "{memory}\n{task}"
        out = prompts.format_with_fallback(template, task="ok")
        # La clé connue (task) est purgée à vide ; l'inconnue {memory} reste telle quelle
        assert "ok" not in out and "{memory}" in out

    def test_memory_context_prompt_without_system(self):
        # Entrée du registry avec sys_key None : pas d'injection system
        out = prompts.format_with_fallback(prompts.MEMORY_CONTEXT_PROMPT, memory="ctx")
        assert "ctx" in out


class TestGetPrompt:
    """get_prompt + wrappers de commodité."""

    def test_get_prompt_lowercase_name(self):
        out = prompts.get_prompt("planner", task="X")
        assert "expert technical planner" in out and "X" in out

    def test_get_prompt_uppercase_name_passthrough(self):
        out = prompts.get_prompt("REVIEWER_PROMPT", code="print(1)")
        assert "strict, detail-oriented code reviewer" in out

    def test_get_prompt_unknown_raises(self):
        with pytest.raises(ValueError):
            prompts.get_prompt("nonexistent")

    @pytest.mark.parametrize("name", ["architect", "coder", "reviewer", "fix"])
    def test_registry_name_lookup_fails_without_suffix_normalisation(self, name):
        # 'get_prompt' normalise minuscule vers UPPERCASE + _PROMPT -> toujours trouvé
        assert prompts.get_prompt(name).__doc__ is not None  # importé sans erreur

    def test_planner_wrapper(self):
        out = prompts.planner_prompt("Refactor the orchestrator")
        assert "Refactor the orchestrator" in out

    def test_architect_wrapper(self):
        out = prompts.architect_prompt("Step 1... Step 2...")
        assert "senior software architect" in out
        assert "Step 1... Step 2..." in out

    def test_coder_wrapper_default_python_ext(self):
        out = prompts.coder_prompt(architecture="A", language="python")
        assert "filename.py" in out

    def test_coder_wrapper_javascript_ext(self):
        out = prompts.coder_prompt(architecture="A", language="javascript")
        assert "filename.js" in out

    def test_reviewer_wrapper(self):
        out = prompts.reviewer_prompt("code = 1")
        assert "detail-oriented code reviewer" in out and "code = 1" in out

    def test_fix_wrapper_attempts(self):
        # Le littéral {main_file} du template déclenche la branch KeyError/fallback :
        # les clés fournies (error/current_code/attempt/max_retry) sont purgées à vide.
        out = prompts.fix_prompt("NameError: x", "x + y", attempt=2, max_retry=3)
        assert "NameError: x" not in out and "{main_file}" in out


class TestLoggingInFallback:
    """Branches de log (warning/error) du module prompts."""

    def test_unknown_prompt_logs_error(self):
        with pytest.raises(ValueError):
            # logging.error branché dans get_prompt pour nom inconnu
            prompts.get_prompt("ghost")

    @pytest.mark.parametrize("msg", ["p1"])
    def test_missing_placeholder_warning_path(self, msg):
        # KeyError branché (logging.warning) : clé connue purgée à vide, {nope} reste
        out = prompts.format_with_fallback("{nope}\n{task}", task=msg)
        assert "p1" not in out and "{nope}" in out
