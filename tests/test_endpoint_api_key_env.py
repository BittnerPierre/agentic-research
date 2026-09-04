"""Résolution de la clé API d'un endpoint via variable d'environnement (#219).

Les clés des fournisseurs cloud (OpenRouter…) vivent dans .env : la config YAML
déclare api_key_env, jamais la clé elle-même. Une clé explicite prime ; une
variable déclarée mais absente échoue clairement plutôt que de partir vide.
"""

import pytest

from src.agents.utils import _extract_endpoint_fields, _resolve_endpoint_api_key
from src.config import ModelEndpointConfig


class TestResolveEndpointApiKey:
    def test_env_variable_is_read(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        assert _resolve_endpoint_api_key(None, "OPENROUTER_API_KEY") == "sk-or-test"

    def test_explicit_key_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        assert _resolve_endpoint_api_key("dummy", "OPENROUTER_API_KEY") == "dummy"

    def test_declared_but_missing_env_fails_clearly(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
            _resolve_endpoint_api_key(None, "OPENROUTER_API_KEY")

    def test_declared_but_empty_env_fails_clearly(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "")
        with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
            _resolve_endpoint_api_key(None, "OPENROUTER_API_KEY")

    def test_nothing_declared_resolves_to_none(self):
        assert _resolve_endpoint_api_key(None, None) is None


class TestExtractEndpointFields:
    def test_pydantic_spec_resolves_env_key(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        spec = ModelEndpointConfig(
            name="openai/deepseek/deepseek-v4-flash-0731",
            base_url="https://openrouter.ai/api/v1",
            api_key_env="OPENROUTER_API_KEY",
        )
        name, base_url, api_key, _api = _extract_endpoint_fields(spec)
        assert name == "openai/deepseek/deepseek-v4-flash-0731"
        assert base_url == "https://openrouter.ai/api/v1"
        assert api_key == "sk-or-test"

    def test_dict_spec_resolves_env_key(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        spec = {
            "name": "openai/deepseek/deepseek-v4-flash-0731",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key_env": "OPENROUTER_API_KEY",
        }
        assert _extract_endpoint_fields(spec)[2] == "sk-or-test"

    def test_existing_specs_without_env_are_untouched(self):
        spec = ModelEndpointConfig(
            name="openai/nvidia/Qwen3.6-35B-A3B-NVFP4",
            base_url="http://spark1:8000/v1",
            api_key="dummy",
        )
        assert _extract_endpoint_fields(spec)[2] == "dummy"
