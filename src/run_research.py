"""Core research run logic, shared by CLI and MCP server (Issue 83)."""

from __future__ import annotations

import importlib
import logging
import os
import shlex
import tempfile
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack

from langsmith.wrappers import OpenAIAgentsTracingProcessor

from agents import add_trace_processor
from agents.mcp import MCPServerSse, MCPServerStdio

from .agents.schemas import ReportData, ResearchInfo
from .agents.utils import context_aware_filter
from .config import get_config
from .dataprep.vector_backends import get_vector_backend
from .logging_config import setup_run_logging
from .tracing.trace_processor import FileTraceProcessor

ProgressCallback = Callable[[float, float | None, str | None], Awaitable[None]]


def get_manager_class(manager_path: str):
    """Dynamically import and return a manager class from a path string."""
    if not manager_path or "." not in manager_path:
        if manager_path == "agentic_manager":
            from .agentic_manager import AgenticResearchManager

            return AgenticResearchManager
        if manager_path == "manager":
            from .manager import StandardResearchManager

            return StandardResearchManager
        if manager_path == "deep_manager":
            from .deep_research_manager import DeepResearchManager

            return DeepResearchManager
        if manager_path == "qa_manager":
            from .qa_manager import QAManager

            return QAManager
        raise ValueError(f"Unknown manager: {manager_path}")

    module_path, class_name = manager_path.rsplit(".", 1)
    module = importlib.import_module(f".{module_path}", package="src")
    return getattr(module, class_name)


async def run_research_async(
    query: str,
    *,
    config_path: str | None = None,
    manager: str | None = None,
    vector_store: str | None = None,
    output_dir: str | None = None,
    debug: bool = False,
    dataprep_host: str | None = None,
    dataprep_port: int | None = None,
    max_search_plan: str | None = None,
    setup_logging: bool = True,
    progress_callback: ProgressCallback | None = None,
) -> ReportData | None:
    """
    Run a full research workflow (query or syllabus content).

    progress_callback(progress, total, message) is called at phase boundaries
    when provided (e.g. for MCP progress notifications).

    Returns ReportData for managers that produce a report (agentic_manager, deep_manager),
    None otherwise.
    """
    os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"

    config = get_config(config_path)
    if setup_logging:
        log_file = setup_run_logging(
            log_level=config.logging.level,
            silence_third_party=config.logging.silence_third_party,
            third_party_level=config.logging.third_party_level,
        )
    logger = logging.getLogger("agentic-research")
    if setup_logging:
        logger.info(f"Log file for this run: {log_file}")
    logger.info(f"App version: {os.getenv('APP_VERSION', 'unknown')}")

    manager_name = manager or config.manager.default_manager
    if vector_store:
        config.vector_store.name = vector_store
    if max_search_plan:
        config.agents.max_search_plan = max_search_plan
    if output_dir:
        config.agents.output_dir = output_dir
        if not os.path.exists(config.agents.output_dir):
            os.makedirs(config.agents.output_dir)
    config.debug.enabled = debug
    if dataprep_host:
        config.mcp.server_host = dataprep_host
    if dataprep_port is not None:
        config.mcp.server_port = dataprep_port

    manager_class = get_manager_class(manager_name)
    add_trace_processor(OpenAIAgentsTracingProcessor())
    add_trace_processor(FileTraceProcessor(log_dir="traces", log_file="trace.log"))

    with tempfile.TemporaryDirectory(delete=not debug) as temp_dir:
        fs_command = os.getenv("MCP_FS_COMMAND")
        fs_args = os.getenv("MCP_FS_ARGS")
        if fs_command:
            fs_args_list = shlex.split(fs_args) if fs_args else []
            fs_args_list.append(temp_dir)
        else:
            fs_command = "npx"
            fs_args_list = ["-y", "@modelcontextprotocol/server-filesystem", temp_dir]

        fs_server = MCPServerStdio(
            name="FS_MCP_SERVER",
            params={"command": fs_command, "args": fs_args_list},
            tool_filter=context_aware_filter,
            cache_tools_list=True,
        )
        canonical_tmp_dir = os.path.realpath(temp_dir)

        dataprep_url = os.getenv(
            "MCP_DATAPREP_URL",
            f"http://{config.mcp.server_host}:{config.mcp.server_port}/sse",
        )
        dataprep_server = MCPServerSse(
            name="DATAPREP_MCP_SERVER",
            params={"url": dataprep_url, "timeout": config.mcp.http_timeout_seconds},
            client_session_timeout_seconds=config.mcp.client_timeout_seconds,
        )
        vector_mcp_server = None

        async with AsyncExitStack() as stack:
            await stack.enter_async_context(fs_server)
            await stack.enter_async_context(dataprep_server)

            backend = get_vector_backend(config)
            vector_store_id = backend.resolve_store_id(
                config.vector_store.name, config
            )
            config.vector_store.vector_store_id = vector_store_id
            research_info = ResearchInfo(
                vector_store_name=config.vector_store.name,
                vector_store_id=vector_store_id,
                temp_dir=canonical_tmp_dir,
                max_search_plan=config.agents.max_search_plan,
                output_dir=config.agents.output_dir,
            )

            result: ReportData | None = await manager_class().run(
                dataprep_server=dataprep_server,
                fs_server=fs_server,
                vector_mcp_server=vector_mcp_server,
                query=query,
                research_info=research_info,
                progress_callback=progress_callback,
            )
            return result
