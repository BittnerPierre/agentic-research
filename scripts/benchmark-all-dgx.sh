#!/usr/bin/env bash
# Benchmark all model setups on DGX
set -euo pipefail

SETUPS=("ministral" "mistralai" "glm" "qwen" "openai")
RUNS=3
INTERACTIVE=false
SYLLABUS="/app/test_files/query_advanced_1.md"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --runs)
      RUNS="${2:-}"
      shift 2
      ;;
    --interactive)
      INTERACTIVE=true
      shift
      ;;
    --syllabus)
      SYLLABUS="${2:-}"
      shift 2
      ;;
    --auto)
      # Backward-compatible no-op: default is already non-interactive.
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: $0 [--runs N] [--interactive] [--syllabus PATH]"
      exit 1
      ;;
  esac
done

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="benchmarks/run_${TIMESTAMP}"

echo "========================================"
echo "Benchmarking All Setups"
echo "========================================"
echo "Output directory: $OUTPUT_DIR"
echo "Setups to benchmark: ${SETUPS[*]}"
echo "Runs per setup: $RUNS"
echo "Syllabus: $SYLLABUS"
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

  if [ "$INTERACTIVE" = true ]; then
    read -p "Benchmark $SETUP? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      echo "⏭️  Skipping $SETUP"
      continue
    fi
  fi

  # Run benchmark for this setup
  ./scripts/benchmark-dgx.sh "$SETUP" \
    --runs "$RUNS" \
    --output-dir "$OUTPUT_DIR" \
    --syllabus "$SYLLABUS" || {
    echo "❌ Benchmark failed for $SETUP"
    continue
  }
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
