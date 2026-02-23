"""
Module de workflow pour le traitement des données avec les fonctions MCP DataPrep.
"""

import logging
from pathlib import Path

from ..config import get_config

# Import direct des fonctions MCP
from .mcp_functions import get_knowledge_entries

logger = logging.getLogger(__name__)


def analyze_knowledge_base(config):
    """Analyse l'état actuel de la base de connaissances."""
    logger.info("=== KNOWLEDGE BASE ANALYSIS ===")

    # État général
    entries = get_knowledge_entries(config)

    logger.info(f"📊 Total entries: {len(entries)}")

    # Compter les fichiers indexés localement
    indexed_count = sum(1 for entry in entries if entry.get("vector_doc_id"))
    logger.info(f"🔍 Locally indexed files: {indexed_count}")

    # Vérifier les fichiers locaux
    local_dir = Path(config.data.local_storage_dir)
    local_files_count = 0
    if local_dir.exists():
        for entry in entries:
            local_file = local_dir / entry["filename"]
            if local_file.exists():
                local_files_count += 1

    logger.info(f"📁 Local files available: {local_files_count}")

    # Détails par entrée
    if entries:
        logger.info("\n=== ENTRY DETAILS ===")
        for entry in entries:
            status_icons = []
            local_file = local_dir / entry["filename"] if local_dir.exists() else None
            if local_file and local_file.exists():
                status_icons.append("📁")
            if entry.get("vector_doc_id"):
                status_icons.append("🔍")
            if not status_icons:
                status_icons.append("❌")

            status_str = " ".join(status_icons)
            title = entry.get("title", "Title not available")
            logger.info(f"{status_str} {entry['filename']} - {title}")

            # Afficher le résumé s'il existe
            if entry.get("summary"):
                summary_preview = (
                    entry["summary"][:100] + "..."
                    if len(entry["summary"]) > 100
                    else entry["summary"]
                )
                logger.info(f"  📝 Summary: {summary_preview}")

    return entries


def run_workflow():
    """
    Fonction principale exécutant le workflow de traitement des données.
    """
    config = get_config()

    # Configuration du logging
    logging.basicConfig(level=getattr(logging, config.logging.level), format=config.logging.format)

    try:
        # 1. Analyser l'état actuel de la base
        analyze_knowledge_base(config)

        raise RuntimeError(
            "Static urls.txt ingestion is deprecated. "
            "Provide dynamic references from the syllabus instead."
        )

    except Exception as e:
        logger.error(f"Critical error: {e}")
        raise


if __name__ == "__main__":
    run_workflow()
