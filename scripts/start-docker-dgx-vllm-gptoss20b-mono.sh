#!/usr/bin/env bash
set -euo pipefail

# Start the DGX Spark stack in vLLM mono-model mode (WS1).
# Default env file: models/models.vllm-gptoss20b-mono.env (override via $VLLM_ENV_FILE).

ENV_FILE="${VLLM_ENV_FILE:-models/models.vllm-gptoss20b-mono.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Error: env file '$ENV_FILE' not found."
  exit 1
fi

APP_VERSION=$(git rev-parse --short HEAD 2>/dev/null || echo dev)

image_exists() {
  docker image inspect "$1" >/dev/null 2>&1
}

if image_exists "agentic-research-agentic-research" \
  && image_exists "agentic-research-dataprep" \
  && image_exists "local/llama.cpp:server-cuda"; then
  echo "Skipping image build (images already exist)."
else
  docker compose -f docker-compose.yml -f docker-compose.dgx-vllm-gptoss20b-mono.yml --env-file "$ENV_FILE" build \
    --build-arg APP_VERSION="${APP_VERSION}" \
    dataprep agentic-research embeddings-gpu
fi

docker compose -f docker-compose.yml -f docker-compose.dgx-vllm-gptoss20b-mono.yml --env-file "$ENV_FILE" up -d \
  chromadb dataprep embeddings-gpu llm

echo "Services started. Run research with:"
echo "docker compose -f docker-compose.yml -f docker-compose.dgx-vllm-gptoss20b-mono.yml --env-file $ENV_FILE run --rm agentic-research agentic-research --config /app/configs/config-docker-dgx-vllm-gptoss20b-mono.yaml --query 'your query'"
