import logging
import re
import tempfile
from pathlib import Path
from typing import Any

from openai import OpenAI

from ..config import get_config
from .vector_store_manager import VectorStoreManager

# from .web_loader import WebDocument, load_documents_from_urls
from .web_loader_improved import WebDocument, load_documents_from_urls

# Configuration du logger
logger = logging.getLogger(__name__)

# Plus de variables globales - utilisation directe de get_config() dans les fonctions


def format_document_as_markdown(doc: WebDocument) -> str:
    """
    Formate un document en markdown avec métadonnées.

    Args:
        doc: Document web à formater

    Returns:
        Contenu formaté en markdown
    """
    title = doc.metadata.get("title", "Document sans titre")
    source_url = doc.metadata.get("source", "URL inconnue")

    # Construction du markdown avec métadonnées
    markdown_content = f"""---
title: "{title}"
source: "{source_url}"
content_length: {len(doc.page_content)}
---

# {title}

**Source:** [{source_url}]({source_url})

## Contenu

{doc.page_content}

---
*Document traité automatiquement par le système de recherche agentique*
"""

    return markdown_content


def save_docs_to_markdown(docs_list: list[WebDocument], temp_dir: Path) -> list[Path]:
    """
    Sauvegarde les documents en format markdown dans le dossier temporaire.

    Args:
        docs_list: Liste des documents web
        temp_dir: Dossier temporaire pour sauvegarder les fichiers

    Returns:
        Liste des chemins des fichiers sauvegardés
    """
    saved_files = []

    for i, doc in enumerate(docs_list):
        # Générer un nom de fichier à partir du titre ou de l'URL
        title = doc.metadata.get("title", f"document_{i+1}")
        filename = f"{i+1:02d}_{title[:50]}.md"

        # Nettoyer le nom de fichier
        filename = re.sub(r"[^a-zA-Z0-9_.-]", "_", filename)
        filename = re.sub(r"_+", "_", filename)  # Supprimer les underscores multiples

        file_path = temp_dir / filename

        try:
            # Formater et sauvegarder le document
            markdown_content = format_document_as_markdown(doc)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            saved_files.append(file_path)
            logger.info(f"Document sauvegardé: {filename}")

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de {filename}: {e}")

    return saved_files


def upload_files_to_vector_store(
    client: OpenAI, file_paths: list[Path], vector_store_id: str
) -> dict[str, Any]:
    """
    Upload les fichiers vers l'API Files OpenAI puis les attache au vector store.

    Cette approche en deux étapes permet de télécharger les fichiers ultérieurement,
    contrairement à l'upload direct au vector store.

    Args:
        client: Client OpenAI
        file_paths: Liste des chemins de fichiers à uploader
        vector_store_id: ID du vector store

    Returns:
        Résultats de l'upload avec statistiques
    """
    upload_results = {"success": [], "failures": [], "total_files": len(file_paths)}

    for file_path in file_paths:
        try:
            logger.info(f"Upload du fichier vers l'API Files: {file_path.name}")

            # Étape 1: Upload du fichier vers l'API Files OpenAI
            with open(file_path, "rb") as file:
                file_upload_response = client.files.create(file=file, purpose="user_data")

            file_id = file_upload_response.id
            logger.info(f"Fichier uploadé vers l'API Files avec l'ID: {file_id}")

            # Étape 2: Attacher le fichier au vector store
            logger.info(f"Attachement du fichier au vector store: {file_path.name}")

            vector_store_file = client.vector_stores.files.create(
                vector_store_id=vector_store_id, file_id=file_id
            )

            # Attendre que le fichier soit traité
            while vector_store_file.status == "in_progress":
                logger.info(f"Traitement en cours pour {file_path.name}...")
                import time

                time.sleep(1)
                vector_store_file = client.vector_stores.files.retrieve(
                    vector_store_id=vector_store_id, file_id=file_id
                )

            if vector_store_file.status == "completed":
                upload_results["success"].append(
                    {
                        "filename": file_path.name,
                        "file_id": file_id,
                        "vector_store_file_id": vector_store_file.id,
                    }
                )
                logger.info(f"Fichier attaché avec succès au vector store: {file_path.name}")
            else:
                raise Exception(
                    f"Échec de l'attachement au vector store. Status: {vector_store_file.status}"
                )

        except Exception as e:
            error_msg = f"Erreur lors de l'upload de {file_path.name}: {e}"
            logger.error(error_msg)
            upload_results["failures"].append({"filename": file_path.name, "error": str(e)})

    return upload_results


def load_urls_from_file() -> list[str]:
    """
    Deprecated: static urls.txt ingestion is not supported.
    Use dynamic references extracted from the syllabus instead.
    """
    raise RuntimeError(
        "Static urls.txt ingestion is deprecated. "
        "Provide dynamic references from the syllabus instead."
    )


def main():
    """
    Fonction principale pour traiter les documents web et les envoyer au vector store.
    Si le mode debug est activé, sauvegarde les documents localement.
    """
    config = get_config()
    try:
        # Chargement des URLs depuis le fichier externe configuré
        urls = load_urls_from_file()

        logger.info(f"Début du traitement de {len(urls)} URLs")

        # Chargement des documents
        logger.info("Chargement des documents depuis les URLs...")
        docs_list = load_documents_from_urls(urls)

        if not docs_list:
            logger.error("Aucun document n'a pu être chargé")
            return

        logger.info(f"{len(docs_list)} documents chargés avec succès")

        # Vérifier si le mode debug est activé
        debug_enabled = config.debug.enabled
        debug_output_dir = Path(config.debug.output_dir)

        if debug_enabled:
            # Mode debug : sauvegarde locale permanente
            logger.info(f"Mode debug activé - sauvegarde dans {debug_output_dir}")

            # Créer le dossier debug_output s'il n'existe pas
            debug_output_dir.mkdir(parents=True, exist_ok=True)

            # Sauvegarde en markdown dans debug_output
            logger.info("Conversion et sauvegarde des documents en markdown...")
            saved_files = save_docs_to_markdown(docs_list, debug_output_dir)

            if not saved_files:
                logger.error("Aucun fichier n'a pu être sauvegardé")
                return

            logger.info(f"{len(saved_files)} fichiers markdown créés dans {debug_output_dir}")

            # Affichage du contenu en mode debug
            logger.info("=== APERÇU DU CONTENU CHARGÉ ===")
            for i, doc in enumerate(docs_list, 1):
                title = doc.metadata.get("title", f"Document {i}")
                source = doc.metadata.get("source", "Source inconnue")
                content_preview = (
                    doc.page_content[:200] + "..."
                    if len(doc.page_content) > 200
                    else doc.page_content
                )

                logger.info(f"\n📄 Document {i}: {title}")
                logger.info(f"🔗 Source: {source}")
                logger.info(f"📝 Aperçu: {content_preview}")
                logger.info(f"📊 Taille: {len(doc.page_content)} caractères")

            # Créer un rapport de synthèse en mode debug
            if config.debug.save_reports:
                report_path = debug_output_dir / "processing_report.md"
                create_processing_report(docs_list, saved_files, report_path)
                logger.info(f"📋 Rapport de traitement sauvegardé: {report_path}")

            logger.info(f"\n✅ Mode debug - Contenu sauvegardé localement dans {debug_output_dir}")
            logger.info(
                "Les fichiers markdown sont prêts à être utilisés pour la recherche locale."
            )

        else:
            # Mode normal : upload vers vector store avec dossier temporaire
            logger.info("Mode normal - upload vers vector store")

            with tempfile.TemporaryDirectory(prefix="agentic_research_docs_") as temp_dir:
                temp_path = Path(temp_dir)
                logger.info(f"Dossier temporaire créé: {temp_path}")

                # Sauvegarde en markdown
                logger.info("Conversion et sauvegarde des documents en markdown...")
                saved_files = save_docs_to_markdown(docs_list, temp_path)

                if not saved_files:
                    logger.error("Aucun fichier n'a pu être sauvegardé")
                    return

                logger.info(f"{len(saved_files)} fichiers markdown créés")

                # Upload vers le vector store
                logger.info("Upload vers le vector store OpenAI...")
                client = OpenAI()
                manager = VectorStoreManager(config.vector_store.name, client)
                vector_store_id = manager.get_or_create_vector_store()

                upload_results = upload_files_to_vector_store(client, saved_files, vector_store_id)

                # Rapport final
                logger.info("=== RAPPORT D'UPLOAD ===")
                logger.info(f"Total de fichiers traités: {upload_results['total_files']}")
                logger.info(f"Uploads réussis: {len(upload_results['success'])}")
                logger.info(f"Échecs: {len(upload_results['failures'])}")

                if upload_results["success"]:
                    logger.info("Fichiers uploadés avec succès:")
                    for result in upload_results["success"]:
                        logger.info(f"  - {result['filename']} (ID: {result['file_id']})")

                if upload_results["failures"]:
                    logger.warning("Fichiers en échec:")
                    for failure in upload_results["failures"]:
                        logger.warning(f"  - {failure['filename']}: {failure['error']}")

            logger.info("Traitement terminé. Dossier temporaire nettoyé automatiquement.")

    except (FileNotFoundError, ValueError, RuntimeError) as e:
        logger.error(f"Erreur de configuration: {e}")
        logger.error("Veuillez fournir des références dynamiques (syllabus) à traiter.")
        raise
    except Exception as e:
        logger.error(f"Erreur critique dans le traitement: {e}")
        raise


def create_processing_report(
    docs_list: list[WebDocument], saved_files: list[Path], report_path: Path
) -> None:
    """
    Crée un rapport de synthèse du traitement des documents.

    Args:
        docs_list: Liste des documents traités
        saved_files: Liste des fichiers sauvegardés
        report_path: Chemin du fichier de rapport
    """
    import datetime

    report_content = f"""# Rapport de Traitement des Documents

**Date de traitement:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Résumé

- **Nombre de documents traités:** {len(docs_list)}
- **Nombre de fichiers créés:** {len(saved_files)}
- **Taille totale du contenu:** {sum(len(doc.page_content) for doc in docs_list):,} caractères

## Documents Traités

"""

    for i, doc in enumerate(docs_list, 1):
        title = doc.metadata.get("title", f"Document {i}")
        source = doc.metadata.get("source", "Source inconnue")
        content_length = len(doc.page_content)

        report_content += f"""### {i}. {title}

- **Source:** {source}
- **Taille:** {content_length:,} caractères
- **Aperçu:** {doc.page_content[:150]}...

"""

    report_content += """
## Fichiers Créés

"""

    for file_path in saved_files:
        report_content += f"- `{file_path.name}`\n"

    report_content += """
---
*Rapport généré automatiquement par le système de recherche agentique*
"""

    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        logger.info(f"Rapport de synthèse créé: {report_path}")
    except Exception as e:
        logger.error(f"Erreur lors de la création du rapport: {e}")


if __name__ == "__main__":
    # Configuration du logging pour l'exécution directe
    config = get_config()
    logging.basicConfig(level=getattr(logging, config.logging.level), format=config.logging.format)

    main()
