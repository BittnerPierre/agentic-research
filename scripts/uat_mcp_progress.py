#!/usr/bin/env python3
"""UAT: test des notifications Progress (MCP) du serveur agentic-research.

Le client envoie un progressToken (via progress_callback) et affiche les
notifications progress reçues (Démarrage recherche, Terminé).

Usage:
  poetry run python scripts/uat_mcp_progress.py [query]
  MCP_AGENTIC_RESEARCH_URL=http://localhost:8008/mcp poetry run python scripts/uat_mcp_progress.py

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
        print(f"Erreur: dépendance manquante — {e}", file=sys.stderr)
        print("Lancer: poetry install", file=sys.stderr)
        return 1

    progress_events: list[tuple[float, float | None, str | None]] = []

    async def on_progress(progress: float, total: float | None, message: str | None) -> None:
        progress_events.append((progress, total, message))
        total_s = f"/{total}" if total is not None else ""
        msg_s = f" — {message}" if message else ""
        print(f"  [Progress] {progress}{total_s}{msg_s}")

    print(f"Connexion à {url} ...")
    print(f"Appel research_query avec progress_callback (query={query!r})")
    try:
        async with streamable_http_client(url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(
                    "research_query",
                    {"query": query},
                    progress_callback=on_progress,
                )
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
    print("--- Résultat (extrait) ---")
    print(text[:500] + "..." if len(text) > 500 else text)
    print(f"\n[UAT Progress] {len(progress_events)} notification(s) reçue(s)")
    if progress_events:
        print("[UAT OK: Progress fonctionne]")
    else:
        print(
            "[UAT: aucune notification progress — le client n'envoie peut-être pas progressToken]",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
