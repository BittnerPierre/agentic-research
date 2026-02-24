import logging
import re
from pathlib import Path
from typing import Any

from openai import OpenAI

# from .web_loader import WebDocument, load_documents_from_urls
from .web_loader_improved import WebDocument

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
