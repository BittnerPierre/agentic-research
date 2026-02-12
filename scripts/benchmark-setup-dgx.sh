#!/usr/bin/env bash
# Benchmark a specific model setup on DGX
set -euo pipefail

SETUP_NAME=${1:-}

if [ -z "$SETUP_NAME" ]; then
  echo "Usage: $0 <setup_name>"
  echo ""
  echo "Available setups:"
  echo "  - ministral"
  echo "  - mistralai"
  echo "  - glm"
  echo "  - qwen"
  echo "  - openai"
  exit 1
fi

MODELS_ENV="models.${SETUP_NAME}.env"

if [ ! -f "$MODELS_ENV" ]; then
  echo "Error: $MODELS_ENV not found"
  exit 1
fi

echo "========================================"
echo "Benchmark Setup: $SETUP_NAME"
echo "========================================"

# 1. Change symlink
echo "🔗 Switching to $MODELS_ENV..."
ln -sf "$MODELS_ENV" models.env

# 2. Restart Docker
echo "🔄 Restarting Docker services..."
./scripts/stop-docker-dgx.sh
./scripts/start-docker-dgx.sh

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# 3. Run benchmark
echo "🚀 Running benchmark (2 runs)..."
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="benchmarks/run_${TIMESTAMP}"

docker compose -f docker-compose.yml -f docker-compose.dgx.yml --env-file models.env run --rm \
  -e BENCHMARK_SETUP_NAME="$SETUP_NAME" \
  agentic-research \
  benchmark-models \
  --config /app/configs/config-docker-dgx.yaml \
  --syllabus /app/test_files/query_advanced_1.md \
  --runs 2 \
  --output "/app/$OUTPUT_DIR" \
  --vector-store-name "agentic-research-dgx"

echo ""
echo "========================================"
echo "✅ Benchmark completed!"
echo "========================================"
echo "Results saved to: $OUTPUT_DIR"
echo ""
