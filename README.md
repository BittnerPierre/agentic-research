# Agentic Research

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

- Dependency requirements are driven by the `vector_search.provider`, not by the
  environment (local vs DGX).
- `sentence-transformers` is required when using the default
  `sentence-transformers:*` embedding function (used by `local`/`chroma`).
  The first run will download the model weights.
- `chromadb` (Python client) is required for the `chroma` provider because
  dataprep uses `chromadb.HttpClient` and the `chroma-mcp` client depends on it.

Note on embeddings config: in DGX Docker, the embeddings model is configured in
two places: models.env (full path for embeddings-gpu) and
configs/config-docker-dgx.yaml (model name for Chroma embedding function). For
now, keep them in sync whenever the embedding model changes.

Note: we could modularize dependencies later (e.g. `agentic-research[chroma]`,
`agentic-research[openai]`), but for now we keep a single package for simplicity.

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

## Benchmarking

Benchmark defaults live in `configs/benchmark-default.yaml` (runs, models, syllabus file, etc.).
CLI flags override the config.

```bash
# Run a single setup with warmup reporting and worst-run exclusion
./scripts/benchmark-dgx.sh mistralai --report-warmup --drop-worst-run

# Run a subset of setups
./scripts/benchmark-all-dgx.sh --models mistralai,qwen --runs 3

# Use a custom benchmark config
./scripts/benchmark-all-dgx.sh --benchmark-config configs/benchmark-default.yaml
```

Per-setup config override (mapping) can be defined in `configs/benchmark-default.yaml`:

```yaml
benchmark:
  config_file: configs/config-docker-dgx.yaml
  setup_config_map:
    openai-api: configs/tests/config-dgx-remote-openai-api.yaml
    mistral-api: configs/tests/config-dgx-remote-mistral-api.yaml
```

## Vector search providers

- `openai`: uses `FileSearchTool` with the configured vector store id.
- `local`: uses the local vector search tool.
- `chroma`: tools are provided by the Chroma MCP server configured under `vector_mcp`
  (e.g. `chroma_query_documents`, `chroma_get_documents`).
