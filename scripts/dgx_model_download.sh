#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(pwd)"
MODELS_ENV_FILE="${MODELS_ENV_FILE:-${ROOT_DIR}/models.env}"
if [[ -f "${MODELS_ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${MODELS_ENV_FILE}"
fi
# MODELS_DIR from models.env points to the hub/ directory (mounted in Docker).
# HF_HOME must be the parent directory, because hf download creates hub/ inside it.
MODELS_DIR="${MODELS_DIR:-${HOME}/.cache/huggingface/hub}"
HF_HOME_DIR="${MODELS_DIR%/hub}"

EMBEDDINGS_MODEL_REPO="${EMBEDDINGS_MODEL_REPO:-Qwen/Qwen3-Embedding-4B-GGUF}"
EMBEDDINGS_GGUF_PATTERN="${EMBEDDINGS_GGUF_PATTERN:-Qwen3-Embedding-4B-Q8_0.gguf}"

LLM_INSTRUCT_MODEL_REPO="${LLM_INSTRUCT_MODEL_REPO:-ggml-org/gpt-oss-20b-GGUF}"
INSTRUCT_GGUF_PATTERN="${INSTRUCT_GGUF_PATTERN:-gpt-oss-20b-mxfp4.gguf}"

LLM_REASONING_MODEL_REPO="${LLM_REASONING_MODEL_REPO:-mistralai/Ministral-3-14B-Reasoning-2512}"
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

echo "HF_HOME=${HF_HOME_DIR} (downloads will go to ${HF_HOME_DIR}/hub/)"

echo "Downloading embeddings model: ${EMBEDDINGS_MODEL_REPO} (${EMBEDDINGS_GGUF_PATTERN})"
HF_HOME="${HF_HOME_DIR}" HF_TOKEN="${HF_TOKEN}" hf download "${EMBEDDINGS_MODEL_REPO}" \
  --include "${EMBEDDINGS_GGUF_PATTERN}"

echo "Downloading instruct model: ${LLM_INSTRUCT_MODEL_REPO} (${INSTRUCT_GGUF_PATTERN})"
HF_HOME="${HF_HOME_DIR}" HF_TOKEN="${HF_TOKEN}" hf download "${LLM_INSTRUCT_MODEL_REPO}" \
  --include "${INSTRUCT_GGUF_PATTERN}"

echo "Downloading reasoning model: ${LLM_REASONING_MODEL_REPO} (${REASONING_GGUF_PATTERN})"
HF_HOME="${HF_HOME_DIR}" HF_TOKEN="${HF_TOKEN}" hf download "${LLM_REASONING_MODEL_REPO}" \
  --include "${REASONING_GGUF_PATTERN}"

echo "Models downloaded to ${MODELS_DIR}"
