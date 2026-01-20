#!/usr/bin/env python3
"""
Smoke test (manual) for file search / research manager.

NOTE:
- This is NOT a unit test and should not run under `pytest` by default.
- It requires a correctly configured environment (API keys, MCP servers, etc.).

Run manually:
  poetry run python integration_tests/manual_file_search_smoke.py
"""

import asyncio


async def main() -> None:
    query = "Agents"
    print("🔍 Smoke test: recherche")
    print(f"Query: {query}")

    # This manager requires MCP servers + ResearchInfo context in normal execution.
    # Keep this as a placeholder entry point for manual runs.
    # If you want this to be runnable, wire MCP servers the same way `src/main.py` does.
    raise SystemExit(
        "Ce script est un smoke test manuel. "
        "Pour l'exécuter, il faut instancier les serveurs MCP et appeler "
        "`StandardResearchManager().run(fs_server, dataprep_server, query, ResearchInfo(...))` "
        "comme dans `src/main.py`."
    )


if __name__ == "__main__":
    asyncio.run(main())

