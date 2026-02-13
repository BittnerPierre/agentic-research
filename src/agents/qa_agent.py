"""Minimal QA agent for local smoke tests."""

from __future__ import annotations

from agents import Agent, RunContextWrapper
from agents.models import get_default_model_settings

from ..config import get_config
from .schemas import ResearchInfo
from .utils import adjust_model_settings_for_base_url, extract_model_name, resolve_model
from .vector_search_tool import vector_search


def qa_instructions(context: RunContextWrapper[ResearchInfo], agent: Agent[ResearchInfo]) -> str:
    return (
        "You are a QA agent. Use the `vector_search` tool to retrieve evidence for the user "
        "question. Use only retrieved information in your answer and keep it to 2-4 sentences."
    )


def create_qa_agent():
    config = get_config()
    model_spec = config.models.search_model
    model = resolve_model(model_spec)

    model_name = extract_model_name(model_spec)
    model_settings = get_default_model_settings(model_name)
    adjust_model_settings_for_base_url(model_spec, model_settings)

    return Agent(
        name="qa_agent",
        instructions=qa_instructions,
        tools=[vector_search],
        model=model,
        model_settings=model_settings,
        output_type=str,
    )
