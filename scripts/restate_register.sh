#!/usr/bin/env bash
set -euo pipefail

NETWORK=${RESTATE_DOCKER_NETWORK:-agentic-research_default}
ADMIN_URL=${RESTATE_ADMIN_URL:-http://restate:9070}
SERVICE_URL=${RESTATE_WRITER_SERVICE_URL:-http://writer-restate:9080}

docker run --rm --network "${NETWORK}" \
  -e RESTATE_ADMIN_URL="${ADMIN_URL}" \
  docker.restate.dev/restatedev/restate-cli:latest \
  deployments register "${SERVICE_URL}" -y --use-http1.1 --force
