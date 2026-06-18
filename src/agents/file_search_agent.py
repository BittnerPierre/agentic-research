from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX
from agents.mcp import MCPServer
from agents.models import get_default_model_settings

from agents import Agent, RunContextWrapper

from ..config import get_config
from .schemas import ResearchInfo
from .utils import (
    adjust_model_settings_for_base_url,
    enable_usage_for_litellm,
    extract_model_name,
    load_prompt_from_file,
    resolve_model,
)
from .vector_search_tool import vector_search

prompt_file = "file_search_prompt.md"


def dynamic_instructions(
    context: RunContextWrapper[ResearchInfo], agent: Agent[ResearchInfo]
) -> str:
    prompt_template = load_prompt_from_file("prompts", prompt_file)

    if prompt_template is None:
        raise ValueError(f"{prompt_file} is None")

    dynamic_prompt = prompt_template.format(RECOMMENDED_PROMPT_PREFIX=RECOMMENDED_PROMPT_PREFIX)

    return (
        f"{dynamic_prompt}"
        "Use ONLY the retrieval tool `vector_search` to access document content.\n"
        "Never try to open or read the source documents directly from the filesystem.\n"
        f"The absolute path to **temporary filesystem** is `{context.context.temp_dir}`."
        " You MUST use it to write and read temporary data.\n"
        "When calling write_file, always set `path` to "
        f"`{context.context.temp_dir}/<normalized_filename>.txt` and never write outside this "
        "directory.\n\n"
        # f"The absolute path to **output filesystem** is `{context.context.output_dir}`."
        #   " You MUST use it to write and read output final content.\n\n"
    )


def create_file_search_agent(
    mcp_servers: list[MCPServer] | None = None, vector_store_id: str | None = None
):
    mcp_servers = mcp_servers or []

    config = get_config()

    model_spec = config.models.search_model
    model = resolve_model(model_spec)
    model_name = extract_model_name(model_spec)
    model_settings = get_default_model_settings(model_name)
    adjust_model_settings_for_base_url(model_spec, model_settings)
    enable_usage_for_litellm(model_spec, model_settings)

    if config.vector_search.provider in {"openai", "local", "chroma"}:
        # Keep a single retrieval contract across providers to avoid provider-
        # specific prompt drift and direct filesystem fallbacks in the agent loop.
        tools = [vector_search]
    else:
        raise ValueError(f"Unknown vector_search.provider: {config.vector_search.provider}")

    file_search_agent = Agent(
        name="file_search_agent",
        handoff_description="Given a search topic, search through vectorized files and produce a clear, CONCISE and RELEVANT summary of the results.",
        instructions=dynamic_instructions,
        tools=tools,
        model=model,
        model_settings=model_settings,
        mcp_servers=mcp_servers,
    )

    return file_search_agent
