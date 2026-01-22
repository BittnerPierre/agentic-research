#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(pwd)"
MODELS_ENV_FILE="${MODELS_ENV_FILE:-${ROOT_DIR}/models.env}"
if [[ -f "${MODELS_ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${MODELS_ENV_FILE}"
fi
MODELS_DIR="${MODELS_DIR:-${HOME}/.cache/huggingface}"

EMBEDDINGS_REPO="${EMBEDDINGS_REPO:-Qwen/Qwen3-Embedding-4B-GGUF}"
EMBEDDINGS_GGUF_PATTERN="${EMBEDDINGS_GGUF_PATTERN:-Qwen3-Embedding-4B-Q8_0.gguf}"

INSTRUCT_REPO="${INSTRUCT_REPO:-ggml-org/gpt-oss-20b-GGUF}"
INSTRUCT_GGUF_PATTERN="${INSTRUCT_GGUF_PATTERN:-gpt-oss-20b-mxfp4.gguf}"

REASONING_REPO="${REASONING_REPO:-mistralai/Ministral-3-14B-Reasoning-2512}"
REASONING_GGUF_PATTERN="${REASONING_GGUF_PATTERN:-Ministral-3-14B-Reasoning-2512*.gguf}"

if ! command -v hf >/dev/null 2>&1; then
  echo "hf CLI not found. Install with: pipx install huggingface-hub" >&2
  exit 1
fi

if [[ -z "${HF_TOKEN:-}" ]]; then
  echo "HF_TOKEN is required (set it in .env or export it before running)." >&2
  exit 1
fi

mkdir -p "${MODELS_DIR}"

if hf auth login --help >/dev/null 2>&1; then
  echo "Logging in to Hugging Face..."
  HF_TOKEN="${HF_TOKEN}" hf auth login --token "${HF_TOKEN}" --add-to-git-credential >/dev/null || true
else
  echo "Skipping HF login (using token for downloads)."
fi

echo "Downloading embeddings model: ${EMBEDDINGS_REPO} (${EMBEDDINGS_GGUF_PATTERN})"
HF_HOME="${MODELS_DIR}" HF_TOKEN="${HF_TOKEN}" hf download "${EMBEDDINGS_REPO}" \
  --include "${EMBEDDINGS_GGUF_PATTERN}"

echo "Downloading instruct model: ${INSTRUCT_REPO} (${INSTRUCT_GGUF_PATTERN})"
HF_HOME="${MODELS_DIR}" HF_TOKEN="${HF_TOKEN}" hf download "${INSTRUCT_REPO}" \
  --include "${INSTRUCT_GGUF_PATTERN}"

echo "Downloading reasoning model: ${REASONING_REPO} (${REASONING_GGUF_PATTERN})"
HF_HOME="${MODELS_DIR}" HF_TOKEN="${HF_TOKEN}" hf download "${REASONING_REPO}" \
  --include "${REASONING_GGUF_PATTERN}"

echo "Models downloaded to ${MODELS_DIR}"
