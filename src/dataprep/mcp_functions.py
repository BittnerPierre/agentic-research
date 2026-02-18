"""Fonctions MCP pour la gestion de la base de connaissances et upload vers vector store."""

import logging
import os
import re
from pathlib import Path
from typing import Any

from openai import OpenAI

from .knowledge_db import KnowledgeDBManager
from .models import KnowledgeEntry, UploadResult
from .vector_backends import get_vector_backend
from .vector_search import VectorSearchResult
from .vector_store_utils import validate_url
from .web_loader_improved import load_documents_from_urls

logger = logging.getLogger(__name__)


def _dataprep_llm_client_and_model(config) -> tuple[OpenAI, str]:
    llm_cfg = config.dataprep.llm
    model_spec = llm_cfg.model

    if isinstance(model_spec, str):
        model_name = model_spec
        base_url = None
        api_key = None
    else:
        model_name = model_spec.name
        base_url = model_spec.base_url
        api_key = model_spec.api_key

    resolved_api_key = api_key or os.getenv(llm_cfg.api_key_env) or "dummy"
    client = OpenAI(
        base_url=base_url,
        api_key=resolved_api_key,
        timeout=float(llm_cfg.timeout_seconds),
    )
    return client, model_name


def download_and_store_url(url: str, config) -> str:
    """
    MCP Function 1: Téléchargement et stockage avec lookup dans la base de connaissances

    Args:
        url: URL à télécharger
        config: Configuration du système

    Returns:
        str: Nom du fichier local (.md)
    """
    validate_url(url)
    # 1. Lookup dans knowledge_db.json
    db_manager = KnowledgeDBManager(config.data.knowledge_db_path)
    existing_entry = db_manager.lookup_url(url)

    if existing_entry:
        logger.info(f"URL found in knowledge base: {existing_entry.filename}")
        # Vérifier que le fichier existe encore
        local_path = Path(config.data.local_storage_dir) / existing_entry.filename
        if local_path.exists():
            return existing_entry.filename
        else:
            logger.warning(f"File missing, re-downloading: {existing_entry.filename}")

    # 2. Télécharger et convertir
    logger.info(f"Downloading URL: {url}")
    docs_list = load_documents_from_urls([url])

    if not docs_list:
        raise ValueError(f"Unable to download content from: {url}")

    doc = docs_list[0]

    # 3. Générer nom de fichier unique
    title = doc.metadata.get("title", "document")
    safe_title = re.sub(r"[^a-zA-Z0-9_.-]", "_", title[:50])
    filename = f"{safe_title}.md"

    # Éviter les collisions de noms
    local_dir = Path(config.data.local_storage_dir)
    local_dir.mkdir(parents=True, exist_ok=True)
    counter = 1
    original_filename = filename
    while (local_dir / filename).exists():
        name, ext = original_filename.rsplit(".", 1)
        filename = f"{name}_{counter}.{ext}"
        counter += 1

    # 4. Sauvegarder le fichier .md
    local_path = local_dir / filename
    markdown_content = _format_document_as_markdown(doc)

    with open(local_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    # 5. Extraire mots-clés avec LLM
    keywords = _extract_keywords_with_llm(doc, config)

    # 6. Générer un résumé avec LLM
    summary = _extract_summary_with_llm(doc, config)

    # 7. Ajouter à la base de connaissances
    entry = KnowledgeEntry(
        url=url,
        filename=filename,
        keywords=keywords,
        summary=summary,  # Ajout du résumé
        title=doc.metadata.get("title"),
        content_length=len(doc.page_content),
        # openai_file_id sera ajouté lors de l'upload
    )

    db_manager.add_entry(entry)

    logger.info(f"Document saved: {filename}")
    return filename


def upload_files_to_vectorstore(inputs: list[str], config, vectorstore_name: str) -> UploadResult:
    """
    MCP Function 2: Indexation locale vers le vector store

    Logic:
    - Si input est URL -> lookup par URL
    - Si input est filename -> lookup par nom
    - Si entrée a déjà vector_doc_id -> réutiliser
    - Sinon -> indexer localement et sauvegarder l'ID

    Args:
        inputs: Liste d'URLs, chemins de fichiers ou noms de fichiers locaux
        config: Configuration
        vectorstore_name: Nom du vector store

    Returns:
        UploadResult: Résultat détaillé de l'opération
    """
    backend = get_vector_backend(config)
    return backend.upload_files(inputs, config, vectorstore_name)


def vector_search(
    query: str,
    config,
    top_k: int | None = None,
    score_threshold: float | None = None,
    filenames: list[str] | None = None,
    vectorstore_id: str | None = None,
) -> VectorSearchResult:
    """
    Recherche locale dans le vector store avec chunking tardif.
    """
    backend = get_vector_backend(config)
    return backend.search(
        query=query,
        config=config,
        top_k=top_k,
        score_threshold=score_threshold,
        filenames=filenames,
        vectorstore_id=vectorstore_id,
    )


def get_knowledge_entries(config) -> list[dict[str, Any]]:
    """
    MCP Function 3: Accès à l'index de la base de connaissances

    Args:
        config: Configuration du système

    Returns:
        List[Dict]: Liste des entrées disponibles
    """
    db_manager = KnowledgeDBManager(config.data.knowledge_db_path)
    return db_manager.get_all_entries_info()


def _extract_keywords_with_llm(doc, config) -> list[str]:
    """Extraction de mots-clés intelligente avec LLM."""
    if not getattr(config.dataprep.llm, "enabled", True):
        logger.warning("dataprep.llm.enabled=false; using basic keyword extraction fallback.")
        return _extract_keywords_basic(doc)
    client, model_name = _dataprep_llm_client_and_model(config)

    # Limiter le contenu pour l'analyse
    content_preview = (
        doc.page_content[:2000] + "..." if len(doc.page_content) > 2000 else doc.page_content
    )
    title = doc.metadata.get("title", "Document sans titre")

    prompt = f"""Analyse ce document et extrais 5-10 mots-clés pertinents qui résument le contenu principal.

Titre: {title}

Contenu:
{content_preview}

Retourne uniquement une liste de mots-clés séparés par des virgules, sans numérotation ni explication.
Concentre-toi sur les concepts techniques, les noms propres, et les thèmes principaux."""

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=float(config.dataprep.llm.temperature),
            max_tokens=min(200, int(config.dataprep.llm.max_tokens)),
        )

        keywords_text = response.choices[0].message.content.strip()
        keywords = [kw.strip() for kw in keywords_text.split(",") if kw.strip()]

        logger.info(f"LLM-extracted keywords: {keywords}")
        return keywords[:10]  # Limiter à 10 mots-clés

    except Exception as e:
        logger.error(f"Failed to extract keywords with LLM: {e}")
        logger.warning("Using basic keyword extraction fallback after LLM failure.")
        # Fallback sur extraction basique
        return _extract_keywords_basic(doc)


def _extract_summary_with_llm(doc, config) -> str:
    """Génération d'un résumé avec LLM."""
    if not getattr(config.dataprep.llm, "enabled", True):
        logger.warning("dataprep.llm.enabled=false; using basic summary fallback.")
        return _extract_basic_summary(doc)
    client, model_name = _dataprep_llm_client_and_model(config)

    # Limiter le contenu pour l'analyse
    content_preview = (
        doc.page_content[:4000] + "..." if len(doc.page_content) > 4000 else doc.page_content
    )
    title = doc.metadata.get("title", "Document sans titre")

    prompt = f"""Génère un résumé concis (maximum 200 mots) de ce document qui capture les points essentiels.
    
Titre: {title}

Contenu:
{content_preview}

Ton résumé doit être factuel, objectif et couvrir les informations principales du document."""

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=float(config.dataprep.llm.temperature),
            max_tokens=max(300, int(config.dataprep.llm.max_tokens)),
        )

        summary = response.choices[0].message.content.strip()
        logger.info(f"LLM-generated summary: {len(summary)} characters")
        return summary

    except Exception as e:
        logger.error(f"Failed to generate summary with LLM: {e}")
        logger.warning("Using basic summary fallback after LLM failure.")
        # Fallback sur résumé basique
        return _extract_basic_summary(doc)


def _extract_basic_summary(doc) -> str:
    """Génération basique d'un résumé (fallback)."""
    title = doc.metadata.get("title", "Document sans titre")
    content = doc.page_content

    # Prendre les premiers caractères comme résumé
    max_length = 200
    summary = content[:max_length] + "..." if len(content) > max_length else content

    return f"{title} - {summary}"


def _extract_keywords_basic(doc) -> list[str]:
    """Extraction basique de mots-clés (fallback)."""
    keywords = []

    # Titre
    if doc.metadata.get("title"):
        keywords.append(doc.metadata["title"])

    # Premiers mots du contenu
    words = doc.page_content.split()[:50]
    # Filtrer et garder mots significatifs (longueur > 3)
    significant_words = [w.strip(".,!?;:") for w in words if len(w) > 3]
    keywords.extend(significant_words[:10])

    return list(set(keywords))  # Dédupliquer


def _format_document_as_markdown(doc) -> str:
    """Formate un document en markdown avec métadonnées."""
    # Réutiliser la logique existante de core.py
    from .core import format_document_as_markdown

    return format_document_as_markdown(doc)
