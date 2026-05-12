#!/usr/bin/env bash
set -euo pipefail

if [ ! -L models.env ] && [ ! -f models.env ]; then
  echo "Error: models.env not found. Copy models.env.example and configure it,"
  echo "       or symlink it to one of models/models.*.env."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/_resolve-overlay.sh
. "$SCRIPT_DIR/_resolve-overlay.sh"

APP_VERSION=$(git rev-parse --short HEAD 2>/dev/null || echo dev)

COMPOSE_ARGS=(-f docker-compose.yml -f "$RESOLVED_OVERLAY" --env-file models.env)

# Discover services dynamically from the resolved overlay (different overlays
# expose different services: llama.cpp duo has llm-instruct/llm-reasoning,
# vLLM mono has a single `llm`). Exclude on-demand services.
SERVICES=$(docker compose "${COMPOSE_ARGS[@]}" config --services 2>/dev/null \
  | grep -v -E '^(agentic-research|evaluations)$' \
  | tr '\n' ' ')

echo "🚀 Starting stack (overlay: $RESOLVED_OVERLAY${RESOLVED_SETUP:+, setup: $RESOLVED_SETUP})"
echo "   services: $SERVICES"

image_exists() {
  docker image inspect "$1" >/dev/null 2>&1
}

# Skip rebuild if core images already exist. The llama.cpp image is only
# needed by overlays that build it; vLLM overlays use a prebuilt image and
# don't need it.
if image_exists "agentic-research-agentic-research" \
  && image_exists "agentic-research-dataprep" \
  && image_exists "local/llama.cpp:server-cuda"; then
  echo "Skipping image build (images already exist)."
else
  # shellcheck disable=SC2086
  docker compose "${COMPOSE_ARGS[@]}" build \
    --build-arg APP_VERSION="${APP_VERSION}" \
    $SERVICES
fi

# shellcheck disable=SC2086
docker compose "${COMPOSE_ARGS[@]}" up -d $SERVICES

echo "Services started. Run research with:"
echo "docker compose ${COMPOSE_ARGS[*]} run --rm agentic-research agentic-research --query 'your query'"
