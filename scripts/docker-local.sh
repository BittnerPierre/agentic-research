#!/usr/bin/env bash
set -euo pipefail

docker compose -f docker-compose.yml -f docker-compose.local.yml up -d

echo "Services started. Run research with:"
echo "docker compose -f docker-compose.yml -f docker-compose.local.yml run --rm agentic-research agentic-research --config /app/configs/config-docker-local.yaml --query 'your query'"
