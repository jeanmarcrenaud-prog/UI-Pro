"""Tests for model_discovery.py — enrichment, TTL cache, and DiscoveredModel."""

from __future__ import annotations

import time

import pytest

from backend.infrastructure.model_discovery import (
    TTLCache,
    DiscoveredModel,
    _estimate_max_context,
    _estimate_speed,
    _infer_capabilities,
    get_models_summary,
)


# ====================== Capability Inference ======================


class TestInferCapabilities:
    def test_vision_model(self):
        caps = _infer_capabilities("llava-v1.6-34b")
        assert "vision" in caps
        assert "image" in caps
        assert "analysis" in caps
        assert "chat" in caps  # always present

    def test_vision_moondream(self):
        caps = _infer_capabilities("moondream-v2")
        assert "vision" in caps

    def test_vision_bakllava(self):
        caps = _infer_capabilities("bakllava:7b")
        assert "vision" in caps

    def test_code_model_deepseek(self):
        caps = _infer_capabilities("deepseek-coder-v2")
        assert "code" in caps
        assert "reasoning" in caps  # deepseek is also reasoning

    def test_code_model_qwen(self):
        caps = _infer_capabilities("qwen2.5-coder:7b")
        assert "code" in caps

    def test_reasoning_model_llama(self):
        caps = _infer_capabilities("llama3:70b")
        assert "reasoning" in caps
        assert "code" not in caps

    def test_reasoning_mistral(self):
        caps = _infer_capabilities("mistral:7b")
        assert "reasoning" in caps

    def test_creative_model_gemma(self):
        caps = _infer_capabilities("gemma2:9b")
        assert "creative" in caps

    def test_embedding_model(self):
        caps = _infer_capabilities("nomic-embed-text")
        assert "embeddings" in caps
        assert "vision" not in caps
        assert "code" not in caps

    def test_generic_model(self):
        caps = _infer_capabilities("some-random-model")
        assert caps == ["chat"]

    def test_no_duplicate_capabilities(self):
        caps = _infer_capabilities("deepseek-coder-v2")
        assert caps == list(dict.fromkeys(caps))  # preserve order, no dupes


# ====================== Context Estimation ======================


class TestEstimateMaxContext:
    def test_70b(self):
        assert _estimate_max_context("70b", "") == 32768

    def test_72b(self):
        assert _estimate_max_context("72b", "") == 32768

    def test_405b(self):
        assert _estimate_max_context("405b", "") == 32768

    def test_32b(self):
        assert _estimate_max_context("32b", "") == 16384

    def test_13b(self):
        assert _estimate_max_context("13b", "") == 8192

    def test_8b(self):
        assert _estimate_max_context("8b", "") == 8192

    def test_3b(self):
        assert _estimate_max_context("3b", "") == 4096

    def test_1b(self):
        assert _estimate_max_context("1b", "") == 4096

    def test_unknown_size(self):
        assert _estimate_max_context("", "") == 8192

    def test_with_family(self):
        # Family doesn't affect current implementation
        assert _estimate_max_context("8b", "llama") == 8192


# ====================== Speed Estimation ======================


class TestEstimateSpeed:
    def test_q2_very_fast(self):
        assert _estimate_speed("Q2_K", "7b") == "very_fast"

    def test_q3_very_fast(self):
        assert _estimate_speed("Q3_K_M", "7b") == "very_fast"

    def test_iq2_very_fast(self):
        assert _estimate_speed("IQ2_XXS", "7b") == "very_fast"

    def test_1b_very_fast(self):
        assert _estimate_speed("Q8_0", "1b") == "very_fast"

    def test_q4_fast(self):
        assert _estimate_speed("Q4_K_M", "7b") == "fast"

    def test_7b_param_fast(self):
        assert _estimate_speed("Q8_0", "7b") == "fast"

    def test_q5_medium(self):
        assert _estimate_speed("Q5_K_M", "13b") == "medium"

    def test_q6_medium(self):
        assert _estimate_speed("Q6_K", "13b") == "medium"

    def test_fallback_slow(self):
        assert _estimate_speed("FP16", "13b") == "slow"

    def test_none_quantization(self):
        assert _estimate_speed(None, "8b") in ("fast", "slow")  # depends on param size

    def test_empty_quantization(self):
        result = _estimate_speed("", "9b")
        assert isinstance(result, str)


# ====================== DiscoveredModel ======================


class TestDiscoveredModel:
    def test_default_capabilities(self):
        model = DiscoveredModel(name="test", backend="ollama")
        assert model.capabilities == ["chat"]

    def test_custom_capabilities(self):
        model = DiscoveredModel(
            name="llava", backend="ollama", capabilities=["chat", "vision"]
        )
        assert "vision" in model.capabilities

    def test_default_speed_tier(self):
        model = DiscoveredModel(name="test", backend="ollama")
        assert model.speed_tier == "medium"

    def test_default_context(self):
        model = DiscoveredModel(name="test", backend="ollama")
        assert model.max_context == 8192

    def test_all_fields(self):
        model = DiscoveredModel(
            name="llava-v1.6-34b",
            backend="ollama",
            size="20GB",
            family="llava",
            parameter_size="34b",
            quantization="Q4_K_M",
            capabilities=["chat", "vision"],
            max_context=8192,
            speed_tier="fast",
            is_vision=True,
            is_loaded=True,
            size_vram_gb=4.5,
        )
        assert model.name == "llava-v1.6-34b"
        assert model.is_vision is True
        assert model.is_loaded is True
        assert model.size_vram_gb == 4.5
        assert model.speed_tier == "fast"


# ====================== get_models_summary ======================


class TestGetModelsSummary:
    def test_empty_list(self):
        assert get_models_summary([]) == []

    def test_single_model(self):
        model = DiscoveredModel(
            name="test", backend="ollama", capabilities=["chat"]
        )
        summary = get_models_summary([model])
        assert len(summary) == 1
        assert summary[0]["name"] == "test"
        assert summary[0]["backend"] == "ollama"
        assert summary[0]["capabilities"] == ["chat"]

    def test_all_fields_in_summary(self):
        model = DiscoveredModel(
            name="llava",
            backend="ollama",
            size="10GB",
            family="llava",
            parameter_size="7b",
            quantization="Q4_K_M",
            speed_tier="fast",
            max_context=8192,
            capabilities=["chat", "vision"],
            is_vision=True,
            is_coder=False,
            is_reasoning=False,
            is_loaded=True,
            size_vram_gb=3.2,
        )
        summary = get_models_summary([model])[0]
        assert summary["is_vision"] is True
        assert summary["is_loaded"] is True
        assert summary["size_vram_gb"] == 3.2
        assert summary["parameter_size"] == "7b"
        assert summary["quantization"] == "Q4_K_M"


# ====================== TTLCache ======================


class TestTTLCache:
    def test_get_set(self):
        cache = TTLCache(ttl=60.0)
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_missing_key(self):
        cache = TTLCache(ttl=60.0)
        assert cache.get("nonexistent") is None

    def test_expiry(self):
        cache = TTLCache(ttl=0.1)  # 100ms TTL
        cache.set("key", "value")
        assert cache.get("key") == "value"
        time.sleep(0.15)
        assert cache.get("key") is None

    def test_clear(self):
        cache = TTLCache(ttl=60.0)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_overwrite(self):
        cache = TTLCache(ttl=60.0)
        cache.set("key", "old")
        cache.set("key", "new")
        assert cache.get("key") == "new"
