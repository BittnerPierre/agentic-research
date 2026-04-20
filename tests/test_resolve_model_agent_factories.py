"""Integration tests for issue #158 — agent factories must NOT route through
LiteLLM when configured against a local OpenAI-compatible endpoint.

These mirror the configs/config-docker-local.yaml shape (every agent pointed at
openai/local-llm with a base_url). They build each public agent factory and
inspect agent.model. Today they fail because resolve_model() wraps every
ModelEndpointConfig in LitellmModel.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from agents.extensions.models.litellm_model import LitellmModel

from agents import OpenAIChatCompletionsModel
from src.config import Config, ModelEndpointConfig, VectorStoreConfig


@pytest.fixture
def docker_local_config(tmp_path):
    """Mirror configs/config-docker-local.yaml — every model on the local stack."""
    config = Config(
        config_name="test-docker-local",
        vector_store=VectorStoreConfig(name="test-vs"),
    )
    local_endpoint = ModelEndpointConfig(
        name="openai/local-llm",
        base_url="http://llama-cpp-cpu:8002",
        api_key="dummy",
    )
    config.models.research_model = local_endpoint
    config.models.planning_model = local_endpoint
    config.models.search_model = local_endpoint
    config.models.writer_model = local_endpoint
    config.models.knowledge_preparation_model = local_endpoint
    config.agents.output_dir = str(tmp_path)
    config.agents.writer_output_format = "markdown"
    config.vector_search.provider = "chroma"
    return config


def _assert_native_openai(agent):
    assert not isinstance(agent.model, LitellmModel), (
        f"Agent {agent.name!r} routes through LitellmModel for an openai/+base_url "
        "config (issue #158). Expected OpenAIChatCompletionsModel."
    )
    assert isinstance(agent.model, OpenAIChatCompletionsModel)


def test_planner_agent_uses_native_openai(docker_local_config):
    from src.agents import file_search_planning_agent as mod

    with patch.object(mod, "get_config", return_value=docker_local_config):
        agent = mod.create_file_planner_agent()

    _assert_native_openai(agent)


def test_file_search_agent_uses_native_openai(docker_local_config):
    from src.agents import file_search_agent as mod

    with patch.object(mod, "get_config", return_value=docker_local_config):
        agent = mod.create_file_search_agent(vector_store_id="vs_test")

    _assert_native_openai(agent)


def test_writer_agent_uses_native_openai(docker_local_config):
    from src.agents import file_writer_agent as mod

    with patch.object(mod, "get_config", return_value=docker_local_config):
        agent = mod.create_writer_agent()

    _assert_native_openai(agent)


def test_knowledge_preparation_agent_uses_native_openai(docker_local_config):
    from src.agents import knowledge_preparation_agent as mod

    with patch.object(mod, "get_config", return_value=docker_local_config):
        agent = mod.create_knowledge_preparation_agent()

    _assert_native_openai(agent)


def test_qa_agent_uses_native_openai(docker_local_config):
    from src.agents import qa_agent as mod

    with patch.object(mod, "get_config", return_value=docker_local_config):
        agent = mod.create_qa_agent()

    _assert_native_openai(agent)
