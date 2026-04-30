#!/usr/bin/env bash
set -euo pipefail

# Stop the DGX Spark stack in vLLM mono-model mode (gpt-oss-20b, WS1).
# Default env file: models/models.vllm-gptoss20b-mono.env (override via $VLLM_ENV_FILE).

ENV_FILE="${VLLM_ENV_FILE:-models/models.vllm-gptoss20b-mono.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Error: env file '$ENV_FILE' not found."
  exit 1
fi

docker compose -f docker-compose.yml -f docker-compose.dgx-vllm-gptoss20b-mono.yml --env-file "$ENV_FILE" down

echo "Stack stopped."
