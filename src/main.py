import argparse
import asyncio
import importlib
import logging
import os
import shlex
import tempfile
from contextlib import AsyncExitStack
from pathlib import Path

# LangSmith tracing support
from langsmith.wrappers import OpenAIAgentsTracingProcessor

from agents import add_trace_processor
from agents.mcp import MCPServerSse, MCPServerStdio

from .agents.schemas import ResearchInfo
from .agents.utils import context_aware_filter
from .config import get_config
from .dataprep.vector_backends import get_vector_backend
from .logging_config import setup_run_logging
from .tracing.trace_processor import FileTraceProcessor


def get_manager_class(manager_path: str):
    """Dynamically import and return a manager class from a path string."""
    if not manager_path or "." not in manager_path:
        # Default managers
        if manager_path == "agentic_manager":
            from .agentic_manager import AgenticResearchManager

            return AgenticResearchManager
        elif manager_path == "manager":
            from .manager import StandardResearchManager

            return StandardResearchManager
        elif manager_path == "deep_manager":
            from .deep_research_manager import DeepResearchManager

            return DeepResearchManager
        elif manager_path == "qa_manager":
            from .qa_manager import QAManager

            return QAManager
        else:
            raise ValueError(f"Unknown manager: {manager_path}")

    # For custom managers with format like "module.ClassName"
    module_path, class_name = manager_path.rsplit(".", 1)
    module = importlib.import_module(f".{module_path}", package="src")
    return getattr(module, class_name)


async def main() -> None:
    os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"

    # Parse command line arguments first (without defaults that depend on config)
    parser = argparse.ArgumentParser(description="Agentic Research CLI")
    parser.add_argument("--syllabus", type=str, help="Path to a syllabus file")
    parser.add_argument("--manager", type=str, help="Manager implementation to use")
    parser.add_argument(
        "--query", type=str, help="Research query (alternative to interactive input)"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Configuration file to use (default: configs/config-default.yaml)",
    )
    parser.add_argument(
        "--vector-store", type=str, help="Name of the vector store to use (overrides config)"
    )
    parser.add_argument("--dataprep-host", type=str, help="DataPrep MCP server host override")
    parser.add_argument("--dataprep-port", type=int, help="DataPrep MCP server port override")
    parser.add_argument(
        "--max-search-plan", type=str, help="Maximum number of search plans to generate"
    )
    parser.add_argument("--output-dir", type=str, help="Output directory")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    args = parser.parse_args()

    # Get configuration (potentially with custom config file)
    config = get_config(args.config)

    # Set up logging for this run (creates timestamped log file)
    log_file = setup_run_logging(
        log_level=config.logging.level,
        silence_third_party=config.logging.silence_third_party,
        third_party_level=config.logging.third_party_level,
    )
    logger = logging.getLogger("agentic-research")
    logger.info(f"Log file for this run: {log_file}")
    logger.info(f"App version: {os.getenv('APP_VERSION', 'unknown')}")
    logger.info(f"Command line arguments: {vars(args)}")

    # Set defaults from config if not provided via CLI
    if not args.manager:
        args.manager = config.manager.default_manager
    if not args.vector_store:
        args.vector_store = config.vector_store.name
    if not args.max_search_plan:
        args.max_search_plan = config.agents.max_search_plan
    if not args.output_dir:
        args.output_dir = config.agents.output_dir
    if not args.debug:
        args.debug = config.debug.enabled

    # Override vector store name if provided
    if args.vector_store:
        config.vector_store.name = args.vector_store
        logger.info(f"Using custom vector store name: {args.vector_store}")

    # Get the appropriate manager class
    logger.info(f"Using manager: {args.manager}")
    manager_class = get_manager_class(args.manager)

    if args.max_search_plan:
        config.agents.max_search_plan = args.max_search_plan
        logger.info(f"Using custom max search plan: {args.max_search_plan}")

    if args.output_dir:
        config.agents.output_dir = args.output_dir
        logger.info(f"Using custom output directory: {args.output_dir}")
        if not os.path.exists(config.agents.output_dir):
            os.makedirs(config.agents.output_dir)

    if args.debug:
        config.debug.enabled = args.debug
        logger.info(f"Using custom debug mode: {args.debug}")

    if args.dataprep_host:
        config.mcp.server_host = args.dataprep_host
        logger.info(f"Using custom DataPrep host: {args.dataprep_host}")
    if args.dataprep_port:
        config.mcp.server_port = args.dataprep_port
        logger.info(f"Using custom DataPrep port: {args.dataprep_port}")

    # Get input: either from syllabus file, command line argument, or interactive input
    if args.syllabus:
        syllabus_path = Path(args.syllabus)
        if not syllabus_path.exists():
            logger.error(f"Syllabus file not found: {args.syllabus}")
            return

        with open(syllabus_path, encoding="utf-8") as f:
            syllabus_content = f.read()
            query = f"<research_request>\n{syllabus_content}\n</research_request>"
        logger.info(f"Using syllabus from file: {args.syllabus}")
    elif args.query:
        query = f"<research_request>\n{args.query}\n</research_request>"
    else:
        query = (
            f"<research_request>\n{input("What would you like to research? ")}\n</research_request>"
        )

    add_trace_processor(OpenAIAgentsTracingProcessor())
    add_trace_processor(FileTraceProcessor(log_dir="traces", log_file="trace.log"))
    debug_mode = config.debug.enabled
    logger.info(f"Debug mode: {debug_mode}")

    logger.info("Setting up MCP servers...")
    with tempfile.TemporaryDirectory(delete=not debug_mode) as temp_dir:
        fs_command = os.getenv("MCP_FS_COMMAND")
        fs_args = os.getenv("MCP_FS_ARGS")
        if fs_command:
            args = shlex.split(fs_args) if fs_args else []
            args.append(temp_dir)
        else:
            fs_command = "npx"
            args = ["-y", "@modelcontextprotocol/server-filesystem", temp_dir]

        fs_server = MCPServerStdio(
            name="FS_MCP_SERVER",
            params={
                "command": fs_command,
                "args": args,
            },
            tool_filter=context_aware_filter,
            cache_tools_list=True,
        )
        canonical_tmp_dir = os.path.realpath(temp_dir)
        logger.info(f"Filesystem MCP server temp directory: {canonical_tmp_dir}")

        dataprep_url = os.getenv(
            "MCP_DATAPREP_URL",
            f"http://{config.mcp.server_host}:{config.mcp.server_port}/sse",
        )
        dataprep_server = MCPServerSse(
            name="DATAPREP_MCP_SERVER",
            params={
                "url": dataprep_url,
                "timeout": config.mcp.http_timeout_seconds,
            },
            client_session_timeout_seconds=config.mcp.client_timeout_seconds,
        )
        logger.info(
            f"Connecting to DataPrep MCP server at {dataprep_url} "
            f"(http timeout: {config.mcp.http_timeout_seconds}s, "
            f"client session timeout: {config.mcp.client_timeout_seconds}s)"
        )
        vector_mcp_server = None
        if config.vector_search.provider == "chroma":
            allowlist = set(config.vector_mcp.tool_allowlist)

            def chroma_tool_filter(_context, tool):
                return tool.name in allowlist

            chroma_env = dict(os.environ)
            chroma_env.update(
                {
                    "ANONYMIZED_TELEMETRY": "False",
                    "HTTPX_LOG_LEVEL": "ERROR",
                    "HTTPCORE_LOG_LEVEL": "ERROR",
                    "FASTMCP_LOG_LEVEL": "ERROR",
                }
            )

            vector_mcp_server = MCPServerStdio(
                name="CHROMA_MCP_SERVER",
                params={
                    "command": config.vector_mcp.command,
                    "args": config.vector_mcp.args,
                    "env": chroma_env,
                },
                tool_filter=chroma_tool_filter,
                cache_tools_list=True,
                client_session_timeout_seconds=config.vector_mcp.client_timeout_seconds,
            )

        async with AsyncExitStack() as stack:
            await stack.enter_async_context(fs_server)
            await stack.enter_async_context(dataprep_server)
            if vector_mcp_server is not None:
                await stack.enter_async_context(vector_mcp_server)

            logger.info("MCP servers connected successfully")
            backend = get_vector_backend(config)
            config.vector_store.vector_store_id = backend.resolve_store_id(
                config.vector_store.name, config
            )

            research_info = ResearchInfo(
                vector_store_name=config.vector_store.name,
                vector_store_id=config.vector_store.vector_store_id,
                temp_dir=canonical_tmp_dir,
                max_search_plan=config.agents.max_search_plan,
                output_dir=config.agents.output_dir,
            )
            logger.info(f"Research info: {research_info}")

            logger.info(f"Starting research with manager: {manager_class.__name__}")
            logger.info(f"Query: {query[:200]}...")

            try:
                await manager_class().run(
                    dataprep_server=dataprep_server,
                    fs_server=fs_server,
                    vector_mcp_server=vector_mcp_server,
                    query=query,
                    research_info=research_info,
                )
                logger.info("Research completed successfully")
            except Exception as e:
                logger.exception(f"Research failed with error: {e}")
                raise


def cli_main():
    """Sync entrypoint for Poetry scripts."""
    asyncio.run(main())


if __name__ == "__main__":
    cli_main()
