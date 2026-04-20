"""TDD red tests for issue #158 — resolve_model() dispatch.

Documents the expected post-fix behavior:

  | name prefix       | base_url | resolved type                    |
  |-------------------|----------|----------------------------------|
  | openai/<name>     | yes      | OpenAIChatCompletionsModel       |
  | openai/<name>     | no       | passthrough (SDK Response API)   |
  | litellm/<prov>/.. | any      | LitellmModel (only legit case)   |

Today resolve_model() wraps every ModelEndpointConfig in LitellmModel, so the
openai/+base_url cases incorrectly route through litellm.completion(). These
tests fail until the dispatch is rewritten.
"""

from __future__ import annotations

import pytest
from agents import OpenAIChatCompletionsModel
from agents.extensions.models.litellm_model import LitellmModel
from agents.model_settings import ModelSettings
from openai import AsyncOpenAI

from src.agents.utils import adjust_model_settings_for_base_url, resolve_model
from src.config import ModelEndpointConfig


class TestOpenAILocalEndpoint:
    """openai/<name> + base_url = local OpenAI-compatible server (vLLM, llama.cpp).
    Must use the SDK's native chat-completions path, NOT LiteLLM."""

    @pytest.fixture
    def local_dict(self):
        return {
            "name": "openai/local-llm",
            "base_url": "http://llama-cpp-cpu:8002",
            "api_key": "dummy",
        }

    @pytest.fixture
    def local_endpoint(self):
        return ModelEndpointConfig(
            name="openai/local-llm",
            base_url="http://llama-cpp-cpu:8002",
            api_key="dummy",
        )

    def test_dict_resolves_to_chat_completions_model(self, local_dict):
        model = resolve_model(local_dict)

        assert not isinstance(model, LitellmModel), (
            "openai/+base_url must NOT be wrapped in LitellmModel (issue #158)."
        )
        assert isinstance(model, OpenAIChatCompletionsModel)

    def test_endpoint_config_resolves_to_chat_completions_model(self, local_endpoint):
        model = resolve_model(local_endpoint)

        assert not isinstance(model, LitellmModel)
        assert isinstance(model, OpenAIChatCompletionsModel)

    def test_chat_completions_model_holds_async_openai_client(self, local_dict):
        model = resolve_model(local_dict)

        client = model._client
        assert isinstance(client, AsyncOpenAI)
        assert str(client.base_url).rstrip("/").startswith("http://llama-cpp-cpu:8002")
        assert client.api_key == "dummy"

    def test_chat_completions_model_uses_bare_model_name(self, local_dict):
        """The openai/ prefix is a routing hint for resolve_model. Once we hand the
        client an AsyncOpenAI instance, the model name must be the bare identifier
        the local server expects."""
        model = resolve_model(local_dict)

        assert model.model == "local-llm", (
            f"Expected bare 'local-llm', got {model.model!r}. "
            "The openai/ prefix should be stripped before reaching the server."
        )


class TestOpenAICloudEndpoint:
    """openai/<name> WITHOUT base_url = OpenAI cloud. The SDK handles it natively
    via the Response API; resolve_model should not wrap it in LiteLLM."""

    def test_string_passes_through(self):
        model = resolve_model("openai/gpt-4.1-mini")

        assert not isinstance(model, LitellmModel)
        assert model == "openai/gpt-4.1-mini"

    def test_endpoint_config_without_base_url_does_not_become_litellm(self):
        spec = ModelEndpointConfig(name="openai/gpt-4.1-mini")

        model = resolve_model(spec)

        assert not isinstance(model, LitellmModel), (
            "openai/ without base_url is cloud OpenAI — the SDK handles it via "
            "Response API; LiteLLM must not be in the chain (issue #158)."
        )


class TestLiteLLMEndpoint:
    """litellm/<provider>/<name> is the only legitimate use of LiteLLM (paid proxy
    APIs like Mistral, Anthropic). Behavior must be preserved by the fix."""

    def test_dict_resolves_to_litellm_model(self):
        spec = {
            "name": "litellm/mistral/mistral-medium-latest",
            "api_key": "key",
        }
        model = resolve_model(spec)

        assert isinstance(model, LitellmModel)
        assert model.model == "litellm/mistral/mistral-medium-latest"

    def test_endpoint_config_resolves_to_litellm_model(self):
        spec = ModelEndpointConfig(
            name="litellm/anthropic/claude-3-7-sonnet-20250219",
            api_key="key",
        )
        model = resolve_model(spec)

        assert isinstance(model, LitellmModel)

    def test_litellm_with_base_url_still_uses_litellm(self):
        """Self-hosted LiteLLM proxy: litellm/ prefix WITH base_url must still
        resolve to LitellmModel (the prefix is the routing signal, not base_url)."""
        spec = ModelEndpointConfig(
            name="litellm/openai/gpt-4o",
            base_url="http://litellm-proxy:4000",
            api_key="proxy-key",
        )
        model = resolve_model(spec)

        assert isinstance(model, LitellmModel)
        assert model.base_url == "http://litellm-proxy:4000"


class TestAdjustModelSettingsScope:
    """adjust_model_settings_for_base_url() applies LiteLLM-specific hacks
    (drop_params, additional_drop_params). After issue #158, openai/+base_url
    no longer routes through LiteLLM, so the function MUST be a no-op for that
    case. The hacks only make sense on the litellm/ path."""

    def test_openai_with_local_base_url_is_no_op(self):
        """Today this fails: the function injects drop_params=True even for
        openai/+base_url because the substring 'llama-cpp' triggers the hack
        regardless of prefix. After the fix it must skip openai/."""
        spec = {
            "name": "openai/local-llm",
            "base_url": "http://llama-cpp-cpu:8002",
            "api_key": "dummy",
        }
        settings = ModelSettings()

        adjust_model_settings_for_base_url(spec, settings)

        assert not (settings.extra_args and settings.extra_args.get("drop_params")), (
            "openai/+base_url no longer goes through LiteLLM (issue #158); "
            "drop_params is a LiteLLM-specific hack and must not be set."
        )
        assert not (
            settings.extra_args and settings.extra_args.get("additional_drop_params")
        ), "additional_drop_params is LiteLLM-specific and must not be set for openai/."

    def test_litellm_with_local_base_url_still_applies_hack(self):
        """Sanity: the LiteLLM-only hack must still fire on the litellm/ path
        when pointed at a llama.cpp endpoint, otherwise we regress that path."""
        spec = {
            "name": "litellm/openai/gpt-oss",
            "base_url": "http://llama-cpp-cpu:8002",
            "api_key": "dummy",
        }
        settings = ModelSettings()

        adjust_model_settings_for_base_url(spec, settings)

        assert settings.extra_args is not None
        assert settings.extra_args.get("drop_params") is True
        assert "response_format" in settings.extra_args.get(
            "additional_drop_params", []
        )


class TestResolveModelIdempotency:
    def test_litellm_model_passes_through(self):
        original = LitellmModel(model="litellm/mistral/foo", api_key="k")
        assert resolve_model(original) is original
