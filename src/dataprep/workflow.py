"""
Module de workflow pour le traitement des données avec les fonctions MCP DataPrep.
"""

import logging
from pathlib import Path

from ..config import get_config

# Import direct des fonctions MCP
from .mcp_functions import (
    download_and_store_url,
    get_knowledge_entries,
    upload_files_to_vectorstore,
)

logger = logging.getLogger(__name__)


def load_urls_from_file(config) -> list[str]:
    """Charge les URLs depuis le fichier configuré."""
    urls_file_path = config.data.urls_file
    current_dir = Path(
        __file__
    ).parent.parent.parent  # src/dataprep -> src -> experiments/agentic-research
    urls_file = current_dir / urls_file_path

    if not urls_file.exists():
        raise FileNotFoundError(f"Fichier URLs non trouvé: {urls_file}")

    urls = []
    with open(urls_file, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            url = line.strip()
            if url and not url.startswith("#"):
                if url.startswith(("http://", "https://")):
                    urls.append(url)
                else:
                    logger.warning(f"URL invalide ignorée (ligne {line_num}): {url}")

    if not urls:
        raise ValueError(f"Aucune URL valide trouvée dans le fichier: {urls_file}")

    return urls


def analyze_knowledge_base(config):
    """Analyse l'état actuel de la base de connaissances."""
    logger.info("=== ANALYSE DE LA BASE DE CONNAISSANCES ===")

    # État général
    entries = get_knowledge_entries(config)

    logger.info(f"📊 Total d'entrées: {len(entries)}")

    # Compter les fichiers indexés localement
    indexed_count = sum(1 for entry in entries if entry.get("vector_doc_id"))
    logger.info(f"🔍 Fichiers indexés localement: {indexed_count}")

    # Vérifier les fichiers locaux
    local_dir = Path(config.data.local_storage_dir)
    local_files_count = 0
    if local_dir.exists():
        for entry in entries:
            local_file = local_dir / entry["filename"]
            if local_file.exists():
                local_files_count += 1

    logger.info(f"📁 Fichiers locaux disponibles: {local_files_count}")

    # Détails par entrée
    if entries:
        logger.info("\n=== DÉTAILS DES ENTRÉES ===")
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
            title = entry.get("title", "Titre non disponible")
            logger.info(f"{status_str} {entry['filename']} - {title}")

            # Afficher le résumé s'il existe
            if entry.get("summary"):
                summary_preview = (
                    entry["summary"][:100] + "..."
                    if len(entry["summary"]) > 100
                    else entry["summary"]
                )
                logger.info(f"  📝 Résumé: {summary_preview}")

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

        # 2. Charger les URLs
        urls = load_urls_from_file(config)
        logger.info(f"\nDébut du traitement de {len(urls)} URLs")

        # 3. Télécharger et stocker chaque URL
        filenames = []
        for url in urls:
            try:
                filename = download_and_store_url(url, config)
                filenames.append(filename)
                logger.info(f"✅ URL traitée: {url} -> {filename}")
            except Exception as e:
                logger.error(f"❌ Erreur pour {url}: {e}")

        if not filenames:
            logger.error("Aucun fichier n'a pu être traité")
            return

        # 4. Mode debug ou upload
        if config.debug.enabled:
            logger.info(f"\nMode debug activé - {len(filenames)} fichiers stockés localement")

            # Afficher le contenu de la base de connaissances
            entries = get_knowledge_entries(config)

            logger.info("\n=== BASE DE CONNAISSANCES FINALE ===")
            for entry in entries:
                openai_status = "🔍 Indexé" if entry.get("vector_doc_id") else "📥 Local"
                logger.info(f"📄 {entry['filename']} ({openai_status})")
                logger.info(f"🔗 Source: {entry['url']}")
                keywords = entry.get("keywords", [])
                if keywords:
                    logger.info(f"🏷️  Mots-clés LLM: {', '.join(keywords[:5])}")
                if entry.get("summary"):
                    logger.info(f"📝 Résumé: {entry['summary'][:150]}...")
                if entry.get("vector_doc_id"):
                    logger.info(f"🆔 Vector Doc ID: {entry['vector_doc_id']}")
                logger.info("---")

        else:
            # Mode normal: indexation locale avec optimisations
            logger.info("\nMode normal - indexation locale vers vector store")

            try:
                result = upload_files_to_vectorstore(
                    inputs=urls,  # Utiliser les URLs qui seront résolues
                    config=config,
                    vectorstore_name="agentic-research-vector-store",
                )

                logger.info("\n=== RAPPORT D'INDEXATION ===")
                logger.info(f"Vector Store ID: {result.vectorstore_id}")
                logger.info(f"Total de fichiers demandés: {result.total_files_requested}")
                logger.info(f"Nouvelles indexations: {result.upload_count}")
                logger.info(f"Fichiers réutilisés (déjà indexés): {result.reuse_count}")

                logger.info("\n=== DÉTAILS DES FICHIERS ===")
                logger.info("🔍 Indexations locales:")
                for file_info in result.files_uploaded:
                    status_icons = {"indexed": "🆕", "reused": "♻️", "failed": "❌"}
                    icon = status_icons.get(file_info["status"], "❓")
                    logger.info(
                        f"  {icon} {file_info['filename']} -> {file_info.get('doc_id', 'N/A')}"
                    )

            except Exception as e:
                logger.error(f"Erreur lors de l'upload: {e}")

    except Exception as e:
        logger.error(f"Erreur critique: {e}")
        raise


if __name__ == "__main__":
    run_workflow()
