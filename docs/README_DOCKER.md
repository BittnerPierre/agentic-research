# Docker Deployment Guide

## Architecture Overview

### Local Development Stack
- **Use case**: Local dev, CPU only
- **Services**: ChromaDB + llama-cpp-cpu + dataprep + CLI
- **Configuration**: `configs/config-docker-local.yaml`
- **Models**: CPU, light models
  - `sentence-transformers` is included in the Docker image (used by the default embedding function).
  - Local model paths/IDs can be overridden via `models.env`.

### DGX Spark Production Stack
- **Use case**: DGX Spark GPU
- **Services**: ChromaDB + embeddings-gpu + llm-instruct + llm-reasoning + dataprep + CLI
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
   docker compose -f docker-compose.yml -f docker-compose.local.yml --env-file models.env up -d
   ```

Note: Docker on macOS runs Linux containers, so llama.cpp runs CPU-only in Docker. For Metal GPU
inference, run llama.cpp natively on macOS outside Docker.

3. Run research:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.local.yml --env-file models.env run --rm agentic-research \
     agentic-research --config /app/configs/config-docker-local.yaml \
     --query "Your research question"
   ```

### Local Smoke Test (Minimal QA)

```bash
bash scripts/test_docker_local_smoke.sh
```

4. Stop services:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.local.yml down
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
   docker compose -f docker-compose.yml -f docker-compose.dgx.yml \
     --env-file models.env up -d
   ```

3. Run research:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.dgx.yml \
     --env-file models.env run --rm agentic-research \
     agentic-research --config /app/configs/config-docker-dgx.yaml \
     --query "Your research question"
   ```

4. Stop services:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.dgx.yml down
   ```

## Testing

### Smoke Test Local
```bash
bash scripts/test_docker_local.sh
```

### Smoke Test DGX
```bash
bash scripts/test_docker_dgx.sh
```

## Troubleshooting

### ChromaDB connection issues
- Ensure `chromadb` service is running: `docker compose ps`
- Check logs: `docker compose logs chromadb`
- Verify config uses `chroma_host: chromadb`

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
- Command: `uvx chroma-mcp`
- Tool allowlist: `chroma_query_documents`, `chroma_get_documents`
- Used by search agents during research
