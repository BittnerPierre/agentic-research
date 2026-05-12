#!/usr/bin/env bash
# Helper sourced by start/stop/logs/bench scripts. Resolves the active
# overlay from the current `models.env` symlink + benchmark setup_compose_map,
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
  # Use `uv run python3` so the parser inherits the project's pyyaml
  # dependency (declared in pyproject.toml). Using system python3 directly
  # used to fall back silently when pyyaml was missing on the host (codex
  # review on PR #193 caught this — ModuleNotFoundError was masked by a
  # 2>/dev/null + || true combo, leaving RESOLVED_OVERLAY on the default
  # without any warning).
  #
  # Stderr is no longer suppressed: any real error (broken YAML, missing
  # uv, etc.) now surfaces. `|| true` still kept so an empty result
  # (legitimate "setup not in map" case) does not abort the caller.
  if command -v uv >/dev/null 2>&1; then
    PY_CMD=(uv run --quiet python3)
  else
    echo "[_resolve-overlay] warning: uv not found, falling back to system python3; pyyaml must be installed in system python or RESOLVED_OVERLAY will stay on default ($DEFAULT_OVERLAY)" >&2
    PY_CMD=(python3)
  fi

  override=$("${PY_CMD[@]}" - "$BENCHMARK_CONFIG" "$RESOLVED_SETUP" <<'PY' || true
import sys
from pathlib import Path

import yaml

config_path = Path(sys.argv[1])
setup = sys.argv[2]
data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

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
