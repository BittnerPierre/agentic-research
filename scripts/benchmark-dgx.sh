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
  if BENCHMARK_DEFAULTS=$(python3 - "$BENCHMARK_CONFIG" <<'PY'
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
); then
    eval "$BENCHMARK_DEFAULTS"
  fi
fi

RUNS="${RUNS:-${BENCH_DEFAULT_RUNS:-1}}"
CONFIG_FILE_DEFAULT="${BENCH_DEFAULT_CONFIG:-configs/config-docker-dgx.yaml}"
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

setup_config_override=""
if [ -f "$BENCHMARK_CONFIG" ]; then
  setup_config_override=$(python3 - "$BENCHMARK_CONFIG" "$SETUP_NAME" <<'PY'
import sys
from pathlib import Path

import yaml

config_path = Path(sys.argv[1])
setup = sys.argv[2]
try:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
except Exception:
    sys.exit(0)

bench = data.get("benchmark", data)
mapping = bench.get("setup_config_map") or {}
value = mapping.get(setup)
if value:
    print(value)
PY
)
fi

if [ -n "$CONFIG_FILE" ]; then
  EFFECTIVE_CONFIG_FILE="$CONFIG_FILE"
elif [ -n "$setup_config_override" ]; then
  EFFECTIVE_CONFIG_FILE="$setup_config_override"
else
  EFFECTIVE_CONFIG_FILE="$CONFIG_FILE_DEFAULT"
fi

# Resolve compose overlay per setup (issue #169). Setups not listed in
# setup_compose_map fall back to docker-compose.dgx.yml (llama.cpp duo).
setup_compose_override=""
if [ -f "$BENCHMARK_CONFIG" ]; then
  setup_compose_override=$(python3 - "$BENCHMARK_CONFIG" "$SETUP_NAME" <<'PY'
import sys
from pathlib import Path

import yaml

config_path = Path(sys.argv[1])
setup = sys.argv[2]
try:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
except Exception:
    sys.exit(0)

bench = data.get("benchmark", data)
mapping = bench.get("setup_compose_map") or {}
value = mapping.get(setup)
if value:
    print(value)
PY
)
fi
EFFECTIVE_COMPOSE_FILE="${setup_compose_override:-docker-compose.dgx.yml}"
COMPOSE_ARGS=(-f docker-compose.yml -f "$EFFECTIVE_COMPOSE_FILE" --env-file models.env)

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

# 2. Restart Docker stack for the resolved compose overlay (#169).
# Bring up everything except agentic-research / evaluations (those are run
# on-demand via `compose run --rm`).
restart_stack() {
  echo "   compose: $EFFECTIVE_COMPOSE_FILE"
  local services
  services=$(docker compose "${COMPOSE_ARGS[@]}" config --services 2>/dev/null \
    | grep -v -E '^(agentic-research|evaluations)$' \
    | tr '\n' ' ')
  # --remove-orphans is essential when switching between overlays (e.g.
  # llama.cpp duo → vLLM mono): containers from a previous overlay's
  # services not defined in the current one would otherwise stay up and
  # hold their published ports (port 8002 collision observed in #169).
  docker compose "${COMPOSE_ARGS[@]}" down --remove-orphans
  # shellcheck disable=SC2086
  docker compose "${COMPOSE_ARGS[@]}" up -d --wait --wait-timeout 600 $services
}

LAST_SETUP_FILE=".benchmark_last_setup"
if [ "$KEEP_SERVICES" = "true" ]; then
  LAST_SETUP=""
  if [ -f "$LAST_SETUP_FILE" ]; then
    LAST_SETUP=$(cat "$LAST_SETUP_FILE" || true)
  fi
  if [ "$LAST_SETUP" != "$SETUP_NAME" ]; then
    echo "🔄 Restarting Docker services (setup changed)..."
    restart_stack
  else
    echo "♻️  Keeping Docker services running for same setup..."
  fi
  echo "$SETUP_NAME" > "$LAST_SETUP_FILE"
else
  echo "🔄 Restarting Docker services..."
  restart_stack
  echo "$SETUP_NAME" > "$LAST_SETUP_FILE"
fi

# Stack health is enforced by `compose up -d --wait` in restart_stack(),
# which returns non-zero if any healthcheck fails. ChromaDB heartbeat probe
# is kept as a final sanity check (its healthcheck cannot exercise the
# /api/v2 endpoint itself).
echo "⏳ Final ChromaDB heartbeat check..."
for i in 1 2 3; do
  if curl -fsS --max-time 3 "http://127.0.0.1:8000/api/v2/heartbeat" >/dev/null 2>&1; then
    echo "✅ ChromaDB heartbeat OK"
    break
  fi
  if [ "$i" -eq 3 ]; then
    echo "❌ ChromaDB heartbeat failed after 3 attempts"
    docker compose "${COMPOSE_ARGS[@]}" logs --tail 100 chromadb || true
    exit 1
  fi
  sleep 10
done

# 3. Run benchmark
echo "🚀 Running benchmark ($RUNS run(s))..."
if [ -z "$OUTPUT_DIR" ]; then
  TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  OUTPUT_DIR="${OUTPUT_BASE}/run_${TIMESTAMP}"
fi

docker compose "${COMPOSE_ARGS[@]}" run --rm \
  -e BENCHMARK_SETUP_NAME="$SETUP_NAME" \
  agentic-research \
  benchmark-models \
  --benchmark-config "/app/${BENCHMARK_CONFIG}" \
  --config "/app/${EFFECTIVE_CONFIG_FILE}" \
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
