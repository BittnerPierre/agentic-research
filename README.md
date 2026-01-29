# Research bot

[![CI](https://github.com/BittnerPierre/agentic-research/workflows/CI/badge.svg)](https://github.com/BittnerPierre/agentic-research/actions/workflows/ci.yml)

This is a simple example of a multi-agent research assistant with local MCP. To run it:

```bash
poetry install
poetry run dataprep_server
poetry run agentic-research
```

## Docker / Containers

For Docker/Docker Compose usage (local, DGX Spark, smoke tests, logs), see
`docs/README_DOCKER.md`.

## Dependencies

- `sentence-transformers` is required when using the default
  `sentence-transformers:*` embedding function (used by local/chroma providers).
  The first run will download the model weights.

## Architecture

The flow is:

1. User enters their research topic
2. `planner_agent` comes up with a plan to search the knowlege_base for information. The plan is a list of search queries, with a search term and a reason for each query.
3. For each search item, we run a `search_agent`, which uses the knowlege_base tool to search for that term and summarize the results. These all run in parallel.
4. Finally, the `writer_agent` receives the search summaries, and creates a written report.

## CLI Usage

The `agentic-research` tool can be used via Poetry with different options:

### Available Options

- `--syllabus`: Path to a syllabus file to use as the query
- `--manager`: Manager implementation to use (options: `agentic_manager`, `manager`, or a custom import path)
- `--query`: Research query (alternative to interactive input)
- `--dataprep-host`: DataPrep MCP server host override
- `--dataprep-port`: DataPrep MCP server port override

### Usage Examples

```bash
# Interactive mode with the default manager
poetry run agentic-research

# Use a syllabus file as the query
poetry run agentic-research --syllabus test_files/syllabus.md

# Specify a particular manager
poetry run agentic-research --syllabus test_files/syllabus.md --manager manager

# Specify a custom manager
poetry run agentic-research --manager custom_module.CustomManager

# Pass a query directly on the command line
poetry run agentic-research --query "Retrieval Augmented Generation"

# Combine multiple options
poetry run agentic-research --query "Agents in LLM" --manager agentic_manager

# Utiliser un serveur dataprep sur un autre port
poetry run agentic-research --dataprep-host 127.0.0.1 --dataprep-port 8010
```

## Dataprep server

Vous pouvez démarrer le serveur dataprep sur un host/port spécifique :

```bash
poetry run dataprep_server --host 127.0.0.1 --port 8010
```

### Configuration

The default manager can be configured in `configs/config-default.yaml`:

```yaml
manager:
  default_manager: "agentic_manager" # Options: agentic_manager (Supervisor with CoT), deep_manager (Deep Agents approach), manager (simple example), ou chemin.vers.ClasseManager
```

You can also set the default manager via the `DEFAULT_MANAGER` environment variable.
Use `--config` to load a different config file.

## Vector search providers

- `openai`: uses `FileSearchTool` with the configured vector store id.
- `local`: uses the local vector search tool.
- `chroma`: tools are provided by the Chroma MCP server configured under `vector_mcp`
  (e.g. `chroma_query_documents`, `chroma_get_documents`).
