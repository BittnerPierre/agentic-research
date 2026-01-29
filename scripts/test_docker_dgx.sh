#!/usr/bin/env bash
set -euo pipefail

if [ ! -f models.env ]; then
  echo "Error: models.env not found. Copy models.env.example and configure it."
  exit 1
fi

docker compose -f docker-compose.yml -f docker-compose.dgx.yml --env-file models.env up -d

docker compose -f docker-compose.yml -f docker-compose.dgx.yml --env-file models.env run --rm agentic-research \
  agentic-research --config /app/configs/config-docker-dgx.yaml \
  --query "Smoke test: dgx docker stack"
