#!/usr/bin/env python3
"""UAT script: client MCP qui appelle le serveur agentic-research (Streamable HTTP).

Usage:
  poetry run python scripts/uat_mcp_agentic_research_client.py [query]
  MCP_AGENTIC_RESEARCH_URL=http://localhost:8008/mcp poetry run python scripts/uat_mcp_agentic_research_client.py

Prérequis: serveur MCP agentic-research et dataprep démarrés (voir docs/MCP_SERVER.md).
"""

from __future__ import annotations

import asyncio
import os
import sys


async def main() -> int:
    url = os.environ.get("MCP_AGENTIC_RESEARCH_URL", "http://localhost:8008/mcp")
    query = (sys.argv[1] if len(sys.argv) > 1 else "RAG en une phrase").strip()

    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
    except ImportError as e:
        print("Erreur: dépendance mcp manquante. Lancer: poetry install", file=sys.stderr)
        return 1

    print(f"Connexion à {url} ...")
    print(f"Appel research_query(query={query!r})")
    try:
        async with streamable_http_client(url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool("research_query", {"query": query})
    except Exception as e:
        print(f"Erreur: {e}", file=sys.stderr)
        print(
            "Vérifier que le serveur MCP et dataprep sont démarrés (voir docs/MCP_SERVER.md).",
            file=sys.stderr,
        )
        return 1

    if not result.content:
        print("Réponse vide.", file=sys.stderr)
        return 1
    text = result.content[0].text if result.content else ""
    if result.isError:
        print("Erreur outil:", text, file=sys.stderr)
        return 1
    print("--- Résultat ---")
    print(text)
    if "short_summary" in text:
        print("\n[UAT OK: short_summary présent dans la réponse]")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
