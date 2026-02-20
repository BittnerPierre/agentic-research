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
poetry run agentic_research_server --host 0.0.0.0 --port 8008 --transport streamable-http --path /mcp
```

Options :

- `--host` : interface d’écoute (défaut `0.0.0.0`)
- `--port` : port (défaut `8008`)
- `--transport` : `streamable-http` (recommandé) ou `sse`
- `--path` : chemin pour Streamable HTTP (défaut `/mcp`)

### Avec Docker Compose

```bash
docker compose up -d dataprep agentic-research-mcp
```

Le service **agentic-research-mcp** écoute sur le port **8008** (Streamable HTTP, path `/mcp`).

Sur DGX Spark (Tailscale), utiliser la même stack ; l’accès se fait via l’URL Tailscale du host (ex. `http://<tailscale-name>:8008/mcp`).

## Outils MCP exposés

Les outils sont appelés en **mode synchrone** uniquement (la recherche s’exécute puis le rapport est renvoyé dans la réponse). Le mode tâche (MCP SEP-1686) n’est pas exposé : l’API expérimentale tasks du client MCP avec Streamable HTTP est instable (erreurs SSE / flux fermé), donc non supportée pour l’instant.

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
# L’URL de base est http://localhost:8008 (path /mcp selon config)

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async def main():
    async with streamable_http_client("http://localhost:8008/mcp") as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            # Appel synchrone de research_query
            result = await session.call_tool("research_query", {"query": "Retrieval Augmented Generation"})
            print(result)
```

## Exemple avec MCP Inspector / MCP Jam

1. Démarrer dataprep et agentic-research-mcp (local ou Docker).
2. Dans MCP Inspector (ou MCP Jam), ajouter un serveur MCP :
   - **URL** : `http://localhost:8008/mcp` (Streamable HTTP).
3. Tester les outils `research_query` et `research_syllabus` avec une requête courte.

## Configuration et variables

- **MCP_DATAPREP_URL** : URL du serveur DataPrep (en Docker : `http://dataprep:8001/sse`).
- **Config YAML** : le serveur utilise la config par défaut (`configs/config-default.yaml`) sauf si `--config` est fourni au démarrage.
- **Manager** : par défaut `agentic_manager` ; les outils utilisent le manager configuré pour produire un rapport (agentic_manager ou deep_manager).

## Tests et UAT (test utilisateur)

- **Tests unitaires** : `poetry run pytest tests/test_agentic_research_server.py -v`.
- **UAT script principal** : `poetry run python scripts/uat_mcp_agentic_research_client.py [query]`. URL : `MCP_AGENTIC_RESEARCH_URL` (défaut `http://localhost:8008/mcp`).
- **UAT Progress** : `poetry run python scripts/uat_mcp_progress.py [query]` — affiche les notifications progress (Démarrage recherche, Terminé).
- **UAT Cancellation** : `poetry run python scripts/uat_mcp_cancellation.py [query] [délai_s]` — lance une recherche, envoie `notifications/cancelled` après délai_s secondes (défaut 3), vérifie l'interruption.

### Progress et annulation

- **Progress** : le serveur envoie des notifications de progression (phases : démarrage, préparation, plan, recherche, rédaction, terminé) selon le manager utilisé.
- **Annulation** : le client peut envoyer `notifications/cancelled` pour interrompre une recherche. L’arrêt est **best-effort** : il prend effet aux **frontières de phase** (points où le moteur cède la main). Avec le transport Streamable HTTP, la notification peut n’être lue qu’après la fin de la réponse en cours ; dans ce cas le spinner côté client peut continuer jusqu’à la fin de la phase en cours. Les managers ont été modifiés pour ajouter des points de rendu en début de phase afin d’améliorer la réactivité à l’annulation.

- **Test manuel (MCP Inspector / MCP Jam)** : voir la section « Exemple avec MCP Inspector / MCP Jam » ci-dessus.

## Multi-utilisateurs et partage DataPrep

Toutes les recherches (tous utilisateurs) s’appuient sur le **même serveur DataPrep** : même base de connaissances (`knowledge_db.json`), même nom de vector store (config), donc même collection / même vector store côté backend (OpenAI ou Chroma).

### Risques de concurrence

- **Base de connaissances** : accès fichier protégé par verrou exclusif (`portalocker`). Pas de corruption ; les écritures sont sérialisées. En multi-process, les index en mémoire d’un process peuvent être périmés après une écriture par un autre process (jusqu’à relecture du fichier).
- **Vector store (OpenAI)** : deux runs concurrents qui résolvent le même nom peuvent, en l’absence de lock, tous les deux « ne pas trouver » puis créer deux vector stores distincts pour le même nom logique. Le registre en mémoire (`VectorStoreRegistry`) n’est pas thread-safe. Une correction possible est un lock autour de `resolve_store_id` / `get_or_create_vector_store`.
- **Config partagée** : le vector store ID résolu est écrit dans la config globale. En concurrence, un run peut lire l’ID résolu par un autre run. Le code utilise désormais une variable locale par run pour construire `ResearchInfo`, afin qu’un run n’utilise pas l’ID d’un autre.
- **Chroma** : écritures concurrentes dans la même collection ; le moteur gère en général la concurrence, pas de lock explicite côté appli.

### Recommandations

- **Monoutilisateur ou faible concurrence** : comportement actuel acceptable (même base, même collection).
- **Multi-utilisateurs fort** : envisager un vector store (ou nom de collection) par session ou par utilisateur pour éviter partage et races, et/ou ajouter un lock autour de la résolution/création du vector store et documenter que la base de connaissances est partagée en lecture (écritures via dataprep sérialisées).
