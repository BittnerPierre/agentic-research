#!/usr/bin/env bash
# Compare benchmark results
set -euo pipefail

BENCHMARK_DIR=${1:-}

if [ -z "$BENCHMARK_DIR" ]; then
  echo "Usage: $0 <benchmark_dir>"
  echo ""
  echo "Example:"
  echo "  $0 benchmarks/run_20260211_143022"
  exit 1
fi

if [ ! -d "$BENCHMARK_DIR" ]; then
  echo "Error: Directory not found: $BENCHMARK_DIR"
  exit 1
fi

echo "========================================"
echo "Comparing Benchmarks"
echo "========================================"
echo "Directory: $BENCHMARK_DIR"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/_resolve-overlay.sh
. "$SCRIPT_DIR/_resolve-overlay.sh"

# compare-benchmarks only reads JSON files on disk — `--no-deps` avoids
# spinning up unrelated services (chromadb/embeddings/llm) on the active
# overlay just for a static comparison.
docker compose -f docker-compose.yml -f "$RESOLVED_OVERLAY" --env-file models.env \
  run --rm --no-deps agentic-research \
  compare-benchmarks --benchmark-dir "/app/$BENCHMARK_DIR"

OUTPUT_FILE="${BENCHMARK_DIR}/comparison_table.md"

if [ -f "$OUTPUT_FILE" ]; then
  echo ""
  echo "✅ Comparison table saved to: $OUTPUT_FILE"
  echo ""
  echo "View with:"
  echo "  cat $OUTPUT_FILE"
  echo "  or"
  echo "  glow $OUTPUT_FILE  # if glow is installed"
fi
