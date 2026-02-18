#!/usr/bin/env bash
# Benchmark a specific model setup on DGX
set -euo pipefail

SETUP_NAME=${1:-}
shift || true

RUNS=""
OUTPUT_DIR=""
CONFIG_FILE=""
SYLLABUS_FILE=""
VECTOR_STORE_NAME=""
REPORT_WARMUP=""
DROP_WORST_RUN=""
TIMEOUT_SECONDS=""
KEEP_SERVICES=""
BENCHMARK_CONFIG="configs/benchmark-default.yaml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h)
      echo "Usage: $0 <setup_name> [--benchmark-config PATH] [--config PATH] [--syllabus PATH] [--runs N] [--output-dir DIR] [--vector-store-name NAME] [--report-warmup|--no-report-warmup] [--drop-worst-run|--no-drop-worst-run] [--timeout-seconds N] [--keep-services|--no-keep-services]"
      exit 0
      ;;
    --benchmark-config)
      BENCHMARK_CONFIG="${2:-}"
      shift 2
      ;;
    --config)
      CONFIG_FILE="${2:-}"
      shift 2
      ;;
    --syllabus)
      SYLLABUS_FILE="${2:-}"
      shift 2
      ;;
    --runs)
      RUNS="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --vector-store-name)
      VECTOR_STORE_NAME="${2:-}"
      shift 2
      ;;
    --report-warmup)
      REPORT_WARMUP="true"
      shift
      ;;
    --no-report-warmup)
      REPORT_WARMUP="false"
      shift
      ;;
    --drop-worst-run)
      DROP_WORST_RUN="true"
      shift
      ;;
    --no-drop-worst-run)
      DROP_WORST_RUN="false"
      shift
      ;;
    --timeout-seconds)
      TIMEOUT_SECONDS="${2:-}"
      shift 2
      ;;
    --keep-services)
      KEEP_SERVICES="true"
      shift
      ;;
    --no-keep-services)
      KEEP_SERVICES="false"
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: $0 <setup_name> [--benchmark-config PATH] [--config PATH] [--syllabus PATH] [--runs N] [--output-dir DIR] [--vector-store-name NAME] [--report-warmup|--no-report-warmup] [--drop-worst-run|--no-drop-worst-run] [--timeout-seconds N] [--keep-services|--no-keep-services]"
      exit 1
      ;;
  esac
done

if [ -z "$SETUP_NAME" ]; then
  echo "Usage: $0 <setup_name> [--benchmark-config PATH] [--config PATH] [--syllabus PATH] [--runs N] [--output-dir DIR] [--vector-store-name NAME] [--report-warmup|--no-report-warmup] [--drop-worst-run|--no-drop-worst-run] [--timeout-seconds N] [--keep-services|--no-keep-services]"
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

if [ -f "$BENCHMARK_CONFIG" ]; then
  if BENCHMARK_DEFAULTS=$(python3 - <<'PY'
import shlex
import sys
from pathlib import Path

import yaml

path = Path(sys.argv[1])
try:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
except Exception:
    sys.exit(1)

bench = data.get("benchmark", data)

def emit(key, value):
    if value is None:
        print(f"{key}=")
    elif isinstance(value, bool):
        print(f"{key}={'true' if value else 'false'}")
    else:
        print(f"{key}={shlex.quote(str(value))}")

emit("BENCH_DEFAULT_RUNS", bench.get("runs"))
emit("BENCH_DEFAULT_OUTPUT_BASE", bench.get("output_dir"))
emit("BENCH_DEFAULT_CONFIG", bench.get("config_file"))
emit("BENCH_DEFAULT_SYLLABUS", bench.get("syllabus_file"))
emit("BENCH_DEFAULT_VECTOR_STORE", bench.get("vector_store_name"))
emit("BENCH_DEFAULT_REPORT_WARMUP", bench.get("report_warmup"))
emit("BENCH_DEFAULT_DROP_WORST", bench.get("drop_worst_run"))
emit("BENCH_DEFAULT_TIMEOUT", bench.get("timeout_seconds"))
emit("BENCH_DEFAULT_KEEP_SERVICES", bench.get("keep_services"))
PY
"$BENCHMARK_CONFIG"); then
    eval "$BENCHMARK_DEFAULTS"
  fi
fi

RUNS="${RUNS:-${BENCH_DEFAULT_RUNS:-1}}"
CONFIG_FILE="${CONFIG_FILE:-${BENCH_DEFAULT_CONFIG:-configs/config-docker-dgx.yaml}}"
SYLLABUS_FILE="${SYLLABUS_FILE:-${BENCH_DEFAULT_SYLLABUS:-test_files/query_advanced_1.md}}"
VECTOR_STORE_NAME="${VECTOR_STORE_NAME:-${BENCH_DEFAULT_VECTOR_STORE:-agentic-research-dgx}}"
REPORT_WARMUP="${REPORT_WARMUP:-${BENCH_DEFAULT_REPORT_WARMUP:-}}"
DROP_WORST_RUN="${DROP_WORST_RUN:-${BENCH_DEFAULT_DROP_WORST:-}}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-${BENCH_DEFAULT_TIMEOUT:-}}"
KEEP_SERVICES="${KEEP_SERVICES:-${BENCH_DEFAULT_KEEP_SERVICES:-false}}"
OUTPUT_BASE="${BENCH_DEFAULT_OUTPUT_BASE:-benchmarks}"

if [ -z "$SYLLABUS_FILE" ]; then
  echo "Error: --syllabus must not be empty"
  exit 1
fi

REPORT_WARMUP_FLAG=""
if [ "$REPORT_WARMUP" = "true" ]; then
  REPORT_WARMUP_FLAG="--report-warmup"
elif [ "$REPORT_WARMUP" = "false" ]; then
  REPORT_WARMUP_FLAG="--no-report-warmup"
fi

DROP_WORST_FLAG=""
if [ "$DROP_WORST_RUN" = "true" ]; then
  DROP_WORST_FLAG="--drop-worst-run"
elif [ "$DROP_WORST_RUN" = "false" ]; then
  DROP_WORST_FLAG="--no-drop-worst-run"
fi

echo "========================================"
echo "Benchmark Setup: $SETUP_NAME"
echo "========================================"

# 1. Change symlink
echo "🔗 Switching to $MODELS_ENV..."
ln -sf "$MODELS_ENV" models.env

# 2. Restart Docker
LAST_SETUP_FILE=".benchmark_last_setup"
if [ "$KEEP_SERVICES" = "true" ]; then
  LAST_SETUP=""
  if [ -f "$LAST_SETUP_FILE" ]; then
    LAST_SETUP=$(cat "$LAST_SETUP_FILE" || true)
  fi
  if [ "$LAST_SETUP" != "$SETUP_NAME" ]; then
    echo "🔄 Restarting Docker services (setup changed)..."
    ./scripts/stop-docker-dgx.sh
    ./scripts/start-docker-dgx.sh
  else
    echo "♻️  Keeping Docker services running for same setup..."
  fi
  echo "$SETUP_NAME" > "$LAST_SETUP_FILE"
else
  echo "🔄 Restarting Docker services..."
  ./scripts/stop-docker-dgx.sh
  ./scripts/start-docker-dgx.sh
  echo "$SETUP_NAME" > "$LAST_SETUP_FILE"
fi

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
  OUTPUT_DIR="${OUTPUT_BASE}/run_${TIMESTAMP}"
fi

docker compose -f docker-compose.yml -f docker-compose.dgx.yml --env-file models.env run --rm \
  -e BENCHMARK_SETUP_NAME="$SETUP_NAME" \
  agentic-research \
  benchmark-models \
  --benchmark-config "/app/${BENCHMARK_CONFIG}" \
  --config "/app/${CONFIG_FILE}" \
  --syllabus "/app/${SYLLABUS_FILE}" \
  --runs "$RUNS" \
  --output "/app/$OUTPUT_DIR" \
  --vector-store-name "$VECTOR_STORE_NAME" \
  $REPORT_WARMUP_FLAG \
  $DROP_WORST_FLAG \
  ${TIMEOUT_SECONDS:+--timeout-seconds "$TIMEOUT_SECONDS"}

echo ""
echo "========================================"
echo "✅ Benchmark completed!"
echo "========================================"
echo "Results saved to: $OUTPUT_DIR"
echo ""
