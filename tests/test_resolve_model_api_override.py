"""TDD red tests for issue #164 — per-endpoint API override.

Documents the expected behavior of resolve_model() once the new `api` field
on ModelEndpointConfig is honored.

Today the dispatch is hardcoded:
- openai/+base_url            → OpenAIChatCompletionsModel
- openai/+api_key (no bu)     → OpenAIResponsesModel
- openai/ alone               → bare string passthrough

After #164, an explicit `api: "chat_completions" | "responses"` on the spec
overrides this default, so e.g. gpt-oss on vLLM can opt into Responses API
(needed to expose the `reasoning` field cleanly).

Sanity tests (api=None) confirm that current behavior is preserved.
"""

from __future__ import annotations

from agents.extensions.models.litellm_model import LitellmModel
from openai import AsyncOpenAI

from agents import OpenAIChatCompletionsModel, OpenAIResponsesModel
from src.agents.utils import resolve_model
from src.config import ModelEndpointConfig


class TestApiOverrideOnLocalEndpoint:
    """openai/+base_url with explicit api override.

    Use case: vLLM serving gpt-oss exposes /v1/responses; we want to opt in
    to Responses API instead of the default Chat Completions choice.
    """

    def test_responses_override_on_local_endpoint(self):
        spec = ModelEndpointConfig(
            name="openai/gpt-oss-20b",
            base_url="http://vllm:8004/v1",
            api_key="dummy",
            api="responses",
        )

        model = resolve_model(spec)

        assert isinstance(model, OpenAIResponsesModel), (
            f"Expected OpenAIResponsesModel for explicit api='responses' on a "
            f"local endpoint (gpt-oss/vLLM use case), got {type(model).__name__}."
        )
        assert isinstance(model._client, AsyncOpenAI)
        assert str(model._client.base_url).rstrip("/").startswith("http://vllm:8004")
        assert model._client.api_key == "dummy"
        assert model.model == "gpt-oss-20b"

    def test_chat_completions_override_on_local_endpoint_is_explicit_default(self):
        """Sanity: passing the current default explicitly must keep working."""
        spec = ModelEndpointConfig(
            name="openai/local-llm",
            base_url="http://llama-cpp-cpu:8002",
            api_key="dummy",
            api="chat_completions",
        )

        model = resolve_model(spec)

        assert isinstance(model, OpenAIChatCompletionsModel)

    def test_no_override_on_local_endpoint_preserves_chat_completions_default(self):
        """Sanity: api=None preserves current behavior (Chat Completions for
        openai/+base_url). Already passes today, must keep passing."""
        spec = ModelEndpointConfig(
            name="openai/local-llm",
            base_url="http://llama-cpp-cpu:8002",
            api_key="dummy",
        )

        model = resolve_model(spec)

        assert isinstance(model, OpenAIChatCompletionsModel)


class TestApiOverrideOnCloudWithKey:
    """openai/+api_key (no base_url) with explicit api override."""

    def test_chat_completions_override_on_cloud_with_key(self):
        """Edge case: cloud OpenAI but the user wants Chat Completions
        (legacy code, specific feature)."""
        spec = ModelEndpointConfig(
            name="openai/gpt-4.1-mini",
            api_key="sk-custom",
            api="chat_completions",
        )

        model = resolve_model(spec)

        assert isinstance(model, OpenAIChatCompletionsModel), (
            f"Expected OpenAIChatCompletionsModel for explicit api='chat_completions', "
            f"got {type(model).__name__}."
        )
        assert isinstance(model._client, AsyncOpenAI)
        assert model._client.api_key == "sk-custom"
        assert model.model == "gpt-4.1-mini"

    def test_no_override_on_cloud_with_key_preserves_responses_default(self):
        """Sanity: api=None preserves current behavior (Responses for cloud+key).
        Already passes today, must keep passing."""
        spec = ModelEndpointConfig(
            name="openai/gpt-4.1-mini",
            api_key="sk-custom",
        )

        model = resolve_model(spec)

        assert isinstance(model, OpenAIResponsesModel)


class TestApiOverrideOnBareCloud:
    """openai/<n> alone (no base_url, no api_key) with explicit api override.

    The override forces a concrete class wrapping AsyncOpenAI(), which falls
    back to the OPENAI_API_KEY env var. Without the override we keep the bare
    string passthrough."""

    def test_chat_completions_override_on_bare_cloud(self):
        spec = ModelEndpointConfig(
            name="openai/gpt-4.1-mini",
            api="chat_completions",
        )

        model = resolve_model(spec)

        assert isinstance(model, OpenAIChatCompletionsModel), (
            f"Expected OpenAIChatCompletionsModel for explicit api override "
            f"on bare cloud spec, got {type(model).__name__}."
        )
        assert isinstance(model._client, AsyncOpenAI)
        assert model.model == "gpt-4.1-mini"

    def test_responses_override_on_bare_cloud(self):
        spec = ModelEndpointConfig(
            name="openai/gpt-4.1-mini",
            api="responses",
        )

        model = resolve_model(spec)

        assert isinstance(model, OpenAIResponsesModel)
        assert isinstance(model._client, AsyncOpenAI)
        assert model.model == "gpt-4.1-mini"

    def test_no_override_on_bare_cloud_preserves_passthrough(self):
        """Sanity: api=None keeps the bare-string passthrough. Already passes
        today, must keep passing."""
        spec = ModelEndpointConfig(name="openai/gpt-4.1-mini")

        model = resolve_model(spec)

        assert model == "openai/gpt-4.1-mini"


class TestApiOverrideIgnoredOnLitellm:
    """The api field is meaningless on the litellm/ path — LiteLLM handles its
    own routing. We must NOT try to wrap litellm specs in OpenAI*Model."""

    def test_responses_override_on_litellm_still_returns_litellm(self):
        spec = ModelEndpointConfig(
            name="litellm/mistral/mistral-medium-latest",
            api_key="key",
            api="responses",
        )

        model = resolve_model(spec)

        assert isinstance(model, LitellmModel), (
            "litellm/ prefix must always resolve to LitellmModel; the api "
            "override only applies to the openai/ path."
        )

    def test_chat_completions_override_on_litellm_still_returns_litellm(self):
        spec = ModelEndpointConfig(
            name="litellm/anthropic/claude-3-7-sonnet-20250219",
            api_key="key",
            api="chat_completions",
        )

        model = resolve_model(spec)

        assert isinstance(model, LitellmModel)


class TestApiOverrideViaDictSpec:
    """Dict-shaped specs (used by some call sites) must also honor the override."""

    def test_dict_with_responses_override(self):
        spec = {
            "name": "openai/gpt-oss-20b",
            "base_url": "http://vllm:8004/v1",
            "api_key": "dummy",
            "api": "responses",
        }

        model = resolve_model(spec)

        assert isinstance(model, OpenAIResponsesModel)
        assert model.model == "gpt-oss-20b"
