#!/usr/bin/env bash
# Benchmark all model setups on DGX
set -euo pipefail

AUTO_MODE=${1:-}

SETUPS=("ministral" "mistralai" "glm" "qwen" "openai")

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="benchmarks/run_${TIMESTAMP}"

echo "========================================"
echo "Benchmarking All Setups"
echo "========================================"
echo "Output directory: $OUTPUT_DIR"
echo "Setups to benchmark: ${SETUPS[*]}"
echo ""

for SETUP in "${SETUPS[@]}"; do
  echo ""
  echo "========================================"
  echo "Setup: $SETUP"
  echo "========================================"

  if [ "$AUTO_MODE" != "--auto" ]; then
    read -p "Benchmark $SETUP? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      echo "⏭️  Skipping $SETUP"
      continue
    fi
  fi

  # Run benchmark for this setup
  ./scripts/benchmark-setup-dgx.sh "$SETUP" || {
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
