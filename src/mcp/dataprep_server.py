"""Serveur MCP pour les fonctions de préparation de données."""

import argparse
import logging
import os
from typing import Any

from fastmcp import FastMCP

from ..config import get_config
from ..dataprep.mcp_functions import (
    download_and_store_url,
    get_knowledge_entries,
    upload_files_to_vectorstore,
)
from ..logging_config import setup_server_logging

logger = logging.getLogger(__name__)


def _summarize_inputs_for_log(inputs: list[str], max_items: int = 3, max_len: int = 200) -> str:
    """
    Résume une liste d'inputs sans logger la liste entière (peut être volumineuse/sensible).
    """
    preview = inputs[:max_items]
    preview_str = ", ".join(repr(x) for x in preview)
    if len(preview_str) > max_len:
        preview_str = preview_str[:max_len] + "..."
    suffix = "" if len(inputs) <= max_items else f", ... (+{len(inputs) - max_items} more)"
    return f"[{preview_str}{suffix}]"


def create_dataprep_server() -> FastMCP:
    """Crée le serveur MCP pour les fonctions dataprep."""

    mcp = FastMCP(
        name="DataPrep MCP Server",
        instructions="""
        Serveur MCP pour la préparation de données et gestion de vector stores locaux.
        
        Outils disponibles:
        - download_and_store_url: Télécharge et stocke une URL dans le système local
        - upload_files_to_vectorstore: Indexation locale des fichiers dans le vector store
        - get_knowledge_entries: Liste les entrées de la base de connaissances
        - check_vectorstore_file_status: Vérifie l'état des fichiers dans un vector store
        """,
    )

    @mcp.tool()
    def download_and_store_url_tool(url: str) -> str:
        """
        Télécharge et stocke une URL dans le système de gestion de connaissances local.

        Args:
            url: URL à télécharger et stocker

        Returns:
            str: Nom du fichier local créé (.md)
        """
        logger.info(f"[MCP Tool] download_and_store_url called with url={url}")
        config = get_config()
        try:
            result = download_and_store_url(url, config)
            logger.info(f"[MCP Tool] download_and_store_url completed successfully: {result}")
            return result
        except Exception as e:
            logger.exception(f"[MCP Tool] download_and_store_url failed: {e}")
            raise

    @mcp.tool()
    def upload_files_to_vectorstore_tool(
        inputs: list[str], vectorstore_name: str
    ) -> dict[str, Any]:
        """
        Indexation locale des fichiers dans le vector store.

        Args:
            inputs: Liste d'URLs (qui seront résolues) ou noms de fichiers locaux
            vectorstore_name: Nom du vector store à créer

        Returns:
            Dict contenant vectorstore_id et informations sur les fichiers uploadés
        """
        logger.info(
            "[MCP Tool] upload_files_to_vectorstore called with "
            f"inputs_count={len(inputs)}, inputs_preview={_summarize_inputs_for_log(inputs)}, "
            f"vectorstore_name={vectorstore_name!r}"
        )
        config = get_config()
        try:
            logger.debug("[MCP Tool] Starting upload_files_to_vectorstore...")
            result = upload_files_to_vectorstore(inputs, config, vectorstore_name)
            logger.info(
                f"[MCP Tool] upload_files_to_vectorstore completed: "
                f"vectorstore_id={result.vectorstore_id}, "
                f"upload_count={result.upload_count}, "
                f"reuse_count={result.reuse_count}"
            )
            return result.model_dump()
        except Exception as e:
            logger.exception(f"[MCP Tool] upload_files_to_vectorstore failed: {e}")
            raise

    @mcp.tool()
    def get_knowledge_entries_tool() -> list[dict[str, Any]]:
        """
        Liste toutes les entrées de la base de connaissances.

        Returns:
            List[Dict]: Liste des entrées avec url, filename, title, keywords, openai_file_id
        """
        logger.info("[MCP Tool] get_knowledge_entries called")
        config = get_config()
        try:
            result = get_knowledge_entries(config)
            logger.info(f"[MCP Tool] get_knowledge_entries returned {len(result)} entries")
            return result
        except Exception as e:
            logger.exception(f"[MCP Tool] get_knowledge_entries failed: {e}")
            raise

    # @mcp.tool()
    # def check_vectorstore_file_status(
    #     vectorstore_id: str,
    #     file_ids: List[str]
    # ) -> Dict[str, List[Dict[str, Any]]]:
    #     """
    #     Vérifie l'état de traitement des fichiers dans un vector store.

    #     Args:
    #         vectorstore_id: ID du vector store
    #         file_ids: Liste des IDs de fichiers à vérifier

    #     Returns:
    #         Dict avec statut de chaque fichier
    #     """
    #     client = OpenAI()
    #     results = []

    #     for file_id in file_ids:
    #         try:
    #             vector_store_file = client.vector_stores.files.retrieve(
    #                 vector_store_id=vectorstore_id,
    #                 file_id=file_id
    #             )
    #             results.append({
    #                 'file_id': file_id,
    #                 'status': vector_store_file.status,
    #                 'last_error': vector_store_file.last_error
    #             })
    #         except Exception as e:
    #             results.append({
    #                 'file_id': file_id,
    #                 'status': 'error',
    #                 'error': str(e)
    #             })

    #     return {'files': results}

    return mcp


def start_server(host: str = "0.0.0.0", port: int = 8001):
    """Démarre le serveur MCP dataprep."""
    server = create_dataprep_server()
    logger.info(f"Starting DataPrep MCP Server on {host}:{port}")
    logger.info("Server ready to accept connections")
    server.run(transport="sse", host=host, port=port)


def main():
    """Démarre le serveur MCP dataprep."""
    parser = argparse.ArgumentParser(description="DataPrep MCP Server")
    parser.add_argument(
        "--config",
        type=str,
        help="Configuration file to use (default: configs/config-default.yaml)",
    )
    parser.add_argument("--host", type=str, help="Server host override")
    parser.add_argument("--port", type=int, help="Server port override")
    args = parser.parse_args()

    config = get_config(args.config)
    host = args.host or config.mcp.server_host
    port = args.port or config.mcp.server_port

    # Set up rolling file logging for long-running server
    log_file = setup_server_logging(
        log_level="INFO",
        silence_third_party=True,
        third_party_level="ERROR",
    )
    logger.info(f"DataPrep MCP Server log file: {log_file}")
    logger.info(f"App version: {os.getenv('APP_VERSION', 'unknown')}")
    start_server(host=host, port=port)


if __name__ == "__main__":
    main()
