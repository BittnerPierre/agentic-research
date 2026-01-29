#!/usr/bin/env bash
set -euo pipefail

APP_VERSION=$(git rev-parse --short HEAD 2>/dev/null || echo dev)

docker compose -f docker-compose.yml -f docker-compose.local.yml build \
  --build-arg APP_VERSION="${APP_VERSION}" \
  dataprep agentic-research

docker compose -f docker-compose.yml -f docker-compose.local.yml up -d

docker compose -f docker-compose.yml -f docker-compose.local.yml run --rm agentic-research \
  agentic-research --config /app/configs/config-docker-local.yaml \
  --query "Smoke test: local docker stack"
