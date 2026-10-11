"""Unit tests for hermes_config.evaluate_hermes_config.

Spec: docs/plans/spec-hermes-config-check.md — report-only readiness
evaluation, no GPU load, short probe timeout. HTTP is mocked so these
tests never touch the network.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from backend.infrastructure.llm import hermes_config

_REQUIRED_KEYS = {
    "configured",
    "base_url",
    "model",
    "backend",
    "llm_reachable",
    "available_models",
    "recommended_model",
    "gpu_headroom_ok",
    "needs_install",
    "message",
}


def _settings(**overrides):
    base = dict(
        hermes_llm_base_url="",
        hermes_llm_model="google/gemma-4-12b-qat",
        lmstudio_url="http://127.0.0.1:1234",
        ollama_url="http://127.0.0.1:11434",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestEvaluateHermesConfig:
    def test_lmstudio_reachable_lists_models(self):
        """LM Studio up: probe hits /v1/models, report is ready and picks the
        lightest model, flagging the heavy 27B model as no headroom."""
        settings = _settings(hermes_llm_base_url="http://127.0.0.1:1234/v1")

        captured = {}

        def fake_probe(url):
            captured["url"] = url
            return True, ["qwen3.8-27b", "aura-4b"]

        with patch.object(hermes_config, "_probe_models", side_effect=fake_probe):
            report = hermes_config.evaluate_hermes_config(settings)

        assert captured["url"] == "http://127.0.0.1:1234/v1/models"
        assert set(report) == _REQUIRED_KEYS
        assert report["backend"] == "lmstudio"
        assert report["configured"] is True
        assert report["llm_reachable"] is True
        assert report["available_models"] == ["qwen3.8-27b", "aura-4b"]
        assert report["recommended_model"] == "aura-4b"
        assert report["gpu_headroom_ok"] is False  # 27B heavy model present
        assert report["needs_install"] is False

    def test_lmstudio_down_needs_install(self):
        """Nothing configured and no local backend reachable → needs_install."""
        settings = _settings(hermes_llm_base_url="")

        with patch.object(hermes_config, "_probe_models", return_value=(False, [])):
            report = hermes_config.evaluate_hermes_config(settings)

        assert report["backend"] == "none"
        assert report["configured"] is False
        assert report["llm_reachable"] is False
        assert report["available_models"] == []
        assert report["needs_install"] is True
        assert "Aucun LLM local" in report["message"]

    def test_ollama_autodetected_when_unconfigured(self):
        """With no base_url, LM Studio misses and Ollama answers → backend
        ollama and the report is ready."""
        settings = _settings(hermes_llm_base_url="")

        def fake_probe(url):
            return (False, []) if "/v1/models" in url else (True, ["llama3.2:3b"])

        with patch.object(hermes_config, "_probe_models", side_effect=fake_probe):
            report = hermes_config.evaluate_hermes_config(settings)

        assert report["backend"] == "ollama"
        assert report["llm_reachable"] is True
        assert report["recommended_model"] == "llama3.2:3b"
        assert report["gpu_headroom_ok"] is True
        assert report["needs_install"] is False
