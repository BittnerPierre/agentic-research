#!/usr/bin/env bash
set -euo pipefail

STACK=${STACK:-dgx}
SERVICE=${1:-llm-instruct}
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.${STACK}.yml"

CID=$(docker compose $COMPOSE_FILES ps -q "$SERVICE")
if [ -z "$CID" ]; then
  echo "Service $SERVICE not running"
  exit 1
fi

echo "== container =="
echo "$CID"

echo "== nvidia-smi =="
docker exec "$CID" nvidia-smi -L || true

echo "== llama.cpp CUDA libs =="
docker exec "$CID" sh -lc 'ls -l /app/libggml-cuda.so /app/libggml-cpu.so' || true

echo "== recent logs (CUDA init) =="
docker logs "$CID" 2>&1 | grep -E "ggml_cuda_init|loaded CUDA backend" | tail -n 20 || true
