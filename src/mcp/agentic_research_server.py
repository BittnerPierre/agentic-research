"""MCP server exposing agentic-research as remote tools (query and syllabus modes). Issue 83."""

from __future__ import annotations

import logging
import os

from fastmcp import FastMCP

from ..agents.schemas import ReportData
from ..logging_config import setup_server_logging
from ..run_research import run_research_async

logger = logging.getLogger(__name__)


def _format_report(report: ReportData) -> str:
    """Format ReportData for MCP tool response."""
    parts = [
        f"research_topic: {report.research_topic}",
        f"short_summary: {report.short_summary}",
        "",
        "markdown_report:",
        report.markdown_report,
        "",
        "follow_up_questions:",
        *report.follow_up_questions,
    ]
    return "\n".join(parts)


def create_agentic_research_server() -> FastMCP:
    """Create the MCP server with research_query and research_syllabus tools."""
    mcp = FastMCP(
        name="Agentic Research MCP Server",
        instructions="""
        Serveur MCP pour lancer des recherches agentic-research depuis un client MCP.
        Deux modes: query (une requête texte) et syllabus (contenu type syllabus à explorer).
        Chaque outil lance une recherche complète (planning, search, report) et retourne le rapport.
        """,
    )

    @mcp.tool()
    async def research_query(query: str) -> str:
        """
        Lance une recherche sur une requête texte.

        Args:
            query: La requête de recherche (sujet ou question).

        Returns:
            Le rapport (résumé, rapport markdown, questions de suivi).
        """
        logger.info("[MCP Tool] research_query called with query=%s", query[:200] if query else "")
        wrapped = f"<research_request>\n{query}\n</research_request>"
        try:
            result = await run_research_async(wrapped, setup_logging=True)
            if result is None:
                return (
                    "ERROR: Manager did not return a report (use agentic_manager or deep_manager)."
                )
            return _format_report(result)
        except Exception as e:
            logger.exception("[MCP Tool] research_query failed: %s", e)
            return f"ERROR: research_query failed: {e}"

    @mcp.tool()
    async def research_syllabus(syllabus_content: str) -> str:
        """
        Lance une recherche à partir d'un contenu type syllabus (chapitres, thèmes).

        Args:
            syllabus_content: Le contenu du syllabus (texte libre).

        Returns:
            Le rapport (résumé, rapport markdown, questions de suivi).
        """
        logger.info(
            "[MCP Tool] research_syllabus called with syllabus_content length=%s",
            len(syllabus_content),
        )
        wrapped = f"<research_request>\n{syllabus_content}\n</research_request>"
        try:
            result = await run_research_async(wrapped, setup_logging=True)
            if result is None:
                return (
                    "ERROR: Manager did not return a report (use agentic_manager or deep_manager)."
                )
            return _format_report(result)
        except Exception as e:
            logger.exception("[MCP Tool] research_syllabus failed: %s", e)
            return f"ERROR: research_syllabus failed: {e}"

    return mcp


def start_server(
    host: str = "0.0.0.0",
    port: int = 8008,
    transport: str = "streamable-http",
    path: str = "/mcp",
) -> None:
    """Start the agentic-research MCP server (Streamable HTTP by default)."""
    server = create_agentic_research_server()
    logger.info("Starting Agentic Research MCP Server on %s:%s (%s)", host, port, transport)
    if transport == "streamable-http":
        server.run(transport="streamable-http", host=host, port=port, path=path)
    else:
        server.run(transport=transport, host=host, port=port)


def main() -> None:
    """CLI entrypoint for the agentic-research MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Agentic Research MCP Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8008, help="Bind port")
    parser.add_argument(
        "--transport",
        type=str,
        default="streamable-http",
        choices=["streamable-http", "sse"],
        help="MCP transport (streamable-http recommended)",
    )
    parser.add_argument("--path", type=str, default="/mcp", help="Path for streamable-http")
    parser.add_argument("--config", type=str, help="Config file (optional)")
    args = parser.parse_args()

    if args.config:
        from ..config import get_config

        get_config(args.config)
    log_file = setup_server_logging(
        log_level="INFO",
        silence_third_party=True,
        third_party_level="ERROR",
    )
    logger.info("Agentic Research MCP Server log file: %s", log_file)
    logger.info("App version: %s", os.getenv("APP_VERSION", "unknown"))
    start_server(host=args.host, port=args.port, transport=args.transport, path=args.path)


if __name__ == "__main__":
    main()
