#!/usr/bin/env bash
# Helper sourced by start/stop-docker-dgx.sh. Resolves the active overlay
# from the current `models.env` symlink + benchmark setup_compose_map,
# so the standalone scripts work with any backend (llama.cpp duo, vLLM
# mono, ...) and not just the legacy hardcoded duo overlay (#182).
#
# Exports:
#   RESOLVED_SETUP    — setup name (e.g. "openai", "vllm-gptoss20b-mono")
#                       or empty if models.env is not a symlink we recognize.
#   RESOLVED_OVERLAY  — overlay file (e.g. "docker-compose.dgx.yml" or
#                       "docker-compose.dgx-vllm-gptoss20b-mono.yml").

BENCHMARK_CONFIG="${BENCHMARK_CONFIG:-configs/benchmark-default.yaml}"
DEFAULT_OVERLAY="docker-compose.dgx.yml"

RESOLVED_SETUP=""
if [ -L models.env ]; then
  target=$(readlink models.env)
  # Expected pattern: models/models.<setup>.env
  base=$(basename "$target")            # models.<setup>.env
  setup="${base#models.}"               # <setup>.env
  setup="${setup%.env}"                 # <setup>
  RESOLVED_SETUP="$setup"
fi

RESOLVED_OVERLAY="$DEFAULT_OVERLAY"
if [ -n "$RESOLVED_SETUP" ] && [ -f "$BENCHMARK_CONFIG" ]; then
  override=$(python3 - "$BENCHMARK_CONFIG" "$RESOLVED_SETUP" <<'PY' 2>/dev/null || true
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
  if [ -n "$override" ]; then
    RESOLVED_OVERLAY="$override"
  fi
fi

export RESOLVED_SETUP RESOLVED_OVERLAY
