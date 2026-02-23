#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="models/models.local.env"
if [ ! -f "${ENV_FILE}" ]; then
  echo "Error: ${ENV_FILE} not found. Configure it for local llama.cpp."
  exit 1
fi

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <service> [docker compose logs args]"
  exit 1
fi

docker compose -f docker-compose.yml -f docker-compose.local.yml --env-file "${ENV_FILE}" logs "$@"
