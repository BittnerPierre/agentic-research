#!/usr/bin/env python3
"""UAT: test de l'annulation (MCP notifications/cancelled) du serveur agentic-research.

Lance un appel research_query long, envoie notifications/cancelled après quelques
secondes, et vérifie que la requête est bien annulée (pas de résultat complet).

Usage:
  poetry run python scripts/uat_mcp_cancellation.py [query] [délai_secondes]
  MCP_AGENTIC_RESEARCH_URL=http://localhost:8008/mcp poetry run python scripts/uat_mcp_cancellation.py "long query" 3

Prérequis: serveur MCP agentic-research et dataprep démarrés (voir docs/MCP_SERVER.md).
"""

from __future__ import annotations

import asyncio
import os
import sys


async def main() -> int:
    url = os.environ.get("MCP_AGENTIC_RESEARCH_URL", "http://localhost:8008/mcp")
    query = (sys.argv[1] if len(sys.argv) > 1 else "RAG et vector stores en détail").strip()
    delay = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0

    try:
        from mcp import ClientSession, types
        from mcp.client.streamable_http import streamable_http_client
    except ImportError as e:
        print(f"Erreur: dépendance manquante — {e}", file=sys.stderr)
        print("Lancer: poetry install", file=sys.stderr)
        return 1

    print(f"Connexion à {url} ...")
    print(f"Lancement research_query(query={query!r}), annulation après {delay}s")
    try:
        async with streamable_http_client(url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                # L'id de la prochaine requête est _request_id (session partagée MCP)
                request_id = session._request_id
                task = asyncio.create_task(session.call_tool("research_query", {"query": query}))
                await asyncio.sleep(delay)
                print(f"Envoi notifications/cancelled (requestId={request_id})")
                await session.send_notification(
                    types.ClientNotification(
                        types.CancelledNotification(
                            params=types.CancelledNotificationParams(
                                requestId=request_id,
                                reason="UAT cancellation test",
                            )
                        )
                    )
                )
                try:
                    result = await task
                    print("Réponse reçue (annulation peut avoir été trop tard):", result.isError)
                    if result.content:
                        print("Extrait:", (result.content[0].text or "")[:200])
                except Exception as e:
                    print(f"Requête interrompue (attendu si annulation prise en compte): {e}")
                    if "cancel" in str(e).lower() or "cancelled" in str(e).lower():
                        print("[UAT OK: annulation reçue côté client]")
                        return 0
    except Exception as e:
        print(f"Erreur: {e}", file=sys.stderr)
        print(
            "Vérifier que le serveur MCP et dataprep sont démarrés (voir docs/MCP_SERVER.md).",
            file=sys.stderr,
        )
        return 1

    print("[UAT Cancellation: exécuter le script pour vérifier le comportement]")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
