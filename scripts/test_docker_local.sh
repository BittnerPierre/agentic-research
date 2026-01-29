#!/usr/bin/env bash
set -euo pipefail

docker compose -f docker-compose.yml -f docker-compose.local.yml up -d

docker compose -f docker-compose.yml -f docker-compose.local.yml run --rm agentic-research \
  agentic-research --config /app/configs/config-docker-local.yaml \
  --query "Smoke test: local docker stack"
