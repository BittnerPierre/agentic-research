# Docker (V0)

This document describes the minimal Docker setup for running the existing CLI as-is
(LLM cloud providers, no Docker Compose).

## Build

```bash
docker build -t agentic-research -f docker/Dockerfile.backend .
```

## Run (default config)

```bash
docker run --rm \
  -e OPENAI_API_KEY=YOUR_KEY \
  agentic-research \
  agentic-research --query "test"
```

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
