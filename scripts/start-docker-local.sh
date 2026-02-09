#!/usr/bin/env bash
set -euo pipefail

if [ ! -f models.env ]; then
  echo "Error: models.env not found. Copy models.env.example and configure it."
  exit 1
fi

if [ "${SKIP_LLAMA_CPP_BUILD:-0}" != "1" ]; then
  bash scripts/build_llama_cpp_arm64.sh
else
  echo "Skipping llama.cpp build (SKIP_LLAMA_CPP_BUILD=1)."
fi

APP_VERSION=$(git rev-parse --short HEAD 2>/dev/null || echo dev)

docker compose -f docker-compose.yml -f docker-compose.local.yml --env-file models.env build \
  --build-arg APP_VERSION="${APP_VERSION}" \
  dataprep agentic-research

docker compose -f docker-compose.yml -f docker-compose.local.yml --env-file models.env up -d \
  chromadb dataprep llama-cpp-cpu restate writer-restate

echo "Services started. Run research with:"
echo "docker compose -f docker-compose.yml -f docker-compose.local.yml --env-file models.env run --rm agentic-research agentic-research --config /app/configs/config-docker-local.yaml --query 'your query'"
