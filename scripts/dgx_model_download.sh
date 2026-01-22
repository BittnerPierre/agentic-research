#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(pwd)"
MODELS_DIR="${ROOT_DIR}/models"

EMBEDDINGS_REPO="${EMBEDDINGS_REPO:-Qwen/Qwen3-Embedding-4B-GGUF}"
EMBEDDINGS_GGUF_PATTERN="${EMBEDDINGS_GGUF_PATTERN:-Qwen3-Embedding-4B-Q8_0.gguf}"

INSTRUCT_REPO="${INSTRUCT_REPO:-ggml-org/gpt-oss-20b-GGUF}"
INSTRUCT_GGUF_PATTERN="${INSTRUCT_GGUF_PATTERN:-gpt-oss-20b-mxfp4.gguf}"

REASONING_REPO="${REASONING_REPO:-mistralai/Ministral-3-14B-Instruct-2512-GGUF}"
REASONING_GGUF_PATTERN="${REASONING_GGUF_PATTERN:-Ministral-3-14B-Instruct-2512.gguf}"

if ! command -v hf >/dev/null 2>&1; then
  echo "hf CLI not found. Install with: pipx install huggingface-hub" >&2
  exit 1
fi

if [[ -z "${HF_TOKEN:-}" ]]; then
  echo "HF_TOKEN is required (set it in .env or export it before running)." >&2
  exit 1
fi

mkdir -p "${MODELS_DIR}"

echo "Logging in to Hugging Face..."
HF_TOKEN="${HF_TOKEN}" hf login --token "${HF_TOKEN}" --add-to-git-credential >/dev/null

echo "Downloading embeddings model: ${EMBEDDINGS_REPO} (${EMBEDDINGS_GGUF_PATTERN})"
hf download "${EMBEDDINGS_REPO}" \
  --local-dir "${MODELS_DIR}" \
  --local-dir-use-symlinks False \
  --include "${EMBEDDINGS_GGUF_PATTERN}"

echo "Downloading instruct model: ${INSTRUCT_REPO} (${INSTRUCT_GGUF_PATTERN})"
hf download "${INSTRUCT_REPO}" \
  --local-dir "${MODELS_DIR}" \
  --local-dir-use-symlinks False \
  --include "${INSTRUCT_GGUF_PATTERN}"

echo "Downloading reasoning model: ${REASONING_REPO} (${REASONING_GGUF_PATTERN})"
hf download "${REASONING_REPO}" \
  --local-dir "${MODELS_DIR}" \
  --local-dir-use-symlinks False \
  --include "${REASONING_GGUF_PATTERN}"

echo "Models downloaded to ${MODELS_DIR}"
