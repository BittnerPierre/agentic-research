#!/usr/bin/env bash
set -euo pipefail

if [ ! -f models.env ]; then
  echo "Error: models.env not found. Copy models.env.example and configure it."
  exit 1
fi

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <service> [docker compose logs args]"
  exit 1
fi

docker compose -f docker-compose.yml -f docker-compose.dgx.yml --env-file models.env logs "$@"
