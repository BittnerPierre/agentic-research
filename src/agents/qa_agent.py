"""Minimal QA agent for local smoke tests."""

from __future__ import annotations

from agents import Agent, RunContextWrapper
from agents.mcp import MCPServer
from agents.models import get_default_model_settings

from ..config import get_config
from .schemas import ResearchInfo
from .utils import adjust_model_settings_for_base_url, extract_model_name, resolve_model


def qa_instructions(context: RunContextWrapper[ResearchInfo], agent: Agent[ResearchInfo]) -> str:
    collection = context.context.vector_store_name
    return (
        "You are a QA agent. Use the MCP tool `chroma_query_documents` to search "
        f"collection `{collection}` for the user question. "
        "Then answer in 2-4 sentences using only retrieved information."
    )


def create_qa_agent(mcp_servers: list[MCPServer] | None = None):
    mcp_servers = mcp_servers or []

    config = get_config()
    model_spec = config.models.search_model
    model = resolve_model(model_spec)

    model_name = extract_model_name(model_spec)
    model_settings = get_default_model_settings(model_name)
    adjust_model_settings_for_base_url(model_spec, model_settings)

    return Agent(
        name="qa_agent",
        instructions=qa_instructions,
        model=model,
        model_settings=model_settings,
        mcp_servers=mcp_servers,
        output_type=str,
    )
