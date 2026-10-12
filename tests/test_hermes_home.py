"""Unit tests for hermes_home — real Hermes agent config resolution.

These tests are hermetic: they pin ``HERMES_HOME`` to a temp dir so they never
read the developer's real ``%LOCALAPPDATA%\\hermes\\config.yaml``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.infrastructure.llm import hermes_home
from backend.infrastructure.llm.hermes_home import (
    LEGACY_DEFAULT_MODEL,
    hermes_config_path,
    read_hermes_agent_config,
    resolve_effective_hermes_llm,
)


def _settings(**overrides):
    base = dict(hermes_llm_base_url="", hermes_llm_model="")
    base.update(overrides)
    return SimpleNamespace(**base)


def _write_config(tmp_path, body: str):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(body, encoding="utf-8")
    return cfg


class TestReadHermesAgentConfig:
    def test_reads_model_mapping(self, monkeypatch, tmp_path):
        _write_config(
            tmp_path,
            "model:\n"
            "  default: bonsai-2-27b-pq2_0-crack\n"
            "  provider: lmstudio\n"
            "  base_url: http://127.0.0.1:1234/v1\n",
        )
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        assert read_hermes_agent_config() == {
            "model": "bonsai-2-27b-pq2_0-crack",
            "base_url": "http://127.0.0.1:1234/v1",
            "provider": "lmstudio",
        }

    def test_missing_file_returns_empty(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "does-not-exist"))
        assert read_hermes_agent_config() == {}

    def test_malformed_yaml_returns_empty(self, monkeypatch, tmp_path):
        _write_config(tmp_path, "model: [unclosed")
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        assert read_hermes_agent_config() == {}

    def test_not_a_mapping_returns_empty(self, monkeypatch, tmp_path):
        _write_config(tmp_path, "- just\n- a\n- list\n")
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        assert read_hermes_agent_config() == {}

    def test_no_model_mapping_returns_empty(self, monkeypatch, tmp_path):
        _write_config(tmp_path, "server:\n  port: 8001\n")
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        assert read_hermes_agent_config() == {}

    def test_ignores_blank_values(self, monkeypatch, tmp_path):
        _write_config(tmp_path, "model:\n  default: '   '\n  base_url: http://x/v1\n")
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        assert read_hermes_agent_config() == {"base_url": "http://x/v1"}

    def test_hermes_home_takes_priority(self, monkeypatch, tmp_path):
        cfg = _write_config(tmp_path, "model:\n  default: x\n")
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        assert hermes_config_path() == cfg


class TestResolveEffectiveHermesLlm:
    def test_explicit_override_wins_over_real_config(self, monkeypatch, tmp_path):
        _write_config(tmp_path, "model:\n  default: real-model\n")
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        s = _settings(hermes_llm_model="ui-model", hermes_llm_base_url="http://ui/v1")
        assert resolve_effective_hermes_llm(s) == ("ui-model", "http://ui/v1")

    def test_falls_back_to_real_config(self, monkeypatch, tmp_path):
        _write_config(
            tmp_path,
            "model:\n"
            "  default: bonsai-2-27b-pq2_0-crack\n"
            "  base_url: http://127.0.0.1:1234/v1\n",
        )
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        assert resolve_effective_hermes_llm(_settings()) == (
            "bonsai-2-27b-pq2_0-crack",
            "http://127.0.0.1:1234/v1",
        )

    def test_legacy_default_is_treated_as_unset(self, monkeypatch, tmp_path):
        _write_config(tmp_path, "model:\n  default: real-model\n")
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        s = _settings(hermes_llm_model=LEGACY_DEFAULT_MODEL)
        assert resolve_effective_hermes_llm(s) == ("real-model", "")

    def test_legacy_default_with_base_url_is_respected(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        s = _settings(
            hermes_llm_model=LEGACY_DEFAULT_MODEL,
            hermes_llm_base_url="http://ui/v1",
        )
        assert resolve_effective_hermes_llm(s) == (LEGACY_DEFAULT_MODEL, "http://ui/v1")

    def test_no_config_no_override_returns_empty(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "empty"))
        assert resolve_effective_hermes_llm(_settings()) == ("", "")

    def test_whitespace_only_override_is_unset(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "empty"))
        s = _settings(hermes_llm_model="   ", hermes_llm_base_url="  ")
        assert resolve_effective_hermes_llm(s) == ("", "")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
