"""TDD red tests for issue #170 — per-agent reasoning_effort and verbosity.

Documents the expected behavior of ModelEndpointConfig.reasoning_effort and
ModelEndpointConfig.verbosity once the agent factories graft them onto
ModelSettings.

Today the factories build ModelSettings via get_default_model_settings() and
never look at the new fields, so .reasoning and .verbosity stay None even when
the spec sets them. After #170:

- spec.reasoning_effort -> model_settings.reasoning = Reasoning(effort=...)
- spec.verbosity        -> model_settings.verbosity = "<level>"

Scope: openai/ specs (gpt-oss/vLLM, o-series, gpt-5). On litellm/ specs the
fields are also forwarded — LiteLLM passes reasoning_effort through for
supported providers — but family-specific behavior is out of scope (no
adapter, no clamping per #170 design discussion).

The helper is named `apply_endpoint_model_settings()` and lives in
src/agents/utils.py next to adjust_model_settings_for_base_url().
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from agents.model_settings import ModelSettings

from src.agents.utils import apply_endpoint_model_settings
from src.config import Config, ModelEndpointConfig, VectorStoreConfig

# ---------------------------------------------------------------------------
# Unit tests on the helper (apply_endpoint_model_settings)
# ---------------------------------------------------------------------------


class TestApplyEndpointModelSettings:
    """Helper grafts reasoning_effort/verbosity from a spec onto ModelSettings."""

    def test_reasoning_effort_grafted_from_pydantic_spec(self):
        spec = ModelEndpointConfig(
            name="openai/gpt-oss-20b",
            base_url="http://vllm:8004/v1",
            api_key="dummy",
            api="responses",
            reasoning_effort="high",
        )
        ms = ModelSettings()

        apply_endpoint_model_settings(spec, ms)

        assert ms.reasoning is not None, (
            "Helper must instantiate Reasoning(effort=...) when reasoning_effort is set."
        )
        assert ms.reasoning.effort == "high"

    def test_verbosity_grafted_from_pydantic_spec(self):
        spec = ModelEndpointConfig(
            name="openai/gpt-5-mini",
            api_key="sk-test",
            verbosity="low",
        )
        ms = ModelSettings()

        apply_endpoint_model_settings(spec, ms)

        assert ms.verbosity == "low"

    def test_both_fields_grafted_together(self):
        spec = ModelEndpointConfig(
            name="openai/gpt-oss-20b",
            base_url="http://vllm:8004/v1",
            api_key="dummy",
            api="responses",
            reasoning_effort="medium",
            verbosity="high",
        )
        ms = ModelSettings()

        apply_endpoint_model_settings(spec, ms)

        assert ms.reasoning is not None and ms.reasoning.effort == "medium"
        assert ms.verbosity == "high"

    def test_no_fields_set_leaves_settings_unchanged(self):
        spec = ModelEndpointConfig(
            name="openai/local-llm",
            base_url="http://llama-cpp-cpu:8002",
            api_key="dummy",
        )
        ms = ModelSettings()

        apply_endpoint_model_settings(spec, ms)

        assert ms.reasoning is None
        assert ms.verbosity is None

    def test_dict_spec_supported(self):
        """Dict-shaped specs (used by some call sites / tests) must work too."""
        spec = {
            "name": "openai/gpt-oss-20b",
            "base_url": "http://vllm:8004/v1",
            "api_key": "dummy",
            "api": "responses",
            "reasoning_effort": "low",
            "verbosity": "medium",
        }
        ms = ModelSettings()

        apply_endpoint_model_settings(spec, ms)

        assert ms.reasoning is not None and ms.reasoning.effort == "low"
        assert ms.verbosity == "medium"

    def test_bare_string_spec_is_noop(self):
        """Plain string model spec ('openai/gpt-4.1-mini') has no fields to graft."""
        ms = ModelSettings()

        apply_endpoint_model_settings("openai/gpt-4.1-mini", ms)

        assert ms.reasoning is None
        assert ms.verbosity is None

    def test_none_effort_is_grafted_explicitly(self):
        """`reasoning_effort='none'` is a meaningful value (gpt-5.1 default,
        gpt-oss "no thinking" mode), not the same as omitting the field."""
        spec = ModelEndpointConfig(
            name="openai/gpt-5-1",
            api_key="sk-test",
            reasoning_effort="none",
        )
        ms = ModelSettings()

        apply_endpoint_model_settings(spec, ms)

        assert ms.reasoning is not None
        assert ms.reasoning.effort == "none"

    def test_existing_reasoning_settings_preserved_when_field_absent(self):
        """If the helper is called on settings that already carry reasoning
        from another source, it must not clobber them when the spec is silent."""
        from openai.types.shared.reasoning import Reasoning

        spec = ModelEndpointConfig(
            name="openai/local-llm",
            base_url="http://llama-cpp-cpu:8002",
            api_key="dummy",
        )
        ms = ModelSettings(reasoning=Reasoning(effort="low"), verbosity="high")

        apply_endpoint_model_settings(spec, ms)

        assert ms.reasoning is not None and ms.reasoning.effort == "low"
        assert ms.verbosity == "high"


# ---------------------------------------------------------------------------
# Integration tests — factories must call the helper
# ---------------------------------------------------------------------------


@pytest.fixture
def docker_dgx_like_config(tmp_path):
    """Mirror configs/config-docker-dgx.yaml — every model on a vLLM endpoint
    with reasoning_effort/verbosity set, so we can prove every factory grafts
    them onto its agent's ModelSettings."""
    config = Config(
        config_name="test-docker-dgx",
        vector_store=VectorStoreConfig(name="test-vs"),
    )
    vllm_endpoint = ModelEndpointConfig(
        name="openai/gpt-oss-20b",
        base_url="http://vllm:8004/v1",
        api_key="dummy",
        api="responses",
        reasoning_effort="high",
        verbosity="medium",
    )
    config.models.research_model = vllm_endpoint
    config.models.planning_model = vllm_endpoint
    config.models.search_model = vllm_endpoint
    config.models.writer_model = vllm_endpoint
    config.models.knowledge_preparation_model = vllm_endpoint
    config.agents.output_dir = str(tmp_path)
    config.agents.writer_output_format = "markdown"
    config.vector_search.provider = "chroma"
    return config


def _assert_reasoning_and_verbosity_grafted(agent):
    ms = agent.model_settings
    assert ms.reasoning is not None, (
        f"Agent {agent.name!r} did not graft reasoning from spec.reasoning_effort. "
        f"Expected ModelSettings.reasoning.effort='high'."
    )
    assert ms.reasoning.effort == "high"
    assert ms.verbosity == "medium", (
        f"Agent {agent.name!r} did not graft verbosity from spec.verbosity. "
        f"Expected 'medium', got {ms.verbosity!r}."
    )


def test_planner_agent_grafts_reasoning_and_verbosity(docker_dgx_like_config):
    from src.agents import file_search_planning_agent as mod

    with patch.object(mod, "get_config", return_value=docker_dgx_like_config):
        agent = mod.create_file_planner_agent()

    _assert_reasoning_and_verbosity_grafted(agent)


def test_file_search_agent_grafts_reasoning_and_verbosity(docker_dgx_like_config):
    from src.agents import file_search_agent as mod

    with patch.object(mod, "get_config", return_value=docker_dgx_like_config):
        agent = mod.create_file_search_agent(vector_store_id="vs_test")

    _assert_reasoning_and_verbosity_grafted(agent)


def test_writer_agent_grafts_reasoning_and_verbosity(docker_dgx_like_config):
    from src.agents import file_writer_agent as mod

    with patch.object(mod, "get_config", return_value=docker_dgx_like_config):
        agent = mod.create_writer_agent()

    _assert_reasoning_and_verbosity_grafted(agent)


def test_knowledge_preparation_agent_grafts_reasoning_and_verbosity(docker_dgx_like_config):
    from src.agents import knowledge_preparation_agent as mod

    with patch.object(mod, "get_config", return_value=docker_dgx_like_config):
        agent = mod.create_knowledge_preparation_agent()

    _assert_reasoning_and_verbosity_grafted(agent)


def test_qa_agent_grafts_reasoning_and_verbosity(docker_dgx_like_config):
    from src.agents import qa_agent as mod

    with patch.object(mod, "get_config", return_value=docker_dgx_like_config):
        agent = mod.create_qa_agent()

    _assert_reasoning_and_verbosity_grafted(agent)
