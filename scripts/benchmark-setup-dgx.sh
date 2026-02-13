#!/usr/bin/env bash
# Benchmark a specific model setup on DGX
set -euo pipefail

SETUP_NAME=${1:-}
shift || true

RUNS=1
OUTPUT_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --runs)
      RUNS="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: $0 <setup_name> [--runs N] [--output-dir DIR]"
      exit 1
      ;;
  esac
done

if [ -z "$SETUP_NAME" ]; then
  echo "Usage: $0 <setup_name> [--runs N] [--output-dir DIR]"
  echo ""
  echo "Available setups:"
  echo "  - ministral"
  echo "  - mistralai"
  echo "  - glm"
  echo "  - qwen"
  echo "  - openai"
  exit 1
fi

MODELS_ENV="models/models.${SETUP_NAME}.env"

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

wait_http() {
  local name="$1"
  local url="$2"
  local retries="${3:-3}"
  local delay="${4:-20}"
  local service="${5:-}"

  echo "⏳ Waiting for ${name} at ${url}..."
  for ((i=1; i<=retries; i++)); do
    if curl -fsS --max-time 3 "$url" >/dev/null 2>&1; then
      echo "✅ ${name} is up"
      return 0
    fi
    sleep "$delay"
  done

  echo "❌ ${name} did not become ready: ${url}"
  if [ -n "$service" ]; then
    echo "📋 Last logs for service: ${service}"
    ./scripts/docker_logs_dgx.sh "$service" --tail=100 || true
  fi
  return 1
}

# Wait for critical services to be ready (fail-fast before benchmark).
echo "⏳ Initial warmup wait..."
sleep 10

wait_http "ChromaDB" "http://127.0.0.1:8000/api/v2/heartbeat" 3 20 "chromadb"
wait_http "LLM instruct (llama.cpp)" "http://127.0.0.1:${LLM_INSTRUCT_PORT:-8002}/health" 3 20 "llm-instruct"
wait_http "LLM reasoning (llama.cpp)" "http://127.0.0.1:${LLM_REASONING_PORT:-8004}/health" 3 20 "llm-reasoning"
wait_http "Embeddings (llama.cpp)" "http://127.0.0.1:${EMBEDDINGS_PORT:-8003}/health" 3 20 "embeddings-gpu"

# 3. Run benchmark
echo "🚀 Running benchmark ($RUNS run(s))..."
if [ -z "$OUTPUT_DIR" ]; then
  TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  OUTPUT_DIR="benchmarks/run_${TIMESTAMP}"
fi

docker compose -f docker-compose.yml -f docker-compose.dgx.yml --env-file models.env run --rm \
  -e BENCHMARK_SETUP_NAME="$SETUP_NAME" \
  agentic-research \
  benchmark-models \
  --config /app/configs/config-docker-dgx.yaml \
  --syllabus /app/test_files/query_advanced_1.md \
  --runs "$RUNS" \
  --output "/app/$OUTPUT_DIR" \
  --vector-store-name "agentic-research-dgx"

echo ""
echo "========================================"
echo "✅ Benchmark completed!"
echo "========================================"
echo "Results saved to: $OUTPUT_DIR"
echo ""
