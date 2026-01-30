"""Tests for local llama model settings overrides."""

from __future__ import annotations

from agents.model_settings import ModelSettings
from src.agents.utils import adjust_model_settings_for_base_url


def test_local_llama_disables_response_format():
    model_spec = {
        "name": "openai/local-llm",
        "base_url": "http://llama-cpp-cpu:8002",
        "api_key": "dummy",
    }
    settings = ModelSettings()
    adjust_model_settings_for_base_url(model_spec, settings)

    assert settings.extra_args is not None
    assert settings.extra_args.get("drop_params") is True
    assert "response_format" in settings.extra_args.get("additional_drop_params", [])
