#!/usr/bin/env bash
# Benchmark all model setups on DGX
set -euo pipefail

DEFAULT_SETUPS=("ministral" "mistralai" "glm" "qwen" "openai")
SETUPS=()
RUNS=""
MODELS_RAW=""
CLI_CONFIG_FILE=""
CONFIG_FILE_DEFAULT=""
SYLLABUS_FILE=""
VECTOR_STORE_NAME=""
REPORT_WARMUP=""
DROP_WORST_RUN=""
TIMEOUT_SECONDS=""
KEEP_SERVICES=""
BENCHMARK_CONFIG="configs/benchmark-default.yaml"
INTERACTIVE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h)
      echo "Usage: $0 [--benchmark-config PATH] [--models a,b,c] [--config PATH] [--syllabus PATH] [--runs N] [--vector-store-name NAME] [--report-warmup|--no-report-warmup] [--drop-worst-run|--no-drop-worst-run] [--timeout-seconds N] [--keep-services|--no-keep-services] [--interactive]"
      exit 0
      ;;
    --benchmark-config)
      BENCHMARK_CONFIG="${2:-}"
      shift 2
      ;;
    --models)
      MODELS_RAW="${2:-}"
      shift 2
      ;;
    --config)
      CLI_CONFIG_FILE="${2:-}"
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
    --interactive)
      INTERACTIVE=true
      shift
      ;;
    --auto)
      # Backward-compatible no-op: default is already non-interactive.
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: $0 [--benchmark-config PATH] [--models a,b,c] [--config PATH] [--syllabus PATH] [--runs N] [--vector-store-name NAME] [--report-warmup|--no-report-warmup] [--drop-worst-run|--no-drop-worst-run] [--timeout-seconds N] [--keep-services|--no-keep-services] [--interactive]"
      exit 1
      ;;
  esac
done

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
models = bench.get("models") or []
emit("BENCH_DEFAULT_MODELS", ",".join(models))
PY
); then
    eval "$BENCHMARK_DEFAULTS"
  fi
fi

RUNS="${RUNS:-${BENCH_DEFAULT_RUNS:-3}}"
CONFIG_FILE_DEFAULT="${BENCH_DEFAULT_CONFIG:-configs/config-docker-dgx.yaml}"
SYLLABUS_FILE="${SYLLABUS_FILE:-${BENCH_DEFAULT_SYLLABUS:-test_files/query_advanced_1.md}}"
VECTOR_STORE_NAME="${VECTOR_STORE_NAME:-${BENCH_DEFAULT_VECTOR_STORE:-agentic-research-dgx}}"
REPORT_WARMUP="${REPORT_WARMUP:-${BENCH_DEFAULT_REPORT_WARMUP:-}}"
DROP_WORST_RUN="${DROP_WORST_RUN:-${BENCH_DEFAULT_DROP_WORST:-}}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-${BENCH_DEFAULT_TIMEOUT:-}}"
KEEP_SERVICES="${KEEP_SERVICES:-${BENCH_DEFAULT_KEEP_SERVICES:-false}}"
OUTPUT_BASE="${BENCH_DEFAULT_OUTPUT_BASE:-benchmarks}"

if [ -z "$MODELS_RAW" ]; then
  MODELS_RAW="${BENCH_DEFAULT_MODELS:-}"
fi

if [ -n "$MODELS_RAW" ]; then
  IFS=',' read -r -a SETUPS <<< "$MODELS_RAW"
  trimmed=()
  for item in "${SETUPS[@]}"; do
    item="${item#"${item%%[![:space:]]*}"}"
    item="${item%"${item##*[![:space:]]}"}"
    if [ -n "$item" ]; then
      trimmed+=("$item")
    fi
  done
  SETUPS=("${trimmed[@]}")
else
  SETUPS=("${DEFAULT_SETUPS[@]}")
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

KEEP_SERVICES_FLAG=""
if [ "$KEEP_SERVICES" = "true" ]; then
  KEEP_SERVICES_FLAG="--keep-services"
elif [ "$KEEP_SERVICES" = "false" ]; then
  KEEP_SERVICES_FLAG="--no-keep-services"
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="${OUTPUT_BASE}/run_${TIMESTAMP}"

echo "========================================"
echo "Benchmarking All Setups"
echo "========================================"
echo "Output directory: $OUTPUT_DIR"
echo "Setups to benchmark: ${SETUPS[*]}"
echo "Runs per setup: $RUNS"
if [ "$INTERACTIVE" = true ]; then
  echo "Mode: interactive"
else
  echo "Mode: automatic (no prompt)"
fi
echo ""

for SETUP in "${SETUPS[@]}"; do
  echo ""
  echo "========================================"
  echo "Setup: $SETUP"
  echo "========================================"

  setup_log_dir="${OUTPUT_DIR}/${SETUP}"
  setup_log_file="${setup_log_dir}/failure.log"
  mkdir -p "$setup_log_dir"

  if [ "$INTERACTIVE" = true ]; then
    read -p "Benchmark $SETUP? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      echo "⏭️  Skipping $SETUP"
      continue
    fi
  fi

  setup_config_override=""
  if [ -f "$BENCHMARK_CONFIG" ]; then
    setup_config_override=$(python3 - "$BENCHMARK_CONFIG" "$SETUP" <<'PY'
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

  if [ -n "$setup_config_override" ]; then
    EFFECTIVE_CONFIG_FILE="$setup_config_override"
  elif [ -n "$CLI_CONFIG_FILE" ]; then
    EFFECTIVE_CONFIG_FILE="$CLI_CONFIG_FILE"
  else
    EFFECTIVE_CONFIG_FILE="$CONFIG_FILE_DEFAULT"
  fi

  ./scripts/benchmark-dgx.sh "$SETUP" \
    --benchmark-config "$BENCHMARK_CONFIG" \
    --config "$EFFECTIVE_CONFIG_FILE" \
    --syllabus "$SYLLABUS_FILE" \
    --runs "$RUNS" \
    --output-dir "$OUTPUT_DIR" \
    --vector-store-name "$VECTOR_STORE_NAME" \
    $REPORT_WARMUP_FLAG \
    $DROP_WORST_FLAG \
    ${TIMEOUT_SECONDS:+--timeout-seconds "$TIMEOUT_SECONDS"} \
    $KEEP_SERVICES_FLAG 2>&1 | tee "$setup_log_file"
  status=${PIPESTATUS[0]}
  if [ $status -ne 0 ]; then
    ts=$(date +%Y%m%d_%H%M%S)
    cat > "${setup_log_dir}/benchmark_result.json" <<EOF
{
  "setup_metadata": { "setup_name": "${SETUP}" },
  "status": "FAILED",
  "timestamp": "${ts}",
  "syllabus_file": "${SYLLABUS_FILE}",
  "runs": [],
  "average": {},
  "error_message": "Benchmark failed for ${SETUP}. See failure log.",
  "log_file": "${setup_log_file}"
}
EOF
    echo "❌ Benchmark failed for $SETUP"
    continue
  fi
done

echo ""
echo "========================================"
echo "All Benchmarks Completed!"
echo "========================================"

# Generate comparison table
echo "📊 Generating comparison table..."
docker compose -f docker-compose.yml -f docker-compose.dgx.yml --env-file models.env run --rm agentic-research \
  compare-benchmarks --benchmark-dir "/app/$OUTPUT_DIR"

echo ""
echo "✅ Comparison table saved to: $OUTPUT_DIR/comparison_table.md"
echo ""
