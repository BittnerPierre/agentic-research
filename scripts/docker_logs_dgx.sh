#!/usr/bin/env bash
set -euo pipefail

if [ ! -f models.env ]; then
  echo "Error: models.env not found. Copy models.env.example and configure it."
  exit 1
fi

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <service> [docker compose logs args]"
  echo "  service: dataprep | agentic-research | chromadb | embeddings-gpu | llm | ..."
  echo "  Example: $0 llm -f       # follow vLLM logs on the active overlay"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/_resolve-overlay.sh
. "$SCRIPT_DIR/_resolve-overlay.sh"

docker compose -f docker-compose.yml -f "$RESOLVED_OVERLAY" --env-file models.env logs "$@"
