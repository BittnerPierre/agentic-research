#!/usr/bin/env python3
"""Serveur MCP compagnon (stdio) : recherche sémantique dataprep.

Le serveur dataprep officiel (src/mcp/dataprep_server.py, SSE :8001) expose
l'acquisition, l'indexation et le catalogue, mais pas la recherche : la
recherche vectorielle est un outil des agents du workflow, pas du MCP. Pour
que le skill « document-research » puisse interroger la base de connaissances
en mode dataprep, ce serveur expose `vector_search` sur la même fonction
(`src.dataprep.mcp_functions.vector_search`), avec la même configuration que
le serveur dataprep (même Chroma, mêmes embeddings).

Chaque extrait renvoyé est journalisé tel quel (texte exact du morceau indexé,
sha256) dans un registre JSONL (`DR_CHUNK_REGISTRY`) — l'équivalent du
`retrieved_chunks` du workflow — pour que l'adaptateur banc puisse écrire
`chunks.json` sans re-interroger l'index.

Lancement (cwd = racine du dépôt) :
    uv run python skills/document-research/mcp/dataprep_search_server.py --config <cfg.yaml>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path

from fastmcp import FastMCP

from src.config import get_config
from src.dataprep.mcp_functions import vector_search as _vector_search

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("dataprep_search")

mcp = FastMCP(
    name="DataPrep Search",
    instructions=(
        "Recherche sémantique dans une collection de la base de connaissances dataprep. "
        "Indexer d'abord les documents avec upload_files_to_vectorstore_tool (serveur dataprep), "
        "puis interroger la collection du même nom avec vector_search."
    ),
)

_CONFIG_PATH: str | None = None


def _registry_path() -> Path | None:
    raw = os.environ.get("DR_CHUNK_REGISTRY")
    return Path(raw) if raw else None


def _record(hits: list[dict]) -> None:
    path = _registry_path()
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for hit in hits:
            handle.write(json.dumps(hit, ensure_ascii=False) + "\n")


@mcp.tool()
def vector_search(
    query: str,
    vectorstore_name: str,
    top_k: int = 8,
    filenames: list[str] | None = None,
) -> dict:
    """Recherche sémantique dans la collection `vectorstore_name`.

    Args:
        query: question ou formulation à rechercher (une idée par requête).
        vectorstore_name: nom de la collection créée par upload_files_to_vectorstore_tool.
        top_k: nombre d'extraits à renvoyer (défaut 8, max 30).
        filenames: optionnel, restreint aux fichiers nommés (champ `filename` exact du catalogue).

    Returns:
        {"query", "vectorstore_name", "results": [{"chunk_id", "document_id", "chunk_index",
        "filename", "source", "score", "text"}]}. `text` est le texte EXACT du morceau indexé :
        un extrait cité doit le recopier tel quel (ou un passage contigu) et porter son chunk_id.
    """
    config = get_config(_CONFIG_PATH)
    config.vector_search.index_name = vectorstore_name
    top_k = max(1, min(int(top_k), 30))
    result = _vector_search(
        query=query,
        config=config,
        top_k=top_k,
        score_threshold=None,
        filenames=[f.strip() for f in filenames if f and f.strip()] if filenames else None,
        vectorstore_id=vectorstore_name,
    )
    hits: list[dict] = []
    for hit in result.results:
        meta = dict(hit.metadata or {})
        text = hit.document or ""
        document_id = meta.get("document_id")
        chunk_index = meta.get("chunk_index")
        resolved = bool(document_id) and chunk_index is not None
        chunk_id = f"{document_id}:{chunk_index}" if resolved else None
        hits.append(
            {
                "chunk_id": chunk_id,
                "document_id": str(document_id) if document_id else None,
                "chunk_index": chunk_index,
                "filename": meta.get("filename"),
                "source": meta.get("source"),
                "score": round(float(hit.score), 4),
                "text": text,
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "resolved": resolved,
            }
        )
    _record(hits)
    return {
        "query": query,
        "vectorstore_name": vectorstore_name,
        "results": [{k: v for k, v in h.items() if k not in {"sha256", "resolved"}} for h in hits],
    }


def main() -> None:
    global _CONFIG_PATH
    parser = argparse.ArgumentParser(description="DataPrep search MCP (stdio)")
    parser.add_argument("--config", type=str, help="fichier de configuration (Chroma + embeddings)")
    args = parser.parse_args()
    _CONFIG_PATH = args.config
    get_config(_CONFIG_PATH)  # charge et valide la config au démarrage
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
