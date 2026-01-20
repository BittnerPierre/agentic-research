# Docker (V0)

This document describes the minimal Docker setup for running the existing CLI as-is,
plus a Docker Compose workflow for local development.

## Build

```bash
docker build -t agentic-research -f docker/Dockerfile.backend .
```

## Build (DataPrep MCP server)

```bash
docker build -t agentic-research-dataprep -f docker/Dockerfile.dataprep .
```

## Run (default config)

```bash
docker run --rm \
  -e OPENAI_API_KEY=YOUR_KEY \
  agentic-research \
  agentic-research --query "test"
```

## Docker Compose (local development)

Create a `.env` file with your API keys (Compose reads it at runtime, nothing is
baked into the image):

```bash
OPENAI_API_KEY=YOUR_KEY
LANGSMITH_API_KEY=YOUR_KEY
LANGSMITH_PROJECT=agentic-research
```

Start the DataPrep MCP server (long-running service):

```bash
docker compose up -d dataprep
```

Run the CLI against the MCP server (one-off client):

```bash
docker compose run --rm agentic-research \
  agentic-research --query "test"
```

Run with a local syllabus file (mount `test_files`):

```bash
docker compose run --rm \
  -v "$(pwd)/test_files:/app/test_files" \
  agentic-research \
  agentic-research --syllabus /app/test_files/your_file.md
```

## V1 Infrastructure (multi-service stack, infra-only)

V1 wires the full stack in Docker but does not yet switch the app off OpenAI
vector store or cloud models (Issue 12 handles file_search migration). These
services are for local/DGX wiring and smoke checks.

Local (CPU) stack:

```bash
docker compose -f docker-compose.yml -f docker-compose.v1.local.yml \
  --profile v1-local up -d dataprep chromadb embeddings-cpu llama-cpp-cpu
```

DGX Spark (GPU) stack:

```bash
docker compose -f docker-compose.yml -f docker-compose.v1.dgx.yml \
  --profile v1-dgx up -d dataprep chromadb embeddings-gpu llama-cpp-gpu
```

Notes:

- Set model choices in `docker-compose.v1.local.yml` or
  `docker-compose.v1.dgx.yml`.
- Place GGUF models under `./models` and update the llama.cpp command with the
  correct filename.
- `embeddings-cpu` and `llama-cpp-cpu` use `platform: linux/amd64` for Mac;
  remove if you build native images.

## Run (mount local config/data)

```bash
docker run --rm \
  -e OPENAI_API_KEY=YOUR_KEY \
  -v "$(pwd)/config.yaml:/app/config.yaml" \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/output:/app/output" \
  agentic-research \
  agentic-research --query "test"
```

## Notes

- The container runs the CLI; there is no exposed port in V0.
- If you use providers other than OpenAI, pass the relevant API keys as env vars.
- `MCP_DATAPREP_URL` overrides the DataPrep server URL (defaults to
  `http://localhost:8001/sse`).
- `MCP_FS_COMMAND` overrides the filesystem MCP server command. The Docker image
  uses `node` with `MCP_FS_ARGS` pointing at the bundled server script; local
  runs default to `npx`.
- `MCP_FS_ARGS` sets extra args for the filesystem MCP command. In Docker
  Compose it points to `.../server-filesystem/dist/index.js`.
