#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/_resolve-overlay.sh
. "$SCRIPT_DIR/_resolve-overlay.sh"

echo "📦 Stopping stack (overlay: $RESOLVED_OVERLAY${RESOLVED_SETUP:+, setup: $RESOLVED_SETUP})"

# --remove-orphans cleans up containers from a previous overlay (e.g. vLLM
# `llm-1` left over after switching to llama.cpp duo, which would otherwise
# hold the network and block subsequent `up` — see #182).
docker compose -f docker-compose.yml -f "$RESOLVED_OVERLAY" down --remove-orphans
