# Docker Deployment Guide

## Architecture Overview

### Local Development Stack

- **Use case**: Local dev, CPU only
- **Services**: ChromaDB + llama-cpp-cpu + dataprep + restate + writer-restate + CLI
- **Configuration**: `configs/config-docker-local.yaml`
- **Models**: CPU, light models
  - `sentence-transformers` is included in the Docker image (used by the default embedding function).
  - Local model paths/IDs can be overridden via `models.env`.

### DGX Spark Production Stack

- **Use case**: DGX Spark GPU
- **Services**: ChromaDB + embeddings-gpu + llm-instruct + llm-reasoning + dataprep + restate + writer-restate + CLI
- **Configuration**: `configs/config-docker-dgx.yaml`
- **Models**: GPU GGUF models wired via `models.env`

## Quick Start

### Local Development

1. Create `.env` (optional):

   ```bash
   LANGSMITH_API_KEY=your_key
   LANGSMITH_PROJECT=agentic-research
   ```

2. Start services:

   ```bash
   # Build llama.cpp image locally (arm64 on Apple Silicon)
   bash scripts/build_llama_cpp_arm64.sh

   # Rebuild app images to avoid stale code (APP_VERSION is logged at startup)
   bash scripts/start-docker-local.sh
   ```

Note: Docker on macOS runs Linux containers, so llama.cpp runs CPU-only in Docker. For Metal GPU
inference, run llama.cpp natively on macOS outside Docker.

3. Register the Writer Restate service:

   ```bash
   restate deployments register http://writer-restate:9080 -y --use-http1.1 --force
   ```

   Or via Docker CLI image:
   ```bash
   bash scripts/restate_register.sh
   ```

4. Run research (deep_manager uses Restate writer by default):
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.local.yml --env-file models.env run --rm agentic-research \
     agentic-research --config /app/configs/config-docker-local.yaml \
     --query "Your research question"
   ```

### Local Smoke Test (Minimal QA)

```bash
bash scripts/test_docker_local_smoke.sh
```

5. Stop services:
   ```bash
   bash scripts/stop-docker-local.sh
   ```

### DGX Spark Production

1. Configure models in `models.env` (see `models.env.example`):

   ```bash
   cp models.env.example models.env
   # Edit models.env with your snapshot IDs
   ```

2. Start services:

   ```bash
   # Rebuild app images to avoid stale code (APP_VERSION is logged at startup)
   bash scripts/start-docker-dgx.sh
   ```

3. Register the Writer Restate service:

   ```bash
   restate deployments register http://writer-restate:9080 -y --use-http1.1 --force
   ```

   Or via Docker CLI image:
   ```bash
   bash scripts/restate_register.sh
   ```

4. Run research (deep_manager uses Restate writer by default):

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.dgx.yml \
     --env-file models.env run --rm agentic-research \
     agentic-research --config /app/configs/config-docker-dgx.yaml \
     --query "Your research question"
   ```

5. Stop services:
   ```bash
   bash scripts/stop-docker-dgx.sh
   ```

## Testing

### Smoke Test Local (QA manager)

```bash
bash scripts/test_docker_local_smoke.sh
```

### Smoke Test DGX (QA manager)

```bash
bash scripts/test_docker_dgx_smoke.sh
```

### E2E Test Local (agentic manager)

```bash
bash scripts/test_docker_local.sh
```

### E2E Test DGX (agentic manager)

```bash
bash scripts/test_docker_dgx.sh
```

## UAT Restate

Voir `docs/UAT_RESTATE.md` pour le parcours UAT Restate + Writer.

## Troubleshooting

### ChromaDB connection issues

- Ensure `chromadb` service is running: `docker compose ps`
- Check logs: `docker compose logs chromadb`
- Verify config uses `chroma_host: chromadb`
- If you see repeated ONNX model downloads, ensure the Chroma client cache volume is mounted
  (./data/chroma-cache -> /root/.cache/chroma in docker-compose.yml for agentic-research/evaluations).

### Model loading issues (DGX)

- Verify `models.env` paths are correct
- Check GPU availability: `docker compose logs llm-instruct`
- Ensure models are available under `${MODELS_DIR}`

## Configuration Details

### Provider Selection

The `vector_search.provider` in config determines the backend:

- `openai`: OpenAI file_search (cloud, requires API key)
- `local`: Local mock (for tests only)
- `chroma`: ChromaDB via MCP

### Docker Configs

- `configs/config-docker-local.yaml`: Local development (CPU)
- `configs/config-docker-dgx.yaml`: DGX production (GPU)

### MCP Integration

The `vector_mcp` section enables agents to query ChromaDB directly:

- Command: `chroma-mcp`
- Tool allowlist: `chroma_query_documents`, `chroma_get_documents`
- Used by search agents during research

### Note on `docker compose run`

If you start services with a plain `docker compose up -d`, the `agentic-research` service
container will stay running. When you run a query with `docker compose run --rm agentic-research ...`,
Docker creates a new one-off container. This is expected. The provided `start-docker-*` scripts
start only dependencies (not the CLI container). If you prefer to reuse an existing container,
use `docker compose exec agentic-research ...`.
