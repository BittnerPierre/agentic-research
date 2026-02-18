import argparse
import asyncio
import logging
import os
from pathlib import Path

from .config import get_config
from .logging_config import setup_run_logging
from .run_research import run_research_async


async def main() -> None:
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

    config = get_config(args.config)
    log_file = setup_run_logging(
        log_level=config.logging.level,
        silence_third_party=config.logging.silence_third_party,
        third_party_level=config.logging.third_party_level,
    )
    logger = logging.getLogger("agentic-research")
    logger.info(f"Log file for this run: {log_file}")
    logger.info(f"App version: {os.getenv('APP_VERSION', 'unknown')}")
    logger.info(f"Command line arguments: {vars(args)}")

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

    if args.vector_store:
        logger.info(f"Using custom vector store name: {args.vector_store}")
    logger.info(f"Using manager: {args.manager}")
    if args.max_search_plan:
        logger.info(f"Using custom max search plan: {args.max_search_plan}")
    if args.output_dir:
        logger.info(f"Using custom output directory: {args.output_dir}")
        if not os.path.exists(args.output_dir):
            os.makedirs(args.output_dir)
    if args.debug:
        logger.info(f"Using custom debug mode: {args.debug}")
    if args.dataprep_host:
        logger.info(f"Using custom DataPrep host: {args.dataprep_host}")
    if args.dataprep_port:
        logger.info(f"Using custom DataPrep port: {args.dataprep_port}")

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
            f"<research_request>\n{input('What would you like to research? ')}\n</research_request>"
        )

    try:
        await run_research_async(
            query,
            config_path=args.config,
            manager=args.manager,
            vector_store=args.vector_store,
            output_dir=args.output_dir,
            debug=args.debug,
            dataprep_host=args.dataprep_host,
            dataprep_port=args.dataprep_port,
            max_search_plan=args.max_search_plan,
            setup_logging=False,
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
