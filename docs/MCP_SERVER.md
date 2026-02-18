# Agentic Research MCP Server (Issue 83)

Serveur MCP exposant agentic-research en mode distant (Streamable HTTP), pour être appelé depuis des clients MCP (ChatGPT, Claude, Le Chat, Open-WebUI, etc.).

## Prérequis

- Le service **dataprep** doit être démarré (le serveur MCP agentic-research s’y connecte pour la base de connaissances et le vector store).
- Variables d’environnement : `.env` avec `OPENAI_API_KEY`, `CHROMA_OPENAI_API_KEY` si besoin, etc. (voir config du projet).

## Démarrer le serveur

### En local (Poetry)

```bash
# Démarrer le serveur DataPrep dans un premier terminal
poetry run dataprep_server

# Démarrer le serveur MCP agentic-research (Streamable HTTP par défaut)
poetry run agentic_research_server --host 0.0.0.0 --port 8002 --transport streamable-http --path /mcp
```

Options :

- `--host` : interface d’écoute (défaut `0.0.0.0`)
- `--port` : port (défaut `8002`)
- `--transport` : `streamable-http` (recommandé) ou `sse`
- `--path` : chemin pour Streamable HTTP (défaut `/mcp`)

### Avec Docker Compose

```bash
docker compose up -d dataprep agentic-research-mcp
```

Le service **agentic-research-mcp** écoute sur le port **8002** (Streamable HTTP, path `/mcp`).

Sur DGX Spark (Tailscale), utiliser la même stack ; l’accès se fait via l’URL Tailscale du host (ex. `http://<tailscale-name>:8002/mcp`).

## Outils MCP exposés

### research_query

Lance une recherche à partir d’une requête texte.

- **Paramètre** : `query` (string) – sujet ou question de recherche.
- **Retour** : rapport texte (research_topic, short_summary, markdown_report, follow_up_questions). En cas d’erreur, une chaîne commençant par `ERROR:`.

### research_syllabus

Lance une recherche à partir d’un contenu type syllabus (chapitres, thèmes).

- **Paramètre** : `syllabus_content` (string) – contenu du syllabus en texte libre.
- **Retour** : même format que `research_query`.

## Exemple de connexion client (Python / MCP)

```python
# Exemple avec le client MCP Python (streamable-http)
# L’URL de base est http://localhost:8002 (path /mcp selon config)

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_transport

async def main():
    async with streamable_http_transport("http://localhost:8002/mcp") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            # Appel de research_query
            result = await session.call_tool("research_query", {"query": "Retrieval Augmented Generation"})
            print(result)
```

## Exemple avec MCP Inspector / MCP Jam

1. Démarrer dataprep et agentic-research-mcp (local ou Docker).
2. Dans MCP Inspector (ou MCP Jam), ajouter un serveur MCP :
   - **URL** : `http://localhost:8002/mcp` (Streamable HTTP).
3. Tester les outils `research_query` et `research_syllabus` avec une requête courte.

## Configuration et variables

- **MCP_DATAPREP_URL** : URL du serveur DataPrep (en Docker : `http://dataprep:8001/sse`).
- **Config YAML** : le serveur utilise la config par défaut (`configs/config-default.yaml`) sauf si `--config` est fourni au démarrage.
- **Manager** : par défaut `agentic_manager` ; les outils utilisent le manager configuré pour produire un rapport (agentic_manager ou deep_manager).

## Tests d’intégration

Les tests unitaires du serveur MCP sont dans `tests/test_agentic_research_server.py`. Pour un test manuel avec un client MCP, utiliser MCP Inspector ou un script appelant l’URL Streamable HTTP du service.
